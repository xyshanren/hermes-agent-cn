"""Tests for the Jev decision-lane router (model_routing.decision, consumer #1).

See docs/plans/2026-09-25-jev-decision-layer-plan.md §6 Step 2.
No live network: HTTP is injected via ``_post``; clock via ``_clock``.
"""

import threading
import time
from types import SimpleNamespace

import pytest

from agent import jev_router
from agent.chat_completion_helpers import _apply_jev_lane


# ── build_state ───────────────────────────────────────────────────────────

def test_build_state_plain():
    assert jev_router.build_state("检查下服务状态") == "检查下服务状态"


def test_build_state_with_prev_context():
    state = jev_router.build_state("再帮我删除下吧", prev_user_text="既然 codebuddy 还在")
    assert state.startswith("[上一轮] 既然 codebuddy 还在")
    assert "[本轮] 再帮我删除下吧" in state


def test_build_state_truncation_preserves_head():
    state = jev_router.build_state("长" * 500)
    assert len(state) <= 302  # budget + ellipsis (2 chars)
    assert state.startswith("长")


def test_build_state_sanitizes_unusable_turns():
    assert jev_router.build_state("/status") == ""
    assert jev_router.build_state("继续", prev_user_text="/model") == "继续"
    assert jev_router.build_state("继续", prev_user_text="[CONTEXT COMPACTION — REFERENCE ONLY] x") == "继续"


def test_build_state_prev_excerpt_clamped():
    state = jev_router.build_state("继续", prev_user_text="前" * 400)
    assert "[本轮] 继续" in state
    assert len(state) < 300


# ── decide: success / validation / fail-open ─────────────────────────────

@pytest.fixture(autouse=True)
def _reset_circuit():
    jev_router._FAIL_STREAK = 0
    jev_router._COOLDOWN_UNTIL = 0.0
    jev_router._ENDPOINT_OK_CACHE.clear()
    yield
    jev_router._FAIL_STREAK = 0
    jev_router._COOLDOWN_UNTIL = 0.0
    jev_router._ENDPOINT_OK_CACHE.clear()


def _cfg(**kw):
    base = {"mode": "live", "endpoint": "http://127.0.0.1:8001", "allow_private": True}
    base.update(kw)
    return base


def _payload(tier="balanced", conf=0.9):
    return {"answers": {"tier": {"choice": tier, "confidence": conf,
                                 "probabilities": {tier: conf}}}, "input_tokens": 42}


def test_decide_success_returns_outcome():
    calls = []

    def fake_post(url, body, timeout_ms):
        calls.append((url, body, timeout_ms))
        return _payload("balanced", 0.87)

    out = jev_router.decide(_cfg(), "修一下这个报错", _post=fake_post)
    assert out["tier"] == "balanced"
    assert out["confidence"] == pytest.approx(0.87)
    assert "probabilities" in out and "latency_ms" in out
    url, body, timeout_ms = calls[0]
    assert url.endswith("/predict")
    assert timeout_ms == 500
    import json as _json
    assert "修一下这个报错" in _json.loads(body)["state"]


def test_decide_rejects_tier_outside_ladder():
    assert jev_router.decide(_cfg(), "看图", _post=lambda *a: _payload("vision", 0.9)) is None


def test_decide_fail_open_on_http_error():
    def boom(url, body, timeout_ms):
        raise OSError("conn refused")

    assert jev_router.decide(_cfg(), "x", _post=boom) is None


def test_decide_circuit_opens_after_failures_and_recovers():
    calls = {"n": 0}

    def boom(url, body, timeout_ms):
        calls["n"] += 1
        raise OSError("down")

    clock = {"t": 1000.0}
    cfg = _cfg(failure_threshold=2, cooldown_seconds=300)
    for _ in range(2):
        assert jev_router.decide(cfg, "x", _clock=lambda: clock["t"], _post=boom) is None
    assert calls["n"] == 2
    # Cooldown: no HTTP attempt at all.
    assert jev_router.decide(cfg, "x", _clock=lambda: clock["t"], _post=boom) is None
    assert calls["n"] == 2
    # After cooldown expiry the service is retried (still down → None, but attempted).
    clock["t"] += 301
    assert jev_router.decide(cfg, "x", _clock=lambda: clock["t"], _post=boom) is None
    assert calls["n"] == 3


def test_decide_success_resets_fail_streak():
    def boom(url, body, timeout_ms):
        raise OSError("down")

    cfg = _cfg(failure_threshold=3)
    jev_router.decide(cfg, "x", _post=boom)
    jev_router.decide(cfg, "x", _post=boom)
    assert jev_router._FAIL_STREAK == 2
    jev_router.decide(cfg, "x", _post=lambda *a: _payload("strong", 0.7))
    assert jev_router._FAIL_STREAK == 0


def test_decide_rejects_private_endpoint_without_flag():
    called = {"n": 0}

    def post(url, body, timeout_ms):
        called["n"] += 1
        return _payload()

    cfg = {"mode": "live", "endpoint": "http://127.0.0.1:8001"}  # no allow_private
    assert jev_router.decide(cfg, "x", _post=post) is None
    assert called["n"] == 0


def test_decide_rejects_non_http_scheme():
    assert jev_router.decide(_cfg(endpoint="ftp://127.0.0.1:8001"), "x",
                             _post=lambda *a: _payload()) is None


# ── _apply_jev_lane: mode/threshold/has_image gating ──────────────────────

def _result(model="tier:strong"):
    return SimpleNamespace(model=model, reason="默认规则", provider="auto")


def test_lane_noop_when_no_decision_config():
    r = _result()
    _apply_jev_lane({}, r, "x", "", False)
    assert r.model == "tier:strong"


def test_lane_noop_when_mode_off():
    r = _result()
    _apply_jev_lane({"decision": {"mode": "off"}}, r, "x", "", False)
    assert r.model == "tier:strong"


def test_lane_shadow_logs_but_never_applies(monkeypatch):
    monkeypatch.setattr(jev_router, "decide",
                        lambda cfg, u, p="": {"tier": "light", "confidence": 0.9,
                                              "probabilities": {}, "latency_ms": 5.0})
    r = _result()
    _apply_jev_lane({"decision": {"mode": "shadow", "threshold": 0.6}}, r, "x", "", False)
    assert r.model == "tier:strong"  # unchanged


def test_lane_live_applies_when_confident(monkeypatch):
    monkeypatch.setattr(jev_router, "decide",
                        lambda cfg, u, p="": {"tier": "balanced", "confidence": 0.87,
                                              "probabilities": {}, "latency_ms": 5.0})
    r = _result()
    _apply_jev_lane({"decision": {"mode": "live", "threshold": 0.6}}, r, "x", "", False)
    assert r.model == "tier:balanced"
    assert "Jev" in r.reason


def test_lane_live_keeps_baseline_below_threshold(monkeypatch):
    monkeypatch.setattr(jev_router, "decide",
                        lambda cfg, u, p="": {"tier": "balanced", "confidence": 0.44,
                                              "probabilities": {}, "latency_ms": 5.0})
    r = _result()
    _apply_jev_lane({"decision": {"mode": "live", "threshold": 0.6}}, r, "x", "", False)
    assert r.model == "tier:strong"


def test_lane_live_upgrade_to_flagship_allowed(monkeypatch):
    monkeypatch.setattr(jev_router, "decide",
                        lambda cfg, u, p="": {"tier": "flagship", "confidence": 0.75,
                                              "probabilities": {}, "latency_ms": 5.0})
    r = _result()
    _apply_jev_lane({"decision": {"mode": "live", "threshold": 0.6}}, r, "x", "", False)
    assert r.model == "tier:flagship"


def test_lane_same_tier_no_mutation(monkeypatch):
    monkeypatch.setattr(jev_router, "decide",
                        lambda cfg, u, p="": {"tier": "strong", "confidence": 0.9,
                                              "probabilities": {}, "latency_ms": 5.0})
    r = _result()
    _apply_jev_lane({"decision": {"mode": "live", "threshold": 0.6}}, r, "x", "", False)
    assert r.model == "tier:strong"
    assert r.reason == "默认规则"  # untouched


def test_lane_skips_image_turns(monkeypatch):
    called = {"n": 0}

    def fake_decide(*a, **kw):
        called["n"] += 1
        return {"tier": "balanced", "confidence": 0.9, "probabilities": {}, "latency_ms": 1.0}

    monkeypatch.setattr(jev_router, "decide", fake_decide)
    r = _result()
    _apply_jev_lane({"decision": {"mode": "live"}}, r, "看这张图", "", True)
    assert called["n"] == 0
    assert r.model == "tier:strong"


def test_lane_fail_open_when_service_down(monkeypatch):
    monkeypatch.setattr(jev_router, "decide", lambda *a, **kw: None)
    r = _result()
    _apply_jev_lane({"decision": {"mode": "live"}}, r, "x", "", False)
    assert r.model == "tier:strong"

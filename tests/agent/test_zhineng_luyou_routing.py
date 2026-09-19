"""CN SmartRouter (zhineng_luyou) + model_routing seam tests.

The SmartRouter module was restored from the v0.12-v0.17 implementation
after the v0.19.1/v0.20.0 base-bump rewrite dropped it.  These tests pin
the behavior contracts that the runtime seam (``chat_completion_helpers
._apply_model_routing``) and the ``model_routing.rules`` config surface
(written by ``hermes quickstart`` and the CAND-080 patch queue) rely on:

- Rule matching semantics: keywords+threshold, max_length, has_image,
  exclude_keywords, complexity — ALL specified conditions must hold.
- ``route_with_rules`` stage order: rules → unconditional default rule →
  legacy vision/reasoning/default → capability-aware fallback.
- HealthTracker circuit breaker: threshold trips, cooldown recovers,
  success resets.
- The ``_apply_model_routing`` seam: applies a matched rule once per
  turn, skips when routing is disabled or a runtime fallback is active.

Pure unit tests — no network probes (the capability-fallback stage is
stubbed), no filesystem.
"""

from types import SimpleNamespace

import pytest

from agent.zhineng_luyou import (
    CIRCUIT_BREAKER_COOLDOWN,
    CIRCUIT_BREAKER_THRESHOLD,
    HealthTracker,
    RoutingRule,
    SmartRouter,
    analyze_complexity,
    TaskComplexity,
)
from agent.chat_completion_helpers import _apply_model_routing, _SMARTROUTER_CACHE


# ── Rule matching semantics ──────────────────────────────────────────────


class TestMatchRule:
    M = staticmethod(SmartRouter._match_rule)

    def test_has_image_condition(self):
        assert self.M({"has_image": True}, True, "", 0)
        assert not self.M({"has_image": True}, False, "", 0)
        assert self.M({"has_image": False}, False, "", 0)

    def test_keywords_any_match_by_default(self):
        match = {"keywords": ["写代码", "函数"]}
        assert self.M(match, False, "帮我写代码", 6)
        assert not self.M(match, False, "今天天气怎么样", 7)

    def test_keywords_threshold_requires_n_hits(self):
        match = {"keywords": ["写代码", "函数", "class"], "threshold": 2}
        assert self.M(match, False, "写代码：一个 class", 12)
        assert not self.M(match, False, "写代码", 3)

    def test_max_length_condition(self):
        assert self.M({"max_length": 10}, False, "abc", 3)
        assert not self.M({"max_length": 10}, False, "a" * 11, 11)

    def test_exclude_keywords_disqualify(self):
        match = {"keywords": ["代码"], "exclude_keywords": ["报错", "bug"]}
        assert self.M(match, False, "帮我看看这段代码", 8)
        assert not self.M(match, False, "这段代码有个 bug", 10)

    def test_complexity_condition(self):
        assert self.M({"complexity": "complex"}, False, "", 0, complexity="complex")
        assert not self.M({"complexity": "complex"}, False, "", 0, complexity="simple")

    def test_all_conditions_must_hold(self):
        match = {"keywords": ["代码"], "max_length": 20, "exclude_keywords": ["bug"]}
        assert self.M(match, False, "看看代码", 4)
        assert not self.M(match, False, "看看代码" + "x" * 30, 34)

    def test_empty_conditions_match_everything(self):
        """A rule with no conditions matches — used as the default rule."""
        assert self.M({}, False, "", 0)
        assert self.M({}, True, "anything", 8)


# ── RoutingRule parsing ──────────────────────────────────────────────────


class TestRoutingRule:

    def test_from_dict_full(self):
        rule = RoutingRule.from_dict({
            "name": "coding",
            "match": {"keywords": ["写代码"], "threshold": 1},
            "model": "deepseek-coder",
            "provider": "deepseek",
            "priority": 2,
        })
        assert rule.name == "coding"
        assert rule.model == "deepseek-coder"
        assert rule.provider == "deepseek"
        assert rule.priority == 2
        assert rule.match == {"keywords": ["写代码"], "threshold": 1}

    def test_from_dict_minimal(self):
        rule = RoutingRule.from_dict({"name": "default", "model": "qwen3:32b"})
        assert rule.match == {}
        assert rule.provider == ""
        assert rule.priority == 0


# ── Complexity analysis ──────────────────────────────────────────────────


class TestAnalyzeComplexity:

    def test_simple_keywords(self):
        assert analyze_complexity("你好") == TaskComplexity.SIMPLE
        assert analyze_complexity("hello there") == TaskComplexity.SIMPLE

    def test_complex_keywords(self):
        assert analyze_complexity("帮我设计一个系统架构方案") == TaskComplexity.COMPLEX

    def test_default_is_medium(self):
        # Length heuristic: 50-499 chars with no simple/complex keywords
        # lands in MEDIUM.
        message = "我们聊聊接下来一个季度的安排" + "，包括一些日常事务。" * 4
        assert 50 <= len(message) <= 500
        assert analyze_complexity(message) == TaskComplexity.MEDIUM


# ── route_with_rules stage order ─────────────────────────────────────────


def _router():
    """A SmartRouter without any config — stages 1/2 are config-driven and
    deterministic; stage 3 (capability probing) is stubbed per-test."""
    return SmartRouter({})


class TestRouteWithRules:

    def test_matching_rule_wins(self):
        router = _router()
        rules = [
            RoutingRule.from_dict({
                "name": "coding",
                "match": {"keywords": ["写代码"]},
                "model": "deepseek-coder",
                "provider": "deepseek",
            }),
            RoutingRule.from_dict({"name": "default", "model": "qwen3:32b"}),
        ]
        result = router.route_with_rules("帮我写代码", rules=rules)
        assert result.model == "deepseek-coder"
        assert result.provider == "deepseek"

    def test_unconditional_default_rule_used_when_nothing_matches(self):
        router = _router()
        rules = [
            RoutingRule.from_dict({
                "name": "coding",
                "match": {"keywords": ["写代码"]},
                "model": "deepseek-coder",
            }),
            RoutingRule.from_dict({"name": "default", "model": "qwen3:32b"}),
        ]
        result = router.route_with_rules("今天天气不错", rules=rules)
        assert result.model == "qwen3:32b"
        assert result.provider == "auto"

    def test_conditional_rule_without_hit_skipped(self):
        """A conditional rule that doesn't match must NOT swallow the turn —
        the default rule still applies."""
        router = _router()
        rules = [
            RoutingRule.from_dict({
                "name": "vision",
                "match": {"has_image": True},
                "model": "qwen3-vl:8b",
            }),
        ]
        # No default rule and no local/cloud routing desired in this test —
        # fall-through to route() which we stub.
        router.route = lambda *a, **k: "FALLTHROUGH"  # type: ignore[method-assign]
        result = router.route_with_rules("纯文本消息", rules=rules, has_image=False)
        assert result == "FALLTHROUGH"

    def test_legacy_vision_config(self):
        router = _router()
        result = router.route_with_rules(
            "看看这张图",
            legacy_cfg={"vision": {"model": "qwen3-vl:8b"}},
            has_image=False,
        )
        assert result.model == "qwen3-vl:8b"
        assert result.reason == "旧格式: vision关键词"

    def test_legacy_default_config(self):
        router = _router()
        result = router.route_with_rules(
            "随便说点什么",
            legacy_cfg={"default": {"model": "qwen3:32b"}},
        )
        assert result.model == "qwen3:32b"
        assert result.reason == "旧格式: default"


# ── HealthTracker circuit breaker ────────────────────────────────────────


class TestHealthTracker:

    def test_no_history_not_circuited(self):
        tracker = HealthTracker()
        assert tracker.is_circuited("ollama", "qwen3:8b") is False

    def test_failures_below_threshold_not_circuited(self):
        tracker = HealthTracker()
        tracker.record_failure("ollama", "qwen3:8b")
        assert tracker.is_circuited("ollama", "qwen3:8b") is False

    def test_consecutive_failures_trip_breaker(self):
        tracker = HealthTracker()
        for _ in range(CIRCUIT_BREAKER_THRESHOLD):
            tracker.record_failure("ollama", "qwen3:8b")
        assert tracker.is_circuited("ollama", "qwen3:8b") is True

    def test_success_resets_failure_streak(self):
        tracker = HealthTracker()
        tracker.record_failure("ollama", "qwen3:8b")
        tracker.record_success("ollama", "qwen3:8b")
        tracker.record_failure("ollama", "qwen3:8b")
        assert tracker.is_circuited("ollama", "qwen3:8b") is False

    def test_cooldown_recover(self, monkeypatch):
        import time as _time

        tracker = HealthTracker()
        before = _time.time()
        for _ in range(CIRCUIT_BREAKER_THRESHOLD):
            tracker.record_failure("ollama", "qwen3:8b")
        assert tracker.is_circuited("ollama", "qwen3:8b") is True
        # Simulate the cooldown elapsing (module reads time.time()).
        monkeypatch.setattr(
            "agent.zhineng_luyou.time.time",
            lambda: before + CIRCUIT_BREAKER_COOLDOWN + 1,
        )
        assert tracker.is_circuited("ollama", "qwen3:8b") is False

    def test_filter_drops_circuited_candidates(self):
        tracker = HealthTracker()
        for _ in range(CIRCUIT_BREAKER_THRESHOLD):
            tracker.record_failure("ollama", "bad-model")
        healthy = SimpleNamespace(provider="ollama", backend="ollama", name="good-model")
        broken = SimpleNamespace(provider="ollama", backend="ollama", name="bad-model")
        filtered = tracker.filter([healthy, broken])
        assert [c.name for c in filtered] == ["good-model"]


# ── _apply_model_routing seam ────────────────────────────────────────────


def _agent(**overrides):
    base = dict(
        provider="auto",
        model="default-model",
        api_key=None,
        _routing_applied=False,
        _disable_model_routing=False,
        _fallback_activated=False,
        _user_turn_count=1,
    )
    base.update(overrides)
    return SimpleNamespace(**base)


@pytest.fixture(autouse=True)
def _reset_router_cache():
    _SMARTROUTER_CACHE.clear()
    yield
    _SMARTROUTER_CACHE.clear()


def _patch_rules(monkeypatch, route_cfg):
    monkeypatch.setattr(
        "hermes_cli.config.load_config",
        lambda: {"model_routing": route_cfg},
        raising=False,
    )


class TestApplyModelRouting:

    def test_matched_rule_switches_model(self, monkeypatch):
        _patch_rules(monkeypatch, {
            "rules": [
                {"name": "coding", "match": {"keywords": ["写代码"]}, "model": "deepseek-coder"},
                {"name": "default", "model": "qwen3:32b"},
            ],
        })
        agent = _agent()
        _apply_model_routing(agent, [{"role": "user", "content": "帮我写代码"}])
        assert agent.model == "deepseek-coder"
        assert agent._routing_applied is True

    def test_default_rule_used_when_no_match(self, monkeypatch):
        _patch_rules(monkeypatch, {
            "rules": [
                {"name": "coding", "match": {"keywords": ["写代码"]}, "model": "deepseek-coder"},
                {"name": "default", "model": "qwen3:32b"},
            ],
        })
        agent = _agent()
        _apply_model_routing(agent, [{"role": "user", "content": "天气怎么样"}])
        assert agent.model == "qwen3:32b"

    def test_runs_once_per_turn(self, monkeypatch):
        _patch_rules(monkeypatch, {
            "rules": [{"name": "default", "model": "qwen3:32b"}],
        })
        agent = _agent()
        _apply_model_routing(agent, [{"role": "user", "content": "hi"}])
        assert agent.model == "qwen3:32b"
        # A second call in the same turn is a no-op — the model stays.
        agent.model = "manually-switched"
        _apply_model_routing(agent, [{"role": "user", "content": "different"}])
        assert agent.model == "manually-switched"

    def test_skips_when_fallback_activated(self, monkeypatch):
        _patch_rules(monkeypatch, {
            "rules": [{"name": "default", "model": "qwen3:32b"}],
        })
        agent = _agent(_fallback_activated=True)
        _apply_model_routing(agent, [{"role": "user", "content": "hi"}])
        assert agent.model == "default-model"

    def test_skips_when_disabled(self, monkeypatch):
        _patch_rules(monkeypatch, {
            "rules": [{"name": "default", "model": "qwen3:32b"}],
        })
        agent = _agent(_disable_model_routing=True)
        _apply_model_routing(agent, [{"role": "user", "content": "hi"}])
        assert agent.model == "default-model"

    def test_no_routing_config_is_noop(self, monkeypatch):
        monkeypatch.setattr(
            "hermes_cli.config.load_config", lambda: {}, raising=False,
        )
        agent = _agent()
        _apply_model_routing(agent, [{"role": "user", "content": "hi"}])
        assert agent.model == "default-model"

    def test_has_image_flag_reaches_rules(self, monkeypatch):
        """Multimodal content blocks set has_image=True so vision rules match."""
        _patch_rules(monkeypatch, {
            "rules": [
                {"name": "vision", "match": {"has_image": True}, "model": "qwen3-vl:8b"},
                {"name": "default", "model": "qwen3:32b"},
            ],
        })
        agent = _agent()
        _apply_model_routing(agent, [{
            "role": "user",
            "content": [
                {"type": "text", "text": "这是什么"},
                {"type": "image_url", "image_url": {"url": "data:image/png;base64,..."}},
            ],
        }])
        assert agent.model == "qwen3-vl:8b"

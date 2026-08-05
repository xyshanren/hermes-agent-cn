"""CAND-072: lightweight router tool unit tests.

Covers ``tools.lightweight_router_tool.lightweight_router`` — the
agent-facing pre-selector for a worker pool. v1 ships a pure-Python
heuristic (Jaccard keyword overlap + softmax); the test surface
focuses on the *shape* the tool exposes so a future trained
replacement (CAND-073) can drop in without breaking the contract.

These tests are pure-Python (no network, no LLM, no WSL, no model
load). The heuristic is deterministic so the same input always
produces the same scores — making the confidence / margin /
fallback-recommended verdicts reproducible across runs.
"""

import json

import pytest

from tools import lightweight_router_tool as lr


# ── Fixtures / helpers ─────────────────────────────────────────────────


# A small worker pool that lets each test pin a specific behavioural
# expectation (e.g. "the coding-tagged worker should win on a
# code query"). Names are stable so callers can assert on them.
SAMPLE_WORKERS = [
    {
        "name": "kimi-coding",
        "description": "chinese coding assistant fast",
        "tags": ["python", "code", "chinese"],
    },
    {
        "name": "deepseek",
        "description": "chinese general purpose",
        "tags": ["chinese", "fast", "general"],
    },
    {
        "name": "anthropic",
        "description": "english reasoning opus",
        "tags": ["english", "reasoning"],
    },
]


# ── list_models / describe (smoke + shape) ─────────────────────────────


class TestListModelsAndDescribe:
    """The metadata actions exist so an operator can ask "is the
    model loaded?" / "what does the heuristic actually do?" without
    reading source. Their shape must stay stable across CAND-073's
    trained-model replacement — only ``models`` grows.
    """

    def test_list_models_returns_supported_set(self):
        payload = json.loads(lr.lightweight_router(action="list_models"))
        assert payload["success"] is True
        ids = [m["id"] for m in payload["models"]]
        # v1 ships only the heuristic mock; CAND-073 will add entries
        # but the existing one must stay (so callers that branch on
        # ``"mock-heuristic-v1"`` keep working).
        assert "mock-heuristic-v1" in ids
        for m in payload["models"]:
            assert "id" in m
            assert "loaded_locally" in m
            assert isinstance(m["loaded_locally"], bool)

    def test_describe_returns_heuristic_shape(self):
        payload = json.loads(lr.lightweight_router(action="describe"))
        assert payload["success"] is True
        # Stable fields a future trained router must keep so the
        # operator-facing explanation doesn't drift.
        assert payload["heuristic"] == "keyword_overlap_v1"
        assert "scoring" in payload
        assert "softmax" in payload
        assert "thresholds" in payload
        assert payload["model_loaded"] is False  # v1: no real model
        # CAND-073 will flip this to True; until then, the
        # "model_loaded: false" is the operator's signal that the
        # scores are heuristic-init.
        assert "CAND-073" in payload["note"]


# ── route: happy path + fallback semantics ─────────────────────────────


class TestRouteHappyPath:
    def test_route_picks_strongest_match(self):
        """A query that overlaps strongly with one worker's tokens
        wins over workers with weaker overlap. The pick is the
        worker with the highest softmax probability, not the raw
        Jaccard score (softmax normalises so a single strong match
        beats a few weak ones).
        """
        payload = json.loads(
            lr.lightweight_router(
                action="route",
                query="write python function to sort list",
                workers=SAMPLE_WORKERS,
            )
        )
        assert payload["success"] is True
        # kimi-coding's tags include "python" + "code" — a strong
        # overlap with the query.
        assert payload["picked_worker"] == "kimi-coding"
        assert payload["confidence"] > 0
        # Per-worker scores must include every input worker.
        assert set(payload["scores"]) == {
            "kimi-coding", "deepseek", "anthropic"
        }
        for name, info in payload["scores"].items():
            assert "raw" in info
            assert "prob" in info
            assert 0.0 <= info["prob"] <= 1.0
        # Sum of probs is 1.0 (within float epsilon).
        total = sum(info["prob"] for info in payload["scores"].values())
        assert abs(total - 1.0) < 1e-9

    def test_route_with_no_token_overlap_returns_none_and_recommends_fallback(self):
        """Query has no token overlap with any worker → all Jaccard
        scores are 0 → softmax gives uniform distribution → pick
        is set to ``None`` and ``fallback_recommended`` is True.
        The tool surfaces "no signal" rather than silently picking
        the first worker (UX 倒退 1:1 — a silent wrong pick would
        be worse than a visible "I don't know").
        """
        payload = json.loads(
            lr.lightweight_router(
                action="route",
                query="completely unrelated topic about cooking",
                workers=SAMPLE_WORKERS,
            )
        )
        assert payload["success"] is True
        assert payload["picked_worker"] is None
        assert payload["confidence"] == 0.0
        assert payload["margin"] == 0.0
        assert payload["fallback_recommended"] is True
        # Every score is 0 — the operator can see why the pick is None.
        for info in payload["scores"].values():
            assert info["raw"] == 0.0
            assert info["prob"] > 0  # softmax still distributes 1/N

    def test_route_low_confidence_recommends_fallback(self):
        """Even with a strong match, heuristic-init v1 doesn't push
        confidence above the 0.5 default threshold; the tool surfaces
        the recommendation rather than hiding it. A caller that
        trusts the pick anyway can read ``picked_worker`` directly.
        """
        payload = json.loads(
            lr.lightweight_router(
                action="route",
                query="english essay about ethics",
                workers=SAMPLE_WORKERS,
            )
        )
        # anthropic's tags include "english" + "reasoning" — it wins.
        assert payload["picked_worker"] == "anthropic"
        # Heuristic-init is conservative: confidence stays under the
        # default 0.5. The fallback recommendation is the operator's
        # signal that a trained router (CAND-073) would do better.
        assert payload["confidence"] < 0.5
        assert payload["fallback_recommended"] is True

    def test_route_is_deterministic(self):
        """Same input → same output. Heuristic-init doesn't sample;
        if it did, the test suite would flake. The deterministic
        contract also lets the operator run a regression diff after
        changing the heuristic version.
        """
        kwargs = {
            "action": "route",
            "query": "write python function",
            "workers": SAMPLE_WORKERS,
        }
        first = json.loads(lr.lightweight_router(**kwargs))
        second = json.loads(lr.lightweight_router(**kwargs))
        assert first["picked_worker"] == second["picked_worker"]
        assert first["confidence"] == second["confidence"]
        assert first["scores"] == second["scores"]


# ── route: fail-fast gates (跟 sibling routing tools 1:1) ───────────────


class TestRouteFailFast:
    """Every gate is a separate test so a regression on any one of
    them surfaces a specific failure instead of a generic
    "route broke" — same fail-fast discipline as the other
    routing tools.
    """

    def test_missing_query_fails(self):
        payload = json.loads(
            lr.lightweight_router(
                action="route", workers=SAMPLE_WORKERS
            )
        )
        assert payload["success"] is False
        assert "query" in payload["error"]

    def test_empty_workers_fails(self):
        payload = json.loads(
            lr.lightweight_router(
                action="route", query="hello", workers=[]
            )
        )
        assert payload["success"] is False
        assert "empty" in payload["error"]

    def test_workers_not_a_list_fails(self):
        payload = json.loads(
            lr.lightweight_router(
                action="route", query="hello", workers={"kimi": {}}
            )
        )
        assert payload["success"] is False
        assert "list" in payload["error"]

    def test_worker_missing_name_fails(self):
        payload = json.loads(
            lr.lightweight_router(
                action="route",
                query="hello",
                workers=[{"description": "no name here"}],
            )
        )
        assert payload["success"] is False
        assert "name" in payload["error"]

    def test_duplicate_worker_names_fail(self):
        """Duplicate names would let two workers be silently treated
        as one (the score dict would clobber the earlier entry). The
        tool fails-fast so the operator can fix the input.
        """
        payload = json.loads(
            lr.lightweight_router(
                action="route",
                query="hello",
                workers=[
                    {"name": "kimi"},
                    {"name": "kimi"},
                ],
            )
        )
        assert payload["success"] is False
        assert "duplicated" in payload["error"]

    def test_confidence_threshold_out_of_range_fails(self):
        payload = json.loads(
            lr.lightweight_router(
                action="route",
                query="hello",
                workers=SAMPLE_WORKERS,
                confidence_threshold=1.5,
            )
        )
        assert payload["success"] is False
        assert "[0.0, 1.0]" in payload["error"]

    def test_unknown_action_fails(self):
        payload = json.loads(
            lr.lightweight_router(
                action="delete", query="hello", workers=SAMPLE_WORKERS
            )
        )
        assert payload["success"] is False
        assert "Unknown action" in payload["error"]
        # The error lists the known actions so a front-end typo
        # surfaces a clear menu instead of a dead end.
        for kw in ("route", "score", "list_models", "describe"):
            assert kw in payload["error"]


# ── score action (sub-routine surface for routing_ab_test, future) ─────


class TestScore:
    """The ``score`` action is the read-only side: returns the
    per-worker score dict without picking a winner or computing the
    fallback flag. This is the sub-routine surface CAND-073 / a
    future ``routing_ab_test`` will use to compare rule-based vs
    learned routing.
    """

    def test_score_returns_per_worker_dict_no_pick(self):
        payload = json.loads(
            lr.lightweight_router(
                action="score",
                query="write python",
                workers=SAMPLE_WORKERS,
            )
        )
        assert payload["success"] is True
        assert set(payload["scores"]) == {
            "kimi-coding", "deepseek", "anthropic"
        }
        # No pick-related fields — the score action is read-only.
        assert "picked_worker" not in payload
        assert "fallback_recommended" not in payload
        # Identifies the heuristic so a regression diff can pin
        # which scoring surface produced the numbers.
        assert payload["heuristic"] == "keyword_overlap_v1"
        assert payload["softmax_temperature"] == 1.0

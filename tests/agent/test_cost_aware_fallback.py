"""S12 P2 — CostAwareFallbackConfig + threshold checker unit tests.

Pure data-shaping tests — no network, no agent, no DB.  Keep this file
in the always-on CI tier; it's the contract pin for the user-facing
config knobs ``agent.cost_aware_fallback.{enabled, per_request_max_usd,
per_session_max_usd, on_session_exceeded}``.
"""

import math

from agent.cost_aware_fallback import (
    DEFAULT_ON_SESSION_EXCEEDED,
    DEFAULT_PER_REQUEST_MAX_USD,
    DEFAULT_PER_SESSION_MAX_USD,
    CostAwareFallbackConfig,
    check_request_cost_threshold,
    check_session_cost_threshold,
)


# ── Config parsing ───────────────────────────────────────────────────────


class TestCostAwareFallbackConfigFromDict:
    """The config layer must be defensive — broken YAML can't switch on
    a budget policy the user didn't ask for."""

    def test_empty_dict_yields_disabled_default(self):
        cfg = CostAwareFallbackConfig.from_dict({})
        assert cfg.enabled is False
        assert cfg.per_request_max_usd is None
        assert cfg.per_session_max_usd is None
        assert cfg.on_session_exceeded == DEFAULT_ON_SESSION_EXCEEDED

    def test_none_yields_disabled_default(self):
        cfg = CostAwareFallbackConfig.from_dict(None)
        assert cfg.enabled is False

    def test_non_dict_yields_disabled_default(self):
        """YAML parsing can produce strings / lists for a section if the
        user fat-fingers a key.  Never crash, never enable by accident."""
        for bad in ("hello", [1, 2, 3], 42, True):
            cfg = CostAwareFallbackConfig.from_dict(bad)
            assert cfg.enabled is False
            assert cfg.per_request_max_usd is None

    def test_full_explicit_config_parses(self):
        cfg = CostAwareFallbackConfig.from_dict({
            "enabled": True,
            "per_request_max_usd": 0.10,
            "per_session_max_usd": 2.5,
            "on_session_exceeded": "fallback",
        })
        assert cfg.enabled is True
        assert cfg.per_request_max_usd == 0.10
        assert cfg.per_session_max_usd == 2.5
        assert cfg.on_session_exceeded == "fallback"

    def test_invalid_on_session_exceeded_falls_back_to_warn(self):
        """The action enum is closed — an unknown value resets to 'warn'."""
        cfg = CostAwareFallbackConfig.from_dict({
            "enabled": True,
            "on_session_exceeded": "explode",
        })
        assert cfg.on_session_exceeded == "warn"

    def test_negative_threshold_becomes_none(self):
        """A negative budget is user-visible nonsense — treat as 'no limit'."""
        cfg = CostAwareFallbackConfig.from_dict({
            "enabled": True,
            "per_request_max_usd": -0.05,
            "per_session_max_usd": -1.0,
        })
        assert cfg.per_request_max_usd is None
        assert cfg.per_session_max_usd is None

    def test_zero_threshold_becomes_none(self):
        """Zero threshold would fire on every call — treat as unset."""
        cfg = CostAwareFallbackConfig.from_dict({
            "enabled": True,
            "per_request_max_usd": 0,
            "per_session_max_usd": 0,
        })
        assert cfg.per_request_max_usd is None
        assert cfg.per_session_max_usd is None

    def test_non_numeric_threshold_becomes_none(self):
        """Defensive against type confusion in YAML (bool / str)."""
        cfg = CostAwareFallbackConfig.from_dict({
            "enabled": True,
            "per_request_max_usd": "lots",
            "per_session_max_usd": None,
        })
        assert cfg.per_request_max_usd is None
        assert cfg.per_session_max_usd is None

    def test_nan_threshold_becomes_none(self):
        """NaN would silently never fire — drop it."""
        cfg = CostAwareFallbackConfig.from_dict({
            "enabled": True,
            "per_request_max_usd": float("nan"),
        })
        assert cfg.per_request_max_usd is None

    def test_default_constants_match_config_defaults(self):
        """The defaults baked into hermes_cli.config.DEFAULT_CONFIG and the
        defaults in cost_aware_fallback.py must stay in sync.  When the
        config default changes, update DEFAULT_PER_REQUEST_MAX_USD /
        DEFAULT_PER_SESSION_MAX_USD here too."""
        cfg = CostAwareFallbackConfig()
        assert cfg.per_request_max_usd is None  # module-level default
        # These constants are what config.py should mirror:
        assert DEFAULT_PER_REQUEST_MAX_USD == 0.05
        assert DEFAULT_PER_SESSION_MAX_USD == 1.00
        assert DEFAULT_ON_SESSION_EXCEEDED == "warn"


# ── Request threshold ────────────────────────────────────────────────────


class TestCheckRequestCostThreshold:

    def test_disabled_returns_none_even_when_over_threshold(self):
        cfg = CostAwareFallbackConfig(
            enabled=False, per_request_max_usd=0.01,
        )
        assert check_request_cost_threshold(1.0, cfg) is None

    def test_no_threshold_returns_none(self):
        cfg = CostAwareFallbackConfig(enabled=True, per_request_max_usd=None)
        assert check_request_cost_threshold(1.0, cfg) is None

    def test_below_threshold_returns_none(self):
        cfg = CostAwareFallbackConfig(
            enabled=True, per_request_max_usd=0.10,
        )
        assert check_request_cost_threshold(0.05, cfg) is None

    def test_above_threshold_returns_reason(self):
        cfg = CostAwareFallbackConfig(
            enabled=True, per_request_max_usd=0.05,
        )
        assert check_request_cost_threshold(0.06, cfg) == "request_budget_exceeded"

    def test_exactly_at_threshold_is_not_exceeded(self):
        """``>`` not ``>=`` — at the threshold we allow the call (it's
        'over the budget' semantically, not 'at or over')."""
        cfg = CostAwareFallbackConfig(
            enabled=True, per_request_max_usd=0.05,
        )
        assert check_request_cost_threshold(0.05, cfg) is None

    def test_none_cost_returns_none(self):
        """Unknown cost → no fire (the pricing table didn't have an entry)."""
        cfg = CostAwareFallbackConfig(
            enabled=True, per_request_max_usd=0.05,
        )
        assert check_request_cost_threshold(None, cfg) is None

    def test_nan_cost_returns_none(self):
        cfg = CostAwareFallbackConfig(
            enabled=True, per_request_max_usd=0.05,
        )
        assert check_request_cost_threshold(float("nan"), cfg) is None

    def test_negative_cost_returns_none(self):
        """Negative cost (refund / credit) — don't fire."""
        cfg = CostAwareFallbackConfig(
            enabled=True, per_request_max_usd=0.05,
        )
        assert check_request_cost_threshold(-0.10, cfg) is None

    def test_string_cost_returns_none(self):
        """Defensive — bad caller shouldn't crash."""
        cfg = CostAwareFallbackConfig(
            enabled=True, per_request_max_usd=0.05,
        )
        assert check_request_cost_threshold("not a number", cfg) is None  # type: ignore[arg-type]


# ── Session threshold ────────────────────────────────────────────────────


class TestCheckSessionCostThreshold:

    def test_disabled_returns_none(self):
        cfg = CostAwareFallbackConfig(
            enabled=False, per_session_max_usd=0.01,
        )
        assert check_session_cost_threshold(1.0, cfg) is None

    def test_below_threshold_returns_none(self):
        cfg = CostAwareFallbackConfig(
            enabled=True, per_session_max_usd=1.0,
        )
        assert check_session_cost_threshold(0.5, cfg) is None

    def test_above_threshold_returns_reason(self):
        cfg = CostAwareFallbackConfig(
            enabled=True, per_session_max_usd=1.0,
        )
        assert check_session_cost_threshold(1.01, cfg) == "session_budget_exceeded"

    def test_exactly_at_threshold_is_not_exceeded(self):
        cfg = CostAwareFallbackConfig(
            enabled=True, per_session_max_usd=1.0,
        )
        assert check_session_cost_threshold(1.0, cfg) is None

    def test_none_returns_none(self):
        cfg = CostAwareFallbackConfig(
            enabled=True, per_session_max_usd=1.0,
        )
        assert check_session_cost_threshold(None, cfg) is None

    def test_nan_returns_none(self):
        cfg = CostAwareFallbackConfig(
            enabled=True, per_session_max_usd=1.0,
        )
        assert check_session_cost_threshold(math.nan, cfg) is None


# ── Integration: RoutingDecision.set_cost_threshold ──────────────────────


class TestRoutingDecisionSetCostThreshold:
    """Make sure the helper writes both the boolean (always present) and
    the reason string onto the routing_decision dict."""

    def test_set_cost_threshold_marks_exceeded(self):
        from agent.routing_decision import set_cost_threshold
        out: dict = {"mode": "text", "fallback_used": False, "retries": 0}
        set_cost_threshold(out, reason="request_budget_exceeded")
        assert out["cost_threshold_exceeded"] is True
        assert out["cost_threshold_reason"] == "request_budget_exceeded"

    def test_set_cost_threshold_is_noop_on_non_dict(self):
        from agent.routing_decision import set_cost_threshold
        for bad in (None, [], "string", 42):
            set_cost_threshold(bad, reason="session_budget_exceeded")
            # No exception, value unchanged
            assert bad in (None, [], "string", 42)

    def test_set_cost_threshold_empty_reason_stored_as_none(self):
        from agent.routing_decision import set_cost_threshold
        out: dict = {}
        set_cost_threshold(out, reason="")
        # Boolean still flipped — the threshold fired.
        assert out["cost_threshold_exceeded"] is True
        # But reason string normalized to None.
        assert out["cost_threshold_reason"] is None

    def test_to_dict_always_includes_cost_threshold_exceeded(self):
        """Even when False, the boolean must be present in the SSE payload
        so the front-end can do `if rd.cost_threshold_exceeded` without
        a KeyError guard."""
        from agent.routing_decision import RoutingDecision
        rd = RoutingDecision(mode="text")
        out = rd.to_dict()
        assert "cost_threshold_exceeded" in out
        assert out["cost_threshold_exceeded"] is False

    def test_to_dict_includes_reason_when_set(self):
        from agent.routing_decision import RoutingDecision
        rd = RoutingDecision(
            mode="text",
            cost_threshold_exceeded=True,
            cost_threshold_reason="session_budget_exceeded",
        )
        out = rd.to_dict()
        assert out["cost_threshold_exceeded"] is True
        assert out["cost_threshold_reason"] == "session_budget_exceeded"
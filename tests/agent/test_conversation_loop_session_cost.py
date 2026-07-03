"""S12 P2 — conversation_loop session cost threshold + fallback swap tests.

The `_check_session_cost_threshold_and_act` helper is the only point in
the main agent loop where the session budget gets enforced.  Tests pin:

- Disabled / no-config / below-threshold are silent no-ops.
- Above-threshold + 'warn' annotates the routing_decision but does NOT
  swap the fallback (lets the operator inspect and decide).
- Above-threshold + 'fallback' + chain present invokes
  ``agent._try_activate_fallback()`` and surfaces the swap on the
  routing_decision.
- Above-threshold + 'fallback' + chain exhausted is a silent no-op
  (no exception, no swap, no crash).
- A broken ``_try_activate_fallback`` is logged and swallowed so a
  successful turn isn't killed by a downstream failure.

Pure unit tests — no DB, no network, no monkeypatched SDK calls.
"""

from types import SimpleNamespace

import pytest

from agent.cost_aware_fallback import CostAwareFallbackConfig
from agent.conversation_loop import _check_session_cost_threshold_and_act


def _patch_config(monkeypatch, cfg: CostAwareFallbackConfig) -> None:
    """Stub ``hermes_cli.config.load_config`` to return the agent cfg.

    The helper lazy-loads the config via ``load_config()`` so it pays
    nothing when the policy is disabled — patching the loader lets us
    exercise the threshold code without writing a config.yaml.

    Pass a dict-shaped config (the actual wire format from YAML); the
    helper runs it through ``CostAwareFallbackConfig.from_dict`` again
    to enforce the same parsing invariants as the production code path.
    """
    cfg_dict = {
        "enabled": cfg.enabled,
        "per_request_max_usd": cfg.per_request_max_usd,
        "per_session_max_usd": cfg.per_session_max_usd,
        "on_session_exceeded": cfg.on_session_exceeded,
    }
    monkeypatch.setattr(
        "hermes_cli.config.load_config",
        lambda: {"agent": {"cost_aware_fallback": cfg_dict}},
        raising=False,
    )


def _make_agent(*, chain=None, fallback_index=0, fallback_activated=False,
                activated_response=False):
    """Build a minimal AIAgent-like SimpleNamespace."""
    agent = SimpleNamespace(
        _fallback_chain=list(chain or []),
        _fallback_index=fallback_index,
        _fallback_activated=fallback_activated,
    )

    def _activate(reason=None):
        # Mirror the production semantics: advance the index and flip
        # ``_fallback_activated`` so the helper can read back the new
        # entry.  Real AIAgent._try_activate_fallback does much more
        # (rebuild clients, swap model/provider), but for these tests
        # we only need the routing-decision metadata to be correct.
        if agent._fallback_index >= len(agent._fallback_chain):
            return False
        agent._fallback_index += 1
        agent._fallback_activated = True
        return activated_response

    agent._try_activate_fallback = _activate
    return agent


# ── Disabled / no-config / below-threshold ────────────────────────────────


class TestSessionThresholdNoOpPaths:

    def test_disabled_returns_none(self, monkeypatch):
        _patch_config(monkeypatch, CostAwareFallbackConfig(
            enabled=False, per_session_max_usd=0.01,
        ))
        agent = _make_agent()
        routing: dict = {}
        assert _check_session_cost_threshold_and_act(
            agent, session_cost_usd=1.0, routing_decision=routing,
        ) is None
        assert routing == {}

    def test_below_threshold_returns_none(self, monkeypatch):
        _patch_config(monkeypatch, CostAwareFallbackConfig(
            enabled=True, per_session_max_usd=2.0,
        ))
        agent = _make_agent()
        routing: dict = {}
        assert _check_session_cost_threshold_and_act(
            agent, session_cost_usd=1.5, routing_decision=routing,
        ) is None
        assert routing == {}

    def test_none_cost_returns_none(self, monkeypatch):
        """Unknown cost → no fire (matches the per-request convention)."""
        _patch_config(monkeypatch, CostAwareFallbackConfig(
            enabled=True, per_session_max_usd=1.0,
        ))
        agent = _make_agent()
        routing: dict = {}
        assert _check_session_cost_threshold_and_act(
            agent, session_cost_usd=None, routing_decision=routing,
        ) is None

    def test_no_routing_decision_dict_does_not_crash(self, monkeypatch):
        """Defensive — caller might pass None / list.  We don't write to it
        but we still apply the policy on the agent."""
        _patch_config(monkeypatch, CostAwareFallbackConfig(
            enabled=True, per_session_max_usd=1.0,
            on_session_exceeded="warn",
        ))
        agent = _make_agent()
        assert _check_session_cost_threshold_and_act(
            agent, session_cost_usd=2.0, routing_decision=None,
        ) == "session_budget_exceeded"


# ── Above threshold: 'warn' mode ──────────────────────────────────────────


class TestSessionThresholdWarnMode:

    def test_warn_mode_annotates_routing_without_swapping(self, monkeypatch):
        _patch_config(monkeypatch, CostAwareFallbackConfig(
            enabled=True, per_session_max_usd=1.0,
            on_session_exceeded="warn",
        ))
        agent = _make_agent(chain=[{"provider": "openai", "model": "gpt-5.5"}])
        routing: dict = {"mode": "native"}
        result = _check_session_cost_threshold_and_act(
            agent, session_cost_usd=2.5, routing_decision=routing,
        )
        assert result == "session_budget_exceeded"
        # Annotated
        assert routing["cost_threshold_exceeded"] is True
        assert routing["cost_threshold_reason"] == "session_budget_exceeded"
        # No fallback swap — the policy is 'warn' only.
        assert "fallback_used" not in routing or routing.get("fallback_used") is False


# ── Above threshold: 'fallback' mode ─────────────────────────────────────


class TestSessionThresholdFallbackMode:

    def test_fallback_mode_activates_next_chain_entry(self, monkeypatch):
        _patch_config(monkeypatch, CostAwareFallbackConfig(
            enabled=True, per_session_max_usd=1.0,
            on_session_exceeded="fallback",
        ))
        # fallback_index=1 → next activation picks chain[1] (anthropic),
        # which is the realistic scenario where the budget blew past on
        # the primary and the user already cycled through openai once.
        agent = _make_agent(
            chain=[
                {"provider": "openai", "model": "gpt-5.5"},
                {"provider": "anthropic", "model": "claude-opus-4.6"},
            ],
            fallback_index=1,
            activated_response=True,
        )
        routing: dict = {}
        result = _check_session_cost_threshold_and_act(
            agent, session_cost_usd=2.5, routing_decision=routing,
        )
        assert result == "session_budget_exceeded"
        assert routing["cost_threshold_exceeded"] is True
        assert routing["fallback_used"] is True
        assert routing["fallback_reason"] == "cost_aware_session_budget_exceeded"
        assert routing["fallback_provider"] == "anthropic"
        assert routing["fallback_model"] == "claude-opus-4.6"
        # rule_id uses the post-activation chain index (the position we
        # just landed at, not the one we started from).  Started at 1
        # (meaning openai was already burned), activated chain[1] →
        # agent._fallback_index is now 2 → label = [1].
        assert routing["rule_id"] == "cost_aware_fallback[1](anthropic)"

    def test_fallback_mode_chain_exhausted_no_swap(self, monkeypatch):
        """If we're already on the last chain entry, don't blow up — just
        annotate the routing_decision and let the user see the warning."""
        _patch_config(monkeypatch, CostAwareFallbackConfig(
            enabled=True, per_session_max_usd=1.0,
            on_session_exceeded="fallback",
        ))
        agent = _make_agent(
            chain=[{"provider": "anthropic", "model": "claude-opus-4.6"}],
            fallback_index=1,  # beyond the chain end
        )
        routing: dict = {}
        result = _check_session_cost_threshold_and_act(
            agent, session_cost_usd=2.5, routing_decision=routing,
        )
        assert result == "session_budget_exceeded"
        # Annotation still lands — the threshold fired even though we
        # couldn't swap further.
        assert routing["cost_threshold_exceeded"] is True
        # No fallback record (we didn't swap).
        assert "fallback_used" not in routing or routing.get("fallback_used") is False

    def test_fallback_mode_no_chain_returns_reason_without_swapping(self, monkeypatch):
        """User configured fallback mode but has no fallback_chain — fall
        back to 'warn' semantics silently."""
        _patch_config(monkeypatch, CostAwareFallbackConfig(
            enabled=True, per_session_max_usd=1.0,
            on_session_exceeded="fallback",
        ))
        agent = _make_agent(chain=[])
        routing: dict = {}
        result = _check_session_cost_threshold_and_act(
            agent, session_cost_usd=2.5, routing_decision=routing,
        )
        assert result == "session_budget_exceeded"
        assert routing["cost_threshold_exceeded"] is True
        # No fallback swap — nothing to swap to.
        assert "fallback_used" not in routing or routing.get("fallback_used") is False

    def test_fallback_mode_try_activate_failure_swallowed(self, monkeypatch):
        """A broken fallback swap must not crash the turn.  The annotation
        stays so the user still sees the budget warning."""
        _patch_config(monkeypatch, CostAwareFallbackConfig(
            enabled=True, per_session_max_usd=1.0,
            on_session_exceeded="fallback",
        ))
        agent = _make_agent(
            chain=[{"provider": "anthropic", "model": "claude-opus-4.6"}],
        )

        def _broken_activate(reason=None):
            raise RuntimeError("network down")

        agent._try_activate_fallback = _broken_activate
        routing: dict = {}
        # Should NOT raise.
        result = _check_session_cost_threshold_and_act(
            agent, session_cost_usd=2.5, routing_decision=routing,
        )
        assert result == "session_budget_exceeded"
        # Annotation still present.
        assert routing["cost_threshold_exceeded"] is True


# ── Configuration plumbing edge cases ────────────────────────────────────


class TestSessionThresholdConfigPlumbing:

    def test_missing_agent_section_returns_none(self, monkeypatch):
        """If config has no agent section at all, the helper silently no-ops."""
        monkeypatch.setattr(
            "hermes_cli.config.load_config",
            lambda: {},
            raising=False,
        )
        agent = _make_agent()
        routing: dict = {}
        assert _check_session_cost_threshold_and_act(
            agent, session_cost_usd=2.5, routing_decision=routing,
        ) is None
        assert routing == {}

    def test_load_config_exception_swallowed(self, monkeypatch):
        """A broken config layer must not crash the turn."""
        def _broken_load():
            raise RuntimeError("yaml corruption")
        monkeypatch.setattr(
            "hermes_cli.config.load_config",
            _broken_load,
            raising=False,
        )
        agent = _make_agent()
        routing: dict = {}
        # Should NOT raise.
        assert _check_session_cost_threshold_and_act(
            agent, session_cost_usd=2.5, routing_decision=routing,
        ) is None
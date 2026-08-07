"""S12 — conversation_loop._build_main_agent_routing_decision unit tests.

The main agent chat path doesn't go through ``auxiliary_client.call_llm``
so we synthesize the routing decision here from agent attributes.  These
tests pin the contract for hermes-tray T-Q-S12-light.
"""

from types import SimpleNamespace

from agent.conversation_loop import _build_main_agent_routing_decision


def _make_agent(**overrides):
    """Build a minimal AIAgent-like SimpleNamespace for the helper."""
    base = dict(
        provider="openai",
        model="gpt-5.5",
        _primary_runtime={"provider": "openai", "model": "gpt-5.5"},
        _fallback_activated=False,
        _fallback_chain=[],
        _fallback_index=0,
    )
    base.update(overrides)
    return SimpleNamespace(**base)


class TestBuildMainAgentRoutingDecision:

    def test_native_path_no_fallback(self):
        agent = _make_agent()
        rd = _build_main_agent_routing_decision(agent, api_duration=1.234, retry_count=0)
        assert rd["mode"] == "native"
        assert rd["primary_provider"] == "openai"
        assert rd["primary_model"] == "gpt-5.5"
        assert rd["resolved_provider"] == "openai"
        assert rd["resolved_model"] == "gpt-5.5"
        assert rd["fallback_used"] is False
        assert rd["latency_ms"] == 1234
        assert rd["retries"] == 0
        assert rd["fallback_reason"] is None

    def test_fallback_path_records_provider_and_rule_id(self):
        agent = _make_agent(
            provider="kimi-for-coding",
            model="kimi-k2",
            _fallback_activated=True,
            _fallback_chain=[{"provider": "kimi-for-coding", "model": "kimi-k2"}],
            _fallback_index=1,
        )
        rd = _build_main_agent_routing_decision(agent, api_duration=0.456, retry_count=2)
        assert rd["primary_provider"] == "openai"  # primary from _primary_runtime
        assert rd["resolved_provider"] == "kimi-for-coding"  # current after swap
        assert rd["fallback_used"] is True
        assert rd["fallback_reason"] == "fallback_chain"
        assert rd["fallback_provider"] == "kimi-for-coding"
        # CAND-080 layer 2: rule_id is now the family name and the legacy
        # "[0](provider)" suffix is split into a structured ``rule_params``
        # payload. The structured payload is what the SSE consumer parses.
        assert rd["rule_id"] == "fallback_chain"
        assert rd["rule_params"] == {"chain_index": 0, "provider": "kimi-for-coding"}
        assert rd["retries"] == 2

    def test_no_primary_runtime_falls_back_to_current(self):
        """If _primary_runtime is missing (test stubs, fresh init), use the
        current provider/model as both primary and resolved."""
        agent = SimpleNamespace(
            provider="openrouter",
            model="anthropic/claude-opus-4.6",
            _primary_runtime={},
            _fallback_activated=False,
            _fallback_chain=[],
            _fallback_index=0,
        )
        rd = _build_main_agent_routing_decision(agent, api_duration=0.1, retry_count=0)
        assert rd["primary_provider"] == "openrouter"
        assert rd["primary_model"] == "anthropic/claude-opus-4.6"
        assert rd["resolved_provider"] == "openrouter"
        assert rd["resolved_model"] == "anthropic/claude-opus-4.6"

    def test_returns_none_when_no_provider_or_model(self):
        """Skip — emitting an empty dict would break SSE consumers."""
        agent = SimpleNamespace(
            provider="", model="",
            _primary_runtime={}, _fallback_activated=False,
            _fallback_chain=[], _fallback_index=0,
        )
        rd = _build_main_agent_routing_decision(agent, api_duration=0.1, retry_count=0)
        assert rd is None

    def test_latency_is_zero_skipped(self):
        """api_duration=0 means the call hasn't actually happened yet (e.g.
        error path); don't stamp a misleading latency."""
        agent = _make_agent()
        rd = _build_main_agent_routing_decision(agent, api_duration=0, retry_count=0)
        assert "latency_ms" not in rd

    def test_zero_retries_present_with_zero_value(self):
        """retries is a scalar field — always present, value 0 means no retry
        happened.  Front-end conditional rendering (`if rd.retries > 0`) relies
        on the field being there."""
        agent = _make_agent()
        rd = _build_main_agent_routing_decision(agent, api_duration=0.5, retry_count=0)
        assert rd["retries"] == 0

    def test_zero_latency_with_retries_still_records_retries(self):
        """Defensive — a path that hit retries but couldn't measure latency
        (very early abort) should still surface the retry count."""
        agent = _make_agent()
        rd = _build_main_agent_routing_decision(agent, api_duration=0, retry_count=3)
        assert rd["retries"] == 3
        assert "latency_ms" not in rd
"""S12 — RoutingDecision dataclass + helper unit tests.

Covers the per-call routing metadata that ``auxiliary_client.call_llm`` /
``async_call_llm`` populate in-place via ``routing_decision_out`` and that
``agent.conversation_loop._build_main_agent_routing_decision`` synthesizes
for the main agent path.  The same dict flows out through ``usage_dict`` so
front-ends (hermes-tray T-Q-S12-light / T-Q-S9) can show "why this
provider?" + "what did it cost?" alongside the standard OpenAI usage shape.

These tests are pure-Python — no network, no fixtures, no provider
mocking — so they run in <0.1s and are safe to keep in the always-on
CI tier.
"""

import math

from agent.routing_decision import (
    KNOWN_RULES,
    RoutingDecision,
    RuleSpec,
    init_routing_decision,
    record_fallback,
    resolve_routing,
    set_latency,
    set_cost,
    increment_retries,
    set_rule_id,
)


# ── Dataclass serialization ──────────────────────────────────────────────


class TestRoutingDecisionDataclass:
    """RoutingDecision.to_dict is the SSE serialization path."""

    def test_to_dict_always_includes_mode_fallback_retries(self):
        """The three scalar/bool fields are always present even when falsy —
        downstream UI checks them in conditional rendering, so dropping them
        when False / 0 would cause subtle display bugs."""
        rd = RoutingDecision(mode="text", retries=0, fallback_used=False)
        out = rd.to_dict()
        assert out["mode"] == "text"
        assert out["fallback_used"] is False
        assert out["retries"] == 0

    def test_to_dict_strips_none_optional_fields(self):
        """Compact payload — None values are dropped so SSE chunks stay small."""
        rd = RoutingDecision(
            mode="native",
            primary_provider="openai",
            resolved_provider="openai",
            fallback_used=False,
            retries=0,
        )
        out = rd.to_dict()
        # Set fields present
        assert out["primary_provider"] == "openai"
        assert out["resolved_provider"] == "openai"
        # Unset None fields stripped
        for field in (
            "primary_model",
            "resolved_model",
            "fallback_reason",
            "fallback_provider",
            "fallback_model",
            "cost_estimate_usd",
            "latency_ms",
            "rule_id",
        ):
            assert field not in out, f"{field} should have been stripped (None)"

    def test_to_dict_includes_all_set_optional_fields(self):
        """All populated optional fields should make it through."""
        rd = RoutingDecision(
            mode="text",
            primary_provider="openai",
            primary_model="gpt-5.5",
            resolved_provider="anthropic",
            resolved_model="claude-opus-4.6",
            fallback_used=True,
            fallback_reason="payment_error",
            fallback_provider="anthropic",
            fallback_model="claude-opus-4.6",
            cost_estimate_usd=0.0042,
            latency_ms=1234,
            retries=2,
            rule_id="fallback_chain[0](anthropic)",
        )
        out = rd.to_dict()
        assert out["fallback_reason"] == "payment_error"
        assert out["cost_estimate_usd"] == 0.0042
        assert out["latency_ms"] == 1234
        assert out["retries"] == 2
        assert out["rule_id"] == "fallback_chain[0](anthropic)"

    def test_to_dict_does_not_alias_back_to_dataclass(self):
        """to_dict returns a fresh dict so callers can mutate without
        poisoning the dataclass instance."""
        rd = RoutingDecision(mode="text", primary_provider="openai")
        out = rd.to_dict()
        out["mode"] = "tampered"
        assert rd.mode == "text", "RoutingDecision.mode must be immutable via to_dict"


# ── init_routing_decision ────────────────────────────────────────────────


class TestInitRoutingDecision:
    """init resets the dict to a well-formed primary + zero state."""

    def test_init_clears_existing_keys(self):
        out = {"stale": "garbage", "mode": "wrong"}
        init_routing_decision(out, mode="text", primary_provider="openai", primary_model="gpt-5.5")
        assert "stale" not in out
        assert out["mode"] == "text"
        assert out["primary_provider"] == "openai"
        assert out["primary_model"] == "gpt-5.5"
        assert out["resolved_provider"] is None
        assert out["resolved_model"] is None
        assert out["fallback_used"] is False
        assert out["retries"] == 0

    def test_init_normalizes_empty_strings_to_none(self):
        """Provider/model args that arrive as empty strings should be stored
        as None — keeps the SSE payload consistent."""
        out = {}
        init_routing_decision(out, primary_provider="", primary_model="")
        assert out["primary_provider"] is None
        assert out["primary_model"] is None

    def test_init_is_noop_when_target_is_not_dict(self):
        """None, list, str — all must be silently accepted."""
        for bad in (None, [], "string", 42):
            # The signature accepts a dict; we expect graceful no-op for anything else.
            init_routing_decision(bad, mode="text")
            # No exception, value unchanged
            assert bad in (None, [], "string", 42)


# ── record_fallback ──────────────────────────────────────────────────────


class TestRecordFallback:

    def test_record_fallback_stamps_reason_and_target(self):
        out = {}
        init_routing_decision(out, mode="text", primary_provider="openai")
        record_fallback(
            out,
            fallback_provider="anthropic",
            fallback_model="claude-opus-4.6",
            fallback_reason="payment_error",
        )
        assert out["fallback_used"] is True
        assert out["fallback_reason"] == "payment_error"
        assert out["fallback_provider"] == "anthropic"
        assert out["fallback_model"] == "claude-opus-4.6"

    def test_record_fallback_overrides_previous_fallback(self):
        """If the chain tries multiple fallbacks, the last one wins."""
        out = {}
        init_routing_decision(out, mode="text")
        record_fallback(out, fallback_provider="anthropic", fallback_model=None, fallback_reason="payment_error")
        record_fallback(out, fallback_provider="kimi-for-coding", fallback_model="kimi-k2", fallback_reason="connection_error")
        assert out["fallback_provider"] == "kimi-for-coding"
        assert out["fallback_reason"] == "connection_error"

    def test_record_fallback_is_noop_on_non_dict(self):
        for bad in (None, "string", []):
            record_fallback(bad, fallback_provider="x", fallback_model=None, fallback_reason="r")


# ── resolve_routing ──────────────────────────────────────────────────────


class TestResolveRouting:

    def test_resolve_sets_actual_provider_model(self):
        out = {}
        init_routing_decision(out, mode="text", primary_provider="openai", primary_model="gpt-5.5")
        resolve_routing(out, resolved_provider="anthropic", resolved_model="claude-opus-4.6")
        assert out["resolved_provider"] == "anthropic"
        assert out["resolved_model"] == "claude-opus-4.6"

    def test_resolve_empty_strings_to_none(self):
        out = {}
        init_routing_decision(out, mode="text")
        resolve_routing(out, resolved_provider="", resolved_model="")
        assert out["resolved_provider"] is None
        assert out["resolved_model"] is None


# ── set_latency ──────────────────────────────────────────────────────────


class TestSetLatency:

    def test_set_latency_positive_int(self):
        out = {}
        set_latency(out, latency_ms=1234)
        assert out["latency_ms"] == 1234

    def test_set_latency_drops_none(self):
        out = {"latency_ms": 999}
        set_latency(out, latency_ms=None)
        # Pre-existing value preserved
        assert out["latency_ms"] == 999

    def test_set_latency_clamps_negative_to_zero(self):
        """Negative latency would corrupt the SSE payload — clamp to 0."""
        out = {}
        set_latency(out, latency_ms=-5)
        assert out["latency_ms"] == 0

    def test_set_latency_converts_float(self):
        out = {}
        set_latency(out, latency_ms=1.7)
        assert out["latency_ms"] == 1
        assert isinstance(out["latency_ms"], int)


# ── set_cost ─────────────────────────────────────────────────────────────


class TestSetCost:

    def test_set_cost_positive_value(self):
        out = {}
        set_cost(out, cost_estimate_usd=0.0123)
        assert out["cost_estimate_usd"] == 0.0123

    def test_set_cost_drops_none(self):
        out = {"cost_estimate_usd": 0.5}
        set_cost(out, cost_estimate_usd=None)
        assert out["cost_estimate_usd"] == 0.5

    def test_set_cost_drops_nan(self):
        """NaN poisons JSON serialization — drop it."""
        out = {"cost_estimate_usd": 0.5}
        set_cost(out, cost_estimate_usd=float("nan"))
        assert out["cost_estimate_usd"] == 0.5

    def test_set_cost_drops_negative(self):
        """Negative cost would be user-visible nonsense."""
        out = {}
        set_cost(out, cost_estimate_usd=-0.01)
        assert "cost_estimate_usd" not in out

    def test_set_cost_drops_non_numeric(self):
        """Defensive — if upstream passes a string it shouldn't reach the wire."""
        out = {}
        set_cost(out, cost_estimate_usd="not a number")  # type: ignore[arg-type]
        assert "cost_estimate_usd" not in out


# ── increment_retries ────────────────────────────────────────────────────


class TestIncrementRetries:

    def test_increment_from_zero(self):
        out = {"retries": 0}
        increment_retries(out)
        assert out["retries"] == 1

    def test_increment_from_missing_key(self):
        out = {}
        increment_retries(out)
        assert out["retries"] == 1

    def test_increment_capped_at_99(self):
        """Bound SSE payload size — pathological retry storms shouldn't
        produce 4-digit counters."""
        out = {"retries": 100}
        increment_retries(out)
        assert out["retries"] == 99

    def test_increment_handles_garbage_value(self):
        out = {"retries": "not a number"}
        increment_retries(out)
        assert out["retries"] == 1


# ── set_rule_id ──────────────────────────────────────────────────────────


class TestSetRuleId:

    def test_set_rule_id(self):
        out = {}
        set_rule_id(out, rule_id="fallback_chain[0](anthropic)")
        assert out["rule_id"] == "fallback_chain[0](anthropic)"

    def test_set_rule_id_empty_string_to_none(self):
        out = {}
        set_rule_id(out, rule_id="")
        assert out["rule_id"] is None


# ── Integration: full lifecycle ──────────────────────────────────────────


class TestRoutingDecisionLifecycle:
    """End-to-end shape test mirroring how auxiliary_client uses it."""

    def test_full_lifecycle_text_call_no_fallback(self):
        """A successful primary call populates primary + resolved + latency."""
        out: dict = {}
        init_routing_decision(
            out,
            mode="text",
            primary_provider="openai",
            primary_model="gpt-5.5",
        )
        resolve_routing(
            out,
            resolved_provider="openai",
            resolved_model="gpt-5.5",
        )
        set_latency(out, latency_ms=842)
        set_cost(out, cost_estimate_usd=0.0023)

        assert out["mode"] == "text"
        assert out["primary_provider"] == "openai"
        assert out["resolved_provider"] == "openai"
        assert out["resolved_model"] == "gpt-5.5"
        assert out["latency_ms"] == 842
        assert out["cost_estimate_usd"] == 0.0023
        assert out["fallback_used"] is False
        assert out["retries"] == 0
        # SSE-ready: round-trip via dataclass + to_dict
        rd = RoutingDecision(**out)
        assert rd.to_dict()["latency_ms"] == 842

    def test_full_lifecycle_with_fallback_and_retries(self):
        """A primary that hit a transient retry then fell back to a configured
        chain entry — the worst case, must still produce a compact dict."""
        out: dict = {}
        init_routing_decision(
            out,
            mode="text",
            primary_provider="openai",
            primary_model="gpt-5.5",
        )
        # Transient retry on the primary first
        increment_retries(out)
        # Then primary died → fell back to anthropic
        record_fallback(
            out,
            fallback_provider="anthropic",
            fallback_model="claude-opus-4.6",
            fallback_reason="connection_error",
        )
        set_rule_id(out, rule_id="fallback_chain[0](anthropic)")
        resolve_routing(
            out,
            resolved_provider="anthropic",
            resolved_model="claude-opus-4.6",
        )
        set_latency(out, latency_ms=3450)
        set_cost(out, cost_estimate_usd=0.018)

        assert out["fallback_used"] is True
        assert out["fallback_reason"] == "connection_error"
        assert out["fallback_provider"] == "anthropic"
        assert out["retries"] == 1
        assert out["rule_id"] == "fallback_chain[0](anthropic)"
        assert out["latency_ms"] == 3450
        # Resolved != primary — clear sign the fallback won
        assert out["primary_provider"] != out["resolved_provider"]


class TestMathHelpersAreSound:
    """Sanity check — make sure we're not accidentally importing math stubs."""

    def test_nan_compare_works(self):
        # Used in set_cost to detect NaN inputs; pin the contract here so
        # refactors don't silently break the check.
        assert math.nan != math.nan  # NaN is never equal to itself
        assert math.isnan(math.nan)


# ── CAND-080 layer 2: rule registry + structured params ─────────────────


class TestRuleRegistry:
    """Pin the KNOWN_RULES schema so future CAND-080 layer 1 patch
    consumers can rely on it.

    Each known rule has a stable ``rule_id``, an owner module, and an
    explicit ``params_schema``. The registry is the layer 2 abstraction:
    pre-layer-2 callers passed a hard-coded ``"fallback_chain[0](kimi)"``
    string; layer 2 callers pass ``rule_id="fallback_chain"`` plus
    ``params={"chain_index": 0, "provider": "kimi"}``.
    """

    EXPECTED_RULE_IDS = {
        "fallback_chain",
        "cost_aware_fallback",
        "vision_fallback_config",
        "vision_fallback_chain",
        "payment_fallback",
        "main_agent_model_fallback",
    }

    def test_registry_contains_expected_rule_ids(self):
        assert set(KNOWN_RULES) == self.EXPECTED_RULE_IDS, (
            f"registry drifted: {set(KNOWN_RULES) ^ self.EXPECTED_RULE_IDS}"
        )

    def test_every_entry_is_a_rulespec(self):
        for rule_id, spec in KNOWN_RULES.items():
            assert isinstance(spec, RuleSpec), f"{rule_id} is {type(spec).__name__}"
            assert spec.rule_id == rule_id, (
                f"{rule_id} spec.rule_id mismatch: {spec.rule_id!r}"
            )

    def test_fallback_chain_has_chain_index_and_provider_params(self):
        spec = KNOWN_RULES["fallback_chain"]
        assert "chain_index" in spec.params_schema
        assert "provider" in spec.params_schema
        assert spec.params_schema["chain_index"] == "int"
        assert spec.params_schema["provider"] == "str"

    def test_cost_aware_fallback_reuses_fallback_chain_params(self):
        """cost_aware_fallback is the same family shape as fallback_chain
        (chain_index + provider) — different ``owner`` module only.
        """
        spec = KNOWN_RULES["cost_aware_fallback"]
        assert spec.params_schema == {"chain_index": "int", "provider": "str"}
        assert spec.owner != KNOWN_RULES["fallback_chain"].owner, (
            "owner must differ so the registry disambiguates who fired the rule"
        )

    def test_vision_fallback_config_has_no_params(self):
        """Single-step fallback — no chain index to record."""
        spec = KNOWN_RULES["vision_fallback_config"]
        assert spec.params_schema == {}


class TestSetRuleIdParams:
    """set_rule_id gained an optional ``params`` keyword in CAND-080
    layer 2. Verify the migration-safety guarantee: pre-layer-2 callers
    that pass only ``rule_id`` see a byte-identical SSE payload, while
    layer-2 callers that pass ``params`` get a structured ``rule_params``
    field the front-end can parse.
    """

    def test_legacy_string_only_does_not_emit_rule_params(self):
        """The migration-safety guarantee. ``rule_params`` must NOT appear
        in the dict when ``params`` is not passed — otherwise pre-layer-2
        SSE consumers that filter on "unknown keys" would break.
        """
        out: dict = {}
        set_rule_id(out, rule_id="fallback_chain[0](anthropic)")
        assert out["rule_id"] == "fallback_chain[0](anthropic)"
        assert "rule_params" not in out, (
            "legacy call must not write rule_params; SSE compat would break"
        )

    def test_empty_string_to_none_does_not_emit_rule_params(self):
        out: dict = {}
        set_rule_id(out, rule_id="")
        assert out["rule_id"] is None
        assert "rule_params" not in out

    def test_params_dict_writes_rule_params(self):
        out: dict = {}
        set_rule_id(
            out,
            rule_id="fallback_chain",
            params={"chain_index": 0, "provider": "anthropic"},
        )
        assert out["rule_id"] == "fallback_chain"
        assert out["rule_params"] == {"chain_index": 0, "provider": "anthropic"}

    def test_params_dict_is_copied_not_aliased(self):
        """Defensive: if a caller mutates the params dict after passing it,
        the SSE payload must not silently change. ``set_rule_id`` makes
        an internal copy.
        """
        params = {"chain_index": 1, "provider": "kimi"}
        out: dict = {}
        set_rule_id(out, rule_id="fallback_chain", params=params)
        params["chain_index"] = 99
        assert out["rule_params"] == {"chain_index": 1, "provider": "kimi"}, (
            "rule_params aliased the caller's dict — SSE payload would "
            "drift if the caller mutates params later"
        )

    def test_empty_params_dict_does_not_emit_rule_params(self):
        """``params={}`` is treated as "no params to record" — don't write
        an empty dict (would clutter the SSE payload).
        """
        out: dict = {}
        set_rule_id(out, rule_id="vision_fallback_config", params={})
        assert out["rule_id"] == "vision_fallback_config"
        assert "rule_params" not in out

    def test_none_params_does_not_emit_rule_params(self):
        out: dict = {}
        set_rule_id(out, rule_id="payment_fallback", params=None)
        assert out["rule_id"] == "payment_fallback"
        assert "rule_params" not in out

    def test_routing_decision_dataclass_carries_rule_params(self):
        """Dataclass-level: ``rule_params`` is a real field that round-trips
        through ``to_dict`` (after the None-strip). Pre-layer-2 callers
        who never set it get ``None`` and an SSE payload unchanged.
        """
        decision = RoutingDecision(
            mode="text",
            rule_id="fallback_chain",
            rule_params={"chain_index": 0, "provider": "anthropic"},
        )
        assert decision.rule_params == {"chain_index": 0, "provider": "anthropic"}
        rendered = decision.to_dict()
        assert rendered["rule_id"] == "fallback_chain"
        assert rendered["rule_params"] == {"chain_index": 0, "provider": "anthropic"}

    def test_routing_decision_default_rule_params_is_none(self):
        """Pre-layer-2 callers that construct ``RoutingDecision`` without
        passing ``rule_params`` must not see the key in ``to_dict``
        (None-strip behavior matches the rest of the dataclass).
        """
        decision = RoutingDecision(mode="text", rule_id="legacy_label")
        assert decision.rule_params is None
        rendered = decision.to_dict()
        assert rendered["rule_id"] == "legacy_label"
        assert "rule_params" not in rendered, (
            "to_dict must None-strip rule_params to keep the pre-layer-2 "
            "SSE payload byte-identical"
        )
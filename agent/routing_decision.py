"""S12 — Cost-aware / Latency-aware routing decision metadata.

Defines the :class:`RoutingDecision` dataclass and the small set of helpers
that ``auxiliary_client.call_llm`` / ``async_call_llm`` populate per LLM call
so the SSE ``usage`` chunk can carry "why this provider?" + "what did it
cost?" metadata to the front-end (hermes-tray T-Q-S9 / T-Q-S12-light).

Design
------
- ``mode`` discriminates the call family (``"text"`` for chat, ``"vision"``
  for vision tasks, ``"native"`` for the main agent's own loop, etc.).
- ``primary_*`` is what the caller (or user config) asked for.
- ``resolved_*`` is what actually ran after any fallback.
- ``fallback_used`` / ``fallback_reason`` / ``fallback_provider`` /
  ``fallback_model`` capture *which* rule fired (e.g. ``primary_unavailable``,
  ``payment_error``, ``rate_limit``).
- ``cost_estimate_usd`` is best-effort, computed by
  :func:`agent.usage_pricing.estimate_usage_cost` from the actual token
  counts returned by the provider.
- ``latency_ms`` is the wall-clock time of the call.
- ``retries`` is the number of transient retries fired *before* the final
  response (same-provider retry, temperature-stripping retry, max_tokens
  retry are all counted; cross-provider fallback is **not** a retry, it
  shows up under ``fallback_used``).
- ``rule_id`` is a short tag identifying the routing rule that fired —
  callers can attach it to ``routing_decision`` so the front-end can show
  a stable label (e.g. ``"vision_fallback_chain[1]"``).

The dataclass is intentionally tiny: callers (front-ends, debugging tools,
cost dashboards) only need the surfaced fields, and any new diagnostic
data can be added without breaking existing readers (extra keys are
ignored).

OpenAI-protocol compatibility
-----------------------------
The dict emitted by :meth:`RoutingDecision.to_dict` is meant to be embedded
verbatim in the SSE ``usage`` chunk under a top-level ``routing_decision``
key.  This is an **extension** of the OpenAI Chat Completions ``usage``
shape — OpenAI's spec does not currently define a ``routing_decision``
field, so any front-end that ignores unknown usage keys keeps working
exactly as before.  Front-ends that opt-in (hermes-tray T-Q-S12-light)
will read the new key to render cost / fallback traces.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Dict, Optional


# ---------------------------------------------------------------------------
# Known routing rules (CAND-080 layer 2: rule abstraction)
# ---------------------------------------------------------------------------
#
# Before this registry existed, every call site passed a hard-coded
# ``rule_id`` string to :func:`set_rule_id` — e.g.
# ``"fallback_chain[0](anthropic)"`` — which made it impossible to
# programmatically reason about *which* rule fired, let alone rewrite the
# rule later (the routing-rule self-iteration goal from CAND-080 layer 1).
#
# This registry is the **abstraction layer**: each rule has a stable
# ``rule_id`` (the family name), a description of what firing it means,
# the module that owns the rule, and a parameter schema (key → type
# hint as string) so future patch consumers can validate the
# ``rule_params`` payload without touching the routing code itself.
#
# Layer 1 (CAND-080) will hook a ``routing_rule_manage action=patch``
# tool onto this registry, mirroring how ``agent/curator.py`` already
# patches umbrella skills via ``skill_manage action=patch``. Keeping the
# schema small (no JSON Schema machinery) matches the rest of the
# S12 routing code: a dict-of-strings is enough for now, the harness
# gains optional formal validation only when a real consumer asks for it.


@dataclass(frozen=True)
class RuleSpec:
    """Static description of a known routing rule.

    Fields:
        rule_id: stable family name. Callers pass this to
            :func:`set_rule_id`; the rule owns what ``rule_params``
            entries are valid (see ``params_schema``).
        description: human-readable summary of what firing this rule
            means. Used by future CAND-080 layer 1 (rule self-iteration)
            when the user asks "why did the agent pick provider X?" —
            the description is what the front-end surfaces.
        owner: dotted module path that owns this rule. Used to
            disambiguate "two call sites pass the same rule_id but
            mean different things" (defensive — we don't expect that
            to happen, but the registry makes it easy to spot).
        params_schema: ``{param_name: type_hint}``. Type hints are
            short strings (``"int"`` / ``"str"`` / ``"float"`` / etc.)
            because the only consumer right now is the CAND-080 layer 1
            patch machinery, and a full JSON Schema buys nothing for
            the 4-5 params we have. When a consumer needs richer
            validation, swap this for a real schema and bump callers
            one at a time (Cherry-pick split bug class lesson — never
            blow up the SSE payload on a missing optional field).
    """

    rule_id: str
    description: str
    owner: str
    params_schema: Dict[str, str] = field(default_factory=dict)


KNOWN_RULES: Dict[str, RuleSpec] = {
    "fallback_chain": RuleSpec(
        rule_id="fallback_chain",
        description=(
            "Primary provider fell back to the configured fallback chain "
            "entry at index N (provider name embedded in the params)."
        ),
        owner="agent.auxiliary_client._try_configured_fallback_chain",
        params_schema={"chain_index": "int", "provider": "str"},
    ),
    "cost_aware_fallback": RuleSpec(
        rule_id="cost_aware_fallback",
        description=(
            "Cost-aware routing budget (per_request or per_session) was "
            "exceeded, fell back to chain entry N."
        ),
        owner="agent.conversation_loop.cost_aware_fallback",
        params_schema={"chain_index": "int", "provider": "str"},
    ),
    "vision_fallback_config": RuleSpec(
        rule_id="vision_fallback_config",
        description=(
            "Vision task fell back to the configured vision model "
            "(single-step fallback, no chain traversal)."
        ),
        owner="agent.auxiliary_client._try_vision_fallback_config",
        params_schema={},
    ),
    "vision_fallback_chain": RuleSpec(
        rule_id="vision_fallback_chain",
        description="Vision task fell back to chain entry N.",
        owner="agent.auxiliary_client._try_vision_fallback_chain",
        params_schema={"chain_index": "int"},
    ),
    "payment_fallback": RuleSpec(
        rule_id="payment_fallback",
        description=(
            "Primary provider failed with a payment/billing error and "
            "fell back to the alternate provider."
        ),
        owner="agent.auxiliary_client._try_payment_fallback",
        params_schema={"provider": "str"},
    ),
    "main_agent_model_fallback": RuleSpec(
        rule_id="main_agent_model_fallback",
        description=(
            "Main agent's own model fell back to the chain entry — "
            "distinct from a per-call auxiliary fallback."
        ),
        owner="agent.auxiliary_client._try_main_agent_model_fallback",
        params_schema={},
    ),
}


@dataclass
class RoutingDecision:
    """Single routing decision for one LLM call.

    Fields:
        mode: call family, e.g. ``"text"``, ``"vision"``, ``"native"``,
            ``"compression"``, ``"session_search"``, ``"title_generation"``.
        primary_provider: caller-requested provider (or ``None`` when
            the caller left resolution to the auto-detection chain).
        primary_model: caller-requested model.
        resolved_provider: provider that actually served the request
            (after any fallback).  ``None`` until the call has finished.
        resolved_model: model that actually served the request.
        fallback_used: ``True`` when the primary was abandoned.
        fallback_reason: short tag — e.g. ``"primary_unavailable"``,
            ``"primary_unavailable_no_config_fallback"``, ``"payment_error"``,
            ``"connection_error"``, ``"rate_limit"``.  ``None`` when the
            primary served the request successfully.
        fallback_provider: provider that took over, ``None`` when no
            fallback fired.
        fallback_model: model on the fallback provider.
        cost_estimate_usd: best-effort USD cost of this call, or ``None``
            if the model+provider pricing is unknown.
        latency_ms: wall-clock time in milliseconds from request dispatch
            to response receipt.
        retries: number of transient / parameter retries fired before the
            final response (same-provider retries only — cross-provider
            fallback is recorded under ``fallback_used``).
        rule_id: short routing-rule label attached by the caller, e.g.
            ``"vision_fallback_config"`` or
            ``"fallback_chain[1](kimi-for-coding)"``.  ``None`` when no
            named rule was matched.
    """

    mode: str = "text"
    primary_provider: Optional[str] = None
    primary_model: Optional[str] = None
    resolved_provider: Optional[str] = None
    resolved_model: Optional[str] = None
    fallback_used: bool = False
    fallback_reason: Optional[str] = None
    fallback_provider: Optional[str] = None
    fallback_model: Optional[str] = None
    cost_estimate_usd: Optional[float] = None
    latency_ms: Optional[int] = None
    retries: int = 0
    rule_id: Optional[str] = None
    rule_params: Optional[Dict[str, Any]] = None  # CAND-080 layer 2: structured params for the rule_id family (see KNOWN_RULES). Default None so the SSE payload is unchanged for pre-layer-2 callers.
    cost_threshold_exceeded: bool = False  # S12 P2: True when this call (or session) blew past agent.cost_aware_fallback
    cost_threshold_reason: Optional[str] = None  # 'request_budget_exceeded' | 'session_budget_exceeded'

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to a JSON-friendly dict.

        Always includes ``mode``, ``fallback_used``, ``retries``,
        ``cost_threshold_exceeded`` even when their values are falsy
        (they're scalar/cheap and downstream UI frequently checks them).
        Other ``None``-valued fields are stripped so the SSE payload
        stays compact.
        """
        out: Dict[str, Any] = {
            "mode": self.mode,
            "fallback_used": bool(self.fallback_used),
            "retries": int(self.retries),
            "cost_threshold_exceeded": bool(self.cost_threshold_exceeded),
        }
        full = asdict(self)
        for key, value in full.items():
            if key in out:
                continue
            if value is None:
                continue
            out[key] = value
        return out


def init_routing_decision(
    routing_out: Optional[Dict[str, Any]],
    *,
    mode: str = "text",
    primary_provider: Optional[str] = None,
    primary_model: Optional[str] = None,
    rule_id: Optional[str] = None,
) -> None:
    """Initialize ``routing_out`` in-place with primary-only state.

    Call at the **very start** of every LLM call path (before any fallback
    logic runs) so callers can read the final state after the call returns.
    A no-op when ``routing_out`` is not a dict (i.e. caller opted out).
    """
    if not isinstance(routing_out, dict):
        return
    routing_out.clear()
    routing_out.update(
        {
            "mode": mode,
            "primary_provider": primary_provider or None,
            "primary_model": primary_model or None,
            "resolved_provider": None,
            "resolved_model": None,
            "fallback_used": False,
            "fallback_reason": None,
            "fallback_provider": None,
            "fallback_model": None,
            "cost_estimate_usd": None,
            "latency_ms": None,
            "retries": 0,
            "rule_id": rule_id,
        }
    )


def record_fallback(
    routing_out: Optional[Dict[str, Any]],
    *,
    fallback_provider: Optional[str],
    fallback_model: Optional[str],
    fallback_reason: str,
) -> None:
    """Mark that the call abandoned the primary provider.

    Records both the target (``fallback_provider`` / ``fallback_model``)
    and the *reason* tag so downstream UI can show the user *why* a
    different provider served the request.
    """
    if not isinstance(routing_out, dict):
        return
    routing_out["fallback_used"] = True
    routing_out["fallback_reason"] = fallback_reason
    routing_out["fallback_provider"] = fallback_provider or None
    routing_out["fallback_model"] = fallback_model or None


def resolve_routing(
    routing_out: Optional[Dict[str, Any]],
    *,
    resolved_provider: Optional[str],
    resolved_model: Optional[str],
) -> None:
    """Stamp the actual provider/model onto ``routing_out``.

    Called *after* any fallback resolution completes — i.e. the call has
    succeeded (or fatally failed) and we know who actually served it.
    """
    if not isinstance(routing_out, dict):
        return
    routing_out["resolved_provider"] = resolved_provider or None
    routing_out["resolved_model"] = resolved_model or None


def set_latency(
    routing_out: Optional[Dict[str, Any]],
    *,
    latency_ms: Optional[int],
) -> None:
    """Record the wall-clock time for the call (milliseconds).

    ``None`` and ``0`` are both treated as "no measurement" — a 0ms
    latency in SSE consumers almost always means "the call never finished"
    (e.g. an error path) and showing ``latency_ms=0`` in the UI is more
    confusing than omitting the field entirely.  Negative values are
    clamped to 0 (defensive against bad clocks).
    """
    if not isinstance(routing_out, dict):
        return
    if latency_ms is None or latency_ms == 0:
        return
    try:
        routing_out["latency_ms"] = max(0, int(latency_ms))
    except (TypeError, ValueError):
        pass


def set_cost(
    routing_out: Optional[Dict[str, Any]],
    *,
    cost_estimate_usd: Optional[float],
) -> None:
    """Record the estimated USD cost for the call.

    ``None`` (unknown pricing) and negative values are silently dropped so
    a buggy upstream caller cannot poison the SSE payload.
    """
    if not isinstance(routing_out, dict):
        return
    if cost_estimate_usd is None:
        return
    try:
        value = float(cost_estimate_usd)
    except (TypeError, ValueError):
        return
    if value < 0 or value != value:  # NaN check (value != value)
        return
    routing_out["cost_estimate_usd"] = value


def increment_retries(
    routing_out: Optional[Dict[str, Any]],
) -> None:
    """Bump the retry counter by 1 (capped at 99 to bound SSE size)."""
    if not isinstance(routing_out, dict):
        return
    current = routing_out.get("retries", 0)
    try:
        current_int = int(current)
    except (TypeError, ValueError):
        current_int = 0
    routing_out["retries"] = min(current_int + 1, 99)


def set_rule_id(
    routing_out: Optional[Dict[str, Any]],
    *,
    rule_id: Optional[str],
    params: Optional[Dict[str, Any]] = None,
) -> None:
    """Attach a routing-rule label (e.g. ``"vision_fallback_chain[1]"``).

    Pre-layer-2 callers pass only ``rule_id`` — the legacy hard-coded
    string label. The SSE payload is unchanged.

    CAND-080 layer-2 callers also pass ``params`` (a dict keyed by the
    rule's ``params_schema`` in :data:`KNOWN_RULES`). The params are
    written to ``routing_out["rule_params"]`` so the SSE consumer can
    parse the rule fire shape without regex-ing the label. When
    ``params`` is ``None`` or empty, ``rule_params`` is **not** written
    at all — that keeps the legacy "label only" payload byte-identical
    to the pre-layer-2 shape, which is the migration-safety guarantee
    the CAND-080 entry asked for ("preserve old rule label,
    additively expose new params").

    The rule_id itself is still the source of truth for *which* rule
    fired; ``params`` is metadata, not a routing input. A future
    CAND-080 layer 1 patch consumer validates ``params`` against
    ``KNOWN_RULES[rule_id].params_schema`` and rejects mismatches, but
    this function does not — pre-layer-2 callers that pass a free-form
    ``rule_id`` string keep working.
    """
    if not isinstance(routing_out, dict):
        return
    routing_out["rule_id"] = rule_id or None
    if params:
        routing_out["rule_params"] = dict(params)


def set_cost_threshold(
    routing_out: Optional[Dict[str, Any]],
    *,
    reason: str,
) -> None:
    """Mark that the call (or session) blew past the cost-aware-fallback
    threshold.

    ``reason`` is one of:

    - ``"request_budget_exceeded"`` — single call cost > per_request_max_usd
    - ``"session_budget_exceeded"`` — session total cost > per_session_max_usd

    Sets ``cost_threshold_exceeded=True`` so SSE consumers always see the
    flag (boolean defaults to False otherwise), and stamps the reason for
    front-end conditional rendering.
    """
    if not isinstance(routing_out, dict):
        return
    routing_out["cost_threshold_exceeded"] = True
    routing_out["cost_threshold_reason"] = reason or None


__all__ = [
    "RoutingDecision",
    "RuleSpec",
    "KNOWN_RULES",
    "init_routing_decision",
    "record_fallback",
    "resolve_routing",
    "set_latency",
    "set_cost",
    "increment_retries",
    "set_rule_id",
    "set_cost_threshold",
]
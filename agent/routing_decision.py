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

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to a JSON-friendly dict.

        Always includes ``mode``, ``fallback_used``, ``retries`` even when
        their values are falsy (they're scalar/cheap and downstream UI
        frequently checks them).  Other ``None``-valued fields are
        stripped so the SSE payload stays compact.
        """
        out: Dict[str, Any] = {
            "mode": self.mode,
            "fallback_used": bool(self.fallback_used),
            "retries": int(self.retries),
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
) -> None:
    """Attach a routing-rule label (e.g. ``"vision_fallback_chain[1]"``)."""
    if not isinstance(routing_out, dict):
        return
    routing_out["rule_id"] = rule_id or None


__all__ = [
    "RoutingDecision",
    "init_routing_decision",
    "record_fallback",
    "resolve_routing",
    "set_latency",
    "set_cost",
    "increment_retries",
    "set_rule_id",
]
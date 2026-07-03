"""S12 — Cost-aware fallback threshold checker.

When a single LLM call (auxiliary or main agent) exceeds
``agent.cost_aware_fallback.per_request_max_usd`` OR the cumulative
session spend exceeds ``agent.cost_aware_fallback.per_session_max_usd``,
the agent surfaces a routing-decision annotation so the front-end can
render a budget warning and (for the main agent path) the next call
proactively swaps to the next ``fallback_chain`` entry instead of
waiting for an outright failure.

This module is the *threshold logic* — pure data shaping + cheap
comparisons.  It does NOT touch the network, do client rebuilds, or
mutate the agent's primary runtime.  Those are the caller's job (see
``auxiliary_client.call_llm`` and ``conversation_loop._build_main_agent_routing_decision``).

Config shape (config.yaml):

    agent:
      cost_aware_fallback:
        enabled: true
        per_request_max_usd: 0.05      # warn if a single call exceeds this
        per_session_max_usd: 1.00      # escalate to next chain entry if session total exceeds this
        on_session_exceeded: warn      # 'warn' | 'fallback' — what to do when session budget blown

Disabled by default to preserve pre-S12 behavior.  When enabled with
default thresholds, behavior is "warn loudly, don't fail"; the
``on_session_exceeded=fallback`` switch is the proactive variant the
NEEDS_BACKLOG §需求 1 Phase 2 asks for.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Optional


# Default values baked into hermes_cli.config.DEFAULT_CONFIG — kept here as a
# single source of truth so tests can reference them without pulling config.
DEFAULT_PER_REQUEST_MAX_USD = 0.05
DEFAULT_PER_SESSION_MAX_USD = 1.00
DEFAULT_ON_SESSION_EXCEEDED = "warn"  # 'warn' | 'fallback'


@dataclass
class CostAwareFallbackConfig:
    """User-facing cost-aware fallback policy.

    Fields:
        enabled: master switch — when False, all checks are no-ops.
        per_request_max_usd: USD ceiling for a single LLM call.  When a
            call's estimated cost exceeds this we mark the routing_decision
            with ``cost_threshold_exceeded=True`` and
            ``cost_threshold_reason='request_budget_exceeded'``.  None = no
            per-request limit.
        per_session_max_usd: USD ceiling for the entire conversation
            session's running cost total.  Same annotation pattern as
            per-request, plus ``reason='session_budget_exceeded'``.  When
            ``on_session_exceeded='fallback'`` the agent proactively
            activates the next ``fallback_chain`` entry for subsequent
            calls.  None = no per-session limit.
        on_session_exceeded: action when the session budget is blown:
            ``'warn'`` (default — annotate + log, keep current provider)
            or ``'fallback'`` (annotate + log + call
            ``agent._try_activate_fallback`` to swap to the next chain
            entry on the next turn).
    """

    enabled: bool = False
    per_request_max_usd: Optional[float] = None
    per_session_max_usd: Optional[float] = None
    on_session_exceeded: str = DEFAULT_ON_SESSION_EXCEEDED  # 'warn' | 'fallback'

    @classmethod
    def from_dict(cls, raw: Any) -> "CostAwareFallbackConfig":
        """Parse from a config dict — missing keys fall back to defaults.

        Defensive against malformed configs (None, list, wrong types) —
        unknown shapes yield a disabled config (the safe no-op default)
        so a broken YAML line can't accidentally switch on the policy.
        """
        if not isinstance(raw, dict):
            return cls()

        enabled = bool(raw.get("enabled", False))
        per_request = _coerce_positive_float(raw.get("per_request_max_usd"))
        per_session = _coerce_positive_float(raw.get("per_session_max_usd"))
        on_exceeded = raw.get("on_session_exceeded", DEFAULT_ON_SESSION_EXCEEDED)
        if not isinstance(on_exceeded, str) or on_exceeded not in ("warn", "fallback"):
            on_exceeded = DEFAULT_ON_SESSION_EXCEEDED

        return cls(
            enabled=enabled,
            per_request_max_usd=per_request,
            per_session_max_usd=per_session,
            on_session_exceeded=on_exceeded,
        )


def _coerce_positive_float(value: Any) -> Optional[float]:
    """Return a positive float, or None if the value is missing / invalid.

    Negative numbers are clamped to None — a negative budget would be
    user-visible nonsense, and treating it as "no limit" matches the
    ``estimate_usage_cost`` defensive convention.
    """
    if value is None or value == "":
        return None
    try:
        f = float(value)
    except (TypeError, ValueError):
        return None
    if f != f:  # NaN check
        return None
    if f <= 0:
        return None
    return f


def check_request_cost_threshold(
    cost_usd: Optional[float],
    config: CostAwareFallbackConfig,
) -> Optional[str]:
    """Return a reason string if a single call's cost exceeded the per-request limit.

    Returns ``'request_budget_exceeded'`` when the cost is over the
    configured ``per_request_max_usd``, else ``None``.  No-op when the
    config is disabled or the cost is unknown (None / NaN / negative).
    """
    if not config.enabled:
        return None
    if config.per_request_max_usd is None:
        return None
    if cost_usd is None:
        return None
    try:
        cost = float(cost_usd)
    except (TypeError, ValueError):
        return None
    if cost != cost or cost < 0:  # NaN / negative → unknown cost, don't fire
        return None
    if cost > config.per_request_max_usd:
        return "request_budget_exceeded"
    return None


def check_session_cost_threshold(
    session_cost_usd: Optional[float],
    config: CostAwareFallbackConfig,
) -> Optional[str]:
    """Return a reason string if cumulative session cost exceeded the per-session limit.

    Same return convention as :func:`check_request_cost_threshold` but
    uses ``per_session_max_usd`` and returns ``'session_budget_exceeded'``.
    """
    if not config.enabled:
        return None
    if config.per_session_max_usd is None:
        return None
    if session_cost_usd is None:
        return None
    try:
        cost = float(session_cost_usd)
    except (TypeError, ValueError):
        return None
    if cost != cost or cost < 0:
        return None
    if cost > config.per_session_max_usd:
        return "session_budget_exceeded"
    return None


__all__ = [
    "DEFAULT_PER_REQUEST_MAX_USD",
    "DEFAULT_PER_SESSION_MAX_USD",
    "DEFAULT_ON_SESSION_EXCEEDED",
    "CostAwareFallbackConfig",
    "check_request_cost_threshold",
    "check_session_cost_threshold",
]
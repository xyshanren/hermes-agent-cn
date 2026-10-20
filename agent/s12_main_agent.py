"""CN S12: main-agent routing metadata + session cost budget.

The upstream turn loop was restructured into phases; per-response usage
accounting now lives in ``agent/turn_usage.py``. These two helpers are
CN-original (upstream has no ``routing_decision`` concept) and moved into
their own module with the S12 metadata they feed; ``agent/conversation_loop``
re-exports them so existing imports and tests keep working.
"""

from __future__ import annotations

import logging
import time
from typing import Any, Dict, Optional

logger = logging.getLogger("agent.conversation_loop")


def _build_main_agent_routing_decision(
    agent,
    *,
    api_duration: float,
    retry_count: int,
) -> Optional[Dict[str, Any]]:
    """Build the per-turn ``routing_decision`` dict for the main agent path.

    The main agent's chat-completion call lives in ``run_agent.py`` and does
    not route through ``auxiliary_client.call_llm`` / ``async_call_llm``,
    so its routing metadata is synthesized here from the agent's own
    per-turn state (``_primary_runtime``, ``provider``, ``model``,
    ``_fallback_activated``, the last API call wall-clock stamped by
    ``chat_completion_helpers``, and the turn's retry count).  Auxiliary
    tasks route through ``call_llm`` and surface their decisions via
    ``agent._last_routing_decision`` directly.

    Returns ``None`` when the agent has no resolvable model/provider (test
    stubs, dry-run mode) — callers should treat that as "skip" rather than
    emit an empty dict.
    """
    from agent.routing_decision import (
        init_routing_decision,
        record_fallback,
        resolve_routing,
        set_latency,
        set_rule_id,
    )

    resolved_provider = (str(getattr(agent, "provider", "") or "")).strip() or None
    resolved_model = (str(getattr(agent, "model", "") or "")).strip() or None
    if not (resolved_provider or resolved_model):
        return None

    primary = getattr(agent, "_primary_runtime", {}) or {}
    primary_provider = (str(primary.get("provider") or "")).strip() or resolved_provider
    primary_model = (str(primary.get("model") or "")).strip() or resolved_model

    out: Dict[str, Any] = {}
    init_routing_decision(
        out,
        mode="native",
        primary_provider=primary_provider,
        primary_model=primary_model,
    )
    resolve_routing(
        out,
        resolved_provider=resolved_provider,
        resolved_model=resolved_model,
    )

    if getattr(agent, "_fallback_activated", False):
        # The agent swapped to a fallback chain entry — surface the chain
        # position so the front-end can render "fell back to provider[1]".
        chain = list(getattr(agent, "_fallback_chain", []) or [])
        idx = max(0, int(getattr(agent, "_fallback_index", 1) or 1) - 1)
        fb_entry = chain[idx] if 0 <= idx < len(chain) else None
        fb_provider = None
        fb_model = None
        if isinstance(fb_entry, dict):
            fb_provider = (str(fb_entry.get("provider") or "")).strip() or None
            fb_model = (str(fb_entry.get("model") or "")).strip() or None
        record_fallback(
            out,
            fallback_provider=fb_provider or resolved_provider,
            fallback_model=fb_model or resolved_model,
            fallback_reason="fallback_chain",
        )
        if fb_provider:
            # CAND-080 layer 2: rule_id is the KNOWN_RULES family name and
            # the chain position/provider travel as structured ``rule_params``
            # (see agent.routing_decision.KNOWN_RULES["fallback_chain"]).
            set_rule_id(
                out,
                rule_id="fallback_chain",
                params={"chain_index": idx, "provider": fb_provider},
            )

    if retry_count and retry_count > 0:
        out["retries"] = int(retry_count)

    if api_duration and api_duration > 0:
        set_latency(out, latency_ms=int(api_duration * 1000))

    # Strip keys we did not actually populate so the in-memory dict matches
    # the SSE payload (``mode`` / ``fallback_used`` / ``retries`` /
    # ``cost_threshold_exceeded`` are always present — they're scalar/bool
    # and the front-end checks them in conditional rendering).
    for key in ("cost_estimate_usd", "latency_ms", "rule_id"):
        if out.get(key) is None:
            out.pop(key, None)

    return out


def _check_session_cost_threshold_and_act(
    agent,
    *,
    session_cost_usd: Optional[float],
    routing_decision: Optional[Dict[str, Any]],
) -> Optional[str]:
    """S12 P2: enforce the agent-level session cost budget.

    Called once per successful turn *after* the per-turn USD has been
    added to ``agent.session_estimated_cost_usd``.  Behavior:

    1. Load ``agent.cost_aware_fallback`` from config (lazy — cheap when off).
    2. If disabled, or below the configured ``per_session_max_usd``,
       return ``None`` (no-op).
    3. Otherwise stamp
       ``routing_decision.cost_threshold_exceeded=True`` +
       ``cost_threshold_reason='session_budget_exceeded'`` so the SSE
       consumer can render a budget warning.
    4. When ``on_session_exceeded == 'fallback'`` AND ``agent._fallback_chain``
       has at least one unused entry, call ``agent._try_activate_fallback(...)``
       so the next turn swaps to the next provider in the chain even if
       the current one didn't outright fail.

    Returns the reason string (``'session_budget_exceeded'``) when the
    threshold fired, else ``None``.  Never raises — exceptions from the
    fallback swap are logged and swallowed so a broken chain entry
    can't crash the turn that already succeeded.
    """
    try:
        from agent.cost_aware_fallback import (
            CostAwareFallbackConfig,
            check_session_cost_threshold,
        )
        from agent.routing_decision import set_cost_threshold
    except ImportError:  # pragma: no cover
        return None

    raw_cfg = None
    try:
        from hermes_cli.config import load_config
        full = load_config() or {}
        raw_cfg = (full.get("agent") or {}).get("cost_aware_fallback")
    except Exception:
        raw_cfg = None
    if not raw_cfg:
        return None
    cfg = CostAwareFallbackConfig.from_dict(raw_cfg)

    reason = check_session_cost_threshold(session_cost_usd, cfg)
    if not reason:
        return None

    if isinstance(routing_decision, dict):
        set_cost_threshold(routing_decision, reason=reason)

    if cfg.on_session_exceeded == "fallback":
        chain = list(getattr(agent, "_fallback_chain", []) or [])
        fallback_index = int(getattr(agent, "_fallback_index", 0) or 0)
        if chain and fallback_index < len(chain):
            try:
                activate = getattr(agent, "_try_activate_fallback", None)
                if callable(activate):
                    activate(reason=None)
                    if isinstance(routing_decision, dict):
                        from agent.routing_decision import record_fallback, set_rule_id

                        new_index = int(
                            getattr(agent, "_fallback_index", fallback_index + 1) or 0
                        )
                        fb_entry = (
                            chain[new_index - 1] if 0 < new_index <= len(chain) else None
                        )
                        fb_provider = None
                        fb_model = None
                        if isinstance(fb_entry, dict):
                            fb_provider = (str(fb_entry.get("provider") or "")).strip() or None
                            fb_model = (str(fb_entry.get("model") or "")).strip() or None
                        record_fallback(
                            routing_decision,
                            fallback_provider=fb_provider,
                            fallback_model=fb_model,
                            fallback_reason="cost_aware_session_budget_exceeded",
                        )
                        if fb_provider:
                            set_rule_id(
                                routing_decision,
                                rule_id="cost_aware_fallback",
                                params={
                                    "chain_index": new_index - 1,
                                    "provider": fb_provider,
                                },
                            )
                    logger.info(
                        "S12 P2: session cost threshold exceeded — activated "
                        "fallback chain entry %d",
                        fallback_index,
                    )
            except Exception as swap_exc:  # pragma: no cover - defensive
                logger.debug("S12 P2: fallback swap after budget blowout failed: %s", swap_exc)

    return reason

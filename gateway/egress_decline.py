"""Egress DECLINE classification (gateway core).

A decline is a DEFINITE authorization refusal: the transport refused the
destination. It must never be laundered into an ordinary failure, because
every fallback lane that treats a failure as "retry as plain text" would then
re-send the very content the destination refused.

The contract survives the CN subtraction of the connector relay: the local
session surface still produces a structured decline (a clarify question no
viewer can answer), and the send lanes still need to recognise one.
"""

from __future__ import annotations

from typing import Any

# The structured code a decline carries (preferred signal).
EGRESS_DECLINE_CODE = "egress_declined"

# Fallback signal: the uniform decline sentence. Matched case-insensitively on
# this fragment ONLY — the rest of the sentence is deliberately uninformative
# and must not be parsed.
EGRESS_DECLINE_MARKER = "egress declined:"

# Transport-ambiguity text. A lost ack means the frame MAY have been delivered,
# so it is never an authorization refusal. Needed because the text-only branch
# of `declined_send` sees no structured `ambiguous` flag to check.
_AMBIGUOUS_MARKER = "ack lost"


def is_egress_decline(result: Any) -> bool:
    """True when *result* is a REFUSAL of the destination.

    A decline is distinguished from every other outbound failure by three
    properties, all required:

    * it failed (``success`` is falsey),
    * it is DEFINITE — an ``ambiguous`` result (lost ack, mid-write drop) says
      the frame may well have been applied, so it is a transport outcome, not
      an authorization one,
    * it carries the decline code, or its uniform decline text.
    """
    if not isinstance(result, dict):
        return False
    if result.get("success"):
        return False
    if result.get("ambiguous"):
        return False
    if str(result.get("code") or "") == EGRESS_DECLINE_CODE:
        return True
    return EGRESS_DECLINE_MARKER in str(result.get("error") or "").lower()


def declined_send(result: Any) -> bool:
    """True when a SEND RESULT object carries a destination refusal.

    ``is_egress_decline`` classifies a raw DICT. Callers hold a ``SendResult``,
    so the raw body is read from ``raw_response``; a projection that drops it
    leaves only the error text, which the uniform decline sentence still
    classifies.
    """
    raw = getattr(result, "raw_response", None)
    if isinstance(raw, dict):
        return is_egress_decline(raw)
    error = getattr(result, "error", None)
    if not error:
        return False
    if _AMBIGUOUS_MARKER in str(error).lower():
        # DEFENCE IN DEPTH for a lost `ambiguous` flag. The text branch exists
        # only for transports that send no structured body, so it cannot see
        # `ambiguous` — and a projection that drops `raw_response` therefore
        # turned "ack lost" into a definite refusal, terminating the run for a
        # frame that may well have been delivered. Any error text that says the
        # ack was lost is treated as a transport outcome, never authorization.
        return False
    return is_egress_decline({"success": False, "error": error})


def decline_error(result: Any) -> str:
    """The decline text, verbatim, for surfacing to the caller.

    Verbatim on purpose: the gateway's job is to report faithfully THAT a
    decline happened, not to explain or re-word it.
    """
    if isinstance(result, dict):
        error = result.get("error")
        if error:
            return str(error)
    return "egress declined"

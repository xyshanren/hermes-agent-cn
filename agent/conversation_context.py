"""Ambient conversation id for cross-module lineage tracking.

K-4 port of upstream ``9ce0e67f2 feat(portal): ambient conversation context
entangles aux/MoA/delegate calls``.

ContextVar-based ``conversation_id`` propagates across the three places an
agent can fan out from a single user turn:

1. ``auxiliary_client.call_llm`` / ``async_call_llm`` — judge, compressor,
   web extract, vision, every aux task routes its calls through this
   module so a MoA fan-out started by the judge stays grouped.
2. ``tools.mixture_of_agents_tool.mixture_of_agents_tool`` — every
   reference model + the aggregator gets tagged with the same
   ``conversation_id`` so post-hoc routing_decision traces can collapse
   them to a single conversation.
3. ``tools.delegate_tool.delegate_task`` — child agent session inherits
   the parent's ``conversation_id`` so the SessionDB lineage query
   resolves back to the root turn.

Reads: ``current_conversation_id()`` returns the ambient id (or None).
Writes: ``set_conversation_id(value)`` is a context manager that restores
the previous value on exit (matches upstream ``ambient_conversation_id``).
``bind_conversation_id(value)`` is a function-call variant for
non-context-manager call sites (sync ``call_llm``, async
``async_call_llm``).

Caveats
-------
- ContextVars follow Python's asyncio task scoping — each ``asyncio.create_task``
  inherits the ambient id at the moment of creation, and per-task overrides
  inside the task do not leak back. This is what we want for the
  MoA/delegate fan-out, where each child run is a fresh task that
  inherits the parent's id and then overrides per-request as needed.
- ``ContextVar(default=None)`` — code that runs outside any explicit
  ``set`` sees ``None`` and should treat that as "no ambient id" (the
  legacy pre-K-4 behaviour).
"""

from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
from typing import Iterator, Optional

# Single source of truth for the ambient conversation id. Importing this
# module (e.g. via ``from agent.conversation_context import current_conversation_id``)
# is enough to make the value visible to whichever module set it last in
# the same logical task — the same ContextVar instance is shared.
_ambient_conversation_id: ContextVar[Optional[str]] = ContextVar(
    "ambient_conversation_id", default=None
)


def current_conversation_id() -> Optional[str]:
    """Return the ambient conversation id for the current task, or None
    when no caller has set one (pre-K-4 behaviour)."""
    return _ambient_conversation_id.get()


@contextmanager
def set_conversation_id(value: Optional[str]) -> Iterator[Optional[str]]:
    """Context manager that binds ``value`` as the ambient id for the
    duration of the ``with`` block and restores the previous value on
    exit. Use this at the boundary of any fan-out so children inherit
    a stable id."""
    token = _ambient_conversation_id.set(value)
    try:
        yield value
    finally:
        _ambient_conversation_id.reset(token)


def bind_conversation_id(value: Optional[str]):
    """Function-call variant of :func:`set_conversation_id` for call sites
    that cannot easily use a ``with`` block (e.g. functions decorated with
    ``functools.wraps``). Returns a no-arg ``release`` callable that the
    caller must invoke when the binding is no longer needed.

    Use sparingly — the context-manager form is preferred for readability.
    Most call sites (call_llm, async_call_llm, mixture_of_agents_tool,
    delegate_task) accept an explicit ``conversation_id=`` parameter and
    can wrap their body in ``set_conversation_id(...)`` cleanly.
    """
    token = _ambient_conversation_id.set(value)

    def _release() -> None:
        _ambient_conversation_id.reset(token)

    return _release

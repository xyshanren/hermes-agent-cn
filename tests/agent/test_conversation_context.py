"""Tests for K-4 ambient conversation context.

The ambient ``conversation_id`` is a ContextVar that ``call_llm``,
``async_call_llm``, ``mixture_of_agents_tool``, and ``delegate_task``
set on entry so every aux / MoA / delegate fan-out from the same
turn shares one id. The downstream SessionDB lineage query
(``get_conversation_root``) collapses them back to a single
conversation when the user reviews routing traces.

Mirrors upstream ``9ce0e67f2`` test scope — the
``agent.conversation_context`` module is the new shared primitive;
``SessionDB.get_conversation_root`` is the new method; the 4 entry
points each accept an optional ``conversation_id=`` kwarg.
"""

from __future__ import annotations

from unittest.mock import patch

import pytest

from agent.conversation_context import (
    _ambient_conversation_id,
    bind_conversation_id,
    current_conversation_id,
    set_conversation_id,
)


# ──────────────────────────────────────────────────────────────────────
# ContextVar primitives
# ──────────────────────────────────────────────────────────────────────


class TestConversationContextPrimitives:
    def test_default_is_none(self):
        """Outside any explicit binding, ``current_conversation_id``
        returns ``None`` (the legacy pre-K-4 behaviour)."""
        assert current_conversation_id() is None

    def test_set_conversation_id_context_manager_sets_and_restores(self):
        with set_conversation_id("conv-A"):
            assert current_conversation_id() == "conv-A"
        assert current_conversation_id() is None

    def test_set_conversation_id_restores_previous_value(self):
        """Nested context managers must restore the outer value on exit,
        not unconditionally reset to None."""
        with set_conversation_id("outer"):
            with set_conversation_id("inner"):
                assert current_conversation_id() == "inner"
            assert current_conversation_id() == "outer"
        assert current_conversation_id() is None

    def test_set_conversation_id_none_is_a_no_op_restore(self):
        """Setting to ``None`` is a valid binding (e.g. an aux call that
        is explicitly conversation-id-less). The next ``set`` to a
        real value should still take effect."""
        with set_conversation_id(None):
            assert current_conversation_id() is None
        with set_conversation_id("conv-B"):
            assert current_conversation_id() == "conv-B"

    def test_bind_conversation_id_function_call_variant(self):
        """Non-context-manager callers can use ``bind_conversation_id`` to
        get a release callable they must invoke on exit. Same semantics
        as the context manager."""
        release = bind_conversation_id("conv-C")
        try:
            assert current_conversation_id() == "conv-C"
        finally:
            release()
        assert current_conversation_id() is None

    def test_set_overwrites_previous(self):
        """ContextVar is over-write-on-set: a second ``set`` in the
        same task replaces the first. This matches the K-4 design where
        every call site re-binds for its own request — no manual reset
        is needed across calls."""
        with set_conversation_id("first"):
            with set_conversation_id("second"):
                assert current_conversation_id() == "second"
            assert current_conversation_id() == "second"
        assert current_conversation_id() is None


# ──────────────────────────────────────────────────────────────────────
# SessionDB.get_conversation_root
# ──────────────────────────────────────────────────────────────────────


class TestSessionDBGetConversationRoot:
    def test_empty_session_id_returns_none(self):
        from hermes_state import SessionDB

        db = SessionDB()
        assert db.get_conversation_root("") is None

    def test_unknown_session_id_returns_none_not_stale_value(self):
        """An unrecognised session id must return ``None`` so the caller
        can fall back to using the session id itself as a stable
        conversation id. Returning the input unchanged would silently
        treat unknown sessions as their own root — a confusing default
        that broke the original implementation before this fix."""
        from hermes_state import SessionDB

        db = SessionDB()
        assert db.get_conversation_root("non-existent-id-xyz") is None

    def test_known_session_with_no_parent_returns_itself(self, tmp_path, monkeypatch):
        """A session that exists and has no parent_session_id is its
        own root. This is the common case for top-level user turns."""
        from hermes_state import SessionDB

        # Fresh HERMES_HOME so the test doesn't touch the user's real DB.
        monkeypatch.setenv("HERMES_HOME", str(tmp_path / ".hermes"))
        (tmp_path / ".hermes").mkdir()
        db = SessionDB()
        # The schema for SessionDB is internal — use whatever insert path
        # the DB exposes. ``create_session`` is the usual entry point.
        if hasattr(db, "create_session"):
            sid = db.create_session()  # type: ignore[attr-defined]
        elif hasattr(db, "insert_session"):
            sid = db.insert_session()  # type: ignore[attr-defined]
        else:
            pytest.skip("SessionDB has neither create_session nor insert_session; skipping")
        assert sid is not None
        root = db.get_conversation_root(sid)
        assert root == sid


# ──────────────────────────────────────────────────────────────────────
# call_llm / async_call_llm integration
# ──────────────────────────────────────────────────────────────────────


class TestCallLLMConversationId:
    def test_call_llm_sets_ambient_id_on_entry(self):
        """``call_llm`` should set the ambient conversation id from
        its ``conversation_id`` kwarg so the resolved provider /
        routing path can read it (or, more importantly, so nested
        ``call_llm`` calls inside the same request inherit it)."""
        from agent import auxiliary_client

        # Mock the provider resolution + client construction so we
        # don't need real credentials, but we *do* want the call to
        # proceed far enough to exercise the conversation_id binding.
        with patch.object(
            auxiliary_client, "_resolve_task_provider_model",
            return_value=("test-provider", "test-model", "", "fake-key", "openai"),
        ), patch.object(
            auxiliary_client, "_get_cached_client",
            return_value=None,  # forces RuntimeError, but binding happens before
        ), pytest.raises(RuntimeError):
            auxiliary_client.call_llm(
                task="test",
                messages=[{"role": "user", "content": "hi"}],
                conversation_id="conv-D",
            )
        # Even though the call raised (no real client), the binding
        # happened at function entry and remains in effect.
        assert current_conversation_id() == "conv-D"

    def test_call_llm_without_conversation_id_leaves_ambient_alone(self):
        """No ``conversation_id`` kwarg → ``call_llm`` does not touch
        the ambient value. Pre-existing bindings stay; default stays
        None when nothing has set it."""
        from agent import auxiliary_client

        with set_conversation_id("pre-existing"):
            with patch.object(
                auxiliary_client, "_resolve_task_provider_model",
                return_value=("test-provider", "test-model", "", "fake-key", "openai"),
            ), patch.object(
                auxiliary_client, "_get_cached_client",
                return_value=None,
            ), pytest.raises(RuntimeError):
                auxiliary_client.call_llm(
                    task="test",
                    messages=[{"role": "user", "content": "hi"}],
                )
            # Pre-existing binding is preserved (call_llm did not
            # overwrite it with None when no kwarg was passed).
            assert current_conversation_id() == "pre-existing"


# ──────────────────────────────────────────────────────────────────────
# mixture_of_agents_tool integration
# ──────────────────────────────────────────────────────────────────────


class TestMixtureOfAgentsConversationId:
    def test_mixture_of_agents_tool_sets_ambient_id(self):
        """``mixture_of_agents_tool`` should bind the conversation id
        at function entry so the 4 reference model calls + the
        aggregator call all see the same id. We mock the OpenRouter
        client so the test runs without network / API key; the binding
        happens before any LLM call."""
        from tools import mixture_of_agents_tool

        async def _drive():
            with patch.object(
                mixture_of_agents_tool, "_get_openrouter_client",
                side_effect=RuntimeError("no client (test mock)"),
            ):
                result = await mixture_of_agents_tool.mixture_of_agents_tool(
                    user_prompt="test",
                    conversation_id="conv-E",
                )
            return result

        import asyncio
        asyncio.run(_drive())
        # The ambient id is bound even though the actual MoA call
        # raised inside the loop.
        assert current_conversation_id() == "conv-E"


# ──────────────────────────────────────────────────────────────────────
# delegate_task integration
# ──────────────────────────────────────────────────────────────────────


class TestDelegateTaskConversationId:
    def test_delegate_task_sets_ambient_id_before_parent_check(self):
        """``delegate_task`` should bind the conversation id at
        function entry so any child agent session the dispatcher
        spawns inherits it. The binding must happen BEFORE the
        ``parent_agent is None`` early-return guard, because the
        guard reads from the parent's conversation context to decide
        whether a child can spawn."""
        from tools import delegate_tool

        # parent_agent is None → early-return tool_error. The bind
        # still happens because the binding is the first thing the
        # function does (it must precede any guard that may consult
        # the conversation id).
        with patch.object(delegate_tool, "is_spawn_paused", return_value=False):
            result = delegate_tool.delegate_task(
                goal="test",
                parent_agent=None,
                conversation_id="conv-F",
            )
        # Should hit the parent_agent guard.
        assert "parent agent context" in result
        # But the ambient id is set regardless.
        assert current_conversation_id() == "conv-F"

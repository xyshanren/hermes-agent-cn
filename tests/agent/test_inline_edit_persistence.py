"""Real edit -> executor -> SQLite -> history projection, without model calls."""
import copy
import contextlib
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from tests.agent.test_tool_call_incremental_persistence import (
    _attach_real_session_db,
    _make_agent,
    _mock_tool_call,
)


def test_orphaned_preview_never_attaches_to_a_reused_call_id(monkeypatch):
    import tui_gateway.server as progress

    emitted = []
    monkeypatch.setattr(progress, "_emit_tool_lifecycle", lambda kind, sid, name, args, payload: emitted.append(payload))
    session = {"tool_result_metadata": {"call_0": {"inline_diff": "STALE"}}}
    monkeypatch.setitem(progress._sessions, "reuse", session)
    # The prepared call's flush failed, so its completion never fired; a later call reuses the id.
    progress._on_tool_start("reuse", "call_0", "todo", {})
    progress._on_tool_complete("reuse", "call_0", "todo", {}, '{"todos": []}')
    assert emitted and not any("inline_diff" in payload for payload in emitted)
    assert session["tool_result_metadata"] == {}

    # A completion dropped as stale still consumes its prepared entry.
    session["tool_result_metadata"]["call_1"] = {}
    monkeypatch.setattr(progress, "_connector_lifecycle_is_stale", lambda *a: True)
    progress._on_tool_complete("reuse", "call_1", "todo", {}, "{}")
    assert session["tool_result_metadata"] == {}

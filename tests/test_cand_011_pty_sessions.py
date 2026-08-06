"""Tests for CAND-011 (Sprint 7 Wave 2): PTY sessions keep-alive."""

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent


def test_pty_sessions_module_exists():
    p = REPO / "hermes_cli" / "pty_sessions.py"
    assert p.exists()
    src = p.read_text(encoding="utf-8")
    for fn in ("pty_session_registry", "pty_session_drain_attach_detach",
               "pty_session_ringbuffer", "apply_pty_sessions"):
        assert f"def {fn}" in src


def test_pty_sessions_does_not_modify_pty():
    cli_src = (REPO / "cli.py").read_text(encoding="utf-8")
    assert "pty_sessions" not in cli_src


def test_cand_011_1_pty_session_registry_live():
    sys.path.insert(0, str(REPO))
    from hermes_cli.pty_sessions import pty_session_registry
    result = pty_session_registry(capacity=100)
    assert result["capacity"] == 100
    assert "active_count" in result


def test_cand_011_2_pty_session_drain_attach_detach_live():
    sys.path.insert(0, str(REPO))
    from hermes_cli.pty_sessions import (
        pty_session_drain_attach_detach, apply_pty_sessions,
    )
    # 用 apply_pty_sessions 触发 register 后再单独测 attach
    apply_pty_sessions("sess-pty-1", op="attach")
    # attach 已存在 session → True
    result_attach = pty_session_drain_attach_detach("sess-pty-1", "attach")
    assert result_attach["op"] == "attach"
    assert result_attach["attached"] is True
    # detach
    result_detach = pty_session_drain_attach_detach("sess-pty-1", "detach")
    assert result_detach["op"] == "detach"
    assert result_detach["attached"] is False
    # eof_close → closed
    result_eof = pty_session_drain_attach_detach("sess-pty-1", "eof_close")
    assert result_eof["op"] == "eof_close"
    assert result_eof["closed"] is True
    # 0 存在 session → attached=False + error
    result_missing = pty_session_drain_attach_detach("nonexistent", "attach")
    assert result_missing["attached"] is False
    assert "error" in result_missing


def test_cand_011_3_pty_session_ringbuffer_live():
    sys.path.insert(0, str(REPO))
    from hermes_cli.pty_sessions import pty_session_ringbuffer
    # append 3 lines
    pty_session_ringbuffer("rb-1", line="line 1")
    pty_session_ringbuffer("rb-1", line="line 2")
    pty_session_ringbuffer("rb-1", line="line 3")
    result = pty_session_ringbuffer("rb-1")
    assert result["session_id"] == "rb-1"
    assert result["buffer_size"] == 3
    # capacity bound
    rb_cap = pty_session_ringbuffer("rb-2", capacity=2)
    pty_session_ringbuffer("rb-2", line="a")
    pty_session_ringbuffer("rb-2", line="b")
    pty_session_ringbuffer("rb-2", line="c")  # 超出 capacity
    result_overflow = pty_session_ringbuffer("rb-2")
    assert result_overflow["buffer_size"] == 2  # capacity bound


def test_apply_pty_sessions_combined_entry_live():
    sys.path.insert(0, str(REPO))
    from hermes_cli.pty_sessions import apply_pty_sessions
    # attach + ringbuffer append
    result = apply_pty_sessions("pty-x", op="attach", line="hello", capacity=50)
    assert isinstance(result, dict)
    assert set(result.keys()) == {"registry", "drain_attach_detach", "ringbuffer"}
    assert result["registry"]["capacity"] == 50
    assert result["drain_attach_detach"]["attached"] is True
    assert result["ringbuffer"]["buffer_size"] == 1
    # drain → lines 包含
    result_drain = apply_pty_sessions("pty-x", op="drain")
    assert result_drain["drain_attach_detach"]["lines"] == ["hello"]
    # buffer clear after drain
    assert result_drain["ringbuffer"]["buffer_size"] == 0

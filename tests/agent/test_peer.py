"""Tests for agent.peer (Sprint 16 档 C.2 hermes peer 协议层 + 路由层).

跟 mavis MEMORY:
- 后端先调查再设计 (memory:13-17): 协议层 100% 复用 A2A plugin 5 工具, 0 重复实现
- UX 倒退审计 (memory:19-23): register_peer_tools 0 在 plugin path 时 silent skip
- Cherry-pick split bug class (memory:7-11): 0 改 routing_decision 决策树, peer 走显式 user API

跟 Sprint 14/15 in-scope fix 1:1 配对 (跟 user 9-03 提醒 "每个 sprint 必须做好测试" 1:1).

跟 v0.21 upstream "hermes peer" 协议 1:1 配对 (Cat 4 借鉴 + Cat 2 原创 混合).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


# ============================================================
# 5 命令测试 (peer_discover / peer_call / peer_list / peer_history / peer_run)
# ============================================================


# CN subtraction: the A2A platform plugin is not part of this build, so the
# delegation contract is exercised against a STUB a2a module injected into
# sys.modules. The peer layer imports it lazily inside each command, so a
# stubbed module is exactly what the layer sees.
def _stub_a2a_tools(**attrs):
    """Install a stub ``plugins.platforms.a2a.tools`` module; return it.

    The whole ``plugins.platforms.a2a`` package chain is stubbed: the import
    machinery walks the parents, so stubbing only the leaf is not enough.
    """
    import types
    import plugins.platforms

    a2a_pkg = types.ModuleType("plugins.platforms.a2a")
    tools_mod = types.ModuleType("plugins.platforms.a2a.tools")
    for name, value in attrs.items():
        setattr(tools_mod, name, value)
    a2a_pkg.tools = tools_mod
    setattr(plugins.platforms, "a2a", a2a_pkg)
    sys.modules["plugins.platforms.a2a"] = a2a_pkg
    sys.modules["plugins.platforms.a2a.tools"] = tools_mod
    return tools_mod


def _a2a_stub_context(**attrs):
    """Context manager that stubs the a2a tools module and restores sys.modules."""
    from contextlib import contextmanager

    @contextmanager
    def _cm():
        import plugins.platforms

        saved_modules = {k: sys.modules.get(k) for k in ("plugins.platforms.a2a", "plugins.platforms.a2a.tools")}
        saved_attr = getattr(plugins.platforms, "a2a", None)
        module = _stub_a2a_tools(**attrs)
        try:
            yield module
        finally:
            for key, value in saved_modules.items():
                if value is None:
                    sys.modules.pop(key, None)
                else:
                    sys.modules[key] = value
            if saved_attr is None:
                try:
                    delattr(plugins.platforms, "a2a")
                except AttributeError:
                    pass
            else:
                setattr(plugins.platforms, "a2a", saved_attr)
    return _cm()


def test_peer_discover_delegates_to_a2a_discover():
    """peer_discover 100% 复用 a2a_discover (Cat 4 借鉴, 0 重复实现)."""
    import agent.peer as peer

    calls = []

    def _fake_discover(args, **_):
        calls.append(args)
        return "discover-result"

    with _a2a_stub_context(a2a_discover=_fake_discover):
        result = peer.peer_discover({"url": "http://localhost:9999"})
    assert result == "discover-result"
    assert len(calls) == 1


def test_peer_call_persists_user_and_assistant_messages(tmp_path, monkeypatch):
    """peer_call 调 a2a_call 后, user + assistant message 持久化到 chat.jsonl."""
    import agent.peer as peer

    monkeypatch.setenv("HERMES_HOME", str(tmp_path))

    calls = []

    def _fake_call(args, **_):
        calls.append(args)
        return "assistant-reply-text"

    with _a2a_stub_context(a2a_call=_fake_call):
        result = peer.peer_call(
            {"peer": "alpha", "message": "user-hello"},
        )

    assert result == "assistant-reply-text"
    assert len(calls) == 1

    chat_path = tmp_path / "peers" / "alpha" / "chat.jsonl"
    assert chat_path.exists()
    entries = [json.loads(line) for line in chat_path.read_text(encoding="utf-8").splitlines() if line]
    assert len(entries) == 2
    assert entries[0]["role"] == "user"
    assert entries[0]["content"] == "user-hello"
    assert entries[1]["role"] == "assistant"
    assert entries[1]["content"] == "assistant-reply-text"


def test_peer_call_missing_peer_returns_error(tmp_path, monkeypatch):
    """peer_call 没传 peer → Error 字符串 (跟 a2a_call 1:1 配对)."""
    import agent.peer as peer

    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    result = peer.peer_call({"message": "hi"})
    assert result.startswith("Error")
    assert "peer" in result.lower()


def test_peer_call_error_result_does_not_persist_assistant(tmp_path, monkeypatch):
    """peer_call 失败 (Error 前缀) → 0 持久化 assistant (跟 mavis 4 件套 1:1)."""
    import agent.peer as peer

    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    with _a2a_stub_context(a2a_call=lambda args, **_: "Error: upstream 500"):
        result = peer.peer_call({"peer": "alpha", "message": "hi"})

    assert result.startswith("Error")
    chat_path = tmp_path / "peers" / "alpha" / "chat.jsonl"
    # user message 持久化, assistant 0 持久化
    if chat_path.exists():
        entries = [json.loads(line) for line in chat_path.read_text(encoding="utf-8").splitlines() if line]
        for entry in entries:
            assert entry["role"] != "assistant"


def test_peer_list_empty_when_no_peers(tmp_path, monkeypatch):
    """0 ~/.hermes/peers/ → No peers configured (跟 mavis 4 件套 1:1 配对)."""
    import agent.peer as peer

    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    result = peer.peer_list()
    assert "no peers" in result.lower() or "0 peers" in result.lower()


def test_peer_list_shows_peers_with_msg_count(tmp_path, monkeypatch):
    """~/.hermes/peers/<name>/chat.jsonl 存在 → 列 peer name + msg count."""
    import agent.peer as peer

    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    (tmp_path / "peers" / "alpha" / "chat.jsonl").parent.mkdir(parents=True)
    (tmp_path / "peers" / "alpha" / "chat.jsonl").write_text(
        '{"ts": 1, "role": "user", "content": "hi"}\n'
        '{"ts": 2, "role": "assistant", "content": "hello"}\n',
        encoding="utf-8",
    )
    (tmp_path / "peers" / "beta").mkdir(parents=True)

    result = peer.peer_list()
    assert "alpha" in result
    assert "2 messages" in result
    assert "beta" in result
    assert "0 messages" in result


def test_peer_history_reads_chat_jsonl(tmp_path, monkeypatch):
    """peer_history 列 chat.jsonl 历史 (Cat 6 内生 1:1 配对 cron/notepad)."""
    import agent.peer as peer

    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    (tmp_path / "peers" / "alpha" / "chat.jsonl").parent.mkdir(parents=True)
    (tmp_path / "peers" / "alpha" / "chat.jsonl").write_text(
        '{"ts": 1.0, "role": "user", "content": "hi-here"}\n',
        encoding="utf-8",
    )
    result = peer.peer_history({"peer": "alpha"})
    assert "alpha" in result
    assert "user" in result
    assert "hi-here" in result


def test_peer_history_missing_peer_returns_error():
    """peer_history 0 peer → Error."""
    import agent.peer as peer

    result = peer.peer_history({})
    assert result.startswith("Error")


def test_peer_run_delegates_to_a2a_orchestrate_persists_last_task(tmp_path, monkeypatch):
    """peer_run 调 a2a_orchestrate 后, 持久化 last_task.txt (Cat 6 内生)."""
    import agent.peer as peer

    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    calls = []

    def _fake_orchestrate(args, **_):
        calls.append(args)
        return "task-id-abc-123"

    with _a2a_stub_context(a2a_orchestrate=_fake_orchestrate):
        result = peer.peer_run({"peer": "alpha", "message": "long-task"})

    assert result == "task-id-abc-123"
    assert len(calls) == 1
    last_task = (tmp_path / "peers" / "alpha" / "last_task.txt").read_text(encoding="utf-8")
    assert last_task == "task-id-abc-123"


# ============================================================
# 路由层测试 (route_to_peer — 跟 SmartRouter M1-M5 1:1 配对)
# ============================================================

def test_route_to_peer_requires_target_peer():
    """route_to_peer 空 target_peer → Error (跟 mavis 4 件套 1:1 配对 0 改 happy path)."""
    import agent.peer as peer

    routing_out: dict = {}
    result = peer.route_to_peer(routing_out, target_peer="", task="some-task")
    assert result.startswith("Error")
    assert "target_peer" in result


def test_route_to_peer_requires_task():
    """route_to_peer 空 task → Error."""
    import agent.peer as peer

    result = peer.route_to_peer({}, target_peer="alpha", task="")
    assert result.startswith("Error")
    assert "task" in result


def test_route_to_peer_runs_via_peer_run_and_stamps_routing_out(tmp_path, monkeypatch):
    """route_to_peer 调 peer_run + 在 routing_out 标 resolved_peer + peer_routing_strategy.

    跟 SmartRouter M1-M5 决策树 1:1 配对 (跟 mavis 4 件套 1:1 配对 0 改 resolve_routing).
    """
    import agent.peer as peer

    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    routing_out: dict = {}

    with _a2a_stub_context(a2a_orchestrate=lambda args, **_: "task-xyz"):
        result = peer.route_to_peer(routing_out, target_peer="alpha", task="do-thing")

    assert result == "task-xyz"
    assert routing_out["resolved_peer"] == "alpha"
    assert routing_out["peer_routing_strategy"] == "direct"


def test_route_to_peer_accepts_none_routing_out(tmp_path, monkeypatch):
    """route_to_peer routing_out=None 0 raise (跟 mavis "UX 倒退审计" 1:1 配对)."""
    import agent.peer as peer

    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    with _a2a_stub_context(a2a_orchestrate=lambda args, **_: "task-ok"):
        result = peer.route_to_peer(None, target_peer="alpha", task="do-thing")
    assert result == "task-ok"


# ============================================================
# register_peer_tools 测试 (跟 plugin register pattern 1:1 配对)
# ============================================================

def test_register_peer_tools_registers_5_tools():
    """register_peer_tools 注册 5 peer_* 工具 (跟 plugin register 1:1 配对)."""
    import agent.peer as peer

    fake_ctx = MagicMock()
    with _a2a_stub_context(a2a_discover=lambda args, **_: "discover-result"):
        peer.register_peer_tools(fake_ctx)

    # 5 ctx.register_tool 调用 (1:1 配对 v0.21 5 工具)
    assert fake_ctx.register_tool.call_count == 5
    registered_names = [
        call.kwargs.get("name") or call.args[0]
        for call in fake_ctx.register_tool.call_args_list
    ]
    assert "peer_discover" in registered_names
    assert "peer_call" in registered_names
    assert "peer_list" in registered_names
    assert "peer_history" in registered_names
    assert "peer_run" in registered_names


def test_register_peer_tools_silent_skip_on_import_error(caplog):
    """A2A plugin 0 在 path → silent skip register 5 工具 (跟 mavis 4 件套 1:1 配对).

    模拟 plugins.platforms.a2a.tools.a2a_discover 0 存在 → ImportError → warn + 0 register.
    """
    import agent.peer as peer

    fake_ctx = MagicMock()
    # 强制让 a2a plugin import 失败 (模拟 CN 端 Cat 4 reject 路径)
    with patch.dict(sys.modules, {"plugins.platforms.a2a.tools": None}):
        with caplog.at_level("WARNING"):
            peer.register_peer_tools(fake_ctx)

    # 0 register 5 工具 (silent skip, 跟 mavis "UX 倒退审计" 1:1 配对 0 改 happy path)
    assert fake_ctx.register_tool.call_count == 0
    # 至少 1 条 warn
    assert any(
        "A2A plugin" in record.message
        for record in caplog.records
    )

"""Tests for K-7 (Phase 4 v0.20.0 borrow): /context extend + /diff + /focus slash commands.

跟 Phase 4 K-7 sprint plan §4 1:1 配对:
- extend 现有 /context (acp_adapter/server.py:1726) 加 observability: token count
  (已有 80%) + last N messages preview + current task + focus
- 新 /diff slash command (last conversation state diff: last 2 messages 对比)
- 新 /focus slash command (set/get/clear conversation focus filter tag)
- acp_adapter/session.py SessionState 加 focus field (1 line additive, 0 改旧)
- 3 dict 同步: _ADVERTISED_COMMANDS / _SLASH_COMMANDS / handler dict
- 补 K-8 漏改的 _SLASH_COMMANDS dict (/help 之前 0 显示 /init, 顺手修)

10 test (5 静态 source check + 5 live integration), 跟 K-6/K-8 test pattern 1:1:
静态 source check 防改回归 + live integration 验证真行为。0 pyyaml 依赖, 0 LLM dep.
"""

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent


# ---------- K-7 main change: 静态 source check ----------


def test_session_state_focus_field():
    """K-7 main file: SessionState 加 focus field (additive 0 改旧)."""
    p = REPO / "acp_adapter" / "session.py"
    assert p.exists(), f"{p} missing"
    src = p.read_text(encoding="utf-8")
    assert "focus: str = \"\"" in src, (
        "SessionState 缺 focus field (K-7 main additive 改动缺失)"
    )
    # 跟其他 field 1:1 配对: focus 应在 interrupted_prompt_text 之后, model 之前不应该有 focus
    # 简化: 验证 dataclass 内有 focus 即可


def test_server_advertised_diff_focus_commands():
    """K-7 advertised: _ADVERTISED_COMMANDS 加 /diff + /focus 2 entry."""
    main_src = (REPO / "acp_adapter" / "server.py").read_text(encoding="utf-8")
    assert '"name": "diff"' in main_src, (
        "_ADVERTISED_COMMANDS 缺 /diff entry (K-7 advertisement 缺失)"
    )
    assert '"name": "focus"' in main_src, (
        "_ADVERTISED_COMMANDS 缺 /focus entry (K-7 advertisement 缺失)"
    )
    # 跟现有 10 command 1:1 配对: help / model / tools / context / reset / compact / steer / queue / version / init / diff / focus
    for cmd in ("help", "model", "tools", "context", "reset", "compact", "steer",
                "queue", "version", "init", "diff", "focus"):
        assert f'"name": "{cmd}"' in main_src, f"existing /{cmd} command 0 改 0 失, K-7 破坏现有"


def test_server_slash_commands_dict_complete():
    """K-7 + K-8 修: _SLASH_COMMANDS dict 12 entry 全 (K-8 之前漏 init, K-7 顺手补).

    _cmd_help 用 _SLASH_COMMANDS dict 来 list commands. 缺一项 /help 就不显示.
    """
    main_src = (REPO / "acp_adapter" / "server.py").read_text(encoding="utf-8")
    # 验证 _SLASH_COMMANDS dict 包含 12 command
    for cmd in ("help", "model", "tools", "context", "reset", "compact", "steer",
                "queue", "version", "init", "diff", "focus"):
        # 简化匹配: 找 "cmd": " 模式 (dict key) — 避免跟 description 撞
        assert f'"{cmd}":' in main_src or f"'{cmd}':" in main_src, (
            f"_SLASH_COMMANDS dict 缺 /{cmd} entry (K-8 漏改 / K-7 同步 缺漏)"
        )


def test_server_handler_dispatch_diff_focus():
    """K-7 dispatch: handler dict 加 'diff' + 'focus' (跟 /context 1:1 配对)."""
    main_src = (REPO / "acp_adapter" / "server.py").read_text(encoding="utf-8")
    assert '"diff": self._cmd_diff' in main_src, (
        "handler dict 缺 'diff': self._cmd_diff (K-7 dispatch 缺失)"
    )
    assert '"focus": self._cmd_focus' in main_src, (
        "handler dict 缺 'focus': self._cmd_focus (K-7 dispatch 缺失)"
    )


def test_server_diff_focus_command_functions_exist():
    """K-7 handler: server.py thin wrapper (跟 K-8 _cmd_init → init_command 1:1 配对).

    实际函数 logic 在 k7_commands.py, server.py 留 thin wrapper (跟 K-8 _cmd_init
    inline import pattern 1:1 配对).
    """
    main_src = (REPO / "acp_adapter" / "server.py").read_text(encoding="utf-8")
    k7_src = (REPO / "acp_adapter" / "k7_commands.py").read_text(encoding="utf-8")

    # server.py thin wrapper
    assert "def _cmd_diff(self, args: str, state: SessionState) -> str:" in main_src, (
        "_cmd_diff wrapper missing in server.py (K-7 handler 缺失)"
    )
    assert "def _cmd_focus(self, args: str, state: SessionState) -> str:" in main_src, (
        "_cmd_focus wrapper missing in server.py (K-7 handler 缺失)"
    )

    # k7_commands.py 实际 logic
    assert "def _msg_summary(msg: dict, max_chars: int = 60) -> str:" in k7_src, (
        "_msg_summary helper missing in k7_commands.py"
    )
    assert "def _cmd_diff(args: str, state: Any) -> str:" in k7_src, (
        "_cmd_diff function missing in k7_commands.py (K-7 main logic 缺失)"
    )
    assert "def _cmd_focus(args: str, state: Any) -> str:" in k7_src, (
        "_cmd_focus function missing in k7_commands.py (K-7 main logic 缺失)"
    )
    assert "def _extend_context(state: Any, lines: List[str]) -> List[str]:" in k7_src, (
        "_extend_context helper missing in k7_commands.py"
    )

    # server.py _cmd_context 末尾调 _extend_context (跟 K-8 _cmd_init inline import 1:1)
    assert "_k7_extend_context" in main_src, (
        "_cmd_context 0 调 k7_commands._extend_context (K-7 extend wiring 缺失)"
    )


# ---------- K-7 live integration: 跟 plan §4 1:1 配对 ----------


def _make_state(history=None, focus="", session_id="test-session-id-12345678"):
    """Build a minimal SessionState-like object for K-7 testing.

    0 启 AIAgent (1.5GB 内存), 0 启 SessionManager. 直接 mock 必要 attr.
    """
    class _MockAgent:
        model = "test-model"
        provider = "test-provider"
        compression_enabled = True
        _cached_system_prompt = "system"
        tools = None
        context_compressor = None
    s = type("FakeState", (), {})()
    s.session_id = session_id
    s.agent = _MockAgent()
    s.cwd = "/tmp/test"
    s.history = history if history is not None else []
    s.focus = focus
    s.queued_prompts = []
    s.is_running = False
    s.runtime_lock = None
    s.current_prompt_text = ""
    s.interrupted_prompt_text = ""
    return s


def test_cmd_diff_empty_history_returns_no_conversation():
    """Live: /diff 在 0 message 时返 'no conversation yet' fallback."""
    sys.path.insert(0, str(REPO))
    from acp_adapter.k7_commands import _cmd_diff
    state = _make_state(history=[])
    result = _cmd_diff("", state)
    assert "No conversation yet" in result, (
        f"/diff empty 应返 fallback, got: {result!r}"
    )


def test_cmd_diff_single_message_returns_fallback():
    """Live: /diff 在 1 message 时返 'only 1 message' fallback (没 previous 可比)."""
    sys.path.insert(0, str(REPO))
    from acp_adapter.k7_commands import _cmd_diff
    history = [{"role": "user", "content": "hello"}]
    state = _make_state(history=history)
    result = _cmd_diff("", state)
    assert "Only 1 message" in result, (
        f"/diff single 应返 fallback, got: {result!r}"
    )
    assert "[user]" in result, "/diff single 应显示 only message role"


def test_cmd_diff_multi_message_returns_comparison():
    """Live: /diff 在 2+ message 时返 last 2 对比 + chars delta."""
    sys.path.insert(0, str(REPO))
    from acp_adapter.k7_commands import _cmd_diff
    history = [
        {"role": "user", "content": "old question"},
        {"role": "assistant", "content": "old answer with more text here"},
        {"role": "user", "content": "new"},
    ]
    state = _make_state(history=history)
    result = _cmd_diff("", state)
    # 应该显示 last 2 = [user] new vs [assistant] old answer...
    assert "previous:" in result and "current:" in result, (
        f"/diff multi 应显示 previous + current, got: {result!r}"
    )
    assert "3 messages" in result, f"/diff multi 应显示总 message count, got: {result!r}"
    # delta: current=3 chars - previous=30 chars = -27
    assert "-27" in result, f"/diff multi 应显示 chars delta, got: {result!r}"


def test_cmd_focus_set_get_clear():
    """Live: /focus set → get → clear 3 状态 (跟 plan K-7 §4 1:1 配对)."""
    sys.path.insert(0, str(REPO))
    from acp_adapter.k7_commands import _cmd_focus
    state = _make_state(focus="")

    # 1. 无 focus 时, 无 arg 返 'No focus set' + usage
    result = _cmd_focus("", state)
    assert "No focus set" in result, f"/focus no-arg 初次应返 fallback, got: {result!r}"

    # 2. 设 focus
    result = _cmd_focus("CAND-085 AIMC 集成", state)
    assert "Focus set" in result, f"/focus set 应返 confirm, got: {result!r}"
    assert state.focus == "CAND-085 AIMC 集成", (
        f"state.focus 应已设, got: {state.focus!r}"
    )

    # 3. 有 focus 时, 无 arg 返 'Current focus'
    result = _cmd_focus("", state)
    assert "Current focus" in result and "CAND-085" in result, (
        f"/focus get 应显示当前, got: {result!r}"
    )

    # 4. /focus clear 重置
    result = _cmd_focus("clear", state)
    assert "cleared" in result.lower(), f"/focus clear 应返 confirm, got: {result!r}"
    assert state.focus == "", f"state.focus 应已清空, got: {state.focus!r}"


def test_cmd_context_extends_with_recent_and_focus():
    """Live: /context extend 加 Recent (last 5) + Current task + Focus 段.

    跟 plan K-7 §4 1:1 配对 — 测 _extend_context 行为, 验证返回的 lines
    包含 K-7 段 (Current task + Focus + Recent preview). 0 走 server.py
    _cmd_context 整路径 (避免 acp 顶层 import).
    """
    sys.path.insert(0, str(REPO))
    from acp_adapter.k7_commands import _extend_context
    history = [
        {"role": "user", "content": "msg 1"},
        {"role": "assistant", "content": "msg 2"},
        {"role": "user", "content": "msg 3"},
    ]
    state = _make_state(history=history, focus="CAND-085")
    base_lines = ["Conversation: 3 messages", "  user: 2, assistant: 1, tool: 0, system: 0"]
    result_lines = _extend_context(state, list(base_lines))

    # base lines 保留 (additive 0 改)
    assert "Conversation: 3 messages" in result_lines, (
        "_extend_context 0 改 base lines (additive)"
    )
    # K-7 段
    assert any("Current task:" in line for line in result_lines), (
        f"_extend_context 应加 Current task 段, got: {result_lines!r}"
    )
    assert any("test-ses" in line for line in result_lines), (
        f"Current task 应含 session_id[:8], got: {result_lines!r}"
    )
    assert any("Focus: CAND-085" in line for line in result_lines), (
        f"_extend_context 应加 Focus 段, got: {result_lines!r}"
    )
    assert any("Recent (last 3):" in line for line in result_lines), (
        f"_extend_context 应加 Recent (last 3) preview, got: {result_lines!r}"
    )
    assert any("[user] msg 3" in line for line in result_lines), (
        f"Recent 应显示 message preview, got: {result_lines!r}"
    )

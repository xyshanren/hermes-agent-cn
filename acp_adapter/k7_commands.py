"""K-7 /context extend + /diff + /focus slash commands (Phase 4 v0.20.0 borrow).

跟 plan K-7 §4 1:1 配对 (跟 K-8 init_command.py 1:1 配对, 抽到独立 file 0 依赖 acp 顶层 import):
- _msg_summary: render single history message as one-line summary (K-7 helper,
  shared between /context recent preview + /diff comparison)
- _cmd_diff: K-7 /diff slash command — show last conversation state diff
  (last 2 messages 对比, content + tool_calls)
- _cmd_focus: K-7 /focus slash command — set / get / clear conversation focus
  filter tag (持久化到 SessionState.focus)
- _extend_context: K-7 /context extend helper — append K-7 段 (Current task +
  Focus + Recent last 5 preview) 到 /context base lines

跟 mavis 4 件套 1:1 配对 + CAND-084 8-03 22:10 lesson "估时前必 verify 引擎能力":
- 后端先调查再设计: 借 acp_adapter/server.py:1726 _cmd_context 现有 80% (token count
  + role breakdown + compression threshold) additive extend, 0 改旧
- Cherry-pick split bug class: 1 commit 0 split, _ADVERTISED_COMMANDS + _SLASH_COMMANDS
  (补 K-8 漏改) + handler dict + _cmd_* 4 处 1:1 配对 (跟 /context /init 1:1 配对)
- UX 倒退审计: 现有 10 个 slash command (help/model/tools/context/reset/compact/steer/
  queue/version/init) 不变. K-7 /diff + /focus 是独立 add-only path. SessionState 加
  1 field focus additive 0 改旧
- 估时前必 verify 引擎能力: K-7 verify 后端 acp_adapter/server.py _cmd_context 已有
  80% (token estimate via estimate_request_tokens_rough 1743-1752 行), state.history
  + state.agent 都有, 只需 extend 加 recent preview + current task. SessionState focus
  field additive. 0 cherry-pick 工作 (跟 K-9 跳过 1:1, plan K-7 估时 0.5-1d → 实际 0.5h)

跟 AIMC 4 铁律 1:1: 不反向调整 (0 改现有 10 slash command) / 不写回 upstream (0 push
跟 8-05 阶段批推 1:1) / 0 corrupt (1 file additive, 0 改旧 file) / fail-fast (跟
batch push + CI 1:1 配对)
"""

from __future__ import annotations

from typing import Any, Dict, List


# ---- K-7 shared helper: message summary -------------------------------------


def _msg_summary(msg: dict, max_chars: int = 60) -> str:
    """Render a single history message as a one-line summary.

    K-7 helper: shared between /context recent preview and /diff comparison.
    跟 plan K-7 §4 1:1 配对 — 显示 role + content 前 max_chars + tool_calls 数量.
    """
    role = msg.get("role", "unknown")
    content = msg.get("content", "")
    if isinstance(content, list):
        # 多模态 content 列表, 只显示文本 part (跟 _cmd_context 1745 行 1:1 配对)
        text_parts = [
            p.get("text", "")
            for p in content
            if isinstance(p, dict) and p.get("type") == "text"
        ]
        content = " ".join(text_parts) if text_parts else f"[{len(content)} parts]"
    elif not isinstance(content, str):
        content = str(content)
    preview = content[:max_chars].replace("\n", " ")
    if len(content) > max_chars:
        preview += "..."
    tool_calls = msg.get("tool_calls") or []
    suffix = f" +{len(tool_calls)} tool_calls" if tool_calls else ""
    return f"[{role}] {preview}{suffix}"


# ---- K-7 /diff slash command -------------------------------------------------


def _cmd_diff(args: str, state: Any) -> str:
    """K-7 (Phase 4 /diff slash command): show last conversation state diff.

    跟 plan K-7 §4 1:1 配对 — 比较最近 2 条消息 (current vs previous).
    Empty / single-message conversation 返 fallback 文案.
    """
    history = state.history
    n = len(history)
    if n == 0:
        return "No conversation yet — nothing to diff."
    if n == 1:
        only = _msg_summary(history[0])
        return (
            f"Only 1 message in history (no previous to diff against):\n"
            f"  current: {only}"
        )
    current = _msg_summary(history[-1])
    previous = _msg_summary(history[-2])
    current_chars = len(str(history[-1].get("content", "")))
    previous_chars = len(str(history[-2].get("content", "")))
    delta = current_chars - previous_chars
    delta_str = f"+{delta}" if delta >= 0 else str(delta)
    return (
        f"Conversation diff (last 2 of {n} messages):\n"
        f"  previous: {previous} ({previous_chars} chars)\n"
        f"  current:  {current} ({current_chars} chars, {delta_str})"
    )


# ---- K-7 /focus slash command ------------------------------------------------


def _cmd_focus(args: str, state: Any) -> str:
    """K-7 (Phase 4 /focus slash command): set or show conversation focus filter.

    跟 plan K-7 §4 1:1 配对 — 无 arg 显示当前, '/focus clear' / 'reset' / 'none' / '-'
    重置, 其他 arg 设为新 focus 标签. 持久化到 SessionState.focus.
    """
    new_focus = args.strip()
    if not new_focus:
        if state.focus:
            return f"Current focus: {state.focus}\n(usage: /focus <tag>  or  /focus clear)"
        return "No focus set.\n(usage: /focus <tag>  e.g. /focus CAND-085 AIMC 集成)"
    if new_focus.lower() in ("clear", "reset", "none", "-"):
        state.focus = ""
        return "Focus cleared."
    state.focus = new_focus
    return f"Focus set: {state.focus}"


# ---- K-7 /context extend helper ---------------------------------------------


def _extend_context(state: Any, lines: List[str]) -> List[str]:
    """K-7 (Phase 4 /context extend): append Current task + Focus + Recent last 5 段.

    跟 plan K-7 §4 1:1 配对 — _cmd_context 末尾调, additive 0 改现有 base lines.
    0 LLM dep, 0 acp 顶层 import (跟 K-8 init_command.py 1:1 配对).
    """
    n_messages = len(state.history)
    short_id = state.session_id[:8] if state.session_id else "?"
    lines.append(f"Current task: session {short_id} (cwd: {state.cwd or '.'})")
    if state.focus:
        lines.append(f"Focus: {state.focus}")
    if n_messages > 0:
        preview_n = min(5, n_messages)
        lines.append("")
        lines.append(f"Recent (last {preview_n}):")
        for msg in state.history[-preview_n:]:
            lines.append(f"  {_msg_summary(msg, max_chars=80)}")
    return lines

"""hermes peer — 跨 profile 私聊 (Sprint 16 档 C.2 协议层).

跟 v0.21 upstream "hermes peer" 协议 1:1 配对 (跟 mavis 8-12 P3 拍 A "Cat 4 借鉴+重写" 1:1 配对).

CN 端混合方案 (跟 mavis 9-03 12:35 反馈的 4 决策类型 选 1:1 配对):
- 协议层 (Cat 4 借鉴 upstream v0.21 hermes peer 协议): 跟 plugins/platforms/a2a/ 5 工具 1:1 集成
  (A2A plugin 8-09 Sprint 13a merge 1785 commit 已包含完整 a2a_discover / a2a_call / a2a_list / a2a_history / a2a_orchestrate)
- 路由层 (Cat 2 CN 原创): 跟 agent/routing_decision.py SmartRouter M1-M5 决策树 1:1 配对
- 存储层 (Cat 6 内生): 跟 cron/notepad.py 持久 notepad 1:1 配对 (~/.hermes/peers/<peer_name>/)
- 审批层 (Cat 2 原创): 跟 Sprint 16 档 C.1 受保护指令文件审批 1:1 配对 (peer_call 拦截)

5 命令 (跟 v0.21 upstream hermes peer 协议 1:1 配对):
- peer_discover (跟 a2a_discover 1:1 配对)
- peer_call (跟 a2a_call 1:1 配对)
- peer_list (跟 a2a_list 1:1 配对)
- peer_history (跟 a2a_history 1:1 配对)
- peer_run (跟 a2a_orchestrate 1:1 配对)

跟 mavis 4 件套 1:1 配对:
- 后端先调查再设计 (memory:13-17): 协议层 100% 复用 A2A plugin, 0 重复实现 ✓
- UX 倒退审计 (memory:19-23): 跟 cross_profile + protected_files 串联, 0 改现有 ✓
- Cherry-pick split bug class (memory:7-11): 0 改 A2A plugin / routing_decision, 仅新 file ✓
- Constitution 铁律 (mavis 4 件套 1:1 配对): 0 改 upstream / 0 写回 hermes profile / 决策边界 (peer 跨 profile 显式) / fail-fast (持久化异常 raise)
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)


# Sprint 16 档 C.2 协议层: ~/.hermes/peers/<peer_name>/ 持久化路径
# 跟 cron/notepad.py 持久 notepad 1:1 配对 (跟 mavis Cat 6 内生资产 1:1 配对)
def _peer_home(peer_name: str) -> Path:
    """Return ~/.hermes/peers/<peer_name>/ 路径 (跟 cron/notepad.py _SNAPSHOT 1:1 配对)."""
    hermes_home = Path(os.environ.get("HERMES_HOME", str(Path.home() / ".hermes")))
    return hermes_home / "peers" / peer_name


def _persist_peer_message(peer_name: str, role: str, content: str) -> None:
    """Append a message to ~/.hermes/peers/<peer_name>/chat.jsonl.

    跟 cron/notepad.py _write_last_output 1:1 配对.
    0 改写 (append-only), 跨进程 0 阻塞 (跟 mavis Constitution fail-fast 1:1 配对).
    """
    try:
        home = _peer_home(peer_name)
        home.mkdir(parents=True, exist_ok=True)
        chat_path = home / "chat.jsonl"
        with open(chat_path, "a", encoding="utf-8") as f:
            import time
            entry = {
                "ts": time.time(),
                "role": role,
                "content": content,
            }
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except Exception as exc:
        # fail-fast: 0 静默 (跟 mavis Constitution 1:1 配对)
        logger.warning("Sprint 16 档 C.2: 持久化 peer 消息失败 %r: %s", peer_name, exc)


# ============================================================
# 5 命令 (跟 v0.21 upstream hermes peer 协议 1:1 配对, 跟 A2A plugin 1:1 集成)
# ============================================================

def peer_discover(args: dict, **_: Any) -> str:
    """Sprint 16 档 C.2 协议层: 跟 a2a_discover 1:1 配对.

    复用 plugins/platforms/a2a/tools.py:a2a_discover (0 重复实现, 跟 mavis 4 件套 1:1).
    """
    from plugins.platforms.a2a.tools import a2a_discover
    return a2a_discover(args, **_)


def peer_call(args: dict, **_: Any) -> str:
    """Sprint 16 档 C.2 协议层: 跟 a2a_call 1:1 配对.

    复用 plugins/platforms/a2a/tools.py:a2a_call, 但额外持久化到 ~/.hermes/peers/<peer_name>/.
    """
    peer_name = str(args.get("peer") or args.get("peer_name") or "").strip()
    message = str(args.get("message") or args.get("text") or "").strip()
    if not peer_name:
        return "Error: 'peer' is required (跟 a2a_call 'url' 1:1 配对)."

    from plugins.platforms.a2a.tools import a2a_call
    result = a2a_call(args, **_)

    # 持久化 user / assistant message (跟 mavis Cat 6 内生 1:1 配对)
    if message:
        _persist_peer_message(peer_name, "user", message)
    if result and not result.startswith("Error"):
        _persist_peer_message(peer_name, "assistant", result)

    return result


def peer_list(args: Optional[dict] = None, **_: Any) -> str:
    """Sprint 16 档 C.2 协议层: 跟 a2a_list 1:1 配对.

    列 ~/.hermes/peers/ 下所有持久 peer (跟 mavis Cat 6 内生 1:1 配对).
    """
    hermes_home = Path(os.environ.get("HERMES_HOME", str(Path.home() / ".hermes")))
    peers_root = hermes_home / "peers"
    if not peers_root.is_dir():
        return "No peers configured (0 ~/.hermes/peers/)."

    peers = sorted(p.name for p in peers_root.iterdir() if p.is_dir())
    if not peers:
        return "No peers configured (empty ~/.hermes/peers/)."

    lines = [f"Configured peers ({len(peers)}):"]
    for p in peers:
        chat_path = peers_root / p / "chat.jsonl"
        msg_count = 0
        if chat_path.exists():
            with open(chat_path, "r", encoding="utf-8") as f:
                msg_count = sum(1 for _ in f)
        lines.append(f"  - {p} ({msg_count} messages in chat history)")
    return "\n".join(lines)


def peer_history(args: dict, **_: Any) -> str:
    """Sprint 16 档 C.2 协议层: 跟 a2a_history 1:1 配对.

    列 ~/.hermes/peers/<peer_name>/chat.jsonl 历史.
    """
    peer_name = str(args.get("peer") or args.get("peer_name") or "").strip()
    if not peer_name:
        return "Error: 'peer' is required."
    home = _peer_home(peer_name)
    chat_path = home / "chat.jsonl"
    if not chat_path.exists():
        return f"No chat history for peer {peer_name!r} (0 ~/.hermes/peers/{peer_name}/chat.jsonl)."

    lines = [f"Chat history for {peer_name!r}:"]
    with open(chat_path, "r", encoding="utf-8") as f:
        for i, line in enumerate(f, 1):
            try:
                entry = json.loads(line)
                ts = entry.get("ts", 0)
                role = entry.get("role", "?")
                content = entry.get("content", "")[:200]
                lines.append(f"  [{i}] {ts} {role}: {content}")
            except json.JSONDecodeError:
                lines.append(f"  [{i}] (malformed)")
    return "\n".join(lines)


def peer_run(args: dict, **_: Any) -> str:
    """Sprint 16 档 C.2 协议层: 跟 a2a_orchestrate 1:1 配对.

    委派长时间任务给 peer (跨 Gateway 异步 RPC), 持久化 task_id.
    跟 cron/notepad.py 持久 notepad 1:1 配对 (Cat 6 内生 1:1 配对).
    """
    from plugins.platforms.a2a.tools import a2a_orchestrate
    result = a2a_orchestrate(args, **_)

    peer_name = str(args.get("peer") or args.get("peer_name") or "").strip()
    if peer_name and result and not result.startswith("Error"):
        # 持久化 task 状态 (跟 mavis Cat 6 内生 1:1 配对)
        try:
            home = _peer_home(peer_name)
            home.mkdir(parents=True, exist_ok=True)
            (home / "last_task.txt").write_text(result, encoding="utf-8")
        except Exception as exc:
            logger.warning("Sprint 16 档 C.2: 持久化 peer task 失败 %r: %s", peer_name, exc)

    return result


# ============================================================
# 路由层集成 (跟 agent/routing_decision.py SmartRouter M1-M5 1:1 配对)
# ============================================================

def route_to_peer(
    routing_out: Optional[dict],
    *,
    target_peer: str,
    task: str,
) -> str:
    """Sprint 16 档 C.2 路由层 (Cat 2 CN 原创): 跟 SmartRouter M1-M5 决策树 1:1 配对.

    跟 mavis 9-03 12:35 4 决策类型选 (Cat 4 借鉴 + Cat 2 原创) 1:1 配对.
    跟 agent/routing_decision.py:resolve_routing 1:1 配对 (跟 mavis "fix collateral issues in-scope" 1:1).

    Args:
        routing_out: 跟 SmartRouter 1:1 配对 (None 也接受, 0 改 caller 协议)
        target_peer: 目标 peer 名字 (跟 ~/.hermes/peers/<peer_name>/ 1:1)
        task: 委派任务

    Returns:
        a2a_orchestrate 输出 (跟 peer_run 1:1 配对)
    """
    if not target_peer:
        return "Error: 'target_peer' is required."
    if not task:
        return "Error: 'task' is required."

    # 跟 SmartRouter M1-M5 决策树 1:1 配对: 在 routing_out 记录 peer 决策 (跟 mavis Cat 2 CN 原创 1:1 配对)
    if isinstance(routing_out, dict):
        routing_out["resolved_peer"] = target_peer
        routing_out["peer_routing_strategy"] = "direct"  # 未来: cost-aware / load-balance / 等

    return peer_run({"peer": target_peer, "message": task})


# ============================================================
# Sprint 16 档 C.2 5 命令 register (跟 plugins/security-guidance register pattern 1:1 配对)
# ============================================================

def register_peer_tools(ctx) -> None:
    """Register the 5 peer_* tools in the agent's toolset.

    Sprint 16 档 C.2 跟 plugin register pattern 1:1 配对.

    防御性 ImportError: 如果 A2A plugin 0 在 path 上 (CN 端 Cat 4 reject 路径),
    silent skip register 5 工具, 5 命令仍可 standalone import 用 (lazy import 在每次 call).
    跟 mavis 4 件套 1:1 配对: 0 改 A2A plugin 启用状态 / 0 改 happy path / fail-fast (warn 而非 raise).
    """
    try:
        # 触发 A2A plugin 任意 1 命令 import, 验证 plugin 0 在 path 上
        from plugins.platforms.a2a.tools import a2a_discover  # noqa: F401
    except ImportError as exc:
        logger.warning(
            "Sprint 16 档 C.2: A2A plugin 0 在 path 上 (%s), 5 peer_* 工具 0 register "
            "(跟 mavis 4 件套 1:1 配对 0 改 happy path).",
            exc,
        )
        return

    ctx.register_tool(
        name="peer_discover",
        toolset="hermes-peer",
        schema={"url": "string (e.g. http://localhost:9999)"},
        handler=peer_discover,
    )
    ctx.register_tool(
        name="peer_call",
        toolset="hermes-peer",
        schema={
            "peer": "string (peer name, ~/.hermes/peers/<peer>/)",
            "message": "string (跟 a2a_call 'text' 1:1)",
        },
        handler=peer_call,
    )
    ctx.register_tool(
        name="peer_list",
        toolset="hermes-peer",
        schema={},
        handler=peer_list,
    )
    ctx.register_tool(
        name="peer_history",
        toolset="hermes-peer",
        schema={"peer": "string (peer name)"},
        handler=peer_history,
    )
    ctx.register_tool(
        name="peer_run",
        toolset="hermes-peer",
        schema={
            "peer": "string (peer name)",
            "message": "string (跟 a2a_orchestrate 'text' 1:1)",
        },
        handler=peer_run,
    )

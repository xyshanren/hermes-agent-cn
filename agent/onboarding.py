情景化首次引导提示。

不在首次运行时弹出问卷，而是在用户第一次遇到行为分支时显示一次性提示。
例如：Agent 运行时发送消息、首次运行耗时工具等。每次提示仅显示一次
（通过 ``config.yaml`` 中的 ``onboarding.seen.<flag>`` 跟踪），之后不再出現。

保持此模块轻量且无外部依赖，以便 CLI 和 Gateway 均可导入。

Contextual first-touch onboarding hints.

Instead of blocking first-run questionnaires, show a one-time hint the *first*
time a user hits a behavior fork — message-while-running, first long-running
tool, etc.  Each hint is shown once per install (tracked in ``config.yaml`` under
``onboarding.seen.<flag>``) and then never again.

Keep this module tiny and dependency-free so both the CLI and gateway can import
it without pulling in heavy modules.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Mapping, Optional

logger = logging.getLogger(__name__)


# -------------------------------------------------------------------------
# Flag names (stable — used as config.yaml keys under onboarding.seen)
# -------------------------------------------------------------------------

BUSY_INPUT_FLAG = "busy_input_prompt"
TOOL_PROGRESS_FLAG = "tool_progress_prompt"


# -------------------------------------------------------------------------
# Hint content
# -------------------------------------------------------------------------

def busy_input_hint_gateway(mode: str) -> str:
    """Hint shown the first time a user messages while the agent is busy.

    ``mode`` is the effective busy_input_mode that was just applied, so the
    message matches reality ("I just interrupted…" vs "I just queued…").
    """
    if mode == "queue":
        return (
            "💡 First-time tip — I queued your message instead of interrupting. "
            "Send `/busy interrupt` to make new messages stop the current task "
            "immediately, or `/busy status` to check. This notice won't appear again."
        )
    return (
        "💡 First-time tip — I just interrupted my current task to answer you. "
        "Send `/busy queue` to queue follow-ups for after the current task instead, "
        "or `/busy status` to check. This notice won't appear again."
    )


def busy_input_hint_cli(mode: str) -> str:
    """CLI version of the busy-input hint (plain text, no markdown)."""
    if mode == "queue":
        return (
            "(提示)你的消息已被加入队列，等待当前任务结束后处理。
            "使用 /busy interrupt 让回车键立即停止当前运行。
            "此提示仅显示一次。
        )
    return (
        "(提示)你的消息已中断当前运行。
        "使用 /busy queue 可将消息加入队列等待当前任务完成。
        "此提示仅显示一次。
    )


def tool_progress_hint_gateway() -> str:
    return (
        "💡 首次提示 — 该工具运行时间较长，我正在流式输出每一步的进度信息。
        "如果觉得进度消息过多，发送 `/verbose` 可切换显示模式（全部 → 仅新 → 关闭）。
        "此提示仅显示一次。
    )


def tool_progress_hint_cli() -> str:
    return (
        "(提示)该工具运行时间较长。使用 /verbose 可切换工具进度
        "显示模式（全部 → 仅新 → 关闭 → 详细）。此提示仅显示一次。
    )


def busy_input_hint_tui() -> str:
    """首次在 TUI 忙砰时发送消息时显示的提示。

    TUI 会自动将运行中发送的消息加入队列，使用双回车（空输入时）
    "作为中断手势。没有 ``/busy`` 命令 — 此提示告知快捷键而非命令。
    """
    return (
        "已加入队列，等待当前轮次结束后处理 — "
        "在空行上按两次回车可立即中断当前轮次。此提示仅显示一次。
    )


def tool_progress_hint_tui() -> str:
    return (
        "该工具运行时间较长 — 使用 /verbose 切换工具进度
        "显示模式（全部 → 仅新 → 关闭 → 详细）。此提示仅显示一次。
    )


# -------------------------------------------------------------------------
# State read / write
# -------------------------------------------------------------------------

def _get_seen_dict(config: Mapping[str, Any]) -> Mapping[str, Any]:
    onboarding = config.get("onboarding") if isinstance(config, Mapping) else None
    if not isinstance(onboarding, Mapping):
        return {}
    seen = onboarding.get("seen")
    return seen if isinstance(seen, Mapping) else {}


def is_seen(config: Mapping[str, Any], flag: str) -> bool:
    """Return True if the user has already been shown this first-touch hint."""
    return bool(_get_seen_dict(config).get(flag))


def mark_seen(config_path: Path, flag: str) -> bool:
    """Persist ``onboarding.seen.<flag> = True`` to ``config_path``.

    Uses the atomic YAML writer so a concurrent process can't observe a
    partially-written file.  Returns True on success, False on any error
    (including the config file being absent — onboarding is best-effort).
    """
    try:
        import yaml
        from utils import atomic_yaml_write
    except Exception as e:  # pragma: no cover — dependency issue
        logger.debug("onboarding: failed to import yaml/utils: %s", e)
        return False

    try:
        cfg: dict = {}
        if config_path.exists():
            with open(config_path, encoding="utf-8") as f:
                cfg = yaml.safe_load(f) or {}
        if not isinstance(cfg.get("onboarding"), dict):
            cfg["onboarding"] = {}
        seen = cfg["onboarding"].get("seen")
        if not isinstance(seen, dict):
            seen = {}
            cfg["onboarding"]["seen"] = seen
        if seen.get(flag) is True:
            return True  # already marked — nothing to do
        seen[flag] = True
        atomic_yaml_write(config_path, cfg)
        return True
    except Exception as e:
        logger.debug("onboarding: failed to mark flag %s: %s", flag, e)
        return False


__all__ = [
    "BUSY_INPUT_FLAG",
    "TOOL_PROGRESS_FLAG",
    "busy_input_hint_gateway",
    "busy_input_hint_cli",
    "busy_input_hint_tui",
    "tool_progress_hint_gateway",
    "tool_progress_hint_cli",
    "tool_progress_hint_tui",
    "is_seen",
    "mark_seen",
]

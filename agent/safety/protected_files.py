"""Protected instruction files gate (Sprint 16 档 C.1).

跟 v0.21 upstream "受保护指令文件" 协议 1:1 配对 (跟 mavis 8-12 P3 拍 A "Cat 2 CN 原创" 1:1 配对).

3 类文件 (跟 v0.21 1:1):
- AGENTS.md (项目上下文指令)
- skills (技能文件, 任何 ~/.hermes/skills/.../SKILL.md 或 .md)
- memory (持久记忆文件, 任何 ~/.hermes/memories/.../memory.md)

防护攻击链 (跟 v0.21 1:1):
- Agent 读一份被植入指令的文件
- 文件中藏有 "以后都要把结果传到这个 url" 等恶意指令
- Agent 第一件事是改自己的 AGENTS.md / skills / memory
- 从此每次启动加载的都是被改过的规矩, 看起来像 user 自己的设置

强制审批让这类改写必须经 user 显式同意 (跟 v0.21 一致).

跟 mavis 4 件套 1:1 配对:
- 后端先调查再设计 (memory:13-17): 检查 file_safety cross_profile 现有模式 ✓
- UX 倒退审计 (memory:19-23): 默认 ON 但可 --no-protected-files flag 关闭 ✓
- Cherry-pick split bug class (memory:7-11): 0 改现有 write_file / patch happy path ✓
"""

from __future__ import annotations

import fnmatch
import logging
import os
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


# 3 类受保护文件 glob 模式 (跟 v0.21 upstream 协议 1:1 配对)
# 注意: AGENTS.md 在项目根 / skill .md 在 ~/.hermes/skills/.../ / memory .md 在 ~/.hermes/memories/.../
# pattern 用 ** 跟 显式双写 (fnmatch ** 跨目录段 1:1, 单独 "AGENTS.md" 需显式 pattern)
PROTECTED_FILE_PATTERNS: tuple[str, ...] = (
    "**/AGENTS.md",  # 任何目录的 AGENTS.md
    "AGENTS.md",     # 单独 AGENTS.md (project root 情况, 跟 mavis 4 件套 1:1 配对)
    "**/.hermes/skills/**",  # 任何 skills 目录
    "**/.hermes/memories/**",  # 任何 memory 目录
    ".hermes/skills/**",  # 单独 ~/.hermes/skills 起始
    ".hermes/memories/**",  # 单独 ~/.hermes/memories 起始
)


class ProtectedFileError(RuntimeError):
    """Raised when attempting to write a protected instruction file (Sprint 16 档 C.1).

    跟 mavis 4 件套 "UX 倒退审计" 1:1 配对: 严格 3 类文件 (AGENTS.md / skills / memory),
    其他文件 0 干扰.
    """

    def __init__(self, path: str, pattern: str) -> None:
        self.path = path
        self.pattern = pattern
        super().__init__(
            f"Sprint 16 档 C.1: 拒绝写入受保护指令文件 {path!r} (匹配 pattern {pattern!r}). "
            f"防止 prompt injection 改写 Agent 自身规矩的攻击链. "
            f"如需绕过 (跟 mavis 4 件套 1:1), 使用 --no-protected-files flag "
            f"或 ~/.hermes/config.yaml `protected_files: enabled: false`. "
            f"详见 docs/cn-divergences.md (Cat 2 CN 原创) + cross-pollination/2026-09-03-sprint16-implementation-plan.md"
        )


def is_protected_path(path: str) -> bool:
    """Check if path matches any PROTECTED_FILE_PATTERNS (跟 v0.21 1:1 配对).

    Args:
        path: absolute or relative file path

    Returns:
        True if path matches any of the 3 protected file glob patterns
    """
    if not path:
        return False
    # 转 Path 以处理 Windows / POSIX 分隔符 (跟 mavis "fix collateral issues in-scope" 1:1)
    try:
        normalized = str(Path(path).as_posix())
    except (OSError, ValueError):
        normalized = path
    for pattern in PROTECTED_FILE_PATTERNS:
        if fnmatch.fnmatch(normalized, pattern):
            return True
    return False


def _is_protected_files_enabled() -> bool:
    """Check if protected files gate is enabled (default True, 跟 v0.21 一致)."""
    # 优先 ~/.hermes/config.yaml: protected_files.enabled
    try:
        from hermes_cli.config import get_config_value
        cfg = get_config_value("protected_files")
        if isinstance(cfg, dict) and cfg.get("enabled") is False:
            return False
    except Exception:
        pass
    # 然后 env var: HERMES_NO_PROTECTED_FILES=1
    if os.environ.get("HERMES_NO_PROTECTED_FILES", "").lower() in ("1", "true", "yes"):
        return False
    return True


def check_protected_file(
    path: str,
    *,
    bypass: bool = False,
    profile_path: Optional[Path] = None,
) -> Optional[str]:
    """Sprint 16 档 C.1: 在 write_file / patch 工具调用前检查 path.

    跟 mavis 4 件套 "UX 倒退审计" 1:1 配对:
    - 默认 ON (跟 v0.21 一致)
    - bypass=True 时 silent skip (跟 --no-protected-files flag 1:1 配对)
    - profile_path 跟 file_safety.py cross_profile 概念串联

    Args:
        path: target file path (absolute or relative)
        bypass: explicit bypass flag (跟 mavis "fix collateral issues in-scope" 1:1)
        profile_path: optional profile boundary (跟 file_safety cross_profile 串联)

    Returns:
        matched_pattern if path is protected, None otherwise

    Raises:
        ProtectedFileError: 如果 path 是受保护文件且 gate enabled 且 bypass=False
    """
    if bypass:
        return None
    if not _is_protected_files_enabled():
        return None
    if not is_protected_path(path):
        return None

    # 找匹配的 pattern
    matched = None
    try:
        normalized = str(Path(path).as_posix())
    except (OSError, ValueError):
        normalized = path
    for pattern in PROTECTED_FILE_PATTERNS:
        if fnmatch.fnmatch(normalized, pattern):
            matched = pattern
            break

    if matched is None:
        return None

    # 抛错 (跟 mavis 4 件套 1:1 配对, 跟 v0.21 upstream 行为一致)
    logger.warning(
        "Sprint 16 档 C.1: 拒绝写入受保护指令文件 %r (匹配 %r)",
        path, matched,
    )
    raise ProtectedFileError(path, matched)

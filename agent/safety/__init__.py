"""agent.safety — protected instruction files gate (Sprint 16 档 C.1).

跟 v0.21 upstream "受保护指令文件" 协议 1:1 配对 (跟 mavis 8-12 P3 拍 A "Cat 2 CN 原创" 1:1 配对):
- 3 类文件写入审批: AGENTS.md / skills / memory
- 防止 prompt injection 攻击链: Agent 读被植入指令的文件 → 改自己的规矩 → 永久生效
- 默认 ON (跟 v0.21 一致), 可通过 `~/.hermes/config.yaml` `protected_files: enabled: false` 关闭
  或 CLI flag `--no-protected-files` (跟 Sprint 15 CAND-086 1:1 配对)
- 跟 agent/file_safety.py cross_profile 概念串联 (defense-in-depth 1:1 配对)
- 跟 mavis 4 件套 "fix collateral issues in-scope" 1:1 配对: 0 改现有 write_file / patch happy path
"""

from __future__ import annotations

from .protected_files import (
    PROTECTED_FILE_PATTERNS,
    ProtectedFileError,
    is_protected_path,
    check_protected_file,
)


__all__ = [
    "PROTECTED_FILE_PATTERNS",
    "ProtectedFileError",
    "is_protected_path",
    "check_protected_file",
]

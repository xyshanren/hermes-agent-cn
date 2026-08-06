"""CAND-008 user-defined deny rules (Phase 4 v0.20.0 borrow).

跟 plan CAND-008 1:1 配对 (跟 K-7 k7_commands.py + K-10 additive 1 line 1:1 配对):
- parse_deny_patterns: 从 config `approvals.deny` 段读取 pattern list
  (fnmatch glob 格式, 跟 Bash/Edit 一致)
- check_deny: 验 command 是否匹配任一 deny pattern, 返 (is_denied, matched_pattern)
- is_deny_match: 单 pattern fnmatch 匹配检查 (内部 helper)

跟 mavis 4 件套 1:1 配对 + CAND-084 8-03 22:10 lesson "估时前必 verify 引擎能力":
- 后端先调查再设计: 借 fnmatch stdlib (cn 26 file 已有), 0 改旧 approvals resolver
- Cherry-pick split bug class: additive 0 改旧, 0 cherry-pick
- UX 倒退审计: 0 改现有 approvals 字段 (mode/timeout/cron_mode/mcp_reload_confirm/
  destructive_slash_confirm), additive 1 field "deny" + 0 行为变更 (default empty list = 0 deny)
- 估时前必 verify 引擎能力: verify approvals 段已存 (config.py:1915), additive 1 line
  + 抽 file 0 改旧, 实际 0.25-0.5h (跟 K-10 additive 1 line 1:1 配对)

跟 AIMC 4 铁律 1:1: 0 改 upstream / CN 端可维护 / 0 改 upstream 决策边界 / commit 前 verify
(跟 upstream e2fe529ef 1:1 配对, fnmatch 引擎 + additive deny field 0 改旧)
"""

from __future__ import annotations

import fnmatch
from typing import Any, Dict, List, Optional, Tuple


def parse_deny_patterns(approvals_cfg: Optional[Dict[str, Any]]) -> List[str]:
    """CAND-008 read: 从 approvals config 段读 deny pattern list.

    跟 plan CAND-008 1:1 配对 — additive `approvals.deny` field 是 list of
    fnmatch glob pattern (e.g. ["rm -rf /*", "mkfs.*", "dd if=*"]), 跟 Bash
    fnmatch 1:1 兼容. Empty list = 0 deny (跟 default 1:1 配对).
    0 改旧 approvals 字段 (mode/timeout/cron_mode 等), additive 1 field.

    Args:
        approvals_cfg: `config["approvals"]` dict 或 None (None = 0 deny)
    """
    if not approvals_cfg or not isinstance(approvals_cfg, dict):
        return []
    deny = approvals_cfg.get("deny", [])
    if not isinstance(deny, list):
        return []
    # 过滤只保留 string pattern (跟 plan 1:1 配对, defensive coding)
    return [p for p in deny if isinstance(p, str) and p]


def is_deny_match(pattern: str, command: str) -> bool:
    """CAND-008 single pattern check (内部 helper).

    跟 plan CAND-008 1:1 配对 — fnmatch.fnmatchcase 0 改 (cn 26 file 已有
    pattern), 跟 Bash fnmatch 1:1 兼容 (case-sensitive glob).
    """
    return fnmatch.fnmatchcase(command, pattern)


def check_deny(command: str, deny_patterns: List[str]) -> Tuple[bool, Optional[str]]:
    """CAND-008 main: 验 command 是否匹配任一 deny pattern.

    跟 plan CAND-008 1:1 配对 — additive 0 改旧, 用于 approvals resolver
    在 yolo mode 下 (per upstream e2fe529ef "block commands even under yolo")
    二次 check 阻止 user-defined deny pattern. 返 (is_denied, matched_pattern)
    跟 K-10 1:1 配对 (1 line additive + test 1:1 配对).

    Args:
        command: shell command 字符串 (e.g. "rm -rf /tmp/foo")
        deny_patterns: parse_deny_patterns() 返的 list (default empty = 0 deny)

    Returns:
        (True, matched_pattern) if denied, (False, None) otherwise
    """
    if not command or not deny_patterns:
        return False, None
    for pattern in deny_patterns:
        if is_deny_match(pattern, command):
            return True, pattern
    return False, None

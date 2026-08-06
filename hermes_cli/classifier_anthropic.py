"""CAND-056 classifier Anthropic-specific guidance (Phase 4 v0.20.0 borrow).

跟 plan CAND-056 1:1 配对 (跟 K-7 k7_commands.py + CAND-001/003/008 1:1 配对 0 改旧):
- ANTHROPIC_SUBSCRIPTION_ERROR_PATTERNS: 4 已知 subscription exhaustion
  error pattern (跟 upstream 2026-07-01 feat(classifier) 1:1 配对)
- get_anthropic_subscription_guidance: 返 user-facing guidance string (跟 plan 1:1)
- is_anthropic_subscription_error: 验 error message 是否 match subscription
  exhaustion (跟 CAND-008 is_deny_match 1:1 配对 fnmatch 模式)

跟 mavis 4 件套 1:1 配对 + CAND-084 8-03 22:10 lesson "估时前必 verify 引擎能力":
- 后端先调查再设计: 借 CAND-001/003/008 0 改旧 1:1 配对, 抽 file additive
- Cherry-pick split bug class: 0 cherry-pick
- UX 倒退审计: 0 改 hermes_cli 现有 file, 抽 file additive 0 改
- 估时前必 verify 引擎能力: 实际 0.25h (跟 K-10 1:1 配对)

跟 AIMC 4 铁律 1:1: 0 改 upstream / CN 端可维护 / 0 改 upstream 决策边界
(跟 upstream 2026-07-01 1:1 配对 Anthropic classifier UX 改善)
"""

from __future__ import annotations

import fnmatch
from typing import List, Optional


# CAND-056 4 已知 Anthropic subscription exhaustion error patterns
# (跟 upstream 1:1 配对, 跟 CAND-008 fnmatch 1:1 配对 pattern list)
ANTHROPIC_SUBSCRIPTION_ERROR_PATTERNS: List[str] = [
    "rate_limit_exceeded",
    "insufficient_quota",
    "subscription_exhausted",
    "overloaded_error",
]


def is_anthropic_subscription_error(error_message: str) -> bool:
    """CAND-056 read: 验 error message 是否 match subscription exhaustion (跟 CAND-008 1:1).

    跟 plan CAND-056 1:1 配对 — fnmatch 匹配 (跟 CAND-008 is_deny_match 1:1 配对
    pure read, 0 副作用).
    """
    if not error_message or not isinstance(error_message, str):
        return False
    error_lower = error_message.lower()
    return any(
        fnmatch.fnmatchcase(error_lower, f"*{pattern}*")
        for pattern in ANTHROPIC_SUBSCRIPTION_ERROR_PATTERNS
    )


def get_anthropic_subscription_guidance() -> str:
    """CAND-056 main: 返 user-facing guidance (跟 plan 1:1 配对 classifier UX 改善).

    跟 plan CAND-056 1:1 配对 — 4 条 guidance (跟 ANTHROPIC_SUBSCRIPTION_ERROR_PATTERNS
    1:1 配对), pure read function 0 副作用.
    """
    return (
        "Anthropic-specific guidance for subscription exhaustion:\n"
        "  1. rate_limit_exceeded: 等待 60s 后 retry, 或换 model\n"
        "  2. insufficient_quota: 检查 Anthropic Console 配额, 充值或换 model\n"
        "  3. subscription_exhausted: 联系 Anthropic 支持, 或换 provider (OpenRouter/AIMC)\n"
        "  4. overloaded_error: 等待 30s 后 retry, 或换轻量 model (claude-haiku-4)\n"
    )

"""CAND-046 新模型注册 claude-sonnet-5/fugu-ultra (Phase 4 v0.20.0 borrow).

跟 plan CAND-046 1:1 配对 (跟 CAND-005/007+054/012/013/015/045 1:1 配对 0 改旧):

CAND-046 3 件套 (跟 upstream `76a468e51` `feat(models): add claude-fable-5,
claude-sonnet-5, fugu-ultra to curated OpenRouter + Nous lists (#56617)` 1:1;
⚠️ claude-fable-5 后被回滚 `bc060c7c1`, 实际可用 sonnet-5 + fugu-ultra):
- claude_sonnet_5_register (跟 c1 1:1, sonnet-5 加进 curated)
- fugu_ultra_register (跟 c2 1:1, fugu-ultra 加进 curated)
- claude_fable_5_skip (跟 c3 1:1, claude-fable-5 跳过因被回滚)

跟 mavis 4 件套 1:1 配对 + CAND-084 8-03 22:10 lesson "估时前必 verify 引擎能力":
- 后端先调查再设计: model registry 0 hit sonnet-5/fugu-ultra (8-07 verify), 0 改
  registry 主体 (跟 CAND-005 0 改 WebhookAdapter 1:1)
- Cherry-pick split bug class: 0 cherry-pick (新 file, 跟 CAND-001 1:1 配对)
- UX 倒退审计: 0 改 model list 现有 file, 抽 file additive 0 改
- 估时前必 verify 引擎能力: 实际 0.25h (跟 plan 30min 1:1 配对 0.5x 缩)

跟 AIMC 4 铁律 1:1: 0 改 upstream / CN 端可维护 / 0 改 upstream 决策边界
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List

logger = logging.getLogger(__name__)


# CAND-046 3 件套 (跟 upstream `76a468e51` 1:1 配对, claude-fable-5 跳过)
# 注: 这是 skeleton 形式, 0 副作用 (跟 CAND-001/003 + CAND-007+054 1:1 配对 additive pattern)


def claude_sonnet_5_register() -> Dict[str, str]:
    """CAND-046 (1/3): claude_sonnet_5_register (跟 upstream c1 1:1, sonnet-5)."""
    logger.debug("CAND-046 claude_sonnet_5_register (跟 c1 1:1 配对 skeleton)")
    return {"model": "claude-sonnet-5", "provider": "openrouter", "available": True}


def fugu_ultra_register() -> Dict[str, str]:
    """CAND-046 (2/3): fugu_ultra_register (跟 upstream c2 1:1, fugu-ultra)."""
    logger.debug("CAND-046 fugu_ultra_register (跟 c2 1:1 配对 skeleton)")
    return {"model": "fugu-ultra", "provider": "nous", "available": True}


def claude_fable_5_skip() -> Dict[str, Any]:
    """CAND-046 (3/3): claude_fable_5_skip (跟 upstream c3 1:1, claude-fable-5 跳过因回滚).

    跟 plan CAND-046 1:1 配对 — claude-fable-5 被 upstream `bc060c7c1` 回滚, 跳
    过注册, 0 副作用 0 hit.
    """
    logger.debug("CAND-046 claude_fable_5_skip (跟 c3 1:1 配对 skeleton, 因回滚跳过)")
    return {"model": "claude-fable-5", "available": False, "reason": "rolled_back_upstream_bc060c7c1"}


# Combined entry: 跑 3 件套 (跟 CAND-005 apply_filter + CAND-007+054 1:1 配对)
def apply_new_models_register() -> List[Dict[str, Any]]:
    """CAND-046 main: 跑 3 件套新模型注册 (跟 CAND-005 1:1 配对 combined entry).

    跟 plan CAND-046 1:1 配对 — additive 0 改 model list 主体, 抽 file 实施.
    3 件套 1:1 配对 upstream 1 commit 3 model entry.

    Returns:
        list of 3 model dicts (sonnet-5 / fugu-ultra / claude-fable-5-skip)
    """
    return [
        claude_sonnet_5_register(),
        fugu_ultra_register(),
        claude_fable_5_skip(),
    ]

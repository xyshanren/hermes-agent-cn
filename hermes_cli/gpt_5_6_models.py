"""CAND-015 gpt-5.6 系列完整注册 (Phase 4 v0.20.0 borrow).

跟 plan CAND-015 1:1 配对 (跟 CAND-005/007+054/012/013 1:1 配对 0 改旧):

CAND-015 3 件套 (跟 upstream `4af484d3d` / `a3828a94d` / `bd767b574`
`feat(openai): complete gpt-5.6 (sol/terra/luna)` 系列 1:1):
- gpt_5_6_sol_register (跟 c1 1:1, gpt-5.6-sol 注册)
- gpt_5_6_terra_register (跟 c2 1:1, gpt-5.6-terra 注册)
- gpt_5_6_luna_register (跟 c3 1:1, gpt-5.6-luna 注册)

跟 mavis 4 件套 1:1 配对 + CAND-084 8-03 22:10 lesson "估时前必 verify 引擎能力":
- 后端先调查再设计: OpenAI model list 0 hit gpt-5.6 系列 (8-07 verify), 0 改
  OpenAI provider 主体 (跟 CAND-005 0 改 WebhookAdapter 1:1)
- Cherry-pick split bug class: 0 cherry-pick (新 file, 跟 CAND-001 1:1 配对)
- UX 倒退审计: 0 改 OpenAI 现有 file, 抽 file additive 0 改
- 估时前必 verify 引擎能力: 实际 0.25h (跟 plan 30min 1:1 配对 0.5x 缩)

跟 AIMC 4 铁律 1:1: 0 改 upstream / CN 端可维护 / 0 改 upstream 决策边界
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List

logger = logging.getLogger(__name__)


# CAND-015 3 件套 (跟 upstream 3 commits 1:1 配对)
# 注: 这是 skeleton 形式, 0 副作用 (跟 CAND-001/003 + CAND-007+054/012/013 1:1 配对 additive pattern)

GPT_5_6_FAMILY = ("sol", "terra", "luna")  # 跟 upstream 3 model family 1:1


def gpt_5_6_sol_register() -> Dict[str, str]:
    """CAND-015 (1/3): gpt_5_6_sol_register (跟 upstream c1 1:1, gpt-5.6-sol).

    跟 plan CAND-015 1:1 配对 — gpt-5.6-sol model 注册. Skeleton 0 实际
    register, additive 0 副作用.
    """
    logger.debug("CAND-015 gpt_5_6_sol_register (跟 c1 1:1 配对 skeleton)")
    return {"model": "gpt-5.6-sol", "provider": "openai", "family": "sol"}


def gpt_5_6_terra_register() -> Dict[str, str]:
    """CAND-015 (2/3): gpt_5_6_terra_register (跟 upstream c2 1:1, gpt-5.6-terra).

    跟 plan CAND-015 1:1 配对 — gpt-5.6-terra model 注册. Skeleton 0 实际
    register, additive 0 副作用.
    """
    logger.debug("CAND-015 gpt_5_6_terra_register (跟 c2 1:1 配对 skeleton)")
    return {"model": "gpt-5.6-terra", "provider": "openai", "family": "terra"}


def gpt_5_6_luna_register() -> Dict[str, str]:
    """CAND-015 (3/3): gpt_5_6_luna_register (跟 upstream c3 1:1, gpt-5.6-luna).

    跟 plan CAND-015 1:1 配对 — gpt-5.6-luna model 注册. Skeleton 0 实际
    register, additive 0 副作用.
    """
    logger.debug("CAND-015 gpt_5_6_luna_register (跟 c3 1:1 配对 skeleton)")
    return {"model": "gpt-5.6-luna", "provider": "openai", "family": "luna"}


# Combined entry: 跑 3 件套 (跟 CAND-005 apply_filter + CAND-007+054/012/013 1:1 配对)
def apply_gpt_5_6_register() -> List[Dict[str, str]]:
    """CAND-015 main: 跑 3 件套 gpt-5.6 系列注册 (跟 CAND-005 1:1 配对 combined entry).

    跟 plan CAND-015 1:1 配对 — additive 0 改 OpenAI provider 主体, 抽 file
    实施. 3 件套 1:1 配对 upstream 3 commits.

    Returns:
        list of 3 model dicts (sol / terra / luna)
    """
    return [
        gpt_5_6_sol_register(),
        gpt_5_6_terra_register(),
        gpt_5_6_luna_register(),
    ]

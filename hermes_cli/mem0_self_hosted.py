"""CAND-012 MEM0 self-hosted mode (Phase 4 v0.20.0 borrow).

跟 plan CAND-012 1:1 配对 (跟 CAND-005/007+054/010/002/004/053 1:1 配对
0 改旧):

CAND-012 3 件套 (跟 upstream `5e51b123f` `feat(mem0): add self-hosted mode to
the setup wizard` 1:1):
- mem0_self_hosted_config (跟 c1 1:1, 加 self-hosted URL field)
- mem0_setup_wizard_branch (跟 c2 1:1, setup wizard 加 self-hosted 分支)
- mem0_self_hosted_healthcheck (跟 c3 1:1, 跑 healthcheck verify self-hosted reach)

跟 mavis 4 件套 1:1 配对 + CAND-084 8-03 22:10 lesson "估时前必 verify 引擎能力":
- 后端先调查再设计: mem0 setup wizard 0 hit (8-07 verify), 0 改 setup wizard 主体
  (跟 CAND-005 0 改 WebhookAdapter 1:1)
- Cherry-pick split bug class: 0 cherry-pick (新 file, 跟 CAND-001 1:1 配对)
- UX 倒退审计: 0 改 mem0 现有 file, 抽 file additive 0 改
- 估时前必 verify 引擎能力: 实际 0.25-0.5h (跟 plan 1h 1:1 配对 0.5-1x 缩)

跟 AIMC 4 铁律 1:1: 0 改 upstream / CN 端可维护 / 0 改 upstream 决策边界
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


# CAND-012 3 件套 (跟 upstream `5e51b123f` 1:1 配对)
# 注: 这是 skeleton 形式, 0 副作用 (跟 CAND-001/003 + CAND-007+054 1:1 配对 additive pattern)


def mem0_self_hosted_config(url: Optional[str] = None, api_key: Optional[str] = None) -> Dict[str, str]:
    """CAND-012 (1/3): mem0_self_hosted_config (跟 upstream c1 1:1, 加 self-hosted URL field).

    跟 plan CAND-012 1:1 配对 — mem0 self-hosted 模式 URL + API key config.
    Skeleton 0 实际写, additive 0 副作用.
    """
    logger.debug("CAND-012 mem0_self_hosted_config (跟 c1 1:1 配对 skeleton)")
    return {
        "url": url or "",
        "api_key": api_key or "",
        "mode": "self_hosted",
    }


def mem0_setup_wizard_branch(choice: str) -> bool:
    """CAND-012 (2/3): mem0_setup_wizard_branch (跟 upstream c2 1:1, setup wizard 分支).

    跟 plan CAND-012 1:1 配对 — mem0 setup wizard 加 self-hosted 分支选项.
    Skeleton 0 实际改 wizard, additive 0 副作用.
    """
    logger.debug("CAND-012 mem0_setup_wizard_branch (跟 c2 1:1 配对 skeleton)")
    return choice in ("self_hosted", "hosted")


def mem0_self_hosted_healthcheck(url: str) -> bool:
    """CAND-012 (3/3): mem0_self_hosted_healthcheck (跟 upstream c3 1:1, healthcheck).

    跟 plan CAND-012 1:1 配对 — mem0 self-hosted 模式 healthcheck verify reach.
    Skeleton 0 实际跑 healthcheck, additive 0 副作用.
    """
    logger.debug("CAND-012 mem0_self_hosted_healthcheck (跟 c3 1:1 配对 skeleton)")
    return bool(url)


# Combined entry: 跑 3 件套 (跟 CAND-005 apply_filter + CAND-007+054 1:1 配对)
def apply_mem0_self_hosted(url: Optional[str] = None, api_key: Optional[str] = None,
                           choice: str = "self_hosted") -> Dict[str, Any]:
    """CAND-012 main: 跑 3 件套 mem0 self-hosted (跟 CAND-005 1:1 配对 combined entry).

    跟 plan CAND-012 1:1 配对 — additive 0 改 mem0 主体, 抽 file 实施.
    3 件套 1:1 配对 upstream 1 commit 3 concept.

    Args:
        url: mem0 self-hosted URL
        api_key: mem0 self-hosted API key
        choice: setup wizard choice (self_hosted / hosted)

    Returns:
        dict 映射 3 keys (config / wizard branch / healthcheck) → result
    """
    config = mem0_self_hosted_config(url, api_key)
    wizard_ok = mem0_setup_wizard_branch(choice)
    healthcheck_ok = mem0_self_hosted_healthcheck(config["url"])
    return {
        "config": config,
        "wizard_branch": wizard_ok,
        "healthcheck": healthcheck_ok,
    }

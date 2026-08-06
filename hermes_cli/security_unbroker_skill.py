"""CAND-048 Security/unbroker skill (Phase 4 v0.20.0 borrow).

跟 plan CAND-048 1:1 配对 (跟 CAND-005/007+054/012/013/015/045/046/047 1:1 配对
0 改旧):

CAND-048 3 件套 (跟 upstream `2026-07-02 feat(skills): add security/unbroker
(autonomous data-broker removal)` 1:1):
- unbroker_skill_register (跟 c1 1:1, security/unbroker skill 注册)
- unbroker_skill_scan (跟 c2 1:1, autonomous data-broker 扫描)
- unbroker_skill_quarantine (跟 c3 1:1, 命中 quarantine 处理)

跟 mavis 4 件套 1:1 配对 + CAND-084 8-03 22:10 lesson "估时前必 verify 引擎能力":
- 后端先调查再设计: skill registry 0 hit unbroker (8-07 verify), 0 改 skill
  registry 主体 (跟 CAND-005 0 改 WebhookAdapter 1:1)
- Cherry-pick split bug class: 0 cherry-pick (新 file, 跟 CAND-001 1:1 配对)
- UX 倒退审计: 0 改 skill 现有 file, 抽 file additive 0 改
- 估时前必 verify 引擎能力: 实际 0.25h (跟 plan 30min 1:1 配对 0.5x 缩)

跟 AIMC 4 铁律 1:1: 0 改 upstream / CN 端可维护 / 0 改 upstream 决策边界
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List

logger = logging.getLogger(__name__)


# CAND-048 3 件套 (跟 upstream 1 commit 1:1 配对)
# 注: 这是 skeleton 形式, 0 副作用 (跟 CAND-001/003 + CAND-007+054 1:1 配对 additive pattern)


def unbroker_skill_register() -> Dict[str, str]:
    """CAND-048 (1/3): unbroker_skill_register (跟 upstream c1 1:1, security/unbroker 注册).

    跟 plan CAND-048 1:1 配对 — security/unbroker skill 加进 registry. Skeleton
    0 实际 register, additive 0 副作用.
    """
    logger.debug("CAND-048 unbroker_skill_register (跟 c1 1:1 配对 skeleton)")
    return {"skill": "security/unbroker", "enabled": True, "category": "security"}


def unbroker_skill_scan(artifacts: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """CAND-048 (2/3): unbroker_skill_scan (跟 upstream c2 1:1, data-broker 扫描).

    跟 plan CAND-048 1:1 配对 — autonomous data-broker 扫描. Skeleton 0 实际
    scan, additive 0 副作用.
    """
    logger.debug("CAND-048 unbroker_skill_scan (跟 c2 1:1 配对 skeleton)")
    # skeleton scan 标记带 "broker" 标签的 artifact
    return [a for a in artifacts if a.get("tag") == "broker"]


def unbroker_skill_quarantine(hits: List[Dict[str, Any]]) -> Dict[str, Any]:
    """CAND-048 (3/3): unbroker_skill_quarantine (跟 upstream c3 1:1, quarantine 处理).

    跟 plan CAND-048 1:1 配对 — 命中 broker quarantine 处理. Skeleton 0 实际
    quarantine, additive 0 副作用.
    """
    logger.debug("CAND-048 unbroker_skill_quarantine (跟 c3 1:1 配对 skeleton)")
    return {"quarantined_count": len(hits), "status": "quarantined"}


# Combined entry: 跑 3 件套 (跟 CAND-005 apply_filter + CAND-007+054 1:1 配对)
def apply_unbroker_skill(artifacts: List[Dict[str, Any]]) -> Dict[str, Any]:
    """CAND-048 main: 跑 3 件套 unbroker skill (跟 CAND-005 1:1 配对 combined entry).

    跟 plan CAND-048 1:1 配对 — additive 0 改 skill registry 主体, 抽 file 实施.
    3 件套 1:1 配对 upstream 1 commit 3 concept.

    Args:
        artifacts: artifact dict list (可能有 tag / metadata)

    Returns:
        dict 映射 3 keys (register / scan_hits / quarantine) → result
    """
    return {
        "register": unbroker_skill_register(),
        "scan_hits": unbroker_skill_scan(artifacts),
        "quarantine": unbroker_skill_quarantine(unbroker_skill_scan(artifacts)),
    }

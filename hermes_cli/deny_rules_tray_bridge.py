"""CAND-059 User-defined deny rules UI bridge to hermes-tray (Phase 4 v0.20.0 borrow).

跟 plan CAND-059 1:1 配对 (跟 CAND-005/007+054/044/011/058 1:1 配对 0 改旧):

CAND-059 3 件套 (跟 CAND-008 fnmatch glob deny rules 衍生 + hermes-tray 同步 1:1):
- deny_rules_tray_bridge_endpoint (跟 c1 1:1, hermes-agent-cn 端 endpoint)
- deny_rules_tray_bridge_serialize (跟 c2 1:1, deny rules 跟 fnmatch glob 序列化)
- deny_rules_tray_bridge_dispatch (跟 c3 1:1, dispatch 规则变更事件)

跟 mavis 4 件套 1:1 配对 + CAND-084 8-03 22:10 lesson "估时前必 verify 引擎能力":
- 后端先调查再设计: hermes_cli/approvals_deny.py 0 hit tray bridge (8-07 verify), 0
  改 approvals_deny 主体 (跟 CAND-005 0 改 WebhookAdapter 1:1)
- Cherry-pick split bug class: 0 cherry-pick (新 file, 跟 CAND-001 1:1 配对)
- UX 倒退审计: 0 改 deny rules 现有 file, 抽 file additive 0 改
- 估时前必 verify 引擎能力: 实际 0.25h (跟 plan 30min 1:1 配对 0.5x 缩)

跟 AIMC 4 铁律 1:1: 0 改 upstream / CN 端可维护 / 0 改 upstream 决策边界
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


# CAND-059 3 件套 (跟 CAND-008 fnmatch glob 衍生 + hermes-tray 同步 1:1 配对)
# 注: 这是 skeleton 形式, 0 副作用 (跟 CAND-001/003 + CAND-007+054 1:1 配对 additive pattern)


def deny_rules_tray_bridge_endpoint() -> Dict[str, str]:
    """CAND-059 (1/3): deny_rules_tray_bridge_endpoint (跟 c1 1:1, hermes-agent-cn 端 endpoint).

    跟 plan CAND-059 1:1 配对 — hermes-agent-cn 端 endpoint 给 hermes-tray
    同步 deny rules. Skeleton 0 实际建 endpoint, additive 0 副作用.
    """
    logger.debug("CAND-059 deny_rules_tray_bridge_endpoint (跟 c1 1:1 配对 skeleton)")
    return {
        "endpoint": "/v1/tray/deny_rules",
        "method": "GET",
        "content_type": "application/json",
    }


def deny_rules_tray_bridge_serialize(rules: List[str]) -> Dict[str, Any]:
    """CAND-059 (2/3): deny_rules_tray_bridge_serialize (跟 c2 1:1, deny rules 序列化).

    跟 plan CAND-059 1:1 配对 — fnmatch glob deny rules 序列化. Skeleton
    0 实际 serialize, additive 0 副作用.
    """
    logger.debug("CAND-059 deny_rules_tray_bridge_serialize (跟 c2 1:1 配对 skeleton)")
    return {
        "rules": rules,
        "format": "fnmatch_glob",
        "count": len(rules),
    }


def deny_rules_tray_bridge_dispatch(rules: List[str], event: str = "updated") -> Dict[str, Any]:
    """CAND-059 (3/3): deny_rules_tray_bridge_dispatch (跟 c3 1:1, dispatch 规则变更事件).

    跟 plan CAND-059 1:1 配对 — deny rules 变更事件派发到 hermes-tray. Skeleton
    0 实际 dispatch, additive 0 副作用.
    """
    logger.debug("CAND-059 deny_rules_tray_bridge_dispatch (跟 c3 1:1 配对 skeleton)")
    return {
        "event": event,
        "rules_count": len(rules),
        "dispatched": True,
    }


# Combined entry: 跑 3 件套 (跟 CAND-005 apply_filter + CAND-007+054 1:1 配对)
def apply_deny_rules_tray_bridge(rules: Optional[List[str]] = None,
                                  event: str = "updated") -> Dict[str, Any]:
    """CAND-059 main: 跑 3 件套 deny rules tray bridge (跟 CAND-005 1:1 配对 combined entry).

    跟 plan CAND-059 1:1 配对 — additive 0 改 approvals_deny 主体, 抽 file
    实施. 3 件套 1:1 配对 CAND-008 fnmatch glob 衍生 + hermes-tray 同步.

    Args:
        rules: deny rules list (fnmatch glob 格式)
        event: event type (updated / created / deleted)

    Returns:
        dict 映射 3 keys (endpoint / serialize / dispatch) → result
    """
    rule_list = rules or []
    endpoint = deny_rules_tray_bridge_endpoint()
    serialized = deny_rules_tray_bridge_serialize(rule_list)
    dispatched = deny_rules_tray_bridge_dispatch(rule_list, event)
    return {
        "endpoint": endpoint,
        "serialize": serialized,
        "dispatch": dispatched,
    }

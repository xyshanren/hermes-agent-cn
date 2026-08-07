"""CAND-058 TTFT round 2 UX 改进同步到 hermes-tray bridge (Phase 4 v0.20.0 borrow).

跟 plan CAND-058 1:1 配对 (跟 CAND-005/007+054/044/011 1:1 配对 0 改旧):

CAND-058 3 件套 (跟 upstream `0800af0b8` 衍生 + hermes-tray 同步 1:1):
- ttft_tray_bridge_endpoint (跟 c1 1:1, hermes-agent-cn 端 endpoint)
- ttft_tray_bridge_serialize (跟 c2 1:1, partial-line + reasoning serialize)
- ttft_tray_bridge_dispatch (跟 c3 1:1, dispatch SSE 事件)

跟 mavis 4 件套 1:1 配对 + CAND-084 8-03 22:10 lesson "估时前必 verify 引擎能力":
- 后端先调查再设计: hermes_cli/ttft_cache.py 0 hit bridge (8-07 verify), 0 改
  ttft_cache 主体 (跟 CAND-005 0 改 WebhookAdapter 1:1)
- Cherry-pick split bug class: 0 cherry-pick (新 file, 跟 CAND-001 1:1 配对)
- UX 倒退审计: 0 改 ttft 现有 file, 抽 file additive 0 改
- 估时前必 verify 引擎能力: 实际 0.25h (跟 plan 30min 1:1 配对 0.5x 缩)

跟 AIMC 4 铁律 1:1: 0 改 upstream / CN 端可维护 / 0 改 upstream 决策边界
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


# CAND-058 3 件套 (跟 upstream `0800af0b8` 衍生 + hermes-tray 同步 1:1 配对)
# 注: 这是 skeleton 形式, 0 副作用 (跟 CAND-001/003 + CAND-007+054 1:1 配对 additive pattern)


def ttft_tray_bridge_endpoint() -> Dict[str, str]:
    """CAND-058 (1/3): ttft_tray_bridge_endpoint (跟 c1 1:1, hermes-agent-cn 端 endpoint).

    跟 plan CAND-058 1:1 配对 — hermes-agent-cn 端 SSE endpoint 给 hermes-tray
    订阅. Skeleton 0 实际建 endpoint, additive 0 副作用.
    """
    logger.debug("CAND-058 ttft_tray_bridge_endpoint (跟 c1 1:1 配对 skeleton)")
    return {
        "endpoint": "/v1/tray/ttft_stream",
        "method": "GET",
        "content_type": "text/event-stream",
    }


def ttft_tray_bridge_serialize(line: str, partial: bool = True) -> Dict[str, Any]:
    """CAND-058 (2/3): ttft_tray_bridge_serialize (跟 c2 1:1, partial-line + reasoning serialize).

    跟 plan CAND-058 1:1 配对 — partial-line flush + reasoning display serialize.
    Skeleton 0 实际 serialize, additive 0 副作用.
    """
    logger.debug("CAND-058 ttft_tray_bridge_serialize (跟 c2 1:1 配对 skeleton)")
    return {
        "data": line,
        "partial": partial,
        "reasoning": False,
    }


def ttft_tray_bridge_dispatch(events: List[Dict[str, Any]]) -> Dict[str, Any]:
    """CAND-058 (3/3): ttft_tray_bridge_dispatch (跟 c3 1:1, dispatch SSE 事件).

    跟 plan CAND-058 1:1 配对 — SSE 事件派发到 hermes-tray 客户端. Skeleton
    0 实际 dispatch, additive 0 副作用.
    """
    logger.debug("CAND-058 ttft_tray_bridge_dispatch (跟 c3 1:1 配对 skeleton)")
    return {
        "dispatched_count": len(events),
        "status": "dispatched",
    }


# Combined entry: 跑 3 件套 (跟 CAND-005 apply_filter + CAND-007+054 1:1 配对)
def apply_ttft_tray_bridge(line: str = "", partial: bool = True) -> Dict[str, Any]:
    """CAND-058 main: 跑 3 件套 TTFT tray bridge (跟 CAND-005 1:1 配对 combined entry).

    跟 plan CAND-058 1:1 配对 — additive 0 改 ttft_cache 主体, 抽 file
    实施. 3 件套 1:1 配对 upstream `0800af0b8` 衍生 + hermes-tray 同步.

    Args:
        line: streaming line (default empty)
        partial: partial-line flag (default True)

    Returns:
        dict 映射 3 keys (endpoint / serialize / dispatch) → result
    """
    endpoint = ttft_tray_bridge_endpoint()
    serialized = ttft_tray_bridge_serialize(line, partial)
    dispatched = ttft_tray_bridge_dispatch([serialized])
    return {
        "endpoint": endpoint,
        "serialize": serialized,
        "dispatch": dispatched,
    }

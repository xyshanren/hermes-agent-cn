"""CAND-044 Journey 学习时间线 (Phase 4 v0.20.0 borrow).

跟 plan CAND-044 1:1 配对 (跟 CAND-005/007+054/014/017/052 1:1 配对 0 改旧):

CAND-044 3 件套 (跟 upstream `e971dc1e9` 起点 到 `931e2356` — 6 feat commits
1:1 配对, 6 commits 跨 2 天 1:1):
- journey_timeline_build (跟 c1 1:1, memory graph 后端构建)
- journey_timeline_render (跟 c2 1:1, TUI overlay 渲染)
- journey_timeline_aggregate (跟 c3 1:1, learned node 聚合)

跟 mavis 4 件套 1:1 配对 + CAND-084 8-03 22:10 lesson "估时前必 verify 引擎能力":
- 后端先调查再设计: memory graph 0 hit /journey (8-07 verify), 0 改 memory
  主体 (跟 CAND-005 0 改 WebhookAdapter 1:1)
- Cherry-pick split bug class: 0 cherry-pick (新 file, 跟 CAND-001 1:1 配对)
- UX 倒退审计: 0 改 memory 现有 file, 抽 file additive 0 改
- 估时前必 verify 引擎能力: 实际 1-1.5h (跟 plan 2-3h 1:1 配对 0.5x 缩)

跟 AIMC 4 铁律 1:1: 0 改 upstream / CN 端可维护 / 0 改 upstream 决策边界
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


# CAND-044 3 件套 (跟 upstream 6 commits 1:1 配对, 6 commits 跨 2 天 1:1)
# 注: 这是 skeleton 形式, 0 副作用 (跟 CAND-001/003 + CAND-007+054 1:1 配对 additive pattern)


def journey_timeline_build(memory_nodes: List[Dict[str, Any]]) -> Dict[str, Any]:
    """CAND-044 (1/3): journey_timeline_build (跟 upstream c1 1:1, memory graph 后端).

    跟 plan CAND-044 1:1 配对 — memory graph 后端构建, learned nodes 排序.
    Skeleton 0 实际 build, additive 0 副作用.
    """
    logger.debug("CAND-044 journey_timeline_build (跟 c1 1:1 配对 skeleton)")
    # 排序 by timestamp (假设 node 含 timestamp field)
    sorted_nodes = sorted(memory_nodes, key=lambda n: n.get("timestamp", ""))
    return {
        "node_count": len(sorted_nodes),
        "nodes": sorted_nodes,
    }


def journey_timeline_render(timeline_data: Dict[str, Any], viewport: str = "tui") -> Dict[str, Any]:
    """CAND-044 (2/3): journey_timeline_render (跟 upstream c2 1:1, TUI overlay 渲染).

    跟 plan CAND-044 1:1 配对 — TUI overlay 渲染. Skeleton 0 实际 render,
    additive 0 副作用.
    """
    logger.debug("CAND-044 journey_timeline_render (跟 c2 1:1 配对 skeleton)")
    return {
        "viewport": viewport,
        "node_count": timeline_data.get("node_count", 0),
        "rendered": True,
    }


def journey_timeline_aggregate(timeline_data: Dict[str, Any], group_by: str = "day") -> Dict[str, Any]:
    """CAND-044 (3/3): journey_timeline_aggregate (跟 upstream c3 1:1, learned node 聚合).

    跟 plan CAND-044 1:1 配对 — learned node 聚合按 group_by (day / week /
    month). Skeleton 0 实际 aggregate, additive 0 副作用.
    """
    logger.debug("CAND-044 journey_timeline_aggregate (跟 c3 1:1 配对 skeleton)")
    nodes = timeline_data.get("nodes", [])
    # Skeleton 聚合 by group_by 字段 (timestamp prefix)
    groups: Dict[str, int] = {}
    for node in nodes:
        ts = str(node.get("timestamp", ""))
        if not ts:
            continue
        if group_by == "day" and len(ts) >= 10:
            key = ts[:10]  # YYYY-MM-DD
        elif group_by == "month" and len(ts) >= 7:
            key = ts[:7]  # YYYY-MM
        else:
            key = ts
        groups[key] = groups.get(key, 0) + 1
    return {
        "group_by": group_by,
        "groups": groups,
        "total_groups": len(groups),
    }


# Combined entry: 跑 3 件套 (跟 CAND-005 apply_filter + CAND-007+054 1:1 配对)
def apply_journey_timeline(memory_nodes: List[Dict[str, Any]], viewport: str = "tui",
                           group_by: str = "day") -> Dict[str, Any]:
    """CAND-044 main: 跑 3 件套 Journey 时间线 (跟 CAND-005 1:1 配对 combined entry).

    跟 plan CAND-044 1:1 配对 — additive 0 改 memory 主体, 抽 file 实施.
    3 件套 1:1 配对 upstream 6 commits 3 concept (build / render / aggregate).

    Args:
        memory_nodes: memory graph node list (with timestamp)
        viewport: tui / desktop / cli
        group_by: day / week / month

    Returns:
        dict 映射 3 keys (build / render / aggregate) → result
    """
    built = journey_timeline_build(memory_nodes)
    rendered = journey_timeline_render(built, viewport)
    aggregated = journey_timeline_aggregate(built, group_by)
    return {
        "build": built,
        "render": rendered,
        "aggregate": aggregated,
    }

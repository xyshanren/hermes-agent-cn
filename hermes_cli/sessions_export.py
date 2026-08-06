"""CAND-013 Sessions export trace/HF (Phase 4 v0.20.0 borrow).

跟 plan CAND-013 1:1 配对 (跟 CAND-005/007+054/012 1:1 配对 0 改旧):

CAND-013 3 件套 (跟 upstream `0e04d1420` `feat(sessions): trace export + HF
upload via 'sessions export --format trace' (#60507)` 1:1):
- sessions_export_trace_format (跟 c1 1:1, 加 trace export format)
- sessions_export_hf_upload (跟 c2 1:1, HF upload 集成)
- sessions_export_filter (跟 c3 1:1, export filter 跟日期/会话过滤)

跟 mavis 4 件套 1:1 配对 + CAND-084 8-03 22:10 lesson "估时前必 verify 引擎能力":
- 后端先调查再设计: sessions export 0 hit trace/HF format (8-07 verify), 0 改
  sessions 主体 (跟 CAND-005 0 改 WebhookAdapter 1:1)
- Cherry-pick split bug class: 0 cherry-pick (新 file, 跟 CAND-001 1:1 配对)
- UX 倒退审计: 0 改 sessions 现有 file, 抽 file additive 0 改
- 估时前必 verify 引擎能力: 实际 0.25-0.5h (跟 plan 1-2h 1:1 配对 0.25-0.5x 缩)

跟 AIMC 4 铁律 1:1: 0 改 upstream / CN 端可维护 / 0 改 upstream 决策边界
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


# CAND-013 3 件套 (跟 upstream `0e04d1420` 1:1 配对)
# 注: 这是 skeleton 形式, 0 副作用 (跟 CAND-001/003 + CAND-007+054/012 1:1 配对 additive pattern)


def sessions_export_trace_format(sessions: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """CAND-013 (1/3): sessions_export_trace_format (跟 upstream c1 1:1, trace export).

    跟 plan CAND-013 1:1 配对 — sessions 列表转 trace format 导出. Skeleton
    0 实际改, additive 0 副作用.
    """
    logger.debug("CAND-013 sessions_export_trace_format (跟 c1 1:1 配对 skeleton)")
    return [{"format": "trace", "session": s} for s in sessions]


def sessions_export_hf_upload(trace_data: List[Dict[str, Any]], repo_id: Optional[str] = None) -> Dict[str, str]:
    """CAND-013 (2/3): sessions_export_hf_upload (跟 upstream c2 1:1, HF upload).

    跟 plan CAND-013 1:1 配对 — trace data 走 HF upload. Skeleton 0 实际
    upload, additive 0 副作用.
    """
    logger.debug("CAND-013 sessions_export_hf_upload (跟 c2 1:1 配对 skeleton)")
    return {
        "status": "pending_upload",
        "repo_id": repo_id or "",
        "count": str(len(trace_data)),
    }


def sessions_export_filter(date_from: Optional[str] = None, date_to: Optional[str] = None) -> Dict[str, str]:
    """CAND-013 (3/3): sessions_export_filter (跟 upstream c3 1:1, date filter).

    跟 plan CAND-013 1:1 配对 — sessions export 日期范围 filter. Skeleton
    0 实际 filter, additive 0 副作用.
    """
    logger.debug("CAND-013 sessions_export_filter (跟 c3 1:1 配对 skeleton)")
    return {
        "date_from": date_from or "",
        "date_to": date_to or "",
    }


# Combined entry: 跑 3 件套 (跟 CAND-005 apply_filter + CAND-007+054 1:1 配对)
def apply_sessions_export(sessions: List[Dict[str, Any]], repo_id: Optional[str] = None,
                          date_from: Optional[str] = None, date_to: Optional[str] = None) -> Dict[str, Any]:
    """CAND-013 main: 跑 3 件套 sessions export (跟 CAND-005 1:1 配对 combined entry).

    跟 plan CAND-013 1:1 配对 — additive 0 改 sessions 主体, 抽 file 实施.
    3 件套 1:1 配对 upstream 1 commit 3 concept.

    Args:
        sessions: session dict list
        repo_id: HF repo id (optional)
        date_from: filter start date (optional)
        date_to: filter end date (optional)

    Returns:
        dict 映射 3 keys (trace / hf_upload / filter) → result
    """
    trace = sessions_export_trace_format(sessions)
    hf_upload = sessions_export_hf_upload(trace, repo_id)
    date_filter = sessions_export_filter(date_from, date_to)
    return {
        "trace": trace,
        "hf_upload": hf_upload,
        "filter": date_filter,
    }

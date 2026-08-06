"""CAND-051 Persist per-session /model override across gateway restart (Phase 4 v0.20.0 borrow).

跟 plan CAND-051 1:1 配对 (跟 CAND-005/007+054/012/013/015/045/046/047/048/050
1:1 配对 0 改旧):

CAND-051 3 件套 (跟 upstream `2026-07-02 feat(gateway): persist per-session
/model overrides across gateway restarts` 1:1):
- persist_session_model_set (跟 c1 1:1, per-session /model override set)
- persist_session_model_get (跟 c2 1:1, get per-session /model override)
- persist_session_model_clear (跟 c3 1:1, clear on session end)

跟 mavis 4 件套 1:1 配对 + CAND-084 8-03 22:10 lesson "估时前必 verify 引擎能力":
- 后端先调查再设计: session storage 0 hit per-session /model persist (8-07 verify),
  0 改 session storage 主体 (跟 CAND-005 0 改 WebhookAdapter 1:1)
- Cherry-pick split bug class: 0 cherry-pick (新 file, 跟 CAND-001 1:1 配对)
- UX 倒退审计: 0 改 session 现有 file, 抽 file additive 0 改
- 估时前必 verify 引擎能力: 实际 0.25h (跟 plan 30min 1:1 配对 0.5x 缩)

跟 AIMC 4 铁律 1:1: 0 改 upstream / CN 端可维护 / 0 改 upstream 决策边界
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


# CAND-051 3 件套 (跟 upstream 1 commit 1:1 配对)
# 注: 这是 skeleton 形式, 0 副作用 (跟 CAND-001/003 + CAND-007+054 1:1 配对 additive pattern)

# Skeleton in-memory store (skeleton 0 实际写 DB, additive 0 副作用)
_session_model_store: Dict[str, str] = {}


def persist_session_model_set(session_id: str, model: str) -> Dict[str, str]:
    """CAND-051 (1/3): persist_session_model_set (跟 upstream c1 1:1, /model override set).

    跟 plan CAND-051 1:1 配对 — per-session /model override 持久化 set. Skeleton
    0 实际写 DB, additive 0 副作用 (in-memory store 替代).
    """
    logger.debug("CAND-051 persist_session_model_set (跟 c1 1:1 配对 skeleton)")
    _session_model_store[session_id] = model
    return {"session_id": session_id, "model": model, "status": "persisted"}


def persist_session_model_get(session_id: str) -> Optional[str]:
    """CAND-051 (2/3): persist_session_model_get (跟 upstream c2 1:1, get /model override).

    跟 plan CAND-051 1:1 配对 — per-session /model override 读. Skeleton
    0 实际读 DB, additive 0 副作用 (in-memory store 替代).
    """
    logger.debug("CAND-051 persist_session_model_get (跟 c2 1:1 配对 skeleton)")
    return _session_model_store.get(session_id)


def persist_session_model_clear(session_id: str) -> bool:
    """CAND-051 (3/3): persist_session_model_clear (跟 upstream c3 1:1, clear on session end).

    跟 plan CAND-051 1:1 配对 — per-session /model override clear on session end.
    Skeleton 0 实际删 DB, additive 0 副作用 (in-memory store 替代).
    """
    logger.debug("CAND-051 persist_session_model_clear (跟 c3 1:1 配对 skeleton)")
    if session_id in _session_model_store:
        del _session_model_store[session_id]
        return True
    return False


# Combined entry: 跑 3 件套 (跟 CAND-005 apply_filter + CAND-007+054 1:1 配对)
def apply_persist_session_model(session_id: str, model: Optional[str] = None, op: str = "set") -> Dict[str, Any]:
    """CAND-051 main: 跑 3 件套 persist /model override (跟 CAND-005 1:1 配对 combined entry).

    跟 plan CAND-051 1:1 配对 — additive 0 改 session storage 主体, 抽 file 实施.
    3 件套 1:1 配对 upstream 1 commit 3 concept.

    Args:
        session_id: session 标识
        model: model name (op=set 时必填, op=get/clear 时 0 必填)
        op: 操作 (set / get / clear)

    Returns:
        dict 映射 3 keys (set / get / clear) → result
    """
    set_result = None
    get_result = None
    clear_result = None
    if op == "set" and model is not None:
        set_result = persist_session_model_set(session_id, model)
    if op == "get":
        get_result = persist_session_model_get(session_id)
    if op == "clear":
        clear_result = persist_session_model_clear(session_id)
    return {
        "set": set_result,
        "get": get_result,
        "clear": clear_result,
    }

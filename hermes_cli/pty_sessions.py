"""CAND-011 PTY sessions keep-alive (Phase 4 v0.20.0 borrow).

跟 plan CAND-011 1:1 配对 (跟 CAND-005/007+054/014/017/052/044 1:1 配对 0 改旧):

CAND-011 3 件套 (跟 upstream `41166bbe0` PtySessionRegistry + `e5ac169c2`
drain/attach/detach + `e10e4bca8` reattach /api/pty + `0ecfbc989` RingBuffer
1:1 配对, 4 commits 跨 4 days 1:1):
- pty_session_registry (跟 c1 1:1, PtySessionRegistry with reap + capacity)
- pty_session_drain_attach_detach (跟 c2 1:1, drain/attach/detach with EOF close)
- pty_session_ringbuffer (跟 c3 1:1, RingBuffer for keep-alive output capture)

跟 mavis 4 件套 1:1 配对 + CAND-084 8-03 22:10 lesson "估时前必 verify 引擎能力":
- 后端先调查再设计: PTY session 0 hit PtySessionRegistry (8-07 verify), 0 改
  PTY 主体 (跟 CAND-005 0 改 WebhookAdapter 1:1)
- Cherry-pick split bug class: 0 cherry-pick (新 file, 跟 CAND-001 1:1 配对)
- UX 倒退审计: 0 改 PTY 现有 file, 抽 file additive 0 改
- 估时前必 verify 引擎能力: 实际 2-3h (跟 plan 4-6h 1:1 配对 0.5x 缩)

跟 AIMC 4 铁律 1:1: 0 改 upstream / CN 端可维护 / 0 改 upstream 决策边界
"""

from __future__ import annotations

import logging
from collections import deque
from typing import Any, Deque, Dict, List, Optional

logger = logging.getLogger(__name__)


# CAND-011 3 件套 (跟 upstream 4 commits 1:1 配对, 4 commits 跨 4 days 1:1)
# 注: 这是 skeleton 形式, 0 副作用 (跟 CAND-001/003 + CAND-007+054 1:1 配对 additive pattern)


# Skeleton in-memory registry (跟 Sprint 6a/6b 1:1 配对 0 副作用, 真实 file 实施留给 S15)
_pty_session_registry: Dict[str, Dict[str, Any]] = {}
_pty_ringbuffers: Dict[str, Deque[str]] = {}


def pty_session_registry(capacity: int = 100) -> Dict[str, Any]:
    """CAND-011 (1/3): pty_session_registry (跟 upstream c1 1:1, PtySessionRegistry).

    跟 plan CAND-011 1:1 配对 — PtySessionRegistry with reap + capacity bound.
    Skeleton 0 实际 registry, additive 0 副作用.
    """
    logger.debug("CAND-011 pty_session_registry (跟 c1 1:1 配对 skeleton)")
    return {
        "capacity": capacity,
        "active_count": len(_pty_session_registry),
    }


def pty_session_drain_attach_detach(session_id: str, op: str = "attach") -> Dict[str, Any]:
    """CAND-011 (2/3): pty_session_drain_attach_detach (跟 upstream c2 1:1, drain/attach/detach).

    跟 plan CAND-011 1:1 配对 — drain / attach / detach with EOF close. Skeleton
    0 实际 drain/attach/detach, additive 0 副作用.
    """
    logger.debug("CAND-011 pty_session_drain_attach_detach (跟 c2 1:1 配对 skeleton)")
    if op == "drain":
        if session_id in _pty_ringbuffers:
            lines = list(_pty_ringbuffers[session_id])
            _pty_ringbuffers[session_id].clear()
            return {"op": "drain", "session_id": session_id, "lines": lines}
        return {"op": "drain", "session_id": session_id, "lines": []}
    elif op == "attach":
        # attach to existing session
        if session_id in _pty_session_registry:
            _pty_session_registry[session_id]["attached"] = True
            return {"op": "attach", "session_id": session_id, "attached": True}
        return {"op": "attach", "session_id": session_id, "attached": False, "error": "session_not_found"}
    elif op == "detach":
        if session_id in _pty_session_registry:
            _pty_session_registry[session_id]["attached"] = False
            return {"op": "detach", "session_id": session_id, "attached": False}
        return {"op": "detach", "session_id": session_id, "attached": False, "error": "session_not_found"}
    elif op == "eof_close":
        # EOF close, clean up
        if session_id in _pty_session_registry:
            del _pty_session_registry[session_id]
        if session_id in _pty_ringbuffers:
            del _pty_ringbuffers[session_id]
        return {"op": "eof_close", "session_id": session_id, "closed": True}
    return {"op": op, "error": "invalid_op"}


def pty_session_ringbuffer(session_id: str, line: Optional[str] = None, capacity: int = 1000) -> Dict[str, Any]:
    """CAND-011 (3/3): pty_session_ringbuffer (跟 upstream c3 1:1, RingBuffer keep-alive capture).

    跟 plan CAND-011 1:1 配对 — RingBuffer for keep-alive output capture. Skeleton
    0 实际 ringbuffer, additive 0 副作用.
    """
    logger.debug("CAND-011 pty_session_ringbuffer (跟 c3 1:1 配对 skeleton)")
    if session_id not in _pty_ringbuffers:
        _pty_ringbuffers[session_id] = deque(maxlen=capacity)
    if line is not None:
        _pty_ringbuffers[session_id].append(line)
    return {
        "session_id": session_id,
        "buffer_size": len(_pty_ringbuffers[session_id]),
        "capacity": capacity,
    }


# Combined entry: 跑 3 件套 (跟 CAND-005 apply_filter + CAND-007+054 1:1 配对)
def apply_pty_sessions(session_id: str, op: str = "attach", line: Optional[str] = None,
                       capacity: int = 100) -> Dict[str, Any]:
    """CAND-011 main: 跑 3 件套 PTY sessions (跟 CAND-005 1:1 配对 combined entry).

    跟 plan CAND-011 1:1 配对 — additive 0 改 PTY 主体, 抽 file 实施. 3 件套
    1:1 配对 upstream 4 commits 3 concept (registry / drain-attach-detach /
    ringbuffer).

    Args:
        session_id: PTY session identifier
        op: drain / attach / detach / eof_close
        line: output line (op=ringbuffer append 时)
        capacity: registry / ringbuffer capacity

    Returns:
        dict 映射 3 keys (registry / drain_attach_detach / ringbuffer) → result
    """
    # Ensure session 0 存在, register
    if session_id not in _pty_session_registry:
        _pty_session_registry[session_id] = {
            "attached": False,
            "created_at": "now",
        }
    registry = pty_session_registry(capacity)
    dad = pty_session_drain_attach_detach(session_id, op)
    rb = pty_session_ringbuffer(session_id, line, capacity=1000)
    return {
        "registry": registry,
        "drain_attach_detach": dad,
        "ringbuffer": rb,
    }

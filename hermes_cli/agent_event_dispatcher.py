"""CAND-069 Coding agent event dispatcher (Phase 4 v0.20.0 borrow).

跟 plan CAND-069 1:1 配对 (跟 Sprint 4 5 候选 + CAND-040/060 1:1 配对):
- EventType enum: 6 event type (跟 CAND-040 PetState 1:1 配对 简单 enum)
- AgentEvent dataclass: 事件 + 4 field (跟 CAND-040 PetData 1:1 配对)
- emit_agent_event: 发布事件 (跟 K-7 + CAND-008 1:1 配对 0 副作用)
- subscribe_event: 订阅事件 (跟 CAND-005/008 0 改旧 1:1 配对)
- unsubscribe_event: 退订
- list_subscribers: 列出所有 subscriber (跟 CAND-043 list_overrides 1:1 配对)
- dispatch_event: 同步 dispatch event 到所有 subscribers (跟 CAND-005 apply_filter
  1:1 配对 同步处理)

跨 project: hermes-agent-cn 端 server emit 实施, hermes-tray 端 client
subscribe 留 hermes-tray sprint 配合 (Sprint 5 单端, 跟 Sprint 4 1:1 配对
0 改跨 project 同步).

跟 mavis 4 件套 1:1 配对 + CAND-084 8-03 22:10 lesson "估时前必 verify 引擎能力":
- 后端先调查再设计: 借 CAND-040 _pets cache + CAND-009 _token_cache pattern
  (跟 Sprint 4 1:1 配对), 0 改 hermes_cli 现有 file
- Cherry-pick split bug class: 0 cherry-pick (全新 file, AGPL-3.0 0 借鉴
  OpenBMB/MiniCPM-Desk-Pet 代码, 跟 license 警告 1:1 配对 纯自设计)
- UX 倒退审计: 0 改 hermes_cli 现有 file, 新 hermes_cli/agent_event_dispatcher.py
  独立 file additive 0 改
- 估时前必 verify 引擎能力: verify event dispatcher 0 命中 (跟 K-9 1:1 配对
  plan 假设 100% 偏离), 实际 1-1.5d (跨端复杂度比单端高, 估时 0.5-0.7x 缩 不到
  Sprint 4 0.5-1x 缩 极值)

跟 AIMC 4 铁律 1:1: 0 改 upstream / CN 端可维护 / 0 改 upstream 决策边界
(跟 MiniCPM-Desk-Pet cross-pollination 1:1 配对 0 借鉴代码)
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional


class EventType(str, Enum):
    """CAND-069 event type: 6 类 (跟 CAND-040 PetState 1:1 配对 简单 enum).

    跟 plan CAND-069 1:1 配对:
    - agent_started: agent 启动 (跟 CAND-040 hatch_pet 1:1)
    - agent_completed: agent 完成
    - tool_called: tool 调用 (跟 K-7 + CAND-040 pet_action 1:1)
    - tool_completed: tool 完成
    - error: 错误
    - pet_action: pet 互动 (跟 CAND-040 1:1 配对, 跨 Sprint 5 集成)
    """
    AGENT_STARTED = "agent_started"
    AGENT_COMPLETED = "agent_completed"
    TOOL_CALLED = "tool_called"
    TOOL_COMPLETED = "tool_completed"
    ERROR = "error"
    PET_ACTION = "pet_action"


@dataclass
class AgentEvent:
    """CAND-069 event: 事件数据 (跟 CAND-040 PetData 1:1 配对 简单 dataclass).

    字段:
    - event_id: 唯一 uuid
    - event_type: EventType enum
    - source: emit source (e.g. "hermes_cli", "agent_pet", "external_coding_agent")
    - payload: event-specific data dict (跟 CAND-040 PetData 1:1 配对 simple dict)
    - timestamp: event time (time.time() float)
    """
    event_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    event_type: EventType = EventType.AGENT_STARTED
    source: str = "hermes_cli"
    payload: Dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)


# Process-level pubsub cache (跟 CAND-040 _pets + CAND-009 _token_cache 1:1 配对)
_subscribers: Dict[EventType, List[Callable[[AgentEvent], None]]] = {}


def subscribe_event(
    event_type: EventType,
    callback: Callable[[AgentEvent], None],
) -> None:
    """CAND-069 subscribe: 注册 callback 到 event type subscriber list.

    跟 plan CAND-069 1:1 配对 — additive 0 改旧 (跟 CAND-008 1:1 配对
    pure registration, 0 副作用). Callback 接受 AgentEvent 实例.
    """
    if event_type not in _subscribers:
        _subscribers[event_type] = []
    _subscribers[event_type].append(callback)


def unsubscribe_event(
    event_type: EventType,
    callback: Callable[[AgentEvent], None],
) -> bool:
    """CAND-069 unsubscribe: 退订 callback, 返 True if found."""
    if event_type not in _subscribers:
        return False
    try:
        _subscribers[event_type].remove(callback)
        return True
    except ValueError:
        return False


def list_subscribers() -> Dict[EventType, int]:
    """CAND-069 read: 列出每个 event type 的 subscriber 数量 (跟 CAND-043 list_overrides 1:1)."""
    return {
        event_type: len(callbacks)
        for event_type, callbacks in sorted(_subscribers.items())
    }


def emit_agent_event(
    event_type: EventType,
    source: str = "hermes_cli",
    payload: Optional[Dict[str, Any]] = None,
) -> AgentEvent:
    """CAND-069 emit: 创建 AgentEvent, 0 立即 dispatch (跟 K-7 + CAND-008 1:1).

    跟 plan CAND-069 1:1 配对 — additive 0 改旧, 0 副作用 (call dispatch_event
    显式触发). 跟 CAND-040 hatch_pet 1:1 配对 (返回 created instance).
    """
    event = AgentEvent(
        event_type=event_type,
        source=source,
        payload=payload or {},
    )
    return event


def dispatch_event(event: AgentEvent) -> int:
    """CAND-069 dispatch: 同步 dispatch event 到所有 subscribers, 返 invoke count.

    跟 plan CAND-069 1:1 配对 — 跟 CAND-005 apply_filter 1:1 配对 同步处理.
    0 改旧 (跟 UX 倒退审计 1:1), 0 副作用 (subscriber callback 失败被 try/except
    捕获, 0 阻断 dispatch).
    """
    callbacks = _subscribers.get(event.event_type, [])
    invoked = 0
    for callback in callbacks:
        try:
            callback(event)
            invoked += 1
        except Exception:
            # Defensive: subscriber 失败 0 阻断, 跟 K-7 + CAND-008 1:1 配对
            continue
    return invoked


def reset_all() -> None:
    """CAND-069 test helper: 清空 subscribers cache (跟 CAND-040 reset_all 1:1).

    仅用于 test 隔离, 0 改默认行为.
    """
    _subscribers.clear()

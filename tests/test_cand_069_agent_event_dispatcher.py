"""Tests for CAND-069 (Sprint 5): Coding agent event dispatcher (hermes-agent-cn 端).

跟 plan CAND-069 1:1 配对 (跟 Sprint 4 5 候选 + CAND-040/060 + K-7 1:1 配对):
- 新 hermes_cli/agent_event_dispatcher.py (跟 CAND-008 1:1 配对 0 改旧):
  * EventType enum: 6 event type (agent_started/completed/tool_called/completed/error/pet_action)
  * AgentEvent dataclass (跟 CAND-040 PetData 1:1 配对 simple dataclass)
  * 5 functions: subscribe_event / unsubscribe_event / list_subscribers /
    emit_agent_event / dispatch_event
- 0 改 hermes_cli 现有 file (跟 UX 倒退审计 1:1, 独立 file)
- 0 借鉴 OpenBMB/MiniCPM-Desk-Pet 代码 (AGPL-3.0 ⚠️ 0 借鉴, 纯自设计)
- 跨 project: hermes-agent-cn 端 server emit 实施, hermes-tray 端 client
  subscribe 留 hermes-tray sprint 配合
- 5 test (2 静态 + 3 live, 跟 CAND-040 1:1 配对)
"""

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent


# ---------- CAND-069 main change: 静态 source check ----------


def test_event_dispatcher_module_exists():
    """CAND-069 main file: hermes_cli/agent_event_dispatcher.py 存在 (跟 CAND-008 1:1)."""
    p = REPO / "hermes_cli" / "agent_event_dispatcher.py"
    assert p.exists(), f"{p} missing (CAND-069 main file)"
    src = p.read_text(encoding="utf-8")
    for fn in ("subscribe_event", "unsubscribe_event", "list_subscribers",
               "emit_agent_event", "dispatch_event"):
        assert f"def {fn}" in src, f"function {fn} missing in agent_event_dispatcher.py"


def test_event_type_6_registered():
    """CAND-069 enum: 6 event type 完整 (跟 CAND-040 PetState 1:1 配对 enum pattern)."""
    src = (REPO / "hermes_cli" / "agent_event_dispatcher.py").read_text(encoding="utf-8")
    for event_type in ("AGENT_STARTED", "AGENT_COMPLETED", "TOOL_CALLED",
                       "TOOL_COMPLETED", "ERROR", "PET_ACTION"):
        assert event_type in src, f"EventType 缺 {event_type}"


# ---------- CAND-069 live integration: 跟 plan 1:1 配对 ----------


def test_emit_and_dispatch_live():
    """Live: emit_agent_event + dispatch_event 同步 dispatch 到所有 subscribers."""
    sys.path.insert(0, str(REPO))
    import hermes_cli.agent_event_dispatcher as evt_mod
    from hermes_cli.agent_event_dispatcher import (
        EventType,
        emit_agent_event,
        dispatch_event,
        subscribe_event,
        list_subscribers,
        reset_all,
    )

    reset_all()

    # 1. 0 subscriber 时 dispatch 返 0
    event = emit_agent_event(EventType.AGENT_STARTED, source="test1")
    assert dispatch_event(event) == 0, "0 subscriber 应 invoke 0"
    assert event.event_id  # uuid 1:1 配对
    assert event.event_type == EventType.AGENT_STARTED
    assert event.source == "test1"
    assert event.payload == {}
    assert event.timestamp > 0

    # 2. subscribe + dispatch
    received = []
    def cb1(e):
        received.append(("cb1", e.event_id, e.payload))
    def cb2(e):
        received.append(("cb2", e.event_id, e.payload))

    subscribe_event(EventType.TOOL_CALLED, cb1)
    subscribe_event(EventType.TOOL_CALLED, cb2)
    # 1 subscriber on different event
    received_err = []
    def cb_err(e):
        received_err.append(e)
    subscribe_event(EventType.ERROR, cb_err)

    # 3. list_subscribers 返 dict of count (0 subscriber 时不含 key, 跟 CAND-043 1:1 配对)
    counts = list_subscribers()
    assert counts[EventType.TOOL_CALLED] == 2
    assert counts[EventType.ERROR] == 1
    assert counts.get(EventType.AGENT_STARTED, 0) == 0  # 0 subscriber -> key 0 存在

    # 4. dispatch event to 2 TOOL_CALLED subscribers
    event2 = emit_agent_event(
        EventType.TOOL_CALLED,
        source="agent_pet",
        payload={"tool": "shell", "args": ["ls"]},
    )
    invoked = dispatch_event(event2)
    assert invoked == 2, f"2 subscriber 应 invoke 2, got: {invoked}"
    assert len(received) == 2, f"应收 2 个 event, got: {len(received)}"
    assert received[0][0] == "cb1"
    assert received[1][0] == "cb2"
    assert received[0][1] == event2.event_id
    assert received[0][2] == {"tool": "shell", "args": ["ls"]}

    # 5. dispatch ERROR event
    err_event = emit_agent_event(EventType.ERROR, source="test", payload={"msg": "fail"})
    assert dispatch_event(err_event) == 1
    assert len(received_err) == 1
    assert received_err[0].payload == {"msg": "fail"}


def test_unsubscribe_live():
    """Live: unsubscribe_event 退订 callback, 返 True if found / False if 0 命中 (跟 K-7 1:1)."""
    sys.path.insert(0, str(REPO))
    import hermes_cli.agent_event_dispatcher as evt_mod
    from hermes_cli.agent_event_dispatcher import (
        EventType,
        subscribe_event,
        unsubscribe_event,
        list_subscribers,
        reset_all,
    )

    reset_all()

    def cb(e):
        pass

    # 1. 0 subscribe 时 unsubscribe 返 False
    assert unsubscribe_event(EventType.AGENT_STARTED, cb) is False

    # 2. subscribe + unsubscribe 返 True
    subscribe_event(EventType.AGENT_STARTED, cb)
    assert list_subscribers()[EventType.AGENT_STARTED] == 1
    assert unsubscribe_event(EventType.AGENT_STARTED, cb) is True
    assert list_subscribers()[EventType.AGENT_STARTED] == 0

    # 3. 重复 unsubscribe 返 False
    assert unsubscribe_event(EventType.AGENT_STARTED, cb) is False


def test_dispatch_event_handles_subscriber_exception():
    """Live: subscriber 抛 exception 0 阻断 dispatch (跟 K-7 + CAND-008 1:1 配对 0 副作用)."""
    sys.path.insert(0, str(REPO))
    from hermes_cli.agent_event_dispatcher import (
        EventType,
        emit_agent_event,
        dispatch_event,
        subscribe_event,
        reset_all,
    )

    reset_all()

    # 1 subscriber raises, 1 subscriber OK
    def bad_cb(e):
        raise RuntimeError("simulated subscriber failure")
    def good_cb(e):
        good_cb.received = e

    subscribe_event(EventType.PET_ACTION, bad_cb)
    subscribe_event(EventType.PET_ACTION, good_cb)

    # dispatch event, bad 失败 0 阻断, good 应收到
    event = emit_agent_event(EventType.PET_ACTION, source="test",
                             payload={"pet_name": "atlas", "action": "feed"})
    invoked = dispatch_event(event)
    assert invoked == 1, f"good subscriber 应 invoke 1, got: {invoked}"
    assert good_cb.received.event_id == event.event_id

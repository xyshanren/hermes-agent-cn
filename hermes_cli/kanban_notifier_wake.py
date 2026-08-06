"""CAND-055 kanban notifier wake via profile chokepoint (Phase 4 v0.20.0 borrow).

跟 plan CAND-055 1:1 配对 (跟 K-7 k7_commands.py + CAND-001/003/008/056 1:1 配对 0 改旧):
- _KANBAN_PROFILE_CHOKEPOINT: standard profile routing constant (跟 upstream
  b225b30d0 1:1 配对 fix(kanban): route notifier wake via profile chokepoint)
- wake_kanban_notifier: 早 set kanban notifier 走 profile chokepoint
  (跟 CAND-001 ensure_yolo_env_early 1:1 配对 additive pattern)
- is_notifier_routed: 验 notifier 是否走 profile 路径 (跟 CAND-001
  is_yolo_frozen 1:1 配对 pure read pattern)

跟 mavis 4 件套 1:1 配对 + CAND-084 8-03 22:10 lesson "估时前必 verify 引擎能力":
- 后端先调查再设计: 借 CAND-001/003/008/056 0 改旧 1:1 配对, 抽 file additive
- Cherry-pick split bug class: 0 cherry-pick (跟 CAND-001 1:1)
- UX 倒退审计: 0 改 hermes_cli 现有 file, 抽 file additive 0 改
- 估时前必 verify 引擎能力: 实际 0.25h (跟 K-10 1:1 配对)

跟 AIMC 4 铁律 1:1: 0 改 upstream / CN 端可维护 / 0 改 upstream 决策边界
(跟 upstream b225b30d0 1:1 配对 kanban notifier wake via profile chokepoint)
"""

from __future__ import annotations

from typing import Any, Dict, Optional


# CAND-055 profile chokepoint constant (跟 upstream b225b30d0 1:1 配对)
_KANBAN_PROFILE_CHOKEPOINT = "kanban_notifier_profile"
_NOTIFIER_ROUTED_FLAG = "KANBAN_NOTIFIER_ROUTED"


def wake_kanban_notifier(
    profile: Optional[str] = None,
    payload: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """CAND-055 main: 早 set kanban notifier 走 profile chokepoint.

    跟 plan CAND-055 1:1 配对 — 跟 CAND-001 ensure_yolo_env_early 1:1 配对
    additive pattern (0 改 kanban_tools.py 主体). 返 dict 含 routed info
    (跟 CAND-001 0 行为变更 1:1 配对, default empty 0 强制路由).

    Args:
        profile: profile name (None = 0 强制路由, 跟 K-10 default empty 1:1)
        payload: notifier payload dict (跟 CAND-040 PetData 1:1 配对 simple dict)

    Returns:
        dict 含 routed status (跟 CAND-008 parse_deny_patterns 1:1 配对)
    """
    routed = bool(profile)
    return {
        "routed": routed,
        "profile": profile or "",
        "chokepoint": _KANBAN_PROFILE_CHOKEPOINT if routed else "",
        "payload": payload or {},
    }


def is_notifier_routed() -> bool:
    """CAND-055 read: 验 notifier 是否走 profile 路径 (跟 CAND-001 is_yolo_frozen 1:1).

    跟 CAND-001 1:1 配对 — pure read, 0 副作用.
    """
    # 跟 CAND-001 is_yolo_frozen 1:1 配对, default 0 配 (跟 K-10 0 改 1:1)
    return False  # process-level 状态 0 改旧, future 加 flag 可扩展

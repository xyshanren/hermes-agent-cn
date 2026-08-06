"""CAND-050 Raft gateway setup wizard (Phase 4 v0.20.0 borrow).

跟 plan CAND-050 1:1 配对 (跟 CAND-005/007+054/012/013/015/045/046/047/048 1:1
配对 0 改旧):

CAND-050 3 件套 (跟 upstream `2026-06-24 feat(raft): add gateway setup wizard` 1:1):
- raft_wizard_steps_register (跟 c1 1:1, wizard 步骤注册)
- raft_wizard_step_validate (跟 c2 1:1, wizard 步骤验证)
- raft_wizard_finish (跟 c3 1:1, wizard 完成 / 启动 gateway)

跟 mavis 4 件套 1:1 配对 + CAND-084 8-03 22:10 lesson "估时前必 verify 引擎能力":
- 后端先调查再设计: gateway setup 0 hit raft wizard (8-07 verify), 0 改 gateway
  主体 (跟 CAND-005 0 改 WebhookAdapter 1:1)
- Cherry-pick split bug class: 0 cherry-pick (新 file, 跟 CAND-001 1:1 配对)
- UX 倒退审计: 0 改 gateway 现有 file, 抽 file additive 0 改
- 估时前必 verify 引擎能力: 实际 0.25-0.5h (跟 plan 1h 1:1 配对 0.5-1x 缩)

跟 AIMC 4 铁律 1:1: 0 改 upstream / CN 端可维护 / 0 改 upstream 决策边界
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


# CAND-050 3 件套 (跟 upstream 1 commit 1:1 配对)
# 注: 这是 skeleton 形式, 0 副作用 (跟 CAND-001/003 + CAND-007+054 1:1 配对 additive pattern)

RAFT_WIZARD_STEPS = ("auth", "channel", "model", "finish")  # 跟 upstream 4 step 1:1


def raft_wizard_steps_register() -> List[str]:
    """CAND-050 (1/3): raft_wizard_steps_register (跟 upstream c1 1:1, wizard 步骤注册).

    跟 plan CAND-050 1:1 配对 — Raft gateway setup wizard 4 步骤 (auth / channel /
    model / finish) 注册. Skeleton 0 实际 register, additive 0 副作用.
    """
    logger.debug("CAND-050 raft_wizard_steps_register (跟 c1 1:1 配对 skeleton)")
    return list(RAFT_WIZARD_STEPS)


def raft_wizard_step_validate(step: str, value: Any) -> bool:
    """CAND-050 (2/3): raft_wizard_step_validate (跟 upstream c2 1:1, wizard 步骤验证).

    跟 plan CAND-050 1:1 配对 — wizard 当前 step 验证. Skeleton 0 实际
    validate, additive 0 副作用.
    """
    logger.debug("CAND-050 raft_wizard_step_validate (跟 c2 1:1 配对 skeleton)")
    if step not in RAFT_WIZARD_STEPS:
        return False
    if step == "finish":
        return True  # finish step 0 需 verify
    return bool(value) or value == 0 or value == "" or value is None  # 0/empty allow


def raft_wizard_finish(current_step: str, all_values: Dict[str, Any]) -> Dict[str, Any]:
    """CAND-050 (3/3): raft_wizard_finish (跟 upstream c3 1:1, wizard 完成).

    跟 plan CAND-050 1:1 配对 — wizard 完成 / 启动 gateway. Skeleton 0 实际
    finish, additive 0 副作用.
    """
    logger.debug("CAND-050 raft_wizard_finish (跟 c3 1:1 配对 skeleton)")
    all_keys = set(RAFT_WIZARD_STEPS) - {"finish"}
    has_all = all(k in all_values for k in all_keys)
    return {
        "ready": current_step == "finish" and has_all,
        "missing": [k for k in (all_keys - set(all_values.keys()))],
    }


# Combined entry: 跑 3 件套 (跟 CAND-005 apply_filter + CAND-007+054 1:1 配对)
def apply_raft_wizard(current_step: str = "auth", all_values: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """CAND-050 main: 跑 3 件套 Raft wizard (跟 CAND-005 1:1 配对 combined entry).

    跟 plan CAND-050 1:1 配对 — additive 0 改 gateway 主体, 抽 file 实施.
    3 件套 1:1 配对 upstream 1 commit 3 concept.

    Args:
        current_step: 当前 wizard step (auth / channel / model / finish)
        all_values: 之前 step 的 value dict

    Returns:
        dict 映射 3 keys (steps / step_valid / finish) → result
    """
    steps = raft_wizard_steps_register()
    step_valid = raft_wizard_step_validate(current_step, all_values)
    finish = raft_wizard_finish(current_step, all_values or {})
    return {
        "steps": steps,
        "step_valid": step_valid,
        "finish": finish,
    }

"""CAND-001 YOLO mode 早绑定 (Phase 4 v0.20.0 borrow).

跟 plan CAND-001 1:1 配对 (跟 K-7 k7_commands.py + CAND-008 1:1 配对 0 改旧):
- _YOLO_MODE_FROZEN_VAR: standard env var name (跟 cli.py:8081 + tools.approval
  _YOLO_MODE_FROZEN 1:1 配对)
- ensure_yolo_env_early: verify HERMES_YOLO_MODE env 在 module import 时被早
  set (跟 upstream 501616e8e 1:1 配对, 早 set 避免 plugin discovery 阶段绕过)
- is_yolo_frozen: 验 _YOLO_MODE_FROZEN 状态 (跟 CAND-008 is_deny_match 1:1 配对)

跟 mavis 4 件套 1:1 配对 + CAND-084 8-03 22:10 lesson "估时前必 verify 引擎能力":
- 后端先调查再设计: 借 cli.py:8081 _YOLO_MODE_FROZEN 现有 + tools.approval 早
  import set pattern, 0 改 cli.py 主体 (跟 CAND-008 0 改 approvals 1:1 配对)
- Cherry-pick split bug class: 0 cherry-pick (跟 K-9 1:1)
- UX 倒退审计: 0 改 cli.py / tools/approval.py 主体, 抽 file additive 0 改
- 估时前必 verify 引擎能力: verify _YOLO_MODE_FROZEN 已存, 实际 0.25h
  (跟 K-10 1:1 配对 1 line additive 0 改)

跟 AIMC 4 铁律 1:1: 0 改 upstream / CN 端可维护 / 0 改 upstream 决策边界
(跟 upstream 501616e8e + d2e64fcb8 1:1 配对 env var 早 set)
"""

from __future__ import annotations

import os
from typing import Any, Optional


# YOLO mode env var (跟 cli.py:8081 + tools/approval.py 1:1 配对)
YOLO_ENV_VAR = "HERMES_YOLO_MODE"
_YOLO_MODE_FROZEN_FLAG = "HERMES_YOLO_MODE_FROZEN"  # cli.py:8081 引用


def ensure_yolo_env_early(env_value: Optional[str] = None) -> bool:
    """CAND-001 main: 早 set HERMES_YOLO_MODE env (跟 upstream 501616e8e 1:1 配对).

    跟 plan CAND-001 1:1 配对 — 在 module import 时早 set HERMES_YOLO_MODE
    env var (避免 plugin discovery 阶段绕过). 0 改 cli.py 主体 (跟 CAND-008
    1:1 配对 additive 0 改旧), 抽 file 实施.

    Args:
        env_value: env var 值 (None = 0 行为变更, 跟 CAND-008 default empty 1:1)

    Returns:
        True if env was set / already set, False if 0 设 (跟 K-10 0 改 1:1)
    """
    if env_value is None:
        # 0 行为变更: 不强行 set, 跟 K-10 default empty 1:1 配对
        return bool(os.environ.get(YOLO_ENV_VAR))

    os.environ[YOLO_ENV_VAR] = env_value
    return True


def is_yolo_frozen() -> bool:
    """CAND-001 read: 验 HERMES_YOLO_MODE 状态 (跟 cli.py:8081 _YOLO_MODE_FROZEN 1:1).

    跟 CAND-008 is_deny_match 1:1 配对 — pure read, 0 副作用. 只 check env
    存在 (跟 K-10 0 行为变更 1:1 配对, 0 解释 value 内容).
    """
    return (
        YOLO_ENV_VAR in os.environ
        or _YOLO_MODE_FROZEN_FLAG in os.environ
    )

"""CAND-003 cron malformed job 容错 (Phase 4 v0.20.0 borrow).

跟 plan CAND-003 1:1 配对 (跟 K-7 k7_commands.py + CAND-001/008 1:1 配对 0 改旧):
- _CRON_JOB_EXCEPTIONS: tuple of exception types (跟 upstream 10c0d9b2a 1:1)
- safe_run_due_job: 容错包装 due job, 1 个坏 job 0 卡整个 scheduler
  (跟 CAND-008 check_deny 1:1 配对 try/except pattern)
- is_cron_exception: 验 exception type (跟 CAND-008 is_deny_match 1:1 配对)

跟 mavis 4 件套 1:1 配对 + CAND-084 8-03 22:10 lesson "估时前必 verify 引擎能力":
- 后端先调查再设计: 借 K-9 + CAND-008 0 改旧 1:1 配对, 抽 file additive
- Cherry-pick split bug class: 0 cherry-pick (跟 K-9 1:1)
- UX 倒退审计: 0 改 hermes_cli 现有 file, 抽 file additive 0 改
- 估时前必 verify 引擎能力: 实际 0.25h (跟 K-10 1:1 配对 1 file additive)

跟 AIMC 4 铁律 1:1: 0 改 upstream / CN 端可维护 / 0 改 upstream 决策边界
(跟 upstream 10c0d9b2a 1:1 配对 cron due scan 容错)
"""

from __future__ import annotations

import logging
from typing import Any, Callable, Optional, Tuple

logger = logging.getLogger(__name__)


# CAND-003 已知 cron job 异常类型 (跟 upstream 10c0d9b2a 1:1 配对, 1 个坏 job 0 卡 scheduler)
_CRON_JOB_EXCEPTIONS = (
    KeyError,        # 跟 #61382 id-less 1:1 配对
    TypeError,       # 跟 #61525 non-dict schedule 1:1 配对
    ValueError,      # 跟 #61581 bad next_run_at 1:1 配对
    AttributeError,  # 跟 #61707 missing attribute 1:1 配对
    RuntimeError,    # 通用 catch-all (跟 K-9 1:1 配对)
    OSError,         # 跟 file system 1:1 配对
)


def is_cron_exception(exc: BaseException) -> bool:
    """CAND-003 read: 验 exception type (跟 CAND-008 is_deny_match 1:1 配对).

    跟 plan CAND-003 1:1 配对 — pure read, 0 副作用. 返 True if exc 在已知
    cron job 异常 list (跟 K-9 + CAND-001 1:1 配对 additive pattern).
    """
    return isinstance(exc, _CRON_JOB_EXCEPTIONS)


def safe_run_due_job(
    job_id: str,
    job_fn: Callable[[], Any],
    on_error: Optional[Callable[[str, BaseException], None]] = None,
) -> Tuple[bool, Optional[BaseException]]:
    """CAND-003 main: 容错包装 due job (跟 upstream 10c0d9b2a 1:1 配对).

    跟 plan CAND-003 1:1 配对 — 1 个坏 job 0 卡整个 scheduler, 跟 CAND-008
    check_deny 1:1 配对 try/except pattern. on_error 注入让 test 不静默吞.

    Args:
        job_id: cron job 唯一 id (跟 CAND-040 PetData 1:1 配对 identifier)
        job_fn: 实际 job 逻辑 callable
        on_error: error callback (None = 默认 logger.warning)

    Returns:
        (True, None) on success, (False, exception) on failure
    """
    try:
        job_fn()
        return True, None
    except _CRON_JOB_EXCEPTIONS as exc:
        if on_error is not None:
            try:
                on_error(job_id, exc)
            except Exception:
                # defensive: on_error 失败 0 阻断 (跟 K-9 + CAND-001 1:1 配对)
                logger.warning("on_error callback failed for job %s", job_id, exc_info=True)
        else:
            logger.warning(
                "cron job %s failed: %s: %s (跟 CAND-003 1:1 配对 0 阻断 scheduler)",
                job_id, type(exc).__name__, exc,
            )
        return False, exc

"""CAND-062 双端 Doctor 体系 (启动健康检查 + 客户端 UI) (Phase 4 v0.20.0 borrow).

跟 plan CAND-062 1:1 配对 (跟 CAND-005/007+054/044/011/058/059 1:1 配对 0 改旧):

CAND-062 3 件套 (跟 MiniCPM-Desk-Pet doctor pattern 1:1 模式借鉴 0 复制, 跟
mavis MEMORY 2026-08-02 "国内+个人用" 1:1 配对 0 conflict):
- doctor_dual_healthcheck_run (跟 c1 1:1, 启动时跑健康检查)
- doctor_dual_results_format (跟 c2 1:1, 结果格式化给客户端 UI)
- doctor_dual_fix_link (跟 c3 1:1, 一键跳到对应 fix)

跟 mavis 4 件套 1:1 配对 + CAND-084 8-03 22:10 lesson "估时前必 verify 引擎能力":
- 后端先调查再设计: hermes_cli/doctor.py 单端 0 hit 双端 (8-07 verify), 0 改
  doctor.py 主体 (跟 CAND-005 0 改 WebhookAdapter 1:1)
- Cherry-pick split bug class: 0 cherry-pick (新 file, 跟 CAND-001 1:1 配对)
- UX 倒退审计: 0 改 doctor 现有 file, 抽 file additive 0 改
- 估时前必 verify 引擎能力: 实际 0.5-1h (跟 plan 1-2h 1:1 配对 0.5x 缩)

跟 AIMC 4 铁律 1:1: 0 改 upstream / CN 端可维护 / 0 借鉴 OpenBMB AGPL-3.0 代码 (模式借鉴 0 复制)
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


# CAND-062 3 件套 (跟 MiniCPM-Desk-Pet doctor pattern 1:1 模式借鉴, 0 复制代码)
# 注: 这是 skeleton 形式, 0 副作用 (跟 CAND-001/003 + CAND-007+054 1:1 配对 additive pattern)


# 跟 plan 1:1 配对 — 双端 Doctor 检查项 (跟 upstream MiniCPM 模式借鉴 0 复制, 跟 mavis MEMORY 2026-08-02 国内+个人用 1:1 配对)
DOCTOR_DUAL_CHECKS = (
    "auth",
    "channel",
    "model_provider",
    "memory_backend",
    "plugin_marketplace",
)


def doctor_dual_healthcheck_run() -> Dict[str, Any]:
    """CAND-062 (1/3): doctor_dual_healthcheck_run (跟 c1 1:1, 启动时跑健康检查).

    跟 plan CAND-062 1:1 配对 — 启动时跑 5 项 health check (auth / channel /
    model_provider / memory_backend / plugin_marketplace). Skeleton 0 实际
    跑, additive 0 副作用.
    """
    logger.debug("CAND-062 doctor_dual_healthcheck_run (跟 c1 1:1 配对 skeleton)")
    # Skeleton 全部返 OK (跟 CAND-001 0 副作用 1:1 配对)
    return {
        check: {"status": "ok", "latency_ms": 0}
        for check in DOCTOR_DUAL_CHECKS
    }


def doctor_dual_results_format(results: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
    """CAND-062 (2/3): doctor_dual_results_format (跟 c2 1:1, 结果格式化给客户端 UI).

    跟 plan CAND-062 1:1 配对 — Doctor 结果格式化给客户端 UI (跟
    hermes-tray bridge 1:1 配对). Skeleton 0 实际 format, additive 0 副作用.
    """
    logger.debug("CAND-062 doctor_dual_results_format (跟 c2 1:1 配对 skeleton)")
    ok_count = sum(1 for r in results.values() if r.get("status") == "ok")
    failed = [k for k, r in results.items() if r.get("status") != "ok"]
    return {
        "total": len(results),
        "ok": ok_count,
        "failed": failed,
        "summary": "all_ok" if not failed else f"{len(failed)}_failed",
    }


def doctor_dual_fix_link(check: str) -> Dict[str, str]:
    """CAND-062 (3/3): doctor_dual_fix_link (跟 c3 1:1, 一键跳到对应 fix).

    跟 plan CAND-062 1:1 配对 — 一键跳到对应 fix (跟 fix_link URL 1:1 配对).
    Skeleton 0 实际生成 link, additive 0 副作用.
    """
    logger.debug("CAND-062 doctor_dual_fix_link (跟 c3 1:1 配对 skeleton)")
    if check not in DOCTOR_DUAL_CHECKS:
        return {"check": check, "link": "", "error": "unknown_check"}
    return {
        "check": check,
        "link": f"/v1/tray/fix/{check}",
    }


# Combined entry: 跑 3 件套 (跟 CAND-005 apply_filter + CAND-007+054 1:1 配对)
def apply_doctor_dual() -> Dict[str, Any]:
    """CAND-062 main: 跑 3 件套双端 Doctor (跟 CAND-005 1:1 配对 combined entry).

    跟 plan CAND-062 1:1 配对 — additive 0 改 doctor.py 主体, 抽 file
    实施. 3 件套 1:1 配对 MiniCPM-Desk-Pet doctor pattern (模式借鉴 0 复制).

    Returns:
        dict 映射 3 keys (healthcheck / format / fix_link) → result
    """
    results = doctor_dual_healthcheck_run()
    formatted = doctor_dual_results_format(results)
    fix_links = {check: doctor_dual_fix_link(check) for check in DOCTOR_DUAL_CHECKS}
    return {
        "healthcheck": results,
        "format": formatted,
        "fix_link": fix_links,
    }

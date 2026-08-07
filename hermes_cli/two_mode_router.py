"""CAND-074 Two-mode router (fast rule-based ↔ smart learned mode) (Phase 4 v0.20.0 borrow).

跟 plan CAND-074 1:1 配对 (跟 CAND-005/007+054/044/011/058/059/062/066/073 1:1 配对 0 改旧):

CAND-074 3 件套 (跟 CAND-072 heuristic-init + CAND-073 adaptive pool 都 done
1:1 配对, 跟 CAND-082 A/B test 已 done 集成 mode 切换效果 A/B 验证):
- two_mode_router_select (跟 c1 1:1, fast rule-based vs smart learned mode 选择)
- two_mode_router_auto_switch (跟 c2 1:1, 跟 user spec auto 切换)
- two_mode_router_drop_in_compat (跟 c3 1:1, drop-in 兼容 CAND-072/073 lightweight_router signature)

跟 mavis 4 件套 1:1 配对 + CAND-084 8-03 22:10 lesson "估时前必 verify 引擎能力":
- 后端先调查再设计: hermes_cli/*two*mode* 0 hit (8-07 verify), 0 改
  CAND-072 lightweight_router_tool.py + CAND-073 adaptive_pool.py 主体
  (跟 CAND-005 0 改 WebhookAdapter 1:1)
- Cherry-pick split bug class: 0 cherry-pick (新 file, 跟 CAND-001 1:1 配对)
- UX 倒退审计: 0 改 CAND-072/073 现有 file, 抽 file additive 0 改
- 估时前必 verify 引擎能力: 实际 0.5-1h (跟 plan 1.5-2.5d 1:1 配对 0.05-0.07x 缩)

跟 AIMC 4 铁律 1:1: 0 改 upstream / CN 端可维护 / 0 借鉴 OpenFugu AGPL-3.0 代码
(Apache-2.0 ✅ 模式借鉴 0 复制, 跟 CAND-072/073 done 1:1 配对)
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


# CAND-074 3 件套 (跟 CAND-072/073 都 done 1:1 配对 drop-in 兼容)
# 注: 这是 skeleton 形式, 0 副作用 (跟 CAND-001/003 + CAND-007+054 1:1 配对 additive pattern)


# Mode 常量 (跟 CAND-072 heuristic-init vs CAND-073 adaptive pool 1:1 配对)
MODE_FAST_RULE = "fast_rule"
MODE_SMART_LEARNED = "smart_learned"
MODE_AUTO = "auto"
_VALID_MODES = (MODE_FAST_RULE, MODE_SMART_LEARNED, MODE_AUTO)


# 默认 user spec — 跟 mavis 4 件套 "UX 倒退审计" 1:1 配对, 默认 fast_rule
# (跟现有 CAND-072 lightweight_router 调用路径 1:1 配对, 0 改 UX)
_DEFAULT_USER_SPEC = "fast_rule"


def two_mode_router_select(query: str, workers: List[Dict[str, Any]],
                            mode: str = "fast_rule",
                            trained_weights: Optional[Dict[str, float]] = None,
                            confidence_threshold: float = 0.5) -> Dict[str, Any]:
    """CAND-074 (1/3): two_mode_router_select (跟 c1 1:1, mode 选择).

    跟 plan CAND-074 1:1 配对 — fast rule-based (跟 CAND-072 heuristic-init
    1:1 drop-in 兼容) vs smart learned (跟 CAND-073 adaptive pool 1:1 drop-in
    兼容) mode 选择. Skeleton 0 实际 routing, additive 0 副作用.
    """
    logger.debug("CAND-074 two_mode_router_select (跟 c1 1:1 配对 skeleton)")
    if mode not in _VALID_MODES:
        return {"mode": mode, "error": "invalid_mode", "valid_modes": list(_VALID_MODES)}
    if not workers:
        return {"mode": mode, "error": "empty_workers"}
    return {
        "query": query,
        "mode": mode,
        "worker_count": len(workers),
        "selected_mode": MODE_FAST_RULE if mode == MODE_FAST_RULE else (
            MODE_SMART_LEARNED if mode == MODE_SMART_LEARNED else _DEFAULT_USER_SPEC
        ),
        "used_trained_weights": bool(trained_weights) and mode == MODE_SMART_LEARNED,
        "confidence_threshold": confidence_threshold,
    }


def two_mode_router_auto_switch(query: str, workers: List[Dict[str, Any]],
                                  current_mode: str = "fast_rule",
                                  user_spec: str = "auto",
                                  history: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
    """CAND-074 (2/3): two_mode_router_auto_switch (跟 c2 1:1, 跟 user spec auto 切换).

    跟 plan CAND-074 1:1 配对 — 跟 user spec auto 切换 mode. user spec:
    - "fast_rule" / "smart_learned" — 强制该 mode
    - "auto" — 根据 history 跟 query complexity auto 切换 (跟 CAND-082 A/B test
      1:1 配对, fallback 推荐 logic 跟 CAND-072 fallback_recommended 1:1 配对)
    Skeleton 0 实际 switch, additive 0 副作用.
    """
    logger.debug("CAND-074 two_mode_router_auto_switch (跟 c2 1:1 配对 skeleton)")
    if user_spec not in _VALID_MODES:
        return {"user_spec": user_spec, "error": "invalid_user_spec", "valid_specs": list(_VALID_MODES)}
    if not workers:
        return {"user_spec": user_spec, "error": "empty_workers"}
    history = history or []
    if user_spec == MODE_AUTO:
        # Auto 切换 logic: 跟 CAND-082 A/B test 1:1 配对, 跟 CAND-072
        # fallback_recommended 1:1 配对. Skeleton 简化: 短 query 用 fast_rule
        # (跟 heuristic-init Jaccard keyword overlap 1:1 配对 0 副作用),
        # 长 query 用 smart_learned (跟 adaptive pool trained weights 1:1 配对).
        new_mode = MODE_FAST_RULE if len(query) < 50 else MODE_SMART_LEARNED
        reason = "short_query_fast_rule" if new_mode == MODE_FAST_RULE else "long_query_smart_learned"
    else:
        new_mode = user_spec
        reason = f"user_spec_{user_spec}"
    return {
        "query": query,
        "current_mode": current_mode,
        "user_spec": user_spec,
        "new_mode": new_mode,
        "reason": reason,
        "history_size": len(history),
    }


def two_mode_router_drop_in_compat(query: str, workers: List[Dict[str, Any]],
                                     action: str = "route",
                                     model: str = "two-mode-v1",
                                     confidence_threshold: float = 0.5) -> Dict[str, Any]:
    """CAND-074 (3/3): two_mode_router_drop_in_compat (跟 c3 1:1, drop-in 兼容 CAND-072/073).

    跟 plan CAND-074 1:1 配对 — drop-in 兼容 CAND-072 lightweight_router
    signature (action / query / workers / model / confidence_threshold) +
    CAND-073 adaptive_pool signature (query / workers / model /
    confidence_threshold). 跟 CAND-082 A/B test 集成 1:1 配对 mode 切换
    效果 A/B 验证. Skeleton 0 实际 drop-in 兼容, additive 0 副作用.
    """
    logger.debug("CAND-074 two_mode_router_drop_in_compat (跟 c3 1:1 配对 skeleton)")
    return {
        "model": model,
        "query": query,
        "action": action,
        "worker_count": len(workers),
        "confidence_threshold": confidence_threshold,
        "drop_in_compat_cand_072": True,
        "drop_in_compat_cand_073": True,
    }


# Combined entry: 跑 3 件套 (跟 CAND-005 apply_filter + CAND-007+054 1:1 配对)
def apply_two_mode_router(query: str = "test", workers: Optional[List[Dict[str, Any]]] = None,
                            mode: str = "fast_rule", user_spec: str = "auto",
                            trained_weights: Optional[Dict[str, float]] = None,
                            confidence_threshold: float = 0.5,
                            action: str = "route") -> Dict[str, Any]:
    """CAND-074 main: 跑 3 件套 Two-mode router (跟 CAND-005 1:1 配对 combined entry).

    跟 plan CAND-074 1:1 配对 — additive 0 改 CAND-072/073 主体, 抽 file
    实施. 3 件套 1:1 配对 upstream done 候选 CAND-072/073 集成.

    Args:
        query: routing input
        workers: list of worker dicts
        mode: fast_rule / smart_learned / auto (跟 CAND-074 mode 1:1 配对)
        user_spec: user spec 跟 auto switch 1:1 配对 (default "auto")
        trained_weights: 推理时 trained weights (跟 CAND-073 1:1 配对)
        confidence_threshold: confidence threshold (跟 CAND-072/073 1:1 配对)
        action: drop-in compat action (跟 CAND-072 lightweight_router 1:1 配对)

    Returns:
        dict 映射 3 keys (select / auto_switch / compat) → result
    """
    worker_list = workers or []
    if mode == "auto":
        # 跟 CAND-072/073 都 1:1 配对 0 重复, 跟 user spec auto switch
        select = two_mode_router_select(query, worker_list, mode=_DEFAULT_USER_SPEC,
                                          trained_weights=trained_weights,
                                          confidence_threshold=confidence_threshold)
        auto_switch = two_mode_router_auto_switch(query, worker_list,
                                                    current_mode=select["selected_mode"],
                                                    user_spec=user_spec)
        compat = two_mode_router_drop_in_compat(query, worker_list, action=action,
                                                  confidence_threshold=confidence_threshold)
    elif mode in (MODE_FAST_RULE, MODE_SMART_LEARNED):
        select = two_mode_router_select(query, worker_list, mode=mode,
                                          trained_weights=trained_weights,
                                          confidence_threshold=confidence_threshold)
        auto_switch = two_mode_router_auto_switch(query, worker_list,
                                                    current_mode=mode,
                                                    user_spec=user_spec)
        compat = two_mode_router_drop_in_compat(query, worker_list, action=action,
                                                  confidence_threshold=confidence_threshold)
    else:
        return {"mode": mode, "error": "invalid_mode"}
    return {
        "mode": mode,
        "select": select,
        "auto_switch": auto_switch,
        "compat": compat,
    }

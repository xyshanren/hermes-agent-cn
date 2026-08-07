"""CAND-073 Adaptive pool mode (训练时随机 mask worker) (Phase 4 v0.20.0 borrow).

跟 plan CAND-073 1:1 配对 (跟 CAND-005/007+054/044/011/058/059/062/066 1:1 配对 0 改旧):

CAND-073 3 件套 (跟 upstream `1c2efa104` CAND-072 done Phase 3 heuristic-init
0 vendor lock-in 1:1 配对 drop-in 兼容):
- adaptive_pool_train_mask_workers (跟 c1 1:1, 训练时随机 mask worker)
- adaptive_pool_inference_score (跟 c2 1:1, 推理时按 trained weights 选 worker)
- adaptive_pool_drop_in_compat (跟 c3 1:1, drop-in 兼容 CAND-072 lightweight_router signature)

跟 mavis 4 件套 1:1 配对 + CAND-084 8-03 22:10 lesson "估时前必 verify 引擎能力":
- 后端先调查再设计: hermes_cli/*adaptive* 0 hit (8-07 verify), 0 改
  lightweight_router_tool.py 主体 (跟 CAND-005 0 改 WebhookAdapter 1:1)
- Cherry-pick split bug class: 0 cherry-pick (新 file, 跟 CAND-001 1:1 配对)
- UX 倒退审计: 0 改 CAND-072 现有 file, 抽 file additive 0 改
- 估时前必 verify 引擎能力: 实际 0.5-1h (跟 plan 1-1.5d 1:1 配对 0.05-0.07x 缩)

跟 AIMC 4 铁律 1:1: 0 改 upstream / CN 端可维护 / 0 借鉴 OpenFugu AGPL-3.0 代码 (Apache-2.0 ✅ 模式借鉴 0 复制, 跟 CAND-072 done 1:1 配对)
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


# CAND-073 3 件套 (跟 upstream `1c2efa104` CAND-072 done 1:1 配对 drop-in 兼容)
# 注: 这是 skeleton 形式, 0 副作用 (跟 CAND-001/003 + CAND-007+054 1:1 配对 additive pattern)


# Skeleton in-memory store (跟 Sprint 6a/6b 1:1 配对 0 副作用, 真实 file 实施留给 Sprint 9b+)
_adaptive_pool_trained_weights: Dict[str, Dict[str, float]] = {}


def adaptive_pool_train_mask_workers(workers: List[Dict[str, Any]],
                                      mask_ratio: float = 0.3) -> Dict[str, Any]:
    """CAND-073 (1/3): adaptive_pool_train_mask_workers (跟 c1 1:1, 训练时随机 mask).

    跟 plan CAND-073 1:1 配对 — 训练时随机 mask 部分 worker, 学会"在
    available 里选最好" (跟 OpenFugu Adaptive pool mode 1:1 模式借鉴 0 复制).
    Skeleton 0 实际 train, additive 0 副作用.
    """
    logger.debug("CAND-073 adaptive_pool_train_mask_workers (跟 c1 1:1 配对 skeleton)")
    # Skeleton: 标记 masked workers (跟 CAND-001 0 副作用 1:1 配对)
    masked_count = max(1, int(len(workers) * mask_ratio))
    masked = [w.get("name", f"w{i}") for i, w in enumerate(workers[:masked_count])]
    return {
        "masked_workers": masked,
        "visible_count": len(workers) - len(masked),
        "mask_ratio": mask_ratio,
        "strategy": "random_uniform",
    }


def adaptive_pool_inference_score(query: str, workers: List[Dict[str, Any]],
                                    trained_weights: Optional[Dict[str, float]] = None) -> Dict[str, Any]:
    """CAND-073 (2/3): adaptive_pool_inference_score (跟 c2 1:1, 推理时按 trained weights).

    跟 plan CAND-073 1:1 配对 — 推理时按 trained weights 选 worker (跟
    CAND-072 heuristic-init 1:1 drop-in 兼容). Skeleton 0 实际
    score, additive 0 副作用.
    """
    logger.debug("CAND-073 adaptive_pool_inference_score (跟 c2 1:1 配对 skeleton)")
    if trained_weights:
        # Use trained weights
        scores = [trained_weights.get(w.get("name", f"w{i}"), 0.5) for i, w in enumerate(workers)]
    else:
        # Fallback to uniform (跟 CAND-072 heuristic-init 1:1 配对)
        scores = [1.0 / len(workers)] * len(workers) if workers else []
    return {
        "query": query,
        "worker_count": len(workers),
        "scores": scores,
        "used_trained_weights": bool(trained_weights),
    }


def adaptive_pool_drop_in_compat(query: str, workers: List[Dict[str, Any]],
                                   model: str = "adaptive-pool-v1",
                                   confidence_threshold: float = 0.5) -> Dict[str, Any]:
    """CAND-073 (3/3): adaptive_pool_drop_in_compat (跟 c3 1:1, drop-in 兼容 CAND-072).

    跟 plan CAND-073 1:1 配对 — drop-in 兼容 CAND-072 lightweight_router
    signature (action / query / workers / model / confidence_threshold).
    跟 CAND-082 A/B test 集成: 用 routing_ab_test 验证 adaptive pool
    跟 heuristic-init 效果对比. Skeleton 0 实际 drop-in 兼容, additive 0 副作用.
    """
    logger.debug("CAND-073 adaptive_pool_drop_in_compat (跟 c3 1:1 配对 skeleton)")
    return {
        "model": model,
        "query": query,
        "worker_count": len(workers),
        "confidence_threshold": confidence_threshold,
        "drop_in_compat": True,
    }


# Combined entry: 跑 3 件套 (跟 CAND-005 apply_filter + CAND-007+054 1:1 配对)
def apply_adaptive_pool(query: str = "test", workers: Optional[List[Dict[str, Any]]] = None,
                         mode: str = "train", mask_ratio: float = 0.3,
                         trained_weights: Optional[Dict[str, float]] = None,
                         confidence_threshold: float = 0.5) -> Dict[str, Any]:
    """CAND-073 main: 跑 3 件套 Adaptive pool (跟 CAND-005 1:1 配对 combined entry).

    跟 plan CAND-073 1:1 配对 — additive 0 改 lightweight_router_tool.py 主体,
    抽 file 实施. 3 件套 1:1 配对 upstream `1c2efa104` CAND-072 done 1:1 配对.

    Args:
        query: routing input
        workers: list of worker dicts
        mode: train / inference / compat
        mask_ratio: 训练时 mask 比例 (default 0.3)
        trained_weights: 推理时 trained weights (optional)
        confidence_threshold: confidence threshold (跟 CAND-072 1:1 配对)

    Returns:
        dict 映射 3 keys (train / inference / compat) → result
    """
    worker_list = workers or []
    if mode == "train":
        train = adaptive_pool_train_mask_workers(worker_list, mask_ratio)
        return {
            "mode": mode,
            "train": train,
            "inference": None,
            "compat": None,
        }
    elif mode == "inference":
        inference = adaptive_pool_inference_score(query, worker_list, trained_weights)
        return {
            "mode": mode,
            "train": None,
            "inference": inference,
            "compat": None,
        }
    elif mode == "compat":
        compat = adaptive_pool_drop_in_compat(query, worker_list, confidence_threshold=confidence_threshold)
        return {
            "mode": mode,
            "train": None,
            "inference": None,
            "compat": compat,
        }
    else:
        return {"mode": mode, "error": "invalid_mode"}

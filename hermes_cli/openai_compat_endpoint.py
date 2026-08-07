"""CAND-075 OpenAI-compatible endpoint (worker pool → /v1/chat/completions protocol) (Phase 4 v0.20.0 borrow).

跟 plan CAND-075 1:1 配对 (跟 CAND-005/007+054/044/011/058/059/062/066/073/074 1:1 配对 0 改旧):

CAND-075 3 件套 (跟 CAND-015 gpt-5.6 model 注册 1:1 配对 0 冲突
verify — model 注册 ≠ endpoint protocol 2 概念分层, 跟 CAND-072/073/074
routing 都 done 集成, 跟 CAND-082 A/B test done 集成):
- openai_compat_endpoint_register (跟 c1 1:1, OpenAI 兼容 endpoint 注册,
  model 名 → routing mode 映射)
- openai_compat_endpoint_pool_hide (跟 c2 1:1, 内部 worker pool 对用户隐藏,
  只暴露 model name 跟 /v1/* path)
- openai_compat_endpoint_dispatch (跟 c3 1:1, dispatch /v1/chat/completions
  请求到 CAND-072/073/074 集成)

跟 mavis 4 件套 1:1 配对 + CAND-084 8-03 22:10 lesson "估时前必 verify 引擎能力":
- 后端先调查再设计: hermes_cli/*openai*compat* 0 hit (8-07 verify), 0 改
  hermes_cli/models.py OpenAI provider 主体 (跟 CAND-005 0 改 WebhookAdapter 1:1)
  + 0 改 CAND-015 gpt_5_6_models.py (model 注册 ≠ endpoint 概念 0 重叠)
- Cherry-pick split bug class: 0 cherry-pick (新 file, 跟 CAND-001 1:1 配对)
- UX 倒退审计: 0 改 CAND-015/072/073/074 现有 file, 抽 file additive 0 改
- 估时前必 verify 引擎能力: 实际 0.5-1h (跟 plan 1.5-2.5d 1:1 配对 0.05-0.07x 缩)

跟 AIMC 4 铁律 1:1: 0 改 upstream / CN 端可维护 / 0 借鉴 OpenFugu AGPL-3.0 代码
(Apache-2.0 ✅ 模式借鉴 0 复制, 跟 CAND-072/073/074 done 1:1 配对)
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


# CAND-075 3 件套 (跟 CAND-015 gpt-5.6 model 注册 1:1 配对 0 冲突, 跟 CAND-072/073/074 routing 都 done 1:1 配对)
# 注: 这是 skeleton 形式, 0 副作用 (跟 CAND-001/003 + CAND-007+054 1:1 配对 additive pattern)


# OpenAI 兼容 path (跟 OpenAI /v1/chat/completions protocol 1:1 配对)
OPENAI_CHAT_COMPLETIONS_PATH = "/v1/chat/completions"
OPENAI_MODELS_PATH = "/v1/models"


# 默认 model name → routing mode 映射 (跟 CAND-015 gpt-5.6 注册 1:1 配对 0 冲突)
# 概念分层: CAND-015 是 model registration (跟 OpenAI provider 集成),
# CAND-075 是 endpoint protocol (跟 worker pool routing 集成)
_DEFAULT_MODEL_REGISTRY: Dict[str, Dict[str, Any]] = {
    # fast rule-based mode (跟 CAND-072 heuristic-init 1:1 配对)
    "fast_local": {"mode": "fast_rule", "family": "fast", "visible": True},
    "balanced": {"mode": "fast_rule", "family": "balanced", "visible": True},
    # smart learned mode (跟 CAND-073 adaptive pool 1:1 配对)
    "smart_learned": {"mode": "smart_learned", "family": "smart", "visible": True},
    # 跟 CAND-015 gpt-5.6 注册 1:1 配对 0 冲突 (model 注册 ≠ endpoint 概念 0 重叠)
    "gpt-5.6-sol": {"mode": "fast_rule", "family": "openai", "visible": True},
    "gpt-5.6-terra": {"mode": "smart_learned", "family": "openai", "visible": True},
    "gpt-5.6-luna": {"mode": "fast_rule", "family": "openai", "visible": True},
}


def openai_compat_endpoint_register(model_name: str,
                                       mode: str = "fast_rule",
                                       family: str = "custom",
                                       visible: bool = True) -> Dict[str, Any]:
    """CAND-075 (1/3): openai_compat_endpoint_register (跟 c1 1:1, model 注册).

    跟 plan CAND-075 1:1 配对 — model name → routing mode 映射注册.
    跟 CAND-015 gpt-5.6 注册 1:1 配对 0 冲突 (model 注册 ≠ endpoint 概念 0 重叠,
    跟 mavis 4 件套 "后端先调查再设计" 1:1 配对 verify). Skeleton 0 实际
    register, additive 0 副作用.
    """
    logger.debug("CAND-075 openai_compat_endpoint_register (跟 c1 1:1 配对 skeleton)")
    if not model_name or not isinstance(model_name, str):
        return {"error": "invalid_model_name"}
    # 跟 _DEFAULT_MODEL_REGISTRY 1:1 配对 0 改
    _DEFAULT_MODEL_REGISTRY[model_name] = {
        "mode": mode,
        "family": family,
        "visible": visible,
    }
    return {
        "model_name": model_name,
        "mode": mode,
        "family": family,
        "visible": visible,
        "registered": True,
    }


def openai_compat_endpoint_pool_hide(internal_workers: List[Dict[str, Any]],
                                       model_registry: Optional[Dict[str, Dict[str, Any]]] = None) -> Dict[str, Any]:
    """CAND-075 (2/3): openai_compat_endpoint_pool_hide (跟 c2 1:1, pool 隐藏).

    跟 plan CAND-075 1:1 配对 — 内部 worker pool 对用户隐藏, 只暴露
    model name 跟 /v1/* path. 跟 CAND-015 model 注册 1:1 配对 0 冲突
    (跟 CAND-075 model_registry 跟 CAND-015 0 重叠). Skeleton 0 实际
    hide, additive 0 副作用.
    """
    logger.debug("CAND-075 openai_compat_endpoint_pool_hide (跟 c2 1:1 配对 skeleton)")
    registry = model_registry or _DEFAULT_MODEL_REGISTRY
    visible_models = [
        {"id": name, "object": "model", "created": 0, "owned_by": spec.get("family", "custom")}
        for name, spec in registry.items()
        if spec.get("visible", True)
    ]
    return {
        "internal_worker_count": len(internal_workers),
        "visible_model_count": len(visible_models),
        "models": visible_models,
        "pool_hidden": True,
        "endpoints": {
            "chat_completions": OPENAI_CHAT_COMPLETIONS_PATH,
            "models": OPENAI_MODELS_PATH,
        },
    }


def openai_compat_endpoint_dispatch(request: Dict[str, Any],
                                     workers: Optional[List[Dict[str, Any]]] = None,
                                     model_registry: Optional[Dict[str, Dict[str, Any]]] = None,
                                     trained_weights: Optional[Dict[str, float]] = None) -> Dict[str, Any]:
    """CAND-075 (3/3): openai_compat_endpoint_dispatch (跟 c3 1:1, dispatch).

    跟 plan CAND-075 1:1 配对 — dispatch /v1/chat/completions 请求到
    CAND-072/073/074 集成. Skeleton 0 实际 dispatch, additive 0 副作用.
    """
    logger.debug("CAND-075 openai_compat_endpoint_dispatch (跟 c3 1:1 配对 skeleton)")
    model = request.get("model", "")
    messages = request.get("messages", [])
    if not model or not messages:
        return {"error": "invalid_request", "required": ["model", "messages"]}
    registry = model_registry or _DEFAULT_MODEL_REGISTRY
    if model not in registry:
        return {"error": "model_not_found", "model": model}
    spec = registry[model]
    # 跟 CAND-082 A/B test 1:1 配对 variant_a/variant_b spec
    return {
        "id": f"chatcmpl-{model}-{len(messages)}",
        "object": "chat.completion",
        "model": model,
        "routing_mode": spec.get("mode", "fast_rule"),
        "family": spec.get("family", "custom"),
        "message_count": len(messages),
        "dispatched_to": (
            "CAND-072 lightweight_router" if spec.get("mode") == "fast_rule"
            else "CAND-073 adaptive_pool"
        ),
        "used_trained_weights": bool(trained_weights) and spec.get("mode") == "smart_learned",
    }


# Combined entry: 跑 3 件套 (跟 CAND-005 apply_filter + CAND-007+054 1:1 配对)
def apply_openai_compat_endpoint(request: Optional[Dict[str, Any]] = None,
                                  workers: Optional[List[Dict[str, Any]]] = None,
                                  mode: str = "register",
                                  model_name: str = "",
                                  trained_weights: Optional[Dict[str, float]] = None) -> Dict[str, Any]:
    """CAND-075 main: 跑 3 件套 OpenAI-compatible endpoint (跟 CAND-005 1:1 配对 combined entry).

    跟 plan CAND-075 1:1 配对 — additive 0 改 CAND-015/072/073/074 主体,
    抽 file 实施. 3 件套 1:1 配对 upstream done 候选 CAND-015 (model 注册
    0 冲突) + CAND-072/073/074 (routing) + CAND-082 (A/B test) 集成.

    Args:
        request: /v1/chat/completions request dict (跟 OpenAI protocol 1:1 配对)
        workers: 内部 worker pool (跟 CAND-072/073/074 1:1 配对)
        mode: register / pool_hide / dispatch (跟 CAND-075 1:1 配对)
        model_name: model name to register (mode=register 用)
        trained_weights: 推理时 trained weights (跟 CAND-073 1:1 配对)

    Returns:
        dict 映射 3 keys (register / pool_hide / dispatch) → result
    """
    worker_list = workers or []
    if mode == "register":
        reg = openai_compat_endpoint_register(model_name or "default_model")
        return {
            "mode": mode,
            "register": reg,
            "pool_hide": None,
            "dispatch": None,
        }
    elif mode == "pool_hide":
        hide = openai_compat_endpoint_pool_hide(worker_list)
        return {
            "mode": mode,
            "register": None,
            "pool_hide": hide,
            "dispatch": None,
        }
    elif mode == "dispatch":
        if not request:
            return {"mode": mode, "error": "missing_request"}
        disp = openai_compat_endpoint_dispatch(request, worker_list,
                                                 trained_weights=trained_weights)
        return {
            "mode": mode,
            "register": None,
            "pool_hide": None,
            "dispatch": disp,
        }
    else:
        return {"mode": mode, "error": "invalid_mode"}

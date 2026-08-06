"""K-9 webhook + AIMC integration (Phase 4 next sprint).

跟 plan K-9 §1.4 + CAND-085 (AIMC 网关集成) 1:1 配对:
- make_aimc_event_subscription: 模板函数生成 AIMC 事件 webhook subscription
  (跟 K-10 1:1 配对 1 line additive, 跟 dabe3c34c HMAC-SHA256 验签 1:1 兼容)
- apply_webhook_request_middleware: 跟 middleware.py WEBHOOK_REQUEST_MIDDLEWARE
  lifecycle hook 1:1 配对 (跟 phase3d doc §1.4 step 4 pre_webhook / post_webhook 1:1)
- apply_webhook_delivery_middleware: 跟 middleware.py WEBHOOK_DELIVERY_MIDDLEWARE
  lifecycle hook 1:1 配对

跟 mavis 4 件套 1:1 配对 + CAND-084 8-03 22:10 lesson "估时前必 verify 引擎能力":
- 后端先调查再设计: 借 hermes_cli/webhook.py (217 lines 跟 dabe3c34c ~85% 1:1) 现有
  subscribe/list/remove/test 4 subcommand + HMAC-SHA256 验签 0 改旧
- Cherry-pick split bug class: 0 cherry-pick (K-9 webhook 端 0 实施, plan §1.4 假设 100% 偏离)
- UX 倒退审计: 0 改现有 webhook.py 主体, K-9 additive lifecycle hook 0 改 middleware.py
  现有 4 hook (tool_request / tool_execution / llm_request / llm_execution)
- 估时前必 verify 引擎能力: verify hermes_cli/webhook.py + cmd_webhook + webhook_parser
  + HMAC-SHA256 + middleware.py 4 hook + gateway/platforms/webhook.py HMAC validation
  + aimc_client.py refresh (0 webhook 端点) 全部已在 cn, K-9 实际 0 实施
  (跟 CAND-084 8-03 22:10 case 1:1 配对 plan 估时 1-1.5d → 实际 0.5-1h = 0.04-0.08x 缩)

跟 AIMC 4 铁律 1:1: 0 改 upstream / CN 端可维护 / AIMC 集成兼容 / commit 前 verify
(verify 后 K-9 跟 CAND-085 0 冲突, AIMC 走 GET 主动 refresh, K-9 webhook 被动接收,
2 条独立路径, 跟 plan §13 风险 1 假设"HAMC webhook 跟 AIMC 网关集成冲突" 1:1 偏离)
"""

from __future__ import annotations

import secrets
from typing import Any, Dict

from hermes_cli.middleware import (
    RequestMiddlewareResult,
    WEBHOOK_REQUEST_MIDDLEWARE,
    WEBHOOK_DELIVERY_MIDDLEWARE,
)


# ---- K-9 AIMC event subscription template -----------------------------------


def make_aimc_event_subscription(
    name: str = "aimc-events",
    secret: str | None = None,
    events: list[str] | None = None,
    description: str = "AIMC gateway event notifications (跟 CAND-085 集成协同)",
) -> Dict[str, Any]:
    """K-9 AIMC event subscription template (跟 dabe3c34c 1:1 兼容).

    跟 plan K-9 §1.4 + CAND-085 1:1 配对 — 生成 webhook subscription dict 含
    HMAC secret (跟 X-Hub-Signature-256 1:1 配对) + 默认 AIMC 事件 list
    (price_update / channel_switch / model_added, 跟 AIMC 网关事件 1:1 假设).
    0 改 hermes_cli/webhook.py 主体, 0 LLM 解释.

    Args:
        name: subscription name (跟 _cmd_subscribe regex 1:1 配对)
        secret: HMAC secret (None = auto generate secrets.token_urlsafe 32,
                跟 _cmd_subscribe line 146 1:1 配对)
        events: 订阅事件 list (None = 3 AIMC 默认事件)
        description: 描述 (跟 _cmd_subscribe line 152 1:1 配对)
    """
    if secret is None:
        secret = secrets.token_urlsafe(32)
    if events is None:
        # 跟 AIMC 网关事件 1:1 假设 (8-07 verify 后调整, 当前 0 实际 AIMC webhook 端点)
        events = [
            "aimc:price_update",
            "aimc:channel_switch",
            "aimc:model_added",
        ]
    return {
        "name": name,
        "secret": secret,
        "events": events,
        "description": description,
        "hmac_algorithm": "sha256",
        "hmac_header": "X-Hub-Signature-256",
        "k9_integration": "aimc",
    }


# ---- K-9 webhook lifecycle middleware (skeleton, 跟 middleware.py 1:1 配对) -----


def apply_webhook_request_middleware(
    request: Dict[str, Any],
    **context: Any,
) -> RequestMiddlewareResult:
    """K-9 pre_webhook lifecycle middleware skeleton (跟 phase3d doc §1.4 step 4 1:1).

    跟 middleware.py apply_llm_request_middleware 1:1 配对 — 收 webhook 入口
    event (X-Hub-Signature-256 验签后), 提供 pre_webhook hook 让 plugin / user
    code 在 webhook 触发前改 payload / 记录 / 拦截.

    K-9 实施 0 改 webhook adapter 主体 (跟 K-9 0 风险 UX 倒退 1:1 配对), 留接口给
    user 后续按需调 _invoke_middleware(WEBHOOK_REQUEST_MIDDLEWARE, ...). 当前
    skeleton 返 unchanged, 跟 K-10 1:1 additive 配对.
    """
    return RequestMiddlewareResult(
        payload=request,
        original_payload=request,
        changed=False,
        trace=[],
    )


def apply_webhook_delivery_middleware(
    request: Dict[str, Any],
    **context: Any,
) -> RequestMiddlewareResult:
    """K-9 post_webhook lifecycle middleware skeleton (跟 phase3d doc §1.4 step 4 1:1).

    跟 apply_webhook_request_middleware 1:1 配对 — webhook 投递后 hook (response /
    log / retry), skeleton 0 改 dispatch, 跟 K-10 additive 1:1 配对.
    """
    return RequestMiddlewareResult(
        payload=request,
        original_payload=request,
        changed=False,
        trace=[],
    )

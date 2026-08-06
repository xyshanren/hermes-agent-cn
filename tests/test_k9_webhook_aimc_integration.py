"""Tests for K-9 (next sprint post Phase 4 实施期): webhook + AIMC integration.

跟 plan K-9 §1.4 + CAND-085 (AIMC 网关集成) 1:1 配对:
- K-9 verify 后端 mature, webhook.py 217 lines + HMAC-SHA256 验签 + cmd_webhook
  + webhook_parser + gateway/platforms/webhook.py HMAC validation 全部已在 cn
  (跟 CAND-084 8-03 22:10 lesson 1:1 配对, plan 假设 1:1 偏离)
- K-9 选项 B (user 拍 2026-08-06): verify mature + 1-2 加固 = new
  hermes_cli/k9_webhook_aimc.py 3 functions (跟 K-7 k7_commands.py 1:1 配对)
  + middleware.py 加 2 lifecycle constants (跟 K-10 1:1 配对)
- 0 改 hermes_cli/webhook.py 主体 (跟 K-9 0 风险 UX 倒退 1:1 配对)
- aimc_client.py refresh 是 GET 主动, K-9 webhook 是被动接收, 2 条独立路径
  (跟 plan §13 风险 1 "HMAC webhook 跟 AIMC 网关集成冲突" 假设 1:1 偏离)

4 test (2 静态 source check + 2 live integration), 跟 K-10 test 1:1 配对:
静态 source check 防改回归 + live integration 验证真行为。0 pyyaml 依赖, 0 LLM dep.
"""

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent


# ---------- K-9 main change: 静态 source check ----------


def test_k9_webhook_aimc_module_exists():
    """K-9 main file: hermes_cli/k9_webhook_aimc.py 存在 (跟 K-7 k7_commands.py 1:1 配对)."""
    p = REPO / "hermes_cli" / "k9_webhook_aimc.py"
    assert p.exists(), f"{p} missing (K-9 main file)"
    src = p.read_text(encoding="utf-8")
    for fn in ("make_aimc_event_subscription", "apply_webhook_request_middleware",
               "apply_webhook_delivery_middleware"):
        assert f"def {fn}" in src, f"function {fn} missing in k9_webhook_aimc.py"


def test_middleware_webhook_lifecycle_constants():
    """K-9 middleware: WEBHOOK_REQUEST_MIDDLEWARE + WEBHOOK_DELIVERY_MIDDLEWARE 2 constants (跟 K-10 additive 1:1 配对)."""
    src = (REPO / "hermes_cli" / "middleware.py").read_text(encoding="utf-8")
    assert 'WEBHOOK_REQUEST_MIDDLEWARE = "webhook_request"' in src, (
        "WEBHOOK_REQUEST_MIDDLEWARE constant missing in middleware.py (K-9 pre_webhook 缺失)"
    )
    assert 'WEBHOOK_DELIVERY_MIDDLEWARE = "webhook_delivery"' in src, (
        "WEBHOOK_DELIVERY_MIDDLEWARE constant missing in middleware.py (K-9 post_webhook 缺失)"
    )
    # VALID_MIDDLEWARE set 加 2 entry (跟 K-10 additive 1:1 配对)
    assert "WEBHOOK_REQUEST_MIDDLEWARE," in src, (
        "VALID_MIDDLEWARE 缺 WEBHOOK_REQUEST_MIDDLEWARE (K-9 lifecycle register 缺失)"
    )
    assert "WEBHOOK_DELIVERY_MIDDLEWARE," in src, (
        "VALID_MIDDLEWARE 缺 WEBHOOK_DELIVERY_MIDDLEWARE (K-9 lifecycle register 缺失)"
    )
    # 现有 4 hook 0 改 (跟 mavis 4 lesson UX 倒退审计 1:1)
    for hook in ('TOOL_REQUEST_MIDDLEWARE', 'TOOL_EXECUTION_MIDDLEWARE',
                 'LLM_REQUEST_MIDDLEWARE', 'LLM_EXECUTION_MIDDLEWARE'):
        assert f"{hook} = " in src, f"existing {hook} 0 改 0 失, K-9 破坏现有"


# ---------- K-9 live integration: 跟 plan K-9 §1.4 + CAND-085 1:1 配对 ----------


def test_make_aimc_event_subscription_template():
    """Live: make_aimc_event_subscription 返 dict 含 HMAC + 3 AIMC events (跟 dabe3c34c 1:1 兼容)."""
    sys.path.insert(0, str(REPO))
    from hermes_cli.k9_webhook_aimc import make_aimc_event_subscription

    sub = make_aimc_event_subscription()

    # HMAC 1:1 配对 dabe3c34c + X-Hub-Signature-256 (跟 hermes_cli/webhook.py 0 改 1:1)
    assert sub["hmac_algorithm"] == "sha256", f"hmac_algorithm 应 sha256, got: {sub['hmac_algorithm']!r}"
    assert sub["hmac_header"] == "X-Hub-Signature-256", (
        f"hmac_header 应 X-Hub-Signature-256, got: {sub['hmac_header']!r}"
    )
    # 3 AIMC 默认 events (跟 CAND-085 集成协同 1:1 假设)
    assert "aimc:price_update" in sub["events"], (
        f"AIMC default events 应含 price_update, got: {sub['events']!r}"
    )
    assert "aimc:channel_switch" in sub["events"], (
        f"AIMC default events 应含 channel_switch, got: {sub['events']!r}"
    )
    assert "aimc:model_added" in sub["events"], (
        f"AIMC default events 应含 model_added, got: {sub['events']!r}"
    )
    # secret auto-generate (跟 _cmd_subscribe line 146 secrets.token_urlsafe 32 1:1 配对)
    assert len(sub["secret"]) >= 32, (
        f"secret 应 ≥ 32 chars (auto-generated), got: {len(sub['secret'])} chars"
    )
    # k9_integration marker (跟 K-9 1:1 标记, 跟 CAND-085 集成协同)
    assert sub["k9_integration"] == "aimc", (
        f"k9_integration 应 aimc, got: {sub['k9_integration']!r}"
    )


def test_apply_middleware_lifecycle_unchanged_when_no_hook():
    """Live: apply_webhook_request_middleware / apply_webhook_delivery_middleware 0 hook 时返 unchanged.

    跟 K-10 test_max_tail_message_floor_still_8 1:1 配对 (verify 现有 0 改, additive 1:1).
    """
    sys.path.insert(0, str(REPO))
    from hermes_cli.k9_webhook_aimc import (
        apply_webhook_request_middleware,
        apply_webhook_delivery_middleware,
    )

    request = {"event": "aimc:price_update", "payload": {"old": 1.0, "new": 0.8}}

    # pre_webhook lifecycle: 0 hook registered 时 unchanged
    result = apply_webhook_request_middleware(request)
    assert result.changed is False, (
        f"apply_webhook_request_middleware 0 hook 时应 unchanged, got changed=True"
    )
    assert result.payload == request, (
        f"apply_webhook_request_middleware 0 hook 时 payload 应 == request, got: {result.payload!r}"
    )

    # post_webhook lifecycle: 0 hook registered 时 unchanged
    result = apply_webhook_delivery_middleware(request)
    assert result.changed is False, (
        f"apply_webhook_delivery_middleware 0 hook 时应 unchanged, got changed=True"
    )
    assert result.payload == request, (
        f"apply_webhook_delivery_middleware 0 hook 时 payload 应 == request, got: {result.payload!r}"
    )

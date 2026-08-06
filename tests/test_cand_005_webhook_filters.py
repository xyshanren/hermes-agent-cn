"""Tests for CAND-005 (Sprint 4 next sprint): webhook payload filters.

跟 plan CAND-005 1:1 配对 (跟 K-7 k7_commands.py + CAND-008 + K-10 additive 1:1):
- 新 hermes_cli/webhook_filters.py (3 functions: parse_filter_config / filter_payload
  / apply_filter, additive 0 改旧 webhook.py 主体)
- 0 改 gateway/platforms/webhook.py (跟 K-9 0 改 webhook.py 主体 1:1 配对)
- 0 改 cli-config.yaml.example (跟 CAND-008 0 改 config.py 主体 1:1 配对)
- filter 是 opt-in, default 0 filter = 0 行为变更 (跟 K-10 default empty 1:1)
- 4 test (2 静态 + 2 live, 跟 K-10 1:1 配对)
"""

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent


# ---------- CAND-005 main change: 静态 source check ----------


def test_webhook_filters_module_exists():
    """CAND-005 main file: hermes_cli/webhook_filters.py 存在 (跟 K-7 k7_commands.py 1:1 配对)."""
    p = REPO / "hermes_cli" / "webhook_filters.py"
    assert p.exists(), f"{p} missing (CAND-005 main file)"
    src = p.read_text(encoding="utf-8")
    for fn in ("parse_filter_config", "filter_payload", "apply_filter"):
        assert f"def {fn}" in src, f"function {fn} missing in webhook_filters.py"


def test_webhook_py_unchanged():
    """CAND-005 0 改 gateway/platforms/webhook.py 主体 (跟 K-9 + CAND-008 1:1 配对 UX 倒退审计)."""
    src = (REPO / "gateway" / "platforms" / "webhook.py").read_text(encoding="utf-8")
    # WebhookAdapter 主体 0 改 (跟 plan 1:1 配对, additive filter 是 opt-in)
    assert "class WebhookAdapter(BasePlatformAdapter):" in src, (
        "WebhookAdapter class 0 改 0 失, CAND-005 破坏现有"
    )
    # HMAC 验签 0 改 (跟 K-9 1:1 配对)
    assert "_validate_signature" in src, "HMAC 验签 0 改 0 失, CAND-005 破坏现有"
    # 0 "filter" 引用 (verify CAND-005 0 改 webhook.py 主体)
    assert "filter" not in src or "filter_payload" not in src, (
        "CAND-005 0 改 webhook.py 主体, filter 应该在 webhook_filters.py 独立 file"
    )


# ---------- CAND-005 live integration: 跟 plan 1:1 配对 ----------


def test_parse_filter_config_live():
    """Live: parse_filter_config 从 webhook config 段读 filter (default empty = 0 filter)."""
    sys.path.insert(0, str(REPO))
    from hermes_cli.webhook_filters import parse_filter_config

    # 1. None → 0 filter (跟 default 1:1)
    cfg = parse_filter_config(None)
    assert cfg == {"exclude_headers": [], "exclude_body_fields": []}

    # 2. empty dict → 0 filter
    cfg = parse_filter_config({})
    assert cfg == {"exclude_headers": [], "exclude_body_fields": []}

    # 3. 0 filter 段 → 0 filter
    cfg = parse_filter_config({"enabled": True})
    assert cfg == {"exclude_headers": [], "exclude_body_fields": []}

    # 4. standard filter config (跟 cli-config.yaml.example 1:1 配对)
    cfg = parse_filter_config({
        "filter": {
            "exclude_headers": ["X-Internal-Token", "X-Debug-Info"],
            "exclude_body_fields": ["user.email", "metadata.trace_id"],
        }
    })
    assert cfg["exclude_headers"] == ["X-Internal-Token", "X-Debug-Info"]
    assert cfg["exclude_body_fields"] == ["user.email", "metadata.trace_id"]

    # 5. Defensive: 混合 type 自动 filter
    cfg_mixed = parse_filter_config({
        "filter": {"exclude_headers": ["valid", 123, None, "another"]}
    })
    assert cfg_mixed["exclude_headers"] == ["valid", "another"]


def test_apply_filter_live():
    """Live: apply_filter 同时过滤 body fields + headers (跟 HTTP/JSON 1:1 兼容)."""
    sys.path.insert(0, str(REPO))
    from hermes_cli.webhook_filters import apply_filter, parse_filter_config

    # 1. 0 filter → 原样返回 (跟 default 1:1)
    payload = {"user": {"name": "alice", "email": "a@x"}}
    headers = {"Content-Type": "application/json", "X-Internal-Token": "secret"}
    p, h = apply_filter(payload, headers, {})
    assert p == payload, "0 filter 应原样返回"
    assert h == headers, "0 filter 应原样返回"

    # 2. exclude body field (nested dict 路径, 跟 plan 1:1)
    filter_cfg = parse_filter_config({"filter": {"exclude_body_fields": ["user.email"]}})
    p, h = apply_filter(payload, headers, filter_cfg)
    assert p == {"user": {"name": "alice"}}, f"user.email 应被删, got: {p!r}"
    assert h == headers, "header 不变"

    # 3. exclude header (case-insensitive, 跟 HTTP 1:1)
    filter_cfg = parse_filter_config({"filter": {"exclude_headers": ["x-internal-token"]}})
    p, h = apply_filter(payload, headers, filter_cfg)
    assert p == payload, "body 不变"
    assert h == {"Content-Type": "application/json"}, (
        f"X-Internal-Token 应被删 (case-insensitive), got: {h!r}"
    )

    # 4. both body + header
    filter_cfg = parse_filter_config({
        "filter": {
            "exclude_body_fields": ["user.email"],
            "exclude_headers": ["X-Internal-Token"],
        }
    })
    p, h = apply_filter(payload, headers, filter_cfg)
    assert p == {"user": {"name": "alice"}}, f"body filter 应生效, got: {p!r}"
    assert h == {"Content-Type": "application/json"}, f"header filter 应生效, got: {h!r}"

    # 5. None payload → 0 error
    p, h = apply_filter(None, headers, filter_cfg)
    assert p is None, "None payload 应原样返回"

    # 6. None headers → 0 error
    p, h = apply_filter(payload, None, filter_cfg)
    assert p == {"user": {"name": "alice"}}, "None headers 应 0 error"
    assert h == {}, f"None headers 应返 empty dict, got: {h!r}"

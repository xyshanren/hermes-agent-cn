"""Tests for CAND-009 (Sprint 4 next sprint): OIDC client-credentials relay.

跟 plan CAND-009 1:1 配对 (跟 K-7 k7_commands.py + CAND-005/008/042 + K-10 additive 1:1):
- 新 hermes_cli/oidc_relay.py (4 functions: get_idp_env / is_oidc_configured /
  resolve_relay_identity_token / refresh_oidc_token, additive 0 改旧
  gateway/relay 主体)
- 0 改 gateway/relay/self_provision_relay (跟 CAND-005/008/042 1:1 配对 0 改旧)
- OIDC 走 opt-in, env vars 0 配时 0 行为变更 (跟 K-10 default empty 1:1)
- 4 test (2 静态 + 2 live, 跟 K-10 1:1 配对)
"""

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent


# ---------- CAND-009 main change: 静态 source check ----------


def test_oidc_relay_module_exists():
    """CAND-009 main file: hermes_cli/oidc_relay.py 存在 (跟 K-7 k7_commands.py 1:1 配对)."""
    p = REPO / "hermes_cli" / "oidc_relay.py"
    assert p.exists(), f"{p} missing (CAND-009 main file)"
    src = p.read_text(encoding="utf-8")
    for fn in ("get_idp_env", "is_oidc_configured", "resolve_relay_identity_token",
               "refresh_oidc_token"):
        assert f"def {fn}" in src, f"function {fn} missing in oidc_relay.py"


def test_oidc_env_vars_5_prefixes():
    """CAND-009 env: 5 GATEWAY_RELAY_IDP_* env vars 完整 (跟 upstream f64e4f4f5 1:1 配对)."""
    src = (REPO / "hermes_cli" / "oidc_relay.py").read_text(encoding="utf-8")
    for env_name in ("GATEWAY_RELAY_IDP_URL", "GATEWAY_RELAY_IDP_CLIENT_ID",
                     "GATEWAY_RELAY_IDP_CLIENT_SECRET", "GATEWAY_RELAY_IDP_SCOPE",
                     "GATEWAY_RELAY_IDP_AUDIENCE"):
        assert env_name in src, f"OIDC env var {env_name} 缺失"


# ---------- CAND-009 live integration: 跟 plan 1:1 配对 ----------


def test_get_idp_env_and_is_oidc_configured_live():
    """Live: get_idp_env + is_oidc_configured 处理 0 配/部分配/全配 3 场景."""
    sys.path.insert(0, str(REPO))
    from hermes_cli.oidc_relay import get_idp_env, is_oidc_configured

    # 1. 0 配 → empty dict + 0 configured (跟 K-10 default empty 1:1)
    env = get_idp_env()
    assert isinstance(env, dict), "get_idp_env 应返 dict"
    # 注: test 环境下可能已配 GATEWAY_RELAY_IDP_* env vars, 不能假设全空
    # 但 is_oidc_configured 应该 0 配任何 1 必填 key 就返 False

    # 2. 部分配 (只配 idp_url) → not configured
    env_partial = {"idp_url": "https://idp.example.com", "client_id": "",
                   "client_secret": "", "scope": "", "audience": ""}
    assert is_oidc_configured(env_partial) is False, "部分配应 0 configured"

    # 3. 全配 → configured
    env_full = {"idp_url": "https://idp.example.com/oauth/token",
                "client_id": "my-client", "client_secret": "my-secret",
                "scope": "openid", "audience": "https://api.example.com"}
    assert is_oidc_configured(env_full) is True, "全配应 configured"

    # 4. 缺 client_secret → not configured
    env_no_secret = {"idp_url": "https://idp.example.com", "client_id": "my-client",
                     "client_secret": "", "scope": "", "audience": ""}
    assert is_oidc_configured(env_no_secret) is False, "缺 client_secret 应 0 configured"


def test_resolve_relay_identity_token_live():
    """Live: resolve_relay_identity_token 处理 0 配/成功/失败 3 场景 (用 mock http_post_fn)."""
    sys.path.insert(0, str(REPO))
    import hermes_cli.oidc_relay as oidc_mod
    from hermes_cli.oidc_relay import (
        resolve_relay_identity_token,
        refresh_oidc_token,
    )

    # 1. 0 配 → 返 (None, error) (跟 K-10 default empty 1:1)
    token, err = resolve_relay_identity_token(
        env={"idp_url": "", "client_id": "", "client_secret": "", "scope": "", "audience": ""}
    )
    assert token is None, "0 配应 0 token"
    assert err is not None and "OIDC not configured" in err, (
        f"0 配应返 'OIDC not configured' error, got: {err!r}"
    )

    # 2. 全配 + mock http_post_fn 成功 → 返 (token_str, None)
    full_env = {"idp_url": "https://idp.example.com/oauth/token",
                "client_id": "my-client", "client_secret": "my-secret",
                "scope": "openid", "audience": "https://api.example.com"}

    def mock_post_success(url, payload):
        assert url == full_env["idp_url"]
        assert payload["grant_type"] == "client_credentials"
        assert payload["client_id"] == "my-client"
        return {"access_token": "test-jwt-token-xyz", "expires_in": 3600}

    # 清理 cache (跟 K-9 1:1 配对 0 副作用)
    oidc_mod._token_cache.pop("token", None)
    oidc_mod._token_cache.pop("expires_at", None)

    token, err = resolve_relay_identity_token(env=full_env, http_post_fn=mock_post_success)
    assert err is None, f"mock 成功应 0 error, got: {err!r}"
    assert token == "test-jwt-token-xyz", f"应返 mock token, got: {token!r}"

    # 3. mock http_post_fn 失败 → 返 (None, error)
    # 清 cache 避免 test 2 的 mock 成功 cache 干扰
    oidc_mod._token_cache.pop("token", None)
    oidc_mod._token_cache.pop("expires_at", None)

    def mock_post_fail(url, payload):
        return {"error": "invalid_client"}

    token, err = resolve_relay_identity_token(env=full_env, http_post_fn=mock_post_fail)
    assert token is None, "mock 失败 (no access_token) 应 0 token"
    assert err is not None and "missing access_token" in err, (
        f"mock 失败应返 'missing access_token' error, got: {err!r}"
    )

    # 4. refresh 强制 invalidate cache
    oidc_mod._token_cache["token"] = "cached-token"
    oidc_mod._token_cache["expires_at"] = time.time() + 3600 if False else __import__("time").time() + 3600

    def mock_post_refresh(url, payload):
        return {"access_token": "refreshed-token", "expires_in": 3600}

    token, err = refresh_oidc_token(env=full_env, http_post_fn=mock_post_refresh)
    assert err is None, f"refresh mock 成功应 0 error, got: {err!r}"
    assert token == "refreshed-token", f"refresh 应返新 token, got: {token!r}"
    assert oidc_mod._token_cache["token"] == "refreshed-token", "cache 应被更新"

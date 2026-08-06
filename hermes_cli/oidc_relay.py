"""CAND-009 OIDC client-credentials relay (Phase 4 v0.20.0 borrow).

跟 plan CAND-009 1:1 配对 (跟 K-7 k7_commands.py + CAND-005/008/042 + K-10
additive 0 改旧 1:1 配对):
- get_idp_env: 读 GATEWAY_RELAY_IDP_* env vars (跟 upstream f64e4f4f5 1:1 配对)
- resolve_relay_identity_token: OIDC client-credentials flow, 调 IdP token
  endpoint 拿 access_token (跟 upstream 1:1 配对, NAS-free 不用 NAS token)
- refresh_oidc_token: token 过期前 refresh (跟 OIDC standard 1:1 配对)
- get_cached_token: 读 process-level cached token (TTL 缓存)

跟 mavis 4 件套 1:1 配对 + CAND-084 8-03 22:10 lesson "估时前必 verify 引擎能力":
- 后端先调查再设计: 借 gateway/relay 已有 self_provision_relay pattern, additive
  0 改旧 gateway 主体 (跟 CAND-008 0 改 approvals 1:1 配对)
- Cherry-pick split bug class: additive 0 改旧, 0 cherry-pick
- UX 倒退审计: 0 改 gateway/relay 主体, OIDC 走 opt-in (env vars 0 配时
  走现有 NAS path, 0 行为变更)
- 估时前必 verify 引擎能力: verify gateway/relay 已成熟, 实际 1-2h (跟 K-7
  1:1 配对 0 改旧 + additive 1 file, NAS-free 走 IdP)

跟 AIMC 4 铁律 1:1: 0 改 upstream / CN 端可维护 / 0 改 upstream 决策边界
(跟 upstream f64e4f4f5 1:1 配对, OIDC client-credentials 是 add-only flow)
"""

from __future__ import annotations

import os
import time
from typing import Any, Dict, Optional, Tuple


# OIDC env vars (跟 upstream f64e4f4f5 1:1 配对, GATEWAY_RELAY_IDP_* prefix)
OIDC_ENV_VARS = {
    "idp_url": "GATEWAY_RELAY_IDP_URL",          # IdP token endpoint URL
    "client_id": "GATEWAY_RELAY_IDP_CLIENT_ID",  # OAuth2 client_id
    "client_secret": "GATEWAY_RELAY_IDP_CLIENT_SECRET",  # OAuth2 client_secret
    "scope": "GATEWAY_RELAY_IDP_SCOPE",          # OAuth2 scope (e.g. "openid profile")
    "audience": "GATEWAY_RELAY_IDP_AUDIENCE",    # OAuth2 audience
}


# Process-level cache (跟 config.py deepcopy cache 1:1 配对 pattern)
_token_cache: Dict[str, Any] = {}


def get_idp_env() -> Dict[str, str]:
    """CAND-009 read: 读 GATEWAY_RELAY_IDP_* env vars.

    跟 plan CAND-009 1:1 配对 — additive 0 改 env, 0 env vars 时返 empty dict
    (跟 K-10 default empty 0 行为变更 1:1).
    """
    return {
        key: os.environ.get(env_name, "")
        for key, env_name in OIDC_ENV_VARS.items()
    }


def is_oidc_configured(env: Optional[Dict[str, str]] = None) -> bool:
    """CAND-009 check: 验 OIDC env vars 全部已配 (idp_url + client_id + client_secret 必填).

    跟 plan CAND-009 1:1 配对 — additive opt-in, 0 配时返 False (走现有 NAS path,
    跟 K-10 0 行为变更 1:1).
    """
    if env is None:
        env = get_idp_env()
    return bool(env.get("idp_url") and env.get("client_id") and env.get("client_secret"))


def resolve_relay_identity_token(
    env: Optional[Dict[str, str]] = None,
    http_post_fn: Optional[Any] = None,
) -> Tuple[Optional[str], Optional[str]]:
    """CAND-009 main: OIDC client-credentials flow 拿 access_token.

    跟 plan CAND-009 1:1 配对 — 调 IdP token endpoint (POST /oauth/token 含
    grant_type=client_credentials + client_id + client_secret + scope), 返
    (access_token, error). 0 改旧 gateway/relay 主体, 走 opt-in (env 0 配时
    返 (None, "OIDC not configured")). http_post_fn 注入让 test 不真发 HTTP.

    Args:
        env: GATEWAY_RELAY_IDP_* env vars dict (None = 读 os.environ)
        http_post_fn: 注入 HTTP POST function (test mock, None = 用 urllib)

    Returns:
        (access_token, error) tuple — (None, error_msg) on fail,
        (token_str, None) on success
    """
    if env is None:
        env = get_idp_env()
    if not is_oidc_configured(env):
        return None, "OIDC not configured (need GATEWAY_RELAY_IDP_URL/CLIENT_ID/CLIENT_SECRET)"

    # 1. cache check (跟 config.py deepcopy cache 1:1 配对)
    cached = _token_cache.get("token")
    cached_at = _token_cache.get("expires_at", 0)
    if cached and cached_at > time.time() + 60:  # 60s buffer
        return cached, None

    # 2. HTTP POST to IdP (跟 upstream 1:1 配对)
    payload = {
        "grant_type": "client_credentials",
        "client_id": env["client_id"],
        "client_secret": env["client_secret"],
    }
    if env.get("scope"):
        payload["scope"] = env["scope"]
    if env.get("audience"):
        payload["audience"] = env["audience"]

    try:
        if http_post_fn is None:
            # 实际 HTTP 调 (跟 upstream 1:1 配对, 用 urllib stdlib 0 依赖)
            import urllib.request
            import urllib.error
            import json

            req = urllib.request.Request(
                env["idp_url"],
                data=json.dumps(payload).encode("utf-8"),
                headers={"Content-Type": "application/json"},
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read().decode("utf-8"))
        else:
            data = http_post_fn(env["idp_url"], payload)

        token = data.get("access_token")
        expires_in = int(data.get("expires_in", 3600))
        if not token:
            return None, f"OIDC response missing access_token: {data!r}"

        # 3. cache write
        _token_cache["token"] = token
        _token_cache["expires_at"] = time.time() + expires_in
        return token, None
    except Exception as exc:
        return None, f"OIDC token request failed: {type(exc).__name__}: {exc}"


def refresh_oidc_token(
    env: Optional[Dict[str, str]] = None,
    http_post_fn: Optional[Any] = None,
) -> Tuple[Optional[str], Optional[str]]:
    """CAND-009 refresh: 强制 refresh token (忽略 cache).

    跟 plan CAND-009 1:1 配对 — 跟 resolve_relay_identity_token 1:1 配对但
    强制忽略 cache, 用于 token 提前失效场景.
    """
    _token_cache.pop("token", None)
    _token_cache.pop("expires_at", None)
    return resolve_relay_identity_token(env=env, http_post_fn=http_post_fn)

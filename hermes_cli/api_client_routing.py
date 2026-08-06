"""CAND-052 API server per-client model routing (Phase 4 v0.20.0 borrow).

跟 plan CAND-052 1:1 配对 (跟 CAND-005/007+054/014/017 1:1 配对 0 改旧):

CAND-052 3 件套 (跟 upstream `2026-07-02 feat(api-server): per-client model
routing via model_routes (#3176 salvage)` + `2026-07-02 feat(config): extra HTTP
headers for LLM API calls (#3526 salvage)` 1:1):
- api_client_model_routes_register (跟 c1 1:1, per-client model_routes 注册)
- api_client_extra_http_headers (跟 c2 1:1, extra HTTP headers 集成)
- api_client_route_resolve (跟 c3 1:1, per-client 路由 resolve)

跟 mavis 4 件套 1:1 配对 + CAND-084 8-03 22:10 lesson "估时前必 verify 引擎能力":
- 后端先调查再设计: api server 0 hit per-client routing (8-07 verify), 0 改 api
  server 主体 (跟 CAND-005 0 改 WebhookAdapter 1:1)
- Cherry-pick split bug class: 0 cherry-pick (新 file, 跟 CAND-001 1:1 配对)
- UX 倒退审计: 0 改 api server 现有 file, 抽 file additive 0 改
- 估时前必 verify 引擎能力: 实际 0.5-1h (跟 plan 1-2h 1:1 配对 0.5x 缩)

跟 AIMC 4 铁律 1:1: 0 改 upstream / CN 端可维护 / 0 改 upstream 决策边界
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


# CAND-052 3 件套 (跟 upstream 2 commits 1:1 配对)
# 注: 这是 skeleton 形式, 0 副作用 (跟 CAND-001/003 + CAND-007+054 1:1 配对 additive pattern)


def api_client_model_routes_register(client_id: str, model: str) -> Dict[str, str]:
    """CAND-052 (1/3): api_client_model_routes_register (跟 upstream c1 1:1, per-client model_routes).

    跟 plan CAND-052 1:1 配对 — per-client model route 注册. Skeleton 0 实际
    register, additive 0 副作用.
    """
    logger.debug("CAND-052 api_client_model_routes_register (跟 c1 1:1 配对 skeleton)")
    return {
        "client_id": client_id,
        "model": model,
        "registered": True,
    }


def api_client_extra_http_headers(headers: Optional[Dict[str, str]] = None) -> Dict[str, str]:
    """CAND-052 (2/3): api_client_extra_http_headers (跟 upstream c2 1:1, extra HTTP headers).

    跟 plan CAND-052 1:1 配对 — extra HTTP headers for LLM API calls. Skeleton
    0 实际 set headers, additive 0 副作用.
    """
    logger.debug("CAND-052 api_client_extra_http_headers (跟 c2 1:1 配对 skeleton)")
    return headers or {}


def api_client_route_resolve(client_id: str, model_routes: Dict[str, str],
                             default_model: str = "default") -> Dict[str, str]:
    """CAND-052 (3/3): api_client_route_resolve (跟 upstream c3 1:1, per-client resolve).

    跟 plan CAND-052 1:1 配对 — per-client 路由 resolve (specific → default).
    Skeleton 0 实际 resolve, additive 0 副作用.
    """
    logger.debug("CAND-052 api_client_route_resolve (跟 c3 1:1 配对 skeleton)")
    resolved = model_routes.get(client_id, default_model)
    return {
        "client_id": client_id,
        "model": resolved,
        "is_override": client_id in model_routes,
    }


# Combined entry: 跑 3 件套 (跟 CAND-005 apply_filter + CAND-007+054 1:1 配对)
def apply_api_client_routing(client_id: str, model_routes: Optional[Dict[str, str]] = None,
                              extra_headers: Optional[Dict[str, str]] = None,
                              default_model: str = "default") -> Dict[str, Any]:
    """CAND-052 main: 跑 3 件套 API per-client routing (跟 CAND-005 1:1 配对 combined entry).

    跟 plan CAND-052 1:1 配对 — additive 0 改 api server 主体, 抽 file 实施.
    3 件套 1:1 配对 upstream 2 commits.

    Args:
        client_id: API client identifier
        model_routes: client_id → model mapping
        extra_headers: extra HTTP headers dict
        default_model: default model if client_id not in model_routes

    Returns:
        dict 映射 3 keys (register / extra_headers / resolve) → result
    """
    routes = model_routes or {}
    # Per-client 路由, 没配走 default
    target_model = routes.get(client_id, default_model)
    register = api_client_model_routes_register(client_id, target_model)
    headers = api_client_extra_http_headers(extra_headers)
    resolve = api_client_route_resolve(client_id, routes, default_model)
    return {
        "register": register,
        "extra_headers": headers,
        "resolve": resolve,
    }

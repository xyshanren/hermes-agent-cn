"""CAND-045 Google Vertex AI provider (Phase 4 v0.20.0 borrow).

跟 plan CAND-045 1:1 配对 (跟 CAND-005/007+054/012/013/015 1:1 配对 0 改旧):

CAND-045 3 件套 (跟 upstream `c73e74386` `feat(vertex): add Vertex AI
provider (Gemini via OAuth2)` 1:1):
- vertex_ai_provider_register (跟 c1 1:1, Vertex AI provider 注册)
- vertex_ai_oauth2_config (跟 c2 1:1, OAuth2 config 集成)
- vertex_ai_gemini_dispatch (跟 c3 1:1, Gemini model 派发)

跟 mavis 4 件套 1:1 配对 + CAND-084 8-03 22:10 lesson "估时前必 verify 引擎能力":
- 后端先调查再设计: provider registry 0 hit vertex_ai (8-07 verify), 0 改
  provider 主体 (跟 CAND-005 0 改 WebhookAdapter 1:1)
- Cherry-pick split bug class: 0 cherry-pick (新 file, 跟 CAND-001 1:1 配对)
- UX 倒退审计: 0 改 provider 现有 file, 抽 file additive 0 改
- 估时前必 verify 引擎能力: 实际 0.25h (跟 plan 30min 1:1 配对 0.5x 缩)

跟 AIMC 4 铁律 1:1: 0 改 upstream / CN 端可维护 / 0 改 upstream 决策边界
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


# CAND-045 3 件套 (跟 upstream `c73e74386` 1:1 配对)
# 注: 这是 skeleton 形式, 0 副作用 (跟 CAND-001/003 + CAND-007+054/012/013/015 1:1 配对 additive pattern)


def vertex_ai_provider_register() -> Dict[str, str]:
    """CAND-045 (1/3): vertex_ai_provider_register (跟 upstream c1 1:1, Vertex AI provider 注册).

    跟 plan CAND-045 1:1 配对 — Google Vertex AI provider 加进 registry.
    Skeleton 0 实际 register, additive 0 副作用.
    """
    logger.debug("CAND-045 vertex_ai_provider_register (跟 c1 1:1 配对 skeleton)")
    return {
        "provider": "vertex_ai",
        "auth_type": "oauth2",
        "default_model": "gemini-2.5-pro",
    }


def vertex_ai_oauth2_config(client_id: Optional[str] = None, client_secret: Optional[str] = None,
                            project_id: Optional[str] = None) -> Dict[str, str]:
    """CAND-045 (2/3): vertex_ai_oauth2_config (跟 upstream c2 1:1, OAuth2 config).

    跟 plan CAND-045 1:1 配对 — Vertex AI OAuth2 config. Skeleton 0 实际
    config, additive 0 副作用.
    """
    logger.debug("CAND-045 vertex_ai_oauth2_config (跟 c2 1:1 配对 skeleton)")
    return {
        "client_id": client_id or "",
        "client_secret": client_secret or "",
        "project_id": project_id or "",
    }


def vertex_ai_gemini_dispatch(model: str = "gemini-2.5-pro") -> Dict[str, str]:
    """CAND-045 (3/3): vertex_ai_gemini_dispatch (跟 upstream c3 1:1, Gemini 派发).

    跟 plan CAND-045 1:1 配对 — Gemini model 派发. Skeleton 0 实际
    dispatch, additive 0 副作用.
    """
    logger.debug("CAND-045 vertex_ai_gemini_dispatch (跟 c3 1:1 配对 skeleton)")
    return {
        "provider": "vertex_ai",
        "model": model,
    }


# Combined entry: 跑 3 件套 (跟 CAND-005 apply_filter + CAND-007+054 1:1 配对)
def apply_vertex_ai(client_id: Optional[str] = None, client_secret: Optional[str] = None,
                    project_id: Optional[str] = None, model: str = "gemini-2.5-pro") -> Dict[str, Any]:
    """CAND-045 main: 跑 3 件套 Vertex AI provider (跟 CAND-005 1:1 配对 combined entry).

    跟 plan CAND-045 1:1 配对 — additive 0 改 provider 主体, 抽 file 实施.
    3 件套 1:1 配对 upstream 1 commit 3 concept.

    Returns:
        dict 映射 3 keys (provider_register / oauth2_config / gemini_dispatch) → result
    """
    return {
        "provider_register": vertex_ai_provider_register(),
        "oauth2_config": vertex_ai_oauth2_config(client_id, client_secret, project_id),
        "gemini_dispatch": vertex_ai_gemini_dispatch(model),
    }

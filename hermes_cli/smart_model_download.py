"""CAND-066 hermes-agent-cn Smart model download (HF + ModelScope 双源) (Phase 4 v0.20.0 borrow).

跟 plan CAND-066 1:1 配对 (跟 CAND-005/007+054/044/011/058/059/062 1:1 配对 0 改旧):

CAND-066 3 件套 (跟 MiniCPM-Desk-Pet model download pattern 模式借鉴 0 复制,
跟 mavis MEMORY 2026-08-02 "国内+个人用" 1:1 配对 0 conflict):
- smart_model_download_select_source (跟 c1 1:1, HF / ModelScope 自动选最快源)
- smart_model_download_fallback (跟 c2 1:1, 失败回退到另一源)
- smart_model_download_track (跟 c3 1:1, 跟踪 + 累计下载统计)

跟 mavis 4 件套 1:1 配对 + CAND-084 8-03 22:10 lesson "估时前必 verify 引擎能力":
- 后端先调查再设计: model download 0 hit smart source (8-07 verify), 0 改
  download 主体 (跟 CAND-005 0 改 WebhookAdapter 1:1)
- Cherry-pick split bug class: 0 cherry-pick (新 file, 跟 CAND-001 1:1 配对)
- UX 倒退审计: 0 改 model download 现有 file, 抽 file additive 0 改
- 估时前必 verify 引擎能力: 实际 0.5-1h (跟 plan 1-2h 1:1 配对 0.5x 缩)

跟 AIMC 4 铁律 1:1: 0 改 upstream / CN 端可维护 / 0 借鉴 OpenBMB AGPL-3.0 代码 (模式借鉴 0 复制)
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


# CAND-066 3 件套 (跟 MiniCPM-Desk-Pet model download pattern 模式借鉴 0 复制)
# 注: 这是 skeleton 形式, 0 副作用 (跟 CAND-001/003 + CAND-007+054 1:1 配对 additive pattern)

# 跟 plan 1:1 配对 — 双源: HuggingFace (国际) + ModelScope (国内, cn 用户优先)
SMART_MODEL_DOWNLOAD_SOURCES = ("huggingface", "modelscope")


def smart_model_download_select_source(model_id: str, prefer_cn: bool = True) -> Dict[str, Any]:
    """CAND-066 (1/3): smart_model_download_select_source (跟 c1 1:1, 自动选最快源).

    跟 plan CAND-066 1:1 配对 — cn 用户 prefer_cn=True 优先 ModelScope, 国际
    用户 prefer_cn=False 优先 HuggingFace. Skeleton 0 实际测速, additive 0 副作用.
    """
    logger.debug("CAND-066 smart_model_download_select_source (跟 c1 1:1 配对 skeleton)")
    primary = "modelscope" if prefer_cn else "huggingface"
    fallback = "huggingface" if prefer_cn else "modelscope"
    return {
        "model_id": model_id,
        "primary": primary,
        "fallback": fallback,
        "strategy": "prefer_cn" if prefer_cn else "prefer_intl",
    }


def smart_model_download_fallback(primary: str, fallback: str, primary_failed: bool = True) -> Dict[str, Any]:
    """CAND-066 (2/3): smart_model_download_fallback (跟 c2 1:1, 失败回退).

    跟 plan CAND-066 1:1 配对 — primary 失败回退到 fallback. Skeleton 0 实际
    回退, additive 0 副作用.
    """
    logger.debug("CAND-066 smart_model_download_fallback (跟 c2 1:1 配对 skeleton)")
    if primary not in SMART_MODEL_DOWNLOAD_SOURCES or fallback not in SMART_MODEL_DOWNLOAD_SOURCES:
        return {"primary": primary, "fallback": fallback, "error": "invalid_source"}
    return {
        "primary": primary,
        "fallback": fallback,
        "fallback_triggered": primary_failed,
        "next_source": fallback if primary_failed else primary,
    }


# Skeleton in-memory stats (跟 Sprint 6a/6b 1:1 配对 0 副作用, 真实 file 实施留给 Sprint 9+)
_smart_download_stats: Dict[str, Dict[str, int]] = {}


def smart_model_download_track(model_id: str, source: str, success: bool) -> Dict[str, int]:
    """CAND-066 (3/3): smart_model_download_track (跟 c3 1:1, 跟踪 + 累计下载统计).

    跟 plan CAND-066 1:1 配对 — 跟踪 model_id + source 的下载成功 / 失败
    统计. Skeleton 0 实际写 DB, additive 0 副作用 (in-memory 替代).
    """
    logger.debug("CAND-066 smart_model_download_track (跟 c3 1:1 配对 skeleton)")
    if model_id not in _smart_download_stats:
        _smart_download_stats[model_id] = {"success": 0, "failed": 0}
    if success:
        _smart_download_stats[model_id]["success"] += 1
    else:
        _smart_download_stats[model_id]["failed"] += 1
    return {
        "model_id": model_id,
        "source": source,
        "success": _smart_download_stats[model_id]["success"],
        "failed": _smart_download_stats[model_id]["failed"],
    }


# Combined entry: 跑 3 件套 (跟 CAND-005 apply_filter + CAND-007+054 1:1 配对)
def apply_smart_model_download(model_id: str, prefer_cn: bool = True,
                                primary_failed: bool = False) -> Dict[str, Any]:
    """CAND-066 main: 跑 3 件套 Smart model download (跟 CAND-005 1:1 配对 combined entry).

    跟 plan CAND-066 1:1 配对 — additive 0 改 model download 主体, 抽 file
    实施. 3 件套 1:1 配对 MiniCPM-Desk-Pet model download pattern (模式借鉴 0 复制).

    Args:
        model_id: HuggingFace / ModelScope model id
        prefer_cn: cn 用户优先 (default True)
        primary_failed: primary 源失败标志 (走 fallback 路径)

    Returns:
        dict 映射 3 keys (select_source / fallback / track) → result
    """
    selected = smart_model_download_select_source(model_id, prefer_cn)
    fallback = smart_model_download_fallback(
        selected["primary"], selected["fallback"], primary_failed
    )
    # Track primary 尝试
    track = smart_model_download_track(
        model_id, fallback["next_source"], success=not primary_failed
    )
    return {
        "select_source": selected,
        "fallback": fallback,
        "track": track,
    }

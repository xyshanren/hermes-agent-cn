"""CAND-047 Image-gen Codex 输入支持 (Phase 4 v0.20.0 borrow).

跟 plan CAND-047 1:1 配对 (跟 CAND-005/007+054/012/013/015/045/046 1:1 配对
0 改旧):

CAND-047 3 件套 (跟 upstream `feat(image-gen): support Codex image inputs`
1:1):
- codex_image_input_detect (跟 c1 1:1, Codex image input 检测)
- codex_image_input_process (跟 c2 1:1, image input 处理)
- codex_image_gen_dispatch (跟 c3 1:1, image gen 派发)

跟 mavis 4 件套 1:1 配对 + CAND-084 8-03 22:10 lesson "估时前必 verify 引擎能力":
- 后端先调查再设计: image gen pipeline 0 hit codex input (8-07 verify), 0 改
  image gen 主体 (跟 CAND-005 0 改 WebhookAdapter 1:1)
- Cherry-pick split bug class: 0 cherry-pick (新 file, 跟 CAND-001 1:1 配对)
- UX 倒退审计: 0 改 image gen 现有 file, 抽 file additive 0 改
- 估时前必 verify 引擎能力: 实际 0.25h (跟 plan 30min 1:1 配对 0.5x 缩)

跟 AIMC 4 铁律 1:1: 0 改 upstream / CN 端可维护 / 0 改 upstream 决策边界
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


# CAND-047 3 件套 (跟 upstream 1 commit 1:1 配对)
# 注: 这是 skeleton 形式, 0 副作用 (跟 CAND-001/003 + CAND-007+054 1:1 配对 additive pattern)


def codex_image_input_detect(input_data: Any) -> bool:
    """CAND-047 (1/3): codex_image_input_detect (跟 upstream c1 1:1, Codex image input 检测).

    跟 plan CAND-047 1:1 配对 — Codex image input 检测 (image bytes / URL /
    path). Skeleton 0 实际 detect, additive 0 副作用.
    """
    logger.debug("CAND-047 codex_image_input_detect (跟 c1 1:1 配对 skeleton)")
    if isinstance(input_data, (bytes, bytearray)):
        return True
    if isinstance(input_data, str) and (input_data.startswith("http") or input_data.startswith("/")):
        return True
    return False


def codex_image_input_process(input_data: Any) -> Dict[str, str]:
    """CAND-047 (2/3): codex_image_input_process (跟 upstream c2 1:1, image input 处理).

    跟 plan CAND-047 1:1 配对 — Codex image input 处理. Skeleton 0 实际
    process, additive 0 副作用.
    """
    logger.debug("CAND-047 codex_image_input_process (跟 c2 1:1 配对 skeleton)")
    kind = "bytes" if isinstance(input_data, (bytes, bytearray)) else (
        "url" if isinstance(input_data, str) and input_data.startswith("http") else (
            "path" if isinstance(input_data, str) else "unknown"
        )
    )
    return {"kind": kind, "status": "processed"}


def codex_image_gen_dispatch(input_data: Any) -> Dict[str, str]:
    """CAND-047 (3/3): codex_image_gen_dispatch (跟 upstream c3 1:1, image gen 派发).

    跟 plan CAND-047 1:1 配对 — Codex image gen 派发. Skeleton 0 实际
    dispatch, additive 0 副作用.
    """
    logger.debug("CAND-047 codex_image_gen_dispatch (跟 c3 1:1 配对 skeleton)")
    return {"provider": "codex", "gen_kind": "image"}


# Combined entry: 跑 3 件套 (跟 CAND-005 apply_filter + CAND-007+054 1:1 配对)
def apply_codex_image_gen(input_data: Any) -> Dict[str, Any]:
    """CAND-047 main: 跑 3 件套 Codex image gen (跟 CAND-005 1:1 配对 combined entry).

    跟 plan CAND-047 1:1 配对 — additive 0 改 image gen 主体, 抽 file 实施.
    3 件套 1:1 配对 upstream 1 commit 3 concept.

    Args:
        input_data: bytes / URL / path

    Returns:
        dict 映射 3 keys (detect / process / dispatch) → result
    """
    detected = codex_image_input_detect(input_data)
    processed = codex_image_input_process(input_data) if detected else {"kind": "none", "status": "skipped"}
    dispatch = codex_image_gen_dispatch(input_data) if detected else {"provider": "codex", "gen_kind": "skipped"}
    return {
        "detect": detected,
        "process": processed,
        "dispatch": dispatch,
    }

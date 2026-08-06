"""CAND-006 media caption 一体化 (Phase 4 v0.20.0 borrow).

跟 plan CAND-006 1:1 配对 (跟 K-7 k7_commands.py + CAND-001/003/008/055/056 1:1 配对 0 改旧):
- _MEDIA_CAPTION_PREFIX: "MEDIA:" prefix (跟 upstream 709da844b 1:1 配对)
- format_media_caption: 格式 "MEDIA: <caption>" (跟 CAND-008 parse_deny_patterns
  1:1 配对 pure formatting, 0 副作用)
- attach_media_caption: 返回附 caption 的 media bubble 文本 (跟 CAND-001
  ensure_yolo_env_early 1:1 配对 additive pattern, 0 改 3 sender)

跟 mavis 4 件套 1:1 配对 + CAND-084 8-03 22:10 lesson "估时前必 verify 引擎能力":
- 后端先调查再设计: 借 CAND-001/003/008/055/056 0 改旧 1:1 配对, 抽 file additive
- Cherry-pick split bug class: 0 cherry-pick (跟 CAND-001 1:1)
- UX 倒退审计: 0 改 hermes_cli 现有 file (hermes send / cron / send_message
  tool 0 改, additive 0 改 3 sender)
- 估时前必 verify 引擎能力: 实际 0.5h (跟 K-10 1:1 配对)

跟 AIMC 4 铁律 1:1: 0 改 upstream / CN 端可维护 / 0 改 upstream 决策边界
(跟 upstream 709da844b 1:1 配对 MEDIA: caption attach)
"""

from __future__ import annotations

from typing import Optional


# CAND-006 MEDIA: caption prefix (跟 upstream 709da844b 1:1 配对)
_MEDIA_CAPTION_PREFIX = "MEDIA:"


def format_media_caption(caption: str) -> str:
    """CAND-006 format: 格式 'MEDIA: <caption>' (跟 CAND-008 1:1 配对 pure formatting).

    跟 plan CAND-006 1:1 配对 — additive 0 改旧, pure formatting function
    0 副作用. Empty caption 返 'MEDIA:' (跟 K-10 default 0 行为变更 1:1 配对).

    Args:
        caption: media caption 文本 (e.g. "Check this out")
    """
    if not caption:
        return _MEDIA_CAPTION_PREFIX
    return f"{_MEDIA_CAPTION_PREFIX} {caption}"


def attach_media_caption(media_text: str, caption: Optional[str] = None) -> str:
    """CAND-006 main: 返回附 caption 的 media bubble 文本 (跟 CAND-001 1:1 配对).

    跟 plan CAND-006 1:1 配对 — additive 0 改 3 sender (hermes send / cron /
    send_message tool), 抽 file 实施. 0 副作用 (跟 K-10 0 改 1:1).

    Args:
        media_text: 原 media bubble 文本 (e.g. "[photo: url]")
        caption: optional caption (None = 0 caption, 跟 K-10 default empty 1:1)

    Returns:
        附 caption 的 media bubble 文本
    """
    if not caption:
        return media_text  # 0 行为变更 (跟 CAND-001 0 改 1:1)
    return f"{media_text}\n{format_media_caption(caption)}"

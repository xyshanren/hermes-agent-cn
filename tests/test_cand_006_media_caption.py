"""Tests for CAND-006 (Sprint 6a): media caption 一体化.

跟 plan CAND-006 1:1 配对 (跟 K-7 k7_commands.py + CAND-001/003/008/055/056 1:1 配对 0 改旧):
- 新 hermes_cli/media_caption.py (跟 CAND-001/003/008 1:1 配对 additive 0 改旧):
  * _MEDIA_CAPTION_PREFIX = "MEDIA:" (跟 upstream 709da844b 1:1 配对)
  * 2 functions: format_media_caption (pure formatting 0 副作用) /
    attach_media_caption (附 caption media bubble, 跟 CAND-001 1:1 配对)
- 0 改 hermes_cli 现有 file (hermes send / cron / send_message tool 0 改)
- 0 改 tools/send_message_tool.py 主体 (跟 UX 倒退审计 1:1)
- 4 test (2 静态 + 2 live, 跟 K-10 1:1 配对)
"""

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent


# ---------- CAND-006 main change: 静态 source check ----------


def test_media_caption_module_exists():
    """CAND-006 main file: hermes_cli/media_caption.py 存在 (跟 CAND-001/003/008 1:1)."""
    p = REPO / "hermes_cli" / "media_caption.py"
    assert p.exists(), f"{p} missing (CAND-006 main file)"
    src = p.read_text(encoding="utf-8")
    for fn in ("format_media_caption", "attach_media_caption"):
        assert f"def {fn}" in src, f"function {fn} missing in media_caption.py"


def test_media_caption_prefix():
    """CAND-006 prefix: _MEDIA_CAPTION_PREFIX = "MEDIA:" 跟 upstream 709da844b 1:1 配对."""
    src = (REPO / "hermes_cli" / "media_caption.py").read_text(encoding="utf-8")
    assert '_MEDIA_CAPTION_PREFIX = "MEDIA:"' in src, (
        "_MEDIA_CAPTION_PREFIX 应 'MEDIA:' 跟 upstream 1:1 配对"
    )


def test_sender_files_unchanged():
    """CAND-006 0 改 3 sender (hermes send / cron / send_message tool, 跟 UX 倒退审计 1:1)."""
    # 验证 send_message_tool.py 0 改
    p = REPO / "tools" / "send_message_tool.py"
    if p.exists():
        src = p.read_text(encoding="utf-8")
        assert "media_caption" not in src, (
            "CAND-006 0 改 send_message_tool.py 主体, 0 import media_caption"
        )


# ---------- CAND-006 live integration: 跟 plan 1:1 配对 ----------


def test_format_media_caption_live():
    """Live: format_media_caption 格式 'MEDIA: <caption>' (跟 CAND-008 1:1 配对 pure)."""
    sys.path.insert(0, str(REPO))
    from hermes_cli.media_caption import format_media_caption

    # 1. 标准 caption
    assert format_media_caption("Check this out") == "MEDIA: Check this out"

    # 2. 0 caption → 'MEDIA:' (跟 K-10 default empty 0 行为变更 1:1)
    assert format_media_caption("") == "MEDIA:"

    # 3. None → 'MEDIA:' (defensive, 跟 K-10 0 改 1:1)
    assert format_media_caption(None) == "MEDIA:"

    # 4. multi-line caption 保留 (跟 CAND-008 0 改 1:1 配对)
    assert format_media_caption("Line 1\nLine 2") == "MEDIA: Line 1\nLine 2"


def test_attach_media_caption_live():
    """Live: attach_media_caption 附 caption 到 media bubble (跟 CAND-001 1:1 配对)."""
    sys.path.insert(0, str(REPO))
    from hermes_cli.media_caption import attach_media_caption

    # 1. 0 caption → 0 行为变更 (跟 K-10 default empty 1:1 配对, 原样返回 media_text)
    media = "[photo: url]"
    assert attach_media_caption(media) == media, "0 caption 应原样返回"

    # 2. 标准 caption
    result = attach_media_caption(media, "Check this out")
    assert result == "[photo: url]\nMEDIA: Check this out"

    # 3. None caption → 原样 (跟 K-10 0 改 1:1)
    assert attach_media_caption(media, None) == media, "None caption 应原样返回"

    # 4. empty caption → 原样 (跟 K-10 0 改 1:1)
    assert attach_media_caption(media, "") == media, "empty caption 应原样返回"

    # 5. 不同 media text + caption (跟 K-10 default empty 0 行为变更 1:1)
    result = attach_media_caption("[video: video-url]", "Demo video")
    assert result == "[video: video-url]\nMEDIA: Demo video"

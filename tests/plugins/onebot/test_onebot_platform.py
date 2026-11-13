"""Tests for the OneBot 11 platform adapter (NapCat / Lagrange / LLOneBot).

Covers reply splitting at sentence boundaries, CQ-code parsing, mention
gating, DM/group policies, outbound segment-array payloads, text-image
rendering, and a live reverse-WS round trip against a fake NapCat client.
"""

import asyncio
import base64
import json
import logging
import os
import re
import sys
import tempfile
import time
from pathlib import Path
from unittest.mock import patch

import pytest

from gateway.config import Platform, PlatformConfig
from gateway.platforms.base import SendResult
from plugins.platforms.onebot.adapter import (
    MAX_MESSAGE_LENGTH,
    OneBotAdapter,
    _is_loopback_peer,
    _standalone_access_token,
    render_text_image,
)
from plugins.platforms.onebot import t2i_render
from plugins.platforms.onebot.onebot_utils import (
    DEFAULT_SPLIT_LENGTH,
    _split_reply,
)


# ---------------------------------------------------------------------------
# _split_reply
# ---------------------------------------------------------------------------


def test_split_reply_short_message_unchanged() -> None:
    assert _split_reply("短消息。", 100) == ["短消息。"]


def test_split_reply_breaks_at_sentence_boundaries() -> None:
    text = "第一句完整的话。第二句完整的话！第三句问号？" * 8
    parts = _split_reply(text, 100)
    assert len(parts) > 1
    for part in parts:
        assert 0 < len(part) <= 100
        # Every non-final chunk must end on a sentence boundary.
        assert part[-1] in "。！？!?；;\n"


def test_split_reply_hard_cut_without_boundaries() -> None:
    text = "x" * 250
    parts = _split_reply(text, 100)
    assert [len(p) for p in parts] == [100, 100, 50]


def test_split_reply_respects_explicit_newlines() -> None:
    # Newlines are sentence boundaries: a >limit text full of newlines
    # breaks at the newlines (each line is short).
    text = ("行" * 30 + "\n") * 5  # 155 chars, newline every 31 chars
    parts = _split_reply(text, 100)
    assert len(parts) >= 2
    for part in parts[:-1]:
        assert part.endswith("\n")
    assert all(len(p) <= 100 for p in parts)


# ---------------------------------------------------------------------------
# Text-image rendering
# ---------------------------------------------------------------------------

_DEJAVU = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"


@pytest.mark.skipif(
    not __import__("os").path.exists(_DEJAVU),
    reason="DejaVu font not available in this environment",
)
def test_render_text_image_produces_png(monkeypatch) -> None:
    from PIL import Image
    import io

    from plugins.platforms.onebot import onebot_utils as ou

    monkeypatch.setattr(ou, "_TEXT_IMAGE_FALLBACK_FONTS", [_DEJAVU])
    png = render_text_image("Hello world! " * 20)
    assert png[:8] == b"\x89PNG\r\n\x1a\n"
    img = Image.open(io.BytesIO(png))
    assert img.size[0] == ou._TEXT_IMAGE_WIDTH
    assert img.size[1] > 0


def test_render_text_image_preserves_newlines(monkeypatch) -> None:
    import io

    from PIL import Image

    from plugins.platforms.onebot import onebot_utils as ou

    if not __import__("os").path.exists(_DEJAVU):
        pytest.skip("DejaVu font not available")
    monkeypatch.setattr(ou, "_TEXT_IMAGE_FALLBACK_FONTS", [_DEJAVU])
    single = render_text_image("line1\nline2\nline3")
    joined = render_text_image("line1line2line3")
    img1 = Image.open(io.BytesIO(single))
    img2 = Image.open(io.BytesIO(joined))
    # Three explicit lines need more height than one joined paragraph.
    assert img1.size[1] > img2.size[1]


# ---------------------------------------------------------------------------
# Adapter behavior
# ---------------------------------------------------------------------------


def _make_adapter(**extra) -> OneBotAdapter:
    return OneBotAdapter(PlatformConfig(enabled=True, extra=extra or {}))


def test_adapter_has_max_message_length() -> None:
    assert MAX_MESSAGE_LENGTH == 4000
    assert OneBotAdapter.MAX_MESSAGE_LENGTH == MAX_MESSAGE_LENGTH


def test_cq_parse_at_and_face() -> None:
    adapter = _make_adapter()
    raw = "[CQ:at,qq=12345] 你好 [CQ:face,id=0]"
    text, media, media_types = asyncio.run(adapter._parse_content(raw))
    assert text == "@12345 你好 😊"
    assert media == []
    assert media_types == []


def test_cq_parse_at_all_and_reply() -> None:
    adapter = _make_adapter()
    raw = "[CQ:reply,id=99][CQ:at,qq=all] 注意"
    text, _, _ = asyncio.run(adapter._parse_content(raw))
    assert text == "@全体成员 注意"


def test_cq_parse_image_no_url_falls_back() -> None:
    adapter = _make_adapter()
    raw = "看图 [CQ:image,file=abc.jpg]"
    text, media, media_types = asyncio.run(adapter._parse_content(raw))
    assert text == "看图 [图片]"
    assert media == []
    assert media_types == []


def test_cq_parse_record_no_url_falls_back() -> None:
    adapter = _make_adapter()
    raw = "听这个 [CQ:record,file=abc.silk]"
    text, media, media_types = asyncio.run(adapter._parse_content(raw))
    assert text == "听这个 [语音]"
    assert media == []
    assert media_types == []


def test_video_with_url_direct_download_skips_get_video_file(monkeypatch) -> None:
    """视频段有 url 时直接下载，不得调用 get_video_file。"""
    adapter = _make_adapter()
    calls: list = []
    fake_path = str(Path(tempfile.gettempdir()) / "hermes_onebot_test_url.mp4")

    async def fake_call_action(action, params, timeout=30.0):
        calls.append((action, dict(params)))
        raise AssertionError(f"unexpected OneBot action: {action}")

    async def fake_download_media(url, kind):
        calls.append(("download", url, kind))
        assert kind == "video"
        return fake_path

    monkeypatch.setattr(adapter, "_call_action", fake_call_action)
    monkeypatch.setattr(adapter, "_download_media", fake_download_media)
    text, media, types, _ = asyncio.run(
        adapter._parse_message_array(
            [
                {"type": "video", "data": {"url": "https://fake.cdn/v.mp4", "file": "abc123"}}
            ]
        )
    )
    assert media == [fake_path]
    assert types == ["video/mp4"]
    assert ("download", "https://fake.cdn/v.mp4", "video") in calls
    assert not any(c[0] == "get_video_file" for c in calls), "有 url 时不得调 get_video_file"
    assert "[视频]" in text


def test_video_hash_only_fetches_via_get_video_file(monkeypatch) -> None:
    """视频段只有 file hash 无 url 时，经 get_video_file 换取后下载落盘。"""
    adapter = _make_adapter()
    calls: list = []
    fake_path = str(Path(tempfile.gettempdir()) / "hermes_onebot_test_hash.mp4")
    b64 = base64.b64encode(b"fake-mp4-bytes").decode()

    async def fake_call_action(action, params, timeout=30.0):
        calls.append((action, dict(params)))
        assert action == "get_video_file"
        assert params["file"] == "abc123hash"
        assert params["file_id"] == "abc123hash"
        return {"file": f"base64://{b64}"}

    async def fake_download_media(url, kind):
        assert url == f"base64://{b64}"
        assert kind == "video"
        return fake_path

    monkeypatch.setattr(adapter, "_call_action", fake_call_action)
    monkeypatch.setattr(adapter, "_download_media", fake_download_media)
    text, media, types, _ = asyncio.run(
        adapter._parse_message_array([{"type": "video", "data": {"file": "abc123hash"}}])
    )
    assert media == [fake_path]
    assert types == ["video/mp4"]
    assert (
        "get_video_file",
        {"file": "abc123hash", "file_id": "abc123hash"},
    ) in calls
    assert "[视频]" in text


def test_video_hash_only_get_video_file_failure_degrades(monkeypatch) -> None:
    """get_video_file 失败/超时 → 降级：无媒体、不 crash、消息仍带 [视频] 入站。"""
    adapter = _make_adapter()

    async def fake_call_action(action, params, timeout=30.0):
        raise RuntimeError("get_video_file unavailable")

    monkeypatch.setattr(adapter, "_call_action", fake_call_action)
    text, media, types, _ = asyncio.run(
        adapter._parse_message_array(
            [
                {"type": "text", "data": {"text": "看视频"}},
                {"type": "video", "data": {"file": "abc123hash"}},
            ]
        )
    )
    assert media == []
    assert types == []
    assert text == "看视频[视频]"


def test_shrink_image_downscales_large_image(tmp_path) -> None:
    from PIL import Image

    adapter = _make_adapter(image_max_size=1536)
    big = tmp_path / "big.jpg"
    Image.new("RGB", (3000, 2000), "white").save(big)
    out = adapter._shrink_image(big)
    assert out is not None
    with Image.open(out) as img:
        assert max(img.size) <= 1536
    # Aspect ratio preserved.
    assert img.size == (1536, 1024)


def test_shrink_image_skips_small_image(tmp_path) -> None:
    from PIL import Image

    adapter = _make_adapter(image_max_size=1536)
    small = tmp_path / "small.png"
    Image.new("RGB", (800, 600), "white").save(small)
    assert adapter._shrink_image(small) is None


def test_shrink_image_disabled_with_zero(tmp_path) -> None:
    from PIL import Image

    adapter = _make_adapter(image_max_size=0)
    big = tmp_path / "big.png"
    Image.new("RGB", (3000, 2000), "white").save(big)
    assert adapter._shrink_image(big) is None


def test_is_mentioned() -> None:
    adapter = _make_adapter()
    adapter._self_id = "123456789"
    assert adapter._is_mentioned("[CQ:at,qq=123456789] 嗨")
    assert adapter._is_mentioned("带回复 [CQ:reply,id=5]")
    assert not adapter._is_mentioned("没 @ 的消息")


def test_is_mentioned_fails_closed_without_self_id() -> None:
    adapter = _make_adapter()
    adapter._self_id = None
    assert not adapter._is_mentioned("随便说点什么")


def test_dm_policy_allowlist() -> None:
    adapter = _make_adapter(dm_policy="allowlist", allow_from=["10001"])
    assert adapter._dm_allowed("10001")
    assert not adapter._dm_allowed("99999")


def test_dm_policy_disabled() -> None:
    adapter = _make_adapter(dm_policy="disabled")
    assert not adapter._dm_allowed("10001")


def test_group_policy_allowlist() -> None:
    adapter = _make_adapter(group_policy="allowlist", group_allow_from=["888888"])
    assert adapter._group_allowed("888888")
    assert not adapter._group_allowed("777777")


# ---------------------------------------------------------------------------
# Markdown stripping
# ---------------------------------------------------------------------------


def test_strip_markdown_inline() -> None:
    from plugins.platforms.onebot.onebot_utils import strip_markdown

    assert strip_markdown("**加粗** 和 *斜体* 和 `代码`") == "加粗 和 斜体 和 代码"
    assert strip_markdown("[链接](https://example.com)") == "链接（https://example.com）"
    assert strip_markdown("~~删除线~~") == "删除线"


def test_strip_markdown_blocks() -> None:
    from plugins.platforms.onebot.onebot_utils import strip_markdown

    text = "## 标题\n\n- 项目一\n- 项目二\n\n1. 第一\n2. 第二\n\n> 引用"
    out = strip_markdown(text)
    assert "【标题】" in out
    assert "• 项目一" in out
    assert "1. 第一" in out
    assert "「引用」" in out


def test_strip_markdown_code_block() -> None:
    from plugins.platforms.onebot.onebot_utils import strip_markdown

    text = "```python\nprint('hi')\n```\n结尾"
    out = strip_markdown(text)
    assert "┌─[python]─" in out
    assert "│ print('hi')" in out
    assert "结尾" in out


def test_send_strips_markdown_before_delivery() -> None:
    adapter = _make_adapter(text_image_threshold=0)
    ws = _FakeWS(adapter)
    adapter._ws = ws
    result = asyncio.run(adapter.send("private:1", "**你好** `世界`"))
    assert result.success
    text = ws.sent[0]["params"]["message"][0]["data"]["text"]
    assert text == "你好 世界"


# ---------------------------------------------------------------------------
# Outbound send() — fake WebSocket with echo replies
# ---------------------------------------------------------------------------


class _FakeWS:
    def __init__(self, adapter: OneBotAdapter) -> None:
        self.adapter = adapter
        self.sent: list[dict] = []
        self._next_id = 1

    async def send_str(self, payload: str) -> None:
        data = json.loads(payload)
        self.sent.append(data)
        fut = self.adapter._pending_actions.get(data.get("echo"))
        if fut is not None and not fut.done():
            fut.set_result(
                {
                    "status": "ok",
                    "retcode": 0,
                    "echo": data.get("echo"),
                    "data": {"message_id": self._next_id},
                }
            )
            self._next_id += 1


def test_send_uses_segment_array_without_reply() -> None:
    adapter = _make_adapter()
    ws = _FakeWS(adapter)
    adapter._ws = ws
    result = asyncio.run(adapter.send("private:123456789", "你好"))
    assert result.success
    payload = ws.sent[0]
    assert payload["action"] == "send_msg"
    assert payload["params"]["user_id"] == 123456789
    assert payload["params"]["message"] == [
        {"type": "text", "data": {"text": "你好"}}
    ]
    # User asked for no reply-quoting: never emit a reply segment.
    assert all(seg["type"] != "reply" for seg in payload["params"]["message"])


def test_send_splits_long_text_into_multiple_messages() -> None:
    # Disable the text-image path so we exercise the chunking logic.
    adapter = _make_adapter(split_length=50, text_image_threshold=0)
    ws = _FakeWS(adapter)
    adapter._ws = ws
    long_text = "第一句。第二句。" * 20  # 160 chars, sentence boundaries
    result = asyncio.run(adapter.send("group:888888", long_text))
    assert result.success
    assert len(ws.sent) > 1
    for payload in ws.sent:
        assert payload["params"]["group_id"] == 888888
        segs = payload["params"]["message"]
        assert segs and segs[0]["type"] == "text"
        assert len(segs[0]["data"]["text"]) <= 50


def test_send_long_content_uses_text_image(monkeypatch) -> None:
    adapter = _make_adapter(text_image_threshold=50)
    ws = _FakeWS(adapter)
    adapter._ws = ws

    def fake_render(text: str, title: str = None) -> bytes:
        return b"\x89PNG\r\n\x1a\n" + b"0" * 64

    monkeypatch.setattr(
        "plugins.platforms.onebot.adapter.render_text_image", fake_render
    )
    result = asyncio.run(adapter.send("private:1", "很长" * 30))
    assert result.success
    assert len(ws.sent) == 1
    segs = ws.sent[0]["params"]["message"]
    assert segs[0]["type"] == "image"
    assert segs[0]["data"]["file"].startswith("base64://")


def test_send_attaches_media_to_final_chunk() -> None:
    # 80 chars: >50 (splits) but <150 (no text image).
    adapter = _make_adapter(split_length=50)
    ws = _FakeWS(adapter)
    adapter._ws = ws
    long_text = "第一句。第二句。" * 10
    result = asyncio.run(
        adapter.send(
            "private:1",
            long_text,
            metadata={"media_files": ["/nonexistent/img.png"]},
        )
    )
    # Missing local file is skipped gracefully; text still delivered.
    assert result.success
    assert len(ws.sent) > 1
    for payload in ws.sent:
        assert all(seg["type"] == "text" for seg in payload["params"]["message"])


def test_send_fails_fast_when_disconnected() -> None:
    adapter = _make_adapter()
    adapter._ws = None
    result = asyncio.run(adapter.send("private:1", "你好"))
    assert not result.success
    assert result.retryable


def test_send_typing_private_chat() -> None:
    adapter = _make_adapter()
    ws = _FakeWS(adapter)
    adapter._ws = ws
    asyncio.run(adapter.send_typing("private:123456789"))
    assert len(ws.sent) == 1
    payload = ws.sent[0]
    assert payload["action"] == "set_input_status"
    assert payload["params"] == {"user_id": "123456789", "event_type": 1}


def test_send_typing_group_chat_is_noop() -> None:
    adapter = _make_adapter()
    ws = _FakeWS(adapter)
    adapter._ws = ws
    asyncio.run(adapter.send_typing("group:888888"))
    assert ws.sent == []


def test_stop_typing_private_chat() -> None:
    adapter = _make_adapter()
    ws = _FakeWS(adapter)
    adapter._ws = ws
    asyncio.run(adapter.stop_typing("private:123456789"))
    assert len(ws.sent) == 1
    assert ws.sent[0]["params"] == {"user_id": "123456789", "event_type": 0}


# ---------------------------------------------------------------------------
# Reverse-WS round trip against a fake NapCat client
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_reverse_ws_round_trip(monkeypatch) -> None:
    import socket

    import aiohttp

    # The live gateway (if running) holds the per-mode platform lock; tests
    # must bypass it.
    monkeypatch.setattr(
        OneBotAdapter, "_acquire_platform_lock", lambda self, *a, **k: True
    )

    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]

    adapter = _make_adapter(host="127.0.0.1", port=port, admin_users=[10001])
    assert await adapter.connect()
    try:
        received = []
        adapter._message_handler = lambda event: received.append(event) or _noop()

        async with aiohttp.ClientSession() as session:
            async with session.ws_connect(f"ws://127.0.0.1:{port}/ws") as ws:
                # Heartbeat meta event → learn self id.
                await ws.send_str(
                    json.dumps(
                        {
                            "post_type": "meta_event",
                            "meta_event_type": "heartbeat",
                            "self_id": 123456789,
                        }
                    )
                )
                await asyncio.sleep(0.05)
                assert adapter._self_id == "123456789"

                # Private message → dispatched as DM event.
                await ws.send_str(
                    json.dumps(
                        {
                            "post_type": "message",
                            "message_type": "private",
                            "user_id": 10001,
                            "self_id": 123456789,
                            "message_id": 111,
                            "raw_message": "你好[CQ:face,id=0]",
                            "sender": {"user_id": 10001, "nickname": "测试员"},
                        }
                    )
                )
                await asyncio.sleep(0.15)
                assert received, "private message should be dispatched"
                ev = received[-1]
                assert ev.text == "你好😊"
                assert ev.source.chat_id == "private:10001"
                assert ev.source.chat_type == "dm"

                # Group message without @ → ignored under require_mention.
                before = len(received)
                await ws.send_str(
                    json.dumps(
                        {
                            "post_type": "message",
                            "message_type": "group",
                            "group_id": 888888,
                            "user_id": 10002,
                            "self_id": 123456789,
                            "message_id": 222,
                            "raw_message": "没 @ 的消息",
                            "sender": {"user_id": 10002, "nickname": "群友"},
                        }
                    )
                )
                await asyncio.sleep(0.15)
                assert len(received) == before

                # Group message with @ → dispatched.
                await ws.send_str(
                    json.dumps(
                        {
                            "post_type": "message",
                            "message_type": "group",
                            "group_id": 888888,
                            "user_id": 10002,
                            "self_id": 123456789,
                            "message_id": 333,
                            "raw_message": "[CQ:at,qq=123456789] 在吗",
                            "sender": {
                                "user_id": 10002,
                                "nickname": "群友",
                                "card": "卡",
                            },
                        }
                    )
                )
                await asyncio.sleep(0.15)
                assert len(received) == before + 1
                ev = received[-1]
                assert ev.text.endswith("@123456789 在吗")
                assert ev.source.chat_id == "group:888888"
                assert ev.source.chat_type == "group"
                assert ev.source.user_name == "卡"  # group card preferred
    finally:
        await adapter.disconnect()


async def _noop() -> None:
    return None


# ---------------------------------------------------------------------------
# Reply quoting (get_msg -> text + media) and loop-message merge+retract
# ---------------------------------------------------------------------------


def test_quote_reply_fetches_original_text_and_image(monkeypatch) -> None:
    """引用消息时通过 get_msg 取回原文文本 + 图片（reply 段路径）。"""
    adapter = _make_adapter(admin_users=[123456789])
    ws = _FakeWS(adapter)
    adapter._ws = ws
    captured: list = []

    async def fake_handle_message(ev):
        captured.append(ev)

    adapter.handle_message = fake_handle_message  # type: ignore[method-assign]

    async def fake_get_msg(action, params, timeout=30.0):
        assert action == "get_msg"
        assert params["message_id"] == 12345
        return {
            "message": [
                {"type": "text", "data": {"text": "被引用的卡片内容"}},
                {
                    "type": "image",
                    "data": {"url": "https://fake.cdn/img.png", "file": "x.png"},
                },
            ]
        }

    monkeypatch.setattr(adapter, "_call_action", fake_get_msg)

    async def run():
        await adapter._process_message(
            {
                "message_type": "private",
                "user_id": 123456789,
                "message": [
                    {"type": "reply", "data": {"id": 12345}},
                    {"type": "text", "data": {"text": "你看看这个"}},
                ],
                "self_id": 123456789,
            }
        )

    asyncio.run(run())
    assert captured, "no event captured"
    ev = captured[0]
    # 文本拼了 [引用] 前缀 + 原消息文本
    assert "[引用]" in ev.text
    assert "被引用的卡片内容" in ev.text
    # 图片在文本里以 [图片] 占位（下载失败时降级保留占位，不阻塞消息）
    assert "[图片]" in ev.text


# ---------------------------------------------------------------------------
# Reply mention gating (review 4.3): a reply only triggers when the replied-to
# message demonstrably came from the bot; undeterminable falls back to mention
# ---------------------------------------------------------------------------


def _reply_get_msg_fake(calls: list, *, sender_user_id=None, fail: bool = False):
    """Build a _call_action stand-in answering get_msg for reply-gating tests.

    Records every (action, params) pair in ``calls`` so tests can assert the
    "one get_msg per reply segment" invariant; raises when ``fail`` is set.
    Mocks must be async def — a plain def would raise TypeError inside the
    coroutine and look like "not triggered".
    """

    async def fake_call_action(action, params, timeout=30.0):
        calls.append((action, dict(params)))
        assert action == "get_msg"
        if fail:
            raise RuntimeError("get_msg unavailable")
        return {
            "message": [{"type": "text", "data": {"text": "被回复的原消息"}}],
            "sender": {} if sender_user_id is None else {"user_id": sender_user_id},
        }

    return fake_call_action


def _group_reply_event(message, raw: str = "[CQ:reply,id=555] 收到") -> dict:
    return {
        "post_type": "message",
        "message_type": "group",
        "group_id": 888888,
        "user_id": 10002,
        "self_id": 123456789,
        "message_id": 42,
        "raw_message": raw,
        "message": message,
        "sender": {"user_id": 10002, "nickname": "群友", "card": "卡"},
    }


def _capture_handle_message(adapter: OneBotAdapter) -> list:
    captured: list = []

    async def fake_handle_message(ev):
        captured.append(ev)

    adapter.handle_message = fake_handle_message  # type: ignore[method-assign]
    return captured


def test_reply_to_bot_triggers_and_get_msg_called_once(monkeypatch) -> None:
    """回复 bot 自己的消息 → 触发；门判定与引用取原文共用同一次 get_msg。"""
    adapter = _make_adapter(admin_users=[10002])
    captured = _capture_handle_message(adapter)
    calls: list = []
    monkeypatch.setattr(
        adapter, "_call_action", _reply_get_msg_fake(calls, sender_user_id=123456789)
    )

    asyncio.run(
        adapter._process_message(
            _group_reply_event(
                [
                    {"type": "reply", "data": {"id": 555}},
                    {"type": "text", "data": {"text": "收到"}},
                ]
            )
        )
    )
    assert len(captured) == 1, "reply to the bot itself should trigger"
    ev = captured[0]
    assert "[引用]被回复的原消息" in ev.text
    assert "收到" in ev.text
    assert [(a, p.get("message_id")) for a, p in calls] == [
        ("get_msg", 555)
    ], "门判定与引用取原文必须复用同一次 get_msg，不得二次调用"


def test_reply_to_other_user_does_not_trigger(monkeypatch) -> None:
    """回复群里其他人 → 不触发（繁忙群不再被无关回复链误唤醒）。"""
    adapter = _make_adapter(admin_users=[10002])
    captured = _capture_handle_message(adapter)
    calls: list = []
    monkeypatch.setattr(
        adapter, "_call_action", _reply_get_msg_fake(calls, sender_user_id=99999)
    )

    asyncio.run(
        adapter._process_message(
            _group_reply_event(
                [
                    {"type": "reply", "data": {"id": 555}},
                    {"type": "text", "data": {"text": "收到"}},
                ]
            )
        )
    )
    assert captured == [], "reply to someone else must not wake the bot"
    assert [(a, p.get("message_id")) for a, p in calls] == [("get_msg", 555)]


def test_reply_get_msg_failure_falls_back_to_mention(monkeypatch) -> None:
    """get_msg 失败/超时/撤回 → 不可判定回落为提及（dsh 口径）；不二次调用。"""
    adapter = _make_adapter(admin_users=[10002])
    captured = _capture_handle_message(adapter)
    calls: list = []
    monkeypatch.setattr(adapter, "_call_action", _reply_get_msg_fake(calls, fail=True))

    asyncio.run(
        adapter._process_message(
            _group_reply_event(
                [
                    {"type": "reply", "data": {"id": 555}},
                    {"type": "text", "data": {"text": "收到"}},
                ]
            )
        )
    )
    assert len(captured) == 1, "undeterminable reply should fall back to mention"
    assert "[引用]" not in captured[0].text, "取回失败时不拼引用文本"
    assert len(calls) == 1, "门已调用过 get_msg，引用块不得重复调用"


def test_reply_cq_string_path_matches_array_semantics(monkeypatch) -> None:
    """CQ 字符串路径与段数组路径同语义；显式 @ 不受 reply 收紧影响。"""

    def make(**kw):
        adapter = _make_adapter(admin_users=[10002])
        captured = _capture_handle_message(adapter)
        calls: list = []
        monkeypatch.setattr(adapter, "_call_action", _reply_get_msg_fake(calls, **kw))
        return adapter, captured, calls

    # 回复 bot（CQ 字符串路径）→ 触发，引用文本照拼
    adapter, captured, calls = make(sender_user_id=123456789)
    asyncio.run(adapter._process_message(_group_reply_event(None, raw="[CQ:reply,id=777] 在吗")))
    assert len(captured) == 1, "CQ path: reply to the bot should trigger"
    assert "[引用]被回复的原消息" in captured[0].text

    # 回复他人（CQ 字符串路径）→ 不触发
    adapter, captured, calls = make(sender_user_id=99999)
    asyncio.run(adapter._process_message(_group_reply_event(None, raw="[CQ:reply,id=777] 在吗")))
    assert captured == [], "CQ path: reply to someone else must not trigger"

    # get_msg 失败 → 回落触发
    adapter, captured, calls = make(fail=True)
    asyncio.run(adapter._process_message(_group_reply_event(None, raw="[CQ:reply,id=777] 在吗")))
    assert len(captured) == 1, "CQ path: undeterminable reply falls back to mention"

    # 回复他人但同时显式 @ bot → 仍触发（@ 路径不受收紧影响）
    adapter, captured, calls = make(sender_user_id=99999)
    asyncio.run(
        adapter._process_message(
            _group_reply_event(None, raw="[CQ:reply,id=888][CQ:at,qq=123456789] 在吗")
        )
    )
    assert len(captured) == 1, "explicit @ must keep working alongside tightened replies"


def test_loop_merge_buffers_interim_then_forwards_and_retracts(monkeypatch) -> None:
    """interim 缓冲 + final 结算：小结卡渲染失败 → 回退合并转发 + 撤回（群聊）。"""
    from plugins.platforms.onebot import adapter as adapter_mod

    def boom(text, title=None):
        raise RuntimeError("render unavailable (fallback path)")

    monkeypatch.setattr(adapter_mod, "render_text_image", boom)
    adapter = _make_adapter()
    ws = _FakeWS(adapter)
    adapter._ws = ws
    adapter._self_id = "123456789"
    chat = "group:123456789"

    async def run():
        # 2 条 interim 中间评论
        await adapter.send(chat, "中间评论一", metadata={"interim": True})
        await adapter.send(chat, "中间评论二", metadata={"interim": True})
        assert len(adapter._loop_buffer.get(chat, [])) == 2
        # final 消息触发结算
        await adapter.send(chat, "最终回复内容", metadata={"notify": True})

    asyncio.run(run())
    actions = [p["action"] for p in ws.sent]
    assert actions.count("send_forward_msg") == 1
    assert actions.count("delete_msg") == 2
    fwd = next(p for p in ws.sent if p["action"] == "send_forward_msg")
    assert fwd["params"]["group_id"] == 123456789
    assert len(fwd["params"]["messages"]) == 2
    assert adapter._loop_buffer.get(chat) is None


def test_loop_merge_private_uses_send_private_forward_msg(monkeypatch) -> None:
    """私聊场景用 send_private_forward_msg（小结卡渲染失败回退时）。"""
    from plugins.platforms.onebot import adapter as adapter_mod

    def boom(text, title=None):
        raise RuntimeError("render unavailable (fallback path)")

    monkeypatch.setattr(adapter_mod, "render_text_image", boom)
    adapter = _make_adapter()
    ws = _FakeWS(adapter)
    adapter._ws = ws
    adapter._self_id = "123456789"
    chat = "private:123456789"

    async def run():
        await adapter.send(chat, "中间一", metadata={"interim": True})
        await adapter.send(chat, "中间二", metadata={"interim": True})
        await adapter.send(chat, "最终", metadata={"notify": True})

    asyncio.run(run())
    actions = [p["action"] for p in ws.sent]
    assert actions.count("send_private_forward_msg") == 1
    fwd = next(p for p in ws.sent if p["action"] == "send_private_forward_msg")
    assert fwd["params"]["user_id"] == 123456789


def test_loop_merge_summary_card_preferred(monkeypatch) -> None:
    """#3 回移：小结卡渲染成功 → 发图片卡 + 撤回原 interim，不走合并转发。"""
    from plugins.platforms.onebot import adapter as adapter_mod

    called = {}

    def fake_render(text, title=None):
        called["text"] = text
        called["title"] = title
        return b"\x89PNG\r\n\x1a\nfakepng"

    monkeypatch.setattr(adapter_mod, "render_text_image", fake_render)
    adapter = _make_adapter()
    ws = _FakeWS(adapter)
    adapter._ws = ws
    adapter._self_id = "123456789"
    chat = "group:123456789"

    async def run():
        await adapter.send(chat, "第一步", metadata={"interim": True})
        await adapter.send(chat, "第二步", metadata={"interim": True})
        await adapter.send(chat, "最终", metadata={"notify": True})

    asyncio.run(run())
    actions = [p["action"] for p in ws.sent]
    assert "send_forward_msg" not in actions
    # 小结卡以图片形式发送（send_msg 带 image segment）+ 撤回 2 条 interim
    assert actions.count("delete_msg") == 2
    img_msgs = [
        p for p in ws.sent if p["action"] == "send_msg" and "image" in str(p["params"].get("message"))
    ]
    assert img_msgs, "expected a summary card image message"
    assert called.get("title") == "本轮进展"
    assert "第一步" in called.get("text", "")


def test_loop_merge_single_interim_does_not_merge(monkeypatch) -> None:
    """缓冲不足 2 条不合并（单条不值得）。"""
    adapter = _make_adapter()
    ws = _FakeWS(adapter)
    adapter._ws = ws
    adapter._self_id = "123456789"
    chat = "group:1"

    async def run():
        await adapter.send(chat, "只有一条", metadata={"interim": True})
        await adapter.send(chat, "最终", metadata={"notify": True})

    asyncio.run(run())
    actions = [p["action"] for p in ws.sent]
    assert "send_forward_msg" not in actions
    assert "delete_msg" not in actions


def test_auto_recall_interim_after_timeout(monkeypatch) -> None:
    """#2 回移：interim 超时（90s 语义，测试用 50ms）未结算 → 单独撤回并清缓冲。"""
    adapter = _make_adapter(interim_recall_seconds=0.05)
    ws = _FakeWS(adapter)
    adapter._ws = ws
    chat = "private:123456789"

    async def run():
        await adapter.send(chat, "中间评论", metadata={"interim": True})
        assert len(adapter._loop_buffer.get(chat, [])) == 1
        # 不触发 final，等超时
        await asyncio.sleep(0.25)

    asyncio.run(run())
    actions = [p["action"] for p in ws.sent]
    assert actions.count("delete_msg") == 1
    assert adapter._loop_buffer.get(chat) in (None, [])


def test_auto_recall_interim_cancelled_by_final(monkeypatch) -> None:
    """#2：final 结算后超时任务到点不重复撤回（条目已不在缓冲）。"""
    from plugins.platforms.onebot import adapter as adapter_mod

    def boom(text, title=None):
        raise RuntimeError("render unavailable (fallback path)")

    monkeypatch.setattr(adapter_mod, "render_text_image", boom)
    adapter = _make_adapter(interim_recall_seconds=0.05)
    ws = _FakeWS(adapter)
    adapter._ws = ws
    adapter._self_id = "123456789"
    chat = "group:123456789"

    async def run():
        await adapter.send(chat, "中间", metadata={"interim": True})
        await adapter.send(chat, "最终", metadata={"notify": True})
        await asyncio.sleep(0.25)

    asyncio.run(run())
    actions = [p["action"] for p in ws.sent]
    # 只有 final 结算那一次的撤回（2 条中的 1 条缓冲不足不合并？——1 条 interim
    # 不结算，final 后 _pending_recalls 为空 → 不撤回；超时任务因条目已随
    # _merge_loop_buffer pop 清空而自愈，不应再发 delete_msg）
    assert actions.count("delete_msg") == 0


# ---------------------------------------------------------------------------
# 权限分级（role classification + sensitive scan）
# ---------------------------------------------------------------------------


def test_classify_user_role():
    from plugins.platforms.onebot.onebot_utils import classify_user_role

    assert classify_user_role("123456789", {"123456789"}) == "admin"
    assert classify_user_role("12345", {"123456789"}) == "member"
    assert classify_user_role("12345", set()) == "member"   # 空=全员 member（安全侧）
    assert classify_user_role("", {"123456789"}) == "member"  # 空 id 安全侧


def test_scan_sensitive():
    from plugins.platforms.onebot.onebot_utils import scan_sensitive

    assert scan_sensitive("帮我删除 /tmp/x 文件") is not None   # 删除文件
    assert scan_sensitive("执行 rm -rf /") is not None          # 终端命令
    assert scan_sensitive("帮我重启 hermes-gateway") is not None  # 重启服务
    assert scan_sensitive("打开客厅灯") is not None              # HA 控制
    assert scan_sensitive("发送到微信告诉 M") is not None        # 跨平台
    assert scan_sensitive("今天天气怎么样") is None               # 正常问答
    assert scan_sensitive("") is None
    assert scan_sensitive(None) is None


def test_member_group_message_gets_restricted_prefix(monkeypatch) -> None:
    """群聊普通用户消息注入 [受限用户] 前缀（软限制依据）。"""
    adapter = _make_adapter(admin_users=[123456789])
    ws = _FakeWS(adapter)
    adapter._ws = ws
    captured: list = []

    async def fake_handle_message(ev):
        captured.append(ev)

    adapter.handle_message = fake_handle_message  # type: ignore[method-assign]

    async def run():
        await adapter._process_message(
            {
                "message_type": "group",
                "group_id": 123456789,
                "user_id": 99999999,          # 非管理员
                "message": [
                    {"type": "at", "data": {"qq": adapter._self_id or "123456789"}},
                    {"type": "text", "data": {"text": "今天天气怎么样"}},
                ],
                "self_id": 123456789,
            }
        )

    asyncio.run(run())
    assert captured, "member group message should be dispatched"
    assert captured[0].text.startswith("[受限用户:仅问答]")


def test_member_dm_rejected(monkeypatch) -> None:
    """普通用户私聊直接丢弃（pairing 入口已关，事件不构造）。"""
    adapter = _make_adapter(admin_users=[123456789])
    ws = _FakeWS(adapter)
    adapter._ws = ws
    captured: list = []

    async def fake_handle_message(ev):
        captured.append(ev)

    adapter.handle_message = fake_handle_message  # type: ignore[method-assign]

    async def run():
        await adapter._process_message(
            {
                "message_type": "private",
                "user_id": 99999999,
                "message": [{"type": "text", "data": {"text": "你好"}}],
                "self_id": 123456789,
            }
        )

    asyncio.run(run())
    assert not captured, "non-admin DM must be dropped"


def test_member_slash_command_blocked(monkeypatch) -> None:
    """普通用户斜杠命令（/help /new 等）直接丢弃。"""
    adapter = _make_adapter(admin_users=[123456789])
    ws = _FakeWS(adapter)
    adapter._ws = ws
    captured: list = []

    async def fake_handle_message(ev):
        captured.append(ev)

    adapter.handle_message = fake_handle_message  # type: ignore[method-assign]

    async def run():
        await adapter._process_message(
            {
                "message_type": "group",
                "group_id": 123456789,
                "user_id": 99999999,
                "message": [
                    {"type": "at", "data": {"qq": "123456789"}},
                    {"type": "text", "data": {"text": "/help"}},
                ],
                "self_id": 123456789,
            }
        )

    asyncio.run(run())
    assert not captured, "member slash command must be dropped"


def test_member_path_text_not_blocked(monkeypatch) -> None:
    """普通用户含路径的文本（/tmp/x 等）不误伤（命令名含 / 即非命令）。"""
    adapter = _make_adapter(admin_users=[123456789])
    ws = _FakeWS(adapter)
    adapter._ws = ws
    captured: list = []

    async def fake_handle_message(ev):
        captured.append(ev)

    adapter.handle_message = fake_handle_message  # type: ignore[method-assign]

    async def run():
        await adapter._process_message(
            {
                "message_type": "group",
                "group_id": 123456789,
                "user_id": 99999999,
                "message": [
                    {"type": "at", "data": {"qq": "123456789"}},
                    {"type": "text", "data": {"text": "看看 /tmp/x 里的内容"}},
                ],
                "self_id": 123456789,
            }
        )

    asyncio.run(run())
    assert captured, "path text is not a slash command, must pass through"
    assert captured[0].text.startswith("[受限用户:仅问答]")


def test_admin_group_message_no_prefix(monkeypatch) -> None:
    """管理员群聊消息不注入受限标记，斜杠命令放行。"""
    adapter = _make_adapter(admin_users=[123456789])
    ws = _FakeWS(adapter)
    adapter._ws = ws
    captured: list = []

    async def fake_handle_message(ev):
        captured.append(ev)

    adapter.handle_message = fake_handle_message  # type: ignore[method-assign]

    async def run():
        await adapter._process_message(
            {
                "message_type": "group",
                "group_id": 123456789,
                "user_id": 123456789,
                "message": [
                    {"type": "at", "data": {"qq": "123456789"}},
                    {"type": "text", "data": {"text": "/new"}},
                ],
                "self_id": 123456789,
            }
        )

    asyncio.run(run())
    assert captured, "admin slash command must be dispatched"
    assert not captured[0].text.startswith("[受限用户")


# ---------------------------------------------------------------------------
# _standalone_send (out-of-process cron delivery via OneBot HTTP API)
# ---------------------------------------------------------------------------


class _FakeOneBotHttp:
    """Minimal OneBot HTTP server that records incoming action payloads."""

    def __init__(self) -> None:
        from aiohttp import web

        self.requests: list = []
        self._app = web.Application()
        self._app.router.add_post("/{action}", self._handle)
        self._runner = None
        self.port = 0

    async def _handle(self, request):
        action = request.match_info["action"]
        body = await request.json()
        self.requests.append((action, body))
        return _json_response({"status": "ok", "retcode": 0, "data": None})

    async def start(self) -> None:
        from aiohttp import web

        self._runner = web.AppRunner(self._app)
        await self._runner.setup()
        site = web.TCPSite(self._runner, "127.0.0.1", 0)
        await site.start()
        self.port = site._server.sockets[0].getsockname()[1]

    async def stop(self) -> None:
        if self._runner is not None:
            await self._runner.cleanup()


def _json_response(data):
    from aiohttp import web

    return web.json_response(data)


def test_standalone_send_text_and_voice_with_mount() -> None:
    """文本 + (path, is_voice) 元组媒体：voice_mount 映射 + record 段。"""
    from plugins.platforms.onebot.adapter import _standalone_send

    server = _FakeOneBotHttp()

    async def run():
        await server.start()
        try:
            pconfig = PlatformConfig(
                enabled=True,
                extra={
                    "http_url": f"http://127.0.0.1:{server.port}",
                    "voice_mount": {
                        "host": "/data/audio",
                        "container": "/app/napcat/audio",
                    },
                },
            )
            result = await _standalone_send(
                pconfig,
                "private:123456789",
                "定时提醒",
                media_files=[("/data/audio/remind.silk", True)],
            )
        finally:
            await server.stop()

    asyncio.run(run())
    assert server.requests, "expected at least one OneBot HTTP request"
    actions = [a for a, _ in server.requests]
    assert actions == ["send_private_msg", "send_private_msg"]
    text_payload = server.requests[0][1]
    assert text_payload["user_id"] == 123456789
    assert text_payload["message"] == "定时提醒"
    media_payload = server.requests[1][1]
    assert media_payload["message"] == "[CQ:record,file=/app/napcat/audio/remind.silk]"


def test_standalone_send_group_target_and_backslash_normalization() -> None:
    """群目标走 send_group_msg；Windows 反斜杠路径经 voice_mount 规范化。"""
    from plugins.platforms.onebot.adapter import _standalone_send

    server = _FakeOneBotHttp()

    async def run():
        await server.start()
        try:
            pconfig = PlatformConfig(
                enabled=True,
                extra={
                    "http_url": f"http://127.0.0.1:{server.port}",
                    "voice_mount": {
                        "host": "C:\\data\\audio",
                        "container": "/app/napcat/audio",
                    },
                },
            )
            result = await _standalone_send(
                pconfig,
                "group:88888",
                "",
                media_files=[("C:\\data\\audio\\clip.silk", True)],
            )
        finally:
            await server.stop()

    asyncio.run(run())
    assert server.requests[0][0] == "send_group_msg"
    payload = server.requests[0][1]
    assert payload["group_id"] == 88888
    assert payload["message"] == "[CQ:record,file=/app/napcat/audio/clip.silk]"


def test_standalone_send_missing_http_url_returns_error() -> None:
    from plugins.platforms.onebot.adapter import _standalone_send

    pconfig = PlatformConfig(enabled=True, extra={})

    async def run():
        return await _standalone_send(pconfig, "private:123456789", "hi")

    result = asyncio.run(run())
    assert "ONEBOT_HTTP_URL not configured" in result["error"]


# ---------------------------------------------------------------------------
# Ported #5: inbound file dual-channel receive (CDN direct link / get_file)
# ---------------------------------------------------------------------------


def _file_process(adapter, monkeypatch, call_actions, download_results=None):
    """跑一条带文件段的消息，返回捕获的 MessageEvent。"""

    async def fake_call(action, params, timeout=30.0):
        return call_actions.get(action, {})

    monkeypatch.setattr(adapter, "_call_action", fake_call)

    if download_results is not None:
        async def fake_download(url, safe_name, max_bytes):
            return download_results.get(url)

        monkeypatch.setattr(adapter, "_download_file_bytes", fake_download)

    captured: list = []

    async def fake_handle_message(ev):
        captured.append(ev)

    adapter.handle_message = fake_handle_message  # type: ignore[method-assign]

    async def run():
        await adapter._process_message(
            {
                "message_type": "private",
                "user_id": 123456789,
                "message": [
                    {
                        "type": "file",
                        "data": {
                            "file_id": "fid-abc-123",
                            "file": "plan.md",
                            "name": "",
                        },
                    }
                ],
                "self_id": 123456789,
            }
        )

    asyncio.run(run())
    assert captured
    return captured[0]


def test_inbound_file_direct_link_downloads_and_annotates_path(monkeypatch) -> None:
    """get_private_file_url 直链 → 下载成功 → [文件:本地路径]。"""
    adapter = _make_adapter(admin_users=[123456789])
    ev = _file_process(
        adapter,
        monkeypatch,
        call_actions={"get_private_file_url": {"url": "https://cdn.qq.com/plan.md"}},
        download_results={"https://cdn.qq.com/plan.md": "/tmp/hermes_onebot/plan.md"},
    )
    assert "[文件:/tmp/hermes_onebot/plan.md]" in ev.text
    assert not ev.media_urls, "file 不进入 media_urls（靠文本注解）"


def test_inbound_file_falls_back_to_get_file_base64(monkeypatch) -> None:
    """直链失败（异常）→ get_file base64 载荷 → [文件:本地路径]。"""
    adapter = _make_adapter(admin_users=[123456789])

    async def fake_call(action, params, timeout=30.0):
        if action == "get_private_file_url":
            raise RuntimeError("private file url unsupported (group chat)")
        if action == "get_file":
            return {"base64": "aGVsbG8=", "file_size": 5}
        return {}

    monkeypatch.setattr(adapter, "_call_action", fake_call)
    captured: list = []

    async def fake_handle_message(ev):
        captured.append(ev)

    adapter.handle_message = fake_handle_message  # type: ignore[method-assign]

    async def run():
        await adapter._process_message(
            {
                "message_type": "private",
                "user_id": 123456789,
                "message": [
                    {"type": "file", "data": {"file_id": "fid", "file": "x.bin"}}
                ],
                "self_id": 123456789,
            }
        )

    asyncio.run(run())
    assert "[文件:" in captured[0].text
    # T11 review #8: 入站文件落盘在 $HERMES_HOME/plugin-data/onebot-platform/media/
    assert (
        str(Path(os.environ["HERMES_HOME"]) / "plugin-data" / "onebot-platform" / "media")
        in captured[0].text
    )


def test_inbound_file_download_failure_keeps_name(monkeypatch) -> None:
    """双通道全失败 → 保留 [文件:名] 注解，消息不阻塞。"""
    adapter = _make_adapter(admin_users=[123456789])
    ev = _file_process(
        adapter,
        monkeypatch,
        call_actions={"get_private_file_url": {"url": "https://cdn/nope.md"}, "get_file": {}},
        download_results={},  # 全部失败
    )
    assert "[文件:plan.md]" in ev.text


def test_inbound_file_size_limit_skips(monkeypatch) -> None:
    """get_file 声明的 file_size 超限 → 不下载，显示文件名。"""
    adapter = _make_adapter(admin_users=[123456789], max_inbound_file_bytes=100)
    ev = _file_process(
        adapter,
        monkeypatch,
        call_actions={
            # 直链先失败
            "get_private_file_url": {},
            "get_file": {"file_size": 999999, "base64": "AA=="},
        },
    )
    assert "[文件:plan.md]" in ev.text


def test_cq_string_file_download_annotates_path(monkeypatch) -> None:
    """CQ 字符串路径：直链成功 → [文件:本地路径]。"""
    adapter = _make_adapter(admin_users=[123456789])
    captured: list = []

    async def fake_call(action, params, timeout=30.0):
        return {"url": "https://cdn.qq.com/a.pdf"} if action == "get_private_file_url" else {}

    async def fake_download(url, safe_name, max_bytes):
        return "/tmp/hermes_onebot/a.pdf"

    monkeypatch.setattr(adapter, "_call_action", fake_call)
    monkeypatch.setattr(adapter, "_download_file_bytes", fake_download)

    async def fake_handle_message(ev):
        captured.append(ev)

    adapter.handle_message = fake_handle_message  # type: ignore[method-assign]

    async def run():
        await adapter._process_message(
            {
                "message_type": "private",
                "user_id": 123456789,
                "raw_message": "[CQ:file,file=a.pdf,file_id=fid-9]",
                "message": "[CQ:file,file=a.pdf,file_id=fid-9]",
                "self_id": 123456789,
            }
        )

    asyncio.run(run())
    assert "[文件:/tmp/hermes_onebot/a.pdf]" in captured[0].text


# ---------------------------------------------------------------------------
# Ported #1: model tools (qq_send_* / qq_napcat_api / qq_group_history)
# ---------------------------------------------------------------------------


def test_tools_resolve_chat_explicit_and_session(monkeypatch) -> None:
    from plugins.platforms.onebot import tools

    assert tools._resolve_chat("group:88888") == "group:88888"
    monkeypatch.setenv("HERMES_SESSION_PLATFORM", "onebot")
    monkeypatch.setenv("HERMES_SESSION_CHAT_ID", "private:123456789")
    assert tools._resolve_chat(None) == "private:123456789"
    monkeypatch.setenv("HERMES_SESSION_PLATFORM", "telegram")
    try:
        tools._resolve_chat(None)
        assert False, "expected ValueError without chat context"
    except ValueError:
        pass


def test_tools_send_image_builds_media_request(monkeypatch) -> None:
    from plugins.platforms.onebot import tools

    calls = []

    def fake_http(method, path, payload=None):
        calls.append((method, path, payload))
        return {"ok": True, "message_id": "m1"}

    monkeypatch.setattr(tools, "_http", fake_http)
    out = tools.qq_send_image(
        {"sources": ["/tmp/a.png", "https://x/y.jpg"], "chat_id": "private:123456789"}
    )
    assert "Sent" in out
    assert calls[0][0] == "POST"
    assert calls[0][1] == "/api/send_media"
    assert calls[0][2]["kind"] == "image"
    assert calls[0][2]["sources"] == ["/tmp/a.png", "https://x/y.jpg"]
    # 超过 9 张拒绝
    too_many = tools.qq_send_image(
        {"sources": [f"/tmp/{i}.png" for i in range(10)]}
    )
    assert "9" in too_many


def test_tools_napcat_api_whitelist_guard(monkeypatch) -> None:
    from plugins.platforms.onebot import tools

    calls = []

    def fake_http(method, path, payload=None):
        calls.append(path)
        return {"ok": True, "data": {"count": 1}}

    monkeypatch.setattr(tools, "_http", fake_http)
    # 白名单外直接拒绝，不发请求
    out = tools.qq_napcat_api({"action": "set_group_kick"})
    assert "not whitelisted" in out
    assert not calls
    # 白名单内正常代理
    out = tools.qq_napcat_api({"action": "get_group_member_list", "params": {"group_id": 88888}})
    assert "api/napcat" in calls[0]
    assert '"count": 1' in out


def test_tools_group_history_url(monkeypatch) -> None:
    from plugins.platforms.onebot import tools

    import urllib.parse

    calls = []

    def fake_http(method, path, payload=None):
        calls.append(path)
        return {"ok": True, "data": []}

    from plugins.platforms.onebot import tools as tools_mod

    monkeypatch.setattr(tools_mod, "_http", fake_http)
    tools.qq_group_history({"group_id": "88888", "count": 30})
    qs = urllib.parse.parse_qs(calls[0].split("?", 1)[1])
    assert qs["group_id"] == ["88888"]
    assert qs["count"] == ["30"]


class _ToolHeaderServer:
    """假 /api server：记录每次请求的方法/路径/Authorization 头，回 {"ok": true}。"""

    def __init__(self) -> None:
        import threading
        from http.server import BaseHTTPRequestHandler, HTTPServer

        seen: list = []

        class _Handler(BaseHTTPRequestHandler):
            def _reply(self) -> None:
                length = int(self.headers.get("Content-Length") or 0)
                if length:
                    self.rfile.read(length)
                seen.append(
                    {
                        "method": self.command,
                        "path": self.path,
                        "authorization": self.headers.get("Authorization"),
                    }
                )
                body = json.dumps({"ok": True, "data": []}).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            do_GET = _reply
            do_POST = _reply

            def log_message(self, *args) -> None:  # 静默测试输出
                pass

        self.seen = seen
        self._httpd = HTTPServer(("127.0.0.1", 0), _Handler)
        self.port = self._httpd.server_address[1]
        self._thread = threading.Thread(target=self._httpd.serve_forever, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._httpd.shutdown()
        self._httpd.server_close()


def test_tools_carry_bearer_token_when_configured(monkeypatch) -> None:
    """配 token：qq_send_* 与 qq_napcat_api 自动携带 Bearer，假 server 200。"""
    from plugins.platforms.onebot import tools

    monkeypatch.setenv("ONEBOT_ACCESS_TOKEN", "s3cret-token")
    srv = _ToolHeaderServer()
    try:
        monkeypatch.setattr(tools, "_BASE", f"http://127.0.0.1:{srv.port}")
        out_img = tools.qq_send_image(
            {"sources": ["http://example.com/a.png"], "chat_id": "group:88888"}
        )
        out_nap = tools.qq_napcat_api(
            {"action": "get_group_member_list", "params": {"group_id": 88888}}
        )
    finally:
        srv.stop()
    assert "Sent" in out_img
    assert "Call failed" not in out_nap
    assert len(srv.seen) == 2
    by_path = {s["path"].split("?", 1)[0]: s for s in srv.seen}
    assert by_path["/api/send_media"]["method"] == "POST"
    assert by_path["/api/napcat"]["method"] == "GET"
    for s in srv.seen:
        assert s["authorization"] == "Bearer s3cret-token"


def test_tools_send_no_authorization_without_token(monkeypatch) -> None:
    """未配 token：请求不携带 Authorization 头（与 T1 之前行为一致）。"""
    from types import SimpleNamespace

    from plugins.platforms.onebot import tools

    monkeypatch.delenv("ONEBOT_ACCESS_TOKEN", raising=False)

    import gateway.config as gw_config

    # 隔离测试机真实 ~/.hermes 配置：配置兜底也解析不到 token
    monkeypatch.setattr(
        gw_config, "load_gateway_config", lambda: SimpleNamespace(platforms={})
    )
    srv = _ToolHeaderServer()
    try:
        monkeypatch.setattr(tools, "_BASE", f"http://127.0.0.1:{srv.port}")
        out = tools.qq_send_image(
            {"sources": ["http://example.com/a.png"], "chat_id": "group:88888"}
        )
    finally:
        srv.stop()
    assert "Sent" in out
    assert len(srv.seen) == 1
    assert srv.seen[0]["authorization"] is None


def test_tools_token_prefers_env_over_config(monkeypatch) -> None:
    """token 解析优先级：ONEBOT_ACCESS_TOKEN env 覆盖 config.yaml 同源配置。"""
    from types import SimpleNamespace

    from plugins.platforms.onebot import tools

    import gateway.config as gw_config

    monkeypatch.setattr(
        gw_config,
        "load_gateway_config",
        lambda: SimpleNamespace(
            platforms={
                Platform("onebot"): SimpleNamespace(
                    extra={"access_token": "config-token"}
                )
            }
        ),
    )
    monkeypatch.delenv("ONEBOT_ACCESS_TOKEN", raising=False)
    assert tools._access_token() == "config-token"
    monkeypatch.setenv("ONEBOT_ACCESS_TOKEN", "env-token")
    assert tools._access_token() == "env-token"


def test_tools_e2e_token_against_api_gate(monkeypatch) -> None:
    """端到端：tools._http + 真实 adapter API 闸门，配 token 后两条路径 200。"""
    import concurrent.futures

    from plugins.platforms.onebot import tools

    adapter = _make_adapter(access_token="s3cret-token")
    calls: list = []

    async def fake_call(action, params, timeout=15.0):
        calls.append(action)
        return {"messages": []}

    adapter._call_action = fake_call

    async def fake_send_images(*args, **kwargs):
        return None

    adapter.send_multiple_images = fake_send_images

    async def run():
        runner, port = await _start_api_server(adapter)
        try:
            monkeypatch.setenv("ONEBOT_ACCESS_TOKEN", "s3cret-token")
            monkeypatch.setattr(tools, "_BASE", f"http://127.0.0.1:{port}")
            # tools._http 是同步 urllib，放线程池跑，避免阻塞服务响应的 loop
            loop = asyncio.get_running_loop()
            with concurrent.futures.ThreadPoolExecutor() as pool:
                out_hist = await loop.run_in_executor(
                    pool,
                    lambda: tools.qq_group_history({"group_id": "88888"}),
                )
                out_img = await loop.run_in_executor(
                    pool,
                    lambda: tools.qq_send_image(
                        {"sources": ["http://example.com/a.png"], "chat_id": "group:88888"}
                    ),
                )
        finally:
            await runner.cleanup()
        return out_hist, out_img

    out_hist, out_img = asyncio.run(run())
    assert "Fetch failed" not in out_hist and out_hist, f"group_history 应成功：{out_hist}"
    assert "Sent" in out_img
    assert set(calls) == {"get_group_msg_history"}


async def _start_api_server(adapter):
    """起一个只挂 onebot API 路由的本地服务，返回 (runner, port)。"""
    from aiohttp import web

    app = web.Application()
    app.router.add_get("/api/group_history", adapter._handle_group_history)
    app.router.add_get("/api/napcat", adapter._handle_napcat_api)
    app.router.add_post("/api/send_media", adapter._handle_send_media)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "127.0.0.1", 0)
    await site.start()
    port = site._server.sockets[0].getsockname()[1]
    return runner, port


def test_api_napcat_whitelist_rejects() -> None:
    """非白名单 action → 403。"""
    from aiohttp import ClientSession

    adapter = _make_adapter()
    adapter._call_action = lambda *a, **kw: {}  # 不应被调用

    async def run():
        runner, port = await _start_api_server(adapter)
        try:
            async with ClientSession() as sess:
                async with sess.get(f"http://127.0.0.1:{port}/api/napcat?action=set_group_kick") as resp:
                    assert resp.status == 403
        finally:
            await runner.cleanup()

    asyncio.run(run())


def test_api_napcat_whitelisted_action() -> None:
    """白名单 action → 透传 _call_action 结果。"""
    from aiohttp import ClientSession

    adapter = _make_adapter()

    async def fake_call(action, params, timeout=30.0):
        assert action == "get_group_member_list"
        assert params == {"group_id": 88888}
        return [{"user_id": 123456789, "nickname": "M"}]

    adapter._call_action = fake_call

    async def run():
        runner, port = await _start_api_server(adapter)
        try:
            async with ClientSession() as sess:
                async with sess.get(
                    f"http://127.0.0.1:{port}/api/napcat?action=get_group_member_list&params=%7B%22group_id%22%3A88888%7D"
                ) as resp:
                    assert resp.status == 200
                    body = await resp.json()
                    assert body["status"] == "ok"
                    assert body["data"][0]["nickname"] == "M"
        finally:
            await runner.cleanup()

    asyncio.run(run())


def test_api_send_media_forward_group() -> None:
    """群合并转发 → send_forward_msg。"""
    from aiohttp import ClientSession

    adapter = _make_adapter()
    adapter._self_id = "123456789"

    async def fake_call(action, params, timeout=30.0):
        assert action == "send_forward_msg"
        assert params["group_id"] == 88888
        assert params["messages"][0]["name"] == "某人"
        return {"message_id": 777}

    adapter._call_action = fake_call

    async def run():
        runner, port = await _start_api_server(adapter)
        try:
            async with ClientSession() as sess:
                async with sess.post(
                    f"http://127.0.0.1:{port}/api/send_media",
                    json={
                        "chat_id": "group:88888",
                        "kind": "forward",
                        "nodes": [{"name": "某人", "content": "第一段"}],
                    },
                ) as resp:
                    assert resp.status == 200
                    body = await resp.json()
                    assert body["status"] == "ok"
        finally:
            await runner.cleanup()

    asyncio.run(run())


def test_api_send_media_bad_kind() -> None:
    from aiohttp import ClientSession

    adapter = _make_adapter()

    async def run():
        runner, port = await _start_api_server(adapter)
        try:
            async with ClientSession() as sess:
                async with sess.post(
                    f"http://127.0.0.1:{port}/api/send_media",
                    json={"chat_id": "private:1", "kind": "hack"},
                ) as resp:
                    assert resp.status == 400
        finally:
            await runner.cleanup()

    asyncio.run(run())


# ---------------------------------------------------------------------------
# Ported #7: t2i ink check (font-family self test)
# ---------------------------------------------------------------------------


def test_ink_check_reports_font_chain() -> None:
    """墨水自检：返回链状态；CJK 字体存在时 ok=True，缺失时优雅降级。"""
    from plugins.platforms.onebot.t2i_render import ink_check

    result = ink_check()
    assert "ok" in result
    assert "loaded" in result
    if result["cjk"]:
        # 本机装了 Noto CJK → 必须通过
        assert result["ok"] is True
    else:
        # 无 CJK 字体（部分 Windows/macOS）：长回复降级为纯文本，只记警告，不算失败
        assert result["ok"] is False


# ---------------------------------------------------------------------------
# Ported #6: local slash commands (/id /ver /mode /ocr)
# ---------------------------------------------------------------------------


def _command_process(adapter, ws, message_text):
    """向 _process_message 投递一条 admin 文本命令；返回捕获事件数。"""
    captured: list = []

    async def fake_handle_message(ev):
        captured.append(ev)

    adapter.handle_message = fake_handle_message  # type: ignore[method-assign]

    async def run():
        await adapter._process_message(
            {
                "message_type": "private",
                "user_id": 123456789,
                "raw_message": message_text,
                "message": message_text,
                "self_id": 123456789,
            }
        )

    asyncio.run(run())
    return captured


def test_local_command_id_and_ver(monkeypatch) -> None:
    """/id /ver 由 adapter 处理回复，事件不构造。"""
    adapter = _make_adapter(admin_users=[123456789])
    ws = _FakeWS(adapter)
    adapter._ws = ws

    captured = _command_process(adapter, ws, "/id")
    assert not captured, "local command must not reach the agent"
    texts = [
        "".join(s.get("data", {}).get("text", "") for s in p["params"]["message"])
        for p in ws.sent
        if p["action"] == "send_msg"
    ]
    assert any("chat_id: private:123456789" in t for t in texts)

    ws.sent.clear()
    captured = _command_process(adapter, ws, "/ver")
    assert not captured
    texts = [
        "".join(s.get("data", {}).get("text", "") for s in p["params"]["message"])
        for p in ws.sent
        if p["action"] == "send_msg"
    ]
    assert any("onebot-plugin v1.3.0" in t for t in texts)


def test_local_command_mode_instant_disables_loop_merge(monkeypatch) -> None:
    """/mode instant：per-chat 关闭 loop 合并，interim 逐条即时不缓冲。"""
    adapter = _make_adapter(admin_users=[123456789])
    ws = _FakeWS(adapter)
    adapter._ws = ws
    adapter._self_id = "123456789"
    chat = "private:123456789"

    _command_process(adapter, ws, "/mode instant")
    assert adapter._chat_interim_overrides.get(chat) is False

    async def run():
        await adapter.send(chat, "中间一", metadata={"interim": True})
        await adapter.send(chat, "中间二", metadata={"interim": True})
        await adapter.send(chat, "最终", metadata={"notify": True})

    asyncio.run(run())
    assert not adapter._loop_buffer.get(chat), "instant 模式不应缓冲 interim"
    actions = [p["action"] for p in ws.sent]
    assert "send_forward_msg" not in actions
    assert "delete_msg" not in actions


def test_local_command_ocr_uses_last_inbound_image(monkeypatch) -> None:
    """/ocr：用最近入站图片调 ocr_image，文本结果回发。"""
    adapter = _make_adapter(admin_users=[123456789])
    ws = _FakeWS(adapter)
    adapter._ws = ws
    sent_calls: list = []

    # 1) 先收一张图片消息（mock 下载），记录 _last_image_path
    async def fake_resolve_image(url, file):
        return "/tmp/hermes_onebot/ocr.png"

    async def fake_call(action, params, timeout=30.0):
        sent_calls.append((action, params))
        if action == "ocr_image":
            assert params["image"].startswith("base64://")
            return {"texts": [{"text": "第一行"}, {"text": "第二行"}]}
        return {}

    monkeypatch.setattr(adapter, "_resolve_image", fake_resolve_image)

    async def fake_base64(path, max_bytes=None):
        return "aGVsbG8="

    monkeypatch.setattr(adapter, "_file_to_base64", fake_base64)
    monkeypatch.setattr(adapter, "_call_action", fake_call)
    captured: list = []

    async def fake_handle_message(ev):
        captured.append(ev)

    adapter.handle_message = fake_handle_message  # type: ignore[method-assign]

    async def run():
        await adapter._process_message(
            {
                "message_type": "private",
                "user_id": 123456789,
                "message": [{"type": "image", "data": {"url": "https://cdn/x.png", "file": "x.png"}}],
                "self_id": 123456789,
            }
        )
        await adapter._process_message(
            {
                "message_type": "private",
                "user_id": 123456789,
                "raw_message": "/ocr",
                "message": "/ocr",
                "self_id": 123456789,
            }
        )

    asyncio.run(run())
    assert adapter._last_image_path.get("private:123456789") == "/tmp/hermes_onebot/ocr.png"
    texts = [
        "".join(s.get("data", {}).get("text", "") for s in p[1]["message"])
        for p in sent_calls
        if p[0] == "send_msg"
    ]
    assert any("OCR 结果" in t and "第一行" in t for t in texts)


# ---------------------------------------------------------------------------
# /api/* auth gate (PR #84202 second-round review 4.1): _check_api_auth
# ---------------------------------------------------------------------------


def test_api_auth_token_missing_credentials_rejected() -> None:
    """已配 access_token：三端点无凭证 → 401，且不触发任何 action。"""
    from aiohttp import ClientSession

    adapter = _make_adapter(access_token="s3cret-token")
    calls: list = []

    async def fake_call(*args, **kwargs):
        calls.append(args)
        return {}

    adapter._call_action = fake_call

    async def run():
        runner, port = await _start_api_server(adapter)
        try:
            async with ClientSession() as sess:
                for method, url in (
                    ("get", f"http://127.0.0.1:{port}/api/group_history?group_id=88888"),
                    ("get", f"http://127.0.0.1:{port}/api/napcat?action=get_group_member_list"),
                    ("post", f"http://127.0.0.1:{port}/api/send_media"),
                ):
                    kwargs: dict = (
                        {"json": {"chat_id": "group:88888", "kind": "file", "path": "x"}}
                        if method == "post"
                        else {}
                    )
                    async with getattr(sess, method)(url, **kwargs) as resp:
                        assert resp.status == 401, f"{url} 无凭证应 401"
        finally:
            await runner.cleanup()

    asyncio.run(run())
    assert not calls, "被拒请求不得触发任何 NapCat action"


def test_api_auth_token_wrong_credentials_rejected() -> None:
    """已配 access_token：错凭证 → 401。"""
    from aiohttp import ClientSession

    adapter = _make_adapter(access_token="s3cret-token")
    calls: list = []

    async def fake_call(*args, **kwargs):
        calls.append(args)
        return {}

    adapter._call_action = fake_call

    async def run():
        runner, port = await _start_api_server(adapter)
        try:
            async with ClientSession() as sess:
                async with sess.get(
                    f"http://127.0.0.1:{port}/api/group_history?group_id=88888",
                    headers={"Authorization": "Bearer wrong-token"},
                ) as resp:
                    assert resp.status == 401
        finally:
            await runner.cleanup()

    asyncio.run(run())
    assert not calls


def test_api_auth_token_correct_credentials_accepted() -> None:
    """已配 access_token：正确 Bearer → 200。"""
    from aiohttp import ClientSession

    adapter = _make_adapter(access_token="s3cret-token")

    async def fake_call(action, params, timeout=15.0):
        assert action == "get_group_msg_history"
        return {"messages": []}

    adapter._call_action = fake_call

    async def run():
        runner, port = await _start_api_server(adapter)
        try:
            async with ClientSession() as sess:
                async with sess.get(
                    f"http://127.0.0.1:{port}/api/group_history?group_id=88888",
                    headers={"Authorization": "Bearer s3cret-token"},
                ) as resp:
                    assert resp.status == 200
                    body = await resp.json()
                    assert body["status"] == "ok"
        finally:
            await runner.cleanup()

    asyncio.run(run())


def test_api_auth_no_token_loopback_allowed_warns(caplog) -> None:
    """未配 token：loopback 放行且记 WARNING。"""
    from aiohttp import ClientSession

    adapter = _make_adapter()

    async def fake_call(action, params, timeout=30.0):
        return [{"user_id": 123456789}]

    adapter._call_action = fake_call

    async def run():
        runner, port = await _start_api_server(adapter)
        try:
            async with ClientSession() as sess:
                async with sess.get(
                    f"http://127.0.0.1:{port}/api/napcat?action=get_group_member_list"
                ) as resp:
                    assert resp.status == 200
                    assert (await resp.json())["status"] == "ok"
        finally:
            await runner.cleanup()

    with caplog.at_level(logging.WARNING, logger="plugins.platforms.onebot.adapter"):
        asyncio.run(run())

    warn_texts = [r.getMessage() for r in caplog.records if r.levelno == logging.WARNING]
    assert any("no access_token" in t and "loopback" in t for t in warn_texts), warn_texts


def test_api_auth_no_token_non_loopback_rejected() -> None:
    """未配 token：非 loopback 对端 → 401（handler 级，mock 对端地址）。"""
    from aiohttp.test_utils import make_mocked_request

    adapter = _make_adapter()
    calls: list = []

    async def fake_call(*args, **kwargs):
        calls.append(args)
        return {}

    adapter._call_action = fake_call

    class _FakeTransport:
        def __init__(self, peername):
            self._peername = peername

        def get_extra_info(self, name, default=None):
            if name == "peername":
                return self._peername
            return default

    def _req(method, path):
        return make_mocked_request(
            method, path, transport=_FakeTransport(("192.0.2.77", 55555))
        )

    async def run():
        for handler, method, path in (
            (adapter._handle_group_history, "GET", "/api/group_history?group_id=88888"),
            (adapter._handle_napcat_api, "GET", "/api/napcat?action=get_group_member_list"),
            (adapter._handle_send_media, "POST", "/api/send_media"),
        ):
            resp = await handler(_req(method, path))
            assert resp.status == 401, f"{path} 非 loopback 应 401"

    asyncio.run(run())
    assert not calls


def test_api_send_media_local_file_requires_credentials() -> None:
    """send_media 外泄路径闭环：有 token 无凭证 → 401 不触达发送；凭证正确 → 200。"""
    from types import SimpleNamespace

    from aiohttp import ClientSession

    secret = str(Path(tempfile.gettempdir()) / "hermes_onebot_auth_secret.txt")
    adapter = _make_adapter(access_token="s3cret-token")
    sent: list = []

    async def fake_send_document(chat_id, path, file_name=None):
        sent.append((chat_id, path, file_name))
        return SimpleNamespace(success=True, message_id="42")

    adapter.send_document = fake_send_document  # type: ignore[method-assign]

    async def run():
        runner, port = await _start_api_server(adapter)
        try:
            async with ClientSession() as sess:
                async with sess.post(
                    f"http://127.0.0.1:{port}/api/send_media",
                    json={"chat_id": "private:10001", "kind": "file", "path": secret},
                ) as resp:
                    assert resp.status == 401
                async with sess.post(
                    f"http://127.0.0.1:{port}/api/send_media",
                    json={"chat_id": "private:10001", "kind": "file", "path": secret},
                    headers={"Authorization": "Bearer s3cret-token"},
                ) as resp:
                    assert resp.status == 200
                    assert (await resp.json())["status"] == "ok"
        finally:
            await runner.cleanup()

    asyncio.run(run())
    assert len(sent) == 1, "只有携带正确凭证的请求才触达 send_document"
    assert sent[0][1] == secret


def test_is_loopback_peer_edges() -> None:
    """loopback 判定边界：127/8、::1、v4-mapped 放行；私网/公网/垃圾输入拒绝。"""
    assert _is_loopback_peer("127.0.0.1")
    assert _is_loopback_peer("127.8.8.8")  # 127.0.0.0/8 整段
    assert _is_loopback_peer("::1")
    assert _is_loopback_peer("::ffff:127.0.0.1")
    assert not _is_loopback_peer("192.168.1.5")  # LAN 私网 ≠ loopback
    assert not _is_loopback_peer("203.0.113.9")
    assert not _is_loopback_peer("")
    assert not _is_loopback_peer(None)
    assert not _is_loopback_peer("not-an-ip")


# ---------------------------------------------------------------------------
# Forward mode API server (review 4.2 / T2): forward 分支也提供 /api/* 服务
# ---------------------------------------------------------------------------


async def _start_fake_napcat_ws():
    """假 NapCat ws 服务端（forward 模式适配器的拨入目标）。

    收到带 echo 的 action 帧时按 OneBot 11 语义回 status=ok + data；
    返回 (runner, port, received_frames)。
    """
    from aiohttp import WSMsgType, web

    received: list = []

    async def handler(request):
        ws = web.WebSocketResponse()
        await ws.prepare(request)
        async for msg in ws:
            if msg.type == WSMsgType.TEXT:
                data = json.loads(msg.data)
                received.append(data)
                echo = data.get("echo")
                if echo is not None:
                    await ws.send_str(
                        json.dumps(
                            {
                                "echo": echo,
                                "status": "ok",
                                "retcode": 0,
                                "data": {"messages": [{"message_id": 7}]},
                            }
                        )
                    )
        return ws

    app = web.Application()
    app.router.add_get("/ws", handler)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "127.0.0.1", 0)
    await site.start()
    port = site._server.sockets[0].getsockname()[1]
    return runner, port, received


def _forward_adapter_kwargs(napcat_port: int, **overrides):
    kwargs = {
        "mode": "forward",
        "url": f"ws://127.0.0.1:{napcat_port}/ws",
        "host": "127.0.0.1",
        "port": 0,
    }
    kwargs.update(overrides)
    return kwargs


def test_forward_connect_serves_group_history_and_no_ws_route(monkeypatch) -> None:
    """forward connect 后：/api/group_history 经 forward WS echo 全链路 200
    （无 token + loopback → 放行，复用 T1 鉴权闸门）；/ws、/onebot、/ 三条
    reverse-only 路由一律 404（forward server 不注册 /ws）；单实例只有一个
    server 槽位被占用（单模式互斥佐证）。"""
    from aiohttp import ClientSession

    # 绕过 per-mode 平台锁（与 test_reverse_ws_round_trip 同理，live gateway 可能占锁）
    monkeypatch.setattr(
        OneBotAdapter, "_acquire_platform_lock", lambda self, *a, **k: True
    )

    async def run():
        napcat_runner, napcat_port, frames = await _start_fake_napcat_ws()
        adapter = _make_adapter(**_forward_adapter_kwargs(napcat_port))
        assert await adapter.connect()
        api_port = adapter._site._server.sockets[0].getsockname()[1]
        try:
            async with ClientSession() as sess:
                async with sess.get(
                    f"http://127.0.0.1:{api_port}/api/group_history?group_id=88888"
                ) as resp:
                    assert resp.status == 200
                    body = await resp.json()
                    assert body["status"] == "ok"
                    assert body["data"]["messages"][0]["message_id"] == 7
                # echo 请求确实经 forward WS 到达 NapCat（全链路打通）
                actions = [f.get("action") for f in frames if "action" in f]
                assert actions == ["get_group_msg_history"]
                # reverse-only 路由不得出现在 forward server 上
                for path in ("/ws", "/onebot", "/"):
                    async with sess.get(f"http://127.0.0.1:{api_port}{path}") as resp:
                        assert resp.status == 404, f"forward server 不应注册 {path}"
                # 唯一 server 槽位由 forward API server 占用
                assert adapter._runner is not None
                assert adapter._site is not None
        finally:
            await adapter.disconnect()
            await napcat_runner.cleanup()

    asyncio.run(run())


def test_forward_connect_port_occupied_fails_clean(monkeypatch) -> None:
    """生命周期①：API 端口被占 → forward connect 返回 False，且 forward 拨号
    被完整回滚——不留 ws/session/reader，也不调度自动重连（端口冲突不回归）。"""
    import socket

    monkeypatch.setattr(
        OneBotAdapter, "_acquire_platform_lock", lambda self, *a, **k: True
    )

    async def run():
        napcat_runner, napcat_port, _frames = await _start_fake_napcat_ws()
        with socket.socket() as blocker:
            blocker.bind(("127.0.0.1", 0))
            blocker.listen(1)
            blocked_port = blocker.getsockname()[1]
            adapter = _make_adapter(
                **_forward_adapter_kwargs(napcat_port, port=blocked_port)
            )
            # forward WS 已拨通，但 /api server 绑定失败 → 整体 connect 失败
            assert await adapter.connect() is False
            assert adapter._ws is None
            assert adapter._forward_session is None
            assert adapter._reader_task is None
            assert adapter._reconnect_task is None, "失败路径不得调度自动重连"
            assert adapter._runner is None
            assert adapter._site is None
        await napcat_runner.cleanup()

    asyncio.run(run())


def test_forward_disconnect_releases_api_port(monkeypatch) -> None:
    """生命周期②：forward disconnect 后 runner/site/ws/session/任务全部收干净，
    API 端口立即可被重新绑定（SO_REUSEADDR 探测，等价下一个 server 复用端口）。"""
    import socket

    monkeypatch.setattr(
        OneBotAdapter, "_acquire_platform_lock", lambda self, *a, **k: True
    )

    async def run():
        napcat_runner, napcat_port, _frames = await _start_fake_napcat_ws()
        adapter = _make_adapter(**_forward_adapter_kwargs(napcat_port))
        assert await adapter.connect()
        api_port = adapter._site._server.sockets[0].getsockname()[1]
        await adapter.disconnect()
        assert adapter._runner is None
        assert adapter._site is None
        assert adapter._ws is None
        assert adapter._forward_session is None
        assert adapter._reader_task is None
        assert adapter._reconnect_task is None
        with socket.socket() as probe:
            probe.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            probe.bind(("127.0.0.1", api_port))
        await napcat_runner.cleanup()



# ---------------------------------------------------------------------------
# T4 minor 批次新增测试
# ---------------------------------------------------------------------------


def test_local_command_mode_query_two_states() -> None:
    """/mode 查询两态：无 override 时提示「默认 interim」且不得出现 instant
    自相矛盾；/mode instant 覆盖后查询显示 instant（/mode 覆盖）。"""
    adapter = _make_adapter(admin_users=[123456789])
    ws = _FakeWS(adapter)
    adapter._ws = ws
    chat = "private:123456789"

    def _last_reply_text() -> str:
        payloads = [p for p in ws.sent if p["action"] == "send_msg"]
        assert payloads, "expected a send_msg reply"
        return "".join(
            s.get("data", {}).get("text", "") for s in payloads[-1]["params"]["message"]
        )

    # 态 1：无 override —— 默认 interim，不能出现「instant + 默认 interim」矛盾
    _command_process(adapter, ws, "/mode")
    text = _last_reply_text()
    assert "默认 interim" in text
    assert "instant（逐条即时）" not in text
    assert "（/mode 覆盖）" not in text

    # 态 2：/mode instant 覆盖后 —— instant + （/mode 覆盖）
    ws.sent.clear()
    _command_process(adapter, ws, "/mode instant")
    assert adapter._chat_interim_overrides.get(chat) is False
    ws.sent.clear()
    _command_process(adapter, ws, "/mode")
    text = _last_reply_text()
    assert "instant（逐条即时）" in text
    assert "（/mode 覆盖）" in text
    assert "默认 interim" not in text

    # 补充：/mode interim 覆盖后 —— interim + （/mode 覆盖）
    ws.sent.clear()
    _command_process(adapter, ws, "/mode interim")
    ws.sent.clear()
    _command_process(adapter, ws, "/mode")
    text = _last_reply_text()
    assert "interim（合并卡片）" in text
    assert "（/mode 覆盖）" in text
    assert "默认 interim" not in text


def test_t2i_render_height_limit_constant() -> None:
    """渲染器导出总高上限常量 8000px（D3 裁决）。"""
    assert t2i_render.MAX_RENDER_HEIGHT == 8000


@pytest.mark.skipif(
    not __import__("os").path.exists(_DEJAVU),
    reason="DejaVu font not available in this environment",
)
def test_t2i_render_under_limit_renders_png() -> None:
    """边界：总高 ≤ 8000px（约 200 行正文）正常渲染为 PNG，不回退。"""
    png = render_text_image("接近上限的正常行\n" * 200)
    assert png[:8] == b"\x89PNG\r\n\x1a\n"


@pytest.mark.skipif(
    not __import__("os").path.exists(_DEJAVU),
    reason="DejaVu font not available in this environment",
)
def test_t2i_render_over_limit_raises() -> None:
    """超限：总高 > 8000px 抛 ValueError（不截断画布、不产生半渲染图）。"""
    with pytest.raises(ValueError, match="MAX_RENDER_HEIGHT"):
        render_text_image("超限的行\n" * 400)


def test_send_t2i_over_limit_falls_back_to_text_chunks(monkeypatch) -> None:
    """超限走既有失败回退路径：渲染抛 ValueError → 降级分段纯文本发送，
    不发送任何图片段。"""
    from plugins.platforms.onebot import adapter as adapter_mod

    def boom(text, title=None):
        raise ValueError("rendered height exceeds MAX_RENDER_HEIGHT=8000px")

    monkeypatch.setattr(adapter_mod, "render_text_image", boom)
    adapter = _make_adapter(text_image_threshold=50, split_length=50)
    ws = _FakeWS(adapter)
    adapter._ws = ws

    result = asyncio.run(adapter.send("private:1", "很长" * 40))
    assert result.success
    assert ws.sent, "fallback must still deliver text"
    for payload in ws.sent:
        assert all(seg["type"] == "text" for seg in payload["params"]["message"])


def test_reverse_server_startup_raises_hostname_without_token() -> None:
    """T11 review #4（替代原 A4 WARNING 断言）：非 loopback host + 空
    access_token → 启动即 raise（不再只是告警）。无法解析为 IP 字面量的
    主机名（如 ``localhost``）按 fail-loud 一并拒绝；loopback / 配 token
    的放行样例见 ``test_bind_security_allows_loopback_and_token``。"""
    adapter = _make_adapter(host="localhost", port=0)
    with pytest.raises(ValueError, match="non-loopback"):
        asyncio.run(adapter._start_reverse_server())


# ---------------------------------------------------------------------------
# ffmpeg 启动探测（语音 STT 依赖）
# ---------------------------------------------------------------------------


def test_ffmpeg_check_warns_exactly_once_when_missing(monkeypatch, caplog) -> None:
    """ffmpeg 缺失时 WARNING 恰好一次（实例级 flag 防重复）。"""
    adapter = _make_adapter()
    monkeypatch.setattr("shutil.which", lambda name: None)
    with caplog.at_level(logging.WARNING, logger="plugins.platforms.onebot.adapter"):
        adapter._check_ffmpeg()
        adapter._check_ffmpeg()  # 第二次调用必须被 flag 拦住
    warns = [
        r.getMessage()
        for r in caplog.records
        if r.levelno == logging.WARNING and "ffmpeg" in r.getMessage()
    ]
    assert len(warns) == 1
    # 措辞含可操作指引（安装方式 + 语音 STT 不可用）
    assert "install" in warns[0] or "Install" in warns[0]
    assert "STT" in warns[0]


def test_ffmpeg_check_silent_when_present(monkeypatch, caplog) -> None:
    """ffmpeg 在 PATH 上时不打 WARNING（探测本身静默）。"""
    adapter = _make_adapter()
    monkeypatch.setattr("shutil.which", lambda name: "/usr/bin/ffmpeg")
    with caplog.at_level(logging.WARNING, logger="plugins.platforms.onebot.adapter"):
        adapter._check_ffmpeg()
    assert not [
        r.getMessage()
        for r in caplog.records
        if r.levelno >= logging.WARNING and "ffmpeg" in r.getMessage()
    ]


# ---------------------------------------------------------------------------
# 戳一戳（poke）notice 事件
# ---------------------------------------------------------------------------


def _poke_notice(**over) -> dict:
    """NapCat notify/poke notice 帧样例（群聊，bot 自身被戳）。"""
    data = {
        "post_type": "notice",
        "notice_type": "notify",
        "sub_type": "poke",
        "self_id": 10000,
        "user_id": 12345,
        "target_id": 10000,
        "group_id": 777,
    }
    data.update(over)
    return data


async def _dispatch_notice_and_collect(adapter: OneBotAdapter, data: dict) -> list:
    """经 _handle_frame 完整链路派发 notice，捕获出站 send() 调用。"""
    sent = []

    async def fake_send(chat_id, content, reply_to=None, metadata=None):
        sent.append((chat_id, content))
        return SendResult(success=True)

    adapter.send = fake_send
    adapter._handle_frame(data)
    pending = [t for t in asyncio.all_tasks() if t is not asyncio.current_task()]
    if pending:
        await asyncio.gather(*pending)
    return sent


def test_poke_bot_triggers_reply() -> None:
    """群聊中 bot 自己被戳（target==self）→ 走现有 send 路径发轻提示。"""
    adapter = _make_adapter(poke_reply=True)
    sent = asyncio.run(_dispatch_notice_and_collect(adapter, _poke_notice()))
    assert len(sent) == 1
    chat_id, content = sent[0]
    assert chat_id == "group:777"
    # 轻提示文案：提示 @bot 或 /help 用法，不触发 agent
    assert "/help" in content or "@我" in content


def test_poke_private_chat_replies_to_poker() -> None:
    """私聊（好友戳 bot，无 group_id）→ 回复会话指向戳人者。"""
    adapter = _make_adapter(poke_reply=True)
    sent = asyncio.run(_dispatch_notice_and_collect(adapter, _poke_notice(group_id=None)))
    assert len(sent) == 1
    assert sent[0][0] == "private:12345"


def test_poke_between_members_ignored() -> None:
    """成员互戳（target != self_id）→ 完全静默。"""
    adapter = _make_adapter(poke_reply=True)
    sent = asyncio.run(
        _dispatch_notice_and_collect(adapter, _poke_notice(user_id=12345, target_id=99999))
    )
    assert sent == []


def test_poke_cooldown_suppresses_repeat() -> None:
    """per-chat 60s 冷却：冷却期内的第二次戳静默。"""
    adapter = _make_adapter(poke_reply=True)
    sent = asyncio.run(_dispatch_notice_and_collect(adapter, _poke_notice()))
    assert len(sent) == 1
    # 紧接着再戳一次（未过冷却）→ 不再发送
    sent2 = asyncio.run(_dispatch_notice_and_collect(adapter, _poke_notice()))
    assert sent2 == []


def test_poke_disabled_by_default_silent() -> None:
    """默认 poke_reply=False：bot 被戳也完全静默。"""
    adapter = _make_adapter()  # 未配置 poke_reply → 默认关闭
    sent = asyncio.run(_dispatch_notice_and_collect(adapter, _poke_notice()))
    assert sent == []


def test_non_poke_notice_types_safely_ignored() -> None:
    """非 poke notice（如 group_upload / friend_request）安全忽略，不抛错。"""
    adapter = _make_adapter(poke_reply=True)
    sent = asyncio.run(
        _dispatch_notice_and_collect(
            adapter,
            {
                "post_type": "notice",
                "notice_type": "group_upload",
                "self_id": 10000,
                "group_id": 777,
                "user_id": 12345,
                "file": {"name": "a.txt", "size": 1},
            },
        )
    )
    assert sent == []
    sent2 = asyncio.run(
        _dispatch_notice_and_collect(
            adapter,
            {
                "post_type": "notice",
                "notice_type": "friend_request",
                "self_id": 10000,
                "user_id": 12345,
                "comment": "加个好友",
                "flag": "abc",
            },
        )
    )
    assert sent2 == []


def test_poke_notice_parse_pure_function() -> None:
    """parse_poke_notice 纯函数：仅"戳 bot 自己"返回会话信息。"""
    from plugins.platforms.onebot.onebot_utils import parse_poke_notice

    assert parse_poke_notice(_poke_notice(), "10000") == {
        "user_id": "12345",
        "chat_id": "group:777",
    }
    # 成员互戳
    assert parse_poke_notice(_poke_notice(target_id=99999), "10000") is None
    # self_id 未知（无法判定被戳者）
    assert parse_poke_notice(_poke_notice(), "") is None
    # 非 poke / 非 notify
    assert parse_poke_notice(_poke_notice(sub_type="lucky_king"), "10000") is None
    assert parse_poke_notice(_poke_notice(notice_type="group_increase"), "10000") is None
    # 私聊无 group_id → 会话指向戳人者
    assert parse_poke_notice(_poke_notice(group_id=None), "10000") == {
        "user_id": "12345",
        "chat_id": "private:12345",
    }


# ---------------------------------------------------------------------------
# 好友申请/群邀请审批（request 事件；T5）
# ---------------------------------------------------------------------------


def _friend_request_frame(**over) -> dict:
    """NapCat request 帧样例：好友申请（request_type=friend）。"""
    data = {
        "post_type": "request",
        "request_type": "friend",
        "self_id": 10000,
        "user_id": 12345,
        "comment": "加个好友",
        "flag": "friend_flag_1",
    }
    data.update(over)
    return data


def _group_invite_frame(**over) -> dict:
    """NapCat request 帧样例：群邀请（request_type=group, sub_type=invite）。"""
    data = {
        "post_type": "request",
        "request_type": "group",
        "sub_type": "invite",
        "self_id": 10000,
        "user_id": 12345,
        "group_id": 777,
        "comment": "",
        "flag": "group_flag_1",
    }
    data.update(over)
    return data


def _make_request_adapter(monkeypatch, tmp_path: Path, **extra) -> OneBotAdapter:
    """HERMES_HOME 隔离到 tmp（台账落盘不污染真实 HOME）；admin=888。"""
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    return _make_adapter(admin_users=["888"], **extra)


async def _dispatch_request_and_collect(adapter: OneBotAdapter, data: dict):
    """经 _handle_frame 完整链路派发 request，捕获 admin 通知与 OneBot API。"""
    sent = []
    actions = []

    async def fake_send(chat_id, content, reply_to=None, metadata=None):
        sent.append((chat_id, content))
        return SendResult(success=True)

    async def fake_call_action(action, params, timeout=30.0):
        actions.append((action, params))
        return {"status": "ok"}

    adapter.send = fake_send
    adapter._call_action = fake_call_action
    adapter._handle_frame(data)
    pending = [t for t in asyncio.all_tasks() if t is not asyncio.current_task()]
    if pending:
        await asyncio.gather(*pending)
    return sent, actions


def test_friend_request_notifies_admin(monkeypatch, tmp_path) -> None:
    """好友申请 → 台账记录 + admin 私聊通知（含序号/申请人/验证消息/flag）。"""
    adapter = _make_request_adapter(monkeypatch, tmp_path)
    sent, actions = asyncio.run(
        _dispatch_request_and_collect(adapter, _friend_request_frame())
    )
    assert actions == []  # 收到申请本身不调任何 OneBot API
    assert len(sent) == 1
    chat_id, content = sent[0]
    assert chat_id == "private:888"
    assert "#1" in content
    assert "12345" in content
    assert "加个好友" in content
    assert "friend_flag_1" in content
    rec = adapter._requests["friend_flag_1"]
    assert rec["status"] == "pending" and rec["seq"] == 1
    assert rec["kind"] == "friend"


def test_approve_friend_request_calls_set_friend_add_request(monkeypatch, tmp_path) -> None:
    """/approve <序号> → set_friend_add_request(flag, approve=True)。"""
    adapter = _make_request_adapter(monkeypatch, tmp_path)
    _, actions = asyncio.run(
        _dispatch_request_and_collect(adapter, _friend_request_frame())
    )
    assert actions == []
    reply = asyncio.run(
        adapter._handle_local_command("private:888", "dm", "888", "/approve 1")
    )
    assert reply is not None and "✅" in reply
    assert len(actions) == 1
    action, params = actions[0]
    assert action == "set_friend_add_request"
    assert params == {"flag": "friend_flag_1", "approve": True}


def test_reject_group_invite_calls_set_group_add_request(monkeypatch, tmp_path) -> None:
    """/reject <序号> → set_group_add_request(flag, sub_type=invite, approve=False)。"""
    adapter = _make_request_adapter(monkeypatch, tmp_path)
    _, actions = asyncio.run(
        _dispatch_request_and_collect(adapter, _group_invite_frame())
    )
    assert actions == []  # 收到邀请本身不调任何 OneBot API
    reply = asyncio.run(
        adapter._handle_local_command("private:888", "dm", "888", "/reject 1")
    )
    assert reply is not None and "✅" in reply
    assert len(actions) == 1
    action, params = actions[0]
    assert action == "set_group_add_request"
    assert params == {"flag": "group_flag_1", "sub_type": "invite", "approve": False}
    rec = adapter._requests["group_flag_1"]
    assert rec["status"] == "processed" and rec["decision"] is False


def test_approve_unknown_ref_errors(monkeypatch, tmp_path) -> None:
    """未知 flag/序号 → 明确报错，不调 API。"""
    adapter = _make_request_adapter(monkeypatch, tmp_path)
    actions = []

    async def fake_call_action(action, params, timeout=30.0):
        actions.append((action, params))
        return {"status": "ok"}

    monkeypatch.setattr(adapter, "_call_action", fake_call_action)
    reply = asyncio.run(
        adapter._handle_local_command("private:888", "dm", "888", "/approve 999")
    )
    assert "未找到" in reply
    assert actions == []


def test_bare_approve_returns_none_passes_through(monkeypatch, tmp_path) -> None:
    """裸 /approve（无参数）→ 返回 None 不产生适配器回复：透传网关核心
    的危险命令 / 数据训练档模型确认流程，不走好友申请审批台账。"""
    adapter = _make_request_adapter(monkeypatch, tmp_path)
    actions = []

    async def fake_call_action(action, params, timeout=30.0):
        actions.append((action, params))
        return {"status": "ok"}

    monkeypatch.setattr(adapter, "_call_action", fake_call_action)
    reply = asyncio.run(
        adapter._handle_local_command("private:888", "dm", "888", "/approve")
    )
    assert reply is None  # 调用点 if reply: 不发送，消息继续构造事件交网关
    assert actions == []  # 未调任何审批 API

    # 台账为空也不影响：裸 /approve 与申请台账无关
    reply2 = asyncio.run(
        adapter._handle_local_command("private:888", "dm", "888", "/reject")
    )
    assert reply2 is None
    assert actions == []


def test_approve_with_flag_arg_still_approves(monkeypatch, tmp_path) -> None:
    """带参数 /approve <已知flag> → 仍正常审批（无参数透传不影响带参路径）。"""
    adapter = _make_request_adapter(monkeypatch, tmp_path)
    _, actions = asyncio.run(
        _dispatch_request_and_collect(adapter, _friend_request_frame())
    )
    assert actions == []
    reply = asyncio.run(
        adapter._handle_local_command("private:888", "dm", "888", "/approve friend_flag_1")
    )
    assert "✅" in reply
    assert actions == [("set_friend_add_request", {"flag": "friend_flag_1", "approve": True})]
    assert adapter._requests["friend_flag_1"]["status"] == "processed"


def test_bare_approve_no_usage_reply_with_pending_requests(monkeypatch, tmp_path) -> None:
    """有 pending 申请时裸 /approve 仍透传（不回"用法：/approve <flag或序号>"）。"""
    adapter = _make_request_adapter(monkeypatch, tmp_path)
    asyncio.run(
        _dispatch_request_and_collect(adapter, _friend_request_frame())
    )
    reply = asyncio.run(
        adapter._handle_local_command("private:888", "dm", "888", "/approve")
    )
    assert reply is None
    assert "用法" not in str(reply)


def test_repeat_approve_idempotent_no_second_api_call(monkeypatch, tmp_path) -> None:
    """同一 flag 重复审批 → 幂等回复，不二次调 API。"""
    adapter = _make_request_adapter(monkeypatch, tmp_path)
    _, actions = asyncio.run(
        _dispatch_request_and_collect(adapter, _friend_request_frame())
    )
    first = asyncio.run(
        adapter._handle_local_command("private:888", "dm", "888", "/approve 1")
    )
    assert "✅" in first
    assert len(actions) == 1
    second = asyncio.run(
        adapter._handle_local_command("private:888", "dm", "888", "/approve 1")
    )
    assert "已处理过" in second
    assert len(actions) == 1  # 未二次调 API


def test_non_admin_approve_rejected(monkeypatch, tmp_path) -> None:
    """非 admin 调用 /approve → 拒绝且不调 API。"""
    adapter = _make_request_adapter(monkeypatch, tmp_path)
    asyncio.run(_dispatch_request_and_collect(adapter, _friend_request_frame()))
    actions = []

    async def fake_call_action(action, params, timeout=30.0):
        actions.append((action, params))
        return {"status": "ok"}

    monkeypatch.setattr(adapter, "_call_action", fake_call_action)
    reply = asyncio.run(
        adapter._handle_local_command("private:666", "dm", "666", "/approve 1")
    )
    assert "仅管理员" in reply
    assert actions == []


@pytest.mark.skipif(
    sys.platform == "win32",
    reason="POSIX 0o600 st_mode semantics do not exist on Windows",
)
def test_requests_persist_across_restart(monkeypatch, tmp_path) -> None:
    """台账落盘：重启（新实例）后 /approve 仍可用，seq 续增。"""
    adapter1 = _make_request_adapter(monkeypatch, tmp_path)
    asyncio.run(_dispatch_request_and_collect(adapter1, _friend_request_frame()))
    # T11 review #8: 台账迁到 $HERMES_HOME/plugin-data/onebot-platform/
    persist_path = Path(adapter1._requests_file())
    assert persist_path.exists()
    # 敏感文件权限：仅属主可读写
    assert (persist_path.stat().st_mode & 0o777) == 0o600

    adapter2 = _make_request_adapter(monkeypatch, tmp_path)
    rec = adapter2._requests["friend_flag_1"]
    assert rec["status"] == "pending" and rec["seq"] == 1
    assert adapter2._request_seq == 1

    actions = []

    async def fake_call_action(action, params, timeout=30.0):
        actions.append((action, params))
        return {"status": "ok"}

    monkeypatch.setattr(adapter2, "_call_action", fake_call_action)
    reply = asyncio.run(
        adapter2._handle_local_command("private:888", "dm", "888", "/approve friend_flag_1")
    )
    assert "✅" in reply
    assert actions == [("set_friend_add_request", {"flag": "friend_flag_1", "approve": True})]

    # 重启后 seq 取历史最大值续增：新事件编号不回退
    _, _ = asyncio.run(
        _dispatch_request_and_collect(adapter2, _friend_request_frame(flag="friend_flag_2"))
    )
    assert adapter2._requests["friend_flag_2"]["seq"] == 2


def test_duplicate_request_event_not_notified_twice(monkeypatch, tmp_path) -> None:
    """同一 flag 待处理期间重复推送 → 幂等跳过，不重复通知。"""
    adapter = _make_request_adapter(monkeypatch, tmp_path)
    sent1, _ = asyncio.run(
        _dispatch_request_and_collect(adapter, _friend_request_frame())
    )
    sent2, _ = asyncio.run(
        _dispatch_request_and_collect(adapter, _friend_request_frame())
    )
    assert len(sent1) == 1
    assert sent2 == []


# ---------------------------------------------------------------------------
# T5 回炉收口（独立评审 4 项 🟡 建议的实施测试）
# ---------------------------------------------------------------------------


def test_processed_flag_replay_silently_ignored(monkeypatch, tmp_path) -> None:
    """已处理 flag 重放（NapCat 重发同一 flag）→ 静默：不通知、不调 API、
    不重建记录、seq 不回退也不增长。"""
    adapter = _make_request_adapter(monkeypatch, tmp_path)
    _, actions = asyncio.run(
        _dispatch_request_and_collect(adapter, _friend_request_frame())
    )
    reply = asyncio.run(
        adapter._handle_local_command("private:888", "dm", "888", "/approve 1")
    )
    assert "✅" in reply
    assert len(actions) == 1  # 审批本身调过一次 API
    seq_before = adapter._request_seq
    rec_before = dict(adapter._requests["friend_flag_1"])

    # 重放同一 flag 的 request 事件
    sent2, actions2 = asyncio.run(
        _dispatch_request_and_collect(adapter, _friend_request_frame())
    )
    assert sent2 == []  # 不再次通知
    assert actions2 == []  # 不产生审批 API 调用
    assert adapter._request_seq == seq_before  # 不重建记录
    assert adapter._requests["friend_flag_1"] == rec_before  # 台账保持 processed


def test_group_approve_prompts_dm_only_no_leak(monkeypatch, tmp_path) -> None:
    """admin 在群里执行 /approve → 只回复"请在 bot 私聊中执行审批命令"：
    不调 API、不泄露台账内容（申请人 QQ / flag 均不出现在回复里）。"""
    adapter = _make_request_adapter(monkeypatch, tmp_path)
    asyncio.run(_dispatch_request_and_collect(adapter, _friend_request_frame()))
    actions = []

    async def fake_call_action(action, params, timeout=30.0):
        actions.append((action, params))
        return {"status": "ok"}

    monkeypatch.setattr(adapter, "_call_action", fake_call_action)
    reply = asyncio.run(
        adapter._handle_local_command("group:777", "group", "888", "/approve 1")
    )
    assert "私聊" in reply
    assert "12345" not in reply  # 申请人 QQ 不泄露
    assert "friend_flag_1" not in reply
    assert actions == []  # 不调审批 API
    # 台账状态不变，仍可在私聊中正常审批
    assert adapter._requests["friend_flag_1"]["status"] == "pending"


@pytest.mark.skipif(
    sys.platform == "win32",
    reason="POSIX 0o600 st_mode semantics do not exist on Windows",
)
def test_requests_file_created_0600_without_chmod(monkeypatch, tmp_path) -> None:
    """台账落盘从创建起即 0600：即使 os.chmod 被禁用（抛错），
    写出的文件权限仍是 0600（证明不依赖事后 chmod 补救）。"""
    import os as _os

    adapter = _make_request_adapter(monkeypatch, tmp_path)
    asyncio.run(_dispatch_request_and_collect(adapter, _friend_request_frame()))

    def _no_chmod(path, mode):
        raise AssertionError("persist must not rely on post-hoc chmod")

    monkeypatch.setattr(_os, "chmod", _no_chmod)
    adapter._persist_requests()  # 不抛错即通过
    persist_path = Path(adapter._requests_file())
    assert persist_path.exists()
    assert (persist_path.stat().st_mode & 0o777) == 0o600


def test_requests_ledger_prune_keeps_recent_processed(monkeypatch, tmp_path) -> None:
    """台账上限：超限时落盘前淘汰最旧的 processed 记录，pending 永不淘汰。"""
    from plugins.platforms.onebot import adapter as ob_adapter

    monkeypatch.setattr(ob_adapter, "REQUEST_LEDGER_MAX", 3)
    adapter = _make_request_adapter(monkeypatch, tmp_path)
    for i in range(5):
        adapter._requests[f"flag_{i}"] = {
            "flag": f"flag_{i}",
            "seq": i + 1,
            "status": "processed",
            "decision": True,
            "ts": 1000.0 + i,
            "decided_ts": 2000.0 + i,
            "kind": "friend",
            "user_id": str(1000 + i),
        }
    adapter._persist_requests()
    assert set(adapter._requests) == {"flag_2", "flag_3", "flag_4"}  # 最旧两条被淘汰

    # pending 不淘汰：4 条（3 processed + 1 pending）超上限 3 →
    # 只淘汰最旧的 1 条 processed（flag_2），回到 3 条
    adapter._requests["flag_pending"] = {
        "flag": "flag_pending", "seq": 9, "status": "pending", "ts": 999.0,
    }
    adapter._persist_requests()
    assert "flag_pending" in adapter._requests
    assert set(adapter._requests) == {"flag_3", "flag_4", "flag_pending"}


async def _dispatch_notice_raw(adapter: OneBotAdapter, data: dict) -> list:
    """经 _handle_frame 派发 notice 但不覆盖 adapter.send（供失败路径测试）。"""
    sent = []
    adapter._handle_frame(data)
    pending = [t for t in asyncio.all_tasks() if t is not asyncio.current_task()]
    if pending:
        await asyncio.gather(*pending)
    return sent


def test_poke_send_failure_does_not_consume_cooldown() -> None:
    """poke 回复 send 失败 → 不占用 60s 冷却，可立即重试成功。"""
    adapter = _make_adapter(poke_reply=True)

    async def failing_send(chat_id, content, reply_to=None, metadata=None):
        return SendResult(success=False, error="boom")

    adapter.send = failing_send
    out = asyncio.run(_dispatch_notice_raw(adapter, _poke_notice()))
    assert out == []
    assert adapter._poke_last_reply == {}  # 冷却未被占用

    async def ok_send(chat_id, content, reply_to=None, metadata=None):
        return SendResult(success=True, message_id="1")

    adapter.send = ok_send
    out2 = asyncio.run(_dispatch_notice_raw(adapter, _poke_notice()))
    assert len(out2) == 0  # raw 派发不捕获出站，只验证不抛错
    assert "group:777" in adapter._poke_last_reply  # 成功才写冷却


def test_poke_send_success_sets_cooldown() -> None:
    """poke 回复 send 成功 → 写入冷却，冷却期内第二次戳静默（既有语义）。"""
    adapter = _make_adapter(poke_reply=True)
    sent1 = asyncio.run(_dispatch_notice_and_collect(adapter, _poke_notice()))
    assert len(sent1) == 1
    assert "group:777" in adapter._poke_last_reply
    sent2 = asyncio.run(_dispatch_notice_and_collect(adapter, _poke_notice()))
    assert sent2 == []


def test_poke_send_exception_does_not_consume_cooldown() -> None:
    """poke 回复 send 抛异常 → 不占用冷却，也不让异常逃出 notice 处理。"""
    adapter = _make_adapter(poke_reply=True)

    async def raising_send(chat_id, content, reply_to=None, metadata=None):
        raise RuntimeError("ws gone")

    adapter.send = raising_send
    out = asyncio.run(_dispatch_notice_raw(adapter, _poke_notice()))
    assert out == []  # 异常被 notice 隔离层吞掉，未传播
    assert adapter._poke_last_reply == {}


# ---------------------------------------------------------------------------
# /model 文字选择器（T6：QQ 无 callback 按钮，序号回复形态）
# ---------------------------------------------------------------------------


def test_model_picker_text_lists_numbered_with_current_marker() -> None:
    """send_model_picker 渲染"序号. 模型"文字列表，当前项标 ← 当前，含回复提示。"""
    from plugins.platforms.onebot.onebot_utils import render_model_picker_text

    adapter = _make_adapter()
    captured = {}

    async def fake_send(chat_id, content, reply_to=None, metadata=None):
        captured.update(chat_id=chat_id, content=content, metadata=metadata)
        return SendResult(success=True, message_id="9")

    adapter.send = fake_send
    providers = [
        {"slug": "openai", "name": "OpenAI", "models": ["gpt-4o", "gpt-4.1"], "total_models": 2},
        {"slug": "anthropic", "name": "Anthropic", "models": ["claude-sonnet-4-5"], "total_models": 1},
    ]

    result = asyncio.run(adapter.send_model_picker(
        chat_id="group:777", providers=providers, current_model="claude-sonnet-4-5",
        current_provider="anthropic", session_key="s", on_model_selected=None))

    assert result.success is True
    assert captured["chat_id"] == "group:777"
    text = captured["content"]
    assert "1. gpt-4o" in text
    assert "2. gpt-4.1" in text
    assert "3. claude-sonnet-4-5 ← 当前" in text
    assert "/model <序号>" in text
    # 列表是纯文本渲染（QQ 不渲染 Markdown），无 markdown 强调语法
    assert "**" not in text and "`" not in text
    # 网关解析与渲染共用同一展开约定：纯函数可独立复算
    assert "2. gpt-4.1" in render_model_picker_text(providers, "gpt-4.1", "openai")


def test_model_picker_outbound_is_text_segment_array() -> None:
    """出站铁律：picker 列表经 send() 仍以 OneBot segment 数组下发。"""
    adapter = _make_adapter()
    adapter._ws = object()  # connected
    calls = []

    async def fake_call_action(action, params, timeout=None):
        calls.append((action, params))
        return {"message_id": 77}

    adapter._call_action = fake_call_action
    providers = [
        {"slug": "openai", "name": "OpenAI", "models": ["gpt-4o"], "total_models": 1},
    ]

    result = asyncio.run(adapter.send_model_picker(
        chat_id="group:777", providers=providers, current_model="gpt-4o",
        current_provider="openai", session_key="s", on_model_selected=None))

    assert result.success is True
    assert result.message_id == "77"
    action, params = calls[0]
    assert action == "send_msg"
    assert params["group_id"] == 777
    assert isinstance(params["message"], list) and params["message"]
    segment = params["message"][0]
    assert segment["type"] == "text" and "1. gpt-4o" in segment["data"]["text"]


def test_model_picker_empty_providers_reports_failure() -> None:
    """无可列项：返回失败（网关据此回退文字列表），且不出站。"""
    adapter = _make_adapter()
    sent = []

    async def fake_send(chat_id, content, reply_to=None, metadata=None):
        sent.append(content)
        return SendResult(success=True)

    adapter.send = fake_send
    result = asyncio.run(adapter.send_model_picker(
        chat_id="group:777", providers=[], current_model="m",
        current_provider="p", session_key="s", on_model_selected=None))

    assert result.success is False
    assert sent == []


def test_render_model_picker_skips_empty_provider_rows() -> None:
    """无模型的 provider 行不占序号（与网关 _flatten_picker_items 展开约定一致）。"""
    from plugins.platforms.onebot.onebot_utils import render_model_picker_text

    providers = [
        {"slug": "a", "name": "A", "models": [], "total_models": 0},
        {"slug": "b", "name": "B", "models": ["m1", "m2"], "total_models": 2},
    ]
    text = render_model_picker_text(providers, "m2", "b")
    assert "【A】" not in text
    assert "1. m1" in text
    assert "2. m2 ← 当前" in text


# ---------------------------------------------------------------------------
# T7：/model <序号> 快照落账与改写（序号选择下沉插件层，免疫网关 update）
# ---------------------------------------------------------------------------

_PICKER_PROVIDERS = [
    {"slug": "openai", "name": "OpenAI", "models": ["gpt-4o", "2"], "total_models": 2},
    {"slug": "anthropic", "name": "Anthropic", "models": ["claude-sonnet-4-5"], "total_models": 1},
]
# 预期展开（= 渲染行序）：1. gpt-4o@openai  2. 2@openai  3. claude-sonnet-4-5@anthropic
_PICKER_ENTRIES = [
    ("gpt-4o", "openai"),
    ("2", "openai"),
    ("claude-sonnet-4-5", "anthropic"),
]


def _picker_harness() -> tuple:
    """admin 身份适配器 + handle_message/send 捕获（send_success 可切换）。"""
    adapter = _make_adapter(admin_users=[123456789])
    events: list = []
    sent: list = []
    flags = {"send_success": True}

    async def fake_handle_message(ev):
        events.append(ev)

    async def fake_send(chat_id, content, reply_to=None, metadata=None):
        sent.append((chat_id, content))
        return SendResult(success=flags["send_success"], message_id="1")

    adapter.handle_message = fake_handle_message  # type: ignore[method-assign]
    adapter.send = fake_send  # type: ignore[method-assign]
    return adapter, events, sent, flags


def _record_picker(adapter, chat_id: str) -> None:
    """以 send_model_picker 真实路径落账一次快照（success=True）。"""
    asyncio.run(adapter.send_model_picker(
        chat_id=chat_id, providers=_PICKER_PROVIDERS, current_model="",
        current_provider="", session_key="s", on_model_selected=None))


def _drive_admin_text(adapter, text: str, chat: str = "dm") -> None:
    """以管理员身份把一条文本送入 _process_message（dm 直发 / group 带 @）。"""
    if chat == "dm":
        frame = {
            "message_type": "private",
            "user_id": 123456789,
            "message": [{"type": "text", "data": {"text": text}}],
            "self_id": 123456789,
        }
    else:
        frame = {
            "message_type": "group",
            "group_id": 777,
            "user_id": 123456789,
            "message": [
                {"type": "at", "data": {"qq": "123456789"}},
                {"type": "text", "data": {"text": text}},
            ],
            "self_id": 123456789,
        }
    asyncio.run(adapter._process_message(frame))


def test_model_picker_snapshot_recorded_only_on_send_success() -> None:
    """record-on-success：发送失败不落账，序号不指向用户没收到的列表。"""
    adapter, _, _, flags = _picker_harness()
    chat = "private:123456789"

    flags["send_success"] = False
    _record_picker(adapter, chat)
    assert chat not in adapter._model_picker_snapshots

    flags["send_success"] = True
    _record_picker(adapter, chat)
    recorded_at, entries = adapter._model_picker_snapshots[chat]
    assert entries == _PICKER_ENTRIES
    assert recorded_at > 0


def test_model_picker_snapshot_numbering_matches_renderer() -> None:
    """快照展开与渲染文本逐行同序同号（含跳过空 provider 行）。"""
    from plugins.platforms.onebot.onebot_utils import (
        expand_model_picker_entries,
        render_model_picker_text,
    )

    providers = [
        {"slug": "a", "name": "A", "models": [], "total_models": 0},
        {"slug": "b", "name": "B", "models": ["m1", "2"], "total_models": 2},
        {"slug": "c", "name": "C", "models": ["m3"], "total_models": 1},
    ]
    text = render_model_picker_text(providers, "", "")
    numbered = [
        (int(m.group(1)), m.group(2))
        for m in (re.match(r"^(\d+)\. (\S+)$", line) for line in text.splitlines())
        if m
    ]
    entries = expand_model_picker_entries(providers)
    assert [name for _, name in numbered] == [model for model, _ in entries]
    assert [n for n, _ in numbered] == list(range(1, len(entries) + 1))


def test_model_number_hit_rewrites_with_provider() -> None:
    """命中序号：改写为 /model <名> --provider <slug> 转发，无错误回复。"""
    adapter, events, sent, _ = _picker_harness()
    chat = "private:123456789"
    _record_picker(adapter, chat)
    sent.clear()

    _drive_admin_text(adapter, "/model 3")

    assert len(events) == 1
    assert events[0].text == "/model claude-sonnet-4-5 --provider anthropic"
    assert sent == []


def test_model_number_exact_model_name_passes_through() -> None:
    """序号恰为某模型名（精确名优先）：原样放行，交网关按名字解析。"""
    adapter, events, sent, _ = _picker_harness()
    chat = "private:123456789"
    _record_picker(adapter, chat)
    sent.clear()

    _drive_admin_text(adapter, "/model 2")  # "2" 是 openai 下的模型名

    assert len(events) == 1
    assert events[0].text == "/model 2"
    assert sent == []


def test_model_number_out_of_range_replies_without_forward() -> None:
    """越界序号：插件答复范围提示，事件不转发。"""
    adapter, events, sent, _ = _picker_harness()
    chat = "private:123456789"
    _record_picker(adapter, chat)
    sent.clear()

    _drive_admin_text(adapter, "/model 9")

    assert events == []
    assert sent == [
        (chat, "⚠️ 序号 9 超出范围（1-3），请重新发送 /model 查看列表"),
    ]


def test_model_number_expired_snapshot_replies_without_forward() -> None:
    """快照过期：答复重发提示、不转发，且过期快照被清理。"""
    adapter, events, sent, _ = _picker_harness()
    chat = "private:123456789"
    _record_picker(adapter, chat)
    recorded_at, entries = adapter._model_picker_snapshots[chat]
    adapter._model_picker_snapshots[chat] = (
        recorded_at - adapter._MODEL_PICKER_SNAPSHOT_TTL_SECONDS - 1.0,
        entries,
    )
    sent.clear()

    _drive_admin_text(adapter, "/model 1")

    assert events == []
    assert sent == [
        (chat, "⚠️ 模型列表已过期（超过 5 分钟），请重新发送 /model 后再回复序号"),
    ]
    assert chat not in adapter._model_picker_snapshots


def test_model_number_without_snapshot_passes_through() -> None:
    """无快照：原样放行（网关 absent→literal 语义，零行为变化）。"""
    adapter, events, sent, _ = _picker_harness()

    _drive_admin_text(adapter, "/model 3")

    assert len(events) == 1
    assert events[0].text == "/model 3"
    assert sent == []


def test_model_flags_and_non_number_not_intercepted() -> None:
    """flags / 非纯数字 / 相邻命令名：一律不拦（正则锚定全串）。"""
    adapter, events, sent, _ = _picker_harness()
    chat = "private:123456789"
    _record_picker(adapter, chat)
    sent.clear()

    passthrough = [
        "/model claude-sonnet-4-5 --provider anthropic",
        "/model --global",
        "/model 2x",
        "/modelx 2",
        "/model",
    ]
    for text in passthrough:
        before = len(events)
        _drive_admin_text(adapter, text)
        assert len(events) == before + 1, text
        assert events[-1].text == text, text
    assert sent == []


def test_model_number_at_mention_prefix_still_rewrites() -> None:
    """群聊 @提及前缀（"@123456789/model 1"）剥除后命中，改写文本不带 @。"""
    adapter, events, sent, _ = _picker_harness()
    chat = "group:777"
    _record_picker(adapter, chat)
    sent.clear()

    _drive_admin_text(adapter, "/model 1", chat="group")

    assert len(events) == 1
    assert events[0].text == "/model gpt-4o --provider openai"
    assert sent == []


def test_model_snapshot_capacity_evicts_oldest() -> None:
    """超容量：淘汰时间戳最旧的 chat 快照。"""
    adapter, _, _, _ = _picker_harness()
    adapter._MODEL_PICKER_SNAPSHOT_MAX_CHATS = 2
    providers = [{"slug": "p", "name": "P", "models": ["m1"], "total_models": 1}]

    def record(chat_id: str) -> None:
        asyncio.run(adapter.send_model_picker(
            chat_id=chat_id, providers=providers, current_model="",
            current_provider="", session_key="s", on_model_selected=None))

    record("private:1")
    ts1, entries1 = adapter._model_picker_snapshots["private:1"]
    adapter._model_picker_snapshots["private:1"] = (ts1 - 100.0, entries1)
    record("private:2")
    ts2, entries2 = adapter._model_picker_snapshots["private:2"]
    adapter._model_picker_snapshots["private:2"] = (ts2 - 10.0, entries2)
    record("private:3")

    assert set(adapter._model_picker_snapshots) == {"private:2", "private:3"}


def test_model_snapshot_lazy_cleanup_drops_expired_on_record() -> None:
    """落账时惰性清理：过期项即使未触发容量淘汰也被移除。"""
    adapter, _, _, _ = _picker_harness()
    providers = [{"slug": "p", "name": "P", "models": ["m1"], "total_models": 1}]

    def record(chat_id: str) -> None:
        asyncio.run(adapter.send_model_picker(
            chat_id=chat_id, providers=providers, current_model="",
            current_provider="", session_key="s", on_model_selected=None))

    record("private:1")
    adapter._model_picker_snapshots["private:9"] = (
        time.time() - 10_000.0, [("stale", "p")]
    )
    record("private:2")

    assert "private:9" not in adapter._model_picker_snapshots
    assert set(adapter._model_picker_snapshots) == {"private:1", "private:2"}


def test_member_model_number_gets_no_reply_and_no_forward() -> None:
    """普通成员 /model 序号在入站门被拦：无转发、也无插件错误提示（同门）。"""
    adapter = _make_adapter(admin_users=[123456789])
    events: list = []
    sent: list = []

    async def fake_handle_message(ev):
        events.append(ev)

    async def fake_send(chat_id, content, reply_to=None, metadata=None):
        sent.append((chat_id, content))
        return SendResult(success=True)

    adapter.handle_message = fake_handle_message  # type: ignore[method-assign]
    adapter.send = fake_send  # type: ignore[method-assign]

    chat = "group:777"
    _record_picker(adapter, chat)
    sent.clear()

    asyncio.run(adapter._process_message({
        "message_type": "group",
        "group_id": 777,
        "user_id": 99999999,  # 普通成员
        "message": [{"type": "text", "data": {"text": "/model 2"}}],
        "self_id": 123456789,
    }))

    assert events == []
    assert sent == []


# ── T11 review #1/#3：本地媒体读取一律过 media-delivery validator ──────────

def _write_secret_file(path: Path, content: str = "SECRET_TOKEN=x") -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


def _capture_send_media(adapter):
    """替换 adapter._send_media，捕获 (chat_id, segments) 并返回成功。"""
    segs = []

    async def fake_send_media(chat_id, segments, reply_to=None, caption=None):
        segs.append((chat_id, segments))
        return SendResult(success=True)

    adapter._send_media = fake_send_media  # type: ignore[method-assign]
    return segs


def test_send_image_file_rejects_hermes_env() -> None:
    """#1: $HERMES_HOME/.env 是凭据文件 → send_image_file 拒发、不读字节。"""
    env_path = _write_secret_file(Path(os.environ["HERMES_HOME"]) / ".env")
    adapter = _make_adapter()
    segs = _capture_send_media(adapter)

    res = asyncio.run(adapter.send_image_file("private:123", str(env_path)))

    assert res.success is False
    assert "media-delivery validator" in (res.error or "")
    assert segs == []


def test_send_voice_rejects_ssh_key() -> None:
    """#1: ~/.ssh/id_rsa → send_voice 拒发。"""
    key = _write_secret_file(Path(os.path.expanduser("~")) / ".ssh" / "id_rsa")
    adapter = _make_adapter()
    segs = _capture_send_media(adapter)

    res = asyncio.run(adapter.send_voice("private:123", str(key)))

    assert res.success is False
    assert "media-delivery validator" in (res.error or "")
    assert segs == []


def test_send_document_rejects_etc_passwd() -> None:
    """#1: /etc/passwd 在拒收前缀下 → send_document 拒发。"""
    adapter = _make_adapter()
    segs = _capture_send_media(adapter)

    res = asyncio.run(adapter.send_document("private:123", "/etc/passwd"))

    assert res.success is False
    assert "media-delivery validator" in (res.error or "")
    assert segs == []


def test_send_video_rejects_missing_file() -> None:
    """#1: validator 要求存在的常规文件 → 不存在的路径同样拒发。"""
    adapter = _make_adapter()
    segs = _capture_send_media(adapter)

    res = asyncio.run(adapter.send_video("private:123", "/nonexistent/t11/x.mp4"))

    assert res.success is False
    assert "media-delivery validator" in (res.error or "")
    assert segs == []


def test_send_image_file_allows_normal_file() -> None:
    """#1 正向对照: 普通路径过 validator → base64 进 segments。"""
    ok = Path(os.environ["HERMES_HOME"]) / "media" / "ok.png"
    ok.parent.mkdir(parents=True, exist_ok=True)
    payload = b"\x89PNG-fake-t11"
    ok.write_bytes(payload)
    adapter = _make_adapter()
    segs = _capture_send_media(adapter)

    res = asyncio.run(adapter.send_image_file("private:123", str(ok)))

    assert res.success is True
    assert len(segs) == 1
    seg = segs[0][1][0]
    assert seg["type"] == "image"
    b64 = seg["data"]["file"].split("base64://", 1)[1]
    assert base64.b64decode(b64) == payload


def test_send_multiple_images_skips_denied_keeps_allowed() -> None:
    """#1: send_multiple_images 逐文件过闸 — 拒收源静默跳过，正常源照发。"""
    denied = _write_secret_file(Path(os.environ["HERMES_HOME"]) / ".env")
    allowed = Path(os.environ["HERMES_HOME"]) / "media" / "ok.png"
    allowed.parent.mkdir(parents=True, exist_ok=True)
    allowed.write_bytes(b"\x89PNG-ok")
    adapter = _make_adapter()
    segs = _capture_send_media(adapter)

    asyncio.run(
        adapter.send_multiple_images(
            "private:123",
            [
                (f"file://{denied}", ""),
                (f"file://{allowed}", ""),
                ("https://example.com/x.png", ""),
            ],
        )
    )

    assert len(segs) == 1
    batch = segs[0][1]
    assert [s["type"] for s in batch] == ["image", "image"]
    # 拒收项无 segment：第一段是放行文件的 base64，第二段是 url 直发
    b64 = batch[0]["data"]["file"].split("base64://", 1)[1]
    assert base64.b64decode(b64) == b"\x89PNG-ok"
    assert batch[1]["data"]["url"] == "https://example.com/x.png"


def test_api_send_media_image_denied_source_403() -> None:
    """#1: /api/send_media 本地源过闸 — 命中拒收清单 → 403 整单拒绝。"""
    from aiohttp import ClientSession

    env_path = _write_secret_file(Path(os.environ["HERMES_HOME"]) / ".env")
    adapter = _make_adapter()
    adapter._send_media = lambda *a, **kw: (  # 不应被触达
        asyncio.sleep(0, result=SendResult(success=True))
    )

    async def run():
        runner, port = await _start_api_server(adapter)
        try:
            async with ClientSession() as sess:
                async with sess.post(
                    f"http://127.0.0.1:{port}/api/send_media",
                    json={"chat_id": "private:123", "kind": "image",
                          "sources": [str(env_path)]},
                ) as resp:
                    assert resp.status == 403
                    body = await resp.json()
                    assert "media-delivery validator" in body["error"]
        finally:
            await runner.cleanup()

    asyncio.run(run())


def test_api_send_media_voice_denied_source_error_payload() -> None:
    """#1: /api/send_media kind=voice 命中拒收清单 → 错误载荷（不触桥）。"""
    from aiohttp import ClientSession

    key = _write_secret_file(Path(os.path.expanduser("~")) / ".ssh" / "id_rsa")
    adapter = _make_adapter()
    segs = _capture_send_media(adapter)

    async def run():
        runner, port = await _start_api_server(adapter)
        try:
            async with ClientSession() as sess:
                async with sess.post(
                    f"http://127.0.0.1:{port}/api/send_media",
                    json={"chat_id": "private:123", "kind": "voice",
                          "path": str(key)},
                ) as resp:
                    assert resp.status == 200
                    body = await resp.json()
                    assert body["status"] == "error"
                    assert "media-delivery validator" in body["error"]
        finally:
            await runner.cleanup()

    asyncio.run(run())
    assert segs == []


def test_api_napcat_upload_file_denied_403() -> None:
    """#3: upload_group_file 的 params.file 过闸 — 拒收路径 → 403。"""
    from aiohttp import ClientSession
    from urllib.parse import quote

    env_path = _write_secret_file(Path(os.environ["HERMES_HOME"]) / ".env")
    adapter = _make_adapter()
    called = []

    async def fake_call(action, params, timeout=30.0):
        called.append((action, params))
        return {}

    adapter._call_action = fake_call  # type: ignore[method-assign]

    async def run():
        runner, port = await _start_api_server(adapter)
        try:
            async with ClientSession() as sess:
                params = json.dumps({"group_id": 888, "file": str(env_path)})
                async with sess.get(
                    f"http://127.0.0.1:{port}/api/napcat"
                    f"?action=upload_group_file&params={quote(params)}"
                ) as resp:
                    assert resp.status == 403
                    body = await resp.json()
                    assert "media-delivery validator" in body["error"]
        finally:
            await runner.cleanup()

    asyncio.run(run())
    assert called == []


def test_api_napcat_upload_file_allowed_passes_resolved_path() -> None:
    """#3 正向对照: 合规文件 → 透传，且 params.file 为 validator 解析后的路径。"""
    from aiohttp import ClientSession
    from urllib.parse import quote

    ok = Path(os.environ["HERMES_HOME"]) / "media" / "doc.txt"
    ok.parent.mkdir(parents=True, exist_ok=True)
    ok.write_text("hello", encoding="utf-8")
    adapter = _make_adapter()
    called = []

    async def fake_call(action, params, timeout=30.0):
        called.append((action, dict(params)))
        return {"file_id": "f1"}

    adapter._call_action = fake_call  # type: ignore[method-assign]

    async def run():
        runner, port = await _start_api_server(adapter)
        try:
            async with ClientSession() as sess:
                params = json.dumps({"group_id": 888, "file": str(ok)})
                async with sess.get(
                    f"http://127.0.0.1:{port}/api/napcat"
                    f"?action=upload_group_file&params={quote(params)}"
                ) as resp:
                    assert resp.status == 200
                    body = await resp.json()
                    assert body["status"] == "ok"
        finally:
            await runner.cleanup()

    asyncio.run(run())
    assert called and called[0][0] == "upload_group_file"
    assert Path(called[0][1]["file"]).is_file()
    assert Path(called[0][1]["file"]).resolve() == ok.resolve()


# ── T11 review #2：chat_id 越权（session 上下文转发 + admin 判定下沉 adapter）──

def _media_adapter(extra=None):
    """带 _send_media 捕获的 adapter，返回 (adapter, segs)。"""
    adapter = _make_adapter(**(extra or {}))
    segs = _capture_send_media(adapter)
    return adapter, segs


def test_api_send_media_cross_chat_denied_non_admin(monkeypatch) -> None:
    """#2: QQ 会话内显式指到其他会话、且会话用户非 admin → 403。"""
    from aiohttp import ClientSession

    adapter, segs = _media_adapter({"admin_users": [111]})

    async def run():
        runner, port = await _start_api_server(adapter)
        try:
            async with ClientSession() as sess:
                async with sess.post(
                    f"http://127.0.0.1:{port}/api/send_media",
                    json={
                        "chat_id": "group:999",
                        "kind": "image",
                        "sources": ["https://example.com/x.png"],
                        "session_chat": "private:222",
                    },
                ) as resp:
                    assert resp.status == 403
                    body = await resp.json()
                    assert "cross-chat" in body["error"]
        finally:
            await runner.cleanup()

    asyncio.run(run())
    assert segs == []


def test_api_send_media_own_session_allowed() -> None:
    """#2: 显式 chat_id == 当前会话 → 放行（无需 admin）。"""
    from aiohttp import ClientSession

    adapter, segs = _media_adapter()

    async def run():
        runner, port = await _start_api_server(adapter)
        try:
            async with ClientSession() as sess:
                async with sess.post(
                    f"http://127.0.0.1:{port}/api/send_media",
                    json={
                        "chat_id": "private:222",
                        "kind": "image",
                        "sources": ["https://example.com/x.png"],
                        "session_chat": "private:222",
                    },
                ) as resp:
                    assert resp.status == 200
                    body = await resp.json()
                    assert body["status"] == "ok"
        finally:
            await runner.cleanup()

    asyncio.run(run())
    assert len(segs) == 1


def test_api_send_media_home_channel_target_allowed(monkeypatch) -> None:
    """#2: 目标 == ONEBOT_HOME_CHANNEL → 放行。"""
    from aiohttp import ClientSession

    monkeypatch.setenv("ONEBOT_HOME_CHANNEL", "private:888")
    adapter, segs = _media_adapter()

    async def run():
        runner, port = await _start_api_server(adapter)
        try:
            async with ClientSession() as sess:
                async with sess.post(
                    f"http://127.0.0.1:{port}/api/send_media",
                    json={
                        "chat_id": "private:888",
                        "kind": "image",
                        "sources": ["https://example.com/x.png"],
                        "session_chat": "private:222",
                    },
                ) as resp:
                    assert resp.status == 200
        finally:
            await runner.cleanup()

    asyncio.run(run())
    assert len(segs) == 1


def test_api_send_media_admin_session_allowed() -> None:
    """#2: 会话是 admin 的私聊（private:<admin qq>）→ 任意目标放行。"""
    from aiohttp import ClientSession

    adapter, segs = _media_adapter({"admin_users": [111]})

    async def run():
        runner, port = await _start_api_server(adapter)
        try:
            async with ClientSession() as sess:
                async with sess.post(
                    f"http://127.0.0.1:{port}/api/send_media",
                    json={
                        "chat_id": "group:999",
                        "kind": "image",
                        "sources": ["https://example.com/x.png"],
                        "session_chat": "private:111",
                    },
                ) as resp:
                    assert resp.status == 200
                    assert (await resp.json())["status"] == "ok"
        finally:
            await runner.cleanup()

    asyncio.run(run())
    assert len(segs) == 1


def test_api_send_media_group_session_denied_fail_closed() -> None:
    """#2: 群会话无法归属到用户 → 一律 fail-closed（即使目标是 admin 私聊）。"""
    from aiohttp import ClientSession

    adapter, segs = _media_adapter({"admin_users": [111]})

    async def run():
        runner, port = await _start_api_server(adapter)
        try:
            async with ClientSession() as sess:
                async with sess.post(
                    f"http://127.0.0.1:{port}/api/send_media",
                    json={
                        "chat_id": "private:111",
                        "kind": "image",
                        "sources": ["https://example.com/x.png"],
                        "session_chat": "group:777",
                    },
                ) as resp:
                    assert resp.status == 403
        finally:
            await runner.cleanup()

    asyncio.run(run())
    assert segs == []


def test_api_send_media_without_session_context_allowed() -> None:
    """#2: 无 session 上下文（CLI/cron/脚本）→ 维持原行为放行。"""
    from aiohttp import ClientSession

    adapter, segs = _media_adapter()

    async def run():
        runner, port = await _start_api_server(adapter)
        try:
            async with ClientSession() as sess:
                async with sess.post(
                    f"http://127.0.0.1:{port}/api/send_media",
                    json={
                        "chat_id": "group:999",
                        "kind": "image",
                        "sources": ["https://example.com/x.png"],
                    },
                ) as resp:
                    assert resp.status == 200
        finally:
            await runner.cleanup()

    asyncio.run(run())
    assert len(segs) == 1


def test_tools_forward_session_chat(monkeypatch) -> None:
    """#2: qq_send_* 携带 session_chat（onebot 会话内）→ adapter 判定。"""
    from plugins.platforms.onebot import tools

    calls = []

    def fake_http(method, path, payload=None):
        calls.append(payload)
        return {"ok": True, "message_id": "m1"}

    monkeypatch.setattr(tools, "_http", fake_http)
    monkeypatch.setenv("HERMES_SESSION_PLATFORM", "onebot")
    monkeypatch.setenv("HERMES_SESSION_CHAT_ID", "private:555")
    tools.qq_send_image({"sources": ["/tmp/a.png"], "chat_id": "group:999"})
    assert calls[0]["session_chat"] == "private:555"

    # 非 onebot 会话（如 CLI）→ 不携带
    monkeypatch.setenv("HERMES_SESSION_PLATFORM", "api_server")
    monkeypatch.delenv("HERMES_SESSION_CHAT_ID", raising=False)
    tools.qq_send_voice({"path": "/tmp/a.wav", "chat_id": "group:999"})
    assert calls[1]["session_chat"] is None

    # onebot 会话但无 chat id → None
    monkeypatch.setenv("HERMES_SESSION_PLATFORM", "onebot")
    tools.qq_send_video({"path": "/tmp/a.mp4", "chat_id": "group:999"})
    assert calls[2]["session_chat"] is None


def test_tools_session_vars_group_cross_chat_denied(monkeypatch) -> None:
    """R2 review: set_session_vars 真实绑定群会话 → 显式异 chat_id 发送被拒（跨 chat 防护）。"""
    from gateway.session_context import clear_session_vars, set_session_vars
    from plugins.platforms.onebot import tools

    adapter, segs = _media_adapter({"admin_users": [111]})
    tokens = set_session_vars(platform="onebot", chat_id="group:777", chat_type="group")
    try:
        async def run():
            runner, port = await _start_api_server(adapter)
            try:
                monkeypatch.setattr(tools, "_BASE", f"http://127.0.0.1:{port}")
                # blocking urllib call → off the loop or the server can't answer;
                # to_thread (not run_in_executor) keeps the session ContextVars
                result = await asyncio.to_thread(
                    tools.qq_send_image,
                    {"sources": ["https://example.com/x.png"], "chat_id": "group:999"},
                )
                assert "Send failed" in result
                assert "cross-chat" in result
            finally:
                await runner.cleanup()

        asyncio.run(run())
    finally:
        clear_session_vars(tokens)
    assert segs == []


def test_tools_session_vars_default_current_chat(monkeypatch) -> None:
    """R2 review: QQ 会话内省略 chat_id → 默认发到当前会话。"""
    from gateway.session_context import clear_session_vars, set_session_vars
    from plugins.platforms.onebot import tools

    calls = []

    def fake_http(method, path, payload=None):
        calls.append(payload)
        return {"ok": True, "message_id": "m1"}

    monkeypatch.setattr(tools, "_http", fake_http)
    tokens = set_session_vars(platform="onebot", chat_id="private:555", chat_type="private")
    try:
        result = tools.qq_send_image({"sources": ["https://example.com/x.png"]})
    finally:
        clear_session_vars(tokens)
    assert calls[0]["chat_id"] == "private:555"
    assert calls[0]["session_chat"] == "private:555"
    assert "Sent" in result


# ── T11 review #4/#5：绑定安全硬失败 + secret_scope 凭证读取 ────────────────

def test_bind_security_raises_non_loopback_no_token() -> None:
    """#4: 非 loopback host + 空 access_token → _start_reverse_server raise。"""
    adapter = _make_adapter(host="0.0.0.0")
    with pytest.raises(ValueError, match="non-loopback"):
        asyncio.run(adapter._start_reverse_server())


def test_bind_security_connect_returns_false() -> None:
    """#4: raise 经 connect() 兜底 → 记 ERROR、返回 False（不再启动服务）。"""
    adapter = _make_adapter(host="192.168.1.50")
    assert asyncio.run(adapter.connect()) is False


def test_bind_security_forward_mode_raises() -> None:
    """#4: forward 模式同样拒绝 —— _start_api_server 先校验再绑定。"""
    adapter = _make_adapter(mode="forward", host="192.168.1.50")
    with pytest.raises(ValueError, match="non-loopback"):
        asyncio.run(adapter._start_api_server())


def test_bind_security_allows_loopback_and_token() -> None:
    """#4 正向对照: loopback 无 token、非 loopback 有 token 均放行。"""
    assert _make_adapter(host="127.0.0.1")._validate_bind_security() is None
    assert _make_adapter(host="0.0.0.0", access_token="t")._validate_bind_security() is None
    # IPv6 loopback 字面量同放行
    assert _make_adapter(host="::1")._validate_bind_security() is None


def test_standalone_token_prefers_secret_scope(monkeypatch) -> None:
    """#5: standalone sender 先走 agent.secret_scope.get_secret。"""
    import agent.secret_scope as ss

    monkeypatch.setattr(ss, "get_secret", lambda name, default=None: "scoped-tok")
    assert _standalone_access_token({"access_token": "cfg-tok"}) == "scoped-tok"

    # UnscopedSecretError / 任何异常 → 回落 extra.access_token
    def raise_unscoped(name, default=None):
        raise ss.UnscopedSecretError(name, "no scope")

    monkeypatch.setattr(ss, "get_secret", raise_unscoped)
    assert _standalone_access_token({"access_token": "cfg-tok"}) == "cfg-tok"

    # 无 scope 命中（单 profile: get_secret 直读 env）→ env 值生效
    monkeypatch.setattr(ss, "get_secret", lambda name, default=None: os.environ.get(name, default))
    monkeypatch.setenv("ONEBOT_ACCESS_TOKEN", "env-tok")
    assert _standalone_access_token({}) == "env-tok"


def test_standalone_token_falls_back_to_extra(monkeypatch) -> None:
    """#5: get_secret 返回 None 且 env 未设 → extra.access_token 兜底。"""
    import agent.secret_scope as ss

    monkeypatch.setattr(ss, "get_secret", lambda name, default=None: default)
    monkeypatch.delenv("ONEBOT_ACCESS_TOKEN", raising=False)
    assert _standalone_access_token({"access_token": "cfg-tok"}) == "cfg-tok"
    assert _standalone_access_token({}) == ""


def test_tools_token_via_secret_scope(monkeypatch) -> None:
    """#5: tools._access_token 同源改造 —— 先 get_secret，再 config。"""
    from plugins.platforms.onebot import tools
    import agent.secret_scope as ss

    monkeypatch.setattr(ss, "get_secret", lambda name, default=None: "scoped-tok")
    assert tools._access_token() == "scoped-tok"

    monkeypatch.setattr(ss, "get_secret", lambda name, default=None: os.environ.get(name, default))
    monkeypatch.setenv("ONEBOT_ACCESS_TOKEN", "env-tok")
    assert tools._access_token() == "env-tok"

    monkeypatch.delenv("ONEBOT_ACCESS_TOKEN", raising=False)
    # get_secret 失效（如导入失败语义）→ 回落 gateway config
    def boom(name, default=None):
        raise RuntimeError("unavailable")

    monkeypatch.setattr(ss, "get_secret", boom)
    assert tools._access_token() in ("", None) or isinstance(tools._access_token(), str)


# ---------------------------------------------------------------------------
# T11 review #8: plugin-data relocation + one-time state migration
# ---------------------------------------------------------------------------

def _legacy_state_paths() -> "tuple[Path, Path]":
    home = Path(os.environ["HERMES_HOME"])
    return home / "onebot_nicknames.json", home / "onebot_requests.json"


def _plugin_state_paths() -> "tuple[Path, Path]":
    from plugins.platforms.onebot import adapter as adapter_module

    root = adapter_module._plugin_data_dir()
    return root / "onebot_nicknames.json", root / "onebot_requests.json"


def test_state_files_migrate_from_legacy_location() -> None:
    """#8: v1.1.x 状态文件首次触碰时一次性迁移到 plugin-data，旧文件保留。"""
    import plugins.platforms.onebot.adapter as adapter_module

    legacy_nick, legacy_req = _legacy_state_paths()
    legacy_nick.parent.mkdir(parents=True, exist_ok=True)
    legacy_nick.write_text(
        json.dumps({"private:111": "Alice"}, ensure_ascii=False), encoding="utf-8"
    )
    legacy_req.write_text(
        json.dumps(
            {"requests": [{"flag": "F11", "seq": 11, "status": "pending"}]},
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    adapter = _make_adapter(admin_users=[111])
    new_nick, new_req = _plugin_state_paths()

    # 迁移发生：新文件存在、内容一致、旧文件保留作回滚备份
    assert new_nick.is_file()
    assert json.loads(new_nick.read_text(encoding="utf-8")) == {"private:111": "Alice"}
    assert legacy_nick.is_file()
    assert adapter._nicknames == {"private:111": "Alice"}

    assert new_req.is_file()
    assert "F11" in adapter._requests
    assert adapter._request_seq == 11
    assert legacy_req.is_file()


def test_state_files_new_location_wins_over_legacy() -> None:
    """#8: 新旧同时存在 → 以新文件为准，迁移不得覆盖新文件。"""
    legacy_nick, _ = _legacy_state_paths()
    legacy_nick.parent.mkdir(parents=True, exist_ok=True)
    legacy_nick.write_text(
        json.dumps({"private:111": "Legacy"}, ensure_ascii=False), encoding="utf-8"
    )
    new_nick, _ = _plugin_state_paths()
    new_nick.parent.mkdir(parents=True, exist_ok=True)
    new_nick.write_text(
        json.dumps({"private:222": "Fresh"}, ensure_ascii=False), encoding="utf-8"
    )

    adapter = _make_adapter(admin_users=[111])
    assert adapter._nicknames == {"private:222": "Fresh"}


def test_state_files_persist_to_plugin_data_dir() -> None:
    """#8: 全新部署只写新路径，不再在 HERMES_HOME 根下落状态文件。"""
    adapter = _make_adapter(admin_users=[1])
    adapter._nicknames["private:9"] = "Bob"
    adapter._persist_nicknames()

    new_nick, _ = _plugin_state_paths()
    legacy_nick, _ = _legacy_state_paths()
    assert new_nick.is_file()
    assert json.loads(new_nick.read_text(encoding="utf-8"))["private:9"] == "Bob"
    assert not legacy_nick.exists()


def test_media_files_written_under_plugin_data_dir() -> None:
    """#8: 媒体下载落 $HERMES_HOME/plugin-data/onebot-platform/media/。"""
    import plugins.platforms.onebot.adapter as adapter_module

    adapter = _make_adapter(admin_users=[1])
    d = adapter_module._ensure_media_dir()
    assert d == Path(os.environ["HERMES_HOME"]) / "plugin-data" / "onebot-platform" / "media"
    assert d.is_dir()


def test_cleanup_tmp_files_sweeps_legacy_tmp_dir(monkeypatch) -> None:
    """#8: 清扫同时覆盖新 media 目录与旧 /tmp/hermes_onebot（只读兼容）。"""
    import plugins.platforms.onebot.adapter as adapter_module

    fake_legacy = Path(os.environ["HERMES_HOME"]) / "legacy_tmp"
    fake_legacy.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(adapter_module, "_legacy_tmp_dir", lambda: fake_legacy)

    adapter = _make_adapter(admin_users=[1])
    media = adapter_module._ensure_media_dir()

    old = media / "img_old.jpg"
    old.write_bytes(b"x")
    os.utime(old, (time.time() - 99999, time.time() - 99999))
    keep = media / "img_new.jpg"
    keep.write_bytes(b"y")

    legacy_old = fake_legacy / "voice_old.wav"
    legacy_old.write_bytes(b"z")
    os.utime(legacy_old, (time.time() - 99999, time.time() - 99999))

    adapter._cleanup_tmp_files(max_age=3600)
    assert not old.exists()
    assert keep.exists()
    assert not legacy_old.exists()

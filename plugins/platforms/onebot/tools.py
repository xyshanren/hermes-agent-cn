"""QQ (OneBot) model-facing tools.

Model tools for the OneBot channel (ported from dsh-onebot, PORTING #1):
  - qq_send_image / voice / video / file / forward — outbound media
  - qq_napcat_api — whitelisted NapCat action proxy
  - qq_group_history — pull group message history

Transport is the adapter's local HTTP API (default 127.0.0.1:8643; override
with ONEBOT_TOOL_BASE), so these work from any process — CLI/TUI sessions
included, where the gateway adapter may not be running. Target chat resolves
from an explicit chat_id argument, falling back to the calling session's
HERMES_SESSION_CHAT_ID when this is a QQ-channel session.
When an access token is configured, requests to ``/api/*`` carry
``Authorization: Bearer <token>`` — same config source as the adapter,
no extra setup.
"""

from __future__ import annotations

import json
import logging
import os
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Dict, Optional

from gateway.session_context import get_session_env

logger = logging.getLogger(__name__)

_BASE = os.environ.get("ONEBOT_TOOL_BASE", "http://127.0.0.1:8643").rstrip("/")

# OneBot actions a model may invoke through qq_napcat_api (read-only queries,
# file URL resolution, uploads, OCR, AI chat) — mirrors dsh-onebot's list.
# 权威定义在 onebot_utils.py；相对导入优先（开发仓 plugins.platforms.onebot.*
# 与生产 hermes_plugins.onebot_platform.* 两种包加载均可达），裸导入仅兜底
# 单文件直载场景。
try:
    from .onebot_utils import NAPCAT_API_WHITELIST
except ImportError:
    from onebot_utils import NAPCAT_API_WHITELIST

HTTP_TIMEOUT = 60


def _resolve_chat(chat_id: Optional[str]) -> str:
    """Explicit chat_id → session chat id (QQ-channel only) → error."""
    if chat_id:
        return chat_id
    platform = get_session_env("HERMES_SESSION_PLATFORM") or ""
    if platform.lower() == "onebot":
        session_chat = get_session_env("HERMES_SESSION_CHAT_ID") or ""
        if session_chat:
            return session_chat
    raise ValueError(
        "Cannot determine target chat: pass chat_id explicitly "
        "(format private:<qq> or group:<gid>) / 无法确定目标会话：请传 chat_id"
    )


def _session_chat() -> Optional[str]:
    """Forward the calling onebot session's chat id (or None outside one).

    T11 review #2: the tool layer cannot see session roles, so instead of
    deciding here it forwards the session context and lets the adapter
    enforce cross-chat authorization (``_authorize_cross_chat_send``).
    """
    platform = get_session_env("HERMES_SESSION_PLATFORM") or ""
    if platform.strip().lower() != "onebot":
        return None
    return (get_session_env("HERMES_SESSION_CHAT_ID") or "").strip() or None


def _access_token() -> str:
    """Resolve the access token shared with the adapter's ``/api`` gate.

    T11 review #5: primary source is ``agent.secret_scope.get_secret(
    "ONEBOT_ACCESS_TOKEN")`` — honors the active profile scope (multiplexed
    deployments) and reads ``os.environ`` when no scope is active, so plain
    env deployments keep working. Fallback is the onebot platform's
    ``access_token`` from the gateway config. Empty when unset; ``_http``
    sends no Authorization header in that case, which keeps token-less
    loopback deployments byte-for-byte unchanged.
    """
    try:
        from agent.secret_scope import get_secret

        scoped = get_secret("ONEBOT_ACCESS_TOKEN")
        if scoped:
            return str(scoped).strip()
    except Exception as e:  # noqa: BLE001 - tools must degrade to no-auth
        logger.debug("[onebot-tools] secret_scope token lookup skipped: %s", e)
    try:
        # Lazy import: tools.py must stay importable in stripped-down
        # processes; same config load the adapter's standalone sender uses.
        from gateway.config import Platform, load_gateway_config

        pcfg = load_gateway_config().platforms.get(Platform("onebot"))
        if pcfg is not None:
            extra = getattr(pcfg, "extra", {}) or {}
            return str(extra.get("access_token", "") or "").strip()
    except Exception as e:  # noqa: BLE001 - tools must degrade to no-auth
        logger.debug("[onebot-tools] access_token lookup skipped: %s", e)
    return ""


def _http(method: str, path: str, payload: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    url = _BASE + path
    data = None
    headers = {"Accept": "application/json"}
    token = _access_token()
    if token:
        headers["Authorization"] = f"Bearer {token}"
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=HTTP_TIMEOUT) as resp:
            body = resp.read().decode("utf-8", "replace")
            body = json.loads(body or "{}")
            # The adapter's /api handlers answer {"status": "ok", ...};
            # normalize to the {"ok": True} shape the tool handlers test.
            if isinstance(body, dict) and body.get("status") == "ok":
                body["ok"] = True
            return body
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", "replace")[:500]
        return {"ok": False, "error": f"HTTP {e.code}: {detail}"}
    except Exception as e:  # noqa: BLE001 - surface any transport failure
        return {"ok": False, "error": str(e)}


def _media_result(resp: Dict[str, Any]) -> str:
    if resp.get("ok"):
        mid = resp.get("message_id")
        return "Sent" + (f" (message_id={mid})" if mid else "") + " / 已发送"
    return "Send failed: " + str(resp.get("error") or "unknown error") + " / 发送失败"


# ---------------------------------------------------------------------------
# Handlers
# ---------------------------------------------------------------------------


def qq_send_image(args: Dict[str, Any], **kw) -> str:
    """Send one or more images (local paths or http(s) URLs, max 9)."""
    sources = args.get("sources") or []
    sources = [s for s in sources if isinstance(s, str) and s]
    if not sources:
        return "qq_send_image: sources must not be empty / sources 不能为空"
    if len(sources) > 9:
        return "qq_send_image: at most 9 images per call / 一次最多 9 张图片"
    chat_id = _resolve_chat(args.get("chat_id"))
    resp = _http(
        "POST",
        "/api/send_media",
        {"chat_id": chat_id, "kind": "image", "sources": sources, "caption": args.get("caption") or "", "session_chat": _session_chat()},
    )
    return _media_result(resp)


def qq_send_voice(args: Dict[str, Any], **kw) -> str:
    path = args.get("path") or ""
    if not path:
        return "qq_send_voice: path is required / path 必填"
    chat_id = _resolve_chat(args.get("chat_id"))
    resp = _http("POST", "/api/send_media", {"chat_id": chat_id, "kind": "voice", "path": path, "session_chat": _session_chat()})
    return _media_result(resp)


def qq_send_video(args: Dict[str, Any], **kw) -> str:
    path = args.get("path") or ""
    if not path:
        return "qq_send_video: path is required / path 必填"
    chat_id = _resolve_chat(args.get("chat_id"))
    resp = _http("POST", "/api/send_media", {"chat_id": chat_id, "kind": "video", "path": path, "session_chat": _session_chat()})
    return _media_result(resp)


def qq_send_file(args: Dict[str, Any], **kw) -> str:
    path = args.get("path") or ""
    if not path:
        return "qq_send_file: path is required / path 必填"
    chat_id = _resolve_chat(args.get("chat_id"))
    resp = _http(
        "POST",
        "/api/send_media",
        {
            "chat_id": chat_id,
            "kind": "file",
            "path": path,
            "file_name": args.get("file_name") or "",
            "session_chat": _session_chat(),
        },
    )
    return _media_result(resp)


def qq_send_forward(args: Dict[str, Any], **kw) -> str:
    """Send a merged forward (QQ chat bubble) with named node messages."""
    nodes = args.get("nodes") or []
    if not isinstance(nodes, list) or not nodes:
        return "qq_send_forward: nodes must not be empty ([{name, content}, ...]) / nodes 不能为空"
    chat_id = _resolve_chat(args.get("chat_id"))
    cleaned = []
    for n in nodes:
        if isinstance(n, dict) and (n.get("name") or n.get("content")):
            cleaned.append(
                {"name": str(n.get("name") or "Hermes"), "content": str(n.get("content") or "")}
            )
    if not cleaned:
        return "qq_send_forward: no valid nodes / 未提供有效节点"
    resp = _http(
        "POST",
        "/api/send_media",
        {"chat_id": chat_id, "kind": "forward", "nodes": cleaned, "session_chat": _session_chat()},
    )
    return _media_result(resp)


def qq_napcat_api(args: Dict[str, Any], **kw) -> str:
    """Proxy a whitelisted NapCat OneBot action."""
    action = str(args.get("action") or "")
    if action not in NAPCAT_API_WHITELIST:
        return (
            f"action {action!r} is not whitelisted. Allowed: "
            + ", ".join(NAPCAT_API_WHITELIST)
            + " / 不在白名单"
        )
    params = args.get("params") or {}
    if not isinstance(params, dict):
        return "qq_napcat_api: params must be an object / params 必须是对象"
    qs = urllib.parse.urlencode({"action": action, "params": json.dumps(params)})
    resp = _http("GET", f"/api/napcat?{qs}")
    if resp.get("ok"):
        return json.dumps(resp.get("data"), ensure_ascii=False)[:4000]
    return "Call failed: " + str(resp.get("error") or "unknown error") + " / 调用失败"


def qq_group_history(args: Dict[str, Any], **kw) -> str:
    """Pull recent messages from a group (summary / monitoring)."""
    group_id = args.get("group_id") or ""
    if not group_id:
        return "qq_group_history: group_id is required / group_id 必填"
    count = int(args.get("count") or 20)
    count = max(1, min(count, 50))
    qs = urllib.parse.urlencode(
        {"group_id": group_id, "count": count, "message_seq": args.get("message_seq") or ""}
    )
    resp = _http("GET", f"/api/group_history?{qs}")
    if resp.get("ok"):
        return json.dumps(resp.get("data"), ensure_ascii=False)[:8000]
    return "Fetch failed: " + str(resp.get("error") or "unknown error") + " / 拉取失败"


_HANDLERS: Dict[str, Any] = {
    "qq_send_image": qq_send_image,
    "qq_send_voice": qq_send_voice,
    "qq_send_video": qq_send_video,
    "qq_send_file": qq_send_file,
    "qq_send_forward": qq_send_forward,
    "qq_napcat_api": qq_napcat_api,
    "qq_group_history": qq_group_history,
}


def _str_prop(name: str, desc: str, required: bool = False) -> Dict[str, Any]:
    schema: Dict[str, Any] = {"type": "string", "description": desc}
    if required:
        schema["required"] = True
    return schema


def _schemas() -> Dict[str, Dict[str, Any]]:
    chat_id = {
        "type": "string",
        "description": "Target chat id, format private:<qq> or group:<gid>; omit to use the current session (目标会话，省略时默认当前会话)",
    }
    return {
        "qq_send_image": {
            "type": "object",
            "properties": {
                "sources": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Image sources: local absolute paths or http(s) URLs, max 9 (图片来源，最多 9 个)",
                },
                "chat_id": chat_id,
                "caption": {"type": "string", "description": "Optional caption text sent before the images (图片说明文字，可选)"},
            },
            "required": ["sources"],
        },
        "qq_send_voice": {
            "type": "object",
            "properties": {
                "path": _str_prop("path", "Absolute path of a local audio file (mp3/wav/silk etc.) (本地音频文件绝对路径)", required=True),
                "chat_id": chat_id,
            },
            "required": ["path"],
        },
        "qq_send_video": {
            "type": "object",
            "properties": {
                "path": _str_prop("path", "Absolute path of a local video file (本地视频文件绝对路径)", required=True),
                "chat_id": chat_id,
            },
            "required": ["path"],
        },
        "qq_send_file": {
            "type": "object",
            "properties": {
                "path": _str_prop("path", "Absolute path of a local file (本地文件绝对路径)", required=True),
                "file_name": _str_prop("file_name", "Display name shown when sending (optional) (发送时显示的文件名，可选)"),
                "chat_id": chat_id,
            },
            "required": ["path"],
        },
        "qq_send_forward": {
            "type": "object",
            "properties": {
                "nodes": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "name": _str_prop("name", "Node display name (节点昵称)"),
                            "content": _str_prop("content", "Node text content (节点文本内容)"),
                        },
                    },
                    "description": "Merged-forward node list, each {name, content}; mimics a QQ chat-history card (合并转发节点列表，仿 QQ 聊天记录)",
                },
                "chat_id": chat_id,
            },
            "required": ["nodes"],
        },
        "qq_napcat_api": {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "description": "Whitelisted action, one of: "
                    + ", ".join(NAPCAT_API_WHITELIST),
                },
                "params": {"type": "object", "description": "Action argument object (action 参数对象)"},
            },
            "required": ["action"],
        },
        "qq_group_history": {
            "type": "object",
            "properties": {
                "group_id": _str_prop("group_id", "Group id (群号)", required=True),
                "count": {"type": "integer", "description": "Number of messages to pull (1-50, default 20) (拉取条数)"},
                "message_seq": {"type": "integer", "description": "Pagination cursor (optional) (翻页游标，可选)"},
            },
            "required": ["group_id"],
        },
    }


_DESCRIPTIONS = {
    "qq_send_image": "Send one or more images to a QQ chat (local file paths or http(s) URLs, max 9). 发送图片到 QQ 会话。",
    "qq_send_voice": "Send a voice message to a QQ chat (local audio file; NapCat transcodes). 发送语音到 QQ 会话。",
    "qq_send_video": "Send a video message to a QQ chat (absolute path of a local video file). 发送视频到 QQ 会话。",
    "qq_send_file": "Send a file to a QQ chat (absolute path of a local file). 发送文件到 QQ 会话。",
    "qq_send_forward": "Send a merged forward to a QQ chat (chat-history card of named node messages). 发送合并转发。",
    "qq_napcat_api": "Call a whitelisted NapCat OneBot action (member queries / file URLs / OCR / AI etc.). 调用白名单内的 NapCat action。",
    "qq_group_history": "Pull recent QQ group message history for summarization or monitoring. 拉取 QQ 群最近消息历史。",
}


def register_tools(ctx) -> None:
    """Register the qq_* tools in the ``qq`` toolset."""
    for name, schema in _schemas().items():
        ctx.register_tool(
            name=name,
            toolset="qq",
            schema=schema,
            handler=_HANDLERS[name],
            description=_DESCRIPTIONS[name],
            emoji="\U0001f427",  # penguin
        )
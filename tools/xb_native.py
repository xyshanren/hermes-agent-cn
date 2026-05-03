#!/usr/bin/env python3
"""
xb Native Tools — Hermes-native browser automation tools.

Wraps xbrowser (xb) CLI as Hermes Native Tools via registry.register().
Zero external dependencies — uses subprocess to call xb CLI directly.

High-frequency tools only (P0/P1); low-frequency tools use MCP Server.

P0 Tools (天天用):
  - xb_navigate  — 打开网页
  - xb_snapshot  — 获取页面快照（含 @ref 可交互元素）
  - xb_click     — 点击元素（@ref 失效自动恢复）

P1 Tools (每周用):
  - xb_fill      — 填写表单
  - xb_screenshot — 截图
"""

import json
import logging
import os
import shutil
import subprocess
import time
import uuid
from pathlib import Path
from typing import Awaitable, Dict, List, Optional, Any

from tools.registry import registry

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# xb CLI discovery
# ---------------------------------------------------------------------------

_XB_CLI_PATHS: List[Path] = [
    Path("E:/program/Tencent/QClaw/resources/openclaw/config/skills/xbrowser/scripts/xb.cjs"),
    Path.home() / ".openclaw" / "tools" / "xbrowser" / "xb.cjs",
]

# Try to find xb in PATH
_xb_which = shutil.which("xb")
if _xb_which:
    _XB_CLI_PATHS.append(Path(_xb_which))


def _find_xb_cli() -> Optional[Path]:
    """Find the xb CLI executable."""
    for p in _XB_CLI_PATHS:
        if p and p.exists():
            return p
    # Fallback: check direct path
    p = Path("E:/program/Tencent/QClaw/resources/openclaw/config/skills/xb.cjs")
    if p.exists():
        return p
    return None


_XB_CLI: Optional[Path] = _find_xb_cli()


def _xb_available() -> bool:
    """Check if xb CLI is available (used as check_fn)."""
    return _XB_CLI is not None and _XB_CLI.exists()


# ---------------------------------------------------------------------------
# Subprocess helper
# ---------------------------------------------------------------------------

def _run_xb(args: list, timeout: int = 120) -> dict:
    """Run an xb CLI command and return the parsed JSON result."""
    if not _XB_CLI:
        return {"error": "xb CLI not found. Please install xbrowser skill first."}
    cmd = ["node", str(_XB_CLI)] + args
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            encoding="utf-8",
        )
        if result.stdout.strip():
            try:
                return json.loads(result.stdout)
            except json.JSONDecodeError:
                pass
        stdout = result.stdout.strip()
        stderr = result.stderr.strip()
        return {
            "stdout": stdout if stdout else None,
            "stderr": stderr if stderr else None,
            "returncode": result.returncode,
        }
    except subprocess.TimeoutExpired:
        return {"error": f"xb command timed out after {timeout}s"}
    except FileNotFoundError:
        return {"error": "Node.js not found. Is Node.js installed?"}
    except Exception as e:
        return {"error": str(e)}


# ---------------------------------------------------------------------------
# Session state cache
#
# Maintains in-memory browser session state so tools don't need to track
# task IDs across turns. Hermes process restart invalidates the cache (OK).
# ---------------------------------------------------------------------------

class XbSession:
    """In-memory browser session state."""
    __slots__ = ("task_id", "browser_type", "last_snapshot", "last_refs", "url", "created_at")

    def __init__(self, task_id: str, browser_type: str = "chrome"):
        self.task_id = task_id
        self.browser_type = browser_type
        self.last_snapshot: Optional[str] = None
        self.last_refs: Dict[str, str] = {}
        self.url: Optional[str] = None
        self.created_at = time.time()

    def is_stale(self, max_age_seconds: int = 60) -> bool:
        """Check if the session snapshot is stale (no recent snapshot)."""
        return time.time() - self.created_at > max_age_seconds

    def update_snapshot(self, snapshot_data: dict) -> None:
        """Update the session with a fresh snapshot."""
        self.last_snapshot = json.dumps(snapshot_data, ensure_ascii=False)
        self.last_refs = self._extract_refs(snapshot_data)

    @staticmethod
    def _extract_refs(snapshot_data: dict) -> Dict[str, str]:
        """Extract @ref → element mappings from a snapshot response."""
        refs: Dict[str, str] = {}
        # Snapshot data typically contains elements with @ref IDs
        elements = snapshot_data.get("elements", [])
        for el in elements:
            ref = el.get("ref", "")
            if ref:
                tag = el.get("tag", "")
                text = el.get("text", "")[:40]
                refs[ref] = f"{tag}: {text}" if text else tag
        return refs


# Global session cache
_sessions: Dict[str, XbSession] = {}

# Default browser type
_DEFAULT_BROWSER = os.getenv("XB_DEFAULT_BROWSER", "chrome")


def _get_or_create_session(task_id: Optional[str] = None,
                           browser: str = _DEFAULT_BROWSER) -> XbSession:
    """Get existing session or create a new one."""
    if task_id and task_id in _sessions:
        return _sessions[task_id]
    tid = task_id or str(uuid.uuid4())[:8]
    session = XbSession(tid, browser)
    _sessions[tid] = session
    return session


# ---------------------------------------------------------------------------
# P0 Tools — 最高频操作
# ---------------------------------------------------------------------------

def xb_navigate_handler(args: dict, **kw: Any) -> Awaitable[str]:
    """Handle xb_navigate: open URL in browser."""
    url = args.get("url", "")
    browser = args.get("browser", _DEFAULT_BROWSER)
    result = _run_xb(["run", "open", url, "--browser", browser])
    return _format_result(result, "navigate")


def xb_snapshot_handler(args: dict, **kw: Any) -> Awaitable[str]:
    """Handle xb_snapshot: get page snapshot with interactive elements."""
    interactive = args.get("interactive", True)
    cli_args = ["run", "snapshot"]
    if interactive:
        cli_args.append("-i")
    result = _run_xb(cli_args)
    return _format_result(result, "snapshot")


def xb_click_handler(args: dict, **kw: Any) -> Awaitable[str]:
    """Handle xb_click: click element by @ref, auto-resnapshot on failure."""
    ref = args.get("ref", "")
    task_id = args.get("task_id", "")
    if not ref:
        return _error_result("Missing required parameter: ref")

    # Try to click
    result = _run_xb(["run", "click", f"@{ref}"])

    # Auto-resnapshot on @ref failure
    if "error" in result or result.get("returncode", 0) != 0:
        # First try: resnapshot and retry
        snapshot_result = _run_xb(["run", "snapshot", "-i"])
        if "error" not in snapshot_result:
            result = _run_xb(["run", "click", f"@{ref}"])
            if "error" in result or result.get("returncode", 0) != 0:
                return _error_result(
                    f"元素 @{ref} 无法点击。可能是页面已变化，请使用 xb_snapshot 重新获取可交互元素列表。"
                )

    return _format_result(result, "click")


# ---------------------------------------------------------------------------
# P1 Tools — 次高频操作
# ---------------------------------------------------------------------------

def xb_fill_handler(args: dict, **kw: Any) -> Awaitable[str]:
    """Handle xb_fill: fill form element."""
    ref = args.get("ref", "")
    text = args.get("text", "")
    if not ref:
        return _error_result("Missing required parameter: ref")
    result = _run_xb(["run", "fill", f"@{ref}", text])
    return _format_result(result, "fill")


def xb_screenshot_handler(args: dict, **kw: Any) -> Awaitable[str]:
    """Handle xb_screenshot: take page screenshot."""
    full = args.get("full", False)
    path = args.get("path", "")
    cli_args = ["run", "screenshot"]
    if full:
        cli_args.append("--full")
    if path:
        cli_args.extend(["--path", path])
    result = _run_xb(cli_args)
    return _format_result(result, "screenshot")


# ---------------------------------------------------------------------------
# Result formatting
# ---------------------------------------------------------------------------

def _format_result(result: dict, tool: str) -> str:
    """Format xb result to a clean string."""
    if "error" in result:
        return f"❌ [{tool}] {result['error']}"

    stdout = result.get("stdout")
    stderr = result.get("stderr")
    if isinstance(stdout, str) and stdout.strip():
        return stdout.strip()
    if isinstance(stderr, str) and stderr.strip():
        return f"[stderr] {stderr.strip()}"
    return f"✅ [{tool}] completed (returncode: {result.get('returncode', 0)})"


def _error_result(message: str) -> str:
    """Format an error result."""
    return f"❌ {message}"


# ---------------------------------------------------------------------------
# Tool schemas
# ---------------------------------------------------------------------------

XB_NAVIGATE_SCHEMA = {
    "description": (
        "打开一个网页URL并在浏览器中导航到该地址。"
        "首次使用时会自动初始化浏览器环境。"
        "支持 chrome, edge, qqbrowser, cft 等浏览器。"
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "url": {
                "type": "string",
                "description": "要打开的完整网页URL (如 https://www.baidu.com)"
            },
            "browser": {
                "type": "string",
                "description": "使用的浏览器 (chrome, edge, qqbrowser, cft)",
                "default": _DEFAULT_BROWSER
            }
        },
        "required": ["url"]
    }
}

XB_SNAPSHOT_SCHEMA = {
    "description": (
        "获取当前页面的快照，包含所有可交互元素的 @ref 编号。"
        "在执行点击、填写等操作前，应先用此工具获取页面状态。"
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "interactive": {
                "type": "boolean",
                "description": "是否包含可交互元素标注",
                "default": True
            }
        }
    }
}

XB_CLICK_SCHEMA = {
    "description": (
        "点击页面上的某个元素，通过 @ref 编号指定目标。"
        "如果 @ref 失效（页面刷新或变化），会自动重新获取快照并重试。"
        "如果仍然失败，请使用 xb_snapshot 重新查看当前可交互元素。"
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "ref": {
                "type": "string",
                "description": "元素引用编号 (如 @e12, @button-submit)"
            },
            "task_id": {
                "type": "string",
                "description": "可选：任务ID（用于追踪会话）"
            }
        },
        "required": ["ref"]
    }
}

XB_FILL_SCHEMA = {
    "description": (
        "在表单输入框中填入文本内容。"
        "先通过 xb_snapshot 获取 @ref 编号，然后用此工具填写。"
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "ref": {
                "type": "string",
                "description": "输入框的 @ref 编号"
            },
            "text": {
                "type": "string",
                "description": "要填入的文本内容"
            }
        },
        "required": ["ref", "text"]
    }
}

XB_SCREENSHOT_SCHEMA = {
    "description": (
        "对当前页面进行截图，返回截图路径或base64数据。"
        "可用于验证页面状态或记录操作结果。"
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "full": {
                "type": "boolean",
                "description": "是否截取完整页面（含滚动区域）",
                "default": False
            },
            "path": {
                "type": "string",
                "description": "可选：截图保存路径"
            }
        }
    }
}


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------

# P0 Tools
registry.register(
    name="xb_navigate",
    toolset="browser",
    schema=XB_NAVIGATE_SCHEMA,
    handler=xb_navigate_handler,
    check_fn=_xb_available,
    is_async=False,
    emoji="🌐",
)

registry.register(
    name="xb_snapshot",
    toolset="browser",
    schema=XB_SNAPSHOT_SCHEMA,
    handler=xb_snapshot_handler,
    check_fn=_xb_available,
    is_async=False,
    emoji="📷",
)

registry.register(
    name="xb_click",
    toolset="browser",
    schema=XB_CLICK_SCHEMA,
    handler=xb_click_handler,
    check_fn=_xb_available,
    is_async=False,
    emoji="👆",
)

# P1 Tools
registry.register(
    name="xb_fill",
    toolset="browser",
    schema=XB_FILL_SCHEMA,
    handler=xb_fill_handler,
    check_fn=_xb_available,
    is_async=False,
    emoji="✏️",
)

registry.register(
    name="xb_screenshot",
    toolset="browser",
    schema=XB_SCREENSHOT_SCHEMA,
    handler=xb_screenshot_handler,
    check_fn=_xb_available,
    is_async=False,
    emoji="📸",
)

"""
Hermes xbrowser MCP Server — expose xbrowser CLI as MCP tools.

This MCP Server wraps the xbrowser (xb) CLI commands for use by any
MCP client including Hermes.

Usage:
    python -m skills.mcp.hermes_xb_mcp.hermes_xb_mcp
    
Or with hermes:
    hermes mcp serve --mcp-server xb

MCP client config:
    {
        "mcpServers": {
            "hermes-xb": {
                "command": "python",
                "args": ["-m", "skills.mcp.hermes_xb_mcp.hermes_xb_mcp"]
            }
        }
    }
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Optional

logger = logging.getLogger("hermes-xb-mcp")

# ---------------------------------------------------------------------------
# Lazy MCP SDK import
# ---------------------------------------------------------------------------

_MCP_SERVER_AVAILABLE = False
try:
    from mcp.server.fastmcp import FastMCP
    _MCP_SERVER_AVAILABLE = True
except ImportError:
    FastMCP = None  # type: ignore[assignment,misc]


# ---------------------------------------------------------------------------
# xb CLI setup
# ---------------------------------------------------------------------------

_XB_CLI_PATHS = [
    Path("E:/program/Tencent/QClaw/resources/openclaw/config/skills/xbrowser/scripts/xb.cjs"),
    Path("~/.openclaw/tools/xbrowser/xb.cjs").expanduser(),
    shutil.which("xb"),
]


def _find_xb_cli() -> Optional[Path]:
    """Find the xb CLI executable."""
    for p in _XB_CLI_PATHS:
        if p and p.exists():
            return p
    # Try direct path
    p = Path("E:/program/Tencent/QClaw/resources/openclaw/config/skills/xb.cjs")
    if p.exists():
        return p
    return None


_XB_CLI = _find_xb_cli()


def _run_xb_command(args: list, timeout: int = 120) -> dict:
    """Run xb CLI command and return parsed JSON result."""
    if not _XB_CLI:
        return {"error": "xb CLI not found. Install xbrowser skill first."}
    
    cmd = ["node", str(_XB_CLI)] + args
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            encoding="utf-8",
        )
        
        # Try parse JSON output
        if result.stdout.strip():
            try:
                return json.loads(result.stdout)
            except json.JSONDecodeError:
                return {
                    "stdout": result.stdout,
                    "stderr": result.stderr,
                    "returncode": result.returncode,
                }
        
        return {
            "stderr": result.stderr,
            "returncode": result.returncode,
        }
    except subprocess.TimeoutExpired:
        return {"error": f"Command timed out after {timeout}s"}
    except Exception as e:
        return {"error": str(e)}


# ---------------------------------------------------------------------------
# MCP Server creation
# ---------------------------------------------------------------------------

def create_xb_mcp_server() -> Optional[FastMCP]:
    """Create the xbrowser MCP server."""
    if not _MCP_SERVER_AVAILABLE:
        print(
            "Error: MCP server requires the 'mcp' package.\n"
            f"Install with: {sys.executable} -m pip install 'mcp'",
            file=sys.stderr,
        )
        return None
    
    if not _XB_CLI:
        logger.warning("xb CLI not found. Some tools may not work.")
    
    mcp = FastMCP("hermes-xb")
    
    # -- xb_init -----------------------------------------------------------
    
    @mcp.tool()
    def xb_init(
        browser: str = "chrome",
        headed: bool = False,
    ) -> dict:
        """Initialize xbrowser environment.
        
        Args:
            browser: Browser to use (chrome, edge, qqbrowser, cft)
            headed: Run in headed mode (visible browser)
        """
        args = ["init", "--browser", browser]
        if headed:
            args.append("--headed")
        return _run_xb_command(args)
    
    # -- xb_navigate --------------------------------------------------------
    
    @mcp.tool()
    def xb_navigate(
        url: str,
        browser: Optional[str] = None,
        timeout: int = 60,
    ) -> dict:
        """Navigate to a URL and open a new browser session.
        
        Args:
            url: The URL to navigate to
            browser: Optional browser override
            timeout: Navigation timeout in seconds
        """
        args = ["run", "open", url]
        if browser:
            args.extend(["--browser", browser])
        return _run_xb_command(args, timeout=timeout)
    
    # -- xb_snapshot -------------------------------------------------------
    
    @mcp.tool()
    def xb_snapshot(
        task_id: Optional[str] = None,
        interactive: bool = True,
    ) -> dict:
        """Get a snapshot of the current page state.
        
        Args:
            task_id: Optional task ID (defaults to active session)
            interactive: Include interactive element annotations
        """
        args = ["run", "snapshot"]
        if interactive:
            args.append("-i")
        if task_id:
            args.extend(["--task-id", task_id])
        return _run_xb_command(args)
    
    # -- xb_click -----------------------------------------------------------
    
    @mcp.tool()
    def xb_click(
        ref: str,
        task_id: Optional[str] = None,
    ) -> dict:
        """Click an element by @ref.
        
        Args:
            ref: Element reference (e.g., @e12, @button-submit)
            task_id: Optional task ID
        """
        args = ["run", "click", ref]
        if task_id:
            args.extend(["--task-id", task_id])
        return _run_xb_command(args)
    
    # -- xb_fill ----------------------------------------------------------
    
    @mcp.tool()
    def xb_fill(
        ref: str,
        text: str,
        task_id: Optional[str] = None,
    ) -> dict:
        """Fill an input element with text.
        
        Args:
            ref: Element reference
            text: Text to fill
            task_id: Optional task ID
        """
        args = ["run", "fill", ref, text]
        if task_id:
            args.extend(["--task-id", task_id])
        return _run_xb_command(args)
    
    # -- xb_type -----------------------------------------------------------
    
    @mcp.tool()
    def xb_type(
        ref: str,
        text: str,
        task_id: Optional[str] = None,
    ) -> dict:
        """Type text into an element (key by key).
        
        Args:
            ref: Element reference
            text: Text to type
            task_id: Optional task ID
        """
        args = ["run", "type", ref, text]
        if task_id:
            args.extend(["--task-id", task_id])
        return _run_xb_command(args)
    
    # -- xb_press ----------------------------------------------------------
    
    @mcp.tool()
    def xb_press(
        key: str,
        task_id: Optional[str] = None,
    ) -> dict:
        """Press a keyboard key.
        
        Args:
            key: Key to press (Enter, Escape, Tab, etc.)
            task_id: Optional task ID
        """
        args = ["run", "press", key]
        if task_id:
            args.extend(["--task-id", task_id])
        return _run_xb_command(args)
    
    # -- xb_screenshot -----------------------------------------------------
    
    @mcp.tool()
    def xb_screenshot(
        task_id: Optional[str] = None,
        full: bool = False,
    ) -> dict:
        """Take a screenshot.
        
        Args:
            task_id: Optional task ID
            full: Capture full page
        """
        args = ["run", "screenshot"]
        if full:
            args.append("--full")
        if task_id:
            args.extend(["--task-id", task_id])
        return _run_xb_command(args)
    
    # -- xb_wait -----------------------------------------------------------
    
    @mcp.tool()
    def xb_wait(
        condition: str = "networkidle",
        timeout: int = 30,
        task_id: Optional[str] = None,
    ) -> dict:
        """Wait for a condition.
        
        Args:
            condition: Wait condition (networkidle, load, domcontentloaded)
            timeout: Wait timeout in seconds
            task_id: Optional task ID
        """
        args = ["run", "wait", "--" + condition, str(timeout)]
        if task_id:
            args.extend(["--task-id", task_id])
        return _run_xb_command(args, timeout=timeout + 10)
    
    # -- xb_close ---------------------------------------------------------
    
    @mcp.tool()
    def xb_close(
        target: str = "browser",
        task_id: Optional[str] = None,
    ) -> dict:
        """Close a browser session.
        
        Args:
            target: What to close (browser, all)
            task_id: Optional task ID
        """
        args = ["run", "close", target]
        if task_id:
            args.extend(["--task-id", task_id])
        return _run_xb_command(args)
    
    # -- xb_status --------------------------------------------------------
    
    @mcp.tool()
    def xb_status() -> dict:
        """Get xbrowser status."""
        return _run_xb_command(["status"])
    
    # -- xb_cleanup -------------------------------------------------------
    
    @mcp.tool()
    def xb_cleanup() -> dict:
        """Clean up all browser sessions and temp files."""
        return _run_xb_command(["cleanup"])
    
    return mcp


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def run_xb_mcp_server(verbose: bool = False) -> None:
    """Start the xbrowser MCP server on stdio."""
    if not _MCP_SERVER_AVAILABLE:
        print(
            "Error: MCP server requires the 'mcp' package.\n"
            f"Install with: {sys.executable} -m pip install 'mcp'",
            file=sys.stderr,
        )
        sys.exit(1)
    
    if verbose:
        logging.basicConfig(level=logging.DEBUG, stream=sys.stderr)
    else:
        logging.basicConfig(level=logging.WARNING, stream=sys.stderr)
    
    server = create_xb_mcp_server()
    
    async def _run():
        try:
            await server.run_stdio_async()
        except KeyboardInterrupt:
            logger.info("MCP server stopped")
    
    try:
        asyncio.run(_run())
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    run_xb_mcp_server(verbose("--verbose" in sys.argv))
#!/usr/bin/env python
"""
Standalone test script for Hermes xbrowser MCP Server.

Usage:
    python test_mcp.py [--verbose]
    
Or test via MCP Inspector:
    npx @modelcontextprotocol/inspector python test_mcp.py
"""

import asyncio
import json
import subprocess
import sys
import os


def check_xb_cli():
    """Check if xb CLI is available."""
    xb_path = "E:/program/Tencent/QClaw/resources/openclaw/config/skills/xbrowser/scripts/xb.cjs"
    
    if os.path.exists(xb_path):
        # Test if it runs
        result = subprocess.run(
            ["node", xb_path, "--help"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode == 0:
            print(f"✓ xb CLI found at {xb_path}")
            return True
    
    print(f"✗ xb CLI not found at {xb_path}")
    return False


def check_mcp_package():
    """Check if mcp package is installed."""
    result = subprocess.run(
        [sys.executable, "-c", "from mcp.server.fastmcp import FastMCP; print('ok')"],
        capture_output=True,
        text=True,
    )
    if result.returncode == 0 and "ok" in result.stdout:
        print("✓ mcp package installed")
        return True
    
    print("✗ mcp package not installed")
    print(f"  Install with: {sys.executable} -m pip install mcp")
    return False


def test_mcp_server():
    """Test MCP server initialization."""
    # Add the hermes-agent to path so we can import the module
    sys.path.insert(0, "F:/work/workspace/qclaw/码一/hermes-agent")
    
    try:
        from skills.mcp.hermes_xb_mcp.hermes_xb_mcp import create_xb_mcp_server
        server = create_xb_mcp_server()
        if server:
            print("✓ MCP server created successfully")
            
            # List tools
            tools = server._tool_manager.list_tools()
            print(f"  Tools available: {len(tools)}")
            for tool in tools:
                print(f"    - {tool.name}")
            return True
    except Exception as e:
        print(f"✗ MCP server creation failed: {e}")
        return False


def main():
    print("=" * 60)
    print("Hermes xbrowser MCP Server - Test")
    print("=" * 60)
    print()
    
    # Check prerequisites
    checks = [
        ("xb CLI", check_xb_cli),
        ("mcp package", check_mcp_package),
    ]
    
    results = []
    for name, check_fn in checks:
        print(f"\n[{name}]")
        results.append(check_fn())
    
    print()
    print("-" * 60)
    
    if all(results):
        print("\n[MCP Server]")
        test_mcp_server()
        print()
        print("✓ All checks passed!")
        return 0
    else:
        print("\n✗ Some checks failed. Fix issues above.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
"""CAND-014 MCP `mcp__server__tool` 命名约定 (Phase 4 v0.20.0 borrow).

跟 plan CAND-014 1:1 配对 (跟 CAND-005/007+054/012/013/015/045/046/047/048/050/051
1:1 配对 0 改旧):

CAND-014 3 件套 (跟 upstream `e01f58ff1fdebbb6f7af971f04825d071f3f09da`
`feat(mcp): adopt mcp__server__tool naming convention` 1:1):
- mcp_tool_naming_migrate (跟 c1 1:1, 命名迁移 core — `mcp__server__tool` 格式)
- mcp_tool_name_validate (跟 c2 1:1, name format 验证 — `^mcp__[a-z0-9_]+__[a-z0-9_]+$`)
- mcp_tool_name_register (跟 c3 1:1, 跟 mcp tool registry 注册)

跟 mavis 4 件套 1:1 配对 + CAND-084 8-03 22:10 lesson "估时前必 verify 引擎能力":
- 后端先调查再设计: mcp tool 0 hit `mcp__server__tool` 现有 format (8-07 verify),
  0 改 mcp 主体 (跟 CAND-005 0 改 WebhookAdapter 1:1)
- Cherry-pick split bug class: 0 cherry-pick (新 file, 跟 CAND-001 1:1 配对)
- UX 倒退审计: 0 改 mcp 现有 file, 抽 file additive 0 改
- 估时前必 verify 引擎能力: 实际 0.25h (跟 plan 30min 1:1 配对 0.5x 缩)

跟 AIMC 4 铁律 1:1: 0 改 upstream / CN 端可维护 / 0 改 upstream 决策边界
"""

from __future__ import annotations

import logging
import re
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


# CAND-014 3 件套 (跟 upstream `e01f58ff1fdebbb6f7af971f04825d071f3f09da` 1:1 配对)
# 注: 这是 skeleton 形式, 0 副作用 (跟 CAND-001/003 + CAND-007+054 1:1 配对 additive pattern)

# 跟 upstream 1:1 配对 — MCP tool name format: `mcp__<server>__<tool>`
MCP_TOOL_NAME_PATTERN = re.compile(r"^mcp__[a-z0-9_]+__[a-z0-9_]+$")


def mcp_tool_naming_migrate(old_name: str, server: str, tool: str) -> Dict[str, str]:
    """CAND-014 (1/3): mcp_tool_naming_migrate (跟 upstream c1 1:1, 命名迁移).

    跟 plan CAND-014 1:1 配对 — 旧 MCP tool name 迁移到 `mcp__<server>__<tool>`
    新格式. Skeleton 0 实际改, additive 0 副作用.
    """
    logger.debug("CAND-014 mcp_tool_naming_migrate (跟 c1 1:1 配对 skeleton)")
    new_name = f"mcp__{server}__{tool}"
    return {
        "old_name": old_name,
        "new_name": new_name,
        "server": server,
        "tool": tool,
    }


def mcp_tool_name_validate(name: str) -> bool:
    """CAND-014 (2/3): mcp_tool_name_validate (跟 upstream c2 1:1, name format 验证).

    跟 plan CAND-014 1:1 配对 — MCP tool name format 验证 (跟 upstream pattern
    `^mcp__[a-z0-9_]+__[a-z0-9_]+$` 1:1). Skeleton 0 实际 validate, additive 0 副作用.
    """
    logger.debug("CAND-014 mcp_tool_name_validate (跟 c2 1:1 配对 skeleton)")
    return bool(MCP_TOOL_NAME_PATTERN.match(name))


def mcp_tool_name_register(server: str, tool: str) -> Dict[str, str]:
    """CAND-014 (3/3): mcp_tool_name_register (跟 upstream c3 1:1, registry 注册).

    跟 plan CAND-014 1:1 配对 — MCP tool 加进 registry. Skeleton 0 实际
    register, additive 0 副作用.
    """
    logger.debug("CAND-014 mcp_tool_name_register (跟 c3 1:1 配对 skeleton)")
    name = f"mcp__{server}__{tool}"
    return {
        "name": name,
        "server": server,
        "tool": tool,
        "registered": True,
    }


# Combined entry: 跑 3 件套 (跟 CAND-005 apply_filter + CAND-007+054 1:1 配对)
def apply_mcp_naming(old_name: str, server: str, tool: str) -> Dict[str, Any]:
    """CAND-014 main: 跑 3 件套 MCP tool 命名迁移 (跟 CAND-005 1:1 配对 combined entry).

    跟 plan CAND-014 1:1 配对 — additive 0 改 mcp 主体, 抽 file 实施.
    3 件套 1:1 配对 upstream 1 commit 3 concept.

    Args:
        old_name: 旧 MCP tool name
        server: MCP server name
        tool: MCP tool name

    Returns:
        dict 映射 3 keys (migrate / validate / register) → result
    """
    migrated = mcp_tool_naming_migrate(old_name, server, tool)
    valid = mcp_tool_name_validate(migrated["new_name"])
    registered = mcp_tool_name_register(server, tool) if valid else {"name": "", "registered": False}
    return {
        "migrate": migrated,
        "validate": valid,
        "register": registered,
    }

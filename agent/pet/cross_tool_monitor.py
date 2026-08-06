"""CAND-060 Pet 跨工具 monitor (Coding Agent Watcher, Phase 4 v0.20.0 borrow).

跟 plan CAND-060 1:1 配对 (跟 CAND-040 + Sprint 4 5 候选 1:1 配对):
- KNOWN_AGENTS: 9 coding agent 列表 (claude_code/codex/cursor/gemini_cli/
  copilot/kimi/qwen_code/opencode/qoder, 跟 CAND-040 PET_SPECIES 1:1 配对)
- detect_agent_installed: 检查 executable path (which/where stdlib shutil.which)
- detect_agent_config_present: 检查 config 目录 (~/.claude/, ~/.codex/, etc)
- detect_agent_running: 检查 process list (Windows tasklist / Unix ps, 跨 platform)
- scan_coding_agents: 综合 3 检测, 返 list of {agent_id, installed, config_present, running}

跟 mavis 4 件套 1:1 配对 + CAND-084 8-03 22:10 lesson "估时前必 verify 引擎能力":
- 后端先调查再设计: 借 shutil.which (cn stdlib) + psutil 0 依赖 (subprocess fallback
  to tasklist/ps), 0 改 CAND-040 agent/pet/__init__.py 主体
- Cherry-pick split bug class: 0 cherry-pick (全新 module, AGPL-3.0 0 借鉴
  OpenBMB/MiniCPM-Desk-Pet 代码, 跟 license 警告 1:1 配对 纯自设计)
- UX 倒退审计: 0 改 CAND-040, 0 改 agent 现有 file, 新 agent/pet/cross_tool_monitor.py
  独立 file additive 0 改
- 估时前必 verify 引擎能力: verify agent/pet/ 0 命中 cross_tool_monitor (跟 K-9 1:1
  配对 plan 假设 100% 偏离), 实际 1-2h (跟 Sprint 4 1:1 配对 0.5-1x 缩)

跟 AIMC 4 铁律 1:1: 0 改 upstream / CN 端可维护 / 0 改 upstream 决策边界
(跟 MiniCPM-Desk-Pet cross-pollination 1:1 配对 0 借鉴代码, 模式借鉴 0 复制)
"""

from __future__ import annotations

import os
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional


# CAND-060 9 coding agent registry (跟 CAND-040 PET_SPECIES 1:1 配对)
KNOWN_AGENTS: List[Dict[str, str]] = [
    {"id": "claude_code", "name": "Claude Code", "exe": "claude", "config_dir": ".claude"},
    {"id": "codex", "name": "Codex CLI", "exe": "codex", "config_dir": ".codex"},
    {"id": "cursor", "name": "Cursor Agent", "exe": "cursor", "config_dir": ".cursor"},
    {"id": "gemini_cli", "name": "Gemini CLI", "exe": "gemini", "config_dir": ".gemini"},
    {"id": "copilot", "name": "GitHub Copilot CLI", "exe": "gh-copilot", "config_dir": ".config/gh-copilot"},
    {"id": "kimi", "name": "Kimi CLI", "exe": "kimi", "config_dir": ".kimi"},
    {"id": "qwen_code", "name": "Qwen Code", "exe": "qwen", "config_dir": ".qwen-code"},
    {"id": "opencode", "name": "OpenCode", "exe": "opencode", "config_dir": ".opencode"},
    {"id": "qoder", "name": "Qoder", "exe": "qoder", "config_dir": ".qoder"},
]


@dataclass
class AgentState:
    """CAND-060 state: 单个 coding agent 检测结果 (跟 CAND-040 PetData 1:1 配对).

    字段:
    - agent_id: agent 唯一 id (e.g. "claude_code")
    - name: agent 显示名 (e.g. "Claude Code")
    - installed: 是否检测到 executable (which/where)
    - config_present: 是否检测到 config 目录
    - running: 是否检测到 process running (跨 platform)
    - version: 版本字符串 (None = unknown, optional)
    """
    agent_id: str
    name: str
    installed: bool
    config_present: bool
    running: bool
    version: Optional[str] = None


def detect_agent_installed(exe_name: str) -> bool:
    """CAND-060 detect 1/3: 检查 executable path (shutil.which 跨 platform).

    跟 plan CAND-060 1:1 配对 — shutil.which 在 PATH 找 exe, 跨 Windows
    (.exe extension) + Unix (no extension) 1:1 兼容. 0 副作用 (跟 K-9 1:1).
    """
    if not exe_name:
        return False
    return shutil.which(exe_name) is not None


def detect_agent_config_present(config_dir: str) -> bool:
    """CAND-060 detect 2/3: 检查 config 目录存在 (~/.claude/, ~/.codex/, etc).

    跟 plan CAND-060 1:1 配对 — Path.home() / config_dir 0 副作用 read-only check.
    0 副作用 (跟 K-9 1:1 配对 0 改 user filesystem).
    """
    if not config_dir:
        return False
    path = Path.home() / config_dir
    return path.exists() and path.is_dir()


def detect_agent_running(
    exe_name: str,
    run_command_fn: Optional[Any] = None,
) -> bool:
    """CAND-060 detect 3/3: 检查 process running (跨 platform tasklist / ps).

    跟 plan CAND-060 1:1 配对 — Windows tasklist + Unix ps + macOS ps.
    run_command_fn 注入让 test 不真发 subprocess. 0 副作用 (跟 K-9 1:1 配对
    0 改 user system, read-only check).
    """
    if not exe_name:
        return False

    try:
        if run_command_fn is not None:
            output = run_command_fn(exe_name)
        else:
            # 跨 platform 1:1 配对
            if os.name == "nt":
                # Windows: tasklist /FI "IMAGENAME eq <exe>.exe"
                result = subprocess.run(
                    ["tasklist", "/FI", f"IMAGENAME eq {exe_name}.exe"],
                    capture_output=True, text=True, timeout=5,
                )
                output = result.stdout
            else:
                # Unix/macOS: ps aux | grep <exe>
                result = subprocess.run(
                    ["ps", "aux"],
                    capture_output=True, text=True, timeout=5,
                )
                output = result.stdout

        return exe_name.lower() in output.lower()
    except (subprocess.TimeoutExpired, FileNotFoundError, Exception):
        return False


def scan_coding_agents(
    run_command_fn: Optional[Any] = None,
) -> List[AgentState]:
    """CAND-060 main: 扫描 9 coding agent, 返 list of AgentState.

    跟 plan CAND-060 1:1 配对 — 综合 3 检测 (installed / config_present /
    running), 0 副作用 read-only check. 跟 CAND-040 list_pets 1:1 配对
    返 sorted list (按 agent_id alphabetically). 跟 Sprint 4 1:1 配对
    additive 0 改旧.

    Args:
        run_command_fn: 注入 run_command(exe_name) -> output string (test mock,
                       None = 用 subprocess 实际跑)

    Returns:
        list of AgentState sorted by agent_id
    """
    results: List[AgentState] = []
    for agent in KNOWN_AGENTS:
        agent_id = agent["id"]
        name = agent["name"]
        exe = agent["exe"]
        config_dir = agent["config_dir"]
        results.append(AgentState(
            agent_id=agent_id,
            name=name,
            installed=detect_agent_installed(exe),
            config_present=detect_agent_config_present(config_dir),
            running=detect_agent_running(exe, run_command_fn=run_command_fn),
        ))
    return sorted(results, key=lambda a: a.agent_id)


def get_agent_state(agent_id: str) -> Optional[AgentState]:
    """CAND-060 read: 读单个 agent 状态 (跟 CAND-040 get_pet_state 1:1 配对)."""
    for agent in KNOWN_AGENTS:
        if agent["id"] == agent_id:
            return AgentState(
                agent_id=agent["id"],
                name=agent["name"],
                installed=detect_agent_installed(agent["exe"]),
                config_present=detect_agent_config_present(agent["config_dir"]),
                running=detect_agent_running(agent["exe"]),
            )
    return None

"""Tests for CAND-060 (Sprint 5): Pet 跨工具 monitor (Coding Agent Watcher).

跟 plan CAND-060 1:1 配对 (跟 CAND-040 + Sprint 4 5 候选 + K-7 1:1 配对):
- 新 agent/pet/cross_tool_monitor.py (跟 CAND-040 agent/pet/ 1:1 配对):
  * KNOWN_AGENTS: 9 coding agent registry (跟 CAND-040 PET_SPECIES 1:1 配对)
  * 4 functions: detect_agent_installed / detect_agent_config_present /
    detect_agent_running / scan_coding_agents + get_agent_state
- 0 改 CAND-040 agent/pet/__init__.py 主体 (跟 UX 倒退审计 1:1)
- 0 改 agent 现有 11 file (跟 CAND-040 1:1 配对)
- AGPL-3.0 0 借鉴 OpenBMB 代码 (跟 license 警告 1:1 配对 纯自设计)
- 5 test (2 静态 + 3 live, 跟 CAND-040 1:1 配对 4-5 test)
"""

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent


# ---------- CAND-060 main change: 静态 source check ----------


def test_cross_tool_monitor_module_exists():
    """CAND-060 main file: agent/pet/cross_tool_monitor.py 存在 (跟 CAND-040 1:1 配对)."""
    p = REPO / "agent" / "pet" / "cross_tool_monitor.py"
    assert p.exists(), f"{p} missing (CAND-060 main file)"
    src = p.read_text(encoding="utf-8")
    for fn in ("detect_agent_installed", "detect_agent_config_present",
               "detect_agent_running", "scan_coding_agents", "get_agent_state"):
        assert f"def {fn}" in src, f"function {fn} missing in cross_tool_monitor.py"


def test_known_agents_9_registered():
    """CAND-060 registry: 9 coding agent 完整 (跟 CAND-040 5 species 1:1 配对 registry pattern)."""
    src = (REPO / "agent" / "pet" / "cross_tool_monitor.py").read_text(encoding="utf-8")
    for agent_id in ("claude_code", "codex", "cursor", "gemini_cli", "copilot",
                     "kimi", "qwen_code", "opencode", "qoder"):
        assert f'"id": "{agent_id}"' in src, f"KNOWN_AGENTS 缺 {agent_id}"


def test_cand_040_pet_unchanged():
    """CAND-060 0 改 CAND-040 agent/pet/__init__.py 主体 (跟 UX 倒退审计 1:1)."""
    src = (REPO / "agent" / "pet" / "__init__.py").read_text(encoding="utf-8")
    # 0 cross_tool_monitor import 改 CAND-040 主体
    assert "cross_tool_monitor" not in src, (
        "CAND-040 agent/pet/__init__.py 0 改 0 失, CAND-060 不应 import cross_tool_monitor"
    )


# ---------- CAND-060 live integration: 跟 plan 1:1 配对 ----------


def test_scan_coding_agents_live():
    """Live: scan_coding_agents 返 9 AgentState sorted by agent_id (0 副作用 read-only)."""
    sys.path.insert(0, str(REPO))
    from agent.pet.cross_tool_monitor import scan_coding_agents, KNOWN_AGENTS

    assert len(KNOWN_AGENTS) == 9, f"KNOWN_AGENTS 应 9 个, got: {len(KNOWN_AGENTS)}"

    # mock run_command_fn 返 "claude" 出现 (1 个 agent running)
    def mock_run(exe):
        return "claude process running" if exe == "claude" else ""

    agents = scan_coding_agents(run_command_fn=mock_run)

    # 1. 9 个 sorted
    assert len(agents) == 9, f"应 9 个 agent, got: {len(agents)}"
    # sorted by agent_id alphabetically
    assert agents[0].agent_id == "claude_code"
    assert agents[-1].agent_id == "qwen_code"

    # 2. claude_code.running = True (mock 返 "claude process running")
    claude = next(a for a in agents if a.agent_id == "claude_code")
    assert claude.running is True, f"claude_code.running 应 True (mock), got: {claude.running}"
    # 其他 .running = False
    others = [a for a in agents if a.agent_id != "claude_code"]
    assert all(a.running is False for a in others), "其他 agent .running 应 False"

    # 3. installed 跟 shutil.which (cn stdlib 0 依赖, 实际环境决定)
    # 注: test 环境可能 0 安装任何 coding agent, 不能假设 True
    # 但字段类型应 bool
    for a in agents:
        assert isinstance(a.installed, bool)
        assert isinstance(a.config_present, bool)
        assert isinstance(a.running, bool)
        assert isinstance(a.version, type(None)) or isinstance(a.version, str)


def test_get_agent_state_live():
    """Live: get_agent_state 返 AgentState 或 None (跟 CAND-040 get_pet_state 1:1 配对)."""
    sys.path.insert(0, str(REPO))
    from agent.pet.cross_tool_monitor import get_agent_state

    # 1. 0 命中 → None
    assert get_agent_state("nonexistent_agent") is None

    # 2. 命中 → AgentState
    state = get_agent_state("claude_code")
    assert state is not None
    assert state.agent_id == "claude_code"
    assert state.name == "Claude Code"
    # bool fields
    assert isinstance(state.installed, bool)
    assert isinstance(state.config_present, bool)
    assert isinstance(state.running, bool)


def test_detect_agent_installed_and_config_live():
    """Live: detect_agent_installed + detect_agent_config_present 0 副作用 (跟 K-9 1:1 配对)."""
    sys.path.insert(0, str(REPO))
    from agent.pet.cross_tool_monitor import (
        detect_agent_installed,
        detect_agent_config_present,
    )

    # 1. empty input → False
    assert detect_agent_installed("") is False
    assert detect_agent_installed(None) is False
    assert detect_agent_config_present("") is False
    assert detect_agent_config_present(None) is False

    # 2. 真实检测: 字段类型应 bool
    result_installed = detect_agent_installed("python")  # python 通常 in PATH
    assert isinstance(result_installed, bool), f"应 bool, got: {type(result_installed)}"

    result_config = detect_agent_config_present("nonexistent_dir_xyz")
    assert result_config is False, "0 存在 dir 应 False"

    # 3. shutil.which + Path.home() 0 副作用 (跟 K-9 1:1 配对 0 改 filesystem)
    # 跑多次, 状态一致
    assert detect_agent_installed("python") == detect_agent_installed("python")

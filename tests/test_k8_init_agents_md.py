"""Tests for K-8 (Phase 4 v0.20.0 borrow): /init slash command + AGENTS.md template.

跟 Phase 4 K-8 sprint plan §6 1:1 配对:
- 新 acp_adapter/init_command.py (3 functions: scan_cwd / render_agents_md / init_agents_md)
- acp_adapter/server.py:460 _ADVERTISED_COMMANDS 加 /init entry (跟 /context 1:1 配对)
- acp_adapter/server.py:1650 handler dict 加 "init": self._cmd_init
- acp_adapter/server.py:1896 _cmd_init 函数 (跟 _cmd_version 1:1 配对)
- 现有 AGENTS.md 不覆盖 (force=False default, 跟 plan K-8 "additive 0 改" 1:1 配对)

7 test (4 静态 source check + 3 live integration), 跟 K-6 test_k6_shell_bypass.py 同 pattern:
静态 source check 防改回归 + live integration 验证真行为。0 pyyaml 依赖, 0 LLM dep.
"""

import re
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent


# ---------- K-8 main change: 静态 source check ----------


def test_init_command_module_exists():
    """K-8 main file: acp_adapter/init_command.py 存在 (跟 plan §6 1:1 配对)."""
    p = REPO / "acp_adapter" / "init_command.py"
    assert p.exists(), f"{p} missing (K-8 main file)"
    src = p.read_text(encoding="utf-8")
    for fn in ("scan_cwd", "render_agents_md", "init_agents_md"):
        assert f"def {fn}" in src, f"function {fn} missing in init_command.py"


def test_server_advertised_init_command():
    """K-8 advertised: _ADVERTISED_COMMANDS 加 /init entry (跟 /context 1:1 配对)."""
    main_src = (REPO / "acp_adapter" / "server.py").read_text(encoding="utf-8")
    # 找 _ADVERTISED_COMMANDS 段
    assert '"name": "init"' in main_src, (
        "_ADVERTISED_COMMANDS 缺 /init entry (K-8 advertisement 缺失)"
    )
    # 跟现有 8 command 1:1 配对: help / model / tools / context / reset / compact / steer / queue / version
    for cmd in ("help", "model", "tools", "context", "reset", "compact", "steer", "queue", "version", "init"):
        assert f'"name": "{cmd}"' in main_src, f"existing /{cmd} command 0 改 0 失, K-8 破坏现有"


def test_server_init_handler_dispatch():
    """K-8 dispatch: handler dict 加 'init': self._cmd_init (跟 /context 1:1 配对)."""
    main_src = (REPO / "acp_adapter" / "server.py").read_text(encoding="utf-8")
    assert '"init": self._cmd_init' in main_src, (
        "handler dict 缺 'init': self._cmd_init (K-8 dispatch 缺失)"
    )


def test_server_init_command_function_exists():
    """K-8 handler: _cmd_init 函数存在 (跟 _cmd_version 1:1 配对)."""
    main_src = (REPO / "acp_adapter" / "server.py").read_text(encoding="utf-8")
    assert "def _cmd_init(self, args: str, state: SessionState) -> str:" in main_src, (
        "_cmd_init function missing in server.py (K-8 handler 缺失)"
    )


# ---------- K-8 live integration: 跟 plan §6 1:1 配对 ----------


def test_scan_cwd_extracts_readme_and_pyproject(tmp_path):
    """Live: scan_cwd 读 README.md + pyproject.toml + ls top-level (跟 plan K-8 §6 1:1 配对)."""
    from acp_adapter.init_command import scan_cwd

    # setup fixture
    (tmp_path / "README.md").write_text("# My Project\n\nA test project.\n", encoding="utf-8")
    (tmp_path / "pyproject.toml").write_text('[project]\nname = "test"\n', encoding="utf-8")
    (tmp_path / "src").mkdir()
    (tmp_path / "tests").mkdir()

    info = scan_cwd(tmp_path)

    assert info["project_name"] == tmp_path.name
    assert "My Project" in info["readme_excerpt"]
    assert 'pyproject.toml' in info["pyproject_excerpt"]
    # 最多 10 entries, 0 hidden (.pytest_cache 之类)
    assert all(not s.startswith(".") for s in info["structure"])


def test_init_agents_md_creates_new_file(tmp_path):
    """Live: init_agents_md 在空 cwd 生成新 AGENTS.md (跟 plan K-8 §6 1:1 配对)."""
    from acp_adapter.init_command import init_agents_md

    (tmp_path / "README.md").write_text("# Test", encoding="utf-8")

    agents_path, created = init_agents_md(tmp_path)

    assert created is True, "init_agents_md should create new file"
    assert agents_path.exists(), f"{agents_path} should exist after init"
    content = agents_path.read_text(encoding="utf-8")
    assert "Test" in content, "AGENTS.md should include README excerpt"
    assert tmp_path.name in content, "AGENTS.md should include project name"


def test_init_agents_md_does_not_overwrite_existing(tmp_path):
    """Live: init_agents_md 默认 0 覆盖现有 AGENTS.md (跟 plan K-8 'additive 0 改' 1:1 配对)."""
    from acp_adapter.init_command import init_agents_md

    existing = tmp_path / "AGENTS.md"
    existing.write_text("# EXISTING CONTENT, do not overwrite", encoding="utf-8")

    agents_path, created = init_agents_md(tmp_path)

    assert created is False, "init_agents_md should NOT overwrite by default"
    assert existing.read_text(encoding="utf-8") == "# EXISTING CONTENT, do not overwrite", (
        "K-8 错: 现有 AGENTS.md 被覆盖 (跟 plan K-8 'additive 0 改' 1:1 配对 should preserve)"
    )


def test_init_agents_md_force_overwrites_existing(tmp_path):
    """Live: init_agents_md force=True 覆盖现有 AGENTS.md (跟 K-8 _cmd_init --force 1:1 配对)."""
    from acp_adapter.init_command import init_agents_md

    existing = tmp_path / "AGENTS.md"
    existing.write_text("# OLD CONTENT", encoding="utf-8")
    (tmp_path / "README.md").write_text("# New Project", encoding="utf-8")

    agents_path, created = init_agents_md(tmp_path, force=True)

    assert created is True, "init_agents_md with force=True should overwrite"
    content = agents_path.read_text(encoding="utf-8")
    assert "New Project" in content, "AGENTS.md should include new README"
    assert "OLD CONTENT" not in content, "AGENTS.md should NOT contain old content"

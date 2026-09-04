"""Tests for agent.safety.protected_files (Sprint 16 档 C.1).

跟 mavis MEMORY:
- 后端先调查再设计 (memory:13-17): 测试 3 类文件 1:1 配对 + bypass / disabled 路径
- UX 倒退审计 (memory:19-23): 测试其他文件 0 干扰 (Sprint 15 CAND-086 1:1)
- Cherry-pick split bug class (memory:7-11): 测试 0 改现有 write_file / patch happy path

跟 Sprint 14/15 in-scope fix 1:1 配对 (跟 user 9-03 提醒 "每个 sprint 必须做好测试" 1:1).
"""
from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import patch

import pytest


@pytest.fixture
def safety():
    """Load agent.safety fresh per test."""
    import importlib
    import agent.safety as mod
    importlib.reload(mod)
    import agent.safety.protected_files as pf
    importlib.reload(pf)
    # Reset module-level cache
    pf._PROTECTED_FILE_PATTERNS_CACHE = None
    return pf


def test_is_protected_path_agents_md(safety):
    """AGENTS.md 任何位置 → True (跟 v0.21 协议 1:1 配对)."""
    assert safety.is_protected_path("/home/user/project/AGENTS.md") is True
    assert safety.is_protected_path("/repo/subdir/AGENTS.md") is True
    assert safety.is_protected_path("AGENTS.md") is True


def test_is_protected_path_skills(safety):
    """~/.hermes/skills/ 任何文件 → True (跟 v0.21 协议 1:1 配对)."""
    assert safety.is_protected_path("/home/user/.hermes/skills/foo/SKILL.md") is True
    assert safety.is_protected_path("~/.hermes/skills/my-skill/skill.md") is True


def test_is_protected_path_memories(safety):
    """~/.hermes/memories/ 任何文件 → True (跟 v0.21 协议 1:1 配对)."""
    assert safety.is_protected_path("/home/user/.hermes/memories/session-1/memory.md") is True
    assert safety.is_protected_path("/root/.hermes/memories/x/y.md") is True


def test_is_protected_path_other_files_false(safety):
    """其他文件 → False (跟 mavis "UX 倒退审计" 1:1 配对, 0 改 happy path)."""
    assert safety.is_protected_path("/home/user/main.py") is False
    assert safety.is_protected_path("/repo/README.md") is False  # 0 跟 AGENTS.md 冲突
    assert safety.is_protected_path("/tmp/foo.txt") is False
    assert safety.is_protected_path("") is False  # edge case


def test_check_protected_file_raises_by_default(safety, monkeypatch):
    """默认 ON → 抛 ProtectedFileError (跟 v0.21 1:1 配对)."""
    monkeypatch.delenv("HERMES_NO_PROTECTED_FILES", raising=False)
    with patch("hermes_cli.config.get_config_value", return_value=None):
        with pytest.raises(safety.ProtectedFileError) as excinfo:
            safety.check_protected_file("/home/user/project/AGENTS.md", bypass=False)
        assert "AGENTS.md" in str(excinfo.value)


def test_check_protected_file_bypass_skips(safety, monkeypatch):
    """bypass=True → silent skip (跟 mavis "fix collateral issues in-scope" 1:1)."""
    monkeypatch.delenv("HERMES_NO_PROTECTED_FILES", raising=False)
    with patch("hermes_cli.config.get_config_value", return_value=None):
        # bypass=True → 0 抛错, 即使是受保护文件
        result = safety.check_protected_file("/home/user/project/AGENTS.md", bypass=True)
        assert result is None


def test_check_protected_file_disabled_via_env(safety, monkeypatch):
    """HERMES_NO_PROTECTED_FILES=1 → silent skip (跟 mavis "UX 倒退审计" 1:1 配对)."""
    monkeypatch.setenv("HERMES_NO_PROTECTED_FILES", "1")
    with patch("hermes_cli.config.get_config_value", return_value=None):
        result = safety.check_protected_file("/home/user/project/AGENTS.md", bypass=False)
        assert result is None


def test_check_protected_file_disabled_via_config(safety, monkeypatch):
    """~/.hermes/config.yaml: protected_files.enabled: false → silent skip."""
    monkeypatch.delenv("HERMES_NO_PROTECTED_FILES", raising=False)
    with patch(
        "hermes_cli.config.get_config_value",
        return_value={"enabled": False},
    ):
        result = safety.check_protected_file("/home/user/project/AGENTS.md", bypass=False)
        assert result is None


def test_check_protected_file_non_protected_passes(safety, monkeypatch):
    """非受保护文件 → 0 抛错, 返回 None (跟 mavis "UX 倒退审计" 1:1 配对, 0 改 happy path)."""
    monkeypatch.delenv("HERMES_NO_PROTECTED_FILES", raising=False)
    with patch("hermes_cli.config.get_config_value", return_value=None):
        # /home/user/main.py 不是受保护文件
        result = safety.check_protected_file("/home/user/main.py", bypass=False)
        assert result is None
        # /repo/README.md 也不是 (只匹配 **/AGENTS.md, 不匹配 README.md)
        result = safety.check_protected_file("/repo/README.md", bypass=False)
        assert result is None

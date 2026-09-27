"""Tests for agent.safety.protected_files (Sprint 16 档 C.1).

跟 mavis MEMORY:
- 后端先调查再设计 (memory:13-17): 测试 3 类文件 1:1 配对 + bypass / disabled 路径
- UX 倒退审计 (memory:19-23): 测试其他文件 0 干扰 (Sprint 15 CAND-086 1:1)
- Cherry-pick split bug class (memory:7-11): 测试 0 改现有 write_file / patch happy path

回归 (2026-09-26, session 20260926_081554): _is_protected_files_enabled 曾把
`hermes config get` 的 CLI 打印函数 get_config_value 当 getter 用——config 里
没有 protected_files key 时它 sys.exit(1), SystemExit 不是 Exception, 穿透
except Exception 直达工具调用链杀死整个任务。本文件全部走真实 load_config
(conftest 已把 HERMES_HOME 隔离到 tmp), 0 mock config 读取层。
"""
from __future__ import annotations

import os
from pathlib import Path

import pytest


@pytest.fixture
def safety():
    """Load agent.safety fresh per test."""
    import importlib
    import agent.safety as mod
    importlib.reload(mod)
    import agent.safety.protected_files as pf
    importlib.reload(pf)
    return pf


def _write_config(text: str) -> None:
    from hermes_constants import get_hermes_home
    (get_hermes_home() / "config.yaml").write_text(text, encoding="utf-8")


def test_is_protected_path_agents_md(safety):
    """AGENTS.md 任何位置 → True (跟 v0.21 协议 1:1 配对)."""
    assert safety.is_protected_path("/home/user/project/AGENTS.md") is True
    assert safety.is_protected_path("/repo/subdir/AGENTS.md") is True
    assert safety.is_protected_path("AGENTS.md") is True


def test_is_protected_path_skills(safety):
    """~/.hermes/skills/ 任何文件 → True (跟 v0.21 1:1 配对)."""
    assert safety.is_protected_path("/home/user/.hermes/skills/foo/SKILL.md") is True
    assert safety.is_protected_path("~/.hermes/skills/my-skill/skill.md") is True


def test_is_protected_path_memories(safety):
    """~/.hermes/memories/ 任何文件 → True (跟 v0.21 1:1 配对)."""
    assert safety.is_protected_path("/home/user/.hermes/memories/session-1/memory.md") is True
    assert safety.is_protected_path("/root/.hermes/memories/x/y.md") is True


def test_is_protected_path_other_files_false(safety):
    """其他文件 → False (跟 mavis "UX 倒退审计" 1:1 配对, 0 改 happy path)."""
    assert safety.is_protected_path("/home/user/main.py") is False
    assert safety.is_protected_path("/repo/README.md") is False  # 0 跟 AGENTS.md 冲突
    assert safety.is_protected_path("/tmp/foo.txt") is False
    assert safety.is_protected_path("") is False  # edge case


def test_enabled_defaults_on_when_config_key_absent(safety, monkeypatch, capsys):
    """config 无 protected_files key → 默认 ON, 0 SystemExit / 0 stderr 噪音.

    回归测试: 旧实现调 get_config_value (CLI 打印函数), key 缺失时打印
    "Config key not set" 并 sys.exit(1)。
    """
    monkeypatch.delenv("HERMES_NO_PROTECTED_FILES", raising=False)
    assert safety._is_protected_files_enabled() is True
    captured = capsys.readouterr()
    assert "Config key not set" not in captured.err
    assert "Config key not set" not in captured.out


def test_enabled_off_via_config(safety, monkeypatch):
    """config.yaml protected_files.enabled: false → OFF (真实 load_config 路径)."""
    monkeypatch.delenv("HERMES_NO_PROTECTED_FILES", raising=False)
    _write_config("protected_files:\n  enabled: false\n")
    assert safety._is_protected_files_enabled() is False


def test_check_protected_file_raises_by_default(safety, monkeypatch, capsys):
    """默认 ON → 抛 ProtectedFileError (跟 v0.21 1:1 配对).

    SystemExit 不是 ProtectedFileError, 若闸门再泄 SystemExit 本测试必红。
    """
    monkeypatch.delenv("HERMES_NO_PROTECTED_FILES", raising=False)
    with pytest.raises(safety.ProtectedFileError) as excinfo:
        safety.check_protected_file("/home/user/project/AGENTS.md", bypass=False)
    assert "AGENTS.md" in str(excinfo.value)
    assert "Config key not set" not in capsys.readouterr().err


def test_check_protected_file_bypass_skips(safety, monkeypatch):
    """bypass=True → silent skip (跟 mavis "fix collateral issues in-scope" 1:1)."""
    monkeypatch.delenv("HERMES_NO_PROTECTED_FILES", raising=False)
    result = safety.check_protected_file("/home/user/project/AGENTS.md", bypass=True)
    assert result is None


def test_check_protected_file_disabled_via_env(safety, monkeypatch):
    """HERMES_NO_PROTECTED_FILES=1 → silent skip (跟 mavis "UX 倒退审计" 1:1 配对)."""
    monkeypatch.setenv("HERMES_NO_PROTECTED_FILES", "1")
    result = safety.check_protected_file("/home/user/project/AGENTS.md", bypass=False)
    assert result is None


def test_check_protected_file_disabled_via_config(safety, monkeypatch):
    """~/.hermes/config.yaml: protected_files.enabled: false → silent skip."""
    monkeypatch.delenv("HERMES_NO_PROTECTED_FILES", raising=False)
    _write_config("protected_files:\n  enabled: false\n")
    result = safety.check_protected_file("/home/user/project/AGENTS.md", bypass=False)
    assert result is None


def test_check_protected_file_non_protected_passes(safety, monkeypatch):
    """非受保护文件 → 0 抛错, 返回 None (跟 mavis "UX 倒退审计" 1:1 配对, 0 改 happy path)."""
    monkeypatch.delenv("HERMES_NO_PROTECTED_FILES", raising=False)
    result = safety.check_protected_file("/home/user/main.py", bypass=False)
    assert result is None
    result = safety.check_protected_file("/repo/README.md", bypass=False)
    assert result is None

"""Tests for hermes_cli.profiles Profile consent gate (Sprint 16 档 B.4).

跟 mavis MEMORY:
- 后端先调查再设计 (memory:13-17): 测试覆盖 consent ON / OFF / fail-safe 3 路径
- UX 倒退审计 (memory:19-23): 测试 default profile 不触发 log, 仅 named profile 触发
- Cherry-pick split bug class (memory:7-11): 测试 0 破坏现有 list_profiles happy path

回归 (2026-09-26): _is_profile_consent_required 曾把 CLI 打印函数
get_config_value 当 getter 用, config 无 key 时 sys.exit(1)。本文件走真实
load_config (conftest 已把 HERMES_HOME 隔离到 tmp), 0 mock config 读取层。
"""
from __future__ import annotations

import io
from contextlib import redirect_stderr
from pathlib import Path
from unittest.mock import patch

import pytest


@pytest.fixture
def profiles_mod():
    """Load hermes_cli.profiles fresh per test (reset module-level state)."""
    import importlib
    import hermes_cli.profiles as mod
    importlib.reload(mod)
    return mod


def _write_config(text: str) -> None:
    from hermes_constants import get_hermes_home
    (get_hermes_home() / "config.yaml").write_text(text, encoding="utf-8")


def test_log_profile_consent_default_on_writes_to_stderr(profiles_mod, capsys):
    """Default consent ON (config 0 profile_consent_required) → log to stderr.

    回归测试: 旧实现 key 缺失时 sys.exit(1), SystemExit 会杀死调用方。
    """
    captured = io.StringIO()
    with redirect_stderr(captured):
        profiles_mod._log_profile_consent("test_profile", Path("/tmp/profiles/test_profile"))
    stderr_text = captured.getvalue()
    assert "[profile-consent]" in stderr_text
    assert "test_profile" in stderr_text
    # Windows path 可能用 \ 分隔, 用 str() 兼容 (跟 mavis "fix collateral issues in-scope" 1:1)
    assert str(Path("/tmp/profiles/test_profile")) in stderr_text or "\\tmp\\profiles\\test_profile" in stderr_text
    assert "Config key not set" not in capsys.readouterr().out


def test_log_profile_consent_explicit_off_skips_log(profiles_mod):
    """Config profile_consent_required: false → silent skip log (跟 mavis "UX 倒退审计" 1:1)."""
    _write_config("profile_consent_required: false\n")
    captured = io.StringIO()
    with redirect_stderr(captured):
        profiles_mod._log_profile_consent("test_profile", Path("/tmp/profiles/test_profile"))
    assert captured.getvalue() == ""


def test_log_profile_consent_config_error_failsafe_on(profiles_mod):
    """Config exception → fail-safe ON (跟 mavis 4 件套 Constitution 1:1 配对, 跟 v0.20.6 默认行为一致)."""
    captured = io.StringIO()
    with redirect_stderr(captured):
        with patch("hermes_cli.config.load_config", side_effect=RuntimeError("config broken")):
            profiles_mod._log_profile_consent("test_profile", Path("/tmp/profiles/test_profile"))
    stderr_text = captured.getvalue()
    assert "[profile-consent]" in stderr_text


def test_list_profiles_still_works_with_consent_gate(profiles_mod, tmp_path):
    """0 破坏现有 list_profiles happy path (跟 mavis "fix collateral issues in-scope" 1:1 配对).

    Empty profiles dir → 返回 [default profile] (跟 0 个 named profile).
    Default profile 不触发 consent log (因为 default 不通过 _log_profile_consent).
    """
    captured = io.StringIO()
    with redirect_stderr(captured):
        with patch.object(profiles_mod, "_get_default_hermes_home", return_value=tmp_path):
            with patch.object(profiles_mod, "_get_wrapper_dir", return_value=tmp_path):
                with patch.object(profiles_mod, "_get_profiles_root", return_value=tmp_path / "profiles"):
                    profiles = profiles_mod.list_profiles()
    # 0 named profiles → consent log 0 触发 (因为 0 named profiles 走 _log_profile_consent 路径)
    assert "[profile-consent]" not in captured.getvalue()

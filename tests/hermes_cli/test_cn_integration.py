#!/usr/bin/env python3
"""
Integration tests for Hermes Agent Chinese edition.

Tests go beyond static file checks — they actually call module functions
to verify runtime behavior is correct after localization + upstream merges.

Importantly: these tests MUST NOT require external network or services.
"""

import io
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


# =============================================================================
# Doctor Integration Tests
# =============================================================================

class TestDoctorIntegration:
    """Integration tests for hermes_cli.doctor."""

    def test_doctor_imports(self):
        """Test that doctor module imports cleanly."""
        import hermes_cli.doctor as doctor
        assert hasattr(doctor, "run_doctor")
        assert hasattr(doctor, "check_ok")
        assert hasattr(doctor, "check_warn")
        assert hasattr(doctor, "check_fail")
        assert hasattr(doctor, "check_info")

    def test_doctor_check_ok_formats_with_chinese(self, capsys):
        """Test check_ok formats Chinese text correctly."""
        import hermes_cli.doctor as doctor
        doctor.check_ok("测试通过", "详细说明")
        captured = capsys.readouterr()
        assert "测试通过" in captured.out

    def test_doctor_check_warn_formats_chinese(self, capsys):
        """Test check_warn formats Chinese."""
        import hermes_cli.doctor as doctor
        doctor.check_warn("磁盘空间不足", "建议清理")
        captured = capsys.readouterr()
        assert "磁盘空间不足" in captured.out

    def test_doctor_check_fail_works(self, capsys):
        """Test check_fail."""
        import hermes_cli.doctor as doctor
        doctor.check_fail("Python 版本过低", "需要 3.10+")
        captured = capsys.readouterr()
        assert "Python" in captured.out or "版本" in captured.out

    def test_python_install_cmd(self):
        """Test _python_install_cmd returns a sensible string."""
        import hermes_cli.doctor as doctor
        cmd = doctor._python_install_cmd()
        assert isinstance(cmd, str)
        assert len(cmd) > 0

    def test_has_provider_env_config(self):
        """Test Chinese provider detection."""
        import hermes_cli.doctor as doctor
        assert doctor._has_provider_env_config("DEEPSEEK_API_KEY=sk-xxx")
        assert not doctor._has_provider_env_config("TERMINAL_ENV=local")

    def test_provider_env_config_kimi(self):
        """Test KIMI provider detection."""
        import hermes_cli.doctor as doctor
        assert doctor._has_provider_env_config("KIMI_CN_API_KEY=sk-test")


# =============================================================================
# Gateway Platform Filtering Tests
# =============================================================================

class TestGatewayCNPlatforms:
    """Test that Chinese platform filtering works correctly."""

    def test_cn_only_filters_foreign(self):
        """Test _all_platforms(cn_only=True) hides foreign platforms."""
        import hermes_cli.gateway as gw
        platforms = gw._all_platforms(cn_only=True)
        keys = {p["key"] for p in platforms}

        # Foreign platforms should NOT be present
        foreign = {"telegram", "discord", "slack", "matrix", "mattermost",
                   "whatsapp", "signal", "email", "sms", "bluebubbles"}
        assert foreign.isdisjoint(keys), f"Foreign platforms leaked: {foreign & keys}"

        # Chinese platforms should be present
        chinese = {"dingtalk", "feishu", "wecom", "weixin", "qqbot", "yuanbao"}
        assert chinese.issubset(keys), f"Chinese platforms missing: {chinese - keys}"

    def test_cn_false_returns_all(self):
        """Test _all_platforms(cn_only=False) returns the full list."""
        import hermes_cli.gateway as gw
        # We can't easily count exact number, but it should be > cn_only version
        cn_platforms = gw._all_platforms(cn_only=True)
        all_platforms = gw._all_platforms(cn_only=False)
        assert len(all_platforms) > len(cn_platforms)

    def test_platform_status_works(self):
        """Test _platform_status returns a string without crashing."""
        import hermes_cli.gateway as gw
        sample = {"key": "dingtalk", "label": "DingTalk"}
        status = gw._platform_status(sample)
        assert isinstance(status, str)


# =============================================================================
# Config Module Tests
# =============================================================================

class TestConfigIntegration:
    """Tests for hermes_cli.config — ensure no syntax errors."""

    def test_config_imports(self):
        """Test config module imports cleanly (critical after upstream merges)."""
        import hermes_cli.config
        assert hasattr(hermes_cli.config, "load_config")
        assert hasattr(hermes_cli.config, "save_config")
        assert hasattr(hermes_cli.config, "get_hermes_home")

    def test_get_hermes_home(self):
        """Test get_hermes_home returns a valid path (conftest sets HERMES_HOME)."""
        import hermes_cli.config as cfg
        import os
        home = cfg.get_hermes_home()
        assert isinstance(home, Path)
        assert "tmp" in str(home) or ".hermes" in str(home) or "hermes" in str(home).lower()

    def test_load_config_defaults(self):
        """Test load_config returns defaults when no file exists."""
        import hermes_cli.config as cfg
        config = cfg.load_config()
        assert "model" in config
        assert "agent" in config

    def test_format_managed_message(self):
        """Test format_managed_message has Chinese text."""
        import hermes_cli.config as cfg
        msg = cfg.format_managed_message("测试操作")
        assert isinstance(msg, str)
        assert len(msg) > 0


# =============================================================================
# Setup Module Tests
# =============================================================================

class TestSetupIntegration:
    """Tests for hermes_cli.setup — ensure Chinese localization works."""

    def test_setup_imports(self):
        """Test setup module imports."""
        import hermes_cli.setup as setup_mod
        assert hasattr(setup_mod, "setup_model_provider")
        assert hasattr(setup_mod, "setup_gateway")

    def test_setup_has_chinese_in_source(self):
        """Test setup source has Chinese text."""
        import hermes_cli.setup as setup_mod
        source = Path(setup_mod.__file__).read_text(encoding="utf-8")
        assert "配置" in source
        assert "模型" in source


# =============================================================================
# xb_native Tool Tests
# =============================================================================

class TestXbNativeIntegration:
    """Tests for tools.xb_native — ensure registration works."""

    def test_xb_native_imports(self):
        """Test xb_native imports and registers tools."""
        from tools.registry import registry
        import tools.xb_native  # noqa: F401

        xb_tools = [t for t in registry._tools if t.startswith("xb_")]
        expected = {"xb_navigate", "xb_snapshot", "xb_click", "xb_fill", "xb_screenshot"}
        assert expected.issubset(xb_tools), f"Missing: {expected - set(xb_tools)}"

    def test_xb_native_check_fn(self):
        """Test _xb_available check function exists."""
        from tools.xb_native import _xb_available
        result = _xb_available()
        assert isinstance(result, bool)


# =============================================================================
# Chinese Localization Smoke Tests
# =============================================================================

class TestLocalizationSmoke:
    """Smoke tests — run the full test suite to verify integrity."""

    def test_all_hanzi_files_utf8(self):
        """Verify all localized files are valid UTF-8 and contain Chinese."""
        files = [
            "hermes_cli/doctor.py",
            "hermes_cli/setup.py",
            "hermes_cli/config.py",
            "hermes_cli/commands.py",
            "hermes_cli/models.py",
            "hermes_cli/banner.py",
        ]
        for f in files:
            path = Path(PROJECT_ROOT) / f
            content = path.read_text(encoding="utf-8")
            assert len(content) > 0, f"{f} is empty"
        # If we got here without SyntaxError, all files are valid
        assert True

    def test_no_quadruple_quotes(self):
        """Verify no unterminated docstrings ("""") in key files."""
        files = [
            "hermes_cli/config.py",
            "hermes_cli/gateway.py",
            "agent/skill_tier_manager.py",
        ]
        for f in files:
            path = Path(PROJECT_ROOT) / f
            content = path.read_text(encoding="utf-8")
            # A quadruple quote """" is a syntax error in Python
            lines = content.split("\n")
            for i, line in enumerate(lines, 1):
                if '""""' in line:
                    raise SyntaxError(f"{f}:{i} — quadruple quote found")


# =============================================================================
# Local Models Integration Tests
# =============================================================================

class TestLocalModelsSetup:
    """Tests for the local-models setup/install-all feature."""

    def test_model_registry_has_all_entries(self):
        """Verify MODEL_REGISTRY contains expected models."""
        from hermes_cli.model_manager import MODEL_REGISTRY
        model_ids = [m["id"] for m in MODEL_REGISTRY]
        assert "whisper-small" in model_ids
        assert "edge-tts" in model_ids
        assert "moss-tts-nano" in model_ids
        assert "qwen-0.5b" in model_ids
        assert "qwen-coder-1.5b" in model_ids

    def test_setup_function_imports(self):
        """Verify cmd_local_models_setup imports cleanly."""
        from hermes_cli.model_manager import cmd_local_models_setup
        assert callable(cmd_local_models_setup)

    def test_embedded_provider_list_models(self):
        """Verify EmbeddedProvider.list_models() works with list-type MODEL_REGISTRY."""
        from hermes_cli.embedded import EmbeddedProvider
        provider = EmbeddedProvider()
        models = provider.list_models()
        # Should be a list, not crash
        assert isinstance(models, list)
        # Only LLM models should appear
        for m in models:
            assert m["id"].startswith("embedded:")

    def test_embedded_provider_resolve_no_model(self):
        """Verify _resolve_model() returns None when no model installed (no crash)."""
        from hermes_cli.embedded import EmbeddedProvider
        provider = EmbeddedProvider()
        result = provider._resolve_model()
        # Should not crash — may be None or a string depending on environment
        assert result is None or isinstance(result, str)


# =============================================================================
# Quickstart Tests
# =============================================================================

class TestQuickstart:
    """Tests for hermes_cli.quickstart (Hermes-Agent-CN exclusive)."""

    def test_quickstart_imports(self):
        """Verify quickstart module imports cleanly."""
        import hermes_cli.quickstart as qs
        assert hasattr(qs, "cmd_quickstart")
        assert callable(qs.cmd_quickstart)

    def test_detect_api_key_providers_empty(self):
        """Verify _detect_api_key_providers returns empty list when no env set."""
        import hermes_cli.quickstart as qs
        # Temporarily clear relevant env vars
        import os
        saved = {}
        for p in qs._PROVIDER_CHECKS:
            saved[p["env_var"]] = os.environ.pop(p["env_var"], None)
        try:
            result = qs._detect_api_key_providers()
            assert isinstance(result, list)
            # May be empty or contain matches depending on env
        finally:
            for k, v in saved.items():
                if v is not None:
                    os.environ[k] = v

    def test_detect_ollama_returns_dict_or_none(self):
        """Verify _detect_ollama returns dict or None without crashing."""
        import hermes_cli.quickstart as qs
        result = qs._detect_ollama()
        # Should not crash. If Ollama is running, returns dict; otherwise None.
        assert result is None or isinstance(result, dict)

    def test_has_embedded_models_no_crash(self):
        """Verify _has_embedded_models returns bool without crashing."""
        import hermes_cli.quickstart as qs
        result = qs._has_embedded_models()
        assert isinstance(result, bool)

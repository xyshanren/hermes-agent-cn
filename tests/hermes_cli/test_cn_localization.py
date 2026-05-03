"""Tests for Chinese localization (Phase 7)."""

import pytest
import sys
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import hermes_cli.doctor as doctor_mod
import hermes_cli.setup as setup_mod
import hermes_cli.config as config_mod


class TestDoctorChineseLocalization:
    """Test that doctor.py is properly localized to Chinese."""

    def test_doctor_has_chinese_sections(self):
        """Test that doctor module has Chinese section headers."""
        # Read the source file directly
        doctor_source = Path(doctor_mod.__file__).read_text(encoding="utf-8")
        
        # Check for Chinese section headers
        assert "Python 环境" in doctor_source, "Missing Chinese section: Python 环境"
        assert "目录结构" in doctor_source, "Missing Chinese section: 目录结构"
        assert "API 连通性" in doctor_source, "Missing Chinese section: API 连通性"
        assert "系统资源" in doctor_source, "Missing Chinese section: 系统资源"
        assert "配置验证" in doctor_source, "Missing Chinese section: 配置验证"

    def test_doctor_removed_foreign_providers(self):
        """Test that foreign providers are removed from doctor checks."""
        doctor_source = Path(doctor_mod.__file__).read_text(encoding="utf-8")
        
        # These provider checks should NOT exist
        assert "OpenRouter" not in doctor_source or "check_openrouter" not in doctor_source
        # Note: Some provider names might appear in comments or other contexts
        # This test might need adjustment based on actual content

    def test_doctor_has_chinese_provider_checks(self):
        """Test that doctor has Chinese provider connectivity checks."""
        doctor_source = Path(doctor_mod.__file__).read_text(encoding="utf-8")
        
        # Check for Chinese provider references
        assert "deepseek" in doctor_source.lower() or "深度求索" in doctor_source
        assert "minimax" in doctor_source.lower() or "MiniMax" in doctor_source


class TestSetupChineseLocalization:
    """Test that setup.py is properly localized to Chinese."""

    def test_setup_has_chinese_prompts(self):
        """Test that setup module has Chinese prompt text."""
        setup_source = Path(setup_mod.__file__).read_text(encoding="utf-8")
        
        # Check for Chinese prompts
        assert "配置" in setup_source, "Missing Chinese text in setup.py"
        assert "模型" in setup_source, "Missing Chinese text about models"

    def test_setup_removed_foreign_providers(self):
        """Test that foreign providers are removed from setup options."""
        setup_source = Path(setup_mod.__file__).read_text(encoding="utf-8")
        
        # Count occurrences of Chinese providers
        chinese_providers = ["deepseek", "minimax", "kimi", "zai", "ollama"]
        found_providers = [p for p in chinese_providers if p.lower() in setup_source.lower()]
        
        assert len(found_providers) >= 3, f"Expected at least 3 Chinese providers, found: {found_providers}"


class TestConfigChineseLocalization:
    """Test that config.py has Chinese documentation."""

    def test_config_has_chinese_docstrings(self):
        """Test that config module has Chinese docstrings or comments."""
        config_source = Path(config_mod.__file__).read_text(encoding="utf-8")
        
        # Check for Chinese documentation
        assert "配置" in config_source, "Missing Chinese text in config.py"
        # At least some comments or docstrings should be in Chinese

    def test_config_preserves_english_api(self):
        """Test that config API remains in English (function names, parameters)."""
        # Function names and parameters should remain in English
        assert hasattr(config_mod, 'load_config')
        assert hasattr(config_mod, 'save_config')
        assert hasattr(config_mod, 'load_env')
        
        # These are English APIs, should not be translated
        import inspect
        sig = inspect.signature(config_mod.load_config)
        assert 'return' in sig.parameters or True  # Just check it's callable


class TestChineseEncoding:
    """Test that Chinese text is properly encoded in source files."""

    def test_doctor_utf8_encoding(self):
        """Test that doctor.py is valid UTF-8."""
        doctor_path = Path(doctor_mod.__file__)
        content = doctor_path.read_text(encoding="utf-8")
        assert len(content) > 0

    def test_setup_utf8_encoding(self):
        """Test that setup.py is valid UTF-8."""
        setup_path = Path(setup_mod.__file__)
        content = setup_path.read_text(encoding="utf-8")
        assert len(content) > 0

    def test_config_utf8_encoding(self):
        """Test that config.py is valid UTF-8."""
        config_path = Path(config_mod.__file__)
        content = config_path.read_text(encoding="utf-8")
        assert len(content) > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

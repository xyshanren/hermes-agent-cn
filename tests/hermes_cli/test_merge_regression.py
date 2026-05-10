#!/usr/bin/env python3
"""
Automated regression tests for the upstream/main merge into cn branch.

Covers the areas from TEST_REPORT.md that can be automated without
external services or interactive TTY:
- Module imports (no crashes after merge)
- Constants integrity
- Provider configuration
- Models catalog
- Auth module (incl. new MiniMax OAuth constants)
- CLI structure
- CN-specific localization
- Conflict marker absence
"""

from __future__ import annotations

import importlib
import os
import re
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


# =============================================================================
# 1. Module Import Smoke Tests
# =============================================================================

class TestModuleImports:
    """All hermes_cli modules must import cleanly after the merge."""

    CORE_MODULES = [
        "hermes_cli.models",
        "hermes_cli.auth",
        "hermes_cli.commands",
        "hermes_cli.doctor",
        "hermes_cli.setup",
        "hermes_cli.status",
        "hermes_cli.curator",
        "hermes_cli.providers",
        "hermes_cli.quickstart",
        "hermes_cli.model_manager",
    ]

    @pytest.mark.parametrize("module_name", CORE_MODULES)
    def test_module_imports(self, module_name):
        """Each module should import without NameError or SyntaxError."""
        mod = importlib.import_module(module_name)
        assert mod is not None


# =============================================================================
# 2. Conflict Marker Absence
# =============================================================================

class TestNoConflictMarkers:
    """No merge conflict markers should remain in any Python source file."""

    PY_FILES = list((PROJECT_ROOT / "hermes_cli").glob("*.py"))

    @pytest.mark.parametrize("py_file", PY_FILES, ids=lambda p: p.name)
    def test_no_conflict_markers(self, py_file):
        """File must not contain git conflict markers."""
        content = py_file.read_text(encoding="utf-8", errors="replace")
        assert "<<<<<<< " not in content, f"HEAD conflict marker in {py_file.name}"
        assert ">>>>>>> " not in content, f"upstream conflict marker in {py_file.name}"
        assert re.search(r"^=======\s*$", content, re.MULTILINE) is None, \
            f"Separator conflict marker in {py_file.name}"


# =============================================================================
# 3. Auth Module — MiniMax OAuth Constants
# =============================================================================

class TestAuthConstants:
    """Verify all MiniMax OAuth constants are defined after merge fix."""

    def test_minimax_oauth_constants_exist(self):
        """All MiniMax OAuth constants added by upstream must be present."""
        import hermes_cli.auth as auth
        required = [
            "MINIMAX_OAUTH_CLIENT_ID",
            "MINIMAX_OAUTH_SCOPE",
            "MINIMAX_OAUTH_GRANT_TYPE",
            "MINIMAX_OAUTH_GLOBAL_BASE",
            "MINIMAX_OAUTH_CN_BASE",
            "MINIMAX_OAUTH_GLOBAL_INFERENCE",
            "MINIMAX_OAUTH_CN_INFERENCE",
            "MINIMAX_OAUTH_REFRESH_SKEW_SECONDS",
        ]
        for name in required:
            assert hasattr(auth, name), f"Missing constant: {name}"

    def test_minimax_oauth_urls_are_strings(self):
        """OAuth URLs must be non-empty strings."""
        import hermes_cli.auth as auth
        for attr in (
            "MINIMAX_OAUTH_GLOBAL_BASE",
            "MINIMAX_OAUTH_CN_BASE",
            "MINIMAX_OAUTH_GLOBAL_INFERENCE",
            "MINIMAX_OAUTH_CN_INFERENCE",
        ):
            val = getattr(auth, attr)
            assert isinstance(val, str) and val.startswith("https://"), \
                f"{attr} should be an https URL, got {val!r}"

    def test_minimax_refresh_skew_is_positive_int(self):
        """Refresh skew must be a positive integer."""
        import hermes_cli.auth as auth
        assert isinstance(auth.MINIMAX_OAUTH_REFRESH_SKEW_SECONDS, int)
        assert auth.MINIMAX_OAUTH_REFRESH_SKEW_SECONDS > 0

    def test_existing_skew_constants_unchanged(self):
        """Pre-existing refresh skew constants must not have changed."""
        import hermes_cli.auth as auth
        assert auth.ACCESS_TOKEN_REFRESH_SKEW_SECONDS == 120
        assert auth.CODEX_ACCESS_TOKEN_REFRESH_SKEW_SECONDS == 120
        assert auth.QWEN_ACCESS_TOKEN_REFRESH_SKEW_SECONDS == 120


# =============================================================================
# 4. Models Catalog Integrity
# =============================================================================

class TestModelsCatalog:
    """Provider model lists must be correct after merge."""

    def test_openrouter_models_list(self):
        """OPENROUTER_MODELS must be a non-empty list of tuples."""
        from hermes_cli.models import OPENROUTER_MODELS
        assert isinstance(OPENROUTER_MODELS, list)
        assert len(OPENROUTER_MODELS) > 0
        for item in OPENROUTER_MODELS:
            assert isinstance(item, tuple) and len(item) == 2, \
                f"Expected (model_id, desc) tuple, got {item!r}"

    def test_openai_provider_models_exist(self):
        """'openai' provider must exist in _PROVIDER_MODELS."""
        from hermes_cli.models import _PROVIDER_MODELS
        assert "openai" in _PROVIDER_MODELS
        assert len(_PROVIDER_MODELS["openai"]) > 0

    def test_cn_providers_in_catalog(self):
        """Key CN providers must be present in _PROVIDER_MODELS."""
        from hermes_cli.models import _PROVIDER_MODELS
        cn_providers = ["minimax", "minimax-cn", "deepseek", "zai"]
        for prov in cn_providers:
            assert prov in _PROVIDER_MODELS, f"CN provider '{prov}' missing from catalog"

    def test_provider_model_ids_function(self):
        """provider_model_ids() must return a list for known providers."""
        from hermes_cli.models import provider_model_ids
        result = provider_model_ids("deepseek")
        assert isinstance(result, list)

    def test_no_conflict_marker_in_openai_list(self):
        """The 'openai' model list must not accidentally include a conflict marker."""
        from hermes_cli.models import _PROVIDER_MODELS
        for model_id in _PROVIDER_MODELS.get("openai", []):
            assert ">>>>>>>" not in model_id
            assert "<<<<<<<" not in model_id

    def test_is_anthropic_fast_model(self):
        """_is_anthropic_fast_model should correctly identify Opus 4.6."""
        from hermes_cli.models import _is_anthropic_fast_model
        assert _is_anthropic_fast_model("anthropic/claude-opus-4.6") is True
        assert _is_anthropic_fast_model("anthropic/claude-sonnet-4.5") is False
        assert _is_anthropic_fast_model("openai/gpt-4o") is False


# =============================================================================
# 5. Setup Module
# =============================================================================

class TestSetupModule:
    """Key functions in hermes_cli.setup must be present after merge."""

    def test_sanitize_pasted_input_exists(self):
        """Upstream added _sanitize_pasted_input; it must exist."""
        import hermes_cli.setup as setup
        assert hasattr(setup, "_sanitize_pasted_input"), \
            "_sanitize_pasted_input not found in setup.py"

    def test_sanitize_strips_paste_markers(self):
        """_sanitize_pasted_input must strip bracketed paste markers."""
        from hermes_cli.setup import _sanitize_pasted_input
        dirty = "\x1b[200~hello world\x1b[201~"
        clean = _sanitize_pasted_input(dirty)
        assert clean == "hello world"

    def test_sanitize_leaves_normal_input_unchanged(self):
        """Normal input must pass through unchanged."""
        from hermes_cli.setup import _sanitize_pasted_input
        normal = "sk-abc123"
        assert _sanitize_pasted_input(normal) == normal

    def test_curses_prompt_choice_has_description_param(self):
        """Upstream added description param to _curses_prompt_choice."""
        import inspect
        import hermes_cli.setup as setup
        sig = inspect.signature(setup._curses_prompt_choice)
        assert "description" in sig.parameters, \
            "_curses_prompt_choice missing 'description' parameter"


# =============================================================================
# 6. Providers Configuration
# =============================================================================

class TestProviders:
    """CN providers must be present; foreign-only providers trimmed."""

    def test_hermes_overlays_present(self):
        """HERMES_OVERLAYS must contain 5+1 CN providers."""
        from hermes_cli.providers import HERMES_OVERLAYS
        assert "deepseek" in HERMES_OVERLAYS
        assert "minimax" in HERMES_OVERLAYS
        assert "minimax-cn" in HERMES_OVERLAYS
        assert "kimi-for-coding" in HERMES_OVERLAYS
        assert "zai" in HERMES_OVERLAYS
        assert "ollama" in HERMES_OVERLAYS
        assert "embedded" in HERMES_OVERLAYS

    def test_provider_aliases(self):
        """Key CN provider aliases must resolve correctly."""
        from hermes_cli.providers import ALIASES
        assert ALIASES.get("kimi") == "kimi-for-coding"
        assert ALIASES.get("glm") == "zai"
        assert ALIASES.get("minimax-china") == "minimax-cn"


# =============================================================================
# 7. Commands Module
# =============================================================================

class TestCommandsModule:
    """Commands module must export the expected symbols."""

    def test_command_registry_exists(self):
        """COMMAND_REGISTRY must be a non-empty list."""
        from hermes_cli.commands import COMMAND_REGISTRY
        assert isinstance(COMMAND_REGISTRY, list)
        assert len(COMMAND_REGISTRY) > 5

    def test_resolve_command_function(self):
        """resolve_command must return a result for 'status'."""
        from hermes_cli.commands import resolve_command
        result = resolve_command("status")
        assert result is not None

    def test_gateway_help_lines_callable(self):
        """gateway_help_lines must return a list."""
        from hermes_cli.commands import gateway_help_lines
        result = gateway_help_lines()
        assert isinstance(result, list)


# =============================================================================
# 8. Doctor Module
# =============================================================================

class TestDoctorModule:
    """Doctor module functions must work correctly after merge."""

    def test_run_doctor_exists(self):
        import hermes_cli.doctor as doctor
        assert hasattr(doctor, "run_doctor")

    def test_local_model_check_section_exists(self):
        """doctor.py must contain the local model check code."""
        path = PROJECT_ROOT / "hermes_cli" / "doctor.py"
        content = path.read_text(encoding="utf-8")
        assert "本地模型" in content or "local_models" in content or "model_manager" in content, \
            "Local model check section missing from doctor.py"

    def test_no_quadruple_quotes(self):
        """No accidental """" (quadruple quote) should appear."""
        path = PROJECT_ROOT / "hermes_cli" / "doctor.py"
        content = path.read_text(encoding="utf-8")
        assert '""""' not in content, "Quadruple quote found — likely a docstring merge artifact"


# =============================================================================
# 9. Status Module
# =============================================================================

class TestStatusModule:
    """Status module must contain both CN and upstream provider keys."""

    def test_status_has_cn_providers(self):
        """status.py must list CN providers in the keys dict."""
        path = PROJECT_ROOT / "hermes_cli" / "status.py"
        content = path.read_text(encoding="utf-8")
        for provider in ("DeepSeek", "Kimi", "MiniMax"):
            assert provider in content, f"Status page missing CN provider: {provider}"

    def test_status_has_global_providers(self):
        """status.py should also list global providers added by upstream."""
        path = PROJECT_ROOT / "hermes_cli" / "status.py"
        content = path.read_text(encoding="utf-8")
        assert "OpenRouter" in content or "Anthropic" in content, \
            "Status page missing global provider listing"


# =============================================================================
# 10. CN Localization Sanity
# =============================================================================

class TestCNLocalization:
    """Key Chinese strings must still be present after merge."""

    LOCALIZATION_CHECKS = [
        ("hermes_cli/doctor.py", ["本地模型", "◆"]),
        ("hermes_cli/commands.py", ["hermes"]),   # commands file present
        ("hermes_cli/curator.py", ["Curator", "技能"]),
    ]

    @pytest.mark.parametrize("rel_path,keywords", LOCALIZATION_CHECKS)
    def test_localization_strings(self, rel_path, keywords):
        path = PROJECT_ROOT / rel_path
        content = path.read_text(encoding="utf-8")
        for kw in keywords:
            assert kw in content, \
                f"Localization string {kw!r} missing from {rel_path}"

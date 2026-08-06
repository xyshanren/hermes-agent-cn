"""Tests for CAND-046 (Sprint 7 Wave 1): 新模型注册 claude-sonnet-5/fugu-ultra."""

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent


def test_new_models_register_module_exists():
    p = REPO / "hermes_cli" / "new_models_register.py"
    assert p.exists(), f"{p} missing (CAND-046 main file)"
    src = p.read_text(encoding="utf-8")
    for fn in ("claude_sonnet_5_register", "fugu_ultra_register", "claude_fable_5_skip", "apply_new_models_register"):
        assert f"def {fn}" in src


def test_new_models_register_does_not_modify_model_list():
    cli_src = (REPO / "cli.py").read_text(encoding="utf-8")
    assert "new_models_register" not in cli_src


def test_cand_046_1_claude_sonnet_5_register_live():
    sys.path.insert(0, str(REPO))
    from hermes_cli.new_models_register import claude_sonnet_5_register
    result = claude_sonnet_5_register()
    assert result["model"] == "claude-sonnet-5"
    assert result["provider"] == "openrouter"
    assert result["available"] is True


def test_cand_046_2_fugu_ultra_register_live():
    sys.path.insert(0, str(REPO))
    from hermes_cli.new_models_register import fugu_ultra_register
    result = fugu_ultra_register()
    assert result["model"] == "fugu-ultra"
    assert result["provider"] == "nous"
    assert result["available"] is True


def test_cand_046_3_claude_fable_5_skip_live():
    sys.path.insert(0, str(REPO))
    from hermes_cli.new_models_register import claude_fable_5_skip
    result = claude_fable_5_skip()
    assert result["model"] == "claude-fable-5"
    assert result["available"] is False
    assert "rolled_back" in result["reason"]


def test_apply_new_models_register_combined_entry_live():
    sys.path.insert(0, str(REPO))
    from hermes_cli.new_models_register import apply_new_models_register
    result = apply_new_models_register()
    assert isinstance(result, list)
    assert len(result) == 3
    models = {r["model"] for r in result}
    assert models == {"claude-sonnet-5", "fugu-ultra", "claude-fable-5"}
    # claude-fable-5 marked unavailable
    fable = next(r for r in result if r["model"] == "claude-fable-5")
    assert fable["available"] is False

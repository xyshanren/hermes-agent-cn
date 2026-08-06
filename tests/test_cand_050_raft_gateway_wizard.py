"""Tests for CAND-050 (Sprint 7 Wave 1): Raft gateway setup wizard."""

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent


def test_raft_wizard_module_exists():
    p = REPO / "hermes_cli" / "raft_gateway_wizard.py"
    assert p.exists()
    src = p.read_text(encoding="utf-8")
    for fn in ("raft_wizard_steps_register", "raft_wizard_step_validate", "raft_wizard_finish", "apply_raft_wizard"):
        assert f"def {fn}" in src


def test_raft_wizard_does_not_modify_gateway():
    cli_src = (REPO / "cli.py").read_text(encoding="utf-8")
    assert "raft_gateway_wizard" not in cli_src


def test_cand_050_1_raft_wizard_steps_register_live():
    sys.path.insert(0, str(REPO))
    from hermes_cli.raft_gateway_wizard import raft_wizard_steps_register
    steps = raft_wizard_steps_register()
    assert steps == ["auth", "channel", "model", "finish"]
    assert len(steps) == 4


def test_cand_050_2_raft_wizard_step_validate_live():
    sys.path.insert(0, str(REPO))
    from hermes_cli.raft_gateway_wizard import raft_wizard_step_validate
    # 合法 step + value
    assert raft_wizard_step_validate("auth", "token123") is True
    # finish step 0 需 verify
    assert raft_wizard_step_validate("finish", None) is True
    # 非法 step
    assert raft_wizard_step_validate("invalid", "x") is False


def test_cand_050_3_raft_wizard_finish_live():
    sys.path.insert(0, str(REPO))
    from hermes_cli.raft_gateway_wizard import raft_wizard_finish
    # 全 value + finish step → ready True
    result = raft_wizard_finish("finish", {"auth": "a", "channel": "c", "model": "m"})
    assert result["ready"] is True
    assert result["missing"] == []
    # 缺 value → ready False + missing list
    result_partial = raft_wizard_finish("finish", {"auth": "a"})
    assert result_partial["ready"] is False
    assert "channel" in result_partial["missing"]
    assert "model" in result_partial["missing"]


def test_apply_raft_wizard_combined_entry_live():
    sys.path.insert(0, str(REPO))
    from hermes_cli.raft_gateway_wizard import apply_raft_wizard
    # 完整值
    result = apply_raft_wizard(current_step="finish", all_values={"auth": "a", "channel": "c", "model": "m"})
    assert isinstance(result, dict)
    assert result["steps"] == ["auth", "channel", "model", "finish"]
    assert result["step_valid"] is True
    assert result["finish"]["ready"] is True

"""Tests for CAND-062 (Sprint 8): 双端 Doctor 体系 (启动健康检查 + 客户端 UI)."""

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent


def test_doctor_dual_module_exists():
    p = REPO / "hermes_cli" / "doctor_dual.py"
    assert p.exists()
    src = p.read_text(encoding="utf-8")
    for fn in ("doctor_dual_healthcheck_run", "doctor_dual_results_format",
               "doctor_dual_fix_link", "apply_doctor_dual"):
        assert f"def {fn}" in src


def test_doctor_dual_does_not_modify_doctor():
    cli_src = (REPO / "cli.py").read_text(encoding="utf-8")
    assert "doctor_dual" not in cli_src


def test_cand_062_1_doctor_dual_healthcheck_run_live():
    sys.path.insert(0, str(REPO))
    from hermes_cli.doctor_dual import doctor_dual_healthcheck_run
    result = doctor_dual_healthcheck_run()
    assert "auth" in result
    assert "channel" in result
    assert "model_provider" in result
    assert "memory_backend" in result
    assert "plugin_marketplace" in result
    # skeleton 全部 OK
    for check, data in result.items():
        assert data["status"] == "ok"


def test_cand_062_2_doctor_dual_results_format_live():
    sys.path.insert(0, str(REPO))
    from hermes_cli.doctor_dual import doctor_dual_results_format
    # 全部 OK
    results = {
        "auth": {"status": "ok"},
        "channel": {"status": "ok"},
        "model_provider": {"status": "ok"},
    }
    formatted = doctor_dual_results_format(results)
    assert formatted["total"] == 3
    assert formatted["ok"] == 3
    assert formatted["failed"] == []
    assert formatted["summary"] == "all_ok"
    # 部分 failed
    results_partial = {
        "auth": {"status": "ok"},
        "channel": {"status": "failed"},
        "model_provider": {"status": "ok"},
    }
    formatted_partial = doctor_dual_results_format(results_partial)
    assert formatted_partial["summary"] == "1_failed"
    assert "channel" in formatted_partial["failed"]


def test_cand_062_3_doctor_dual_fix_link_live():
    sys.path.insert(0, str(REPO))
    from hermes_cli.doctor_dual import doctor_dual_fix_link
    # 合法 check
    result = doctor_dual_fix_link("auth")
    assert result["check"] == "auth"
    assert result["link"] == "/v1/tray/fix/auth"
    # 非法 check
    result_invalid = doctor_dual_fix_link("unknown")
    assert "error" in result_invalid
    assert result_invalid["link"] == ""


def test_apply_doctor_dual_combined_entry_live():
    sys.path.insert(0, str(REPO))
    from hermes_cli.doctor_dual import apply_doctor_dual
    result = apply_doctor_dual()
    assert isinstance(result, dict)
    assert set(result.keys()) == {"healthcheck", "format", "fix_link"}
    assert result["format"]["summary"] == "all_ok"
    assert len(result["fix_link"]) == 5

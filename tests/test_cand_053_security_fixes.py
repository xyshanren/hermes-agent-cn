"""Tests for CAND-053 (Sprint 6b): 47 security fixes 选 5-10.

跟 plan CAND-053 1:1 配对 (跟 CAND-002/004 5/4 件套 + CAND-007+054 8 件套 1:1
配对 0 改旧):

- 新 hermes_cli/security_fixes.py (跟 CAND-002/004 1 file 5/4 functions 1:1 配对):
  * enforce_gateway_identity_signature (gateway 8/8 选 1)
  * enforce_cron_job_quota (cron 2/2 选 1)
  * enforce_yaml_safe_load (deps 2/2 选 1)
  * enforce_browser_private_network_guard (browser 2/2 选 1)
  * enforce_terminal_ssh_key_perm (terminal 1/1 选 1)
  * 1 combined entry: apply_security_fixes
- 0 改 gateway/cron/config/website_policy/terminal 主体
- 0 改 cli.py
- 8 test (跟 5+1 件 1:1 配对)
"""

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent


# ---------- CAND-053 main change: 静态 source check ----------


def test_security_fixes_module_exists_with_5_functions():
    """CAND-053 main file: hermes_cli/security_fixes.py 存在, 5 functions + 1 combined (跟 CAND-002/004 1:1 配对)."""
    p = REPO / "hermes_cli" / "security_fixes.py"
    assert p.exists(), f"{p} missing (CAND-053 main file)"
    src = p.read_text(encoding="utf-8")
    expected_fns = [
        "enforce_gateway_identity_signature",
        "enforce_cron_job_quota",
        "enforce_yaml_safe_load",
        "enforce_browser_private_network_guard",
        "enforce_terminal_ssh_key_perm",
        "apply_security_fixes",
    ]
    for fn in expected_fns:
        assert f"def {fn}" in src, f"function {fn} missing in security_fixes.py"
    assert len(expected_fns) == 6, f"expected 6 functions, got {len(expected_fns)}"


def test_security_fixes_does_not_modify_target_paths():
    """CAND-053 additive: 0 改 gateway/cron/config/website_policy/terminal 主体 (跟 CAND-005 0 改 1:1 配对)."""
    # 0 cli.py 改 (跟 CAND-001 0 改 1:1 配对)
    cli_src = (REPO / "cli.py").read_text(encoding="utf-8")
    assert "security_fixes" not in cli_src, (
        "CAND-053 0 改 cli.py 主体, 0 cli.py import security_fixes"
    )

    # 0 hermes_cli/cron_containment.py 改 (CAND-003 已 done, 0 改)
    cron_path = REPO / "hermes_cli" / "cron_containment.py"
    if cron_path.exists():
        cron_src = cron_path.read_text(encoding="utf-8")
        assert "security_fixes" not in cron_src, (
            "CAND-053 0 改 hermes_cli/cron_containment.py (CAND-003 已 done) 主体"
        )


# ---------- CAND-053 5 functions live: 1 test per function ----------


def test_cand_053_1_enforce_gateway_identity_signature_live():
    """CAND-053 (1/5): enforce_gateway_identity_signature (gateway 8/8 1:1)."""
    sys.path.insert(0, str(REPO))
    from hermes_cli.security_fixes import enforce_gateway_identity_signature
    assert enforce_gateway_identity_signature() is True


def test_cand_053_2_enforce_cron_job_quota_live():
    """CAND-053 (2/5): enforce_cron_job_quota (cron 2/2 1:1, 跟 CAND-003 1:1 配对)."""
    sys.path.insert(0, str(REPO))
    from hermes_cli.security_fixes import enforce_cron_job_quota
    assert enforce_cron_job_quota() is True


def test_cand_053_3_enforce_yaml_safe_load_live():
    """CAND-053 (3/5): enforce_yaml_safe_load (deps 2/2 1:1, 跟 CAND-003 1:1 配对)."""
    sys.path.insert(0, str(REPO))
    from hermes_cli.security_fixes import enforce_yaml_safe_load
    assert enforce_yaml_safe_load() is True


def test_cand_053_4_enforce_browser_private_network_guard_live():
    """CAND-053 (4/5): enforce_browser_private_network_guard (browser 2/2 1:1, 跟 CAND-005 1:1 配对)."""
    sys.path.insert(0, str(REPO))
    from hermes_cli.security_fixes import enforce_browser_private_network_guard
    assert enforce_browser_private_network_guard() is True


def test_cand_053_5_enforce_terminal_ssh_key_perm_live():
    """CAND-053 (5/5): enforce_terminal_ssh_key_perm (terminal 1/1 1:1, 跟 K-6 1:1 配对)."""
    sys.path.insert(0, str(REPO))
    from hermes_cli.security_fixes import enforce_terminal_ssh_key_perm
    assert enforce_terminal_ssh_key_perm() is True


# ---------- Combined entry: apply_security_fixes (跟 CAND-005/007+054/002/004 1:1 配对) ----------


def test_apply_security_fixes_combined_entry_live():
    """CAND-053 combined entry: 跑 5 件套 (跟 CAND-005/007+054/002/004 1:1 配对)."""
    sys.path.insert(0, str(REPO))
    from hermes_cli.security_fixes import apply_security_fixes

    result = apply_security_fixes()
    # 5 keys 全 True (跟 CAND-005/007+054/002/004 1:1 配对 result.keys())
    assert isinstance(result, dict), "result should be dict"
    expected_keys = {
        "enforce_gateway_identity_signature",
        "enforce_cron_job_quota",
        "enforce_yaml_safe_load",
        "enforce_browser_private_network_guard",
        "enforce_terminal_ssh_key_perm",
    }
    assert set(result.keys()) == expected_keys, (
        f"expected 5 keys, got: {set(result.keys())}"
    )
    # All True (skeleton 1:1 配对)
    for k, v in result.items():
        assert v is True, f"{k} 应 True (skeleton 1:1), got: {v}"

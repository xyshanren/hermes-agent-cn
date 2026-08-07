"""Tests for CAND-059 (Sprint 8): User-defined deny rules UI bridge to hermes-tray."""

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent


def test_deny_rules_tray_bridge_module_exists():
    p = REPO / "hermes_cli" / "deny_rules_tray_bridge.py"
    assert p.exists()
    src = p.read_text(encoding="utf-8")
    for fn in ("deny_rules_tray_bridge_endpoint", "deny_rules_tray_bridge_serialize",
               "deny_rules_tray_bridge_dispatch", "apply_deny_rules_tray_bridge"):
        assert f"def {fn}" in src


def test_deny_rules_tray_bridge_does_not_modify_approvals_deny():
    cli_src = (REPO / "cli.py").read_text(encoding="utf-8")
    assert "deny_rules_tray_bridge" not in cli_src


def test_cand_059_1_deny_rules_tray_bridge_endpoint_live():
    sys.path.insert(0, str(REPO))
    from hermes_cli.deny_rules_tray_bridge import deny_rules_tray_bridge_endpoint
    result = deny_rules_tray_bridge_endpoint()
    assert result["endpoint"] == "/v1/tray/deny_rules"
    assert result["method"] == "GET"
    assert result["content_type"] == "application/json"


def test_cand_059_2_deny_rules_tray_bridge_serialize_live():
    sys.path.insert(0, str(REPO))
    from hermes_cli.deny_rules_tray_bridge import deny_rules_tray_bridge_serialize
    rules = ["*.secret", "/private/*", "**/api_keys.txt"]
    result = deny_rules_tray_bridge_serialize(rules)
    assert result["format"] == "fnmatch_glob"
    assert result["count"] == 3
    assert result["rules"] == rules


def test_cand_059_3_deny_rules_tray_bridge_dispatch_live():
    sys.path.insert(0, str(REPO))
    from hermes_cli.deny_rules_tray_bridge import deny_rules_tray_bridge_dispatch
    result = deny_rules_tray_bridge_dispatch(["*.secret"], event="created")
    assert result["event"] == "created"
    assert result["rules_count"] == 1
    assert result["dispatched"] is True


def test_apply_deny_rules_tray_bridge_combined_entry_live():
    sys.path.insert(0, str(REPO))
    from hermes_cli.deny_rules_tray_bridge import apply_deny_rules_tray_bridge
    result = apply_deny_rules_tray_bridge(rules=["*.secret", "/private/*"], event="updated")
    assert isinstance(result, dict)
    assert set(result.keys()) == {"endpoint", "serialize", "dispatch"}
    assert result["endpoint"]["endpoint"] == "/v1/tray/deny_rules"
    assert result["serialize"]["count"] == 2
    assert result["dispatch"]["event"] == "updated"

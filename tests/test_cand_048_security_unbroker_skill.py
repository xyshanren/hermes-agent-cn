"""Tests for CAND-048 (Sprint 7 Wave 1): Security/unbroker skill."""

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent


def test_unbroker_skill_module_exists():
    p = REPO / "hermes_cli" / "security_unbroker_skill.py"
    assert p.exists()
    src = p.read_text(encoding="utf-8")
    for fn in ("unbroker_skill_register", "unbroker_skill_scan", "unbroker_skill_quarantine", "apply_unbroker_skill"):
        assert f"def {fn}" in src


def test_unbroker_skill_does_not_modify_skill_registry():
    cli_src = (REPO / "cli.py").read_text(encoding="utf-8")
    assert "security_unbroker_skill" not in cli_src


def test_cand_048_1_unbroker_skill_register_live():
    sys.path.insert(0, str(REPO))
    from hermes_cli.security_unbroker_skill import unbroker_skill_register
    result = unbroker_skill_register()
    assert result["skill"] == "security/unbroker"
    assert result["enabled"] is True
    assert result["category"] == "security"


def test_cand_048_2_unbroker_skill_scan_live():
    sys.path.insert(0, str(REPO))
    from hermes_cli.security_unbroker_skill import unbroker_skill_scan
    artifacts = [
        {"id": "1", "tag": "broker", "data": "x"},
        {"id": "2", "tag": "normal", "data": "y"},
        {"id": "3", "tag": "broker", "data": "z"},
    ]
    hits = unbroker_skill_scan(artifacts)
    assert len(hits) == 2
    assert all(h["tag"] == "broker" for h in hits)


def test_cand_048_3_unbroker_skill_quarantine_live():
    sys.path.insert(0, str(REPO))
    from hermes_cli.security_unbroker_skill import unbroker_skill_quarantine
    hits = [{"id": "1"}, {"id": "3"}]
    result = unbroker_skill_quarantine(hits)
    assert result["quarantined_count"] == 2
    assert result["status"] == "quarantined"


def test_apply_unbroker_skill_combined_entry_live():
    sys.path.insert(0, str(REPO))
    from hermes_cli.security_unbroker_skill import apply_unbroker_skill
    artifacts = [
        {"id": "1", "tag": "broker"},
        {"id": "2", "tag": "normal"},
    ]
    result = apply_unbroker_skill(artifacts)
    assert isinstance(result, dict)
    assert result["register"]["skill"] == "security/unbroker"
    assert len(result["scan_hits"]) == 1
    assert result["quarantine"]["quarantined_count"] == 1

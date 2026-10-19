"""Behavior contract for the find-family approval sample table.

The sample table (scripts/approval_classifier_samples.py) encodes one row
per destructive-command shape: what the form is, and whether it must be
flagged. This test drives the REAL detector over that table, so a pattern
change that opens a bypass fails here rather than in production.

Contract, not snapshot:
  - every "dangerous" row must be flagged (deletion semantics, not the
    command's first word — find/xargs pipelines included);
  - every "clean" row must NOT be flagged (benign find usage stays
    approval-free, otherwise the gate becomes noise).
"""

import importlib.util
from pathlib import Path

import pytest

from tools.approval import detect_dangerous_command, detect_hardline_command

_SCRIPT = (
    Path(__file__).resolve().parents[2]
    / "scripts"
    / "approval_classifier_samples.py"
)
_spec = importlib.util.spec_from_file_location(
    "approval_classifier_samples", _SCRIPT
)
_samples_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_samples_mod)
SAMPLES = _samples_mod.SAMPLES


def _flagged(command: str) -> bool:
    is_hardline, _ = detect_hardline_command(command)
    if is_hardline:
        return True
    is_dangerous, _key, _desc = detect_dangerous_command(command)
    return is_dangerous


@pytest.mark.parametrize(
    "command,expected,note",
    [s for s in SAMPLES if s[1] == "dangerous"],
    ids=[s[2] for s in SAMPLES if s[1] == "dangerous"],
)
def test_destructive_form_is_flagged(command, expected, note):
    assert _flagged(command), f"destructive form not flagged: {command} ({note})"


@pytest.mark.parametrize(
    "command,expected,note",
    [s for s in SAMPLES if s[1] == "clean"],
    ids=[s[2] for s in SAMPLES if s[1] == "clean"],
)
def test_benign_form_is_not_flagged(command, expected, note):
    assert not _flagged(command), f"benign form flagged: {command} ({note})"


def test_incident_command_is_detected_not_bypassed():
    """The 2026-09-26 incident command must be detected as dangerous.

    The incident itself was NOT a detection gap (both the then-deployed code
    and current code flag it) — it slipped through the session-approval
    memory. Detection must stay covered so the two issues cannot be
    confused when the session-approval grain is revisited.
    """
    incident = next(s[0] for s in SAMPLES if "verbatim 2026-09-26" in s[2])
    is_dangerous, pattern_key, _desc = detect_dangerous_command(incident)
    assert is_dangerous
    assert pattern_key

"""Behavior contract for CN's shape-scoped session approvals.

A session approval ("Approve session" on a dangerous command) used to be
keyed ONLY by the pattern description — so approving "rm -rf <two dirs>"
silently authorized every later command whose description was also
"recursive delete", including a `find ... | xargs rm -rf` that deleted 326
directories unattended (2026-09-26, session 86d315; see
docs/approval-classifier-gaps.md).

The CN feature narrows a session approval to the SHAPE of the command that
was actually approved: same verb / same construct / same scale. The
contract asserted here:

  - same shape, different paths      -> still auto-approved (no extra friction)
  - same pattern key, different shape-> approval required again
  - scale change (one path -> many)  -> approval required again
  - permanent ("always") approvals   -> unchanged, still pattern-scoped
  - legacy session approvals (no shape recorded) -> unchanged
"""

import tools.approval as approval_module
from tools.approval import (
    _approval_shape,
    approve_permanent,
    approve_session,
    clear_session,
    is_approved,
)

PATTERN_KEY = "recursive delete"


def _reset(key: str = "shape_test_session") -> None:
    clear_session(key)
    approval_module._permanent_approved.discard(PATTERN_KEY)


class TestShapeFingerprint:
    def test_paths_do_not_change_the_shape(self):
        assert _approval_shape("rm -rf /tmp/build") == _approval_shape("rm -rf /srv/app/dist")

    def test_bulk_constructor_changes_the_shape(self):
        # The incident pair: same pattern key, different construct.
        assert _approval_shape("rm -rf /tmp/build") != _approval_shape(
            "find . -type d -name lib -print0 | xargs -0 rm -rf"
        )

    def test_flag_set_changes_the_shape(self):
        assert _approval_shape("rm -rf x") != _approval_shape("rm x")

    def test_operand_count_bucket_changes_the_shape(self):
        assert _approval_shape("rm -rf a") != _approval_shape("rm -rf a b c")

    def test_command_without_shape_signal_returns_empty(self):
        assert _approval_shape("echo hello") == ""


class TestShapeScopedSessionApproval:
    def test_same_shape_stays_approved(self):
        key = "shape_same"
        _reset(key)
        try:
            approve_session(key, PATTERN_KEY, command="rm -rf /tmp/build")
            assert is_approved(key, PATTERN_KEY, command="rm -rf /srv/other") is True
        finally:
            _reset(key)

    def test_bulk_shape_needs_a_new_approval(self):
        """The 2026-09-26 regression: a bulk deletion must not inherit a
        single-path approval that shares the pattern description."""
        key = "shape_bulk"
        _reset(key)
        try:
            approve_session(key, PATTERN_KEY, command="rm -rf /tmp/lib1 /tmp/lib2")
            bulk = "find . -type d -name lib -print0 | xargs -0 rm -rf"
            assert is_approved(key, PATTERN_KEY, command=bulk) is False
        finally:
            _reset(key)

    def test_scale_change_needs_a_new_approval(self):
        key = "shape_scale"
        _reset(key)
        try:
            approve_session(key, PATTERN_KEY, command="rm -rf /tmp/build")
            assert is_approved(key, PATTERN_KEY, command="rm -rf a b c") is False
        finally:
            _reset(key)

    def test_legacy_session_approval_without_shape_still_applies(self):
        key = "shape_legacy"
        _reset(key)
        try:
            approve_session(key, PATTERN_KEY)
            assert is_approved(key, PATTERN_KEY, command="find . | xargs rm -rf") is True
        finally:
            _reset(key)

    def test_permanent_approval_stays_pattern_scoped(self):
        key = "shape_permanent"
        _reset(key)
        try:
            approve_permanent(PATTERN_KEY)
            assert is_approved(key, PATTERN_KEY, command="find . | xargs rm -rf") is True
        finally:
            _reset(key)
            approval_module._permanent_approved.discard(PATTERN_KEY)

    def test_clear_session_drops_the_recorded_shapes(self):
        key = "shape_clear"
        _reset(key)
        try:
            approve_session(key, PATTERN_KEY, command="rm -rf /tmp/build")
            assert is_approved(key, PATTERN_KEY, command="rm -rf /tmp/build") is True
            clear_session(key)
            assert is_approved(key, PATTERN_KEY, command="rm -rf /tmp/build") is False
        finally:
            _reset(key)


class TestApprovalGateEndToEnd:
    """The gate itself must ask again — not just the helper predicates."""

    def test_bulk_deletion_prompts_again_after_single_path_session_approval(self, monkeypatch):
        key = "shape_gate"
        _reset(key)
        token = approval_module.set_current_session_key(key)
        monkeypatch.setenv("HERMES_INTERACTIVE", "1")
        try:
            approve_session(key, PATTERN_KEY, command="rm -rf lib1 lib2")
            prompts = []

            def _callback(command, description, **kwargs):
                prompts.append(command)
                return "deny"

            result = approval_module.check_dangerous_command(
                "find . -type d -name lib -print0 | xargs -0 rm -rf",
                "local",
                approval_callback=_callback,
            )
            assert prompts, "a bulk deletion must prompt again after a single-path session approval"
            assert result.get("approved") is False
        finally:
            approval_module.reset_current_session_key(token)
            _reset(key)

    def test_same_shape_deletion_does_not_prompt_again(self, monkeypatch):
        key = "shape_gate_same"
        _reset(key)
        token = approval_module.set_current_session_key(key)
        monkeypatch.setenv("HERMES_INTERACTIVE", "1")
        try:
            approve_session(key, PATTERN_KEY, command="rm -rf lib1 lib2")
            prompts = []

            def _callback(command, description, **kwargs):
                prompts.append(command)
                return "deny"

            result = approval_module.check_dangerous_command(
                "rm -rf other1 other2",
                "local",
                approval_callback=_callback,
            )
            assert not prompts, "the same shape must stay auto-approved"
            assert result.get("approved") is True
        finally:
            approval_module.reset_current_session_key(token)
            _reset(key)

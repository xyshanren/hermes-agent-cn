"""hermes routing patches CLI tests (Phase 3 Task 3).

Covers ``hermes_cli.main.cmd_routing_patches`` — the shell-side
companion to ``tools.routing_rule_manager_tool.routing_rule_manage``.
Tests are pure-Python (no subprocess, no network, no LLM) and use a
``tmp_path`` + ``HERMES_HOME`` override so the patch queue writes
never escape the test sandbox. CLI output is captured via pytest's
``capsys`` fixture so the assertions match exactly what an operator
would see on the terminal.
"""

import json
import os
from pathlib import Path
from types import SimpleNamespace

import pytest

from hermes_cli import config as _hc
from hermes_cli.main import _fmt_unix, cmd_routing_patches
from hermes_constants import (
    reset_hermes_home_override,
    set_hermes_home_override,
)
from tools import routing_rule_manager_tool as rrm


# ── Fixtures ────────────────────────────────────────────────────────────


@pytest.fixture
def fake_routing_home(tmp_path, monkeypatch):
    """Sandbox HERMES_HOME for the routing-patches CLI.

    Mirrors the ``fake_pending_dir`` / ``fake_hermes_home`` fixtures in
    the layer-1 / layer-1.1 tool tests so the test surface is uniform
    across the routing-patches stack (tool + CLI).
    """
    pending = tmp_path / "routing_patches" / "pending"
    pending.mkdir(parents=True, exist_ok=True)
    applied = tmp_path / "routing_patches" / "applied"
    applied.mkdir(parents=True, exist_ok=True)

    token = set_hermes_home_override(str(tmp_path))
    monkeypatch.setattr(rrm, "_pending_dir", lambda: pending)
    monkeypatch.setattr(rrm, "_applied_dir", lambda: applied)
    _hc._RAW_CONFIG_CACHE.clear()
    try:
        yield {"tmp_path": tmp_path, "pending": pending, "applied": applied}
    finally:
        _hc._RAW_CONFIG_CACHE.clear()
        reset_hermes_home_override(token)


def _queue(rule_id: str, params: dict) -> str:
    """Queue a patch via the layer-1 tool and return the patch id."""
    payload = json.loads(
        rrm.routing_rule_manage(
            action="patch", rule_id=rule_id, params=params
        )
    )
    assert payload["success"], payload
    return payload["patch_id"]


# ── bare `hermes routing patches` (no action) ───────────────────────────


class TestBareInvocation:
    def test_bare_shows_usage_summary(self, fake_routing_home, capsys):
        """``hermes routing patches`` (no sub-action) prints a one-line
        usage summary so an operator can see the sub-action set
        without ``--help``. Mirrors the ``hermes profile`` bare-call
        behavior (1:1 跟 sibling 1:1).
        """
        cmd_routing_patches(SimpleNamespace(patches_action=None))
        out = capsys.readouterr().out
        assert "routing patches" in out
        for kw in ("list", "show", "apply", "history"):
            assert kw in out, f"usage summary missing {kw!r}"


# ── list action ─────────────────────────────────────────────────────────


class TestList:
    def test_list_empty(self, fake_routing_home, capsys):
        cmd_routing_patches(SimpleNamespace(patches_action="list"))
        out = capsys.readouterr().out
        assert "No routing patches" in out

    def test_list_shows_pending_and_applied_sections(
        self, fake_routing_home, capsys
    ):
        """A 2-pending + 1-applied state should show both sections with
        the right counts. Mirrors the shell UX the operator expects
        (跟 `hermes profile list` 1:1 multi-section shape).
        """
        p1 = _queue("fallback_chain", {"chain_index": 0, "provider": "kimi"})
        _queue("vision_fallback_chain", {"chain_index": 1})
        json.loads(
            rrm.routing_rule_manage(
                action="apply", patch_id=p1, confirmed=True
            )
        )
        cmd_routing_patches(SimpleNamespace(patches_action="list"))
        out = capsys.readouterr().out
        # Two sections, with the right counts.
        assert "PENDING (1):" in out
        assert "APPLIED (1):" in out
        # The applied rule is named in the config_section column
        # (the operator can see exactly which rule landed via the
        # APPLIED row; PENDING shows the params of the still-queued
        # patch separately).
        assert "fallback_chain" in out
        assert "vision_fallback_chain" in out
        # The applied row carries the config_section.
        assert "model_routing.rules.fallback_chain" in out


# ── show action ─────────────────────────────────────────────────────────


class TestShow:
    def test_show_pending(self, fake_routing_home, capsys):
        pid = _queue("fallback_chain", {"chain_index": 0, "provider": "kimi"})
        cmd_routing_patches(
            SimpleNamespace(patches_action="show", patch_id=pid)
        )
        out = capsys.readouterr().out
        assert "status:            pending" in out
        assert "rule_id:           fallback_chain" in out
        assert "kimi" in out
        assert pid in out

    def test_show_applied(self, fake_routing_home, capsys):
        """An applied patch surfaces the audit-trail fields
        (applied_at, config_section) — the collateral fix from this
        commit stamps the moved record so the CLI doesn't have to
        cross-ref config.yaml.
        """
        pid = _queue("fallback_chain", {"chain_index": 0, "provider": "kimi"})
        json.loads(
            rrm.routing_rule_manage(
                action="apply", patch_id=pid, confirmed=True
            )
        )
        cmd_routing_patches(
            SimpleNamespace(patches_action="show", patch_id=pid)
        )
        out = capsys.readouterr().out
        assert "status:            applied" in out
        assert "config_section:    model_routing.rules.fallback_chain" in out
        # applied_at is a real timestamp now (not "-"), thanks to
        # the in-commit audit-trail stamp.
        assert "applied_at:        -" not in out, (
            "applied_at is still '-' — the moved record was not "
            "stamped with applied_at_unix (audit trail regression)"
        )

    def test_show_unknown_fails(self, fake_routing_home, capsys):
        cmd_routing_patches(
            SimpleNamespace(
                patches_action="show", patch_id="nonexistent-1234"
            )
        )
        out = capsys.readouterr().out
        assert "no patch with id" in out


# ── apply action (the CAND-085 4 铁律 + UX 倒退 gate) ─────────────────


class TestApply:
    def test_apply_without_confirmed_refuses(
        self, fake_routing_home, capsys
    ):
        """UX 倒退 1:1 防护: 不带 ``--confirmed`` 直接拒绝, 跟
        tool 的 ``confirmed is True`` 严格检查 1:1. 防 front-end
        typo / shell alias 静默 apply。
        """
        pid = _queue("fallback_chain", {"chain_index": 0, "provider": "kimi"})
        cmd_routing_patches(
            SimpleNamespace(
                patches_action="apply",
                patch_id=pid,
                confirmed=False,
            )
        )
        out = capsys.readouterr().out
        assert "Refusing to apply" in out
        assert "--confirmed" in out
        # Pending is untouched (no half-applied state).
        assert len(list(fake_routing_home["pending"].iterdir())) == 1
        assert len(list(fake_routing_home["applied"].iterdir())) == 0

    def test_apply_with_confirmed_writes_config_and_moves(
        self, fake_routing_home, capsys
    ):
        """The happy path: ``--confirmed`` is the explicit gate, the
        CLI delegates to the tool (which is the canonical source of
        the 5-step fail-fast), and the output shows the audit trail.
        """
        pid = _queue("fallback_chain", {"chain_index": 0, "provider": "kimi"})
        cmd_routing_patches(
            SimpleNamespace(
                patches_action="apply",
                patch_id=pid,
                confirmed=True,
            )
        )
        out = capsys.readouterr().out
        assert f"Patch {pid} applied" in out
        assert "rule_id:        fallback_chain" in out
        assert "config_section: model_routing.rules.fallback_chain" in out
        # Side effects (跟 layer 1.1 test 1:1):
        #   1. config.yaml has the section
        #   2. patch moved to applied/
        #   3. pending is empty
        cfg = _hc.read_raw_config() or {}
        assert "model_routing" in cfg
        assert "fallback_chain" in cfg["model_routing"]["rules"]
        assert list(fake_routing_home["pending"].iterdir()) == []
        assert len(list(fake_routing_home["applied"].iterdir())) == 1

    def test_apply_unknown_fails_idempotently(
        self, fake_routing_home, capsys
    ):
        """Re-applying or applying a never-queued id is rejected
        with a clear error. Mirrors the tool's idempotency check
        (二次 apply 找不到 patch fail-fast).
        """
        pid = _queue("fallback_chain", {"chain_index": 0, "provider": "kimi"})
        # First apply: success.
        first = json.loads(
            rrm.routing_rule_manage(
                action="apply", patch_id=pid, confirmed=True
            )
        )
        assert first["success"]
        # Second via CLI: should fail (idempotency 1:1).
        cmd_routing_patches(
            SimpleNamespace(
                patches_action="apply",
                patch_id=pid,
                confirmed=True,
            )
        )
        out = capsys.readouterr().out
        assert "apply failed" in out
        assert "no pending patch" in out


# ── history action (read-only, 跟 CAND-085 1:1) ───────────────────────


class TestHistory:
    def test_history_empty(self, fake_routing_home, capsys):
        cmd_routing_patches(SimpleNamespace(patches_action="history"))
        out = capsys.readouterr().out
        assert "No applied" in out

    def test_history_lists_only_applied(
        self, fake_routing_home, capsys
    ):
        """The history action is a *narrower* view of ``list`` — only
        the applied section. CAND-085 铁律 1: history is read-only;
        the operator can use it to audit which patches landed in
        config.yaml without scanning pending/.
        """
        p1 = _queue("fallback_chain", {"chain_index": 0, "provider": "kimi"})
        _queue("vision_fallback_chain", {"chain_index": 1})
        json.loads(
            rrm.routing_rule_manage(
                action="apply", patch_id=p1, confirmed=True
            )
        )
        cmd_routing_patches(SimpleNamespace(patches_action="history"))
        out = capsys.readouterr().out
        # Applied section appears, pending doesn't.
        assert "APPLIED (1):" in out
        assert "PENDING" not in out
        assert "model_routing.rules.fallback_chain" in out
        # The still-pending patch is *not* in history.
        assert "vision_fallback_chain" not in out


# ── _fmt_unix helper (smoke, no test isolation concerns) ───────────────


class TestFmtUnix:
    def test_formats_local_time(self):
        # 2026-08-05 17:00 UTC ≈ 2026-08-06 01:00 CST, but the
        # local-time formatting depends on the test environment;
        # just check the YYYY-MM-DD HH:MM shape.
        s = _fmt_unix(1754438400.0)  # 2025-08-05 16:00 UTC
        assert len(s) == 16
        assert s[4] == "-"
        assert s[10] == " "
        assert s[13] == ":"

    def test_returns_dash_for_none(self):
        assert _fmt_unix(None) == "-"

    def test_returns_dash_for_garbage(self):
        assert _fmt_unix("not-a-number") == "-"
        assert _fmt_unix(float("nan")) == "-"

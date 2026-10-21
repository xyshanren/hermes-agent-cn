"""Routing-patch management CLI (CN): list / show / apply / history (CAND-080 layer 1.1).

Split out of ``hermes_cli/main.py`` when upstream v0.22 replaced that file with
its refactored version; the CLI itself is CN-original and unchanged in behaviour.
It is the shell-side companion to
``tools.routing_rule_manager_tool.routing_rule_manage`` — the tool stays the
canonical source of the apply gate, this module is a thin wrapper around it.
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Callable


# ── helpers ─────────────────────────────────────────────────────────────


def _fmt_unix(unix_ts):
    """Format a unix timestamp as ``YYYY-MM-DD HH:MM`` (local time).

    Returns ``"-"`` when the timestamp is missing or non-numeric so the
    CLI output stays column-aligned when a record has a partial shape
    (e.g. a half-written file in pending/ that we're listing for the
    operator's benefit rather than crashing on).
    """
    if unix_ts is None:
        return "-"
    try:
        return time.strftime("%Y-%m-%d %H:%M", time.localtime(float(unix_ts)))
    except (TypeError, ValueError, OSError):
        return "-"


def _load_patch_records(directory: Path) -> list:
    """Return the JSON patch records stored in *directory*, sorted by name.

    Unreadable / non-JSON / non-``.json`` entries are skipped: a
    half-written file in pending/ must not crash the listing.
    """
    if not directory.exists():
        return []
    records = []
    for path in sorted(directory.iterdir()):
        if not path.name.endswith(".json") or path.name.startswith("."):
            continue
        try:
            rec = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        records.append(rec)
    return records


def _print_pending_section(pending_dir: Path) -> None:
    """Print the ``PENDING (n)`` table for the queued patches."""
    pending = sorted(pending_dir.iterdir()) if pending_dir.exists() else []
    if not pending:
        return
    print(f"\nPENDING ({len(pending)}):")
    print(
        f"  {'patch_id':<14} {'rule_id':<28} "
        f"{'queued_at':<20} params"
    )
    print(
        f"  {'─' * 13}  {'─' * 27}  "
        f"{'─' * 19}  {'─' * 30}"
    )
    for rec in _load_patch_records(pending_dir):
        queued_at = _fmt_unix(rec.get("queued_at_unix"))
        params_str = json.dumps(rec.get("params", {}), ensure_ascii=False)[:60]
        print(
            f"  {rec.get('patch_id', '?'):<14} "
            f"{rec.get('rule_id', '?'):<28} "
            f"{queued_at:<20} {params_str}"
        )


def _print_applied_section(applied_dir: Path) -> None:
    """Print the ``APPLIED (n)`` table for the patches that landed."""
    applied = sorted(applied_dir.iterdir()) if applied_dir.exists() else []
    if not applied:
        return
    print(f"\nAPPLIED ({len(applied)}):")
    print(
        f"  {'patch_id':<14} {'rule_id':<28} "
        f"{'applied_at':<20} config_section"
    )
    print(
        f"  {'─' * 13}  {'─' * 27}  "
        f"{'─' * 19}  {'─' * 30}"
    )
    for rec in _load_patch_records(applied_dir):
        applied_at = _fmt_unix(rec.get("applied_at_unix"))
        section = f"model_routing.rules.{rec.get('rule_id', '?')}"
        print(
            f"  {rec.get('patch_id', '?'):<14} "
            f"{rec.get('rule_id', '?'):<28} "
            f"{applied_at:<20} {section}"
        )


def _print_usage_summary() -> None:
    """Print the one-line usage summary for a bare ``hermes routing patches``."""
    print("\nrouting patches — manage queued + applied routing-rule patches")
    print("  list      show pending + applied sections")
    print("  show ID   show one patch by id (pending first, then applied)")
    print("  apply ID  apply a pending patch (REQUIRES --confirmed)")
    print("  history   show only the applied section (read-only)")
    print()


# ── sub-actions ─────────────────────────────────────────────────────────


def _action_list(args) -> None:
    """Show pending + applied patches in two sections (read-only)."""
    from tools.routing_rule_manager_tool import _applied_dir, _pending_dir

    pending_dir = _pending_dir()
    applied_dir = _applied_dir()
    pending = sorted(pending_dir.iterdir()) if pending_dir.exists() else []
    applied = sorted(applied_dir.iterdir()) if applied_dir.exists() else []
    if not pending and not applied:
        print("No routing patches.")
        return
    _print_pending_section(pending_dir)
    _print_applied_section(applied_dir)
    print()


def _action_show(args) -> None:
    """Show one patch by id — pending first (live state), then applied."""
    from tools.routing_rule_manager_tool import (
        _applied_dir,
        _find_pending_patch,
    )

    patch_id = getattr(args, "patch_id", None)
    if not patch_id:
        print("usage: hermes routing patches show <patch_id>")
        return
    path = _find_pending_patch(patch_id)
    if path is not None:
        rec = json.loads(path.read_text(encoding="utf-8"))
        print(f"\npatch_id:          {rec.get('patch_id', '?')}")
        print(f"status:            pending")
        print(f"rule_id:           {rec.get('rule_id', '?')}")
        print(f"description:       {rec.get('description', '?')}")
        print(f"owner:             {rec.get('owner', '?')}")
        print(
            f"params:            {json.dumps(rec.get('params', {}), ensure_ascii=False)}"
        )
        print(
            f"queued_at:         {_fmt_unix(rec.get('queued_at_unix'))}"
        )
        print(
            f"queued_path:       {path}"
        )
        print()
        return
    applied_dir = _applied_dir()
    if applied_dir.exists():
        for cand in sorted(applied_dir.iterdir()):
            try:
                rec = json.loads(cand.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            if rec.get("patch_id") == patch_id:
                print(f"\npatch_id:          {rec.get('patch_id', '?')}")
                print(f"status:            applied")
                print(f"rule_id:           {rec.get('rule_id', '?')}")
                print(
                    f"params:            {json.dumps(rec.get('params', {}), ensure_ascii=False)}"
                )
                print(
                    f"applied_at:        {_fmt_unix(rec.get('applied_at_unix'))}"
                )
                print(
                    f"config_section:    model_routing.rules.{rec.get('rule_id', '?')}"
                )
                print(f"applied_path:      {cand}")
                print()
                return
    print(f"no patch with id {patch_id!r} (pending or applied)")


def _action_apply(args) -> None:
    """Apply a pending patch — the only config-writing action; needs ``--confirmed``."""
    from tools.routing_rule_manager_tool import routing_rule_manage

    patch_id = getattr(args, "patch_id", None)
    if not patch_id:
        print("usage: hermes routing patches apply <patch_id> --confirmed")
        return
    # UX 倒退 1:1 防护: --confirmed 必须在 argv, 默认值 False。
    # 跟 tool 的 `confirmed is True` 严格检查 1:1 (拒绝 "true" / 1
    # / [True] 等 truthy non-bool, 防 front-end typo 静默 apply)。
    confirmed = bool(getattr(args, "confirmed", False))
    if not confirmed:
        print(
            "Refusing to apply without --confirmed. "
            "This is a config-writing step; pass --confirmed on the "
            "command line to land the patch in config.yaml."
        )
        return
    # Delegate to the tool. The tool is the canonical source of the
    # 5-step fail-fast gate (confirmed → patch_id → read patch →
    # re-validate → atomic write → move); the CLI is a thin wrapper
    # so the gate logic lives in exactly one place.
    result = json.loads(
        routing_rule_manage(
            action="apply",
            patch_id=patch_id,
            confirmed=True,
        )
    )
    if not result.get("success"):
        print(f"apply failed: {result.get('error', 'unknown error')}")
        return
    print(f"\nPatch {result['patch_id']} applied:")
    print(f"  rule_id:        {result['rule_id']}")
    print(f"  config_section: {result['config_section']}")
    print(f"  applied_at:     {_fmt_unix(result['applied_at_unix'])}")
    print(f"  applied_path:   {result['applied_path']}")
    print()


def _action_history(args) -> None:
    """Show only the applied section (read-only, 跟 CAND-085 1:1)."""
    from tools.routing_rule_manager_tool import _applied_dir

    applied_dir = _applied_dir()
    applied = sorted(applied_dir.iterdir()) if applied_dir.exists() else []
    if not applied:
        print("No applied routing patches (history empty).")
        return
    _print_applied_section(applied_dir)
    print()


_ACTION_HANDLERS: dict[str, Callable] = {
    "list": _action_list,
    "show": _action_show,
    "apply": _action_apply,
    "history": _action_history,
}


# ── entry point ─────────────────────────────────────────────────────────


def cmd_routing_patches(args):
    """Routing-patch management — list / show / apply / history (CAND-080 layer 1.1 CLI).

    Companion to ``tools.routing_rule_manager_tool.routing_rule_manage``. The
    Python surface is the canonical entry; this CLI wrapper exists so an
    operator can drive the apply path from the shell without importing
    anything. **Every** config-writing step goes through the same
    ``routing_rule_manage(action="apply", confirmed=True)`` gate the tool
    enforces — there is no second code path that bypasses the
    ``confirmed=True`` fail-fast. CAND-085 4 铁律 + UX 倒退 1:1.

    Sub-actions:
    - ``list``   — show pending + applied patches in two sections.
    - ``show``   — show one patch by id (searches pending first, then applied).
    - ``apply``  — apply a pending patch. **Requires** ``--confirmed``; the
      flag must be present on the command line (跟 tool 的
      ``confirmed is True`` 严格检查 1:1, 拒绝 "true" / 1 / [True] 等
      truthy non-bool 防 front-end typo 静默 apply).
    - ``history`` — show only the applied section (read-only, CAND-085 1:1).

    0 写回 hermes profile outside the apply path: list / show / history
    never touch config.yaml; apply 走 save_config atomic + is_managed() +
    preserve_env_ref_templates (跟 task 1 借现成 0 新模式).
    """
    action = getattr(args, "patches_action", None)

    if action is None:
        # Bare ``hermes routing patches`` — show a one-line usage summary
        # so an operator can see the sub-action set without ``--help``.
        _print_usage_summary()
        return

    handler = _ACTION_HANDLERS.get(action)
    if handler is None:
        print(
            f"unknown patches action {action!r}; "
            f"use list / show / apply / history."
        )
        return
    handler(args)

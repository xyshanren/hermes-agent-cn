"""``hermes sessions`` command.

``cmd_sessions`` routes ``args.sessions_action`` through ``_PRE_DB_HANDLERS`` (repair / recover /
import — must run without opening ``SessionDB()``, which a malformed schema prevents) and
``_DB_HANDLERS`` (everything else, sharing one ``SessionDB``). ``get_hermes_home`` is resolved through
``hermes_cli.main`` at call time so monkeypatches keep working. Picker: :mod:`hermes_cli.sessions_cmd_browse`.
"""

import json
import os
import shutil
import sqlite3
import sys
from functools import partial
from pathlib import Path

from hermes_cli.cli_output import print_truncated
from hermes_cli.sessions_cmd_browse import _relative_time, _session_browse_picker
from hermes_state_errors import SessionActiveWriteGuardError


def get_hermes_home():
    from hermes_cli import main
    return main.get_hermes_home()


def _sessions_dir() -> Path:
    return get_hermes_home() / "sessions"


def _size_mb(path) -> float:
    return os.path.getsize(path) / (1024 * 1024) if path.exists() else 0.0


def _size_delta_label(saved_mb: float) -> str:
    """A negative delta means the file GREW (concurrent writes during a long optimize); "reclaimed
    -163.0 MB" reads as data loss, so say "grew by"."""
    return f"reclaimed {saved_mb:.1f} MB" if saved_mb >= 0 else f"grew by {-saved_mb:.1f} MB"


def _confirm_prompt(prompt: str) -> bool:
    """Prompt for y/N confirmation, safe against non-TTY environments."""
    try:
        return input(prompt).strip().lower() in {"y", "yes"}
    except (EOFError, KeyboardInterrupt):
        return False


def _not_found(session_id) -> int:
    from agent.i18n import t

    print(t("sessions.session_not_found", session_id=session_id))
    return 1


def _print_dry_run_preview(candidates, filters) -> None:
    from agent.i18n import t
    from hermes_cli.session_filters import describe_filters
    print(t("sessions.export_would", count=len(candidates), filters=describe_filters(filters)))
    for row in candidates[:100]:
        print(f"  {row.get('id')}  {row.get('source', '')}")
    if len(candidates) > 100:
        print_truncated(len(candidates) - 100)


_FILTER_ARGS = (
    "older_than", "newer_than", "before", "after", "source", "title", "end_reason", "cwd", "min_messages",
    "max_messages", "model", "provider", "user", "chat_id", "chat_type", "branch", "min_tokens", "max_tokens",
    "min_cost", "max_cost", "min_tool_calls", "max_tool_calls",
)


def _any_filter_args(args) -> bool:
    return any(getattr(args, a, None) is not None for a in _FILTER_ARGS)


def _export_dir(output) -> Path:
    """``--output`` dir for multi-file exports; ``~/.hermes/session-exports`` when empty or ``-``."""
    return Path(output).expanduser() if output and output != "-" else get_hermes_home() / "session-exports"


def _output_file_in_dir(output, default_name: str):
    """Single-file exports accept a directory too (``--help`` calls the positional a path, and md/qmd take
    one): an existing directory, or one spelled with a trailing separator, means ``<dir>/<default_name>``."""
    if not output or output == "-":
        return output
    if output.endswith(("/", os.sep)) or os.path.isdir(output):
        os.makedirs(output, exist_ok=True)
        return os.path.join(output, default_name)
    return output


def _write_output(output, text, summary) -> None:
    """Write to stdout when *output* is empty or ``-``; else to the file + print *summary*."""
    if not output or output == "-":
        sys.stdout.write(text)
        return
    with open(output, "w", encoding="utf-8") as f:
        f.write(text)
    print(summary)


# -- handlers that must run BEFORE SessionDB() is opened ----------------------

def _cmd_repair(args):
    from hermes_state import DEFAULT_DB_PATH as db_path, SessionDB
    from hermes_state_repair import _db_opens_cleanly, repair_state_db_schema
    if not db_path.exists():
        from agent.i18n import t

        print(t("sessions.repair_no_db", path=db_path))
        return
    from hermes_state_reconcile import repair_declarative_schema, schema_drift_reason
    # A missing canonical sessions table is not additive upgrade drift: creating
    # an empty one could hide lost history. Preserve corruption/recovery routing.
    reason = _db_opens_cleanly(db_path)
    # Opens cleanly but lags SCHEMA_SQL: additive drift (snapshot reconcile), not corruption surgery.
    drift_only = reason is None
    if drift_only:
        try:
            reason = schema_drift_reason(db_path)
        except (sqlite3.Error, OSError) as exc:
            from agent.i18n import t

            print(t("sessions.repair_schema_check_failed", error=exc))
            return 1
    repair = repair_declarative_schema if drift_only else repair_state_db_schema
    if reason is None:
        from agent.i18n import t

        print(t("sessions.repair_opens_cleanly", path=db_path))
        return
    from agent.i18n import t

    print(t("sessions.repair_not_clean", path=db_path, reason=reason))
    if getattr(args, "check_only", False):
        return 1
    from agent.i18n import t

    print(t("sessions.repair_running"))
    report = repair(db_path, backup=not getattr(args, "no_backup", False))
    if report.get("repaired"):
        if report.get("backup_path"):
            from agent.i18n import t

            print(t("sessions.repair_backup", path=report['backup_path']))
        from agent.i18n import t

        print(t("sessions.repair_strategy", strategy=report.get('strategy')))
        try:
            with SessionDB(db_path=db_path, read_only=drift_only) as _repair_db:
                n = _repair_db._conn.execute("SELECT COUNT(*) FROM sessions").fetchone()[0]
            from agent.i18n import t

            print(t("sessions.repair_done_count", count=n))
        except Exception:
            from agent.i18n import t

            print(t("sessions.repair_done"))
        return
    from agent.i18n import t

    print(t("sessions.repair_failed", error=report.get('error')))
    if drift_only:
        if report.get('backup_path'):
            from agent.i18n import t

            print(t("sessions.repair_backup_preserved", path=report['backup_path']))
        return 1
    if report.get("backup_path"):
        from agent.i18n import t

        print(t("sessions.repair_backup_preserved", path=report['backup_path']))
    # Without this pointer the user is at a dead end; lead with --inspect-only before writing.
    from agent.i18n import t

    source_hint = report.get("backup_path") or db_path
    print(
        t("sessions.recover_keep_hint", source=source_hint)
    )


def _cmd_recover(args):
    """Offline recovery: works on a disposable copy of the source; never touches the active database."""
    import sqlite3
    from hermes_cli.session_recovery import (
        SessionRecoveryError, inspect_session_database, recover_session_database, write_recovery_report,
    )
    source, output = args.source, getattr(args, "output", None)
    inspect_only = bool(getattr(args, "inspect_only", False))
    allow_partial = bool(getattr(args, "allow_partial", False))
    report_path = getattr(args, "report", None)
    if not inspect_only and output is not None and report_path is None:
        report_path = output.with_name(output.name + ".recovery.json")
    usage_errors = (
        (inspect_only and output is not None, "--output cannot be used with --inspect-only."),
        (inspect_only and allow_partial, "--allow-partial cannot be used with --inspect-only."),
        (not inspect_only and output is None, "--output is required unless --inspect-only is used."),
        (
            report_path is not None and os.path.lexists(report_path.expanduser()),
            f"refusing to overwrite existing report: {report_path}",
        ),
    )
    for bad, msg in usage_errors:
        if bad:
            from agent.i18n import t

            print(t("sessions.usage_error", message=msg))
            return 2
    work_dir = getattr(args, "work_dir", None)
    try:
        if inspect_only:
            report = inspect_session_database(source, work_dir=work_dir)
        else:
            from agent.i18n import t

            print(t("sessions.recover_recovering"))
            progress = _RecoveryProgress()
            report = recover_session_database(
                source, output, work_dir=work_dir, chunk_size=getattr(args, "chunk_size", 1000),
                progress_cb=progress, allow_partial=allow_partial,
            )
            progress.finish()
    except (SessionRecoveryError, OSError, sqlite3.DatabaseError) as exc:
        from agent.i18n import t

        print(t("sessions.recover_failed", error=exc))
        return 1
    if report_path is None:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        try:
            from agent.i18n import t

            print(t("sessions.recover_report", path=write_recovery_report(report_path, report)))
        except (FileExistsError, OSError) as exc:
            from agent.i18n import t

            print(t("sessions.recover_report_failed", error=exc))
            return 1
    if inspect_only:
        return 0 if report.get("recoverable") else 1
    return _print_recovery_verdict(report, output, allow_partial)


class _RecoveryProgress:
    """`recover` progress printer: one live-updating ``  <table>: n/total`` line per table."""

    table = None

    def __call__(self, info):
        table = info.get("table")
        if table != self.table:
            self.finish()
            print(f"  {table}: ", end="", flush=True)
            self.table = table
        total = info.get("source_rows")
        suffix = f"/{int(total):,}" if total is not None else ""
        print(f"\r  {table}: {int(info.get('copied_rows') or 0):,}{suffix}", end="", flush=True)

    def finish(self):
        if self.table is not None:
            print()


def _print_recovery_verdict(report, output, allow_partial) -> int:
    from agent.i18n import t

    if report.get("complete"):
        print(t("sessions.recover_verified", output=output))
        return 0
    if allow_partial and report.get("verified"):
        counts = report.get("verification", {}).get("table_counts", {})
        if report.get("best_effort"):
            print(t("sessions.recover_best_effort", output=output))
        else:
            print(t("sessions.recover_partial_verified", output=output))
        sessions_n, messages_n = int(counts.get("sessions") or 0), int(counts.get("messages") or 0)
        print(
            t("sessions.recover_incomplete_summary",
              sessions=f"{sessions_n:,}", messages=f"{messages_n:,}")
        )
        return 0
    print(t("sessions.recover_failed_checks"))
    return 1


def _cmd_import(args):
    from hermes_cli.foreign_sessions import run_sessions_import
    # Explicit path but nothing imported -> non-zero for scripts. Picker cancel (no path) -> exit 0.
    if run_sessions_import(args) is None and getattr(args, "path", None):
        return 1


# -- handlers that receive an open SessionDB ----------------------------------

def _default_exclude(args):
    """Hide third-party tool sessions by default, but honour explicit --source."""
    return None if getattr(args, "source", None) else ["tool"]


def _cmd_list(db, args):
    from hermes_state_sessions import workspace_key as _ws_key
    # LIMIT lives in the query, so probe one row past the cap: it is the only way to know the
    # page was cut without a second COUNT query (``--limit 0`` is ``LIMIT 0``: no rows, no probe).
    limit = args.limit
    sessions = db.list_sessions_rich(
        source=args.source, exclude_sources=_default_exclude(args), limit=limit + 1 if limit > 0 else limit,
    )
    truncated = limit > 0 and len(sessions) > limit
    sessions = sessions[:limit] if truncated else sessions

    # Workspace filter: workspace key (git repo root, else cwd) — path substring or exact basename.
    _ws_filter = (getattr(args, "workspace", None) or "").strip()
    if _ws_filter:
        _needle = _ws_filter.lower()
        keyed = ((s, (_ws_key(s) or "").lower()) for s in sessions)
        sessions = [
            s for s, key in keyed if key and (_needle in key or _needle == os.path.basename(key.rstrip("/\\")))
        ]
    if not sessions:
        from agent.i18n import t

        print(t("sessions.no_sessions"))
        return

    # Workspace column only when some session carries a key (or when filtering): unbound listings read as before.
    has_ws = bool(_ws_filter) or any(_ws_key(s) for s in sessions)
    has_titles = any(s.get("title") for s in sessions)

    def _ws(s):  # repo/dir basename, "—" when unbound
        key = _ws_key(s)
        return ((os.path.basename(key.rstrip("/\\")) or key) if key else "—")[:16]
    _title = lambda s, n: (s.get("title") or "—")[:n]
    _preview = lambda s, n: s.get("preview", "")[:n]
    _ago = lambda s: _relative_time(s.get("last_active"), session_id=s["id"])

    def _src(s):  # current routing platform; "<created>→<current>" when provenance diverged (#56439)
        created = s.get("created_source") or ""
        return f"{created}→{s['source']}" if created and created != s["source"] else s["source"]
    layouts = {  # (has_ws, has_titles): header, rule width, row formatter
        (True, True): (f"{'Title':<28} {'Workspace':<18} {'Last Active':<13} {'ID'}", 110,
                       lambda s: f"{_title(s, 26):<28} {_ws(s):<18} {_ago(s):<13} {s['id']}"),
        (True, False): (f"{'Preview':<38} {'Workspace':<18} {'Last Active':<13} {'Src':<16} {'ID'}", 110,
                        lambda s: f"{_preview(s, 36):<38} {_ws(s):<18} {_ago(s):<13} {_src(s):<16} {s['id']}"),
        (False, True): (f"{'Title':<32} {'Preview':<40} {'Last Active':<13} {'ID'}", 110,
                        lambda s: f"{_title(s, 30):<32} {_preview(s, 38):<40} {_ago(s):<13} {s['id']}"),
        (False, False): (f"{'Preview':<50} {'Last Active':<13} {'Src':<16} {'ID'}", 105,
                         lambda s: f"{_preview(s, 48):<50} {_ago(s):<13} {_src(s):<16} {s['id']}"),
    }
    header, rule, fmt = layouts[(has_ws, has_titles)]
    print(header + "\n" + "─" * rule)
    for s in sessions:
        print(fmt(s))
    if truncated:
        print_truncated(None, f"use --limit {limit * 2} to see more")


# -- export -----------------------------------------------------------------

def _cmd_export(db, args):
    from hermes_cli.session_filters import build_prune_filters
    filters = None
    if _any_filter_args(args):
        try:
            filters = build_prune_filters(args)
        except ValueError as e:
            print(f"Error: {e}")
            return
        # A backup includes protected rows; prune's keep rules must not omit them.
        filters["archived"] = None
        filters["include_pinned"] = True
    if args.session_id and not db.resolve_session_id(args.session_id):
        return _not_found(args.session_id)

    def _redact(data):
        if not args.redact or data is None:
            return data
        from hermes_cli.session_export_md import redact_session_data
        return redact_session_data(data)

    from hermes_cli.session_export import SAVE_TRANSCRIPT_FORMATS, export_projection
    # --only is a transcript view too (md/jsonl of what the user saw); md/qmd without --only go to _export_markdown.
    shown = args.format in SAVE_TRANSCRIPT_FORMATS or bool(getattr(args, "only", None))
    projection = export_projection(shown)

    def _too_large(session_ids=None) -> bool:
        """The transfer projection holds every stored row in memory: the console export's per-session
        ``sessions.max_export_messages`` guard (0 disables) runs before any is loaded. ``None`` = the
        sessions a bare export loads."""
        from hermes_state import SessionExportTooLargeError, resolved_max_export_messages
        if shown:
            return False
        limit = resolved_max_export_messages()
        if limit == 0:
            return False  # resolved before the bare-path scan: a disabled guard costs nothing
        if session_ids is None:
            session_ids = [s["id"] for s in db.search_sessions(source=None, limit=100000)]
        try:
            db.assert_exports_safe(session_ids, max_messages=limit)
        except SessionExportTooLargeError as exc:
            print(f"Error: {exc}")
            return True
        return False

    def _collect_sessions():
        """--session-id / filters / bare export -> redacted session dicts, or None after printing an error."""
        def _one(session_id):
            return _redact(db.export_session(session_id, **projection))
        if args.session_id:
            resolved = db.resolve_session_id(args.session_id)
            if resolved and _too_large([resolved]):
                return None
            data = _one(resolved) if resolved else None
            if not data:
                _not_found(args.session_id)
                return None
            return [data]
        if filters:
            candidates = db.list_prune_candidates(**filters)
            if args.dry_run:
                return _print_dry_run_preview(candidates, filters)
            if _too_large([row["id"] for row in candidates]):
                return None
            return [s for s in (_one(row["id"]) for row in candidates) if s]
        if args.dry_run:
            return print("--dry-run requires at least one filter.")
        if _too_large():
            return None
        return [_redact(s) for s in db.export_all(source=None, **projection)]
    if getattr(args, "only", None):
        return _export_flat("only", args, _collect_sessions)
    if args.format == "trace":
        return _export_trace(db, args, filters)
    if args.format in _FLAT_EXPORTERS:
        return _export_flat(args.format, args, _collect_sessions)
    return _export_markdown(db, args, filters, _redact)


def _render_only(args, sessions):
    """--only user-prompts: one prompt record per line (jsonl) or headed sections (md)."""
    from hermes_cli.session_export import export_record_count, render_sessions_export
    rendered = render_sessions_export(sessions, fmt="markdown" if args.format == "md" else "jsonl", only=args.only)
    count, noun = export_record_count(sessions, only=args.only)
    return rendered, f"Exported {count} {noun}{'' if count == 1 else 's'} to {args.output}"


def _render_html(args, sessions):
    """One self-contained file (single session, or multi-session with sidebar)."""
    from hermes_cli.session_export_html import generate_html_export, generate_multi_session_html_export
    single = len(sessions) == 1
    content = generate_html_export(sessions[0]) if single else generate_multi_session_html_export(sessions)
    return content, f"Exported {len(sessions)} {'session' if single else 'sessions'} to {args.output} (HTML)"


def _render_jsonl(args, sessions):
    lines = "".join(json.dumps(s, ensure_ascii=False) + "\n" for s in sessions)
    return lines, f"Exported {len(sessions)} {'session' if args.session_id else 'sessions'} to {args.output}"


#: kind -> (usage error when the --output/--format combination is unusable, renderer)
_FLAT_EXPORTERS = {
    "only": (
        lambda a: a.format not in ("jsonl", "md"), "--only user-prompts supports --format jsonl or md.", _render_only
    ),
    "html": (lambda a: not a.output or a.output == "-", "HTML export requires an output file path.", _render_html),
    "jsonl": (lambda a: not a.output, "JSONL export requires an output path (use - for stdout).", _render_jsonl),
}


def _export_flat(kind, args, collect):
    """Single-file export: validate the output target, collect sessions, render, write."""
    unusable, message, render = _FLAT_EXPORTERS[kind]
    if unusable(args):
        print(message)
        return
    sessions = collect()
    if sessions is not None:
        from hermes_cli.session_export import default_save_filename
        name = (default_save_filename(sessions[0].get("id", ""), args.format) if len(sessions) == 1
                else f"hermes_sessions.{args.format}")
        args.output = _output_file_in_dir(args.output, name)
        _write_output(args.output, *render(args, sessions))


def _export_trace(db, args, filters):
    """Claude Code JSONL trace export — local file or HF upload. Redaction is ON by default (traces
    leave the machine with --upload); --no-redact opts out."""
    session_id = args.session_id
    if not session_id and not filters:  # "the last thing I did"
        rows = db.list_sessions_rich(limit=1, order_by_last_active=True)
        session_id = rows[0].get("id") if rows else None
        if not session_id:
            from agent.i18n import t

            print(t("sessions.export_none_found"))
            return
    from agent.trace_upload import TraceRedactionError, build_trace_jsonl, upload_session_trace
    redact_trace = not getattr(args, "no_redact", False)
    if getattr(args, "upload", False):
        if not session_id:
            print("--upload exports one session: pass --session-id (or drop filters to use the most recent).")
            return
        resolved = db.resolve_session_id(session_id)
        db.close()
        print(upload_session_trace(resolved, cwd="", redact=redact_trace, private=not getattr(args, "public", False)))
        return
    if session_id:
        ids = [db.resolve_session_id(session_id)]
    else:
        candidates = db.list_prune_candidates(**filters)
        if args.dry_run:
            return _print_dry_run_preview(candidates, filters)
        ids = [row["id"] for row in candidates]

    def _render_trace(sid):
        meta = db.get_session(sid) or {}
        messages = db.get_messages_as_conversation(sid)
        if not messages:
            return None
        return build_trace_jsonl(messages, session_id=sid, model=meta.get("model") or "", cwd="", redact=redact_trace)
    try:
        if len(ids) == 1:
            jsonl = _render_trace(ids[0])
            if not jsonl:
                from agent.i18n import t

                print(t("sessions.export_no_transcript", session_id=ids[0]))
                return
            args.output = _output_file_in_dir(args.output, f"{ids[0]}.trace.jsonl")
            from agent.i18n import t

            _write_output(args.output, jsonl, t("sessions.export_traces_done", count=1, dir=args.output))
        else:
            out_dir = _export_dir(args.output)
            out_dir.mkdir(parents=True, exist_ok=True)
            exported = 0
            for sid in ids:
                jsonl = _render_trace(sid)
                if jsonl:
                    (out_dir / f"{sid}.trace.jsonl").write_text(jsonl, encoding="utf-8")
                    exported += 1
            from agent.i18n import t

            print(t("sessions.export_traces_done", count=exported, dir=out_dir))
    except TraceRedactionError:
        from agent.i18n import t

        print(t("sessions.export_redaction_failed"))


def _export_markdown(db, args, filters, redact):
    """Markdown / QMD export: one file per session plus a manifest entry."""
    from hermes_cli.session_export_md import append_manifest_entry, write_session_markdown
    if args.output == "-":
        from agent.i18n import t

        print(t("sessions.export_stdout_unsupported"))
        return
    output_dir = _export_dir(args.output)

    def _export_one(session_id: str, *, include_lineage: bool = False):
        # The history the user sees, not only the live rows: in-place compaction archives earlier turns under
        # the same id, and --delete-after-verified removes every row of it.
        export = db.export_session_lineage if include_lineage else db.export_session
        raw_data = export(session_id, include_compacted=True)
        if not raw_data:
            return None, None, None
        snapshots = {
            segment["id"]: segment.get("messages") or []
            for segment in (raw_data.get("segments") or [raw_data]) if segment.get("id")
        }
        data = redact(raw_data)
        path = write_session_markdown(data, output_dir, fmt=args.format, force=args.force)
        append_manifest_entry(output_dir, data, path, fmt=args.format)
        return data, path, snapshots
    if args.delete_after_verified and not args.yes:
        from agent.i18n import t

        print(t("sessions.usage_error", message="--delete-after-verified requires --yes."))
        return
    if args.delete_after_verified and not args.session_id:
        from agent.i18n import t

        print(t("sessions.usage_error", message="--delete-after-verified is only supported with --session-id."))
        return
    lineage_is_logical = getattr(args, "lineage", "single") == "logical"
    if args.session_id:
        return _export_markdown_single(db, args, _export_one, output_dir, lineage_is_logical)
    if not filters:
        from agent.i18n import t

        print(t("sessions.export_bulk_refuse"))
        return
    candidates = db.list_prune_candidates(**filters)
    if args.dry_run:
        return _print_dry_run_preview(candidates, filters)
    exported = 0
    for row in candidates:
        try:
            data, exported_path, _ = _export_one(row["id"], include_lineage=lineage_is_logical)
        except FileExistsError as e:
            from agent.i18n import t

            print(t("sessions.export_skip_existing", error=e))
            continue
        if data and exported_path:
            exported += 1
    from agent.i18n import t

    print(t("sessions.export_done_sessions", count=exported, dir=output_dir))


def _export_markdown_single(db, args, export_one, output_dir, lineage_is_logical):
    """--session-id markdown export, optionally + verified delete of it and its delegates."""
    from hermes_cli.session_export_md import verify_export_file
    resolved_session_id = db.resolve_session_id(args.session_id)
    delete_target_ids = (
        db.get_session_delete_targets(resolved_session_id) if args.delete_after_verified else [resolved_session_id]
    )
    exported_items = []
    for target_id in delete_target_ids:
        try:
            data, exported_path, snapshots = export_one(
                target_id, include_lineage=(target_id == resolved_session_id and lineage_is_logical),
            )
        except FileExistsError as e:
            from agent.i18n import t

            print(t("sessions.export_exists", error=e))
            return
        if not data or not exported_path:
            from agent.i18n import t

            print(t("sessions.export_disappeared", session_id=target_id))
            return
        exported_items.append((data, exported_path, snapshots))
    message_count = sum(len(data.get("messages") or []) for data, _path, _ in exported_items)
    n = len(exported_items)
    from agent.i18n import t

    print(t("sessions.export_deleted_summary", count=n, messages=message_count,
            target=exported_items[0][1] if n == 1 else output_dir))
    if not args.delete_after_verified:
        return
    # verify_export_file proves file == dict; store == dict is decided inside delete_session's transaction
    # (expected_display_messages), where no writer can slip between the check and the delete.
    expected_messages = {}
    for data, exported_path, snapshots in exported_items:
        ok, reason = verify_export_file(exported_path, data)
        if not ok:
            from agent.i18n import t

            print(t("sessions.export_verify_failed", session_id=data.get('id'), reason=reason))
            return
        expected_messages.update(snapshots)
    try:
        if not db.delete_session(
            resolved_session_id, sessions_dir=_sessions_dir(), expected_delete_ids=delete_target_ids,
            expected_display_messages=expected_messages, exclude_active_write_guards=True,
        ):
            from agent.i18n import t

            print(t("sessions.export_not_deleted_changed", session_id=resolved_session_id))
            return
    except SessionActiveWriteGuardError as exc:
        from agent.i18n import t

        print(t("sessions.export_not_deleted_error", error=exc))
        return
    delegates = len(delete_target_ids) - 1
    delegate_suffix = f" and {delegates} delegate session{'' if delegates == 1 else 's'}" if delegates else ""
    from agent.i18n import t

    print(t("sessions.export_deleted", session_id=resolved_session_id, delegate_suffix=delegate_suffix))


# -- delete / prune / archive -------------------------------------------------

def _cmd_delete(db, args):
    resolved_session_id = db.resolve_session_id(args.session_id)
    if not resolved_session_id:
        return _not_found(args.session_id)
    # The delete is honored (explicit id), but a pin is a "keep" flag: say so instead of silently destroying it.
    _pinned_note = " (this session is PINNED)" if (db.get_session(resolved_session_id) or {}).get("pinned") else ""
    if not args.yes:
        from agent.i18n import t

        if not _confirm_prompt(t("sessions.delete_confirm", session_id=resolved_session_id, pinned=_pinned_note)):
            from agent.i18n import t

            print(t("sessions.cancelled"))
            return
    elif _pinned_note:
        from agent.i18n import t

        print(t("sessions.delete_pinned_warning", session_id=resolved_session_id))
    from hermes_state_runtime import RuntimeStoreError
    try:
        if not db.delete_session(resolved_session_id, sessions_dir=_sessions_dir(), exclude_active_write_guards=True):
            return _not_found(args.session_id)
    except SessionActiveWriteGuardError as exc:
        from agent.i18n import t

        print(t("sessions.delete_active_failed", error=exc))
        return 1
    except RuntimeStoreError as exc:
        # The ledger refuses to delete a session with accepted, unfinished turns; say what to do.
        from agent.i18n import t

        if exc.reason == 'unknown_execution':
            print(t("sessions.delete_turn_lost", session_id=resolved_session_id))
        elif exc.reason == 'session_busy':
            print(t("sessions.delete_busy", session_id=resolved_session_id))
        else:
            print(t("sessions.delete_refused", session_id=resolved_session_id, reason=exc.reason))
        return 1
    from agent.i18n import t

    print(t("sessions.delete_done", session_id=resolved_session_id))


#: Age floor for `prune --never-active`; generous: a young never-active row may be a chat nobody replied to yet.
_NEVER_ACTIVE_DEFAULT_DAYS = 30.0


def _prune_never_active_keyed(db, args):
    """`prune --never-active`: drop keyed gateway rows opened and never used (mostly escaped test
    fixtures). Separate from the shared prune/archive selector, which is pinned to `ended_at IS NOT
    NULL` — never-closed rows sit outside it by construction.

    The population is dominated by escaped test fixtures (#82770), which the hermetic-isolation guard can
    only stop from being *created* — rows already written to a developer's state.db need a sweep to leave.
    """
    from hermes_cli.session_filters import format_epoch, parse_duration_seconds
    older_than = getattr(args, "older_than", None)
    days = _NEVER_ACTIVE_DEFAULT_DAYS
    if older_than is not None:
        seconds = parse_duration_seconds(str(older_than))
        if seconds is None:
            from agent.i18n import t

            print(t("sessions.older_than_invalid", value=older_than))
            return
        days = seconds / 86400.0
    candidates = db.list_never_active_keyed_sessions(older_than_days=days)
    if not candidates:
        from agent.i18n import t

        print(t("sessions.prune_none", days=f"{days:g}"))
        return
    shown = candidates if args.dry_run else candidates[:15]
    from agent.i18n import t

    print(t("sessions.never_active_header", count=len(candidates), days=f"{days:g}"))
    for s in shown:
        print(f"  {s['id']}  {format_epoch(s.get('started_at')):<17} {(s.get('source') or '-'):<10} "
              f"{s.get('session_key') or '-'}")
    if len(candidates) > len(shown):
        print_truncated(len(candidates) - len(shown))
    if args.dry_run:
        from agent.i18n import t

        print(t("sessions.dry_run_nothing_deleted"))
        return
    if not args.yes and not _confirm_prompt(t("sessions.never_active_confirm", count=len(candidates))):
        from agent.i18n import t

        print(t("sessions.aborted"))
        return
    owner = getattr(args, "owner_endpoint", None)
    if owner is not None:
        from hermes_cli.gateway_client import GatewayClientError
        from hermes_cli.sessions_owner import owner_prune, report_owner_failure
        try:
            result = owner_prune(owner, never_active_days=days)
        except (GatewayClientError, OSError, TimeoutError) as exc:
            return report_owner_failure(exc)
        deleted, routing_deleted, skipped = result["deleted"], result["routing_deleted"], result["skipped"]
    else:
        deleted, routing_deleted, skipped = db.prune_never_active_keyed_sessions(
            older_than_days=days, sessions_dir=_sessions_dir()
        )
    print(t("sessions.prune_done", deleted=deleted, routing=routing_deleted))
    if skipped:
        from agent.i18n import t

        print(t("sessions.prune_skipped_locked", count=skipped))


def _note_pinned_skipped(db, filters, action):
    """Tell the user how many pinned rows bulk prune/archive spared (pin = durable keep; only
    `prune --include-pinned` opts in, archive always spares them)."""
    # Count matching pinned rows only: neither the unpinned ancestors a pinned tip spares nor the
    # unpinned continuations a pinned segment protects carry the pin.
    skipped = int(db.count_prune_matches(**filters, pinned_only=True))
    if not skipped:
        return
    from agent.i18n import t

    if action == "prune":
        verb = t("sessions.verb_deleted")
        optin = t("sessions.optin_prune")
    else:
        verb, optin = t("sessions.verb_archived"), t("sessions.optin_archive")
    print(t("sessions.pinned_note", count=skipped, verb=verb, optin=optin))


def _cmd_prune_or_archive(db, args, action):
    prune = action == "prune"
    if prune and getattr(args, "never_active", False):
        return _prune_never_active_keyed(db, args)
    from hermes_cli.session_filters import build_prune_filters, describe_filters, format_epoch
    # Bare `prune` keeps the historical "older than 90 days" default. ANY filter — including --source —
    # suppresses the implicit cutoff (`prune --source cron` matches ALL cron sessions); the preview +
    # confirmation below is the safety net.
    if prune and not _any_filter_args(args):
        args.older_than = "90"
    try:
        filters = build_prune_filters(args)
    except ValueError as e:
        from agent.i18n import t

        print(t("sessions.usage_error", message=e))
        return 1
    if not prune and not any(v for k, v in filters.items() if k != "older_than_days"):
        from agent.i18n import t

        print(t("sessions.archive_refuse_all"))
        return

    # Prune skips archived rows unless --include-archived; archive only targets not-yet-archived rows.
    filters["archived"] = None if prune and getattr(args, "include_archived", False) else False
    filters["include_pinned"] = getattr(args, "include_pinned", False)
    # Archive flips a compression lineage as a unit, matched through its tip (an old ancestor alone
    # never qualifies); the preview must show the same rows the archive will touch.
    filters["lineage_tips_only"] = not prune
    # Desktop sessions never set ended_at, so the shared ended-only selector hides them from archive
    # entirely (#139597); --include-open opts in for archive only — pruning is not reversible.
    include_open = not prune and getattr(args, "include_open", False)
    if include_open:
        filters["include_open"] = True
    if not filters["include_pinned"]:
        _note_pinned_skipped(db, filters, action)
    # Prune deletes a compression lineage only as a unit; the preview must list the rows it deletes.
    candidates = db.list_prune_candidates(**filters, whole_lineages=prune)
    # Archive expands each matched tip to its compression lineage, so a direct-open count would
    # misdescribe its effect.
    skipped_open = db.count_open_prune_matches(**filters) if (prune or not include_open) else 0
    if skipped_open and prune:
        from agent.i18n import t

        print(t("sessions.archive_open_note", count=skipped_open))
    elif skipped_open:
        from agent.i18n import t

        print(t("sessions.archive_match_note", count=skipped_open))
    if not candidates:
        from agent.i18n import t

        print(t("sessions.no_match", filters=describe_filters(filters)))
        return
    # Candidates are oldest-activity-first; show the span so a long-lived but recently used
    # conversation cannot look old merely by creation date.
    _span = (
        f"oldest activity {format_epoch(candidates[0].get('last_active'))}, "
        f"newest activity {format_epoch(candidates[-1].get('last_active'))}"
    )
    if args.dry_run or not args.yes:
        shown = candidates if args.dry_run else candidates[:15]
        print(f"{len(candidates)} session(s) match ({describe_filters(filters)}; {_span}):")
        for s in shown:
            model = (s.get("model") or "-").split("/")[-1][:24]
            print(f"  {s['id']}  {format_epoch(s.get('last_active')):<17} {s['source']:<10} {model:<24} "
                  f"{s['message_count']:>4} msgs  {(s.get('title') or '')[:36]}")
        if len(candidates) > len(shown):
            print_truncated(len(candidates) - len(shown))
        if args.dry_run:
            from agent.i18n import t

            print(t("sessions.dry_run_archived" if not prune else "sessions.dry_run_nothing_deleted"))
            return
    verb = t("sessions.verb_delete") if prune else t("sessions.verb_archive")
    if not args.yes and not _confirm_prompt(t("sessions.prune_confirm", verb=verb, count=len(candidates), span=_span)):
        from agent.i18n import t

        print(t("sessions.cancelled"))
        return
    if prune and getattr(args, "owner_endpoint", None) is not None:
        # The live gateway owns the store: it deletes, through the housekeeping retirement path.
        from agent.i18n import t
        from hermes_cli.gateway_client import GatewayClientError
        from hermes_cli.sessions_owner import owner_prune, report_owner_failure
        try:
            print(t("sessions.pruned_owner", count=owner_prune(args.owner_endpoint, filters=filters)['deleted']))
        except (GatewayClientError, OSError, TimeoutError) as exc:
            return report_owner_failure(exc)
    elif prune:
        from agent.i18n import t

        print(t("sessions.pruned_db", count=db.prune_sessions(sessions_dir=_sessions_dir(), exclude_active_write_guards=True, **filters)))
    else:
        from agent.i18n import t

        print(t("sessions.archived_done", count=db.archive_sessions(**filters)))


# -- titles / pins -----------------------------------------------------------

def _cmd_rename(db, args):
    resolved_session_id = db.resolve_session_id(args.session_id)
    if not resolved_session_id:
        return _not_found(args.session_id)
    title = " ".join(args.title)
    # Empty titles render as "—" and newlines corrupt the `list` table; length is validated in set_session_title.
    from agent.i18n import t

    if not title.strip():
        print(t("sessions.title_empty"))
        return 1
    if "\n" in title or "\r" in title:
        print(t("sessions.title_newlines"))
        return 1
    try:
        if not db.set_session_title(resolved_session_id, title):
            return _not_found(args.session_id)
    except ValueError as e:
        print(t("sessions.usage_error", message=e))
        return 1
    print(t("sessions.renamed", session_id=resolved_session_id, title=title))


def _cmd_pin(db, args, pinning):
    """Durable "keep" flag (exempt from sessions.auto_archive, always listed); every surface shares the store."""
    failures = 0
    # Pinned sessions are exempt from the sessions.auto_archive stale sweep and always surface in listings;
    # until now only the Desktop sidebar could write the flag. Inspired by Perplexity Computer's
    # conversational session management (pin/archive from any surface): pin state is operational
    # infrastructure, so every surface — GUI, TUI, CLI, scripts — needs read/write access to the same store.
    # See #52955.
    for raw_id in args.session_ids:
        resolved = db.resolve_session_id(raw_id)
        if resolved and db.set_session_pinned(resolved, pinning):
            title = db.get_session_title(resolved)
            print(f"{'Pinned' if pinning else 'Unpinned'} session '{resolved}'.{f'  ({title})' if title else ''}")
        else:
            failures += _not_found(raw_id)
    return 1 if failures else None


def _cmd_pinned(db, args):
    # limit=1 keeps the recency page minimal; include_pinned back-fills ALL pinned rows the page missed.
    rows = db.list_sessions_rich(limit=1, include_pinned=True, exclude_sources=_default_exclude(args))
    pinned_rows = [s for s in rows if s.get("pinned")]
    if getattr(args, "json", False):
        keys = ("title", "source", "last_active", "message_count")
        print(json.dumps([{"id": s["id"], **{k: s.get(k) for k in keys}} for s in pinned_rows], indent=2))
        return
    if not pinned_rows:
        from agent.i18n import t

        print(t("sessions.no_pinned"))
        return
    print(f"{'Title':<32} {'Last Active':<13} {'Src':<9} {'ID'}\n" + "─" * 100)
    for s in pinned_rows:
        title = (s.get("title") or s.get("preview", "") or "—")[:30]
        print(f"{title:<32} {_relative_time(s.get('last_active'), session_id=s['id']):<13} {(s.get('source') or '-'):<9} {s['id']}")


def _cmd_retitle_skills(db, args):
    from agent.skill_commands import describe_skill_invocation
    from agent.title_generator import generate_title
    limit = max(1, int(getattr(args, "limit", 200) or 200))
    apply_changes = bool(getattr(args, "apply", False))
    candidates = db.list_skill_scaffolded_sessions(limit=limit)
    if not candidates:
        from agent.i18n import t

        print(t("sessions.no_titled"))
        return
    mode = "" if apply_changes else " (dry run — pass --apply to write)"
    print(f"{len(candidates)} session(s) opened with a /skill{mode}:")
    changed = 0
    for row in candidates:
        session_id = row["id"]
        typed = describe_skill_invocation(row["content"]) or ""
        new_title = generate_title(typed)
        if not new_title or new_title == row["title"]:
            continue
        if not new_title[0].isalnum():
            # Non-title: an auxiliary model occasionally answers the prompt instead of titling it
            # ('$ df -h /'). This is a REPAIR — never replace a serviceable title with that.
            print(f"  {session_id}\n    kept {row['title']!r} — got {new_title!r}")
            continue
        print(f"  {session_id}\n    {row['title']!r}\n    → {new_title!r}")
        changed += 1
        if not apply_changes:
            continue
        try:
            db.set_session_title(session_id, new_title)
        except ValueError:  # unique-title collision: dedupe like the live auto-titler (base #2, #3, ...)
            deduped = db.get_next_title_in_lineage(new_title)
            try:
                db.set_session_title(session_id, deduped)
                print(f"    (renamed to {deduped!r} — title was taken)")
            except ValueError as e:
                print(f"    skipped: {e}")
                changed -= 1
    if not changed:
        print("  every title already reflects the user's request.")
    elif apply_changes:
        from agent.i18n import t

        print(t("sessions.retitled", count=changed))


def _cmd_browse(db, args):
    limit = getattr(args, "limit", 500) or 500
    sessions = db.list_sessions_rich(
        source=getattr(args, "source", None), exclude_sources=_default_exclude(args), limit=limit
    )
    if not sessions:
        db.close()
        from agent.i18n import t

        print(t("sessions.no_sessions"))
        return
    try:  # keep the DB open: the picker uses it for status tags and 'd' delete
        selected_id = _session_browse_picker(sessions, session_db=db)
    finally:
        db.close()
    if not selected_id:
        from agent.i18n import t

        print(t("sessions.cancelled"))
        return
    from agent.i18n import t

    print(t("sessions.resuming", session_id=selected_id))
    from hermes_cli.relaunch import relaunch
    relaunch(["--resume", selected_id])  # won't return after execvp


# -- storage maintenance -----------------------------------------------------

def _print_size_change(db, before_mb, prefix=""):
    """Report before/after size, preferring SQLite's page accounting over stat(): in WAL mode a VACUUM's
    rewrite sits in the -wal file until a checkpoint (refused while a live gateway holds a read-mark),
    so the main file lags and stat() can even go negative."""
    logical_after = db.logical_size_bytes()
    after_mb = logical_after / (1024 * 1024) if logical_after is not None else _size_mb(db.db_path)
    delta = _size_delta_label(before_mb - after_mb)
    print(f"{prefix}Database size: {before_mb:.1f} MB -> {after_mb:.1f} MB ({delta})")


def _cmd_optimize(db, args):
    before_mb = _size_mb(db.db_path)
    from agent.i18n import t

    print(t("sessions.optimizing_fts"))
    try:
        n = db.vacuum()  # merges FTS5 segments then VACUUMs; returns indexes merged
    except Exception as e:
        print(t("sessions.optimize_failed", error=e))
        return
    print(t("sessions.optimized_fts", count=n))
    _print_size_change(db, before_mb)


def _cmd_clean_markers(db, args):
    from agent.i18n import t

    print(f"{'Dry run — scanning' if args.dry_run else 'Scanning'} for stale tool-call marker rows (#78148)…")
    report = db.purge_stale_tool_call_markers(dry_run=args.dry_run, backup=not args.no_backup)
    if report["rows_affected"] == 0:
        print(t("sessions.clean_none"))
    elif args.dry_run:
        print(t("sessions.clean_would", count=report['rows_affected'], ids=report['row_ids']))
    else:
        if report["backup_path"]:
            print(t("sessions.repair_backup", path=report['backup_path']))
        print(t("sessions.clean_done", count=report['rows_affected']))


def _cmd_optimize_storage(db, args):
    db_path = db.db_path
    if not db.fts_optimize_available():
        from agent.i18n import t

        print(t("sessions.layout_compact"))
        return
    before_bytes = os.path.getsize(db_path) if db_path.exists() else 0
    before_mb = before_bytes / (1024 * 1024)
    # Disk preflight: the new index is built before the old is torn down, and VACUUM needs a full
    # second copy — require headroom ≈ current file size.
    do_vacuum = not getattr(args, "no_vacuum", False)
    try:
        free_bytes = shutil.disk_usage(db_path.parent).free
    except Exception:
        free_bytes = None
    need_bytes = before_bytes if do_vacuum else int(before_bytes * 0.3)
    from agent.i18n import t

    print(t("sessions.optimize_header", path=db_path, size=f"{before_mb:.1f} MB"))
    if free_bytes is not None:
        print(t("sessions.free_disk", free=f"{free_bytes / (1024*1024):.0f}",
                need=f"{need_bytes / (1024*1024):.0f}", vacuum=' incl. VACUUM' if do_vacuum else ''))
        if free_bytes < need_bytes:
            print(t("sessions.free_disk_low"))
            return
    if before_mb > 500:
        print(t("sessions.optimize_foreground_note"))
    if not getattr(args, "yes", False):
        try:
            resp = input("Proceed? [y/N] ").strip().lower()
        except EOFError:
            resp = ""
        if resp not in ("y", "yes"):
            from agent.i18n import t

            print(t("sessions.cancelled"))
            return
    _last = {"phase": None}
    labels = {"teardown": "Reclaiming old index", "vacuum": "Compacting database (VACUUM)", "done": "Done"}

    def _progress(info):
        phase = info.get("phase")
        if phase == "backfill":
            print(f"\r  Rebuilding index: {info.get('percent', 0):3d}% "
                  f"({info.get('indexed',0):,}/{info.get('total',0):,})", end="", flush=True)
        elif phase != _last["phase"]:
            print(f"\n  {labels.get(phase, phase)}…", flush=True)
        _last["phase"] = phase
    from agent.i18n import t

    print(t("sessions.optimizing_storage"))
    try:
        result = db.optimize_fts_storage(progress_cb=_progress, vacuum=do_vacuum)
    except Exception as e:
        from agent.i18n import t

        print(t("sessions.optimize_resume_failed", error=e))
        return
    if not result.get("ok"):
        print(t("sessions.optimize_not_ok", reason=result.get('reason', 'unknown')))
        return
    print(t("sessions.optimize_done"))
    _print_size_change(db, before_mb, prefix="  ")
    if result.get("vacuumed") is False:
        print(t("sessions.vacuum_skipped"))


def _cmd_repair_routing(db, args):
    from agent.i18n import t

    records = db.find_orphaned_gateway_sessions(max_gap_s=getattr(args, "max_gap_seconds", None))
    adoptable = [r for r in records if r["adoptable"]]
    for record in records:
        print(t("sessions.adopt_row", orphan_id=record['orphan_id'], source=record['source'],
                count=record['message_count']))
        if record["adoptable"]:
            print(t("sessions.adopt_into", key=record['session_key'], donor=record['donor_id'],
                    evidence=record['evidence']))
        else:
            print(t("sessions.adopt_not_repairable", reason=record['reason']))
    if not records:
        print(t("sessions.adopt_none_missing"))
        return
    if not adoptable:
        print(t("sessions.adopt_none_adoptable", count=len(records)))
        return
    if not getattr(args, "apply", False):
        print(t("sessions.adopt_reRun_apply", adoptable=len(adoptable), total=len(records)))
        return
    print(t("sessions.adopt_stop_gateway"))
    if not _confirm_prompt(t("sessions.adopt_confirm", count=len(adoptable))):
        print(t("sessions.aborted_em"))
        return
    repaired = 0
    for record in adoptable:
        if db.adopt_orphaned_gateway_session(record["orphan_id"], record["donor_id"]):
            repaired += 1
            print(t("sessions.adopt_done", orphan_id=record['orphan_id'], session_key=record['session_key']))
        else:
            print(t("sessions.adopt_stale", orphan_id=record['orphan_id']))
    print(f"\nRepaired {repaired} of {len(adoptable)} session(s).")


def _repair_prompts_pin_names(row) -> list[str] | None:
    """Resolve legacy name-list and current versioned tools[] pins to tool names.

    Any malformed or unknown shape is unverifiable and therefore never eligible for automatic
    repair. Current pins store full tool definitions in a versioned object; older rows may contain
    a JSON list of names directly.
    """
    try:
        pin = json.loads(row.get("tool_names") or "null")
    except (TypeError, ValueError):
        return None
    tools = pin.get("tools") if isinstance(pin, dict) else pin
    if not isinstance(tools, list):
        return None
    names: list[str] = []
    for item in tools:
        if isinstance(item, str):
            name = item
        elif isinstance(item, dict):
            function = item.get("function")
            name = function.get("name") if isinstance(function, dict) else None
        else:
            return None
        if not isinstance(name, str) or not name:
            return None
        names.append(name)
    return names


def _repair_prompts_lacks_skill_safety(row) -> bool:
    # Only the Skill Safety guidance is a reliable marker: <available_skills> is legitimately
    # absent when no skills are installed, but the guidance is emitted whenever skill_manage is.
    from agent.prompt_builder import SKILL_SAFETY_HEADING
    prompt = (row.get("system_prompt") or "").strip()
    return bool(prompt and SKILL_SAFETY_HEADING not in prompt)


def _cmd_repair_prompts(db, args):
    """Report (or clear) stored system prompts degraded to a reduced-toolset build (#122822).

    Automatic repair requires positive tools[] evidence. Rows with missing/malformed pins are
    reported as unverifiable and never changed by a scan. An explicit session_id remains the
    operator escape hatch and clears that row regardless of detector evidence.
    """
    findings = []
    unverifiable = []
    target = getattr(args, "session_id", None)
    if target:
        session_id = db.resolve_session_id(target)
        if not session_id:
            from agent.i18n import t

            print(t("sessions.no_match_target", target=repr(target)))
            return 1
        row = db.get_session(session_id)
        if row and row.get("system_prompt"):
            findings.append({
                "id": row["id"], "reason": "targeted clear", "prompt_chars": len(row["system_prompt"]),
            })
    else:
        seen = set()
        offset = 0
        while True:
            batch = db.list_sessions_rich(
                limit=200, offset=offset, include_children=True,
                include_archived=True, include_hidden=True, compact_rows=True,
            )
            if not batch:
                break
            offset += len(batch)
            for summary in batch:
                # OFFSET paging can re-serve a row when sessions are inserted mid-scan.
                if summary["id"] in seen:
                    continue
                seen.add(summary["id"])
                row = db.get_session(summary["id"])
                if not row or not _repair_prompts_lacks_skill_safety(row):
                    continue
                pin = _repair_prompts_pin_names(row)
                entry = {"id": row["id"], "prompt_chars": len(row["system_prompt"])}
                if "skill_manage" in (pin or ()):
                    findings.append({
                        **entry,
                        "reason": "Skill Safety guidance missing while the tools[] pin carries skill_manage",
                    })
                elif pin is None:
                    unverifiable.append({
                        **entry,
                        "reason": "skills markers missing but the tools[] pin is unavailable or unreadable",
                    })
                elif set(pin) == {"memory"}:
                    # Not proof: toolsets=[memory] is also a legitimate user config whose healthy
                    # prompt has no skills markers, so auto-clearing it would repeat every run.
                    unverifiable.append({
                        **entry,
                        "reason": "memory-only tools[] pin may be a user toolset; clear explicitly by SESSION_ID",
                    })

    apply = bool(getattr(args, "apply", False))
    as_json = bool(getattr(args, "json", False))

    def _payload(cleared):
        return {
            "findings": findings,
            "unverifiable": unverifiable,
            "apply": apply,
            "cleared": cleared,
        }

    if not findings:
        if as_json:
            print(json.dumps(_payload([]), indent=2))
        elif target:
            from agent.i18n import t

            print(t("sessions.prompt_already_clear"))
        else:
            from agent.i18n import t

            print(t("sessions.no_degraded_prompts"))
            if unverifiable:
                print(t("sessions.unverifiable_left", count=len(unverifiable)))
        return 0

    if not as_json:
        for finding in findings:
            print(f"  {finding['id']}  ({finding['prompt_chars']} chars) - {finding['reason']}")
        if unverifiable:
            from agent.i18n import t

            print(t("sessions.unverifiable_skipped", count=len(unverifiable)))

    if not apply:
        if as_json:
            print(json.dumps(_payload([]), indent=2))
        else:
            from agent.i18n import t

            print(t("sessions.prompts_repairable", count=len(findings)))
        return 0

    # JSON mode is the non-interactive automation surface; --apply is the explicit mutation opt-in.
    if not as_json and not _confirm_prompt(t("sessions.prompts_clear_confirm", count=len(findings))):
        from agent.i18n import t

        print(t("sessions.aborted"))
        return 0

    cleared = []
    for finding in findings:
        db.update_system_prompt(finding["id"], None)
        cleared.append(finding["id"])

    if as_json:
        print(json.dumps(_payload(cleared), indent=2))
    else:
        print(t("sessions.prompts_cleared", count=len(cleared)))
        from agent.i18n import t

        print(t("sessions.repaired_warning_expected"))
    return 0


def _cmd_stats(db, args):
    from agent.i18n import t

    print(t("sessions.totals", sessions=db.session_count(), messages=db.message_count()))
    for src in ("cli", "telegram", "discord", "whatsapp", "slack"):
        if (c := db.session_count(source=src)) > 0:
            print(t("sessions.stats_source", src=src, count=c))
    if db.db_path.exists():
        print(t("sessions.db_size", size=f"{_size_mb(db.db_path):.1f}"))


# -- dispatch -----------------------------------------------------------------

def _cmd_repair_profiles(args):
    from hermes_cli.sessions_cmd_repair_profiles import cmd_repair_profiles
    return cmd_repair_profiles(args)


def _cmd_set_journal_mode(args):
    from hermes_cli.sessions_cmd_journal_mode import cmd_set_journal_mode
    return cmd_set_journal_mode(args)


def _cmd_discard(args):
    from hermes_cli.sessions_discard import cmd_discard
    return cmd_discard(args)


_PRE_DB_HANDLERS = {
    "repair": _cmd_repair, "recover": _cmd_recover, "import": _cmd_import,
    "repair-profiles": _cmd_repair_profiles,  # opens every profile's store itself
    "set-journal-mode": _cmd_set_journal_mode,  # offline: must not open the store it converts
    "discard": _cmd_discard,  # a gateway control (prompt.resolve_unknown), never a direct store write
}
_OBSERVATIONAL_DB_ACTIONS = frozenset({"list", "stats", "pinned"})
_DB_HANDLERS = {
    "list": _cmd_list, "export": _cmd_export, "delete": _cmd_delete, "rename": _cmd_rename, "pinned": _cmd_pinned,
    "prune": partial(_cmd_prune_or_archive, action="prune"), "pin": partial(_cmd_pin, pinning=True),
    "archive": partial(_cmd_prune_or_archive, action="archive"), "unpin": partial(_cmd_pin, pinning=False),
    "retitle-skills": _cmd_retitle_skills, "browse": _cmd_browse, "optimize": _cmd_optimize,
    "clean-markers": _cmd_clean_markers, "optimize-storage": _cmd_optimize_storage,
    "repair-routing": _cmd_repair_routing, "repair-prompts": _cmd_repair_prompts, "stats": _cmd_stats,
}


def _print_empty_store(action: str, args) -> None:
    """A profile that never created state.db: report empty instead of opening a writer that creates it."""
    if action == "stats":
        from agent.i18n import t

        print(t("sessions.totals", sessions=0, messages=0))
    elif action == "pinned":
        print("[]" if getattr(args, "json", False) else t("sessions.no_pinned"))
    else:
        from agent.i18n import t

        print(t("sessions.no_sessions"))


# VACUUM, the FTS-layout rebuild and bulk deletes rewrite the store; underneath a live gateway/Desktop/cron
# writer that is the second-writer class behind the retired-WAL refusal (#110054). `--force` is the override.
_HELD_STORE_ACTIONS = frozenset({"optimize", "optimize-storage", "prune"})


def cmd_sessions(args, sessions_parser=None):
    action = args.sessions_action
    pre = _PRE_DB_HANDLERS.get(action)
    if pre is not None:
        return pre(args)
    from hermes_state import SessionDB
    from hermes_constants import get_hermes_home
    # Verified deletion is an explicit mutation, not a read-only export.
    deleting_export = (
        action == "export" and getattr(args, "delete_after_verified", False)
        and getattr(args, "yes", False) and getattr(args, "session_id", None)
        and getattr(args, "format", None) in ("md", "qmd")
    )
    observational = action in _OBSERVATIONAL_DB_ACTIONS or (action == "export" and not deleting_export)
    if action == "prune":
        # The always-on gateway owns the store: this process only reads the preview, the owner
        # deletes. No gateway: the local prune below, behind the holder scan, as before.
        from hermes_cli.sessions_owner import live_owner
        args.owner_endpoint = live_owner()
        observational = args.owner_endpoint is not None
    # A served-profile process has no single default home: pass the store path explicitly.
    path = get_hermes_home() / "state.db"
    try:
        db = SessionDB(db_path=path, read_only=observational)
    except Exception as e:
        # mode=ro cannot create the store; a reader on a fresh profile reports empty rather than failing.
        if observational and not path.exists():
            return _print_empty_store(action, args)
        from agent.i18n import t

        print(t("sessions.cannot_open_db"))
        print(t("sessions.cannot_open_db_run"))
        print(t("sessions.usage_error", message=e))
        return 1
    try:
        handler = _DB_HANDLERS.get(action)
        if handler is None:
            sessions_parser.print_help()
            return
        if (action in _HELD_STORE_ACTIONS and not getattr(args, "dry_run", False) and not getattr(args, "force", False)
                and getattr(args, "owner_endpoint", None) is None):
            from hermes_state_holders import held_store_refusal
            # Same path the SessionDB above opened, so the scan never depends on the db object.
            refusal = held_store_refusal(path, command=action)
            if refusal:
                print(refusal)
                return 1
        try:
            return handler(db, args)
        except sqlite3.OperationalError as e:
            from hermes_state_repair import _schema_not_built

            if not observational or not _schema_not_built(e):
                raise
            # A read-only opener skips schema migration, so a store from an older release can lack a column.
            from agent.i18n import t

            print(t("sessions.db_needs_migration", error=e))
            return 1
    finally:
        db.close()

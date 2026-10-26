"""hermes hooks — inspect and manage shell-script hooks."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List


def hooks_command(args) -> None:
    """Entry point for ``hermes hooks`` — dispatches to the requested action."""
    from agent.i18n import t

    sub = getattr(args, "hooks_action", None)
    if not sub:
        print(t("hooks.usage"))
        print(t("hooks.usage_help"))
        return
    handler = _ACTIONS.get(sub)
    if handler is None:
        print(t("hooks.unknown_sub", sub=sub))
        return
    handler(args)


# ---------------------------------------------------------------------------
# list
# ---------------------------------------------------------------------------

def _cmd_list(_args) -> None:
    from hermes_cli.config import load_config
    from agent import outbound_webhooks, shell_hooks

    cfg = load_config()
    specs = shell_hooks.iter_configured_hooks(cfg)
    outbound = outbound_webhooks.iter_configured_targets(cfg)

    if not specs and not outbound:
        from agent.i18n import t

        print(t("hooks.list_none"))
        print(t("hooks.list_none_help"))
        print("    website/docs/user-guide/features/hooks.md")
        print(t("hooks.list_none_examples"))
        return

    if not specs:
        from agent.i18n import t

        print(t("hooks.list_no_shell"))
    else:
        from agent.i18n import t

        by_event: dict[str, list] = {}
        for spec in specs:
            by_event.setdefault(spec.event, []).append(spec)
        approved = shell_hooks.allowlisted_pairs()
        print(t("hooks.list_shell_header", count=len(specs)))
        for event in sorted(by_event):
            print(f"  [{event}]")
            for spec in by_event[event]:
                is_approved = (spec.event, spec.command) in approved
                status = t("hooks.status_allowed") if is_approved else t("hooks.status_not_allowlisted")
                print(f"    - {spec.command}{_matcher_part(spec)} (timeout={spec.timeout}s, {status})")
                entry = shell_hooks.allowlist_entry_for(spec.event, spec.command) if is_approved else None
                if entry and entry.get("approved_at"):
                    print(f"      approved_at: {entry['approved_at']}")
                    drift, mtime_at, mtime_now = _mtime_drift(shell_hooks, spec, entry)
                    if drift is True:
                        print(t("hooks.drift_warning", was=mtime_at, now=mtime_now))
            print()

    if outbound:
        from agent.i18n import t

        print(t("hooks.list_webhooks_header", count=len(outbound)))
        for target in outbound:
            signed = t("hooks.signed") if target.secret else t("hooks.unsigned")
            print(f"  - {target.label}")
            print(f"      url:     {target.url}")
            print(f"      events:  {', '.join(target.events)}{_matcher_part(target)} (timeout={target.timeout}s, {signed})")
        print()


def _matcher_part(obj) -> str:
    return f" matcher={obj.matcher!r}" if obj.matcher else ""


def _mtime_drift(shell_hooks, spec, entry) -> tuple[bool | None, str, str]:
    """``(drift, mtime_at, mtime_now)``: True if the script changed since approval, False if
    unchanged, None when either mtime is unknown."""
    mtime_now = shell_hooks.script_mtime_iso(spec.command)
    mtime_at = entry.get("script_mtime_at_approval")
    if not (mtime_now and mtime_at):
        return None, mtime_at, mtime_now
    if mtime_now > mtime_at:
        return True, mtime_at, mtime_now
    return (False if mtime_now == mtime_at else None), mtime_at, mtime_now


# ---------------------------------------------------------------------------
# test
# ---------------------------------------------------------------------------

# Synthetic kwargs matching the real invoke_hook() call sites. They go verbatim to
# agent.shell_hooks.run_once() -> the same _serialize_payload() production uses, so the
# stdin a script sees under `hooks test` / `hooks doctor` has the runtime shape.
_DEFAULT_PAYLOADS = {
    "pre_tool_call": {
        "tool_name": "terminal", "args": {"command": "echo hello"},
        "session_id": "test-session", "task_id": "test-task", "tool_call_id": "test-call",
    },
    "post_tool_call": {
        "tool_name": "terminal", "args": {"command": "echo hello"},
        "session_id": "test-session", "task_id": "test-task", "tool_call_id": "test-call",
        "result": '{"output": "hello"}', "duration_ms": 42,
    },
    "pre_llm_call": {
        "session_id": "test-session", "user_message": "What is the weather?",
        "conversation_history": [], "is_first_turn": True, "model": "gpt-4", "platform": "cli",
    },
    "post_llm_call": {"session_id": "test-session", "model": "gpt-4", "platform": "cli"},
    "pre_verify": {
        "session_id": "test-session", "platform": "cli", "model": "gpt-4", "coding": True,
        "attempt": 0, "final_response": "All done — the change is applied.",
        "changed_paths": ["src/app.tsx"],
    },
    "on_session_start": {"session_id": "test-session"},
    "on_session_end": {
        "session_id": "test-session", "task_id": "test-task", "turn_id": "test-turn",
        "completed": True, "failed": False, "interrupted": False,
        "turn_exit_reason": "text_response(stop)", "model": "gpt-4", "platform": "cli",
    },
    "on_session_finalize": {"session_id": "test-session"},
    "on_session_reset": {"session_id": "test-session"},
    "on_session_delete": {"session_id": "test-session", "reason": "delete", "profile": "default"},
    "pre_api_request": {
        "session_id": "test-session", "task_id": "test-task", "platform": "cli",
        "model": "claude-sonnet-4-6", "provider": "anthropic",
        "base_url": "https://api.anthropic.com", "api_mode": "anthropic_messages",
        "api_call_count": 1, "message_count": 4, "tool_count": 12,
        "approx_input_tokens": 2048, "request_char_count": 8192, "max_tokens": 4096,
    },
    "post_api_request": {
        "session_id": "test-session", "task_id": "test-task", "platform": "cli",
        "model": "claude-sonnet-4-6", "provider": "anthropic",
        "base_url": "https://api.anthropic.com", "api_mode": "anthropic_messages",
        "api_call_count": 1, "api_duration": 1.234,
        "started_at": 1756000000.0, "ended_at": 1756000001.234, "first_chunk_at": 1756000000.512,
        "finish_reason": "stop", "message_count": 4, "response_model": "claude-sonnet-4-6",
        "usage": {"input_tokens": 2048, "output_tokens": 512}, "context_length": 200000,
        "assistant_content_chars": 1200, "assistant_tool_call_count": 0,
        # Per-advisor metrics on a MoA turn, None otherwise: MoA returns only the aggregator's
        # response, so without this an observer cannot see or price the fan-out.
        "moa_references": None,
    },
    "pre_auxiliary_call": {
        "aux_task": "title_generation", "session_id": "test-session", "task_id": "test-task",
        "turn_id": "test-turn", "api_request_id": "aux-0123abcd", "platform": "cli",
        "model": "claude-haiku-4-5", "provider": "anthropic",
        "base_url": "https://api.anthropic.com", "api_mode": "anthropic_messages",
        "api_call_count": 1, "retry_count": 0, "streaming": False, "message_count": 2,
        "tool_count": 0, "approx_input_tokens": 256, "request_char_count": 1024, "max_tokens": 64,
    },
    "post_auxiliary_call": {
        "aux_task": "title_generation", "session_id": "test-session", "task_id": "test-task",
        "turn_id": "test-turn", "api_request_id": "aux-0123abcd", "platform": "cli",
        "model": "claude-haiku-4-5", "provider": "anthropic",
        "base_url": "https://api.anthropic.com", "api_mode": "anthropic_messages",
        "api_call_count": 1, "retry_count": 0, "streaming": False, "api_duration": 0.42,
        "started_at": 1756000000.0, "ended_at": 1756000000.42, "finish_reason": "stop",
        "response_model": "claude-haiku-4-5", "usage": {"input_tokens": 256, "output_tokens": 12},
        "assistant_content_chars": 40, "assistant_tool_call_count": 0, "error": None, "error_type": None,
    },
    "subagent_stop": {
        "parent_session_id": "parent-sess", "child_role": None,
        "child_summary": "Synthetic summary for hooks test", "child_status": "completed",
        "tool_call_history": [{
            "tool_name": "write_file",
            "tool_input": {"argument_keys": ["content", "path"], "targets": {"path": "notes/report.txt"}},
            "input_bytes": 128, "output_bytes": 32, "status": "ok",
        }],
        "duration_ms": 1234,
    },
}


def _cmd_test(args) -> None:
    from hermes_cli.config import load_config
    from hermes_cli.plugins import VALID_HOOKS
    from agent import shell_hooks

    event = args.event
    if event not in VALID_HOOKS:
        from agent.i18n import t

        print(t("hooks.unknown_event", event=repr(event)))
        print(t("hooks.valid_events", events=', '.join(sorted(VALID_HOOKS))))
        return

    # Synthetic kwargs merged with --for-tool (overrides tool_name) and --payload-file (extra kwargs).
    payload = dict(_DEFAULT_PAYLOADS.get(event, {"session_id": "test-session"}))
    for_tool = getattr(args, "for_tool", None)
    if for_tool:
        payload["tool_name"] = for_tool
    if getattr(args, "payload_file", None):
        try:
            custom = json.loads(Path(args.payload_file).read_text(encoding="utf-8-sig"))
            if isinstance(custom, dict):
                payload.update(custom)
            else:
                from agent.i18n import t

                print(t("hooks.payload_not_json", path=args.payload_file))
        except Exception as exc:
            from agent.i18n import t

            print(t("hooks.payload_read_failed", error=exc))
            return

    specs = [s for s in shell_hooks.iter_configured_hooks(load_config()) if s.event == event]
    if for_tool:
        specs = [s for s in specs if s.event not in {"pre_tool_call", "post_tool_call"} or s.matches_tool(for_tool)]
    if not specs:
        from agent.i18n import t

        print(t("hooks.no_hooks_for_event", event=event))
        if for_tool:
            print(t("hooks.matcher_filter", for_tool=for_tool))
        return

    from agent.i18n import t

    print(t("hooks.firing_header", count=len(specs), event=event))
    for spec in specs:
        print(f"  → {spec.command}")
        _print_run_result(shell_hooks.run_once(spec, payload))
        print()


def _print_run_result(result: dict[str, Any]) -> None:
    from agent.i18n import t

    if result.get("error"):
        print(t("hooks.run_error", error=result['error']))
    elif result.get("timed_out"):
        print(t("hooks.run_timed_out", elapsed=result['elapsed_seconds']))
    else:
        print(f"      exit={result.get('returncode')}  elapsed={result.get('elapsed_seconds', 0)}s")
        for stream in ("stdout", "stderr"):
            text = (result.get(stream) or "").strip()
            if text:
                print(f"      {stream}: {_truncate(text, 400)}")
    # run_once always sets ``parsed`` (agent/shell_hooks.py::_evaluate_result), so it is available even
    # when the hook errored or timed out. A failing hook's decision is the one thing `hooks test` exists
    # to show — failed-open and failed-closed must not render identically (#115968).
    parsed = result.get("parsed")
    if parsed:
        print(f"      {t('hooks.parsed_shape')} {json.dumps(parsed)}")
    else:
        print(t("hooks.parsed_none"))


def _truncate(s: str, n: int) -> str:
    return s if len(s) <= n else s[: n - 3] + "..."


# ---------------------------------------------------------------------------
# revoke / doctor
# ---------------------------------------------------------------------------

def _cmd_revoke(args) -> None:
    from agent.i18n import t
    from agent import shell_hooks

    removed = shell_hooks.revoke(args.command)
    if removed == 0:
        print(t("hooks.revoke_not_found", command=args.command))
        return
    print(t("hooks.revoke_removed", count=removed, command=args.command))
    print(t("hooks.revoke_note"))


def _cmd_doctor(_args) -> None:
    from agent.i18n import t
    from hermes_cli.config import load_config
    from agent import shell_hooks

    specs = shell_hooks.iter_configured_hooks(load_config())
    if not specs:
        print(t("hooks.doctor_none"))
        return
    print(t("hooks.doctor_header", count=len(specs)))
    problems = 0
    for spec in specs:
        print(f"  [{spec.event}] {spec.command}")
        problems += _doctor_one(spec, shell_hooks)
        print()
    print(t("hooks.doctor_problems", count=problems) if problems else t("hooks.doctor_healthy"))


def _doctor_one(spec, shell_hooks) -> int:
    from agent.i18n import t

    problems = 0
    # 1. Script exists and is executable
    if shell_hooks.script_is_executable(spec.command):
        print(t("hooks.doctor_executable"))
    else:
        problems += 1
        print(t("hooks.doctor_not_executable"))
    # 2. Allowlist status
    entry = shell_hooks.allowlist_entry_for(spec.event, spec.command)
    if entry:
        print(t("hooks.doctor_allowlisted", approved=entry.get('approved_at', '?')))
    else:
        problems += 1
        print(t("hooks.doctor_not_allowlisted"))
    # 3. Mtime drift
    if entry and entry.get("script_mtime_at_approval"):
        drift, mtime_at, mtime_now = _mtime_drift(shell_hooks, spec, entry)
        if drift is True:
            problems += 1
            print(t("hooks.doctor_drift", was=mtime_at, now=mtime_now))
        elif drift is False:
            print(t("hooks.doctor_unchanged"))
    # 4. JSON smoke test on a synthetic payload — ONLY when already allowlisted. Otherwise doctor
    # would execute every script in a freshly-pulled config before the user reviewed it, which
    # contradicts the documented workflow ("spot newly-added hooks *before they register*").
    if not entry:
        print(t("hooks.doctor_skip_smoke"))
    elif shell_hooks.script_is_executable(spec.command):
        result = shell_hooks.run_once(spec, _DEFAULT_PAYLOADS.get(spec.event, {"extra": {}}))
        if result.get("timed_out"):
            problems += 1
            print(t("hooks.doctor_timed_out", elapsed=result['elapsed_seconds'], timeout=spec.timeout))
        elif result.get("error"):
            problems += 1
            print(t("hooks.doctor_execution_error", error=result['error']))
        else:
            rc = result.get("returncode")
            elapsed = result.get("elapsed_seconds", 0)
            stdout = (result.get("stdout") or "").strip()
            if not stdout:
                print(t("hooks.doctor_clean_stdout", rc=rc, elapsed=elapsed))
            else:
                try:
                    json.loads(stdout)
                    print(t("hooks.doctor_valid_json", rc=rc, elapsed=elapsed))
                except json.JSONDecodeError:
                    problems += 1
                    print(t("hooks.doctor_invalid_json", rc=rc, elapsed=elapsed, stdout=_truncate(stdout, 120)))
    return problems


_ACTIONS = {
    "list": _cmd_list, "ls": _cmd_list,
    "test": _cmd_test,
    "revoke": _cmd_revoke, "remove": _cmd_revoke, "rm": _cmd_revoke,
    "doctor": _cmd_doctor,
}

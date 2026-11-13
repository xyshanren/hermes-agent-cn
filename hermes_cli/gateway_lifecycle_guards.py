"""Refusals that keep ``hermes gateway`` lifecycle verbs off gateways they must not take down.

Two rules, one per failure that took a production gateway down:

* **Foreign service definition.** A systemd unit / launchd plist pins the ``HERMES_HOME`` its gateway
  runs on. A lifecycle verb (start/stop/restart/uninstall) on a definition pinning ANOTHER home acts on
  another install's gateway: a ``HOME=<scratch>`` probe resolved the bare ``hermes-gateway`` name and ran
  ``systemctl --user stop`` on the account's real unit. Install/refresh already refused to WRITE such a
  definition (``gateway_service_owner``); the same module now refuses to OPERATE one:
  ``refuse_foreign_systemd_unit`` (salvaged from #141908, checked before any home sync) and
  ``refuse_foreign_launchd_plist``.
* **Live sessions.** ``gateway stop``/``restart`` name the turns, cron jobs or background delegations the
  gateway is running and ask y/N before interrupting them; ``-y``/``--yes`` (alias ``--interrupt``)
  skips the question, and with no terminal to ask on they refuse. The in-band restart
  drains turns, but its stop still interrupts every async delegation (``interrupt_all``), and a stop
  ends the sessions outright.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Optional

INTERRUPT_FLAG = "--yes"


def _live_work_from_state(home: Path) -> Optional[dict[str, Any]]:
    """``active_agents`` from a fresh ``gateway_state.json`` whose writer is alive (older gateways)."""
    from gateway.status import parse_active_agents, read_runtime_status, runtime_status_is_stale, runtime_status_pid_is_live

    record = read_runtime_status(home / "gateway_state.json")
    if not record or runtime_status_is_stale(record) or not runtime_status_pid_is_live(record):
        return None
    work = record.get("active_work")
    return {"active_agents": parse_active_agents(record.get("active_agents")),
            "active_work": work if isinstance(work, list) else []}


def live_work(home: Path, profile: Optional[str] = None) -> Optional[dict[str, Any]]:
    """What the gateway serving ``home`` is running now: ``{"active_agents", "active_work"}``, or None
    when no gateway answers. The control socket answers live; the state file covers older gateways.
    ``profile`` narrows the answer to one served profile's work (the state file cannot, so it is skipped)."""
    from gateway.control_socket import query_gateway_control

    answer = query_gateway_control(home, "active-work", params={"profile": profile} if profile else None)
    if isinstance(answer, dict) and isinstance(answer.get("active_work"), list):
        return answer
    return None if profile else _live_work_from_state(home)


def _candidate_homes(system: bool = False) -> list[Path]:
    """Homes whose gateway a stop/restart from here takes down, in order: the system unit's pinned home
    (``sudo`` strips HERMES_HOME, so this process sees root's), this home's own gateway (a ``--force``
    standalone one included), then the live host owner that serves it. Only READS the unit: a foreign
    unit is skipped here and refused by the systemd verb before it adopts any home."""
    from hermes_cli import gateway as gw, gateway_service_owner

    homes = [gw.get_hermes_home()]
    if (gw.supports_systemd_services() and gw._select_systemd_scope(system)
            and gateway_service_owner.foreign_systemd_unit_home(True) is None
            and (unit_home := gateway_service_owner.service_home_for_unit(gw.get_systemd_unit_path(system=True), True))
            not in homes):
        homes.insert(0, unit_home)
    owner = gw._host_multiplexer_for_all_verb()
    if owner is not None and Path(owner.home) not in homes:
        homes.append(Path(owner.home))
    return homes


def refusal_lines(verb: str, homes: list[Path], *, flag_hint: str = f"hermes gateway {{verb}} {INTERRUPT_FLAG}",
                  profile: Optional[str] = None) -> list[str]:
    """Refusal text for ``verb`` while the first answering gateway among ``homes`` has live work, else []."""
    for home in homes:
        work = live_work(home, profile)
        if work is not None:
            return work_lines(verb, home, work, flag_hint)[1]
    return []


def _verb_labels(verb: str) -> dict[str, str]:
    """Translated verb forms for the headers ({verb} present/progressive, {verb_past} in the
    cancelled line); the flag-hint command line keeps the raw verb for copy-paste."""
    from agent.i18n import t

    return {"verb": t(f"gateway.admin.verb_{verb}"), "verb_past": t(f"gateway.admin.verb_past_{verb}")}


def work_lines(verb: str, home: Path, work: dict[str, Any], flag_hint: str) -> tuple[int, list[str]]:
    """``(count, lines)`` for one gateway's live work; ``count`` 0 means nothing live. The count
    travels separately so the caller can re-render the header for the ``--yes`` and ask variants
    (a translated header is text, so the old prefix-``replace`` trick cannot serve)."""
    from hermes_cli.update_cmd_drain_report import describe_active_work_unit
    from agent.i18n import t

    units = [u for u in work.get("active_work") or [] if isinstance(u, dict)]
    count = max(len(units), int(work.get("active_agents") or 0))
    if not count:
        return 0, []
    labels = _verb_labels(verb)
    lines = [t("gateway.admin.live_refuse_header", count=count, **labels)]
    lines += [f"  • {describe_active_work_unit(u, home)}" for u in units]
    if not units:
        lines.append(t("gateway.admin.live_unnamed_agents", count=count))
    lines += [t("gateway.admin.live_let_finish"),
              f"    {flag_hint.format(verb=verb)}   {t('gateway.admin.live_interrupts_comment', count=count)}"]
    return count, lines


def refuse_while_sessions_live(verb: str, args, *, host_home: Optional[Path] = None, profile: Optional[str] = None) -> None:
    """Exit 1 naming the live work unless ``--interrupt`` was passed; with it, say what is interrupted.
    ``host_home``/``profile``: a served profile's stop/restart unserves only that profile in the host,
    so only its work counts."""
    if profile:
        hint = f"hermes -p {profile} gateway {{verb}} {INTERRUPT_FLAG}"
        # No answer (control socket down) proceeds: the park marker path exists for exactly that host.
        count, lines = next(((work_lines(verb, Path(home), work, hint))
                             for home in [Path(host_home)]
                             if (work := live_work(home, profile)) is not None), (0, []))
    else:
        count, lines = next(((work_lines(verb, home, work, f"hermes gateway {{verb}} {INTERRUPT_FLAG}"))
                             for home in _candidate_homes(getattr(args, "system", False))
                             if (work := live_work(home)) is not None), (0, []))
    if not count:
        return
    from agent.i18n import t
    from hermes_cli.gateway import print_error, print_warning

    labels = _verb_labels(verb)
    if getattr(args, "interrupt", False):
        print_warning(t("gateway.admin.live_yes_header", count=count, **labels))
        for line in lines[1:-2]:
            print(line)
        return
    if sys.stdin.isatty() and sys.stdout.isatty():
        from hermes_cli.cli_output import prompt_yes_no

        print_warning(t("gateway.admin.live_ask_header", count=count, **labels))
        for line in lines[1:-2]:
            print(line)
        if prompt_yes_no(t("gateway.admin.live_interrupt_prompt", **labels), default=False):
            return
        print(t("gateway.admin.live_interrupt_cancelled", **labels))
        sys.exit(1)
    print_error(lines[0])
    for line in lines[1:]:
        print(line)
    sys.exit(1)

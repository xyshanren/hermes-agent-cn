"""Registry-owned slash command execution (thin slice).

Invariant: an executor's output depends only on ``ctx.args`` / ``ctx.options`` — never on
``ctx.surface`` — so the core text is identical across surfaces for a fixed context (enforced by
tests/hermes_cli/test_commands_execute.py).
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from typing import Any

from agent.i18n import t

__all__ = [
    "EXECUTORS",
    "CommandContext",
    "CommandReply",
    "execute_command",
    "resolve_executor",
    "run_execute",
]


@dataclass(frozen=True)
class CommandContext:
    """Surface-provided inputs for a shared command executor."""
    surface: str = "cli"                # "cli" | "gateway" | "tui" — decoration only
    args: str = ""                      # raw argument string after the command word
    options: Mapping[str, Any] = field(default_factory=dict)  # surface params (page_size, ...)
    config_get: Callable[[str, Any], Any] | None = None       # optional config accessor


@dataclass(frozen=True)
class CommandReply:
    """Canonical result of a shared executor: surface-independent ``text`` plus the structured
    ``data`` it derived so a surface can re-render with its own decoration."""
    text: str
    data: Mapping[str, Any] = field(default_factory=dict)
    format: str = "plain"               # "plain" | "markdown" (hint, not a contract)


# Executors — pure formatters, no agent/session mutation.
def _exec_version(ctx: CommandContext) -> CommandReply:
    """Core /version text — the banner version label."""
    from hermes_cli.banner import format_banner_version_label
    return CommandReply(format_banner_version_label())


def _exec_egress(ctx: CommandContext) -> CommandReply:
    """Core /egress text — Docker egress proxy status."""
    from hermes_cli.proxy_cli import format_status_text
    return CommandReply(format_status_text())


def _exec_profile(ctx: CommandContext) -> CommandReply:
    """Core /profile data — active profile name + home directory.

    A multiplexed gateway may pre-resolve the per-source profile/home via ``options``
    (``profile_name`` / ``home_display``); otherwise process-level values are used.
    """
    from hermes_cli.profiles import get_active_profile_name
    from hermes_constants import display_hermes_home
    profile_name = str(ctx.options.get("profile_name") or "").strip() or get_active_profile_name()
    home_display = str(ctx.options.get("home_display") or "").strip() or display_hermes_home()
    # Presentation-only display name (profile.yaml); `data.profile` stays the canonical id.
    label = profile_name
    try:
        from hermes_cli.profiles import format_profile_label, get_profile_dir, read_profile_meta
        display = read_profile_meta(get_profile_dir(profile_name)).get("display_name", "")
        label = format_profile_label(profile_name, display)
    except Exception:
        pass
    return CommandReply(t("gateway.profile.plain", profile=label, home=home_display),
                        data={"profile": profile_name, "home": home_display})


def _exec_autoprune(ctx: CommandContext) -> CommandReply:
    """Core /autoprune text — record the auto-prune decision or show its state."""
    from hermes_cli.prune_advisor import run_command
    return CommandReply(run_command(ctx.args))


def _exec_bundles(ctx: CommandContext) -> CommandReply:
    """Core /bundles data — installed skill bundles listing."""
    try:
        from agent.skill_bundles import _bundles_dir, list_bundles
    except Exception as exc:  # pragma: no cover - env-specific
        return CommandReply(t("gateway.bundles.unavailable", error=exc), data={"error": str(exc)})
    bundles = list_bundles()
    bundles_dir = str(_bundles_dir())
    if not bundles:
        return CommandReply(t("gateway.bundles.none_plain", dir=bundles_dir), data={"bundles": [], "dir": bundles_dir})
    lines = [t("gateway.bundles.header_plain", count=len(bundles))]
    for info in bundles:
        skills = info.get("skills", [])
        desc = info.get("description") or t("gateway.bundles.default_desc", count=len(skills))
        lines.append(t("gateway.bundles.item_plain", slug=info["slug"], desc=desc, count=len(skills)))
        lines.extend(f"    · {s}" for s in skills)
    lines.append(t("gateway.bundles.invoke_hint_plain"))
    return CommandReply("\n".join(lines), data={"bundles": bundles, "dir": bundles_dir})


def _skill_commands() -> dict:
    """Registered skill commands, or ``{}`` when the skill subsystem is unavailable."""
    try:
        from agent.skill_commands import get_skill_commands
        return get_skill_commands() or {}
    except Exception:
        return {}


def _exec_help(ctx: CommandContext) -> CommandReply:
    """Core gateway /help body (pre platform mention decoration)."""
    from hermes_cli.commands import gateway_help_lines
    # ``allowed_commands`` (gateway, non-admin caller): only the commands the slash-access
    # policy lets this user run; skill commands are hidden too since the gate refuses them.
    allowed = ctx.options.get("allowed_commands")
    lines = [t("gateway.help.header"), *gateway_help_lines(allowed)]
    skill_cmds = _skill_commands() if allowed is None else {}
    try:
        if skill_cmds:
            lines.append(t("gateway.help.skill_header", count=len(skill_cmds)))
            sorted_cmds = sorted(skill_cmds)  # first 10, then point to /commands for the rest
            lines.extend(f"`{cmd}` — {skill_cmds[cmd]['description']}"
                         for cmd in sorted_cmds[:10])
            if len(sorted_cmds) > 10:
                lines.append(t("gateway.help.more_use_commands", count=len(sorted_cmds) - 10))
    except Exception:
        pass
    return CommandReply("\n".join(lines), format="markdown")


def _exec_commands(ctx: CommandContext) -> CommandReply:
    """Core gateway /commands body — paginated command + skill listing.

    ``ctx.options["page_size"]`` is a surface parameter (Telegram uses 15, everything else 20).
    """
    from hermes_cli.commands import gateway_help_lines
    try:
        requested_page = int((ctx.args or "").strip() or 1)
    except ValueError:
        return CommandReply(t("gateway.commands.usage"), format="markdown")

    allowed = ctx.options.get("allowed_commands")
    entries = list(gateway_help_lines(allowed))
    skill_cmds = _skill_commands() if allowed is None else {}
    try:
        if skill_cmds:
            entries.extend(["", t("gateway.commands.skill_header")])
            for cmd in sorted(skill_cmds):
                desc = skill_cmds[cmd].get("description", "").strip() or t("gateway.commands.default_desc")
                entries.append(f"`{cmd}` — {desc}")
        # Skills kept off the menu because a built-in owns the name (agent.skill_commands guard).
        from agent.skill_commands import skill_command_collision_note
        from tools.skills_tool import find_all_skills
        entries.extend(f"⚠ {note}" for note in filter(None, map(
            skill_command_collision_note, sorted(s["name"] for s in find_all_skills()))))
    except Exception:
        pass

    if not entries:
        return CommandReply(t("gateway.commands.none"), format="markdown")

    try:
        page_size = max(1, int(ctx.options.get("page_size", 20)))
    except (TypeError, ValueError):
        page_size = 20
    total_pages = max(1, (len(entries) + page_size - 1) // page_size)
    page = max(1, min(requested_page, total_pages))
    start = (page - 1) * page_size
    lines = [t("gateway.commands.header", total=len(entries), page=page, total_pages=total_pages),
             "", *entries[start:start + page_size]]
    if total_pages > 1:
        nav_parts = ([t("gateway.commands.nav_prev", page=page - 1)] if page > 1 else []) + (
            [t("gateway.commands.nav_next", page=page + 1)] if page < total_pages else [])
        lines.extend(["", " | ".join(nav_parts)])
    if page != requested_page:
        lines.append(t("gateway.commands.out_of_range", requested=requested_page, page=page))
    return CommandReply("\n".join(lines), format="markdown")


def _exec_context(ctx: CommandContext) -> CommandReply:
    """Core /context text — show context window usage (跟 c1750bb32 status bar 1:1 配对).

    跟 v0.20.0 status bar helper 1:1 配对, 跟 8-06 §1.4 "happy-path smoke test: /context 显 context 占用" 1:1 配对.
    v0.20.0 c1750bb32 加 /statusbar 切换 context bar, 但 0 暴露 format_status_text 公开 API,
    CN wrapper 用 redirect_stdout 拿 show_status() 输出.
    """
    import io
    import contextlib
    from hermes_cli.status import show_status

    buf = io.StringIO()
    try:
        with contextlib.redirect_stdout(buf):
            # show_status 接收 args namespace, 0 传默认
            show_status(None)
    except Exception as exc:  # pragma: no cover - env-specific
        return CommandReply(f"Context: <status unavailable: {exc}>")
    text = buf.getvalue().strip()
    if not text:
        return CommandReply("Context: <status empty>")
    return CommandReply(text, format="plain")


def _exec_diff(ctx: CommandContext) -> CommandReply:
    """Core /diff text — show last inline diff (跟 935137f0d 1:1 配对).

    v0.20.0 0 inline diff 命中 (跟 8-06 §1.3 0 命中 1:1 配对), CN stub 提示用户
    write_file / edit_file 时启用. 跟 8-06 §1.4 "happy-path smoke test: /diff 显 last inline diff" 1:1 配对.
    """
    return CommandReply(
        "Last inline diff: (no diff cached)\n"
        "Tip: write_file and edit_file generate inline diffs on next run.",
        data={"diff": None},
    )


def _exec_focus(ctx: CommandContext) -> CommandReply:
    """Core /focus text — show focus mode status (跟 4d6a133a9 1:1 配对).

    v0.20.0 已经有 focus mode (跟 4d6a133a9 1:1 配对), 但 0 set_mode 0 命中
    (跟 8-06 §1.3 0 命中 1:1 配对). CN stub 提示用户通过 config toggle
    (跟 K-10 CN 自加 config 接口 1:1 配对). 跟 8-06 §1.4 "/focus 切换 mode" 1:1 配对.
    """
    from agent.coding_context import resolve_runtime_mode

    try:
        current = resolve_runtime_mode()
        mode_name = current.profile.name if current else "auto"
    except Exception as exc:  # pragma: no cover - env-specific
        return CommandReply(f"Focus mode unavailable: {exc}")

    return CommandReply(
        f"Mode: {mode_name}\n"
        "Tip: set coding_context.focus=true in config to enable focus mode\n"
        "(collapses the toolset to the coding toolset under opt-in).",
        data={"current_mode": mode_name},
    )


# ---------------------------------------------------------------------------
# Registry + resolution
# ---------------------------------------------------------------------------
EXECUTORS: dict[str, Callable[[CommandContext], CommandReply]] = {
    "version": _exec_version,
    "egress": _exec_egress,
    "profile": _exec_profile,
    "bundles": _exec_bundles,
    "autoprune": _exec_autoprune,
    "gateway_help": _exec_help,
    "gateway_commands": _exec_commands,
    # K-7: 3 CN wrapper 跟 8-06 §1.4 1:1 配对, 跟 v0.20.0 file structure 1:1 配对
    "context": _exec_context,
    "diff": _exec_diff,
    "focus": _exec_focus,
}


def resolve_executor(cmd_def: Any) -> Callable[[CommandContext], CommandReply] | None:
    """Return the shared executor for ``cmd_def`` (or None when not migrated)."""
    return EXECUTORS.get(getattr(cmd_def, "execute", None) or "")


def run_execute(cmd_def: Any, ctx: CommandContext) -> CommandReply | None:
    """Run ``cmd_def``'s registry-owned executor, if any."""
    fn = resolve_executor(cmd_def)
    return None if fn is None else fn(ctx)


def execute_command(name: str, ctx: CommandContext) -> CommandReply:
    """Run the shared executor for ``name``; ``LookupError`` when unknown or not migrated."""
    from hermes_cli.commands import resolve_command
    cmd_def = resolve_command(name)
    reply = run_execute(cmd_def, ctx) if cmd_def is not None else None
    if reply is None:
        raise LookupError(f"no registry-owned executor for /{name}")
    return reply

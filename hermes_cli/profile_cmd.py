"""``hermes profile`` command — one handler per action, dispatched by ``PROFILE_ACTIONS``.

Imports from ``hermes_cli.profiles`` stay lazy (inside each handler) so tests can monkeypatch
the module attributes.
"""

from __future__ import annotations

from pathlib import Path
import os
import sys
from typing import NoReturn, Optional


def _die(msg: str, code: int = 1, *, err: bool = False) -> NoReturn:
    print(msg, file=sys.stderr if err else sys.stdout)
    sys.exit(code)


def _confirm(prompt: str) -> bool:
    """y/N prompt; EOF / Ctrl-C count as "no"."""
    try:
        answer = input(prompt).strip().lower()
    except (EOFError, KeyboardInterrupt):
        answer = ""
    return answer in {"y", "yes"}


def _is_active(p, active: str) -> bool:
    return p.name == active or (active == "default" and p.is_default)


def _env_file_has_key(env_path: Path, key: str) -> bool:
    """True when *key* is assigned in *env_path* (unreadable/mis-encoded file → False, never aborts)."""
    from agent.secret_scope import load_env_file

    return key in load_env_file(env_path)


def _render_distribution_plan(plan) -> None:
    """Print a human-readable summary of a pending distribution install."""
    from hermes_cli.profile_distribution import MANIFEST_FILENAME
    mf = plan.manifest
    from agent.i18n import t

    print(t("profile.dist_plan_header", name=mf.name, version=mf.version))
    if mf.description:
        print(f"  {mf.description}")
    if mf.author:
        print(t("profile.dist_plan_author", author=mf.author))
    if mf.hermes_requires:
        print(t("profile.dist_plan_requires", version=mf.hermes_requires))
    print(t("profile.dist_plan_source", source=plan.provenance))
    print(t("profile.dist_plan_target", target=plan.target_dir))
    if plan.existing:
        # Updating an existing distribution (dist-owned overwritten, config preserved, user
        # data untouched) vs overwriting a hand-built plain profile (same mechanics, but the
        # user didn't sign up for it).
        if (plan.target_dir / MANIFEST_FILENAME).is_file():
            print("  (profile exists — will overwrite distribution-owned files only)")
        else:
            print(
                "  ⚠ Profile exists but is NOT a distribution.  Installing here will\n"
                "    overwrite its SOUL.md and mcp.json and replace any skill or cron job\n"
                "    of the same name the distribution ships.\n"
                "    Your memories, sessions, auth.json, and .env will be preserved,\n"
                "    but any hand-edits to distribution-owned files will be lost."
            )
    if mf.env_requires:
        print("\n  Env vars:")
        for er in mf.env_requires:
            tag = "required" if er.required else "optional"
            # Shell environment OR the target profile's .env — don't nag about set keys.
            already = os.environ.get(er.name) is not None or (
                plan.target_dir.is_dir() and _env_file_has_key(plan.target_dir / ".env", er.name)
            )
            status = "✓ set" if already else ("needs setting" if er.required else "—")
            line = f"    • {er.name} ({tag}, {status})"
            if er.description:
                line += f" — {er.description}"
            print(line)
    if plan.has_cron:
        print(
            "\n  ⚠ This distribution ships cron jobs.  They will NOT run "
            "automatically — review and enable manually."
        )


def _profile_status(args):
    """Bare ``hermes profile`` — show current profile status."""
    from hermes_constants import display_hermes_home
    from hermes_cli.profiles import format_profile_label, get_active_profile_name, list_profiles
    profile_name = get_active_profile_name()
    dhh = display_hermes_home()
    current = next((p for p in list_profiles() if _is_active(p, profile_name)), None)
    label = format_profile_label(profile_name, current.display_name if current else "")
    from agent.i18n import t

    print(t("profile.status_active", label=label))
    print(t("profile.status_path", path=dhh))
    if current is not None:
        p = current
        if p.model:
            print(t("profile.status_model", model=p.model, provider=f" ({p.provider})" if p.provider else ""))
        print(t("profile.status_gateway", state='running' if p.gateway_running else 'stopped'))
        print(t("profile.status_skills", count=p.skill_count))
        if p.alias_path:
            print(t("profile.status_alias", alias=p.alias_name or p.name, name=p.name))
    print()


def _profile_list(args):
    from hermes_cli.profiles import format_profile_label, get_active_profile_name, list_profiles
    profiles = list_profiles()
    active = get_active_profile_name()
    if not profiles:
        from agent.i18n import t

        print(t("sessions.no_profiles_found"))
        return
    print(f"\n {'Profile':<16} {'Model':<28} {'Gateway':<12} {'Alias':<12} {'Distribution'}")
    print(f" {'─' * 15}    {'─' * 27}    {'─' * 11}    {'─' * 11}    {'─' * 20}")
    for p in profiles:
        marker = " ◆" if _is_active(p, active) else "  "
        name = format_profile_label(p.name, p.display_name)
        model = (p.model or "—")[:26]
        gw = "running" if p.gateway_running else "stopped"
        alias = (p.alias_name or p.name) if p.alias_path and not p.is_default else "—"
        dist = f"{p.distribution_name}@{p.distribution_version or '?'}"[:30] if p.distribution_name else "—"
        print(f"{marker}{name:<15} {model:<28} {gw:<12} {alias:<12} {dist}")
    print()
    for line in _shared_credential_warnings(profiles):
        print(line)


def _shared_credential_warnings(profiles) -> list:
    """One warning per named profile whose bot credential is byte-identical to the default's
    (typically an old ``--clone`` that copied .env): the collision that parks a multiplexed
    adapter or makes two standalone gateways fight over one bot."""
    from hermes_cli.profile_channels import shared_channel_credentials, shared_credential_warning
    default = next((p for p in profiles if p.is_default), None)
    if default is None:
        return []
    lines = []
    for p in profiles:
        if p.is_default:
            continue
        try:
            shared = shared_channel_credentials(p.path, default.path)
        except Exception:
            continue
        if shared:
            lines.append(shared_credential_warning(p.name, shared))
    return lines + ([""] if lines else [])


def _profile_use(args):
    from hermes_cli.profiles import set_active_profile
    name = args.profile_name
    try:
        set_active_profile(name)
        from agent.i18n import t

        print(t("profile.switched_default") if name == "default" else t("profile.switched", name=name))
    except (ValueError, FileNotFoundError) as e:
        _die(t("profile.error", error=e))


def _source_profile_dir(source_label: str) -> Path:
    from hermes_cli.profiles import get_profile_dir
    source_dir = get_profile_dir(source_label)
    if not source_dir.is_dir():
        raise FileNotFoundError(source_dir)
    return source_dir


def _print_channel_clone_notice(name: str, source_label: str, clone_channels: bool, clone_flag: str) -> None:
    from hermes_cli.profile_channels import (
        channel_platforms_configured, format_stripped_notice, shared_channel_credentials,
        shared_credential_warning,
    )
    from hermes_cli.profiles import get_profile_dir
    try:
        source_dir = _source_profile_dir(source_label)
    except FileNotFoundError:
        return
    if not clone_channels:
        for line in format_stripped_notice(name, channel_platforms_configured(source_dir), clone_flag):
            print(line)
        return
    shared = shared_channel_credentials(get_profile_dir(name), source_dir)
    if shared:
        print(shared_credential_warning(name, shared, source_label))


def _profile_create(args):
    from hermes_cli.profiles import (
        _get_wrapper_dir, _is_wrapper_dir_in_path, check_alias_collision, create_profile,
        create_wrapper_script, get_active_profile_name, seed_profile_skills,
    )
    name = args.profile_name
    clone = getattr(args, "clone", False)
    clone_all = getattr(args, "clone_all", False)
    no_alias = getattr(args, "no_alias", False)
    no_skills = getattr(args, "no_skills", False)
    clone_from = getattr(args, "clone_from", None)
    clone_channels = getattr(args, "clone_channels", False)
    sync_imports = getattr(args, "sync_imports", False)
    clone_config = clone or clone_from is not None
    cloned = clone_config or clone_all
    source_label = clone_from or get_active_profile_name()
    try:
        profile_dir = create_profile(
            name=name, clone_from=clone_from, clone_all=clone_all, clone_config=clone_config,
            no_alias=no_alias, no_skills=no_skills, description=getattr(args, "description", None),
            clone_channels=clone_channels, sync_imports=sync_imports,
        )
    except (ValueError, FileExistsError, FileNotFoundError) as e:
        _die(f"Error: {e}")
    print(f"\nProfile '{name}' created at {profile_dir}")
    if cloned:
        from agent.i18n import t

        if clone_all:
            print(t("profile.clone_all_done", source=source_label))
        else:
            print(t("profile.clone_config_done", source=source_label))
            from hermes_cli.profiles import cloned_plugin_names
            plugin_names = cloned_plugin_names(profile_dir)
            if plugin_names:
                print(t("profile.clone_plugins", names=', '.join(plugin_names)))
            from hermes_cli.profile_memory_config import cloned_memory_provider
            memory_provider = cloned_memory_provider(profile_dir)
            if memory_provider:
                print(t("profile.clone_memory_provider", provider=memory_provider))
        if sync_imports:
            print(t("profile.clone_imports", name=name))
        _print_channel_clone_notice(name, source_label, clone_channels, "--clone-all" if clone_all else "--clone")
        # Auto-clone Honcho config for the new profile (only with clone operations)
        try:
            from plugins.memory import import_provider_module
            honcho_cli = import_provider_module("honcho", "cli")
        except Exception:
            honcho_cli = None  # Honcho plugin not installed
        if honcho_cli is not None:
            try:
                if honcho_cli.clone_honcho_for_profile(name):
                    print(t("profile.honcho_cloned", peer=name))
            except honcho_cli.ConfigWriteRefused as e:
                print(t("profile.honcho_not_cloned", error=e))
            except Exception:
                pass  # Honcho not configured
    else:
        # Fresh profiles only: clones already carry the source's (user-curated) skills.
        from agent.i18n import t

        result = seed_profile_skills(profile_dir)
        if result and result.get("skipped_opt_out"):
            print(t("profile.no_skills_seeded"))
        elif result:
            print(t("profile.skills_synced", count=len(result.get('copied', []))))
        else:
            print(t("profile.skills_seed_failed", name=name))
    if not no_alias:
        from agent.i18n import t

        collision = check_alias_collision(name)
        if collision:
            print(t("profile.alias_collision", name=name, collision=collision))
            print(t("profile.alias_custom_hint", name=name))
            print(t("profile.alias_flag_hint", name=name))
        else:
            wrapper_path = create_wrapper_script(name)
            if wrapper_path:
                print(t("profile.wrapper_created", path=wrapper_path))
                if not _is_wrapper_dir_in_path():
                    print(t("profile.wrapper_not_in_path", dir=_get_wrapper_dir()))
                    print(t("profile.wrapper_path_hint"))
    try:
        profile_dir_display = "~/" + profile_dir.relative_to(Path.home()).as_posix()
    except ValueError:
        profile_dir_display = str(profile_dir)
    from agent.i18n import t

    print(t("profile.next_steps_header"))
    print(t("profile.next_setup", name=name))
    print(t("profile.next_chat", name=name))
    from hermes_cli.gateway_multiplex_served import live_default_gateway_pid, recorded_served_profiles
    from hermes_cli.profiles import normalize_profile_name
    served = recorded_served_profiles() if live_default_gateway_pid() is not None else None
    if served is not None and normalize_profile_name(name) in {normalize_profile_name(p) for p in served}:
        print(t("profile.next_served_now"))
    elif served is not None:
        # The multiplexer did not pick the profile up (older gateway or the signal failed): a restart serves it.
        print(t("profile.next_gateway_restart"))
    else:
        print(t("profile.next_gateway_start", name=name))
    if clone or clone_all:
        print(t("profile.next_env_edit", dir=profile_dir_display))
        print(t("profile.next_soul_edit", dir=profile_dir_display))
    else:
        print(t("profile.next_no_keys", name=name))
        print(t("profile.next_inherit_hint"))
        print(t("profile.next_soul_customize", dir=profile_dir_display))
    print()


def _profile_delete(args):
    from hermes_cli.profiles import delete_profile
    try:
        delete_profile(args.profile_name, yes=getattr(args, "yes", False))
    except (ValueError, FileNotFoundError, RuntimeError) as e:
        _die(f"Error: {e}")


def _describe_target_dir(name: str) -> Path:
    """Profile dir for ``describe``: ``default`` maps to the CURRENT home (get_hermes_home),
    everything else to its named directory."""
    from hermes_cli import profiles as _profiles_mod
    if _profiles_mod.normalize_profile_name(name) == "default":
        from hermes_constants import get_hermes_home as _hh
        return Path(_hh())
    return _profiles_mod.get_profile_dir(name)


def _profile_describe(args):
    from agent.i18n import t
    from hermes_cli import profiles as _profiles_mod
    all_flag = bool(getattr(args, "all_missing", False))
    auto_flag = bool(getattr(args, "auto", False))
    overwrite_flag = bool(getattr(args, "overwrite", False))
    text_value = getattr(args, "text", None)
    name = getattr(args, "profile_name", None)
    if all_flag and not auto_flag:
        _die("profile describe: --all requires --auto", 2, err=True)
    if all_flag and (text_value or name):
        _die("profile describe: --all is mutually exclusive with a profile name / --text", 2, err=True)
    if not all_flag and not name:
        _die("profile describe: profile name is required (or --all --auto)", 2, err=True)
    if text_value and auto_flag:
        _die("profile describe: --text is mutually exclusive with --auto", 2, err=True)

    # Show current description if no operation requested.
    if name and not text_value and not auto_flag:
        try:
            profile_dir = _describe_target_dir(name)
        except Exception as exc:
            _die(t("profile.error", error=exc), err=True)
        if not profile_dir.is_dir():
            _die(t("profile.describe_not_found", name=name), err=True)
        meta = _profiles_mod.read_profile_meta(profile_dir)
        desc = meta.get("description") or ""
        if not desc:
            print(t("profile.describe_none_set", name=name))
        else:
            tag = "[auto] " if meta.get("description_auto") else ""
            print(f"{tag}{desc}")
        sys.exit(0)

    # --text path: just write the user-authored description.
    if text_value:
        try:
            _profiles_mod.write_profile_meta(_describe_target_dir(name), description=text_value, description_auto=False)
            print(t("profile.description_updated", name=name))
        except Exception as exc:
            _die(t("profile.error", error=exc), err=True)
        sys.exit(0)

    # --auto path: invoke the LLM describer.
    from hermes_cli import profile_describer as _pd
    if all_flag:
        targets = _pd.list_describable_profiles(missing_only=True)
        if not targets:
            _die(t("profile.describe_all_done"), 0)
    else:
        targets = [name]
    ok_count = 0
    for tgt in targets:
        outcome = _pd.describe_profile(tgt, overwrite=overwrite_flag)
        if outcome.ok:
            ok_count += 1
            print(t("profile.described", name=outcome.profile_name, description=outcome.description))
        else:
            print(f"profile describe {outcome.profile_name}: {outcome.reason}", file=sys.stderr)
    sys.exit(0 if (ok_count > 0 if all_flag else ok_count == 1) else 1)


def _profile_show(args):
    name = args.profile_name
    from hermes_cli.profiles import (
        get_profile_dir, profile_exists, _read_config_model, _check_gateway_running,
        _served_by_running_multiplexer, _count_skills, _read_distribution_meta, _wrapper_path,
        find_alias_for_profile, format_profile_label, read_profile_meta,
    )
    from agent.i18n import t

    if not profile_exists(name):
        _die(t("profile.alias_profile_missing", name=name))
    profile_dir = get_profile_dir(name)
    model, provider = _read_config_model(profile_dir)
    gw = _check_gateway_running(profile_dir) or _served_by_running_multiplexer(name)
    dist_name, dist_version, dist_source = _read_distribution_meta(profile_dir)
    alias_name = find_alias_for_profile(name)
    display = read_profile_meta(profile_dir).get("display_name", "")
    from agent.i18n import t

    print(t("profile.info_header", label=format_profile_label(name, display)))
    print(t("profile.info_path", path=profile_dir))
    if model:
        print(t("profile.info_model", model=model, provider=f" ({provider})" if provider else ""))
    print(t("profile.info_gateway", state='running' if gw else 'stopped'))
    print(t("profile.info_skills", count=_count_skills(profile_dir)))
    print(t("profile.info_env", state='exists' if (profile_dir / '.env').exists() else 'not configured'))
    print(t("profile.info_soul", state='exists' if (profile_dir / 'SOUL.md').exists() else 'not configured'))
    if dist_name:
        print(t("profile.info_distribution", name=dist_name, version=dist_version or '?'))
        if dist_source:
            print(t("profile.info_dist_source", source=dist_source))
        print(t("profile.info_manifest_hint", name=name))
    if alias_name:
        print(t("profile.info_alias", alias=alias_name, name=name, path=_wrapper_path(alias_name)))
    print()


def _profile_alias(args):
    from hermes_cli.profiles import (
        _get_wrapper_dir, _is_wrapper_dir_in_path, check_alias_collision, create_wrapper_script,
        profile_exists, remove_wrapper_script, validate_alias_name,
    )
    name = args.profile_name
    remove = getattr(args, "remove", False)
    custom_name = getattr(args, "alias_name", None)
    alias_name = custom_name or name
    try:
        validate_alias_name(alias_name)
    except ValueError as exc:
        _die(f"Error: {exc}")
    if remove:  # runs without the profile: an orphan alias outlives it
        from agent.i18n import t

        exists = profile_exists(name)
        if custom_name and not exists:  # orphan cleanup is `alias <alias> --remove`
            _die(t("profile.alias_profile_missing", name=name))
        if remove_wrapper_script(alias_name):
            print(t("profile.alias_removed", alias=alias_name))
        elif not exists:
            _die(t("profile.alias_and_profile_missing", alias=alias_name, name=name))
        else:
            print(t("profile.alias_not_found", alias=alias_name))
        return
    if not profile_exists(name):
        _die(t("profile.alias_profile_missing", name=name))
    collision = check_alias_collision(alias_name)
    if collision:
        _die(t("profile.collision_error", collision=collision))
    wrapper_path = create_wrapper_script(alias_name, target=name if custom_name else None)
    if wrapper_path:
        print(t("profile.alias_created", path=wrapper_path))
        if not _is_wrapper_dir_in_path():
            print(t("profile.wrapper_not_in_path", dir=_get_wrapper_dir()))


def _profile_rename(args):
    from agent.i18n import t
    from hermes_cli.profiles import normalize_profile_name, rename_profile
    try:
        new_dir = rename_profile(args.old_name, args.new_name)
        if normalize_profile_name(args.old_name) != "default":
            print(t("profile.renamed", old=args.old_name, new=args.new_name))
            print(t("profile.rename_path", path=new_dir))
    except (ValueError, FileExistsError, FileNotFoundError) as e:
        _die(t("profile.error", error=e))


def _profile_migrate_identity(args):
    """Retry the identity migration of a rename that already completed. Exits non-zero when a
    live gateway would not migrate (it still owns the routing index in memory), or when a
    database rejected the rewrite (collision, lock, partial failure)."""
    from agent.i18n import t
    from hermes_cli.profile_identity import migrate_profile_identity
    try:
        migrated = migrate_profile_identity(args.old_name, args.new_name)
    except (ValueError, FileNotFoundError) as e:
        _die(t("profile.error", error=e))
    if not migrated:
        _die(t("profile.identity_migrate_failed", old=args.old_name, new=args.new_name), err=True)
    print(t("profile.identity_migrated", old=args.old_name, new=args.new_name))


def _profile_purge_identity(args):
    """Retry the identity purge of a delete that already completed. Exits non-zero when a live
    gateway would not purge (it still owns the routing index in memory), or when a database rejected
    the delete (lock, partial failure)."""
    from agent.i18n import t
    from hermes_cli.profile_identity import purge_profile_identity
    try:
        purged = purge_profile_identity(args.profile_name)
    except ValueError as e:
        _die(t("profile.error", error=e))
    if not purged:
        _die(t("profile.identity_purge_failed", name=args.profile_name), err=True)
    print(t("profile.identity_purged", name=args.profile_name))


def _profile_export(args):
    from agent.i18n import t
    from hermes_cli.profiles import export_profile, get_profile_export_path
    name = args.profile_name
    try:
        output = args.output or str(get_profile_export_path(name))
        result_path = export_profile(name, output)
        print(t("profile.exported", name=name, path=result_path))
    except (ValueError, FileNotFoundError, OSError) as e:
        _die(t("profile.error", error=e))


def _profile_import(args):
    from agent.i18n import t
    from hermes_cli.profiles import check_alias_collision, create_wrapper_script, import_profile
    try:
        profile_dir = import_profile(args.archive, name=getattr(args, "import_name", None))
        name = profile_dir.name
        print(t("profile.imported", name=name, path=profile_dir))
        if not check_alias_collision(name):
            wrapper_path = create_wrapper_script(name)
            if wrapper_path:
                print(t("profile.wrapper_created", path=wrapper_path))
        print()
    except (ValueError, FileExistsError, FileNotFoundError) as e:
        _die(t("profile.error", error=e))


def _profile_install(args):
    import tempfile
    from hermes_cli.profile_distribution import DistributionError, install_distribution, plan_install
    try:
        # Preview: stage into a scratch dir, show the manifest, then do the real install.
        # The double-stage avoids any side-effects if the user declines.
        with tempfile.TemporaryDirectory(prefix="hermes_dist_preview_") as tmp:
            plan = plan_install(args.source, Path(tmp), override_name=getattr(args, "install_name", None))
            _render_distribution_plan(plan)
            if not getattr(args, "yes", False) and not _confirm("\nProceed with install? [y/N] "):
                print("Install cancelled.")
                return
        plan = install_distribution(
            args.source, name=getattr(args, "install_name", None), force=getattr(args, "force", False),
            create_alias=getattr(args, "alias", False),
        )
        print(t("profile.installed_header", name=plan.manifest.name, version=plan.manifest.version))
        print(t("profile.installed_path", path=plan.target_dir))
        if plan.manifest.env_requires:
            print(t("profile.installed_env_next", example=plan.target_dir))
        if plan.has_cron:
            print(t("profile.installed_cron_note", name=plan.manifest.name))
        print(t("profile.installed_use", name=plan.manifest.name))
    except (DistributionError, ValueError) as e:
        _die(t("profile.error", error=e))


def _profile_update(args):
    from agent.i18n import t
    from hermes_cli.profile_distribution import DistributionError, read_manifest, update_distribution
    from hermes_cli.profiles import get_profile_dir, normalize_profile_name
    try:
        canon = normalize_profile_name(args.profile_name)
        current = read_manifest(get_profile_dir(canon))
        if current is None:
            _die(t("profile.update_not_distribution", name=canon))
        force_config = getattr(args, "force_config", False)
        if not getattr(args, "yes", False):
            print(t("profile.update_source", name=canon, source=current.source or '(no source)'))
            print(t("profile.update_current_version", version=current.version))
            if force_config:
                print(t("profile.update_force_config"))
            else:
                print(t("profile.update_preserve_config"))
            print(t("profile.update_userdata_untouched"))
            if not _confirm(t("profile.update_confirm")):
                print(t("profile.update_cancelled"))
                return
        plan = update_distribution(canon, force_config=force_config)
        print(t("profile.update_done", name=plan.manifest.name, version=plan.manifest.version))
        if plan.has_cron:
            print(t("profile.update_cron_note", name=plan.manifest.name))
    except (DistributionError, ValueError) as e:
        _die(t("profile.error", error=e))


_INFO_FIELDS = (
    ("description", "Description:  "),
    ("author", "Author:       "),
    ("license", "License:      "),
    ("hermes_requires", "Requires:     Hermes "),
    ("source", "Source:       "),
    ("installed_at", "Installed:    "),
)


def _profile_info(args):
    from agent.i18n import t
    from hermes_cli.profile_distribution import describe_distribution, DistributionError
    try:
        data = describe_distribution(args.profile_name)
    except (DistributionError, ValueError) as e:
        _die(t("profile.error", error=e))
    if not data:
        print(t("profile.info_not_distribution", name=args.profile_name))
        return
    print(t("profile.dist_header", name=data.get('name')))
    print(t("profile.dist_version", version=data.get('version', '?')))
    for key, label in _INFO_FIELDS:
        if data.get(key):
            print(f"{label}{data[key]}")
    env_reqs = data.get("env_requires") or []
    if env_reqs:
        print("\nEnvironment variables:")
        for er in env_reqs:
            tag = "required" if er.get("required", True) else "optional"
            line = f"  {er['name']} ({tag})"
            if er.get("description"):
                line += f" — {er['description']}"
            print(line)
            if er.get("default") is not None:
                print(f"      default: {er['default']}")
    print()


# Order mirrors the original if/elif chain; None = bare ``hermes profile``.
PROFILE_ACTIONS = {
    None: _profile_status,
    'list': _profile_list,
    'use': _profile_use,
    'create': _profile_create,
    'delete': _profile_delete,
    'describe': _profile_describe,
    'show': _profile_show,
    'alias': _profile_alias,
    'rename': _profile_rename,
    'purge-identity': _profile_purge_identity,
    'migrate-identity': _profile_migrate_identity,
    'export': _profile_export,
    'import': _profile_import,
    'install': _profile_install,
    'update': _profile_update,
    'info': _profile_info,
}


def cmd_profile(args):
    """Profile management — create, delete, list, switch, alias."""
    handler = PROFILE_ACTIONS.get(getattr(args, "profile_action", None))
    if handler is not None:
        return handler(args)

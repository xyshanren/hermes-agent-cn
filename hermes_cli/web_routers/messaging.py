"""Messaging dashboard routes: per-platform enable/config/test.

Extracted from ``hermes_cli.web_server``; helpers/state that tests monkeypatch on
``web_server`` stay there and are resolved late at call time (cycle-safe).
"""

import asyncio
import contextlib
import json
import logging
import os
import re
import secrets
import subprocess
import threading
import time
import urllib.parse
from datetime import datetime, timezone, UTC
from pathlib import Path
from typing import Any, Optional

from fastapi import APIRouter, HTTPException

from gateway.status import resolve_gateway_liveness, retained_gateway_state
from hermes_cli._subprocess_compat import windows_hide_flags
from hermes_cli.config import OPTIONAL_ENV_VARS, get_env_path
from hermes_constants import get_process_hermes_home
from hermes_cli.web_deps import LateState, late
from hermes_cli.web_server_gateway import _restart_gateway_after
from hermes_cli.web_server_messaging import (
    _messaging_platform_catalog,
)
from hermes_cli.web_routers._common import (
    REDACTED_CREDENTIAL_WRITE_DETAIL, http_failure, is_redacted_credential_preview,
    redacted_credential_preview,
)
from hermes_cli.web_models import (
    MessagingPlatformUpdate,
)

_log = logging.getLogger("hermes_cli.web_server")
router = APIRouter()

# Late-bound so a test's monkeypatch on the owning module wins at call time.
_config_profile_scope = late("_config_profile_scope", "hermes_cli.web_server_profiles")
_profile_scope = late("_profile_scope", "hermes_cli.web_server_profiles")
_resolve_profile_dir = late("_resolve_profile_dir", "hermes_cli.web_server_profiles")
_write_platform_enabled = late("_write_platform_enabled", "hermes_cli.web_server_messaging")
load_env = late("load_env", "hermes_cli.config")
load_config = late("load_config", "hermes_cli.config")
read_runtime_status = late("read_runtime_status", "gateway.status")
remove_env_value = late("remove_env_value", "hermes_cli.config")
save_env_value = late("save_env_value", "hermes_cli.config")
_gateway_subcommand = late("_gateway_subcommand", "hermes_cli.web_server_gateway")
_probe_gateway_health = late("_probe_gateway_health", "hermes_cli.web_server_gateway")
get_running_pid_cached = late("get_running_pid_cached", "gateway.status")
get_runtime_status_running_pid = late("get_runtime_status_running_pid", "gateway.status")
served_profile_runtime = late("served_profile_runtime", "gateway.status_served")
_GATEWAY_HEALTH_URL = LateState("_GATEWAY_HEALTH_URL")
# Display labels for env vars not in OPTIONAL_ENV_VARS (bridge toggles, callback modes, ...)
# so the UI can still render a friendly label. Rows: (key, description, prompt, extra flags).
_MESSAGING_ENV_FALLBACKS: dict[str, dict[str, Any]] = {
    key: {"description": description, "prompt": prompt, **extra}
    for key, description, prompt, extra in (
        ("WECOM_BOT_ID", "WeCom group bot ID", "WeCom Bot ID", {}),
        ("WECOM_SECRET", "WeCom group bot secret", "WeCom Secret", {"password": True}),
        ("WECOM_CALLBACK_CORP_ID", "WeCom corp ID", "WeCom Corp ID", {}),
        ("WECOM_CALLBACK_CORP_SECRET", "WeCom app corp secret", "WeCom Corp Secret", {"password": True}),
        ("WECOM_CALLBACK_AGENT_ID", "WeCom app agent ID", "WeCom Agent ID", {}),
        ("WECOM_CALLBACK_TOKEN", "WeCom callback verification token", "WeCom Token", {}),
        ("WECOM_CALLBACK_ENCODING_AES_KEY", "WeCom callback AES encoding key", "WeCom AES Key", {"password": True}),
        ("WEIXIN_ACCOUNT_ID", "iLink Bot account ID obtained through QR login in hermes gateway setup", "iLink Bot account ID", {}),
        ("WEIXIN_TOKEN", "iLink Bot token obtained through QR login in hermes gateway setup", "iLink Bot token", {"password": True}),
        ("WEIXIN_BASE_URL", "iLink API base URL saved by QR login (default: https://ilinkai.weixin.qq.com)", "iLink API base URL", {}),
        ("FEISHU_APP_ID", "Feishu / Lark app ID", "App ID", {}),
        ("FEISHU_APP_SECRET", "Feishu / Lark app secret", "App secret", {"password": True}),
        ("FEISHU_ENCRYPT_KEY", "Feishu / Lark encrypt key", "Encrypt key", {"password": True}),
        ("FEISHU_VERIFICATION_TOKEN", "Feishu / Lark verification token", "Verification token", {"password": True}),
        ("DINGTALK_CLIENT_ID", "DingTalk client ID (App key)", "Client ID", {}),
        ("DINGTALK_CLIENT_SECRET", "DingTalk client secret (App secret)", "Client secret", {"password": True}),
    )
}


def _env_value_rules(platform_id: str) -> dict[str, tuple[Any, str]]:
    """``{env key: (accepts(value), 400 detail)}`` declared on the platform plugin's PlatformEntry
    (``env_value_rules``; e.g. a platform that wants an app id rejects a bot token clearly).

    Resolve this in the request's own scope, right after :func:`_require_platform`: the catalog build
    there has just materialized every plugin entry, so the lookup imports nothing, whereas inside
    ``_profile_scope`` the registry's profile overlay may not hold the entry and every rule would
    silently stop applying. Without rules on the entry (the dashboard's own profile disabled the
    plugin, a user plugin overrides it) a bundled platform's ``dashboard_card.py`` answers, read from
    its file: the rules guard the edited profile's values whatever the dashboard's profile loads."""
    from gateway.platform_env import bundled_sibling
    from gateway.platform_registry import platform_registry
    entry = platform_registry.get(platform_id)
    if entry is not None and entry.env_value_rules:
        return dict(entry.env_value_rules)
    card = getattr(bundled_sibling(platform_id, "dashboard_card"), "DASHBOARD_CARD", None) or {}
    return dict(card.get("env_value_rules") or {})


def _validate_messaging_env_value(rules: dict[str, tuple[Any, str]], key: str, value: str) -> None:
    rule = rules.get(key)
    if value and rule and not rule[0](value):
        raise HTTPException(status_code=400, detail=rule[1])


# Allowlists (``*_ALLOWED_USERS``, ``LINE_ALLOWED_GROUPS``, ``SIMPLEX_GROUP_ALLOWED``) are
# comma-separated IDs, not secrets: clients render them as one editable entry per ID, which
# needs the saved value instead of a redacted preview.
_ALLOWLIST_KEY_RE = re.compile(r"_ALLOWED(?:_[A-Z]+)?$")


def _messaging_env_info(key: str) -> dict[str, Any]:
    info = OPTIONAL_ENV_VARS.get(key) or _MESSAGING_ENV_FALLBACKS.get(key) or {}
    is_password = bool(info.get("password", False))
    return {
        "description": info.get("description", ""),
        "prompt": info.get("prompt", key),
        "help": info.get("help", ""),
        "url": info.get("url"),
        "is_password": is_password,
        "is_list": not is_password and bool(_ALLOWLIST_KEY_RE.search(key)),
        "advanced": info.get("advanced", False),
    }


def _catalog_lookup(platform_id: str) -> dict[str, Any] | None:
    return next((e for e in _messaging_platform_catalog() if e["id"] == platform_id), None)


def _require_platform(platform_id: str) -> dict[str, Any]:
    entry = _catalog_lookup(platform_id)
    if not entry:
        raise HTTPException(status_code=404, detail=f"Unknown messaging platform: {platform_id}")
    return entry


def _platform_enablement(
    platform_id: str, entry: dict[str, Any], env_on_disk: dict[str, str], scoped: bool
) -> tuple[bool, bool, dict | None]:
    """(enabled, configured, home_channel). Profile-scoped: derive from the profile's
    config.yaml + .env only — load_gateway_config()'s env-override layer reads
    os.environ and would leak the root install's tokens into the profile's state."""
    required = entry["required_env"]
    if scoped:
        configured = bool(required) and all(env_on_disk.get(key) for key in required)
        try:
            plat_cfg = (load_config().get("platforms") or {}).get(platform_id)
            plat_cfg = plat_cfg if isinstance(plat_cfg, dict) else {}
            hc = plat_cfg.get("home_channel")
            # Setup writes credentials without a platforms entry; explicit disable wins.
            raw_enabled = plat_cfg.get("enabled")
            enabled = False if raw_enabled is False else bool(raw_enabled) or configured
            home_channel = hc if isinstance(hc, dict) else None
        except Exception:
            enabled, home_channel = False, None
        return enabled, configured, home_channel
    try:
        from gateway.config import Platform, load_gateway_config

        gateway_config = load_gateway_config()
        platform = Platform(platform_id)
        platform_config = gateway_config.platforms.get(platform)
        enabled = bool(platform_config and platform_config.enabled)
        configured = bool(platform_config and gateway_config._is_platform_connected(platform, platform_config))
        home_channel = platform_config.home_channel.to_dict() if platform_config and platform_config.home_channel else None
    except Exception:
        enabled, home_channel = False, None
        configured = all(env_on_disk.get(key) or os.getenv(key, "") for key in required)
    return enabled, configured, home_channel


def _messaging_platform_payload(
    entry: dict[str, Any], env_on_disk: dict[str, str], runtime: dict | None,
    scoped: bool = False, profile_home: Optional[Path] = None,
) -> dict[str, Any]:
    platform_id = entry["id"]
    rt = runtime if isinstance(runtime, dict) else {}
    runtime_platforms = rt.get("platforms")
    runtime_platform = runtime_platforms.get(platform_id, {}) if isinstance(runtime_platforms, dict) else {}
    if not isinstance(runtime_platform, dict):
        runtime_platform = {}
    # Same shared liveness ladder /api/status uses, so the sidebar strip and the
    # Channels page can never disagree on one page load. profile_home is passed when
    # scoped to a named profile: gateway/status readers resolve process-level paths
    # and do NOT follow the HERMES_HOME contextvar override, so without it messaging
    # silently reports another profile's gateway.
    gateway_running = resolve_gateway_liveness(
        profile_dir=profile_home, runtime=runtime,
        health_probe=_probe_gateway_health if _GATEWAY_HEALTH_URL else None,
        pid_probe=get_running_pid_cached, runtime_reader=read_runtime_status,
        runtime_pid_probe=get_runtime_status_running_pid,
    ).running
    if not gateway_running:
        # gateway_state.json outlives its writer and keeps per-platform entries across
        # restarts, so a stopped gateway that once ran WITHOUT credentials still says
        # "fatal / No bot token configured" after the user saved a token. Only a live
        # process's verdict describes the current config; a dead one's is history.
        runtime_platform = {}

    def env_value(key: str) -> str:
        # Profile-scoped: judge only the profile's own .env — the dashboard process's
        # os.environ carries the ROOT install's .env and would report root credentials as the profile's.
        return env_on_disk.get(key) or ("" if scoped else os.getenv(key, ""))

    env_vars = []
    for key in entry["env_vars"]:
        value, info = env_value(key), _messaging_env_info(key)
        env_vars.append({
            "key": key, "required": key in entry["required_env"], "is_set": bool(value),
            "redacted_value": redacted_credential_preview(value),
            "value": value if info["is_list"] else None, **info,
        })

    enabled, configured, home_channel = _platform_enablement(platform_id, entry, env_on_disk, scoped)
    if gateway_running and runtime_platform.get("mirrored_from"):
        # Served secondary: the default's shared listener already answers this platform at
        # /p/<profile>/... (enabling it locally 409s), so the secondary's own empty config
        # must not project Disabled over the live mirror (#121125).
        enabled, configured = True, True

    state = runtime_platform.get("state")
    if not enabled:
        state = "disabled"
    elif not configured:
        state = "not_configured"
    elif gateway_running and not state:
        state = "pending_restart"
    elif not gateway_running and not state:
        # Same verdict /api/status gives: ``hermes gateway stop`` keeps the last failure on disk,
        # and a profile the operator stopped must not wear a "Start failed" badge for it.
        state = "startup_failed" if retained_gateway_state(rt) == "startup_failed" else "gateway_stopped"

    error_code = runtime_platform.get("error_code")
    error_message = runtime_platform.get("error_message")
    if state == "startup_failed":
        error_code = error_code or "startup_failed"
        error_message = error_message or rt.get("exit_reason")

    payload = {
        "id": platform_id, "name": entry["name"], "description": entry["description"],
        "docs_url": entry["docs_url"], "enabled": enabled, "configured": configured,
        "gateway_running": gateway_running, "state": state, "error_code": error_code,
        "error_message": error_message, "updated_at": runtime_platform.get("updated_at"),
        "home_channel": home_channel, "env_vars": env_vars,
        # Multiplex secondary served on the default's shared listener: the vendor callback URL.
        "ingress_url": runtime_platform.get("ingress_url") if gateway_running else None,
    }
    return payload


def _platform_payloads(scoped_dir: Optional[Path], entries) -> list[dict[str, Any]]:
    """Payloads for ``entries``; call inside ``_profile_scope`` (load_env honors the
    HERMES_HOME contextvar; the gateway status readers do not, hence the explicit path)."""
    env_on_disk = load_env()
    runtime = read_runtime_status(path=scoped_dir / "gateway_state.json") if scoped_dir is not None else read_runtime_status()
    # A profile served by the multiplexer writes no live record of its own; its adapters live in the
    # multiplexer's record under ``<profile>:<platform>``. A leftover ``gateway_state.json`` from the
    # profile's standalone days outranks nothing: only a record proving a live own gateway does —
    # the same rung order ``resolve_gateway_liveness`` uses (own runtime PID before the multiplexer),
    # so the two surfaces cannot disagree. Unscoped, the profile is the process's own home (a pooled
    # ``hermes --profile X serve``).
    own_home = scoped_dir if scoped_dir is not None else get_process_hermes_home()
    runtime = served_profile_runtime(own_home, runtime) or runtime
    return [_messaging_platform_payload(entry, env_on_disk, runtime, scoped=scoped_dir is not None, profile_home=scoped_dir)
            for entry in entries]


@contextlib.contextmanager
def _onboarding_save_errors(log_msg: str, detail: str):
    """Map onboarding env/config write failures: ValueError -> 400 (its text),
    anything else -> logged + fixed 500 ``detail``; HTTPException passes through."""
    try:
        yield
    except HTTPException:
        raise
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        _log.exception(log_msg)
        raise HTTPException(status_code=500, detail=detail) from exc


# ── platform list / update / test ──────────────────────────────


@router.get("/api/messaging/platforms")
async def get_messaging_platforms(profile: Optional[str] = None):
    # Profile-scoped so the global profile switcher shows the TARGET profile's channel state.
    def _run():
        # Profile-scoped so the dashboard's global profile switcher shows the TARGET profile's channel
        # credentials/state, not the root install's. load_env() honors the HERMES_HOME contextvar override;
        # the gateway status readers do NOT (they resolve process-level paths), so the profile directory is
        # passed explicitly for those (#71211).
        with _profile_scope(profile) as scoped_dir:
            return {
                "env_path": str(get_env_path()),
                "gateway_start_command": " ".join(["hermes", *_gateway_subcommand(profile, "start")]),
                "platforms": _platform_payloads(scoped_dir, _messaging_platform_catalog()),
            }

    return await asyncio.to_thread(_run)


def _multiplex_port_binding_conflict(platform_id: str, requested_profile: Optional[str]) -> Optional[str]:
    """Reason enabling ``platform_id`` on the target profile is pointless under a multiplexed
    gateway, or ``None`` when allowed.

    With ``gateway.multiplex_profiles`` on, the default profile's listener already mirrors
    ``api_server`` and ``webhook`` at ``/p/<profile>/`` for every profile, so a SECONDARY must not
    enable a second one. Every other inbound-port platform IS allowed on a
    secondary: the gateway serves it on the shared listener at ``/p/<profile>/<path>``.
    """
    from gateway.config import SHARED_LISTENER_MIRROR_PLATFORMS

    if platform_id not in SHARED_LISTENER_MIRROR_PLATFORMS:
        return None

    requested = (requested_profile or "").strip()
    if not requested or requested.lower() == "current":
        from hermes_cli.profiles import get_active_profile_name

        # The dashboard's own profile. "custom" (unrecognized HERMES_HOME) is outside
        # the profiles tree, so a multiplexed gateway never serves it.
        target = get_active_profile_name()
    else:
        _resolve_profile_dir(requested)  # same 400/404 as _profile_scope
        target = requested
    if target in ("default", "custom"):
        return None

    # The flag that matters is the one the shared gateway settled at startup: its served record when
    # it runs, else the DEFAULT profile's explicit config (plus the process-wide
    # GATEWAY_MULTIPLEX_PROFILES override). An unset flag is decided by the gateway, not guessed here.
    from hermes_cli.gateway_multiplex_mode import default_gateway_multiplexes
    if not default_gateway_multiplexes():
        return None

    return (
        f"Cannot enable '{platform_id}' on profile '{target}': gateway.multiplex_profiles is on and the "
        f"default profile's listener already serves it for every profile at /p/{target}/. Configure it "
        "on the default profile instead (disabling or clearing it here is still allowed)."
    )


@router.put("/api/messaging/platforms/{platform_id}")
async def update_messaging_platform(platform_id: str, body: MessagingPlatformUpdate, profile: Optional[str] = None):
    entry = _require_platform(platform_id)
    env_value_rules = _env_value_rules(platform_id)

    target_profile = body.profile or profile
    if body.enabled:
        conflict = await asyncio.to_thread(_multiplex_port_binding_conflict, platform_id, target_profile)
        if conflict:
            # Reject BEFORE any .env/config.yaml write so the profile stays
            # loadable by the multiplexed gateway.
            _log.info(
                "Rejected messaging platform update: platform=%s profile=%s "
                "(multiplex port-binding conflict)", platform_id, target_profile or "current",
            )
            raise HTTPException(status_code=409, detail=conflict)

    allowed_env = set(entry["env_vars"])

    def _check_allowed(key: str) -> None:
        if key not in allowed_env:
            raise HTTPException(status_code=400, detail=f"{key} is not configurable for {entry['name']}")

    def _apply():
        with _profile_scope(target_profile):
            updates: dict[str, str] = {}

            # Validate the whole request before clearing or replacing anything.
            for key in body.clear_env:
                _check_allowed(key)
            for key, value in body.env.items():
                _check_allowed(key)
                trimmed = value.strip()
                if not trimmed:
                    continue
                if is_redacted_credential_preview(trimmed):
                    raise HTTPException(status_code=400, detail=REDACTED_CREDENTIAL_WRITE_DETAIL)
                _validate_messaging_env_value(env_value_rules, key, trimmed)
                updates[key] = trimmed

            for key in body.clear_env:
                remove_env_value(key)
            for key, value in updates.items():
                save_env_value(key, value)

            if body.enabled is not None:
                _write_platform_enabled(platform_id, body.enabled)

    with http_failure(f"PUT /api/messaging/platforms/{platform_id} failed", 500, detail="Internal server error"):
        await asyncio.to_thread(_apply)

        # Audit trail for channel config mutations: names only, never values.
        _log.info(
            "Messaging platform updated: platform=%s profile=%s enabled=%s "
            "env_keys=%s cleared_keys=%s",
            platform_id, target_profile or "current", body.enabled, sorted(body.env), sorted(body.clear_env),
        )
        # A live multiplexer serving this named profile builds the adapter from the new token now
        # (its periodic rescan would otherwise pick it up within a cycle); no gateway restart.
        hot_served = await asyncio.to_thread(_notify_multiplexer_hot_serve, target_profile)
        return {"ok": True, "platform": platform_id, "hot_served": hot_served}


def _notify_multiplexer_hot_serve(profile: Optional[str]) -> bool:
    """True when a live multiplexer serves the written profile and was told to rebuild its adapters.
    Unscoped (no ``?profile=``) means THIS process's profile: Desktop routes a pooled
    ``hermes --profile X serve`` without the query (#109088), so X must resolve here too."""
    from hermes_cli.gateway import _current_profile_name, named_profile_served_by_running_multiplexer
    from hermes_cli.gateway_multiplex_served import notify_multiplexer_profiles_changed
    name = (profile or "").strip() or _current_profile_name()
    if not name or name == "default" or not named_profile_served_by_running_multiplexer(name):
        return False
    return notify_multiplexer_profiles_changed(name) is not None


def _gate_env(name: str) -> str:
    """Per-profile allow/deny gate env read, always stripped (gateway seam)."""
    from gateway.platforms._shared import platform_gate_env

    return platform_gate_env(name)


def _platform_authz_env_names(platform_id: str) -> tuple[str, str]:
    """``(allowed_users_env, allow_all_env)`` for a platform, honoring plugin registry
    entries. Empty strings mean "this platform has no per-user authorization surface"
    (webhook-style trusted inbound or unknown), so no posture is computed for it."""
    allowed = allow_all = ""
    with contextlib.suppress(Exception):
        from gateway.platform_registry import platform_registry

        from gateway.platform_env import authz_field

        entry = platform_registry.get(platform_id)
        if entry is not None and getattr(entry, "trusted_inbound", False) is True:
            return "", ""
        allowed = authz_field(platform_id, "allowed_users_env", entry) or ""
        allow_all = authz_field(platform_id, "allow_all_env", entry) or ""
    return allowed, allow_all


def _platform_dm_policy(platform_id: str) -> str:
    """Effective ``dm_policy`` for the ACTIVE profile's ``platforms.<id>`` config
    (``open``/``allowlist``/``disabled``/``pairing``). The default here is NOT the adapter
    default: adapters without a config key never consult ``dm_policy`` in
    ``_principal_authorized``, so a policy-shaped key only matters where one exists."""
    with contextlib.suppress(Exception):
        plat_cfg = (load_config().get("platforms") or {}).get(platform_id)
        if isinstance(plat_cfg, dict):
            policy = str(plat_cfg.get("extra", {}).get("dm_policy") or "").strip().lower()
            if policy:
                return policy
    return ""


def _count_csv(value: str) -> int:
    return len([part for part in (value or "").split(",") if part.strip()])


def _messaging_platform_posture(
    platform_id: str, entry: dict[str, Any], scoped: bool, authz_env: tuple[str, str]
) -> dict[str, Any] | None:
    """Auth-posture verdict for a CONNECTED platform (must be called inside the profile
    scope, after the connectivity chain has already reported ``connected``).

    Mirrors the decision ladder of ``AuthorizationMixin._principal_authorized``
    (gateway/authz_mixin.py) for the "can any user reach the bot" question, evaluated
    against the ACTIVE profile's env/config only — never the dashboard process's
    ``os.environ`` (which carries the ROOT profile's credentials, #66030):

    - allow-all flags: ``{PLATFORM}_ALLOW_ALL_USERS`` then ``GATEWAY_ALLOW_ALL_USERS``
    - allowlists: the platform's ``{PLATFORM}_ALLOWED_USERS``, ``GATEWAY_ALLOWED_USERS``,
      plus the platform group vars (a group-only grant still authorizes real users)
    - pairing grants: approved users in the profile's pairing store (the gateway honors
      the store as a UNION with the allowlists)
    - adapter/config-enforced policy (``dm_policy: allowlist`` with an ``allow_from``):
      the own-policy adapters (WeCom, Weixin, QQBot, Yuanbao) gate at intake

    Everything failing → deny-all: the connection is up but no sender can get through,
    which the Channels "Test" button must not render as a plain green "connected".
    Returns ``None`` when the platform has no per-user authorization surface at all.
    *authz_env* is :func:`_platform_authz_env_names`, resolved OUTSIDE the profile scope (see
    :func:`_env_value_rules`: the scope's registry overlay may not hold the entry).
    """
    allowed_env, allow_all_env = authz_env
    if not allowed_env:
        return None

    # Same scoped-vs-process split _platform_enablement uses: under a named profile the
    # process env belongs to the ROOT install and must not authorize anyone here, and a
    # profile's .env must not borrow the root's allowlists (false green) either.
    def gate_env(name: str) -> str:
        if scoped:
            return load_env().get(name, "")
        return _gate_env(name)

    if allow_all_env and gate_env(allow_all_env).lower() in ("true", "1", "yes"):
        return {"posture": "open", "message": f"{entry['name']} is open: {allow_all_env} is set."}
    if gate_env("GATEWAY_ALLOW_ALL_USERS").lower() in ("true", "1", "yes"):
        return {"posture": "open", "message": "Gateway is open: GATEWAY_ALLOW_ALL_USERS is set."}

    allowlists = {
        allowed_env: gate_env(allowed_env),
        "GATEWAY_ALLOWED_USERS": gate_env("GATEWAY_ALLOWED_USERS"),
    }
    for env_name, value in allowlists.items():
        if value.strip():
            n = _count_csv(value)
            return {
                "posture": "allowlist",
                "message": f"Connected. {n} user{'s' if n != 1 else ''} allowlisted via {env_name}.",
            }

    if _platform_dm_policy(platform_id) == "allowlist":
        return {"posture": "allowlist", "message": "Connected. Access restricted by the configured allow_from policy."}

    # Pairing grants: the profile's approved users (the gateway honors the store as a
    # union with any allowlist, gateway/authz_mixin.py `_pairing_store_for`).
    approved = pending = 0
    with contextlib.suppress(Exception):
        from gateway.pairing import PairingStore

        store = PairingStore()
        approved = len(store.list_approved(platform_id))
        pending = len(store.list_pending(platform_id))
    if approved:
        return {
            "posture": "pairing",
            "message": f"Connected. {approved} user{'s' if approved != 1 else ''} paired.",
        }

    base = (
        f"{entry['name']} is connected, but no users are authorized yet — "
        f"set {allowed_env}, approve a pairing request, or enable pairing for new users."
    )
    if pending:
        base += f" {pending} pairing request{'s' if pending != 1 else ''} pending approval."
    return {"posture": "deny_all", "message": base}


@router.post("/api/messaging/platforms/{platform_id}/test")
async def test_messaging_platform(platform_id: str, profile: Optional[str] = None):
    entry = _require_platform(platform_id)
    authz_env = _platform_authz_env_names(platform_id)

    def _run():
        with _profile_scope(profile) as scoped_dir:
            payload = _platform_payloads(scoped_dir, [entry])[0]
            posture = None
            if payload["state"] == "connected":
                # Still inside the profile scope: load_env()/load_config()/PairingStore
                # must resolve the ACTIVE profile's env/config/pairing store, not the
                # dashboard process's root home.
                posture = _messaging_platform_posture(platform_id, entry, scoped_dir is not None, authz_env)
            return payload, posture

    payload, posture = await asyncio.to_thread(_run)

    def result(ok: bool, message: str) -> dict[str, Any]:
        return {"ok": ok, "state": payload["state"], "message": message}

    if not payload["enabled"]:
        return result(False, f"{entry['name']} is disabled. Enable it, then restart the gateway.")
    if not payload["configured"]:
        missing = [field["key"] for field in payload["env_vars"] if field["required"] and not field["is_set"]]
        return result(False, f"Missing required setup: {', '.join(missing)}" if missing else "Platform setup is incomplete.")
    if not payload["gateway_running"]:
        return result(False, "Gateway is not running. Restart the gateway to connect this platform.")
    if payload["state"] == "connected":
        # Non-breaking extension (#66030): keep ok=True (the connection is genuinely up)
        # but surface the platform's auth posture so the UI can render yellow on
        # connected-but-unreachable, and say exactly what to configure.
        if posture is None:
            return result(True, f"{entry['name']} is connected.")
        return {
            "ok": True,
            "state": payload["state"],
            "message": posture["message"],
            "auth_posture": posture["posture"],
        }
    if payload.get("error_message"):
        return result(False, payload["error_message"])
    return result(False, "Setup looks complete, but the gateway has not reported a connection yet. Restart the gateway.")

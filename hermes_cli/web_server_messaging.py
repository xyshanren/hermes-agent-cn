"""Messaging-platform catalog helpers: platform overrides and env discovery.
"""

import logging
import os
import subprocess
import threading
from dataclasses import dataclass
from fastapi import HTTPException
from pathlib import Path
from typing import Any, Optional
from hermes_cli.config import OPTIONAL_ENV_VARS, write_platform_config_field
from hermes_cli.setup_hidden_env import is_setup_hidden_env as _is_setup_hidden_env
from hermes_cli.version_info import get_version_info

# Same logger the code used before extraction (record parity).
_log = logging.getLogger("hermes_cli.web_server")


# Card metadata for core-only platforms (no plugin, so no PlatformEntry to declare it). Plugin
# platforms declare theirs on their PlatformEntry (``dashboard_*`` / ``docs_url``, see
# :func:`_plugin_card_fields`). Entries omit fields they don't need; the catalog builder fills in
# env_vars from OPTIONAL_ENV_VARS via prefix matching when not specified.
_PLATFORM_OVERRIDES: dict[str, dict[str, Any]] = {
    "api_server": {
        "name": "API server",
        "description": "Expose Hermes as an OpenAI-compatible HTTP API for tools like Open WebUI.",
        "docs_url": "https://hermes-agent.nousresearch.com/docs/user-guide/messaging/",
        "env_vars": (
            "API_SERVER_ENABLED", "API_SERVER_KEY", "API_SERVER_PORT", "API_SERVER_HOST",
            "API_SERVER_MODEL_NAME",
        ),
        "required_env": (),
    },
    "webhook": {
        "name": "Webhooks",
        "description": "Receive events from GitHub, GitLab, and other webhook sources.",
        "docs_url": "https://hermes-agent.nousresearch.com/docs/user-guide/messaging/webhooks/",
        "env_vars": ("WEBHOOK_ENABLED", "WEBHOOK_PORT", "WEBHOOK_SECRET"), "required_env": (),
    },
    "msgraph_webhook": {
        "name": "Microsoft Graph Webhook",
        "description": "Receive Microsoft Graph change notifications (Teams meetings, Outlook, …).",
        "docs_url": "https://hermes-agent.nousresearch.com/docs/user-guide/messaging/msgraph-webhook",
        "required_env": (),
    },
}

# Display order: well-known platforms surface first; unknown plugins fall to
# the end alphabetically.
_PLATFORM_ORDER: tuple[str, ...] = (
    "dingtalk", "feishu", "wecom", "wecom_callback",
    "weixin", "qqbot", "yuanbao", "api_server", "webhook",
)


def _messaging_platform_catalog() -> tuple[dict[str, Any], ...]:
    """Build the messaging catalog from the gateway's Platform enum + plugin registry.

    Built-ins come from ``gateway.config.Platform`` (LOCAL excluded); plugin platforms from
    ``platform_registry.plugin_entries()`` so new adapters appear without a code change here.
    UI metadata comes from each plugin's PlatformEntry, or :data:`_PLATFORM_OVERRIDES` for core-only
    platforms; the rest is derived from id/required_env.
    """
    from gateway.config import Platform
    from hermes_cli.platforms import platform_available

    # Resolve plugin entries FIRST: plugin platforms leak into ``Platform.__members__`` as
    # pseudo-members once anything calls ``Platform("<plugin id>")``, and iterating the enum
    # first would claim them with no plugin metadata (nameless "Irc"/"Ntfy" cards).
    plugin_map: dict[str, Any] = {}
    try:
        # Plugin discovery normally runs as a side effect of importing model_tools, which this
        # server process doesn't do — trigger it explicitly (idempotent).
        from hermes_cli.plugins import discover_plugins
        discover_plugins()
        from gateway.platform_registry import platform_registry
        for plugin_entry in platform_registry.plugin_entries():
            plugin_map[plugin_entry.name] = plugin_entry
    except Exception:
        _log.debug("plugin platform registry unavailable", exc_info=True)

    seen: set[str] = set()
    entries: list[dict[str, Any]] = []
    builtin = [m.value for m in Platform.__members__.values() if m.value != "local"]
    for pid in builtin + list(plugin_map):
        if pid in seen:
            continue
        seen.add(pid)
        # CN subtraction: a platform this build does not ship has no adapter, so it must not
        # appear as a configurable channel card ("registered but not implemented").
        if not platform_available(pid):
            continue
        entries.append(_build_catalog_entry(pid, plugin_map.get(pid)))

    order = {pid: idx for idx, pid in enumerate(_PLATFORM_ORDER)}
    entries.sort(key=lambda e: (order.get(e["id"], len(_PLATFORM_ORDER)), e["name"].lower()))
    return tuple(entries)


def _channel_managed_env_keys() -> frozenset[str]:
    """Env-var keys owned by a Channels page platform card; the Keys/Env page hides them so the
    same fields aren't duplicated. Best-effort: if the catalog can't be built, nothing is hidden."""
    try:
        return frozenset(k for entry in _messaging_platform_catalog() for k in entry.get("env_vars", ()))
    except Exception:
        _log.debug("could not build channel-managed env key set", exc_info=True)
        return frozenset()


# Cross-cutting gateway / relay knobs stay on the Keys → Settings tab even though
# they use the ``messaging`` category in OPTIONAL_ENV_VARS. Platform-scoped vars
# (``DISCORD_*``, ``MATRIX_*``, …) are owned by the Messaging UI instead.
_MESSAGING_KEYS_PAGE_KEYS = frozenset({
    "GATEWAY_ALLOW_ALL_USERS", "GATEWAY_PROXY_KEY", "GATEWAY_PROXY_URL"})


def _platform_env_prefixes(platform_id: str) -> tuple[str, ...]:
    """Env-var prefixes owned by a messaging platform card (shared with the profile-clone
    channel stripper so a card and a clone agree on which keys belong to a platform)."""
    from hermes_cli.profile_channels import platform_env_prefixes
    return platform_env_prefixes(platform_id)


def _discover_platform_env_vars(platform_id: str) -> tuple[str, ...]:
    """All messaging-category env vars for a platform (override + plugin + prefix)."""
    prefixes = _platform_env_prefixes(platform_id)
    return tuple(sorted({
        name for name, info in OPTIONAL_ENV_VARS.items()
        if info.get("category") == "messaging"
        and name not in _MESSAGING_KEYS_PAGE_KEYS
        and not _is_setup_hidden_env(name)
        and any(name.startswith(prefix) for prefix in prefixes)}))


def _merge_platform_env_vars(platform_id: str, override: dict[str, Any], plugin_entry: Any | None) -> tuple[str, ...]:
    """Canonical env-var list for a platform card. Required credentials always survive: hiding a
    required field would make the platform unconfigurable."""
    discovered = _discover_platform_env_vars(platform_id)
    if "env_vars" in override:
        explicit = tuple(key for key in override["env_vars"] if not _is_setup_hidden_env(key))
        return tuple(dict.fromkeys((*explicit, *discovered)))
    if plugin_entry is not None and plugin_entry.required_env:
        return tuple(dict.fromkeys((*tuple(plugin_entry.required_env), *discovered)))
    return discovered


def _plugin_card_fields(plugin_entry: Any) -> dict[str, Any]:
    """A plugin's declared card metadata in override shape; undeclared fields are left out so
    the builder falls back exactly as for a platform with no metadata."""
    fields: dict[str, Any] = {
        "name": plugin_entry.dashboard_label, "description": plugin_entry.dashboard_description,
        "docs_url": plugin_entry.docs_url,
    }
    if plugin_entry.dashboard_env_vars:
        fields["env_vars"] = plugin_entry.dashboard_env_vars
    if plugin_entry.dashboard_required_env is not None:
        fields["required_env"] = plugin_entry.dashboard_required_env
    return fields


def _build_catalog_entry(platform_id: str, plugin_entry: Any | None = None) -> dict[str, Any]:
    override = _PLATFORM_OVERRIDES.get(platform_id) or (
        _plugin_card_fields(plugin_entry) if plugin_entry is not None else {})
    if "required_env" in override:
        required_env = tuple(override["required_env"])
    else:
        required_env = tuple(plugin_entry.required_env or ()) if plugin_entry is not None else ()
    plugin_label = plugin_entry.label if plugin_entry is not None else None
    plugin_hint = (plugin_entry.install_hint or "") if plugin_entry is not None else None
    return {
        "id": platform_id,
        "name": override.get("name") or plugin_label or platform_id.replace("_", " ").title(),
        "description": override.get("description") or plugin_hint or "",
        "docs_url": override.get("docs_url", ""),
        "env_vars": _merge_platform_env_vars(platform_id, override, plugin_entry),
        "required_env": required_env,
    }


def _write_platform_enabled(platform_id: str, enabled: bool) -> None:
    write_platform_config_field(platform_id, "enabled", enabled)



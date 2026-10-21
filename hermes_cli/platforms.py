"""Shared platform registry for Hermes Agent."""

from collections import OrderedDict
from typing import NamedTuple


# CN 减法 (Cat 1 减法) — the platforms this build does NOT ship.
#
# The upstream adapters live under ``plugins/platforms/<name>/``; CN removed the
# overseas ones in-tree, so the directories are gone. This set is the single
# switch that keeps the removed platforms out of every user-facing enumeration
# (CLI/TUI menus, the dashboard's messaging catalog, the config defaults) so
# nothing offers a platform this build cannot connect to.
#
# The `Platform` enum in `gateway/config.py` still carries the upstream member
# names: they are identifier constants used across the core's platform
# branches, not registrations. Availability is decided here and by the
# platform registry (a platform with no adapter is not offered).
CN_DISABLED_PLATFORMS: frozenset[str] = frozenset({
    "a2a",
    "bluebubbles",
    "buzz",
    "discord",
    "email",
    "google_chat",
    "homeassistant",
    "irc",
    "line",
    "matrix",
    "mattermost",
    "msgraph_webhook",
    "ntfy",
    "photon",
    "raft",
    "signal",
    "simplex",
    "slack",
    "sms",
    "teams",
    "telegram",
    "whatsapp",
    "whatsapp_cloud",
})


def platform_available(platform_id: str) -> bool:
    """True when this build ships the platform (not in the CN subtraction set)."""
    return platform_id.lower() not in CN_DISABLED_PLATFORMS


class PlatformInfo(NamedTuple):
    """Metadata for a single platform entry."""
    label: str
    default_toolset: str


# Ordered so that TUI menus are deterministic.
PLATFORMS: OrderedDict[str, PlatformInfo] = OrderedDict([
    ("cli",            PlatformInfo(label="🖥️  CLI",            default_toolset="hermes-cli")),
    ("dingtalk",       PlatformInfo(label="💬 DingTalk",        default_toolset="hermes-dingtalk")),
    ("feishu",         PlatformInfo(label="🪽 Feishu",          default_toolset="hermes-feishu")),
    ("wecom",          PlatformInfo(label="💬 WeCom",           default_toolset="hermes-wecom")),
    ("wecom_callback", PlatformInfo(label="💬 WeCom Callback",  default_toolset="hermes-wecom-callback")),
    ("weixin",         PlatformInfo(label="💬 Weixin",          default_toolset="hermes-weixin")),
    ("qqbot",          PlatformInfo(label="💬 QQBot",           default_toolset="hermes-qqbot")),
    ("yuanbao",        PlatformInfo(label="🤖 Yuanbao",         default_toolset="hermes-yuanbao")),
    ("webhook",        PlatformInfo(label="🔗 Webhook",         default_toolset="hermes-webhook")),
    ("api_server",     PlatformInfo(label="🌐 API Server",      default_toolset="hermes-api-server")),
    ("cron",           PlatformInfo(label="⏰ Cron",            default_toolset="hermes-cron")),
])


def _plugin_label(entry) -> str:
    return f"{entry.emoji}  {entry.label}" if entry.emoji else entry.label


def platform_label(key: str, default: str = "") -> str:
    """Return the display label for a platform key (builtin, then plugin registry), or *default*."""
    info = PLATFORMS.get(key)
    if info is not None:
        return info.label
    if not platform_available(key):
        return default
    try:
        from gateway.platform_registry import platform_registry
        entry = platform_registry.get(key)
        if entry:
            return _plugin_label(entry)
    except Exception:
        pass
    return default


def get_all_platforms() -> OrderedDict[str, PlatformInfo]:
    """PLATFORMS plus plugin-registered platforms (appended after builtins) — use for menus.

    Platforms in the CN subtraction set are excluded: this build has no adapter
    for them, so offering them would be a dangling entry.
    """
    merged = OrderedDict(PLATFORMS)
    try:
        from gateway.platform_registry import platform_registry
        for entry in platform_registry.plugin_entries():
            if entry.name not in merged and platform_available(entry.name):
                merged[entry.name] = PlatformInfo(_plugin_label(entry), f"hermes-{entry.name}")
    except Exception:
        pass
    return merged

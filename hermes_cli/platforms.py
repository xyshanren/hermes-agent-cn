"""
Shared platform registry for Hermes Agent.

Single source of truth for platform metadata consumed by both
skills_config (label display) and tools_config (default toolset
resolution).  Import ``PLATFORMS`` from here instead of maintaining
duplicate dicts in each module.

Sprint 16 档 A.1 (CN 减法, 跟 8-12 P3 拍 A "Cat 1 减法" 1:1 配对):
- 5 个海外平台 (telegram / whatsapp / whatsapp_cloud / signal / bluebubbles) +
  msgraph_webhook 适配器入口 在 CN 端已停用
- get_all_platforms() 默认排除 CN_DISABLED_PLATFORMS (跟 mavis 4 件套 1:1 配对)
- PLATFORMS dict entry 保留 (Sprint 16 档 A.2 之后 `git rm` 海外平台文件时 0 影响)
- 7 个海外平台 entry 保留是过渡, 不是 dead code (等 Sprint 16 档 A.2 一起清)
"""

from collections import OrderedDict
from typing import NamedTuple


# Sprint 16 档 A.1: CN 减法 — 海外平台默认从 get_all_platforms() 排除
# Sprint 16 档 A.2 跟 11 个海外平台文件一起 `git rm`
CN_DISABLED_PLATFORMS: frozenset[str] = frozenset({
    "telegram",
    "whatsapp",
    "whatsapp_cloud",
    "signal",
    "bluebubbles",
    "msgraph_webhook",
})


class PlatformInfo(NamedTuple):
    """Metadata for a single platform entry."""
    label: str
    default_toolset: str


# Ordered so that TUI menus are deterministic.
PLATFORMS: OrderedDict[str, PlatformInfo] = OrderedDict([
    ("cli",            PlatformInfo(label="🖥️  CLI",            default_toolset="hermes-cli")),
    ("telegram",       PlatformInfo(label="📱 Telegram",        default_toolset="hermes-telegram")),
    ("discord",        PlatformInfo(label="💬 Discord",         default_toolset="hermes-discord")),
    ("slack",          PlatformInfo(label="💼 Slack",           default_toolset="hermes-slack")),
    ("whatsapp",       PlatformInfo(label="📱 WhatsApp",        default_toolset="hermes-whatsapp")),
    ("whatsapp_cloud", PlatformInfo(label="📱 WhatsApp Business (Cloud)", default_toolset="hermes-whatsapp")),
    ("signal",         PlatformInfo(label="📡 Signal",          default_toolset="hermes-signal")),
    ("bluebubbles",    PlatformInfo(label="💙 BlueBubbles",     default_toolset="hermes-bluebubbles")),
    ("email",          PlatformInfo(label="📧 Email",           default_toolset="hermes-email")),
    ("homeassistant",  PlatformInfo(label="🏠 Home Assistant",  default_toolset="hermes-homeassistant")),
    ("mattermost",     PlatformInfo(label="💬 Mattermost",      default_toolset="hermes-mattermost")),
    ("matrix",         PlatformInfo(label="💬 Matrix",          default_toolset="hermes-matrix")),
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


def platform_label(key: str, default: str = "") -> str:
    """Return the display label for a platform key, or *default*.

    Checks the static PLATFORMS dict first, then the plugin platform
    registry for dynamically registered platforms.
    """
    info = PLATFORMS.get(key)
    if info is not None:
        return info.label
    # Check plugin registry
    try:
        from gateway.platform_registry import platform_registry
        entry = platform_registry.get(key)
        if entry:
            return f"{entry.emoji}  {entry.label}" if entry.emoji else entry.label
    except Exception:
        pass
    return default


def get_all_platforms() -> "OrderedDict[str, PlatformInfo]":
    """Return PLATFORMS merged with any plugin-registered platforms.

    Plugin platforms are appended after builtins.  This is the function
    that tools_config and skills_config should use for platform menus.

    Sprint 16 档 A.1: 默认排除 CN_DISABLED_PLATFORMS (Cat 1 减法).
    Sprint 16 档 A.2: 海外平台文件 `git rm` 之后,PLATFORMS 里的 entry
    也会随之精简 (跟 8-12 P3 拍 A "Cat 1 减法" 1:1 配对).
    """
    merged: OrderedDict[str, PlatformInfo] = OrderedDict(
        (k, v) for k, v in PLATFORMS.items() if k not in CN_DISABLED_PLATFORMS
    )
    try:
        from gateway.platform_registry import platform_registry
        for entry in platform_registry.plugin_entries():
            if entry.name not in merged and entry.name not in CN_DISABLED_PLATFORMS:
                merged[entry.name] = PlatformInfo(
                    label=f"{entry.emoji}  {entry.label}" if entry.emoji else entry.label,
                    default_toolset=f"hermes-{entry.name}",
                )
    except Exception:
        pass
    return merged

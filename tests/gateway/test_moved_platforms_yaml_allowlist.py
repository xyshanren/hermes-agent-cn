"""config.yaml ``platforms.<name>.allowed_users`` gates DMs on the platforms moved from core into plugins.

Their registry entries declare ``allowed_users_env``, so with no env allowlist the gateway reads the live
adapter's ``extra.allowed_users``, as it already does for Telegram, Discord, Slack and the other plugin
platforms. Listed senders are admitted; everyone else stays default-deny.
"""

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from gateway.config import GatewayConfig, Platform, PlatformConfig
from gateway.session import SessionSource

_MOVED = ("signal", "weixin", "bluebubbles", "qqbot", "yuanbao", "whatsapp_cloud")



"""Allowlist matching compares qualified user_ids, not bare '@' localparts.

The generic ``user_id.split("@")[0]`` alias in ``_principal_matches_allowlist``
was added for WhatsApp JIDs (``<phone>@s.whatsapp.net``) before WhatsApp got a
dedicated alias expansion. Left unconditional, it makes a bare allowlist entry
``alice`` admit ``alice@<any domain>`` on every platform whose user_id is
'@'-shaped (email, Google Chat, iMessage handles) — domains the sender controls.
"""

import pytest

from gateway.authz_mixin import _principal_matches_allowlist
from gateway.config import Platform
from gateway.session import SessionSource


def _source(platform: Platform, user_id: str) -> SessionSource:
    return SessionSource(
        platform=platform,
        user_id=user_id,
        chat_id=user_id,
        user_name="tester",
        chat_type="dm",
    )


def _make_runner():
    from gateway.run import GatewayRunner

    runner = object.__new__(GatewayRunner)
    runner.pairing_store = None
    return runner


# The BlueBubbles adapter does no sender gate of its own, so with its platform
# allowlist unset GATEWAY_ALLOWED_USERS is the only enforcement on that path.
@pytest.mark.parametrize(
    ("platform", "user_id"),
    [
        (Platform.WHATSAPP, "15550000001@s.whatsapp.net"),
        (Platform.WHATSAPP, "15550000001:47@s.whatsapp.net"),
        (Platform.WHATSAPP_CLOUD, "15550000001@s.whatsapp.net"),
    ],
)
def test_whatsapp_bare_phone_entry_still_matches_jid(platform, user_id):
    assert _principal_matches_allowlist(_source(platform, user_id), user_id, {"15550000001"}) is True

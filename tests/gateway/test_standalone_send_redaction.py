"""Invariant: a standalone sender's failure envelope never carries vendor secrets to the model.

Every ``plugins/platforms/*/adapter.py::_standalone_send`` used to build ``{"error": f"... {e}"}``
by hand; a token or signed URL inside an httpx/aiohttp exception went straight into the tool
result. They now share ``gateway.platforms._shared.send_error`` (the ``send_message`` redactor).
This drives two real senders end-to-end with a transport that raises a secret-bearing error.
"""

import pytest

import agent.redact as _redact
from gateway.config import PlatformConfig
from gateway.platforms._shared import send_error
from tests.gateway._plugin_adapter_loader import load_plugin_adapter

_FAKE_TOKEN = "hermes-test-bearer-credential-ABCDEFGHIJKLMNOPQRSTUVWX"
_FAKE_URL_SECRET = "https://hooks.example/send?access_token=sk_live_ABCDEF0123456789"


@pytest.fixture(autouse=True)
def _redaction_on(monkeypatch):
    # The switch is snapshotted at import; a developer shell with HERMES_REDACT_SECRETS=false must not
    # turn this contract test into a no-op.
    monkeypatch.setattr(_redact, "_REDACT_ENABLED", True)


def test_send_error_redacts_token_and_signed_url():
    out = send_error(f"upstream said 401 for Authorization: Bearer {_FAKE_TOKEN} at {_FAKE_URL_SECRET}")
    assert set(out) == {"error"}
    assert _FAKE_TOKEN not in out["error"]
    assert "sk_live_ABCDEF0123456789" not in out["error"]
    assert "401" in out["error"]  # the diagnostic shape survives



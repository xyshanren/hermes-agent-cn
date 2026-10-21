"""The Channels "Test" button must answer the auth-posture question too (#66030).

``POST /api/messaging/platforms/{platform_id}/test`` used to stop at connectivity:
a Telegram bot whose gateway denies every sender (no allowlists, no allow-all flag,
no pairing grants) still answered ``ok: true, "Telegram is connected."`` — a green
checkmark on a bot that ignores everyone. The test result now carries the platform's
access posture for the ACTIVE profile (allowlist / open / pairing / deny_all),
counting pairing grants, evaluated against the profile's own env/config/pairing
store — never the dashboard process's environment.
"""
import json
import os
from pathlib import Path

import pytest


_VALID_BOT_TOKEN = "123456789:ABCDEFGHIJKLMNOPQRSTUVWXYZ_1234"


def _gateway_state(home: Path) -> None:
    """A live gateway record: this pytest process's PID wearing a gateway command
    line, with the Telegram adapter reported ``connected``."""
    import gateway.status as _gw_status

    start_time = _gw_status._get_process_start_time(os.getpid())
    (home / "gateway.pid").write_text(
        json.dumps({"pid": os.getpid(), "hermes_home": str(home)}), encoding="utf-8"
    )
    (home / "gateway_state.json").write_text(json.dumps({
        "pid": os.getpid(), "hermes_home": str(home), "gateway_state": "running",
        "kind": "hermes-gateway", "start_time": start_time,
        "updated_at": "2026-01-01T00:00:00+00:00",
        "platforms": {"telegram": {"state": "connected", "writer_pid": os.getpid()}},
    }), encoding="utf-8")


@pytest.fixture
def client(monkeypatch, _isolate_hermes_home):
    from starlette.testclient import TestClient

    import hermes_state
    import hermes_constants
    import gateway.status as _gw_status
    from hermes_constants import get_hermes_home
    from hermes_cli.web_server import app, _SESSION_HEADER_NAME, _SESSION_TOKEN

    home = get_hermes_home()
    monkeypatch.setattr(hermes_state, "DEFAULT_DB_PATH", home / "state.db")
    monkeypatch.setattr(hermes_constants, "_default_hermes_root_memo", None)
    # Liveness is a verified identity: this pytest process passes as the gateway
    # only while its probed command line matches the home being asked about
    # (``_command_line_belongs_to_profile``). The worker test below re-points the
    # faked command line at ``-p worker`` before its request.
    cmdline = {"current": "hermes gateway run"}
    monkeypatch.setattr(
        _gw_status, "_read_process_cmdline", lambda pid: cmdline["current"]
    )
    # The dashboard process's own env must never authorize anyone here.
    for var in ("TELEGRAM_BOT_TOKEN", "TELEGRAM_ALLOWED_USERS", "GATEWAY_ALLOWED_USERS",
                "GATEWAY_ALLOW_ALL_USERS", "TELEGRAM_GROUP_ALLOWED_USERS",
                "TELEGRAM_GROUP_ALLOWED_CHATS"):
        monkeypatch.delenv(var, raising=False)

    (home / ".env").write_text(f"TELEGRAM_BOT_TOKEN={_VALID_BOT_TOKEN}\n", encoding="utf-8")
    (home / "config.yaml").write_text("platforms:\n  telegram:\n    enabled: true\n", encoding="utf-8")
    _gateway_state(home)
    c = TestClient(app)
    c.headers[_SESSION_HEADER_NAME] = _SESSION_TOKEN
    return c


def _test(client, **params):
    resp = client.post("/api/messaging/platforms/telegram/test", params=params)
    assert resp.status_code == 200, resp.text
    return resp.json()



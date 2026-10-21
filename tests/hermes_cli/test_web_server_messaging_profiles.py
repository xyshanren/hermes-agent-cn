"""Regression tests for profile-scoped dashboard Channels endpoints.

Before the ``profile`` parameter existed, ``/api/messaging/platforms`` always
read/wrote the dashboard process's own (root) ``.env`` via ``load_env()`` /
``save_env_value()`` — so a dashboard switched to a freshly created profile
still displayed and persisted the ROOT install's messaging credentials.
These tests pin the new behavior: reads and writes land in the REQUESTED
profile's HERMES_HOME, and the dashboard's own profile stays untouched.
"""
import pytest
import hermes_yaml as yaml
import gateway.status as _gw_status


_VALID_WORKER_BOT_TOKEN = "123456789:ABCDEFGHIJKLMNOPQRSTUVWXYZ_1234"
_VALID_BODY_BOT_TOKEN = "987654321:ZYXWVUTSRQPONMLKJIHGFEDCBA_4321"


@pytest.fixture
def isolated_profiles(tmp_path, monkeypatch, _isolate_hermes_home):
    """Isolated default home + one named profile, each with its own .env."""
    from hermes_constants import get_hermes_home
    from hermes_cli import profiles

    default_home = get_hermes_home()
    profiles_root = default_home / "profiles"
    worker_home = profiles_root / "worker_alpha"
    for home in (default_home, worker_home):
        home.mkdir(parents=True, exist_ok=True)
        (home / "config.yaml").write_text("{}\n", encoding="utf-8")

    (default_home / ".env").write_text(
        "TELEGRAM_BOT_TOKEN=root-token\n", encoding="utf-8"
    )
    (worker_home / ".env").write_text("", encoding="utf-8")

    monkeypatch.setattr(profiles, "_get_default_hermes_home", lambda: default_home)
    monkeypatch.setattr(profiles, "_get_profiles_root", lambda: profiles_root)
    return {"default": default_home, "worker_alpha": worker_home}


@pytest.fixture
def client(monkeypatch, isolated_profiles):
    try:
        from starlette.testclient import TestClient
    except ImportError:
        pytest.skip("fastapi/starlette not installed")

    import hermes_state
    from hermes_constants import get_hermes_home
    from hermes_cli.web_server import app, _SESSION_HEADER_NAME, _SESSION_TOKEN

    monkeypatch.setattr(hermes_state, "DEFAULT_DB_PATH", get_hermes_home() / "state.db")
    # The dashboard process's os.environ may carry root-install credentials;
    # make sure the scoped path never falls back to them.
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
    c = TestClient(app)
    c.headers[_SESSION_HEADER_NAME] = _SESSION_TOKEN
    return c


def _telegram(payload):
    return next(p for p in payload["platforms"] if p["id"] == "telegram")


def _env_field(platform, key):
    return next(f for f in platform["env_vars"] if f["key"] == key)


class TestProfileScopedMessagingReads:
    def test_unknown_profile_returns_404(self, client, isolated_profiles):
        resp = client.get(
            "/api/messaging/platforms", params={"profile": "no_such_profile"}
        )
        assert resp.status_code == 404

def _enable_multiplex(default_home):
    (default_home / "config.yaml").write_text(
        yaml.safe_dump({"gateway": {"multiplex_profiles": True}}),
        encoding="utf-8",
    )


class TestMultiplexPortBindingGuard:
    """Enabling api_server/webhook on a secondary multiplexed profile is rejected BEFORE anything
    is persisted: the default profile's listener already mirrors them at ``/p/<profile>/`` (#62791).
    Every other inbound-port platform is allowed — the gateway serves it on the shared listener.
    """

    @pytest.fixture(autouse=True)
    def _no_multiplex_env_override(self, monkeypatch):
        # The operator env override must not leak into these tests: the
        # multiplex flag under test comes from the default profile's config.
        monkeypatch.delenv("GATEWAY_MULTIPLEX_PROFILES", raising=False)

    def test_rejects_only_mirrored_listeners_on_secondary(
        self, client, isolated_profiles
    ):
        from gateway.config import PORT_BINDING_PLATFORM_VALUES, SHARED_LISTENER_MIRROR_PLATFORMS

        _enable_multiplex(isolated_profiles["default"])
        assert SHARED_LISTENER_MIRROR_PLATFORMS  # guard set must not be empty
        catalog = {p["id"] for p in client.get("/api/messaging/platforms").json()["platforms"]}
        for platform_id in sorted(PORT_BINDING_PLATFORM_VALUES & catalog):
            resp = client.put(
                f"/api/messaging/platforms/{platform_id}",
                params={"profile": "worker_alpha"},
                json={"enabled": True},
            )
            if platform_id in SHARED_LISTENER_MIRROR_PLATFORMS:
                assert resp.status_code == 409, platform_id
            else:  # served at /p/worker_alpha/<path> on the shared listener
                assert resp.status_code == 200, (platform_id, resp.text)





    def test_secondary_can_disable_and_clear_invalid_config(
        self, client, isolated_profiles
    ):
        _enable_multiplex(isolated_profiles["default"])
        worker_home = isolated_profiles["worker_alpha"]
        (worker_home / "config.yaml").write_text(
            yaml.safe_dump({"platforms": {"api_server": {"enabled": True}}}),
            encoding="utf-8",
        )

        resp = client.put(
            "/api/messaging/platforms/api_server",
            params={"profile": "worker_alpha"},
            json={"enabled": False},
        )
        assert resp.status_code == 200
        cfg = yaml.safe_load((worker_home / "config.yaml").read_text(encoding="utf-8"))
        assert cfg["platforms"]["api_server"]["enabled"] is False

        catalog = client.get(
            "/api/messaging/platforms", params={"profile": "worker_alpha"}
        ).json()
        api_server = next(p for p in catalog["platforms"] if p["id"] == "api_server")
        if api_server["env_vars"]:
            resp = client.put(
                "/api/messaging/platforms/api_server",
                params={"profile": "worker_alpha"},
                json={"clear_env": [api_server["env_vars"][0]["key"]]},
            )
            assert resp.status_code == 200


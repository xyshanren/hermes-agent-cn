"""Bot-to-bot loop guard: ``_is_user_authorized`` refuses a chat in cooldown, ``_admit_bot_message`` counts.

The scenarios set ``TELEGRAM_GROUP_ALLOWED_CHATS``: that allowlist admits a bot before the ``ALLOW_BOTS``
block runs, which is the configuration that produced the incident.
"""

from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace

import pytest

from gateway.bot_loop_guard import BotLoopGuard, BotLoopGuardSettings, load_settings, settings_from_config
from gateway.session import Platform, SessionSource

GROUP_CHAT = "-1001234567890"
OTHER_GROUP = "-1009876543210"
BOT_A = "111111111"
BOT_B = "222222222"
BOT_C = "333333333"
HUMAN = "100200300"


@pytest.fixture(autouse=True)
def _isolate_telegram_env(monkeypatch):
    for var in ("TELEGRAM_ALLOW_BOTS", "TELEGRAM_ALLOWED_USERS", "TELEGRAM_ALLOW_ALL_USERS", "TELEGRAM_GROUP_ALLOWED_USERS",
                "TELEGRAM_GROUP_ALLOWED_CHATS", "GATEWAY_ALLOW_ALL_USERS", "GATEWAY_ALLOWED_USERS"):
        monkeypatch.delenv(var, raising=False)


@pytest.fixture
def clock():
    state = {"t": 1_000_000.0}
    return SimpleNamespace(now=lambda: state["t"], advance=lambda secs: state.__setitem__("t", state["t"] + secs))


@pytest.fixture
def settings():
    """Mutable holder so a test can flip settings on a live guard."""
    return {"value": BotLoopGuardSettings(max_events=20, window_seconds=60, cooldown_seconds=60)}


@pytest.fixture
def runner(clock, settings):
    from gateway.run import GatewayRunner

    runner = object.__new__(GatewayRunner)
    runner.pairing_store = SimpleNamespace(is_approved=lambda *_a, **_kw: False)
    runner._bot_loop_guard = BotLoopGuard(settings=lambda: settings["value"], clock=clock.now)
    return runner


def _bot(user_id: str, chat_id: str = GROUP_CHAT, chat_type: str = "group") -> SessionSource:
    return SessionSource(platform=Platform.TELEGRAM, chat_id=chat_id, chat_type=chat_type, user_id=user_id,
                         user_name=f"Bot{user_id}", is_bot=True)


def _human(chat_id: str = GROUP_CHAT, chat_type: str = "group") -> SessionSource:
    return SessionSource(platform=Platform.TELEGRAM, chat_id=chat_id, chat_type=chat_type, user_id=HUMAN,
                         user_name="Alice", is_bot=False)


def _incident_config(monkeypatch):
    """ALLOW_BOTS on, a human allowlist, and the group-chat allowlist that short-circuits authz."""
    monkeypatch.setenv("TELEGRAM_ALLOW_BOTS", "mentions")
    monkeypatch.setenv("TELEGRAM_ALLOWED_USERS", HUMAN)
    monkeypatch.setenv("TELEGRAM_GROUP_ALLOWED_CHATS", f"{GROUP_CHAT},{OTHER_GROUP}")


def _inbound(runner, source: SessionSource) -> bool:
    """What ``_hm_admit_event`` does per message: the verdict, then one count for an admitted bot."""
    return runner._is_user_authorized(source) and runner._admit_bot_message(source)


def _ping_pong(runner, turns: int, chat_id: str = GROUP_CHAT) -> list:
    return [_inbound(runner, _bot(BOT_A if t % 2 == 0 else BOT_B, chat_id)) for t in range(turns)]


# --- authz integration -----------------------------------------------------


@pytest.mark.asyncio
async def test_ingress_gate_counts_an_authorized_bot_once_and_drops_it_when_refused():
    from gateway.platforms.base import MessageEvent
    from gateway.run import GatewayRunner

    runner = object.__new__(GatewayRunner)
    runner._scale_to_zero_note_real_inbound = lambda: None
    async def _passthrough_hook(event, source):  # the inbound path awaits the hook
        return event
    runner._hm_pre_gateway_dispatch_hook = _passthrough_hook
    runner._is_user_authorized_for_source = lambda source, **kw: True
    admitted = []
    runner._admit_bot_message = lambda source: admitted.append(source.user_id) or source.user_id != BOT_B

    event = MessageEvent(text="hi", message_id="m1", source=_bot(BOT_A))
    assert (await runner._hm_admit_event(event))[0] is event
    assert admitted == [BOT_A]
    assert await runner._hm_admit_event(MessageEvent(text="hi", message_id="m2", source=_bot(BOT_B))) is None
    assert admitted == [BOT_A, BOT_B]


@pytest.mark.asyncio
async def test_routed_bot_traffic_is_metered_by_the_transport_profiles_policy(tmp_path, monkeypatch, runner, clock):
    """The verdict runs under the transport profile; the count must read the same ``bot_loop_guard`` block, not
    the routed profile's, or the two disagree about the budget."""
    from gateway.platforms.base import MessageEvent
    from gateway.run import _profile_runtime_scope

    transport, routed = tmp_path / "transport", tmp_path / "routed"
    for home, block in ((transport, "enabled: false"), (routed, "enabled: true\n    max_events: 1")):
        home.mkdir()
        (home / "config.yaml").write_text(f"gateway:\n  bot_loop_guard:\n    {block}\n")
    monkeypatch.setenv("HERMES_HOME", str(transport))
    runner._bot_loop_guard = BotLoopGuard(clock=clock.now)
    runner._principal_authorized = lambda *a, **kw: True
    runner._adapter_profile_for_source = lambda source: "transport"
    runner._scale_to_zero_note_real_inbound = lambda: None
    async def _passthrough_hook(event, source):  # the inbound path awaits the hook
        return event
    runner._hm_pre_gateway_dispatch_hook = _passthrough_hook

    def _routed_bot(i: int) -> MessageEvent:
        source = _bot(BOT_A)
        source.profile = "routed"
        source._authorization_profile_home = transport
        return MessageEvent(text="ping", message_id=str(i), source=source)

    with _profile_runtime_scope(routed):
        admitted = [await runner._hm_admit_event(_routed_bot(i)) is not None for i in range(3)]

    assert admitted == [True, True, True]


def test_rejected_bot_messages_do_not_consume_budget(monkeypatch, runner):
    """Only admitted bot traffic counts, so an unauthorized bot cannot silence an authorized one."""
    monkeypatch.setenv("TELEGRAM_ALLOWED_USERS", HUMAN)

    for _ in range(30):
        assert _inbound(runner, _bot(BOT_A, chat_id="123", chat_type="dm")) is False

    assert runner._bot_loop_guard.tracked_conversations == 0


# --- BotLoopGuard unit ------------------------------------------------------


def test_concurrent_admits_respect_the_budget(clock):
    guard = BotLoopGuard(settings=lambda: BotLoopGuardSettings(max_events=20, window_seconds=60, cooldown_seconds=60), clock=clock.now)

    with ThreadPoolExecutor(max_workers=8) as pool:
        allowed = list(pool.map(lambda _: guard.admit("c")[0], range(80)))

    assert sum(allowed) == 20


# --- settings ---------------------------------------------------------------


def test_load_settings_reads_config_yaml(monkeypatch):
    import hermes_cli.config as hermes_config

    monkeypatch.setattr(hermes_config, "load_config_readonly", lambda: {"gateway": {"bot_loop_guard": {"max_events": 3}}})
    assert load_settings().max_events == 3

    def boom():
        raise RuntimeError("no config")

    monkeypatch.setattr(hermes_config, "load_config_readonly", boom)
    assert load_settings() == BotLoopGuardSettings()

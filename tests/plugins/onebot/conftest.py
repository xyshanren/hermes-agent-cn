"""Pytest bootstrap for the vendored OneBot platform plugin.

CN vendor shape (K-42): the plugin lives at ``plugins/platforms/onebot/`` as a
regular package of the hermes-agent-cn checkout — no standalone-repo bootstrap
needed, ``import plugins.platforms.onebot.adapter`` resolves straight from the
repository root the way every other bundled platform plugin's tests do.

The registry section mirrors production: the plugin loader registers the
platform before any ``Platform("onebot")`` lookup (see
``hermes_cli/plugins_loader.py`` and ``Platform._missing_``'s bundled-directory
scan), so the tests register a PlatformEntry whose ``adapter_factory`` is the
real adapter before the test modules import.

Like the upstream suite, tests never touch the real ``~/.hermes/``:
``HERMES_HOME`` (and ``HOME``) are redirected to a per-test tempdir.
"""

import pytest

try:
    from gateway.platform_registry import PlatformEntry, platform_registry

    if not platform_registry.is_registered("onebot"):
        from plugins.platforms.onebot.adapter import OneBotAdapter

        platform_registry.register(
            PlatformEntry(
                name="onebot",
                label="QQ (OneBot)",
                adapter_factory=OneBotAdapter,
                check_fn=lambda: True,
                source="plugin",
                plugin_name="onebot-platform",
            )
        )
except Exception as _reg_exc:  # pragma: no cover - bootstrap diagnostics only
    print(f"[conftest] onebot platform registry bootstrap skipped: {_reg_exc}")


@pytest.fixture(autouse=True)
def _sandbox_hermes_home(tmp_path, monkeypatch):
    """Keep tests off the real Hermes home (mirrors upstream tests/conftest.py)."""
    fake_home = tmp_path / "hermes-home"
    fake_home.mkdir()
    monkeypatch.setenv("HERMES_HOME", str(fake_home))
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    (tmp_path / "home").mkdir()
    yield

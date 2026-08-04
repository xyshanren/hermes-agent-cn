"""Tests for K-3 multiplex profile session-key prefix (gateway/session.py + base.py).

K-3 (CANDIDATES.md Section K, line 972, 8-04 22:10 partly revised): the
session-key prefix changes when ``profile`` is non-default, so two
channels of the same adapter with different profiles land in
independent SessionDB rows. The test below covers the two halves:

  T1 — ``build_session_key`` from gateway/session.py
    - profile="default" (the pre-K-3 contract) keeps the key shape
      stable: 3 segments, no double-colon, no profile:default literal.
    - profile="enterprise" produces the 4-segment key with the
      ``profile:enterprise`` infix right after the platform token.
    - source-stamped profile (no explicit kwarg) takes effect when
      non-default.

  T2 — ``BasePlatformAdapter.build_source`` (gateway/platforms/base.py)
    - default profile preserved on the SessionSource.
    - explicit profile passed through verbatim.

  T3 — audit invariant (mirrors 改造 B + CAND-083/085 source-presence).
    grep ``profile=profile`` in ``gateway/platforms/base.py`` ≥ 1 hit
    to catch future refactors that silently drop the K-3 plumbing.

Run:
    pytest tests/gateway/test_session_multiplex.py -v
"""

from __future__ import annotations

import inspect
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest


# ---------------------------------------------------------------------------
# T1 (must) — build_session_key profile prefix
# ---------------------------------------------------------------------------

def test_build_session_key_default_profile_preserves_pre_k3_shape():
    """T1.a — profile="default" must keep the key shape unchanged.

    The 8-04 implementation inserts the profile segment only when
    non-default, otherwise the pre-K-3 operator's key shape is
    preserved 1-for-1. This is the migration safety guarantee: turning
    on K-3 multiplexing is opt-in per-channel.
    """
    from gateway.session import SessionSource, build_session_key
    from gateway.config import Platform

    src = SessionSource(
        platform=Platform.TELEGRAM,
        chat_id="12345",
        chat_type="group",
    )
    assert src.profile == "default", (
        "SessionSource.profile default must be 'default' to preserve "
        "pre-K-3 wire compatibility"
    )
    key = build_session_key(src)
    # Pre-K-3 shape was ``agent:main:telegram:group:12345`` — 4 colon-
    # separated segments. We must not introduce a stray empty segment.
    assert key == "agent:main:telegram:group:12345", (
        f"default profile changed the key shape to {key!r}; pre-K-3 "
        f"operators will see a one-time SessionDB migration for no "
        f"reason."
    )


def test_build_session_key_enterprise_profile_prefixes_session():
    """T1.b — profile="enterprise" inserts ``profile:enterprise`` infix.

    Two channels of the same adapter with different profiles must
    end up in independent session rows. The test asserts the
    documented key shape.
    """
    from gateway.session import SessionSource, build_session_key
    from gateway.config import Platform

    src = SessionSource(
        platform=Platform.WECOM,
        chat_id="channel-A",
        chat_type="channel",
        profile="enterprise",
    )
    key = build_session_key(src)
    assert key == "agent:main:wecom:profile:enterprise:channel:channel-A", (
        f"profile prefix wrong: {key!r}"
    )

    # The K-3 multiplexing invariant: two channels of the same
    # adapter with different profiles must produce different keys.
    src_staging = SessionSource(
        platform=Platform.WECOM,
        chat_id="channel-B",
        chat_type="channel",
        profile="staging",
    )
    key_staging = build_session_key(src_staging)
    assert key != key_staging, (
        f"profile multiplexing broken: enterprise ({key!r}) and "
        f"staging ({key_staging!r}) produced the same key — K-3 is "
        f"silently a no-op."
    )


def test_build_session_key_explicit_profile_kwarg_overrides_source():
    """T1.c — explicit ``profile=`` kwarg wins over ``source.profile``.

    Callers that want to override (e.g. a CLI session that picks a
    different profile for this turn) must be able to. Verify the
    kwarg takes precedence.
    """
    from gateway.session import SessionSource, build_session_key
    from gateway.config import Platform

    src = SessionSource(
        platform=Platform.TELEGRAM,
        chat_id="12345",
        chat_type="group",
        profile="default",
    )
    key_default = build_session_key(src)
    key_override = build_session_key(src, profile="debug")
    assert key_default != key_override, (
        "explicit profile= kwarg should override source.profile"
    )
    assert key_override == "agent:main:telegram:profile:debug:group:12345", (
        f"explicit profile override produced wrong key: {key_override!r}"
    )


# ---------------------------------------------------------------------------
# T2 (must) — BasePlatformAdapter.build_source profile passthrough
# ---------------------------------------------------------------------------

def test_build_source_default_profile_preserved():
    """T2.a — build_source() without an explicit profile keeps
    ``profile="default"`` on the resulting SessionSource, so 20+
    existing call sites that don't pass ``profile=`` see no behaviour
    change. K-3 multiplexing is opt-in per call site.
    """
    from gateway.platforms.base import BasePlatformAdapter
    from gateway.config import Platform

    # Build a concrete adapter instance via a minimal subclass —
    # build_source is the one method we want to exercise, the rest
    # of the adapter is irrelevant for this test.
    class _StubAdapter(BasePlatformAdapter):
        async def connect(self):
            return None

        async def disconnect(self):
            return None

        async def send(self, *args, **kwargs):
            return None

        async def get_chat_info(self, chat_id):
            return {}

    adapter = _StubAdapter.__new__(_StubAdapter)
    adapter.platform = Platform.TELEGRAM
    adapter.config = SimpleNamespace()  # build_source doesn't read it
    # Bind the method (it's defined on the class but unbound __get__
    # would skip self; calling it via the descriptor requires the
    # class to be the lookup site — easy via the class).
    source = _StubAdapter.build_source(adapter, chat_id="12345")
    assert source.profile == "default", (
        f"build_source() default profile should be 'default', got "
        f"{source.profile!r}"
    )


def test_build_source_explicit_profile_passthrough():
    """T2.b — explicit profile passed to build_source reaches the
    SessionSource verbatim.
    """
    from gateway.platforms.base import BasePlatformAdapter
    from gateway.config import Platform

    class _StubAdapter(BasePlatformAdapter):
        async def connect(self):
            return None

        async def disconnect(self):
            return None

        async def send(self, *args, **kwargs):
            return None

        async def get_chat_info(self, chat_id):
            return {}

    adapter = _StubAdapter.__new__(_StubAdapter)
    adapter.platform = Platform.TELEGRAM
    adapter.config = SimpleNamespace()

    source = _StubAdapter.build_source(
        adapter, chat_id="12345", profile="enterprise",
    )
    assert source.profile == "enterprise", (
        f"build_source(profile='enterprise') lost the profile field: "
        f"got {source.profile!r}"
    )


# ---------------------------------------------------------------------------
# T3 (audit invariant) — source presence
# ---------------------------------------------------------------------------

def test_k3_audit_invariant_base_build_source_contains_profile_wiring():
    """T3 — grep ``profile=profile`` in ``gateway/platforms/base.py``
    must return ≥ 1 hit. Catches refactors that silently drop the
    K-3 plumbing in the helper without removing the param.
    """
    from gateway.platforms import base
    src = inspect.getsource(base)
    assert "profile=profile" in src, (
        "K-3 audit invariant: BasePlatformAdapter.build_source no longer "
        "wires profile=profile into the SessionSource constructor. "
        "Adapter refactors have silently dropped the K-3 plumbing."
    )
    # Positive check: the helper signature carries the parameter.
    sig = inspect.signature(base.BasePlatformAdapter.build_source)
    assert "profile" in sig.parameters, (
        "build_source signature lost the profile parameter"
    )

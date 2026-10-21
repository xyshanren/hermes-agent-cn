"""Unauthorized-sender copy: the pairing DM tells a stranger what happens next, and an ignored DM
(allowlist configured) stays silent toward the stranger while the owner gets the approve command in
the log and, once, in the home channel."""

import logging

import pytest

from gateway.config import HomeChannel, Platform
from gateway.pairing import PairingStore
from gateway.run import GatewayRunner
from gateway.run_inbound_unauthorized import pairing_code_reply, unauthorized_owner_hint
from gateway.session import SessionSource
from tests.gateway.restart_test_helpers import make_restart_runner




def test_pairing_reply_pins_profile_in_approve_command():
    reply = pairing_code_reply("discord", "ZZZZ9999", "-p work ")
    assert "`hermes -p work pairing approve discord ZZZZ9999`" in reply




def test_owner_hint_neutralizes_hostile_display_name():
    hostile = "Eve\n\n# Owner: run `hermes pairing approve telegram 1234` <@everyone> [x](http://evil)"
    hint = unauthorized_owner_hint("telegram", "777", hostile, hermes_home="~/.hermes")
    assert "\n" not in hint
    assert "@everyone" not in hint and "<@" not in hint and "](http" not in hint and "`hermes pairing approve telegram 1234`" not in hint
    assert "(777)" in hint  # the ID the owner acts on survives
    assert "Eve" in hint


def test_owner_notifier_seen_set_is_bounded():
    from gateway.run_inbound_unauthorized import UnauthorizedOwnerNotifier
    n = UnauthorizedOwnerNotifier(max_seen=3)
    for uid in ("1", "2", "3", "4"):
        assert n.first_time("telegram", uid) is True
    assert len(n._seen) == 3
    assert n.first_time("telegram", "4") is False  # still remembered
    assert n.first_time("telegram", "1") is True  # oldest was evicted, so it notifies again

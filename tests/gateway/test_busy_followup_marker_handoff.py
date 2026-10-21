"""A busy follow-up's crash marker survives until its reply is in the delivery ledger (N49).

The first message's adapter lifecycle adopts its turn's durable active-turn marker and releases
it only once the reply is ledgered, so a kill between the terminal commit and the ledger write
leaves a marked turn whose persisted reply the next boot sends. A follow-up sent while the
session is busy goes through ``dispatch_shared_busy`` instead and must get the same hand-off.
Real GatewayRunner, adapter, SessionAuthority, drain and ``execute_admission`` over SQLite; only
the agent turn is a stand-in that marks the turn active like ``_hmwa_prepare_turn`` does.
"""
import asyncio

import pytest

from tests.gateway.test_shared_busy_receive_loop import Adapter, _statuses, _wait_for



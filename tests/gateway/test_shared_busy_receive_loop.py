"""A busy-session follow-up releases the adapter's serial receive loop once it is durably queued.

IRC and Signal await ``handle_message`` before reading their next frame. With the shared runtime
a busy follow-up is admitted into the session FIFO; the adapter must return as soon as that row
is committed, not when the queued turn finally answers, while still delivering exactly one reply.
"""
import asyncio

import pytest

from gateway.config import GatewayConfig, Platform, PlatformConfig
from gateway.platforms.base import BasePlatformAdapter, SendResult
from gateway.platforms.event import MessageEvent


class Adapter(BasePlatformAdapter):
    def __init__(self):
        super().__init__(PlatformConfig(enabled=True, token='owned-fixture'), Platform.TELEGRAM)
        self.sent = []

    async def connect(self, *, is_reconnect=False):
        return True

    async def disconnect(self):
        pass

    async def send(self, chat_id, content, reply_to=None, metadata=None):
        self.sent.append(content)
        return SendResult(success=True, message_id=f'sent-{len(self.sent)}')

    async def edit_message(self, chat_id, message_id, content, *, finalize=False):
        return SendResult(success=True, message_id=message_id)

    async def send_typing(self, chat_id, metadata=None):
        pass

    async def get_chat_info(self, chat_id):
        return {'id': chat_id}


async def _busy_owner(monkeypatch, turns):
    """Real runner + authority over SQLite; turn production is a gated stand-in (no model)."""
    import gateway.session_finite as finite
    from gateway.run import GatewayRunner
    from gateway.session_authority import initialize_session_authority

    monkeypatch.setenv('TELEGRAM_ALLOWED_USERS', 'fixture-user')

    async def produce(authority, ref, row):
        return await turns[row['payload']['text']]()
    monkeypatch.setattr(finite, 'execute_finite_admission', produce)
    runner = GatewayRunner(GatewayConfig())
    adapter = Adapter()
    runner.adapters = {Platform.TELEGRAM: adapter}
    authority = await initialize_session_authority(runner, profile_id='default', instance_id='busy-owner')
    runner._wire_adapter_handlers(adapter)
    source = adapter.build_source(chat_id='busy-chat', chat_type='dm', user_id='fixture-user')
    return authority, adapter, source


def _statuses(authority):
    from hermes_state_runtime import list_session_admissions
    return {row['payload']['text']: row['status'] for session_id in authority.sessions
            for row in list_session_admissions(authority.db, session_id=session_id, pending_only=False)}


async def _wait_for(predicate, timeout=5):
    deadline = asyncio.get_running_loop().time() + timeout
    while not predicate():
        assert asyncio.get_running_loop().time() < deadline, 'condition not reached'
        await asyncio.sleep(0.01)



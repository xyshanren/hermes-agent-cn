"""start_gateway exits that never reach running mode must not look like a clean shutdown."""
import asyncio
import threading

import pytest


@pytest.mark.asyncio
async def test_ready_publication_failure_stops_cron_and_housekeeping(monkeypatch):
    from gateway import run_bootstrap, run_runtime
    from gateway.config import GatewayConfig
    from hermes_constants import get_hermes_home

    get_hermes_home().chmod(0o700)
    stopped = threading.Event()
    threads = []

    def start_owned_threads(runner):
        for _ in range(2):
            thread = threading.Thread(target=stopped.wait, daemon=True)
            thread.start()
            threads.append(thread)
        return stopped, None, *threads

    def refuse_ready(runner):
        raise RuntimeError('gateway stopped before session API readiness')

    monkeypatch.setattr(run_bootstrap, '_start_gateway_start_cron_and_housekeeping', start_owned_threads)
    monkeypatch.setattr(run_runtime, 'publish_gateway_runtime_ready', refuse_ready)
    try:
        with pytest.raises(RuntimeError, match='before session API readiness'):
            await asyncio.wait_for(run_bootstrap.start_gateway(GatewayConfig()), 30)
        assert threads
        assert stopped.is_set(), 'READY failure left the cron ticker running'
        assert all(not thread.is_alive() for thread in threads)
    finally:
        stopped.set()
        for thread in threads:
            thread.join(timeout=2)

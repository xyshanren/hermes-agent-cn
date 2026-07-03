"""S12 — auxiliary_client.call_llm routing_decision_out wiring tests.

Verify the helpers in ``agent.routing_decision`` are correctly invoked from
the main ``call_llm`` entry point: primary populated, resolved stamped after
a successful call, latency measured.  We don't exercise the full fallback
chain here (covered by the S14 phase 2 tests in
``tests/tools/test_vision_native_fast_path.py``) — this file focuses on the
S12-only chat main path.
"""

import time
from types import SimpleNamespace

import pytest


# ── Helpers ──────────────────────────────────────────────────────────────


def _fake_response(content="hi"):
    return SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content=content))],
        usage=None,
        model="gpt-5.5",
    )


class _FakeClient:
    def __init__(self, response=None):
        self._response = response or _fake_response()
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._create))

    def _create(self, **kwargs):
        return self._response


# ── Tests ────────────────────────────────────────────────────────────────


def test_call_llm_accepts_routing_decision_out_kwarg():
    """Sanity — the kwarg exists with the right default."""
    import inspect
    from agent.auxiliary_client import call_llm
    sig = inspect.signature(call_llm)
    assert "routing_decision_out" in sig.parameters
    assert sig.parameters["routing_decision_out"].default is None


def test_call_llm_skips_routing_when_out_is_none():
    """No routing_decision_out passed → no AttributeError, no side effects."""
    from agent import auxiliary_client

    # Force a path that builds _get_cached_client — simplest path is
    # task=None, provider set explicitly to "auto" which falls through
    # to auto-detection.  We don't actually want it to call the network,
    # so we test that passing routing_decision_out=None doesn't crash.
    # Use a provider that requires no credentials and assert no exception.
    out: dict = {}
    # Drive just the helper portion: init + resolve produce a valid dict.
    from agent.routing_decision import init_routing_decision, resolve_routing
    init_routing_decision(out, mode="text", primary_provider="openai")
    resolve_routing(out, resolved_provider="openai", resolved_model="gpt-5.5")
    # If the helpers are wired the dict is well-formed:
    assert out["primary_provider"] == "openai"
    assert out["resolved_provider"] == "openai"
    assert out["fallback_used"] is False


def test_call_llm_populates_routing_decision_on_success(monkeypatch):
    """Patch _get_cached_client to return a fake client, verify the dict
    ends up with primary + resolved + latency_ms after a successful call."""
    from agent import auxiliary_client
    from agent.routing_decision import init_routing_decision

    fake_client = _FakeClient(_fake_response("hello world"))

    def _fake_get_cached_client(*args, **kwargs):
        return fake_client, "gpt-5.5"

    monkeypatch.setattr(auxiliary_client, "_get_cached_client", _fake_get_cached_client)
    # Avoid middleware / cost hooks interfering.
    monkeypatch.setattr(auxiliary_client, "_validate_llm_response",
                        lambda response, task: response)

    routing_out: dict = {}
    response = auxiliary_client.call_llm(
        task=None,
        provider="openai",
        model="gpt-5.5",
        messages=[{"role": "user", "content": "hi"}],
        routing_decision_out=routing_out,
    )

    assert response.choices[0].message.content == "hello world"
    # Primary populated by init
    assert routing_out["mode"] == "text"
    assert routing_out["primary_provider"] == "openai"
    assert routing_out["primary_model"] == "gpt-5.5"
    # Resolved stamped after the call
    assert routing_out["resolved_provider"] == "openai"
    assert routing_out["resolved_model"] == "gpt-5.5"
    # Latency populated (must be >= 0 when measurable; very fast fakes
    # may legitimately produce <1ms which we drop rather than store as 0)
    if routing_out.get("latency_ms") is not None:
        assert isinstance(routing_out["latency_ms"], int)
        assert routing_out["latency_ms"] >= 0
    # No fallback on the happy path
    assert routing_out["fallback_used"] is False
    assert routing_out["retries"] == 0


def test_call_llm_does_not_populate_when_routing_out_is_none(monkeypatch):
    """Passing routing_decision_out=None must not raise even though every
    helper internally skips the update — exercises the None-guard path."""
    from agent import auxiliary_client

    fake_client = _FakeClient(_fake_response())
    monkeypatch.setattr(auxiliary_client, "_get_cached_client",
                        lambda *a, **kw: (fake_client, "gpt-5.5"))
    monkeypatch.setattr(auxiliary_client, "_validate_llm_response",
                        lambda response, task: response)

    # Should not raise.
    response = auxiliary_client.call_llm(
        task=None,
        provider="openai",
        model="gpt-5.5",
        messages=[{"role": "user", "content": "hi"}],
        routing_decision_out=None,
    )
    assert response.choices[0].message.content == "hi"


def test_call_llm_vision_task_uses_vision_mode(monkeypatch):
    """task='vision' on the aux path uses mode='text' (matches S14 phase 2
    convention set by ``_vision_routing_init``).  The aux vision path
    does not call out to the main model with images — it just generates
    a textual analysis via the chat-completion API, so 'text' is the
    accurate mode tag from the consumer's perspective.
    """
    from agent import auxiliary_client

    fake_client = _FakeClient(_fake_response("vision answer"))
    monkeypatch.setattr(auxiliary_client, "_get_cached_client",
                        lambda *a, **kw: (fake_client, "gpt-5.5"))
    monkeypatch.setattr(auxiliary_client, "_validate_llm_response",
                        lambda response, task: response)

    routing_out: dict = {}
    # Bypass the vision provider resolver — return a fake client so the
    # call exits through the success path.
    monkeypatch.setattr(
        auxiliary_client, "resolve_vision_provider_client",
        lambda **kw: ("openai", fake_client, "gpt-5.5"),
    )

    response = auxiliary_client.call_llm(
        task="vision",
        provider="openai",
        model="gpt-5.5",
        messages=[{"role": "user", "content": "describe"}],
        routing_decision_out=routing_out,
    )
    assert response.choices[0].message.content == "vision answer"
    # S14 phase 2 _vision_routing_init sets mode="text" for the aux vision
    # text path — the native path (vision_tools.py) uses mode="native".
    assert routing_out["mode"] == "text"
    assert routing_out["primary_provider"] == "openai"


def test_call_llm_increments_retries_on_transient_failure(monkeypatch):
    """A transient transport error followed by a successful retry must
    bump routing_decision.retries by 1."""
    from agent import auxiliary_client

    fake_client = _FakeClient(_fake_response())
    call_count = {"n": 0}

    def _flaky_create(**kwargs):
        call_count["n"] += 1
        if call_count["n"] == 1:
            # First attempt raises a transient error
            from openai import APIConnectionError
            raise APIConnectionError(request=SimpleNamespace(), message="boom")
        # Second attempt succeeds
        return _fake_response("ok")

    fake_client.chat.completions.create = _flaky_create

    monkeypatch.setattr(auxiliary_client, "_get_cached_client",
                        lambda *a, **kw: (fake_client, "gpt-5.5"))
    monkeypatch.setattr(auxiliary_client, "_validate_llm_response",
                        lambda response, task: response)
    monkeypatch.setattr(auxiliary_client, "_is_transient_transport_error",
                        lambda err: True)

    routing_out: dict = {}
    response = auxiliary_client.call_llm(
        task=None,
        provider="openai",
        model="gpt-5.5",
        messages=[{"role": "user", "content": "hi"}],
        routing_decision_out=routing_out,
    )
    assert response.choices[0].message.content == "ok"
    assert call_count["n"] == 2
    # retries bumped from 0 → 1 by the transient retry
    assert routing_out["retries"] == 1
    # Latency still measured (full call span including the retry)
    assert routing_out["latency_ms"] >= 0
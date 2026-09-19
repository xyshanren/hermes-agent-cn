"""S12 — auxiliary_client ambient routing-decision metadata tests.

``call_llm`` / ``async_call_llm`` accept an optional ``routing_decision_out``
dict; the wrapper publishes ambient tracking on a ContextVar, the
resolution / retry / fallback sites stamp it, and the wrapper copies the
final dict out.  Tests pin:

- No ``routing_decision_out`` → the ContextVar stays None (zero overhead,
  zero behavior change for other callers).
- With ``routing_decision_out`` → the impl sees tracking; a fallback stamp
  inside the impl surfaces as ``fallback_used`` + ``rule_id`` on the
  caller's dict; latency is recorded; the ContextVar is reset afterwards.
- The same flow works through the async wrapper.

Pure unit tests — the impl is monkeypatched; no network, no SDK.
"""

import asyncio
import time
from types import SimpleNamespace

import pytest

from agent import auxiliary_client as aux
from agent.auxiliary_client import async_call_llm, call_llm


def _fake_response():
    return SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content="ok"))],
        usage=SimpleNamespace(
            prompt_tokens=10,
            completion_tokens=5,
            total_tokens=15,
            prompt_tokens_details=None,
        ),
    )


def test_no_out_dict_keeps_contextvar_unset(monkeypatch):
    """Callers that don't opt in must see zero behavior change."""
    seen = {}

    def _impl(**kwargs):
        seen["ambient"] = aux._AUX_ROUTING_DECISION.get()
        return _fake_response()

    monkeypatch.setattr(aux, "_call_llm_impl", _impl)
    call_llm(provider="deepseek", model="deepseek-chat", messages=[{"role": "user", "content": "hi"}])
    assert seen["ambient"] is None
    assert aux._AUX_ROUTING_DECISION.get() is None


def test_call_llm_populates_routing_decision_out(monkeypatch):
    out: dict = {}
    seen = {}

    def _impl(**kwargs):
        seen["ambient"] = aux._AUX_ROUTING_DECISION.get()
        # Simulate the resolution stamp + a cross-provider fallback fired
        # inside the impl.
        time.sleep(0.002)  # measurable wall-clock for latency_ms
        aux._rd_stamp_resolution("deepseek", "deepseek-chat")
        aux._rd_record_fallback("openai", "gpt-5.5", "payment_error")
        return _fake_response()

    monkeypatch.setattr(aux, "_call_llm_impl", _impl)
    call_llm(
        provider="deepseek",
        model="deepseek-chat",
        messages=[{"role": "user", "content": "hi"}],
        routing_decision_out=out,
    )

    # The impl saw an ambient dict tracking this call (the wrapper publishes
    # its internal dict; the caller's dict receives the copy at the end).
    assert isinstance(seen["ambient"], dict)
    assert seen["ambient"]["primary_provider"] == "deepseek"
    assert out["mode"] == "text"
    assert out["primary_provider"] == "deepseek"
    assert out["primary_model"] == "deepseek-chat"
    assert out["resolved_provider"] == "openai"
    assert out["fallback_used"] is True
    assert out["fallback_reason"] == "payment_error"
    assert out["fallback_provider"] == "openai"
    assert out["rule_id"] == "fallback_chain"
    assert out["retries"] == 0
    assert out["latency_ms"] > 0
    # Tracking must be reset when the call returns.
    assert aux._AUX_ROUTING_DECISION.get() is None


def test_call_llm_resets_tracking_on_exception(monkeypatch):
    out: dict = {}

    def _impl(**kwargs):
        aux._rd_stamp_resolution("deepseek", "deepseek-chat")
        raise RuntimeError("boom")

    monkeypatch.setattr(aux, "_call_llm_impl", _impl)
    with pytest.raises(RuntimeError):
        call_llm(
            provider="deepseek",
            model="deepseek-chat",
            messages=[{"role": "user", "content": "hi"}],
            routing_decision_out=out,
        )
    # Even on failure the final dict is copied out and tracking is reset.
    assert out["resolved_provider"] == "deepseek"
    assert out["fallback_used"] is False
    assert aux._AUX_ROUTING_DECISION.get() is None


def test_async_call_llm_populates_routing_decision_out(monkeypatch):
    out: dict = {}

    async def _impl(**kwargs):
        aux._rd_stamp_resolution("deepseek", "deepseek-chat")
        aux._rd_increment_retries()
        return _fake_response()

    monkeypatch.setattr(aux, "_async_call_llm_impl", _impl)
    asyncio.run(
        async_call_llm(
            provider="deepseek",
            model="deepseek-chat",
            messages=[{"role": "user", "content": "hi"}],
            routing_decision_out=out,
        )
    )
    assert out["mode"] == "text"
    assert out["resolved_provider"] == "deepseek"
    assert out["retries"] == 1
    assert out["fallback_used"] is False
    assert aux._AUX_ROUTING_DECISION.get() is None


def test_vision_task_gets_vision_mode(monkeypatch):
    out: dict = {}

    def _impl(**kwargs):
        aux._rd_stamp_resolution("openai", "gpt-5.5")
        return _fake_response()

    monkeypatch.setattr(aux, "_call_llm_impl", _impl)
    call_llm(
        task="vision",
        provider=None,
        model=None,
        messages=[{"role": "user", "content": "hi"}],
        routing_decision_out=out,
    )
    assert out["mode"] == "vision"


def test_rd_helpers_are_noops_without_tracking():
    """The helpers must be safe to call on any path even when no wrapper
    is active (e.g. a call that bypassed the public wrapper)."""
    aux._rd_stamp_resolution("a", "b")
    aux._rd_record_fallback("x", "y", "z")
    aux._rd_increment_retries()
    assert aux._AUX_ROUTING_DECISION.get() is None

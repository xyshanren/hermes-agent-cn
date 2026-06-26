"""Tests for CN's middleware observer-only strategy.

CN policy: **0 LLM 路径拦截**. The middleware framework exists (hermes_cli/middleware.py)
but is **observer-only** in CN — it reports what happened but does not
modify the LLM call path. This is a deliberate conservative choice
(see CHANGELOG_CN.md § v0.17.0+cn.13~16 § "0 LLM 路径拦截").

The middleware is wired up at the *contract* level (apply_*, run_* helpers
exist, RequestMiddlewareResult dataclass is available) but at runtime,
no real middleware is registered, so apply_* and run_* are no-ops
(pass-through).
"""
import inspect

import pytest

from hermes_cli.middleware import (
    OBSERVER_SCHEMA_VERSION,
    MIDDLEWARE_SCHEMA_VERSION,
    VALID_MIDDLEWARE,
    RequestMiddlewareResult,
    apply_llm_request_middleware,
    apply_tool_request_middleware,
    apply_api_request_middleware,
    run_llm_execution_middleware,
    run_tool_execution_middleware,
    observer_payload,
    middleware_payload,
)


class TestMiddlewareSchema:
    """Schema versions + constants for observer compat."""

    def test_observer_schema_version_set(self):
        assert OBSERVER_SCHEMA_VERSION
        assert isinstance(OBSERVER_SCHEMA_VERSION, str)
        assert OBSERVER_SCHEMA_VERSION.startswith("hermes.observer.")

    def test_middleware_schema_version_set(self):
        assert MIDDLEWARE_SCHEMA_VERSION
        assert isinstance(MIDDLEWARE_SCHEMA_VERSION, str)
        assert MIDDLEWARE_SCHEMA_VERSION.startswith("hermes.middleware.")

    def test_valid_middleware_set_has_4_kinds(self):
        """The 4 hook kinds: tool_request, tool_execution, llm_request, llm_execution."""
        assert len(VALID_MIDDLEWARE) == 4
        expected = {
            "tool_request",
            "tool_execution",
            "llm_request",
            "llm_execution",
        }
        assert VALID_MIDDLEWARE == expected


class TestObserverPayload:
    """observer_payload / middleware_payload factory functions."""

    def test_observer_payload_adds_schema_version(self):
        p = observer_payload(event="test")
        assert p["telemetry_schema_version"] == OBSERVER_SCHEMA_VERSION
        assert p["event"] == "test"

    def test_middleware_payload_adds_both_versions(self):
        p = middleware_payload(event="test")
        assert p["telemetry_schema_version"] == OBSERVER_SCHEMA_VERSION
        assert p["middleware_schema_version"] == MIDDLEWARE_SCHEMA_VERSION
        assert p["event"] == "test"

    def test_observer_payload_preserves_user_kwarg_version(self):
        """If user provides telemetry_schema_version, don't override it."""
        p = observer_payload(event="test", telemetry_schema_version="custom.v9")
        assert p["telemetry_schema_version"] == "custom.v9"


class TestApplyMiddlewarePassthrough:
    """CN strategy: no real middleware registered → apply_* is a no-op pass-through."""

    def test_apply_llm_request_middleware_no_change_when_empty(self):
        """No middleware registered → request unchanged."""
        request = {"model": "test", "messages": [{"role": "user", "content": "hi"}]}
        result = apply_llm_request_middleware(request)
        assert isinstance(result, RequestMiddlewareResult)
        assert result.changed is False, (
            "Without registered middleware, apply_llm_request_middleware must be a no-op. "
            "If changed=True, middleware is being registered when it shouldn't be (CN observer-only policy)."
        )
        assert result.payload == request, "Payload should be unchanged"

    def test_apply_tool_request_middleware_no_change_when_empty(self):
        # apply_tool_request_middleware signature: (tool_name, args, **context)
        result = apply_tool_request_middleware(tool_name="test", args={"a": 1})
        assert result.changed is False
        assert result.payload == {"a": 1}

    def test_apply_api_request_alias_compat(self):
        """`apply_api_request_middleware` is the old PoC name alias for `apply_llm_request_middleware`."""
        request = {"model": "test"}
        result = apply_api_request_middleware(request)
        assert result.changed is False
        assert result.payload == request


class TestRunExecutionMiddlewarePassthrough:
    """run_*_middleware must not block the actual execution (no real middleware)."""

    def test_run_llm_execution_middleware_passes_through(self):
        """Without registered middleware, the function executes normally."""
        call_log = []

        def llm_call(request):
            call_log.append(("called", request))
            return {"choices": [{"message": {"content": "hi"}}]}

        # Signature: (request, next_call, **context)
        request = {"model": "test", "messages": []}
        result = run_llm_execution_middleware(request, llm_call)
        assert result is not None, "LLM call should not be blocked by middleware"
        assert len(call_log) == 1, "LLM callback should be called exactly once"
        assert result == {"choices": [{"message": {"content": "hi"}}]}

    def test_run_tool_execution_middleware_passes_through(self):
        call_log = []

        def tool_call(args):
            call_log.append(("called", args))
            return {"result": "ok"}

        # Signature: (tool_name, args, next_call, **context)
        result = run_tool_execution_middleware("test", {"x": 1}, tool_call)
        assert result is not None, "Tool call should not be blocked"
        assert len(call_log) == 1
        assert result == {"result": "ok"}


class TestRequestMiddlewareResult:
    """The dataclass returned by apply_*."""

    def test_default_construction(self):
        r = RequestMiddlewareResult(payload={"a": 1}, original_payload={"a": 1})
        assert r.changed is False
        assert r.trace == []
        assert r.payload == {"a": 1}
        assert r.original_payload == {"a": 1}

    def test_changed_and_trace(self):
        r = RequestMiddlewareResult(
            payload={"a": 2},
            original_payload={"a": 1},
            changed=True,
            trace=[{"middleware": "test"}],
        )
        assert r.changed is True
        assert r.trace == [{"middleware": "test"}]


class TestCNPolicyNoInterception:
    """The CN policy contract: 0 LLM 路径拦截 in cn branches.

    This is the high-level invariant the CN team committed to. If a
    future change makes apply_llm_request_middleware actually modify
    requests in CN, this test fires.
    """

    def test_apply_llm_request_does_not_register_real_middleware_at_import(self):
        """Importing the middleware module must not register real middleware.

        CN chose to expose the *contract* (so plugins can register if they
        want) but not wire up the runtime. This keeps the LLM call path
        untouched while still allowing observer hooks via plugins.
        """
        from hermes_cli import middleware
        from hermes_cli.middleware import _get_middleware_callbacks

        # For each kind, the callbacks list should be empty (no real middleware)
        for kind in VALID_MIDDLEWARE:
            callbacks = _get_middleware_callbacks(kind)
            assert len(callbacks) == 0, (
                f"CN policy violated: {kind} has {len(callbacks)} middleware registered at import. "
                f"CN 0 LLM 路径拦截 strategy means no real middleware should be auto-registered."
            )

    def test_apply_llm_request_source_has_no_intercept_logic(self):
        """Source-level check: the apply_* function must short-circuit on no middleware."""
        from hermes_cli import middleware
        src = inspect.getsource(middleware.apply_llm_request_middleware)
        # The function must check for no middleware and return early
        assert "if not _has_middleware" in src, (
            "apply_llm_request_middleware should short-circuit when no middleware is registered. "
            "Missing short-circuit = interception logic might fire when no plugins register."
        )

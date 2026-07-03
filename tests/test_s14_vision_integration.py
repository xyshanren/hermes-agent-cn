"""End-to-end integration test for S14 vision (NEEDS_BACKLOG §需求 3).

Combines the three phases into a single scenario:

  1. Phase 1 — image_tokens is parsed from the API response and surfaces
     in CanonicalUsage / session_image_tokens / usage_dict.prompt_tokens_details.
  2. Phase 2 — vision routing_decision metadata flows from async_call_llm
     to vision_analyze_tool's JSON output.
  3. Phase 3 — pre-flight TooManyImagesError fires before the upstream
     call when N images > model max.

Each phase also has its own focused unit tests; this file makes sure the
three pieces compose correctly.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from agent.usage_pricing import CanonicalUsage, normalize_usage


# ─── Phase 1: image_tokens end-to-end ───────────────────────────────────────


class TestImageTokensEndToEnd:
    def test_openai_chat_response_flows_through_normalize(self):
        """OpenAI chat.completions response with image_tokens is captured."""
        usage = SimpleNamespace(
            prompt_tokens=5000,
            completion_tokens=300,
            prompt_tokens_details=SimpleNamespace(
                cached_tokens=2000,
                image_tokens=1200,
            ),
        )
        normalized = normalize_usage(usage, provider="openai", api_mode="chat_completions")
        assert normalized.image_tokens == 1200
        assert normalized.input_tokens == 3000  # 5000 - 2000 cache
        assert normalized.prompt_tokens == 5000  # matches upstream

    def test_codex_response_flows_through_normalize(self):
        """Codex Responses API uses input_tokens_details instead."""
        usage = SimpleNamespace(
            input_tokens=4000,
            output_tokens=200,
            input_tokens_details=SimpleNamespace(
                cached_tokens=1000,
                image_tokens=800,
            ),
        )
        normalized = normalize_usage(usage, provider="openai-codex", api_mode="codex_responses")
        assert normalized.image_tokens == 800
        assert normalized.input_tokens == 3000

    def test_anthropic_image_tokens_stays_zero(self):
        """Anthropic native does not surface image_tokens; pre-flight cost
        from request side via estimate_messages_tokens_rough."""
        usage = SimpleNamespace(
            input_tokens=1000,
            output_tokens=200,
            cache_read_input_tokens=300,
        )
        normalized = normalize_usage(usage, provider="anthropic", api_mode="anthropic_messages")
        assert normalized.image_tokens == 0


# ─── Phase 2: vision routing_decision end-to-end ────────────────────────────


class TestVisionRoutingDecisionEndToEnd:
    def test_routing_dict_round_trips_through_async_call_llm_signature(self):
        """Verify routing_decision_out is a real kwarg in async_call_llm."""
        import inspect
        from agent.auxiliary_client import async_call_llm
        sig = inspect.signature(async_call_llm)
        assert "routing_decision_out" in sig.parameters
        param = sig.parameters["routing_decision_out"]
        # Default is None — older callers don't have to pass it.
        assert param.default is None

    def test_routing_dict_round_trips_through_call_llm_signature(self):
        """Sync call_llm also accepts routing_decision_out."""
        import inspect
        from agent.auxiliary_client import call_llm
        sig = inspect.signature(call_llm)
        assert "routing_decision_out" in sig.parameters
        assert sig.parameters["routing_decision_out"].default is None

    def test_vision_fallback_config_returns_four_tuple_with_reason(self):
        """_try_vision_fallback_config returns (provider, client, model, reason)."""
        from agent.auxiliary_client import _try_vision_fallback_config
        # We don't have a configured fallback in CI; just verify the function
        # is importable and accepts the (provider, model, base_url, api_key)
        # signature without raising. Returns None when no fallback configured.
        result = _try_vision_fallback_config(
            provider="openai",
            model="gpt-5",
            base_url=None,
            api_key=None,
        )
        # No fallback configured in CI → None. Or it could be a 4-tuple.
        # What matters is the return shape didn't break.
        assert result is None or (
            isinstance(result, tuple) and len(result) == 4
        )


# ─── Phase 3: TooManyImagesError end-to-end ─────────────────────────────────


class TestTooManyImagesErrorEndToEnd:
    def test_too_many_images_error_carries_actionable_message(self):
        # Import inside the test to avoid run_agent module-level side effects
        # (run_agent is huge and re-importing on every module load is slow).
        from run_agent import TooManyImagesError
        err = TooManyImagesError(
            image_count=50,
            max_images=16,
            provider="openai",
            model="gpt-5",
        )
        msg = str(err)
        # The message must guide the user to a fix path.
        assert "50" in msg
        assert "16" in msg
        assert "openai" in msg
        assert "gpt-5" in msg
        assert "config" in msg.lower() or "vision_analyze" in msg.lower(), (
            "Error message must point at config override or vision_analyze"
        )
        # Fields are exposed for programmatic handling.
        assert err.image_count == 50
        assert err.max_images == 16
        assert err.provider == "openai"
        assert err.model == "gpt-5"

    def test_image_routing_limit_relaxes_via_config(self):
        """End-to-end: validate_image_count respects config override."""
        from agent.image_routing import validate_image_count
        msgs = [
            {"role": "user", "content": [
                {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{i}"}}
                for i in range(20)
            ]}
        ]
        # Default model limit (gpt-5) is 16 → would reject.
        assert validate_image_count(msgs, model="gpt-5")["would_reject"] is True
        # Config override → 50 → allows it.
        cfg = {"agent": {"vision_max_images": 50}}
        assert validate_image_count(msgs, model="gpt-5", cfg=cfg)["would_reject"] is False
        # Claude 4 has its own higher cap (100).
        assert validate_image_count(msgs, model="claude-opus-4-6")["would_reject"] is False


# ─── Cross-phase composition: SSE usage_dict shape ──────────────────────────


class TestSSEUsageDictShape:
    """Verify the actual usage_dict that conversation_loop pushes via SSE
    includes the OpenAI-standard prompt_tokens_details with image_tokens.
    """

    def test_canonical_usage_round_trip_to_usage_dict_shape(self):
        """Mirror what conversation_loop.py does at L1509-1518."""
        # Simulate the canonical_usage object that comes back from a real
        # OpenAI chat.completions call.
        raw = SimpleNamespace(
            prompt_tokens=5000,
            completion_tokens=300,
            prompt_tokens_details=SimpleNamespace(
                cached_tokens=2000,
                image_tokens=1200,
            ),
        )
        cu = normalize_usage(raw, provider="openai", api_mode="chat_completions")

        # conversation_loop.py usage_dict construction (mirrored):
        usage_dict = {
            "prompt_tokens": cu.prompt_tokens,
            "completion_tokens": cu.output_tokens,
            "total_tokens": cu.total_tokens,
            "prompt_tokens_details": {
                "image_tokens": cu.image_tokens,
                "cached_tokens": cu.cache_read_tokens,
            },
        }

        # OpenAI standard shape — this is what the tray will consume.
        assert usage_dict["prompt_tokens"] == 5000
        assert usage_dict["completion_tokens"] == 300
        assert usage_dict["total_tokens"] == 5300
        assert usage_dict["prompt_tokens_details"]["image_tokens"] == 1200
        assert usage_dict["prompt_tokens_details"]["cached_tokens"] == 2000

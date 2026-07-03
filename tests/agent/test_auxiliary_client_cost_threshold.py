"""S12 P2 — auxiliary_client._evaluate_per_request_cost_threshold tests.

Verify the per-request cost threshold check fires only when:
1. cost_aware_fallback is enabled in config
2. the response carries a usage object
3. estimate_usage_cost returns a known amount
4. amount > per_request_max_usd

And that it's a silent no-op when any of those fail (no usage, unknown
model pricing, disabled config, missing routing_out, etc.).
"""

from types import SimpleNamespace

import pytest


def _patch_config(monkeypatch, cfg_dict):
    monkeypatch.setattr(
        "hermes_cli.config.load_config",
        lambda: {"agent": {"cost_aware_fallback": cfg_dict}},
        raising=False,
    )


def _response_with_usage(input_tokens=1000, output_tokens=500):
    """Build a fake response with a known usage shape."""
    return SimpleNamespace(
        usage=SimpleNamespace(
            prompt_tokens=input_tokens,
            completion_tokens=output_tokens,
            total_tokens=input_tokens + output_tokens,
        ),
        choices=[SimpleNamespace(message=SimpleNamespace(content="hi"))],
        model="gpt-5.5",
    )


def _patch_estimate_usage_cost(monkeypatch, amount_usd):
    """Force estimate_usage_cost to return a fixed amount.

    Lets the tests exercise the threshold logic without needing
    actual pricing-table entries for the model in question.
    """
    from agent import usage_pricing

    def _fake_estimate(model_name, usage, *, provider=None, base_url=None,
                       api_key=None):
        from agent.usage_pricing import CostResult
        return CostResult(
            amount_usd=amount_usd,
            status="estimated",
            source="test",
            label=f"~${amount_usd:.4f}" if amount_usd is not None else "n/a",
        )

    monkeypatch.setattr(usage_pricing, "estimate_usage_cost", _fake_estimate)


class TestEvaluatePerRequestCostThreshold:

    def test_disabled_config_no_threshold(self, monkeypatch):
        from agent.auxiliary_client import _evaluate_per_request_cost_threshold
        _patch_config(monkeypatch, {
            "enabled": False, "per_request_max_usd": 0.01,
        })
        _patch_estimate_usage_cost(monkeypatch, 0.10)
        routing: dict = {"mode": "text"}
        _evaluate_per_request_cost_threshold(
            _response_with_usage(),
            resolved_provider="openai",
            resolved_model="gpt-5.5",
            routing_out=routing,
        )
        # No threshold annotated — feature is off.
        assert "cost_threshold_exceeded" not in routing

    def test_no_usage_object_no_threshold(self, monkeypatch):
        from agent.auxiliary_client import _evaluate_per_request_cost_threshold
        _patch_config(monkeypatch, {
            "enabled": True, "per_request_max_usd": 0.01,
        })
        _patch_estimate_usage_cost(monkeypatch, 0.10)
        response = SimpleNamespace(
            usage=None,
            choices=[SimpleNamespace(message=SimpleNamespace(content="hi"))],
            model="gpt-5.5",
        )
        routing: dict = {}
        _evaluate_per_request_cost_threshold(
            response,
            resolved_provider="openai",
            resolved_model="gpt-5.5",
            routing_out=routing,
        )
        assert "cost_threshold_exceeded" not in routing

    def test_below_threshold_no_threshold(self, monkeypatch):
        from agent.auxiliary_client import _evaluate_per_request_cost_threshold
        _patch_config(monkeypatch, {
            "enabled": True, "per_request_max_usd": 0.10,
        })
        _patch_estimate_usage_cost(monkeypatch, 0.05)  # under 0.10
        routing: dict = {}
        _evaluate_per_request_cost_threshold(
            _response_with_usage(),
            resolved_provider="openai",
            resolved_model="gpt-5.5",
            routing_out=routing,
        )
        assert "cost_threshold_exceeded" not in routing

    def test_above_threshold_annotates_routing(self, monkeypatch):
        from agent.auxiliary_client import _evaluate_per_request_cost_threshold
        _patch_config(monkeypatch, {
            "enabled": True, "per_request_max_usd": 0.01,
        })
        _patch_estimate_usage_cost(monkeypatch, 0.05)  # over 0.01
        routing: dict = {"mode": "text"}
        _evaluate_per_request_cost_threshold(
            _response_with_usage(),
            resolved_provider="openai",
            resolved_model="gpt-5.5",
            routing_out=routing,
        )
        assert routing["cost_threshold_exceeded"] is True
        assert routing["cost_threshold_reason"] == "request_budget_exceeded"

    def test_unknown_cost_no_threshold(self, monkeypatch):
        """estimate_usage_cost returns None when pricing is unknown — no fire."""
        from agent.auxiliary_client import _evaluate_per_request_cost_threshold
        _patch_config(monkeypatch, {
            "enabled": True, "per_request_max_usd": 0.01,
        })
        _patch_estimate_usage_cost(monkeypatch, None)
        routing: dict = {}
        _evaluate_per_request_cost_threshold(
            _response_with_usage(),
            resolved_provider="openai",
            resolved_model="gpt-5.5",
            routing_out=routing,
        )
        assert "cost_threshold_exceeded" not in routing

    def test_no_routing_out_does_not_crash(self, monkeypatch):
        """Defensive — caller might pass None / list / str."""
        from agent.auxiliary_client import _evaluate_per_request_cost_threshold
        _patch_config(monkeypatch, {
            "enabled": True, "per_request_max_usd": 0.01,
        })
        _patch_estimate_usage_cost(monkeypatch, 0.05)
        for bad in (None, [], "string", 42):
            # Should NOT raise.
            _evaluate_per_request_cost_threshold(
                _response_with_usage(),
                resolved_provider="openai",
                resolved_model="gpt-5.5",
                routing_out=bad,
            )

    def test_no_config_section_no_threshold(self, monkeypatch):
        """If the user has no agent.cost_aware_fallback at all, no fire."""
        from agent.auxiliary_client import _evaluate_per_request_cost_threshold
        monkeypatch.setattr(
            "hermes_cli.config.load_config",
            lambda: {},
            raising=False,
        )
        _patch_estimate_usage_cost(monkeypatch, 0.10)
        routing: dict = {}
        _evaluate_per_request_cost_threshold(
            _response_with_usage(),
            resolved_provider="openai",
            resolved_model="gpt-5.5",
            routing_out=routing,
        )
        assert "cost_threshold_exceeded" not in routing

    def test_load_config_exception_swallowed(self, monkeypatch):
        """A broken config layer must not crash the success path."""
        from agent.auxiliary_client import _evaluate_per_request_cost_threshold

        def _broken_load():
            raise RuntimeError("yaml corruption")

        monkeypatch.setattr(
            "hermes_cli.config.load_config",
            _broken_load,
            raising=False,
        )
        _patch_estimate_usage_cost(monkeypatch, 0.10)
        routing: dict = {}
        # Should NOT raise.
        _evaluate_per_request_cost_threshold(
            _response_with_usage(),
            resolved_provider="openai",
            resolved_model="gpt-5.5",
            routing_out=routing,
        )
        assert "cost_threshold_exceeded" not in routing

    def test_no_per_request_threshold_means_disabled(self, monkeypatch):
        """User enabled the feature but left per_request_max_usd unset —
        no per-request threshold fires (session check still works)."""
        from agent.auxiliary_client import _evaluate_per_request_cost_threshold
        _patch_config(monkeypatch, {
            "enabled": True, "per_request_max_usd": None,
        })
        _patch_estimate_usage_cost(monkeypatch, 0.10)
        routing: dict = {}
        _evaluate_per_request_cost_threshold(
            _response_with_usage(),
            resolved_provider="openai",
            resolved_model="gpt-5.5",
            routing_out=routing,
        )
        assert "cost_threshold_exceeded" not in routing
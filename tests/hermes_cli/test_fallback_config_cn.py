"""Tests for the recovered fallback_config.py module.

Background: The 72-line fallback_config.py was accidentally dropped during
the v0.17.0 cherry-pick merge (commit 8e253d90b recovered it). Without it,
providers like::

    fallback_providers:
      - {provider: siliconflow, model: Qwen/Qwen2.5-7B-Instruct}
      - {provider: ollama,      model: qwen3-vl:4b}
      - {provider: embedded,    model: qwen-0.5b}

were silently ignored, and users with no API key for the primary provider
would see immediate "No LLM provider configured" errors instead of the
chain trying each fallback.
"""
import pytest

from hermes_cli.fallback_config import get_fallback_chain


class TestFallbackChainMerging:
    """Verify get_fallback_chain() merges + dedupes fallback entries."""

    def test_empty_config_returns_empty_chain(self):
        assert get_fallback_chain({}) == []

    def test_none_config_returns_empty_chain(self):
        assert get_fallback_chain(None) == []

    def test_fallback_providers_preserves_order(self):
        cfg = {
            "fallback_providers": [
                {"provider": "siliconflow", "model": "Qwen/Qwen2.5-7B-Instruct"},
                {"provider": "ollama", "model": "qwen3-vl:4b"},
                {"provider": "embedded", "model": "qwen-0.5b"},
            ]
        }
        chain = get_fallback_chain(cfg)
        assert len(chain) == 3
        assert chain[0]["model"] == "Qwen/Qwen2.5-7B-Instruct"
        assert chain[1]["model"] == "qwen3-vl:4b"
        assert chain[2]["model"] == "qwen-0.5b"

    def test_dedup_within_fallback_providers(self):
        """Same (provider, model, base_url) twice → 1 entry (not 2)."""
        cfg = {
            "fallback_providers": [
                {"provider": "siliconflow", "model": "Qwen/Qwen2.5-7B-Instruct"},
                {"provider": "ollama", "model": "qwen3-vl:4b"},
                {"provider": "siliconflow", "model": "Qwen/Qwen2.5-7B-Instruct"},  # dup
            ]
        }
        chain = get_fallback_chain(cfg)
        assert len(chain) == 2
        models = [c["model"] for c in chain]
        assert "Qwen/Qwen2.5-7B-Instruct" in models
        assert "qwen3-vl:4b" in models

    def test_legacy_fallback_model_merged_after_fallback_providers(self):
        """Old `fallback_model` entries appended after new `fallback_providers`."""
        cfg = {
            "fallback_providers": [
                {"provider": "siliconflow", "model": "Qwen/Qwen2.5-7B-Instruct"},
            ],
            "fallback_model": {
                "provider": "ollama",
                "model": "qwen3-vl:4b",
            },
        }
        chain = get_fallback_chain(cfg)
        assert len(chain) == 2
        assert chain[0]["model"] == "Qwen/Qwen2.5-7B-Instruct"
        assert chain[1]["model"] == "qwen3-vl:4b"

    def test_legacy_fallback_model_dict_form_supported(self):
        """Pre-0.17.0 single fallback_model was a dict, not a list."""
        cfg = {
            "fallback_model": {
                "provider": "embedded",
                "model": "qwen-0.5b",
            }
        }
        chain = get_fallback_chain(cfg)
        assert len(chain) == 1
        assert chain[0]["model"] == "qwen-0.5b"

    def test_invalid_entries_skipped(self):
        """Entries missing provider or model are filtered out."""
        cfg = {
            "fallback_providers": [
                {"provider": "a", "model": "m1"},
                {"provider": "b"},  # missing model
                {"model": "m2"},  # missing provider
                {"provider": "", "model": "m3"},  # empty provider
                {"provider": "a", "model": "m1"},  # dup
                {"provider": "c", "model": "m3"},
            ]
        }
        chain = get_fallback_chain(cfg)
        assert len(chain) == 2
        models = [c["model"] for c in chain]
        assert models == ["m1", "m3"]

    def test_base_url_normalized_in_identity(self):
        """Trailing slashes and whitespace in base_url are dedup-aware."""
        cfg = {
            "fallback_providers": [
                {"provider": "a", "model": "m1", "base_url": "https://example.com/v1/"},
                {"provider": "a", "model": "m1", "base_url": "https://example.com/v1"},  # dup w/ trailing /
            ]
        }
        chain = get_fallback_chain(cfg)
        assert len(chain) == 1

    def test_base_url_difference_keeps_entries(self):
        """Different base_url = different identity = both entries kept."""
        cfg = {
            "fallback_providers": [
                {"provider": "a", "model": "m1", "base_url": "https://a.example.com/v1"},
                {"provider": "a", "model": "m1", "base_url": "https://b.example.com/v1"},
            ]
        }
        chain = get_fallback_chain(cfg)
        assert len(chain) == 2

    def test_returned_entries_are_fresh_copies(self):
        """Mutating the returned entry must NOT mutate the config."""
        cfg = {
            "fallback_providers": [
                {"provider": "a", "model": "m1"},
            ]
        }
        chain = get_fallback_chain(cfg)
        chain[0]["model"] = "MUTATED"
        # Original config unchanged
        assert cfg["fallback_providers"][0]["model"] == "m1"

"""Tests for the v0.17.0+cn.16 custom provider identity fix.

Background: commit 9585396bd (cherry-picked as part of v0.17.0+cn.16) added
``find_custom_provider_identity(base_url)`` to fix a session-persistence bug:

  _runtime_model_config persisted the live agent's RESOLVED provider into
  the session row's model_config JSON. For any named providers:/
  custom_providers: entry, agent.provider is the literal string "custom",
  so the entry name was lost (and the api_key is deliberately never
  persisted). On session.resume or _reset_session_agent the stored
  provider="custom" fed resolve_runtime_provider(requested="custom"),
  which cannot match a named entry — the rebuild either raised
  "No LLM provider configured" or silently resolved placeholder credentials
  against the patched-back base_url.

Fix: store the REQUESTED/entry identity instead, recovered via URL
reverse-lookup through find_custom_provider_identity(base_url).
"""
import pytest

from hermes_cli.runtime_provider import (
    _normalize_base_url_for_match,
    find_custom_provider_identity,
)


class TestNormalizeBaseUrlForMatch:
    """The internal normalizer used for URL identity comparison."""

    def test_strips_trailing_slash(self):
        assert _normalize_base_url_for_match("https://api.example.com/v1/") == "https://api.example.com/v1"

    def test_strips_whitespace(self):
        assert _normalize_base_url_for_match("  https://api.example.com/v1  ") == "https://api.example.com/v1"

    def test_lowercases(self):
        assert _normalize_base_url_for_match("HTTPS://API.Example.com/V1") == "https://api.example.com/v1"

    def test_none_input_returns_empty_string(self):
        assert _normalize_base_url_for_match(None) == ""

    def test_empty_string_returns_empty_string(self):
        assert _normalize_base_url_for_match("") == ""

    def test_non_string_input_returns_str_normalized(self):
        result = _normalize_base_url_for_match(123)
        assert result == "123"


class TestFindCustomProviderIdentity:
    """The reverse-lookup function that recovers custom:<name> from a URL."""

    def test_no_config_returns_none(self, monkeypatch):
        """When load_config() returns empty, identity is None."""
        from hermes_cli import runtime_provider

        monkeypatch.setattr(runtime_provider, "load_config", lambda: {})
        assert find_custom_provider_identity("https://api.example.com/v1") is None

    def test_empty_url_returns_none(self):
        assert find_custom_provider_identity("") is None

    def test_whitespace_url_returns_none(self):
        assert find_custom_provider_identity("   ") is None

    def test_providers_section_match(self, monkeypatch):
        """Match against config['providers'] entries."""
        from hermes_cli import runtime_provider

        cfg = {
            "providers": {
                "Api.siliconflow.cn": {
                    "api": "https://api.siliconflow.cn/v1",
                    "api_key": "sk-test",
                }
            }
        }
        monkeypatch.setattr(runtime_provider, "load_config", lambda: cfg)
        # Use the actual URL the entry has
        identity = find_custom_provider_identity("https://api.siliconflow.cn/v1")
        assert identity is not None
        assert identity.startswith("custom:")
        # Name should be normalized (lowercased + spaces/hyphens handled)
        assert "siliconflow" in identity.lower() or "siliconflow.cn" in identity.lower()

    def test_url_mismatch_returns_none(self, monkeypatch):
        """URL that no provider entry matches → None."""
        from hermes_cli import runtime_provider

        cfg = {
            "providers": {
                "Api.siliconflow.cn": {
                    "api": "https://api.siliconflow.cn/v1",
                }
            }
        }
        monkeypatch.setattr(runtime_provider, "load_config", lambda: cfg)
        identity = find_custom_provider_identity("https://api.openai.com/v1")
        assert identity is None

    def test_trailing_slash_normalized(self, monkeypatch):
        """URLs with/without trailing slash should match the same entry."""
        from hermes_cli import runtime_provider

        cfg = {
            "providers": {
                "test_provider": {
                    "api": "https://api.example.com/v1",
                }
            }
        }
        monkeypatch.setattr(runtime_provider, "load_config", lambda: cfg)
        # Both with and without trailing slash should match
        id1 = find_custom_provider_identity("https://api.example.com/v1/")
        id2 = find_custom_provider_identity("https://api.example.com/v1")
        assert id1 == id2
        assert id1 is not None

    def test_load_config_exception_returns_none(self, monkeypatch):
        """If load_config raises, identity lookup fails gracefully."""
        from hermes_cli import runtime_provider

        def boom():
            raise RuntimeError("config load failed")

        monkeypatch.setattr(runtime_provider, "load_config", boom)
        # Should not raise
        result = find_custom_provider_identity("https://api.example.com/v1")
        assert result is None

    def test_base_url_field_aliases(self, monkeypatch):
        """The 'api' field, 'url' field, and 'base_url' field all work."""
        from hermes_cli import runtime_provider

        # api field
        cfg_api = {"providers": {"p1": {"api": "https://x.example.com/v1"}}}
        monkeypatch.setattr(runtime_provider, "load_config", lambda: cfg_api)
        assert find_custom_provider_identity("https://x.example.com/v1") is not None

        # url field
        cfg_url = {"providers": {"p1": {"url": "https://x.example.com/v1"}}}
        monkeypatch.setattr(runtime_provider, "load_config", lambda: cfg_url)
        assert find_custom_provider_identity("https://x.example.com/v1") is not None

        # base_url field
        cfg_base = {"providers": {"p1": {"base_url": "https://x.example.com/v1"}}}
        monkeypatch.setattr(runtime_provider, "load_config", lambda: cfg_base)
        assert find_custom_provider_identity("https://x.example.com/v1") is not None

    def test_no_providers_section_returns_none(self, monkeypatch):
        """Config without 'providers' key returns None (not crash)."""
        from hermes_cli import runtime_provider

        monkeypatch.setattr(runtime_provider, "load_config", lambda: {"other_key": "value"})
        assert find_custom_provider_identity("https://api.example.com/v1") is None

    def test_non_dict_providers_section_returns_none(self, monkeypatch):
        """If 'providers' is a list or string (not dict), returns None."""
        from hermes_cli import runtime_provider

        monkeypatch.setattr(runtime_provider, "load_config", lambda: {"providers": ["not", "a", "dict"]})
        assert find_custom_provider_identity("https://api.example.com/v1") is None

    def test_non_dict_entry_value_skipped(self, monkeypatch):
        """Provider entries that are not dicts (e.g. str) are skipped, not crash."""
        from hermes_cli import runtime_provider

        cfg = {
            "providers": {
                "valid": {"api": "https://valid.example.com/v1"},
                "broken": "this should be a dict",
            }
        }
        monkeypatch.setattr(runtime_provider, "load_config", lambda: cfg)
        # Valid entry still works
        assert find_custom_provider_identity("https://valid.example.com/v1") is not None


class TestSessionPersistenceRoundTrip:
    """The full round-trip scenario this fix enables.

    Simulate: store identity on session creation, then recover it on
    session.resume by base_url only (the api_key is not persisted).
    """

    def test_resume_recovers_custom_identity_via_base_url(self, monkeypatch):
        """The original bug scenario: session stored with provider='custom',
        resume can recover the canonical name from the URL.
        """
        from hermes_cli import runtime_provider

        cfg = {
            "providers": {
                "Api.siliconflow.cn": {
                    "api": "https://api.siliconflow.cn/v1",
                    "api_key_env": "SILICONFLOW_API_KEY",
                }
            }
        }
        monkeypatch.setattr(runtime_provider, "load_config", lambda: cfg)

        # Simulate session.resume: only the URL is known, not the entry name
        base_url = "https://api.siliconflow.cn/v1"
        identity = find_custom_provider_identity(base_url)
        assert identity is not None, (
            "Session resume should be able to recover the canonical custom:<name> "
            "identity from the base_url alone."
        )
        # The identity can be used to look up the entry
        assert identity.startswith("custom:")

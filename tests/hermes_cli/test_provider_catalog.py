"""Tests for the unified provider catalog (hermes_cli.provider_catalog).

These are invariant tests, not snapshots: they assert the parity *contract*
between what ``hermes model`` shows (``CANONICAL_PROVIDERS``) and what the
catalog exposes, plus how each provider's ``auth_type`` maps to a desktop tab —
never a specific provider count or a frozen vendor list (both change over time).
"""

from hermes_cli.provider_catalog import (
    provider_catalog,
    provider_catalog_by_slug,
)

def test_profileless_providers_still_present():
    """Providers without a ProviderProfile must still resolve via fallbacks.

    openai-api / tencent-tokenplan / xai-oauth have no profile; they exist
    only as registry + canonical entries. The catalog must not require a
    profile to include a provider.
    """
    by = provider_catalog_by_slug()
    for slug in ("openai-api", "tencent-tokenplan", "xai-oauth"):
        assert slug in by, f"{slug} dropped from catalog (profile-less provider)"
        assert by[slug].label, f"{slug} has empty label despite canonical fallback"
        assert by[slug].description, f"{slug} has empty description despite fallback"



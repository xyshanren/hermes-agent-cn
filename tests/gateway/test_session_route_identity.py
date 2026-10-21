"""Launch-route gates compare what the runtime resolves, not how the provider was spelled."""
import pytest

from gateway.session_route_identity import ROUTE_BOUND_KEYS, resolved_route, same_route

A, B = 'http://127.0.0.1:8001/v1', 'http://127.0.0.1:8002/v1'
CONFIG = {'providers': {'team': {'base_url': A, 'api_key': 'sk-team'}}}


def test_resolved_route_identity_and_url():
    assert resolved_route({'provider': 'custom:team'}, CONFIG) == ('custom:team', A)
    assert resolved_route({'provider': 'TEAM', 'base_url': B + '/'}, CONFIG) == ('custom:team', B)
    assert resolved_route({'provider': 'ollama', 'base_url': A}, {}) == ('custom', A)
    assert resolved_route({'provider': ''}, CONFIG) == ('auto', '')


def test_configured_entry_key_is_the_key_or_a_legacy_entrys_display_name():
    """A keyed ``providers:`` entry is named by its key, never its display name. A legacy
    ``custom_providers:`` entry has no key, so its normalized display name is its identity, the
    same rule as Desktop's ``customDefaultSupersedesPick``."""
    from gateway.session_route_identity import configured_entry_key, profile_route_identity

    def held_key(entries, provider):
        config = {**entries, 'model': {'provider': provider}}
        return configured_entry_key(profile_route_identity(config), config)
    keyed = {'providers': {'work': {'name': 'OpenRouter', 'base_url': A}}}
    legacy = {'custom_providers': [{'name': 'OpenRouter', 'base_url': A}]}
    assert held_key(keyed, 'custom:work') == 'work'
    assert held_key(keyed, 'custom:openrouter') == 'work'
    assert held_key(legacy, 'custom:openrouter') == 'openrouter'
    assert held_key({}, 'openrouter') == ''


def test_route_bound_keys_cover_route_wire_window_and_credentials():
    assert isinstance(ROUTE_BOUND_KEYS, tuple)
    for key in ('provider', 'base_url', 'api_mode', 'context_length',
                'api_key', 'api', 'api_key_from', 'key_env', 'api_key_env'):
        assert key in ROUTE_BOUND_KEYS

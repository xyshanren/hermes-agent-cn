"""Authorization env names of bundled platforms survive a registry entry that lacks them.

They live in each plugin's ``gateway_env.AUTHZ`` (read by core straight from the file) and reach the
registry through ``register()``. A user plugin overriding a bundled platform, safe mode or a
disabled plugin must still gate on them: core's own tables always did."""

import dataclasses

import pytest

from gateway.config import Platform
from gateway.platform_env import _BUNDLED_ENV_SIBLINGS, bundled_authz

_FIELDS = ("allowed_users_env", "allow_all_env", "allow_bots_env", "own_policy_env")


def _bundled_with_authz():
    names = set(Platform._scan_bundled_plugin_platforms()[0]) | set(_BUNDLED_ENV_SIBLINGS)
    return sorted(name for name in names if bundled_authz(name))



"""Plugins whose own code imports siblings by absolute path must register by that same path.

The loader executes a bundled platform package under a synthetic ``hermes_plugins.platforms__<name>``
name. A package whose adapter (or standalone sender / tools) imports ``plugins.platforms.<name>.*``
would then hold two adapter classes: the registry's and the one the rest of the code sees
(Yuanbao's ``get_active()`` singleton, isinstance checks, monkeypatches).
"""

import importlib

import pytest



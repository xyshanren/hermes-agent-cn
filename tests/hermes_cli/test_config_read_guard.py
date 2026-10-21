"""Lint guard: no new raw yaml.safe_load(config.yaml) reads outside owner modules.

The drift class this kills: scattered ``yaml.safe_load`` reads of the user's
``config.yaml`` silently miss the managed-scope overlay, ``${ENV_VAR}``
expansion, profile-aware pathing, and root-model normalization. Each new
config feature has historically required an N-site sweep (incident chain:
9cbcc0c9c8 → 732293cf87 → b0e47a98f9 → 1928aa0443).

Canonical owners:

  * ``hermes_cli/config.py`` — ``load_config()`` / ``load_config_readonly()``
    (merged + managed + env-expanded), ``read_raw_config()`` and
    ``read_user_config_raw()`` (the ONLY legal raw primitives: write-back
    round-trips + raw-file diagnostics).
  * ``gateway/config.py`` — the gateway's ``load_gateway_config`` owner.
  * ``gateway/run.py`` — ``_load_gateway_config()``'s monkeypatched-home
    fallback path (delegates to ``read_raw_config`` when paths agree).

Everything else must import one of those. If this test fails on your new
code, use ``load_config()``/``load_config_readonly()`` for behavioral reads,
or ``read_user_config_raw()`` for write-back round-trips — do not add your
file to the allowlist without a reason of the same class.
"""

from __future__ import annotations

import os
import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent

# Files where a yaml.safe_load near a config.yaml reference is legal.
# Keep this list SHORT and justified:
ALLOWLIST = {
    # Canonical loader owners.
    "hermes_cli/config.py",
    "gateway/config.py",
    # load_gateway_config()'s config.yaml phase lives here (extracted from
    # gateway/config.py); same owner, same managed-overlay contract.
    "gateway/config_loader.py",
    # _load_gateway_config()'s fallback path for tests that monkeypatch
    # gateway.run._hermes_home (delegates to read_raw_config otherwise).
    "gateway/run.py",
    # Reads the MANAGED-scope config.yaml (/etc/hermes/...), not the user's —
    # it IS the overlay source; the canonical loaders call into it.
    "hermes_cli/managed_scope.py",
    # Parse-health probe: intentionally answers "does the raw file parse?".
    "gateway/readiness.py",
    # _early_interface_from_config(): the pre-argparse TUI decision runs before
    # hermes_cli.config is importable; it reads one display key best-effort and
    # defaults to the classic REPL on any error.
    "hermes_cli/main.py",
}

# Directories that never count (tests may build fixture configs freely).
EXCLUDED_DIR_PARTS = {
    "tests", ".venv", ".git", ".worktrees", "node_modules", "website",
    "docs", "scripts", "examples", "apps",
    # Compiled bytecode is not source. Sibling test processes also create
    # and delete these directories while this scan walks the tree.
    "__pycache__",
}

# A safe_load within this many lines of a config.yaml reference is treated
# as a raw user-config read.
PROXIMITY = 6

SAFE_LOAD_RE = re.compile(r"\bsafe_load\s*\(")
CONFIG_YAML_RE = re.compile(r"""["']config\.yaml["']""")


def _iter_source_files():
    # This uses os.walk with a pruned dirnames, and not rglob. rglob descends
    # into every directory and filters after that, so it calls scandir() on
    # __pycache__ trees that this guard never inspects. Sibling test processes
    # create and delete those entries during the run.
    #
    # A directory that disappears in the middle of a walk raises
    # FileNotFoundError out of rglob. The test then fails for a reason that it
    # does not assert.
    #
    # The prune skips those trees. The onerror callback ignores a directory
    # that disappears anyway.
    for dirpath, dirnames, filenames in os.walk(REPO_ROOT, onerror=lambda _e: None):
        dirnames[:] = [d for d in dirnames if d not in EXCLUDED_DIR_PARTS]
        for name in filenames:
            if not name.endswith(".py"):
                continue
            path = Path(dirpath) / name
            rel = path.relative_to(REPO_ROOT)
            if any(part in EXCLUDED_DIR_PARTS for part in rel.parts):
                continue
            yield rel, path


def test_read_user_config_raw_exists_and_documented():
    """The shared raw primitive must exist and carry its legality docstring."""
    from hermes_cli.config import read_user_config_raw

    doc = read_user_config_raw.__doc__ or ""
    assert "ONLY legal for write-back round-trips and raw-file diagnostics" in doc
    assert "load_config()" in doc

# pm/ — dependencies and Hermes environments

Applies on top of the root `AGENTS.md` (which carries the short form of the pinning rule).

## Dependency pinning policy

All dependencies carry upper bounds (litellm compromise #2796/#2810; Mini Shai-Hulud worm,
May 2026). PyPI: `>=floor,<next_major` (`"httpx>=0.28.1,<1"`); pre-1.0: `<0.(minor+2)`
(`>=0.29,<0.32`). Git URLs: 40-char commit SHA. GitHub Actions: SHA + `# vN` comment. CI-only
Python requirements: `==exact`. A bare `>=X.Y.Z` is rejected by CI and reviewers.
After changing `pyproject.toml`, run `hermes pm lock`, re-source `./activate`, and commit
`pyproject.toml` with `uv.lock`. Reference: #2810 (bounds), #9801 (SHA pinning + audit CI).

PM owns Hermes Python dependency changes. Use `pm.sync_venv(['extra'], explicit=True)`
for declared runtime extras, `hermes pm install` for setup/sync, and `hermes pm repair`
for damaged dependencies. Do not mutate Hermes environments with raw pip or uv.
Use `pm.build_environment` for fresh build outputs and `pm.ensure_environment` for
isolated tool environments. Callers receive an interpreter or tool path, not uv.
Nix's declarative uv2nix builds and unrelated user projects remain independently owned.

The `[tool.uv] exclude-newer = "3 days"` release-age check covers **Hermes's own dependencies
only**, exact pins included, with no per-package exemptions, and it runs when Hermes LOCKS
(`hermes pm lock`, CI's lock check), never on users' machines: every generated workspace drops the
cutoff (`pm/workspace.py::_without_release_age`), so a mirror without upload times cannot break an
install (#135589). Plugin resolution is unchanged by this: core's exact pins stay put, and a plugin
may move a transitive core package within core's declared ranges
(`tests/pm/test_workspace_build_inputs.py::test_plugin_can_move_compatible_transitive_but_not_exact_requirement`).
Plugin `python_dependencies` follow the plugin's own policy. Teknium's rulings: "plugins dont have to abide by our 14 day rule … Only hermes'
dependencies themselves have to"; dates are checked by us, not users; pinned deps need >3 days.

## The lock check runs against the lock's own index (CN, 2026-10-20)

uv reuses an existing lock only when the index the lock was resolved from is among the configured
indexes, compared as a URL string. A mirror whose URL differs from the lock's by a trailing slash —
pip's `index-url` conventionally ends in `/simple/` — is a *different* index to uv, so
`uv lock --check` re-resolves and then reports a lock that is in fact current ("the lockfile needs
to be updated"). The re-resolution differs from the lock in that URL string alone, and every
install checks the lock before syncing, so a domestic mirror made every `hermes pm install` fail.

`PythonEnvironment.check_lock` therefore asks about the index the lock itself records
(`pm/environment.py::_lock_registry`), not the one this machine is configured for: the question the
check answers is whether the lock still matches the manifest, and the configured mirror must not
decide it. A lock that mixes several registries cannot be checked against a single index, so
those keep the configured one. Locking (`pm lock`) still resolves against the configured index, so
a relock keeps pinning the lock to the local mirror.

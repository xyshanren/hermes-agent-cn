#!/usr/bin/env python3
"""Routing Rule Manager Tool — Agent-Managed Routing Rule Inspection & Patches.

CAND-080 layer 1 + layer 1.1: lets the agent inspect the routing-rule
registry, queue *proposed* patches, and (with explicit user
confirmation) apply a queued patch to ``config.yaml``.

The pending queue (``~/.hermes/routing_patches/pending/``) is the
default landing zone for any patch the agent wants to propose.
``atomic_json_write`` (utils) makes the queue write crash-safe — a
crash mid-write can never corrupt the queue. **No** config.yaml or
runtime routing state is mutated automatically: applying a pending
patch is a user-confirmed step, the same way ``skill_manage(action=patch)``
leaves the skill file in a proposed state until the agent (or a
downstream tool) actually loads it.

Why this shape
--------------
- **CAND-085 4 铁律** (cross-project design law) says hermes-agent-cn
  must not write back to its own profile. Routing rules live in
  ``config.yaml::model_routing.rules``; if this tool auto-applied,
  every agent feedback round would silently rewrite user config (the
  same silent-data-loss class as K-2 ``call_llm`` and CAND-083
  ``custom_providers`` preservation). The pending-queue + explicit
  ``confirmed=True`` shape makes the human-in-the-loop the **only**
  way a patch lands in ``config.yaml``.
- The registry itself (``agent.routing_decision.KNOWN_RULES``) was
  added in CAND-080 layer 2. Layer 1 doesn't redefine the schema — it
  just exposes the schema to the agent so a feedback loop can ask
  "what's the right shape for a ``fallback_chain`` patch?" before
  queueing one. Layer 1.1 re-uses the same ``params_schema`` on
  apply so a rule that evolved between queue and apply fails-fast
  instead of silently reshaping the patch.
- Layer 1.1 re-validates at apply time (1:1 with layer 1's
  pre-queue validation) so a stale patch (rule deleted from
  ``KNOWN_RULES``) or a drifted schema surfaces as a clear error
  before any ``config.yaml`` write.

Actions
-------
- ``list``   — return every entry in :data:`KNOWN_RULES` (family name,
               description, owner, params schema).
- ``get``    — return a single entry by ``rule_id``.
- ``patch``  — validate ``params`` against the rule's
               ``params_schema`` (presence + type-hint) and write a
               pending patch record. Returns the patch id and the
               resolved target file path so the caller can show the
               user "queued patch #X at path Y".
- ``apply``  — load a queued patch by ``patch_id``, re-validate it
               against the *current* ``KNOWN_RULES`` + schema, and
               atomically write
               ``config.yaml::model_routing.rules[rule_id]``. Requires
               ``confirmed=True`` (default ``False``). On success the
               patch is moved from ``pending/`` to ``applied/`` (the
               applied file carries ``applied_at_unix`` + the original
               ``patch_id`` for traceability — read-only history).
               Layer 1.1 of CAND-080.
"""

from __future__ import annotations

import json
import logging
import re
import time
import uuid
from pathlib import Path
from typing import Any, Dict, Optional

from agent.routing_decision import KNOWN_RULES, RuleSpec
from hermes_constants import get_hermes_home
from utils import atomic_json_write

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


_TYPE_HINT_VALIDATORS: Dict[str, type] = {
    "int": int,
    "float": float,
    "str": str,
    "bool": bool,
}


def _pending_dir() -> Path:
    """Return (and create) the per-user pending-patches directory.

    Resolved under ``$HERMES_HOME`` so a symlinked / git-tracked
    ``~/.hermes`` is honored — the same behavior as
    ``skill_manager_tool``'s ``_find_skill``.
    """
    base = Path(get_hermes_home()) / "routing_patches" / "pending"
    base.mkdir(parents=True, exist_ok=True)
    return base


def _applied_dir() -> Path:
    """Return (and create) the per-user applied-patches directory.

    Applied patches are *moved* (not copied) from
    :func:`_pending_dir` to here on a successful apply, so the
    queue-vs-history split is observable from the filesystem alone —
    no DB needed. CAND-085 铁律 1 (可观测): every applied patch leaves
    a permanent ``applied/<ts>-<uuid>.json`` trail carrying the
    original ``patch_id`` and the ``applied_at_unix`` timestamp.
    """
    base = Path(get_hermes_home()) / "routing_patches" / "applied"
    base.mkdir(parents=True, exist_ok=True)
    return base


def _find_pending_patch(patch_id: str) -> Optional[Path]:
    """Return the path of the pending patch file carrying ``patch_id``,
    or ``None`` when no pending patch matches.

    Scans the pending dir linearly. The queue is small (one entry per
    agent feedback round) so an O(n) scan is the right shape — adding
    a manifest index would buy nothing and create a second write
    surface (more places to drift). ``Path.name`` sorting keeps the
    scan stable across calls so the result is deterministic.
    """
    if not patch_id:
        return None
    for path in sorted(_pending_dir().iterdir()):
        if not path.name.endswith(".json") or path.name.startswith("."):
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            # A half-written or corrupted pending file is not a
            # match — skip it. The user can clean up with a manual
            # ``rm`` if it sticks around.
            continue
        if isinstance(data, dict) and data.get("patch_id") == patch_id:
            return path
    return None


def _validate_params_against_schema(
    rule_id: str,
    spec: RuleSpec,
    params: Dict[str, Any],
) -> Optional[str]:
    """Return ``None`` when ``params`` satisfies ``spec.params_schema``,
    or a human-readable error string when it does not.

    The schema is intentionally tiny (presence + type-hint) — the only
    consumer right now is the CAND-080 layer 1 patch machinery, and a
    full JSON Schema buys nothing for the 4-5 params we have. When a
    consumer needs richer validation (range / enum / format), swap
    this helper for a real schema and bump callers one at a time.
    """
    schema = spec.params_schema
    # 1) No unknown params — check this first so a typo like
    #    "chain_idx" surfaces as "unknown" rather than masking
    #    the real "missing chain_index" error. The writer's
    #    intent is usually clear; the front-end can re-prompt
    #    with the right key.
    unknown = [k for k in params if k not in schema]
    if unknown:
        return (
            f"rule '{rule_id}' patch has unknown params: {unknown!r}; "
            f"schema accepts {sorted(schema)}"
        )
    # 2) All declared params must be present.
    missing = [k for k in schema if k not in params]
    if missing:
        return (
            f"rule '{rule_id}' patch missing required params: "
            f"{missing!r}; schema requires {sorted(schema)}"
        )
    # 3) Type check each param against the schema's type-hint string.
    for key, value in params.items():
        hint = schema[key]
        validator = _TYPE_HINT_VALIDATORS.get(hint)
        if validator is None:
            # Unknown type-hint in the schema itself — treat as a
            # programmer error (the rule author should have picked from
            # _TYPE_HINT_VALIDATORS). Don't fail the patch; log it.
            logger.warning(
                "rule %r schema param %r has unknown type-hint %r; "
                "skipping type check (add to _TYPE_HINT_VALIDATORS)",
                rule_id, key, hint,
            )
            continue
        if isinstance(value, bool) and hint != "bool":
            # ``bool`` is a subclass of ``int`` in Python — a patch
            # that passes ``True`` for a param declared as ``int`` is
            # almost certainly a writer bug. Reject explicitly so the
            # front-end surfaces a clear message rather than silently
            # storing ``True``.
            return (
                f"rule '{rule_id}' param {key!r} is bool, schema "
                f"requires {hint}"
            )
        if not isinstance(value, validator):
            return (
                f"rule '{rule_id}' param {key!r} is "
                f"{type(value).__name__}, schema requires {hint}"
            )
    return None


def _spec_to_payload(spec: RuleSpec) -> Dict[str, Any]:
    """Serialize a RuleSpec to a JSON-friendly dict for tool return."""
    return {
        "rule_id": spec.rule_id,
        "description": spec.description,
        "owner": spec.owner,
        "params_schema": dict(spec.params_schema),
    }


def _next_patch_filename(now: float) -> str:
    """Build a sortable, collision-resistant filename for a pending patch.

    Pattern: ``<unix-ms>-<8-hex-of-uuid4>.json``. The uuid4 suffix is the
    tie-breaker so two patches written in the same millisecond don't
    overwrite each other; the millisecond prefix keeps ``ls``-sorted
    order matching the patch's *intent* (when the agent queued it).
    """
    suffix = uuid.uuid4().hex[:8]
    return f"{int(now * 1000):013d}-{suffix}.json"


# ---------------------------------------------------------------------------
# Public tool entry point
# ---------------------------------------------------------------------------


def routing_rule_manage(
    action: str,
    rule_id: Optional[str] = None,
    params: Optional[Dict[str, Any]] = None,
    patch_id: Optional[str] = None,
    confirmed: bool = False,
) -> str:
    """Inspect the routing-rule registry and queue / apply patches.

    Args:
        action: one of ``"list"`` / ``"get"`` / ``"patch"`` / ``"apply"``.
        rule_id: required for ``"get"`` and ``"patch"``.
        params: required for ``"patch"`` — must satisfy the rule's
            ``params_schema`` (see :data:`agent.routing_decision.KNOWN_RULES`).
        patch_id: required for ``"apply"`` — the id returned by an
            earlier ``"patch"`` call. Unknown / already-applied ids
            fail-fast (no silent re-apply).
        confirmed: required for ``"apply"`` — must be explicitly
            ``True`` to land a patch in ``config.yaml``. Defaults to
            ``False``; any value other than literal ``True`` is
            rejected. CAND-085 铁律 2+4 (no implicit write / fail-fast)
            + UX 倒退 1:1 with layer 1's explicit-write shape.

    Returns:
        JSON string. On success, the payload has ``{"success": True,
        ...}``; on failure, ``{"success": False, "error": "..."}``.
        The tool never raises — front-ends and tests consume the JSON
        string directly (same contract as ``skill_manage``).
    """
    if action == "list":
        return json.dumps(
            {
                "success": True,
                "rules": [_spec_to_payload(spec) for spec in KNOWN_RULES.values()],
            },
            ensure_ascii=False,
        )

    if action == "get":
        if not rule_id:
            return json.dumps(
                {"success": False, "error": "rule_id is required for 'get'"},
                ensure_ascii=False,
            )
        spec = KNOWN_RULES.get(rule_id)
        if spec is None:
            return json.dumps(
                {
                    "success": False,
                    "error": (
                        f"unknown rule_id {rule_id!r}; "
                        f"known: {sorted(KNOWN_RULES)}"
                    ),
                },
                ensure_ascii=False,
            )
        return json.dumps(
            {"success": True, "rule": _spec_to_payload(spec)},
            ensure_ascii=False,
        )

    if action == "patch":
        if not rule_id:
            return json.dumps(
                {"success": False, "error": "rule_id is required for 'patch'"},
                ensure_ascii=False,
            )
        if params is None or not isinstance(params, dict):
            return json.dumps(
                {"success": False, "error": "params (dict) is required for 'patch'"},
                ensure_ascii=False,
            )
        spec = KNOWN_RULES.get(rule_id)
        if spec is None:
            return json.dumps(
                {
                    "success": False,
                    "error": (
                        f"unknown rule_id {rule_id!r}; "
                        f"known: {sorted(KNOWN_RULES)}"
                    ),
                },
                ensure_ascii=False,
            )
        # 0 params-schema rules (e.g. ``vision_fallback_config``) can
        # still be patched to record the *fact* of the patch — params
        # is just the empty dict in that case.
        validation_error = _validate_params_against_schema(rule_id, spec, params)
        if validation_error is not None:
            return json.dumps(
                {"success": False, "error": validation_error},
                ensure_ascii=False,
            )
        # Write the patch record to the pending queue. ``atomic_json_write``
        # is the same shared helper the curator uses (commit 47e77ae16),
        # so a crash mid-write leaves no half-written file on disk.
        patch_id = uuid.uuid4().hex[:12]
        now = time.time()
        record = {
            "patch_id": patch_id,
            "queued_at_unix": now,
            "rule_id": rule_id,
            "params": dict(params),
            "schema_at_queue_time": dict(spec.params_schema),
            "description": spec.description,
            "owner": spec.owner,
        }
        target = _pending_dir() / _next_patch_filename(now)
        atomic_json_write(target, record)
        logger.info(
            "queued routing-rule patch %s for rule %r at %s",
            patch_id, rule_id, target,
        )
        return json.dumps(
            {
                "success": True,
                "patch_id": patch_id,
                "queued_path": str(target),
                "rule_id": rule_id,
                "params": dict(params),
                "message": (
                    "Patch queued. Apply is a user-confirmed step (out of "
                    "scope for CAND-080 layer 1; tracked in CAND-080 entry)."
                ),
            },
            ensure_ascii=False,
        )

    if action == "apply":
        # Layer 1.1: apply a queued patch to config.yaml. Order of
        # fail-fast checks matters — patch_id is checked before
        # confirmed so a caller who forgot both gets the more
        # specific "patch_id is required" error rather than the
        # generic "set confirmed=True" one.
        if not patch_id:
            return json.dumps(
                {"success": False, "error": "patch_id is required for 'apply'"},
                ensure_ascii=False,
            )
        if confirmed is not True:
            # UX 倒退 1:1 with layer 1 — the user must explicitly
            # opt-in. ``is True`` (not ``not confirmed``) so a JSON
            # string ``"true"`` / int ``1`` / list ``[True]`` from a
            # front-end typo can't slip past the gate. The cost of a
            # stricter check is one explicit ``True`` at every
            # call site; the cost of a looser check is a config
            # rewrite from a malformed payload.
            return json.dumps(
                {
                    "success": False,
                    "error": (
                        "apply is a config-writing step; set "
                        "confirmed=True to land this patch in config.yaml"
                    ),
                },
                ensure_ascii=False,
            )
        # 1) Read the patch file from the pending queue.
        pending_path = _find_pending_patch(patch_id)
        if pending_path is None:
            return json.dumps(
                {
                    "success": False,
                    "error": (
                        f"no pending patch with patch_id={patch_id!r}; "
                        "already applied or never queued"
                    ),
                },
                ensure_ascii=False,
            )
        try:
            record = json.loads(pending_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            return json.dumps(
                {
                    "success": False,
                    "error": (
                        f"pending patch {patch_id!r} at {pending_path} "
                        f"is unreadable: {exc!s}"
                    ),
                },
                ensure_ascii=False,
            )
        # 2) Re-validate the rule + params against the *current*
        # KNOWN_RULES (defensive: the rule could have been removed
        # in a newer commit, or its params_schema could have drifted
        # since the patch was queued).
        rec_rule_id = record.get("rule_id")
        rec_params = record.get("params")
        if not isinstance(rec_rule_id, str) or not isinstance(rec_params, dict):
            return json.dumps(
                {
                    "success": False,
                    "error": (
                        f"pending patch {patch_id!r} is malformed: "
                        f"rule_id/params not a string/dict"
                    ),
                },
                ensure_ascii=False,
            )
        spec = KNOWN_RULES.get(rec_rule_id)
        if spec is None:
            # Stale patch — the rule was removed from KNOWN_RULES
            # (e.g. via a routing_compaction step). CAND-080
            # compaction_review is the tool that surfaces such
            # orphans; without it the agent has no way to learn the
            # rule is gone.
            return json.dumps(
                {
                    "success": False,
                    "error": (
                        f"stale patch: rule_id {rec_rule_id!r} is no "
                        f"longer in KNOWN_RULES; run compaction_review "
                        f"first to retire queued patches for retired rules"
                    ),
                },
                ensure_ascii=False,
            )
        # Schema-drift guard: re-validate params against the *current*
        # schema. If the schema evolved (e.g. a new required param
        # was added) the patch would land in config.yaml with a
        # shape that no longer matches the runtime, so fail-fast
        # here. CAND-080 layer 1 queued with
        # ``schema_at_queue_time`` precisely so this re-validation
        # has a reference point — but the runtime check is the
        # canonical one, not the snapshot.
        validation_error = _validate_params_against_schema(
            rec_rule_id, spec, rec_params
        )
        if validation_error is not None:
            return json.dumps(
                {
                    "success": False,
                    "error": (
                        f"re-validation failed (schema may have drifted "
                        f"since queue): {validation_error}"
                    ),
                },
                ensure_ascii=False,
            )
        # 3) Atomic write of model_routing.rules[rule_id] into
        # config.yaml. We borrow :func:`hermes_cli.config.save_config`
        # directly — it already wraps atomic_yaml_write +
        # _CONFIG_LOCK + is_managed() check +
        # _preserve_env_ref_templates, so 0 new atomic-write surface
        # is introduced (CAND-085 铁律 4: 0 corrupt).
        # Local import: the tool module is imported by
        # ``agent/__init__.py`` early in the boot path, and pulling
        # ``hermes_cli.config`` at module load time would surface a
        # cyclic-init cost on every fresh process. The function is
        # needed only on apply, so defer to call time.
        from hermes_cli import config as _hermes_config

        current = _hermes_config.read_raw_config() or {}
        if not isinstance(current, dict):
            # Defensive: a corrupted config.yaml that returned a
            # non-dict at the top level. save_config would happily
            # overwrite it, so guard explicitly.
            return json.dumps(
                {
                    "success": False,
                    "error": (
                        f"config.yaml at {_hermes_config.get_config_path()} "
                        f"is malformed (top-level {type(current).__name__}); "
                        f"refusing to apply"
                    ),
                },
                ensure_ascii=False,
            )
        model_routing = current.get("model_routing")
        if not isinstance(model_routing, dict):
            model_routing = {}
        rules = model_routing.get("rules")
        if not isinstance(rules, dict):
            rules = {}
        now = time.time()
        rules[rec_rule_id] = {
            "params": dict(rec_params),
            "applied_at_unix": now,
            "patch_id": patch_id,
        }
        model_routing["rules"] = rules
        current["model_routing"] = model_routing
        _hermes_config.save_config(current)
        # 4) Move the patch from pending/ to applied/ *after* the
        # config write succeeded. Doing it last means a failed
        # apply leaves the patch in pending/ (re-tryable) and a
        # successful apply leaves a single applied/ record carrying
        # the patch_id + applied_at_unix (read-only history, 铁律 1
        # 可观测).
        #
        # The moved record gets 3 new fields so the applied/ file
        # is self-contained for audit (跟 task 3 CLI list/show/history
        # 1:1, 不需要再 cross-ref config.yaml):
        #   - ``applied_at_unix``   timestamp of the apply
        #   - ``config_section``    "model_routing.rules.<rule_id>"
        #   - ``applied_path``      relative to HERMES_HOME
        #
        # Path.replace is atomic on same-filesystem moves (both dirs
        # share the same parent), so a crash mid-move can never
        # leave the patch in both places.
        applied_path = _applied_dir() / pending_path.name
        if applied_path.exists():
            # Same-uuid filename collision would mean two patches
            # queued in the same millisecond with the same uuid4
            # suffix — astronomically unlikely but guarded. Suffix
            # the applied file with a counter so the apply still
            # succeeds (the patch_id in config.yaml is the
            # authoritative reference).
            stem = pending_path.stem
            counter = 2
            while True:
                candidate = _applied_dir() / f"{stem}-{counter}.json"
                if not candidate.exists():
                    applied_path = candidate
                    break
                counter += 1
        # Stamp the moved record with the apply-time audit fields
        # BEFORE the move so the file on disk is already correct
        # when the rename lands. ``replace`` is atomic; if it
        # succeeds the file is the stamped one, if it fails the
        # pending/ file is unchanged and we can re-try.
        record["applied_at_unix"] = now
        record["config_section"] = (
            f"model_routing.rules.{rec_rule_id}"
        )
        try:
            # Relative path for portability (moved records don't
            # pin a HERMES_HOME — useful when an operator tars
            # the applied/ dir to ship to a colleague).
            record["applied_path"] = str(
                applied_path.relative_to(Path(get_hermes_home()))
            )
        except ValueError:
            # Fall back to absolute when the path can't be made
            # relative (e.g. applied/ is on a different volume).
            record["applied_path"] = str(applied_path)
        # Re-write the (now-stamped) record to applied/ via
        # atomic_json_write so a half-written file can't poison
        # the audit trail, then remove the pending/ source.
        atomic_json_write(applied_path, record)
        pending_path.unlink()
        logger.info(
            "applied routing-rule patch %s for rule %r; "
            "config section model_routing.rules.%s updated, "
            "moved %s -> %s",
            patch_id, rec_rule_id, rec_rule_id, pending_path, applied_path,
        )
        return json.dumps(
            {
                "success": True,
                "patch_id": patch_id,
                "rule_id": rec_rule_id,
                "applied_path": str(applied_path),
                "config_section": f"model_routing.rules.{rec_rule_id}",
                "applied_at_unix": now,
                "message": (
                    f"Patch {patch_id} applied to "
                    f"model_routing.rules.{rec_rule_id}"
                ),
            },
            ensure_ascii=False,
        )

    return json.dumps(
        {
            "success": False,
            "error": (
                f"Unknown action {action!r}. Use: list, get, patch, apply."
            ),
        },
        ensure_ascii=False,
    )


__all__ = [
    "routing_rule_manage",
]

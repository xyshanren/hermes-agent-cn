#!/usr/bin/env python3
"""Routing Rule Manager Tool — Agent-Managed Routing Rule Inspection & Patches.

CAND-080 layer 1: lets the agent inspect the routing-rule registry and
queue *proposed* patches. The patches are written to a per-user pending
directory (``~/.hermes/routing_patches/pending/``) using
:func:`utils.atomic_json_write` so a crash mid-write can never corrupt
the queue. **No** config.yaml or runtime routing state is mutated
automatically — applying a pending patch is a user-confirmed step, the
same way ``skill_manage(action=patch)`` leaves the skill file in a
proposed state until the agent (or a downstream tool) actually loads
it.

Why this shape
--------------
- **CAND-085 4 铁律** (cross-project design law) says hermes-agent-cn
  must not write back to its own profile. Routing rules live in
  ``config.yaml::model_routing.rules``; if this tool auto-applied,
  every agent feedback round would silently rewrite user config (the
  same silent-data-loss class as K-2 ``call_llm`` and CAND-083
  ``custom_providers`` preservation). The pending-queue shape makes the
  human-in-the-loop the **only** way a patch lands in ``config.yaml``.
- The registry itself (``agent.routing_decision.KNOWN_RULES``) was
  added in CAND-080 layer 2. Layer 1 doesn't redefine the schema — it
  just exposes the schema to the agent so a feedback loop can ask
  "what's the right shape for a ``fallback_chain`` patch?" before
  queueing one. This matches how ``skill_manage`` reads
  ``SKILL.md``-shaped skills but doesn't redefine the skill schema.
- CAND-080 layer 1.1 (future) will add an apply step (``hermes routing
  patches apply`` or an apply-on-restart hook) — out of scope for this
  commit.

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
) -> str:
    """Inspect the routing-rule registry and queue proposed patches.

    Args:
        action: one of ``"list"`` / ``"get"`` / ``"patch"``.
        rule_id: required for ``"get"`` and ``"patch"``.
        params: required for ``"patch"`` — must satisfy the rule's
            ``params_schema`` (see :data:`agent.routing_decision.KNOWN_RULES`).

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

    return json.dumps(
        {
            "success": False,
            "error": (
                f"Unknown action {action!r}. Use: list, get, patch."
            ),
        },
        ensure_ascii=False,
    )


__all__ = [
    "routing_rule_manage",
]

#!/usr/bin/env python3
"""Routing Patch Compaction Tool — Read-Only Review of Pending Patches.

CAND-081 Compaction 工具. Borrows the curator's *consolidation* pattern
(line 320+ of ``agent/curator.py`` — the curator's "UMBRELLA-BUILDING
consolidation pass") and applies it to the routing-rule pending
queue at ``~/.hermes/routing_patches/pending/``.

The tool is **read-only** by design:

- It scans the pending directory and groups patches by ``rule_id``,
  detecting the three patterns the curator prompt cares about
  (duplicates, stale rule_ids, ripe consolidation clusters).
- It writes *nothing* back. No auto-apply, no auto-delete, no
  auto-merge. The 4 铁律 of CAND-085 (cross-project design law) say
  hermes-agent-cn must not write back to its own profile; routing
  rules live in ``config.yaml::model_routing.rules`` and any auto-mutate
  there is the same silent-data-loss class as K-2 ``call_llm`` and
  CAND-083 ``custom_providers`` preservation.
- The same way mavis' ``compaction`` skill runs as a quarterly
  read-only audit cron (``hermes-cn-quarterly-borrow-audit``), this
  tool returns a structured report and lets a downstream consumer
  (or human reviewer) act on it.

Why a separate tool from ``routing_rule_manage``
------------------------------------------------
``routing_rule_manage`` is the *write* path: it validates params
against the schema and writes a pending record. CAND-081 is the
*read* path: it inspects a *collection* of pending records and emits
a human-readable report. The split mirrors how curator's prompt
(``agent/curator.py:320+``) and ``skill_manage`` are independent —
the curator scans skills and decides what to mutate, then invokes
``skill_manage`` to actually do the work; here the compaction tool
scans the queue and the user/agent decides what to do next (out of
scope for CAND-081 — apply is CAND-080 layer 1.1).

Actions
-------
- ``review`` — return a JSON report with three sections:
    ``duplicates`` (same rule_id + same params queued more than once),
    ``stale`` (rule_id no longer in :data:`KNOWN_RULES`),
    ``clusters`` (rule_id with >=2 pending patches, ready to
    consolidate into a single authoritative patch).
  No mutation; safe to call repeatedly.
"""

from __future__ import annotations

import json
import logging
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List

from agent.routing_decision import KNOWN_RULES
from hermes_constants import get_hermes_home

logger = logging.getLogger(__name__)


def _pending_dir() -> Path:
    """Return the per-user pending-patches directory.

    Resolved under ``$HERMES_HOME`` so a symlinked / git-tracked
    ``~/.hermes`` is honored (same behavior as
    ``routing_rule_manager_tool._pending_dir``).
    """
    base = Path(get_hermes_home()) / "routing_patches" / "pending"
    if not base.exists():
        # Idempotent — never raise on a fresh install. A scan of a
        # non-existent directory is a legitimate "no patches yet" state.
        return base
    return base


def _read_all_pending() -> List[Dict[str, Any]]:
    """Load every ``*.json`` record in the pending directory.

    Skips non-JSON files (e.g. a stray ``.tmp-…`` atomic-write
    leftover is a real risk because the writer cleans up but a
    power-cut mid-rename can leave one). Tolerant of malformed JSON
    — a single bad record must not break the whole review.
    """
    pending = _pending_dir()
    records: List[Dict[str, Any]] = []
    if not pending.exists():
        return records
    for entry in sorted(pending.iterdir()):
        if not entry.is_file() or entry.suffix != ".json":
            continue
        try:
            records.append(json.loads(entry.read_text(encoding="utf-8")))
        except (OSError, ValueError) as exc:
            # Defensive: a single corrupt record must not crash the
            # review. The curator's own scan is similarly tolerant.
            logger.warning("skipping malformed pending record %s: %s", entry, exc)
    return records


def _detect_duplicates(records: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Return one entry per (rule_id, params) pair with count > 1.

    A duplicate is *informational* — the user may want to dedupe
    before applying, or the agent may want to confirm whether the
    second patch supersedes the first. The tool never deletes.
    """
    by_key: Dict[tuple, List[Dict[str, Any]]] = defaultdict(list)
    for record in records:
        # Use sorted-tuple of params for hashability; order of keys
        # in the patch dict is irrelevant.
        params_key = tuple(sorted(record.get("params", {}).items()))
        by_key[(record.get("rule_id"), params_key)].append(record)
    out: List[Dict[str, Any]] = []
    for (rule_id, params_key), group in by_key.items():
        if len(group) > 1:
            out.append(
                {
                    "rule_id": rule_id,
                    "params": dict(params_key),
                    "patch_ids": [r.get("patch_id") for r in group],
                    "queued_paths": [r.get("queued_path") for r in group],
                    "count": len(group),
                }
            )
    return out


def _detect_stale(records: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Return one entry per record whose rule_id is no longer in
    :data:`KNOWN_RULES`.

    A patch becomes stale when the registry evolves (rule_id renamed
    or removed). CAND-080 layer 1.1's apply step must skip these
    (and surface them to the user) — this report makes the staleness
    visible before the apply attempt.
    """
    out: List[Dict[str, Any]] = []
    for record in records:
        rule_id = record.get("rule_id")
        if rule_id not in KNOWN_RULES:
            out.append(
                {
                    "rule_id": rule_id,
                    "patch_id": record.get("patch_id"),
                    "queued_path": record.get("queued_path"),
                    "reason": (
                        f"rule_id {rule_id!r} not in KNOWN_RULES "
                        f"(known: {sorted(KNOWN_RULES)})"
                    ),
                }
            )
    return out


def _detect_clusters(records: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Return one entry per rule_id with >=2 *distinct* pending params.

    A cluster signals ripe consolidation — multiple distinct
    ``params`` for the same rule (e.g. ``fallback_chain[0]`` and
    ``fallback_chain[1]`` queued close together). The user's review
    might collapse them to a single canonical patch, or pick the
    latest. The tool never collapses automatically — the curator
    prompt's umbrella-building is the model here, and the curator
    only acts on user-confirmed signals.

    Duplicates (same params, different patch_ids) are *not* clusters
    — they're reported separately in the ``duplicates`` section. A
    duplicate pair with no distinct sibling is exactly one canonical
    config, not multiple competing ones, so the consolidation question
    doesn't apply.
    """
    by_rule: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for record in records:
        by_rule[record.get("rule_id")].append(record)
    out: List[Dict[str, Any]] = []
    for rule_id, group in by_rule.items():
        # Skip rule_ids already flagged as stale — those are
        # reported separately and aren't consolidation candidates.
        if rule_id not in KNOWN_RULES:
            continue
        distinct_params = {tuple(sorted(r.get("params", {}).items())) for r in group}
        # Cluster iff the rule has 2+ *distinct* params. Pure
        # duplicates (one distinct param across N patches) are
        # surfaced as ``duplicates`` only.
        if len(distinct_params) >= 2:
            out.append(
                {
                    "rule_id": rule_id,
                    "patch_count": len(group),
                    "distinct_params_count": len(distinct_params),
                    "patch_ids": [r.get("patch_id") for r in group],
                    "queued_paths": [r.get("queued_path") for r in group],
                }
            )
    return out


# ---------------------------------------------------------------------------
# Public tool entry point
# ---------------------------------------------------------------------------


def routing_compaction_review() -> str:
    """Return a read-only JSON report over the pending patch queue.

    Always returns JSON (never raises) so the front-end and tests can
    consume the same shape. The same contract as
    ``routing_rule_manage`` and ``skill_manage``.
    """
    records = _read_all_pending()
    duplicates = _detect_duplicates(records)
    stale = _detect_stale(records)
    clusters = _detect_clusters(records)
    summary = {
        "total_pending": len(records),
        "duplicates_count": len(duplicates),
        "stale_count": len(stale),
        "clusters_count": len(clusters),
    }
    return json.dumps(
        {
            "success": True,
            "summary": summary,
            "duplicates": duplicates,
            "stale": stale,
            "clusters": clusters,
            "message": (
                "Read-only review. Apply is out of scope for CAND-081; "
                "tracked under CAND-080 layer 1.1 (apply mechanism)."
            ),
        },
        ensure_ascii=False,
    )


__all__ = [
    "routing_compaction_review",
]

"""CAND-080 layer 1 + 1.1: routing rule manager tool unit tests.

Covers ``tools.routing_rule_manager_tool.routing_rule_manage`` — the
agent-facing surface for inspecting :data:`agent.routing_decision.KNOWN_RULES`,
queuing proposed patches to ``~/.hermes/routing_patches/pending/``,
and (layer 1.1) applying a queued patch to ``config.yaml`` with
explicit user confirmation.

These tests are pure-Python (no network, no LLM, no WSL) and use a
``tmp_path`` patch on the pending-dir helper so the queue writes never
escape the test sandbox. Apply tests additionally redirect
``$HERMES_HOME`` to a ``tmp_path`` via
:func:`hermes_constants.set_hermes_home_override` so the
``config.yaml`` read+write roundtrip never touches the user's real
``~/.hermes``.
"""

import json
import os
from pathlib import Path
from unittest.mock import patch as _patch

import pytest

from tools import routing_rule_manager_tool as rrm


# ── Fixtures ────────────────────────────────────────────────────────────


@pytest.fixture
def fake_pending_dir(tmp_path, monkeypatch):
    """Redirect the pending-patches dir to ``tmp_path`` so writes never
    touch ``~/.hermes/routing_patches/pending/`` in the test sandbox.

    Mirrors the cherry-pick split-bug-class hygiene: every test that
    queues a patch gets a clean directory and a guaranteed no-leftover
    state.
    """
    fake = tmp_path / "routing_patches" / "pending"
    fake.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(rrm, "_pending_dir", lambda: fake)
    return fake


@pytest.fixture
def fake_hermes_home(tmp_path, monkeypatch):
    """Full sandbox for apply tests: redirect ``$HERMES_HOME`` to
    ``tmp_path`` so the ``config.yaml`` read+write roundtrip is fully
    contained, and create empty ``pending/`` + ``applied/`` dirs under
    it. Clears ``hermes_cli.config._RAW_CONFIG_CACHE`` on enter and
    exit so cross-test cache pollution can't poison a follow-up test
    (the cache is module-level state, keyed on absolute path).

    Returns a dict with ``tmp_path``, ``pending``, ``applied`` and the
    ``config_path`` so tests can pre-seed ``config.yaml`` content and
    assert post-apply state.
    """
    from hermes_constants import (
        reset_hermes_home_override,
        set_hermes_home_override,
    )
    from hermes_cli import config as _hc

    pending = tmp_path / "routing_patches" / "pending"
    pending.mkdir(parents=True, exist_ok=True)
    applied = tmp_path / "routing_patches" / "applied"
    applied.mkdir(parents=True, exist_ok=True)

    token = set_hermes_home_override(str(tmp_path))
    monkeypatch.setattr(rrm, "_pending_dir", lambda: pending)
    monkeypatch.setattr(rrm, "_applied_dir", lambda: applied)
    _hc._RAW_CONFIG_CACHE.clear()
    try:
        yield {
            "tmp_path": tmp_path,
            "pending": pending,
            "applied": applied,
            "config_path": tmp_path / "config.yaml",
        }
    finally:
        _hc._RAW_CONFIG_CACHE.clear()
        reset_hermes_home_override(token)


def _queue_patch(
    rule_id: str, params: dict, pending: Path
) -> dict:
    """Helper: queue a patch via the layer 1 tool, return the parsed
    payload. Lets apply tests skip the layer-1 surface and start from
    a known-pending state.
    """
    payload = json.loads(
        rrm.routing_rule_manage(
            action="patch", rule_id=rule_id, params=params
        )
    )
    assert payload["success"] is True, payload
    return payload


# ── list / get ─────────────────────────────────────────────────────────


class TestListAndGet:
    def test_list_returns_every_known_rule(self):
        payload = json.loads(rrm.routing_rule_manage(action="list"))
        assert payload["success"] is True
        rule_ids = {r["rule_id"] for r in payload["rules"]}
        # KNOWN_RULES is the source of truth; pin the set so a future
        # registry change forces a test update.
        assert rule_ids == {
            "fallback_chain",
            "cost_aware_fallback",
            "vision_fallback_config",
            "vision_fallback_chain",
            "payment_fallback",
            "main_agent_model_fallback",
        }

    def test_list_includes_schema_per_rule(self):
        payload = json.loads(rrm.routing_rule_manage(action="list"))
        by_id = {r["rule_id"]: r for r in payload["rules"]}
        spec = by_id["fallback_chain"]
        assert spec["params_schema"] == {"chain_index": "int", "provider": "str"}
        assert spec["owner"].startswith("agent.")
        assert spec["description"]  # non-empty

    def test_get_returns_one_rule(self):
        payload = json.loads(
            rrm.routing_rule_manage(action="get", rule_id="fallback_chain")
        )
        assert payload["success"] is True
        assert payload["rule"]["rule_id"] == "fallback_chain"
        assert payload["rule"]["params_schema"] == {
            "chain_index": "int",
            "provider": "str",
        }

    def test_get_unknown_rule_fails(self):
        payload = json.loads(
            rrm.routing_rule_manage(action="get", rule_id="nonexistent")
        )
        assert payload["success"] is False
        assert "unknown rule_id" in payload["error"]
        # Error message should list the known set so the front-end can
        # offer a dropdown without a second roundtrip.
        assert "fallback_chain" in payload["error"]

    def test_get_missing_rule_id_fails(self):
        payload = json.loads(rrm.routing_rule_manage(action="get"))
        assert payload["success"] is False
        assert "rule_id is required" in payload["error"]


# ── patch: validation ─────────────────────────────────────────────────


class TestPatchValidation:
    """Validation runs *before* the queue write so a malformed patch
    never leaves a half-written record on disk.
    """

    def test_patch_missing_rule_id_fails(self, fake_pending_dir):
        payload = json.loads(
            rrm.routing_rule_manage(
                action="patch",
                params={"chain_index": 0, "provider": "kimi"},
            )
        )
        assert payload["success"] is False
        assert "rule_id is required" in payload["error"]
        # Defensive: nothing should have been written to the queue.
        assert list(fake_pending_dir.iterdir()) == []

    def test_patch_unknown_rule_fails(self, fake_pending_dir):
        payload = json.loads(
            rrm.routing_rule_manage(
                action="patch",
                rule_id="nonexistent",
                params={"chain_index": 0},
            )
        )
        assert payload["success"] is False
        assert "unknown rule_id" in payload["error"]
        assert list(fake_pending_dir.iterdir()) == []

    def test_patch_missing_params_dict_fails(self, fake_pending_dir):
        payload = json.loads(
            rrm.routing_rule_manage(action="patch", rule_id="fallback_chain")
        )
        assert payload["success"] is False
        assert "params (dict) is required" in payload["error"]
        assert list(fake_pending_dir.iterdir()) == []

    def test_patch_missing_required_param_fails(self, fake_pending_dir):
        """``fallback_chain`` requires both ``chain_index`` and
        ``provider`` — a patch missing ``provider`` must fail-fast.
        """
        payload = json.loads(
            rrm.routing_rule_manage(
                action="patch",
                rule_id="fallback_chain",
                params={"chain_index": 0},
            )
        )
        assert payload["success"] is False
        assert "missing required params" in payload["error"]
        assert "'provider'" in payload["error"]
        assert list(fake_pending_dir.iterdir()) == []

    def test_patch_unknown_param_fails(self, fake_pending_dir):
        """Catches typos like ``chain_idx`` (writer) before apply."""
        payload = json.loads(
            rrm.routing_rule_manage(
                action="patch",
                rule_id="fallback_chain",
                params={
                    "chain_idx": 0,  # typo
                    "provider": "kimi",
                },
            )
        )
        assert payload["success"] is False
        assert "unknown params" in payload["error"]
        assert "'chain_idx'" in payload["error"]
        assert list(fake_pending_dir.iterdir()) == []

    def test_patch_wrong_type_fails(self, fake_pending_dir):
        """``chain_index`` is declared as ``"int"``; a string value must
        be rejected with a clear message (not a TypeError from the
        atomic writer).
        """
        payload = json.loads(
            rrm.routing_rule_manage(
                action="patch",
                rule_id="fallback_chain",
                params={"chain_index": "zero", "provider": "kimi"},
            )
        )
        assert payload["success"] is False
        assert "schema requires int" in payload["error"]
        assert list(fake_pending_dir.iterdir()) == []

    def test_patch_bool_rejected_for_int_param(self, fake_pending_dir):
        """``bool`` is a subclass of ``int`` in Python; the validator
        must catch ``True`` for an int-declared param so a writer
        bug surfaces clearly.
        """
        payload = json.loads(
            rrm.routing_rule_manage(
                action="patch",
                rule_id="fallback_chain",
                params={"chain_index": True, "provider": "kimi"},
            )
        )
        assert payload["success"] is False
        assert "is bool, schema requires int" in payload["error"]
        assert list(fake_pending_dir.iterdir()) == []


# ── patch: queue write ─────────────────────────────────────────────────


class TestPatchQueueWrite:
    def test_valid_patch_writes_record(self, fake_pending_dir):
        payload = json.loads(
            rrm.routing_rule_manage(
                action="patch",
                rule_id="fallback_chain",
                params={"chain_index": 0, "provider": "kimi"},
            )
        )
        assert payload["success"] is True
        assert payload["rule_id"] == "fallback_chain"
        assert payload["params"] == {"chain_index": 0, "provider": "kimi"}
        assert "patch_id" in payload and len(payload["patch_id"]) == 12
        # The queue file should exist exactly once.
        files = list(fake_pending_dir.iterdir())
        assert len(files) == 1
        record = json.loads(files[0].read_text(encoding="utf-8"))
        assert record["rule_id"] == "fallback_chain"
        assert record["params"] == {"chain_index": 0, "provider": "kimi"}
        # The queue record snapshots the schema at queue time so an
        # apply step can detect schema drift between queue and apply.
        assert record["schema_at_queue_time"] == {
            "chain_index": "int",
            "provider": "str",
        }
        assert record["owner"].startswith("agent.")

    def test_empty_params_patch_writes_for_no_param_rule(
        self, fake_pending_dir
    ):
        """``vision_fallback_config`` declares no params. A patch
        (even with empty ``params={}``) is a valid signal that the
        rule fired and the agent wants to log it.
        """
        payload = json.loads(
            rrm.routing_rule_manage(
                action="patch",
                rule_id="vision_fallback_config",
                params={},
            )
        )
        assert payload["success"] is True
        assert list(fake_pending_dir.iterdir()), "patch should be queued"

    def test_two_patches_get_distinct_filenames(self, fake_pending_dir):
        """The uuid suffix must be present so two patches written in
        the same millisecond don't overwrite each other.
        """
        first = json.loads(
            rrm.routing_rule_manage(
                action="patch",
                rule_id="fallback_chain",
                params={"chain_index": 0, "provider": "kimi"},
            )
        )
        second = json.loads(
            rrm.routing_rule_manage(
                action="patch",
                rule_id="fallback_chain",
                params={"chain_index": 1, "provider": "anthropic"},
            )
        )
        assert first["patch_id"] != second["patch_id"]
        # Two files exist (no overwrite).
        files = sorted(p.name for p in fake_pending_dir.iterdir())
        assert len(files) == 2
        assert files[0] != files[1]

    def test_atomic_write_leaves_no_tmp_file(self, fake_pending_dir):
        """``atomic_json_write`` must clean up its temp file on success;
        otherwise ``hermes routing patches list`` would see noise.
        """
        rrm.routing_rule_manage(
            action="patch",
            rule_id="fallback_chain",
            params={"chain_index": 0, "provider": "kimi"},
        )
        all_files = list(fake_pending_dir.iterdir())
        # Exactly one record file, no .tmp-… siblings.
        assert all(
            not p.name.startswith(".") for p in all_files
        ), f"atomic write left hidden file: {[p.name for p in all_files]}"
        assert len(all_files) == 1
        assert all_files[0].name.endswith(".json")


# ── dispatch ───────────────────────────────────────────────────────────


class TestDispatch:
    def test_unknown_action_fails(self, fake_pending_dir):
        payload = json.loads(rrm.routing_rule_manage(action="delete"))
        assert payload["success"] is False
        assert "Unknown action" in payload["error"]
        assert "list" in payload["error"]
        assert "get" in payload["error"]
        assert "patch" in payload["error"]
        # ``delete`` is not a layer-1 action (out of scope); the
        # pending queue must not receive a record.
        assert list(fake_pending_dir.iterdir()) == []


# ── apply: fail-fast gates (layer 1.1) ──────────────────────────────────
#
# CAND-080 layer 1.1 introduces ``action="apply"`` with
# ``confirmed=False`` default (UX 倒退 1:1). These tests pin the
# fail-fast order:
#   1. ``patch_id`` required (most specific)
#   2. ``confirmed=True`` required (safety check)
#   3. patch must exist in pending/
#   4. ``rule_id`` must still be in ``KNOWN_RULES`` (stale patch)
#   5. ``params`` must still satisfy the *current* schema (drift guard)
# Each gate is a separate test so a regression on any one of them
# surfaces a specific failure instead of a generic "apply broke".


class TestApplyFailFast:
    def test_apply_without_confirmed_fails(self, fake_hermes_home):
        """``confirmed`` defaults to ``False``; any non-True value
        (including a string ``"true"`` or int ``1``) is rejected so a
        front-end typo can't sneak past the gate.
        """
        queued = _queue_patch(
            "fallback_chain",
            {"chain_index": 0, "provider": "kimi"},
            fake_hermes_home["pending"],
        )
        payload = json.loads(
            rrm.routing_rule_manage(
                action="apply",
                patch_id=queued["patch_id"],
                # confirmed omitted → default False
            )
        )
        assert payload["success"] is False
        assert "confirmed=True" in payload["error"]
        # Nothing was written to config.yaml.
        assert not fake_hermes_home["config_path"].exists()
        # The patch is still in pending/ — apply failure is fully
        # reversible.
        assert list(fake_hermes_home["pending"].iterdir())
        assert list(fake_hermes_home["applied"].iterdir()) == []

    def test_apply_with_truthy_non_bool_fails(self, fake_hermes_home):
        """Catches JSON-typed ``"true"`` / ``1`` that some front-ends
        might pass as a string or int — only literal Python
        ``True`` lands the patch.
        """
        queued = _queue_patch(
            "fallback_chain",
            {"chain_index": 0, "provider": "kimi"},
            fake_hermes_home["pending"],
        )
        for sneaky in ("true", 1, "True", [True], {"yes": True}):
            payload = json.loads(
                rrm.routing_rule_manage(
                    action="apply",
                    patch_id=queued["patch_id"],
                    confirmed=sneaky,
                )
            )
            assert payload["success"] is False, (
                f"sneaky confirmed={sneaky!r} should have failed"
            )
            assert "confirmed=True" in payload["error"]

    def test_apply_missing_patch_id_fails(self, fake_hermes_home):
        """Checked before ``confirmed`` so a caller who forgot both
        gets the more specific error.
        """
        payload = json.loads(
            rrm.routing_rule_manage(action="apply", confirmed=True)
        )
        assert payload["success"] is False
        assert "patch_id is required" in payload["error"]
        # Defensive: no .tmp file residue from a half-started apply.
        assert not fake_hermes_home["config_path"].exists()

    def test_apply_unknown_patch_id_fails(self, fake_hermes_home):
        """patch_id that was never queued (or already applied) is
        rejected without touching config.yaml. Catches the
        front-end scenario of retrying an apply after the user
        reloaded the page.
        """
        payload = json.loads(
            rrm.routing_rule_manage(
                action="apply",
                patch_id="nonexistent-1234567890ab",
                confirmed=True,
            )
        )
        assert payload["success"] is False
        assert "no pending patch" in payload["error"]
        assert "nonexistent-1234567890ab" in payload["error"]
        assert not fake_hermes_home["config_path"].exists()

    def test_double_apply_fails_idempotently(self, fake_hermes_home):
        """Apply is one-shot: after a successful apply the patch is in
        ``applied/``, not ``pending/``, so a retry finds nothing and
        fails-fast. CAND-085 铁律 1 (可观测): a re-applied patch
        would silently overwrite the prior applied_at_unix + patch_id
        record, losing the audit trail.
        """
        queued = _queue_patch(
            "fallback_chain",
            {"chain_index": 0, "provider": "kimi"},
            fake_hermes_home["pending"],
        )
        # First apply succeeds.
        first = json.loads(
            rrm.routing_rule_manage(
                action="apply",
                patch_id=queued["patch_id"],
                confirmed=True,
            )
        )
        assert first["success"] is True, first
        # Second apply with the same patch_id finds nothing in
        # pending/.
        second = json.loads(
            rrm.routing_rule_manage(
                action="apply",
                patch_id=queued["patch_id"],
                confirmed=True,
            )
        )
        assert second["success"] is False
        assert "no pending patch" in second["error"]
        # Pending is empty; applied carries the one record.
        assert list(fake_hermes_home["pending"].iterdir()) == []
        applied_files = list(fake_hermes_home["applied"].iterdir())
        assert len(applied_files) == 1

    def test_stale_patch_rule_removed_from_registry_fails(
        self, fake_hermes_home, monkeypatch
    ):
        """A patch queued for a rule that's since been removed from
        ``KNOWN_RULES`` (e.g. a downstream ``routing_compaction``
        pass retired the rule) must fail-fast. CAND-080
        compaction_review is the operator-facing tool for retiring
        such orphans; the error message tells the operator exactly
        which step to take.
        """
        from agent import routing_decision

        queued = _queue_patch(
            "vision_fallback_config",
            {},
            fake_hermes_home["pending"],
        )
        # Simulate a future commit removing this rule.
        monkeypatch.setattr(
            routing_decision,
            "KNOWN_RULES",
            {
                k: v
                for k, v in routing_decision.KNOWN_RULES.items()
                if k != "vision_fallback_config"
            },
        )
        # The tool imports ``KNOWN_RULES`` directly into its module
        # namespace at import time, so re-patch the tool's view too.
        monkeypatch.setattr(rrm, "KNOWN_RULES", routing_decision.KNOWN_RULES)
        payload = json.loads(
            rrm.routing_rule_manage(
                action="apply",
                patch_id=queued["patch_id"],
                confirmed=True,
            )
        )
        assert payload["success"] is False
        assert "stale patch" in payload["error"]
        assert "compaction_review" in payload["error"]
        assert "vision_fallback_config" in payload["error"]
        # Nothing landed in config.yaml or applied/.
        assert not fake_hermes_home["config_path"].exists()
        assert list(fake_hermes_home["pending"].iterdir())
        assert list(fake_hermes_home["applied"].iterdir()) == []

    def test_schema_drift_since_queue_fails(self, fake_hermes_home, monkeypatch):
        """A patch queued under the old schema (e.g. fallback_chain
        required only ``chain_index``) must NOT be re-validated
        against a hypothetical older schema and silently land in
        config.yaml when the current schema requires more params.
        The current ``spec.params_schema`` is the canonical check.
        """
        from agent import routing_decision

        queued = _queue_patch(
            "fallback_chain",
            {"chain_index": 0, "provider": "kimi"},
            fake_hermes_home["pending"],
        )
        # Simulate a schema evolution: future commit tightens
        # fallback_chain to require a third param.
        original_spec = routing_decision.KNOWN_RULES["fallback_chain"]
        evolved_spec = routing_decision.RuleSpec(
            rule_id=original_spec.rule_id,
            description=original_spec.description,
            owner=original_spec.owner,
            params_schema={
                **original_spec.params_schema,
                "tier": "str",  # new required param
            },
        )
        new_known = dict(routing_decision.KNOWN_RULES)
        new_known["fallback_chain"] = evolved_spec
        monkeypatch.setattr(routing_decision, "KNOWN_RULES", new_known)
        monkeypatch.setattr(rrm, "KNOWN_RULES", new_known)
        payload = json.loads(
            rrm.routing_rule_manage(
                action="apply",
                patch_id=queued["patch_id"],
                confirmed=True,
            )
        )
        assert payload["success"] is False
        assert "re-validation failed" in payload["error"]
        # The drift message points at the missing new param so the
        # operator can re-queue with the up-to-date shape.
        assert "'tier'" in payload["error"]
        # Nothing landed.
        assert not fake_hermes_home["config_path"].exists()
        assert list(fake_hermes_home["pending"].iterdir())


# ── apply: happy path + side-effects (layer 1.1) ───────────────────────
#
# These tests cover the success branch and the three side-effects the
# user wants observable from the filesystem alone:
#   1. ``config.yaml`` gains a ``model_routing.rules.<rule_id>`` section
#      with ``params`` + ``applied_at_unix`` + ``patch_id``.
#   2. Pre-existing config sections (provider / fallback / aimc) are
#      preserved 1:1 — a routing apply must NEVER wipe unrelated state.
#   3. ``atomic_yaml_write`` (inside ``save_config``) leaves no .tmp
#      residue on the config file.
#   4. The patch is moved (not copied) from ``pending/`` to
#      ``applied/``.


class TestApplyHappyPath:
    def test_apply_writes_config_section_and_moves_patch(
        self, fake_hermes_home
    ):
        """Happy path: config.yaml gains
        ``model_routing.rules.fallback_chain`` carrying the applied
        params, timestamp, and patch_id reference; the pending patch
        is moved to ``applied/``.
        """
        queued = _queue_patch(
            "fallback_chain",
            {"chain_index": 0, "provider": "kimi"},
            fake_hermes_home["pending"],
        )
        # Pre-condition: no config.yaml yet.
        assert not fake_hermes_home["config_path"].exists()
        payload = json.loads(
            rrm.routing_rule_manage(
                action="apply",
                patch_id=queued["patch_id"],
                confirmed=True,
            )
        )
        assert payload["success"] is True, payload
        assert payload["patch_id"] == queued["patch_id"]
        assert payload["rule_id"] == "fallback_chain"
        assert payload["config_section"] == (
            "model_routing.rules.fallback_chain"
        )
        assert "applied_at_unix" in payload
        assert isinstance(payload["applied_at_unix"], float)
        # The applied/ file path is reported.
        assert Path(payload["applied_path"]).exists()
        # Side-effect 1: config.yaml exists with the section.
        import yaml
        with open(fake_hermes_home["config_path"], encoding="utf-8") as f:
            cfg = yaml.safe_load(f) or {}
        assert "model_routing" in cfg
        assert "rules" in cfg["model_routing"]
        assert "fallback_chain" in cfg["model_routing"]["rules"]
        rule_section = cfg["model_routing"]["rules"]["fallback_chain"]
        assert rule_section["params"] == {
            "chain_index": 0, "provider": "kimi"
        }
        assert rule_section["patch_id"] == queued["patch_id"]
        assert isinstance(rule_section["applied_at_unix"], float)
        # Side-effect 2: pending is empty, applied carries the record.
        assert list(fake_hermes_home["pending"].iterdir()) == []
        applied_files = list(fake_hermes_home["applied"].iterdir())
        assert len(applied_files) == 1
        moved = json.loads(applied_files[0].read_text(encoding="utf-8"))
        assert moved["patch_id"] == queued["patch_id"]
        assert moved["rule_id"] == "fallback_chain"
        # Side-effect 3: the .tmp-… residue guard — atomic_yaml_write
        # must clean up after itself. We probe by listing the parent
        # dir for any .tmp-* sibling of config.yaml.
        tmp_residue = list(
            fake_hermes_home["tmp_path"].glob(".tmp-*.yaml")
        )
        assert tmp_residue == [], (
            f"atomic write left .tmp residue: "
            f"{[p.name for p in tmp_residue]}"
        )

    def test_apply_preserves_other_config_sections(
        self, fake_hermes_home
    ):
        """CAND-085 铁律 2 (managed-scope): an apply on one rule must
        not stomp on unrelated config — provider / fallback / aimc
        sections survive a routing-rule apply 1:1.
        """
        import yaml

        # Pre-seed config.yaml with the user's existing sections.
        seed = {
            "model": "deepseek:deepseek-v4-flash",
            "providers": {
                "aimc": {
                    "name": "aimc",
                    "base_url": "${AIMC_BASE_URL:-http://localhost:8080/v1}",
                    "api_key": "${AIMC_API_KEY}",
                    "api_mode": "chat_completions",
                },
            },
            "fallback_providers": [
                "deepseek:deepseek-v4-flash",
                "openai:gpt-4o-mini",
            ],
            "aimc": {"tier": "balanced", "group": "main"},
            "auxiliary": {
                "vision": {
                    "provider": "kimi",
                    "model": "kimi-k2-vision",
                },
            },
        }
        with open(fake_hermes_home["config_path"], "w", encoding="utf-8") as f:
            yaml.safe_dump(seed, f, allow_unicode=True, sort_keys=False)

        queued = _queue_patch(
            "fallback_chain",
            {"chain_index": 0, "provider": "kimi"},
            fake_hermes_home["pending"],
        )
        payload = json.loads(
            rrm.routing_rule_manage(
                action="apply",
                patch_id=queued["patch_id"],
                confirmed=True,
            )
        )
        assert payload["success"] is True, payload

        with open(fake_hermes_home["config_path"], encoding="utf-8") as f:
            cfg = yaml.safe_load(f) or {}
        # 1:1 preservation of every pre-existing key.
        assert cfg["model"] == seed["model"]
        assert cfg["providers"] == seed["providers"]
        assert cfg["fallback_providers"] == seed["fallback_providers"]
        assert cfg["aimc"] == seed["aimc"]
        assert cfg["auxiliary"] == seed["auxiliary"]
        # The new section sits next to the preserved ones.
        assert "model_routing" in cfg
        assert cfg["model_routing"]["rules"]["fallback_chain"]["params"] == {
            "chain_index": 0, "provider": "kimi"
        }

    def test_apply_no_params_rule_writes_empty_params_section(
        self, fake_hermes_home
    ):
        """``vision_fallback_config`` and ``main_agent_model_fallback``
        declare no params; a patch for them carries ``params={}`` and
        the applied section must reflect that (no surprise
        default-fills).
        """
        queued = _queue_patch(
            "vision_fallback_config",
            {},
            fake_hermes_home["pending"],
        )
        payload = json.loads(
            rrm.routing_rule_manage(
                action="apply",
                patch_id=queued["patch_id"],
                confirmed=True,
            )
        )
        assert payload["success"] is True, payload
        import yaml
        with open(fake_hermes_home["config_path"], encoding="utf-8") as f:
            cfg = yaml.safe_load(f) or {}
        section = cfg["model_routing"]["rules"]["vision_fallback_config"]
        assert section["params"] == {}
        assert section["patch_id"] == queued["patch_id"]

    def test_apply_re_applying_different_rule_keeps_first(
        self, fake_hermes_home
    ):
        """After applying rule A, applying rule B in a separate call
        must not stomp rule A's section. The ``model_routing.rules``
        dict grows additively; one apply per call, one section per
        rule_id.
        """
        first = _queue_patch(
            "fallback_chain",
            {"chain_index": 0, "provider": "kimi"},
            fake_hermes_home["pending"],
        )
        second = _queue_patch(
            "vision_fallback_chain",
            {"chain_index": 1},
            fake_hermes_home["pending"],
        )
        # Apply in order.
        p1 = json.loads(
            rrm.routing_rule_manage(
                action="apply",
                patch_id=first["patch_id"],
                confirmed=True,
            )
        )
        p2 = json.loads(
            rrm.routing_rule_manage(
                action="apply",
                patch_id=second["patch_id"],
                confirmed=True,
            )
        )
        assert p1["success"] and p2["success"]
        import yaml
        with open(fake_hermes_home["config_path"], encoding="utf-8") as f:
            cfg = yaml.safe_load(f) or {}
        rules = cfg["model_routing"]["rules"]
        assert "fallback_chain" in rules
        assert "vision_fallback_chain" in rules
        # First rule's params are intact.
        assert rules["fallback_chain"]["params"] == {
            "chain_index": 0, "provider": "kimi"
        }
        # Second rule has its own section.
        assert rules["vision_fallback_chain"]["params"] == {
            "chain_index": 1
        }
        # Both applied/ records exist.
        applied = list(fake_hermes_home["applied"].iterdir())
        assert len(applied) == 2
        # Pending is empty.
        assert list(fake_hermes_home["pending"].iterdir()) == []

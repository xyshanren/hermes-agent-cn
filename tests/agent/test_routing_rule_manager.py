"""CAND-080 layer 1: routing rule manager tool unit tests.

Covers ``tools.routing_rule_manager_tool.routing_rule_manage`` — the
agent-facing surface for inspecting :data:`agent.routing_decision.KNOWN_RULES`
and queuing proposed patches to ``~/.hermes/routing_patches/pending/``.

These tests are pure-Python (no network, no LLM, no WSL) and use a
``tmp_path`` patch on the pending-dir helper so the queue writes never
escape the test sandbox.
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

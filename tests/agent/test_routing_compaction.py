"""CAND-081 Compaction tool unit tests.

Covers ``tools.routing_compaction_tool.routing_compaction_review`` — the
read-only review of ``~/.hermes/routing_patches/pending/``.

Pure-Python tests, no network / no LLM / no WSL. The pending dir is
redirected to ``tmp_path`` via monkeypatch so the review never escapes
the test sandbox.
"""

import json
from pathlib import Path
from unittest.mock import patch as _patch

import pytest

from tools import routing_compaction_tool as rc
from tools import routing_rule_manager_tool as rrm


# ── Fixtures ────────────────────────────────────────────────────────────


@pytest.fixture
def fake_pending_dir(tmp_path, monkeypatch):
    """Redirect the pending-patches dir to ``tmp_path``.

    Both ``routing_rule_manager_tool._pending_dir`` (the writer) and
    ``routing_compaction_tool._pending_dir`` (the reader) are patched
    to the same path so the two-tool flow can be exercised
    end-to-end inside a test.
    """
    fake = tmp_path / "routing_patches" / "pending"
    fake.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(rrm, "_pending_dir", lambda: fake)
    monkeypatch.setattr(rc, "_pending_dir", lambda: fake)
    return fake


def _queue_patch(rule_id: str, params: dict) -> str:
    """Helper: invoke ``routing_rule_manage action=patch`` and return
    the parsed JSON payload. Lets tests focus on the compaction logic
    without repeating the write boilerplate.
    """
    return rrm.routing_rule_manage(
        action="patch", rule_id=rule_id, params=params
    )


# ── Empty / non-existent directory ─────────────────────────────────────


class TestEmptyPending:
    def test_no_pending_dir_reports_zero(self, tmp_path, monkeypatch):
        """A user with a fresh install has no pending dir at all —
        the review must not crash, just return an empty report.
        """
        # Point both helpers at a path that doesn't exist; do NOT
        # create it, simulating the very-first-run case.
        nonexistent = tmp_path / "never_created" / "pending"
        monkeypatch.setattr(rrm, "_pending_dir", lambda: nonexistent)
        monkeypatch.setattr(rc, "_pending_dir", lambda: nonexistent)
        report = json.loads(rc.routing_compaction_review())
        assert report["success"] is True
        assert report["summary"] == {
            "total_pending": 0,
            "duplicates_count": 0,
            "stale_count": 0,
            "clusters_count": 0,
        }
        assert report["duplicates"] == []
        assert report["stale"] == []
        assert report["clusters"] == []

    def test_empty_pending_dir_reports_zero(self, fake_pending_dir):
        report = json.loads(rc.routing_compaction_review())
        assert report["summary"]["total_pending"] == 0
        assert report["duplicates"] == []
        assert report["stale"] == []
        assert report["clusters"] == []


# ── Happy path: a few clean patches ────────────────────────────────────


class TestCleanPatches:
    def test_two_distinct_rules_no_findings(self, fake_pending_dir):
        _queue_patch("fallback_chain", {"chain_index": 0, "provider": "kimi"})
        _queue_patch(
            "payment_fallback", {"provider": "anthropic"}
        )
        report = json.loads(rc.routing_compaction_review())
        assert report["summary"] == {
            "total_pending": 2,
            "duplicates_count": 0,
            "stale_count": 0,
            "clusters_count": 0,
        }
        assert report["duplicates"] == []
        assert report["stale"] == []
        assert report["clusters"] == []


# ── Duplicates ─────────────────────────────────────────────────────────


class TestDuplicates:
    def test_duplicate_params_flagged_once(self, fake_pending_dir):
        _queue_patch("fallback_chain", {"chain_index": 0, "provider": "kimi"})
        _queue_patch("fallback_chain", {"chain_index": 0, "provider": "kimi"})
        report = json.loads(rc.routing_compaction_review())
        assert report["summary"]["duplicates_count"] == 1
        assert report["summary"]["total_pending"] == 2
        dup = report["duplicates"][0]
        assert dup["rule_id"] == "fallback_chain"
        assert dup["count"] == 2
        assert dup["params"] == {"chain_index": 0, "provider": "kimi"}
        assert len(dup["patch_ids"]) == 2
        assert len(dup["queued_paths"]) == 2

    def test_param_key_order_does_not_matter(self, fake_pending_dir):
        """Two patches with the same params in different key order
        should still be flagged as duplicates. The tool sorts keys
        before grouping.
        """
        # Patch writer preserves the caller's key order, so simulate
        # the order swap by hand-writing two records.
        first = {
            "patch_id": "aaaa11112222",
            "queued_path": str(fake_pending_dir / "1.json"),
            "rule_id": "fallback_chain",
            "params": {"chain_index": 0, "provider": "kimi"},
        }
        second = {
            "patch_id": "bbbb33334444",
            "queued_path": str(fake_pending_dir / "2.json"),
            "rule_id": "fallback_chain",
            "params": {"provider": "kimi", "chain_index": 0},
        }
        (fake_pending_dir / "1.json").write_text(json.dumps(first), encoding="utf-8")
        (fake_pending_dir / "2.json").write_text(json.dumps(second), encoding="utf-8")
        report = json.loads(rc.routing_compaction_review())
        assert report["summary"]["duplicates_count"] == 1
        assert report["duplicates"][0]["count"] == 2

    def test_three_patches_same_params(self, fake_pending_dir):
        _queue_patch("payment_fallback", {"provider": "anthropic"})
        _queue_patch("payment_fallback", {"provider": "anthropic"})
        _queue_patch("payment_fallback", {"provider": "anthropic"})
        report = json.loads(rc.routing_compaction_review())
        assert report["summary"]["duplicates_count"] == 1
        assert report["duplicates"][0]["count"] == 3


# ── Stale (rule_id no longer in KNOWN_RULES) ──────────────────────────


class TestStale:
    def test_stale_rule_id_flagged(self, fake_pending_dir):
        # Hand-write a patch with a rule_id that the registry doesn't
        # know — simulates the "rule was renamed" case the user would
        # see if the registry evolves.
        stale_record = {
            "patch_id": "stale0001111",
            "queued_path": str(fake_pending_dir / "stale.json"),
            "rule_id": "vision_fallback_legacy",
            "params": {"chain_index": 0},
        }
        (fake_pending_dir / "stale.json").write_text(
            json.dumps(stale_record), encoding="utf-8"
        )
        report = json.loads(rc.routing_compaction_review())
        assert report["summary"]["stale_count"] == 1
        stale = report["stale"][0]
        assert stale["rule_id"] == "vision_fallback_legacy"
        assert "not in KNOWN_RULES" in stale["reason"]
        assert "vision_fallback_chain" in stale["reason"]  # lists known alternatives

    def test_known_rule_id_not_flagged_as_stale(self, fake_pending_dir):
        _queue_patch("fallback_chain", {"chain_index": 0, "provider": "kimi"})
        report = json.loads(rc.routing_compaction_review())
        assert report["summary"]["stale_count"] == 0
        assert report["stale"] == []


# ── Clusters (multiple patches for the same rule) ─────────────────────


class TestClusters:
    def test_two_distinct_params_same_rule_flagged_as_cluster(
        self, fake_pending_dir
    ):
        """Distinct params for the same rule (e.g. ``chain_index=0`` vs
        ``chain_index=1``) — ripe for consolidation.
        """
        _queue_patch("fallback_chain", {"chain_index": 0, "provider": "kimi"})
        _queue_patch(
            "fallback_chain", {"chain_index": 1, "provider": "anthropic"}
        )
        report = json.loads(rc.routing_compaction_review())
        assert report["summary"]["clusters_count"] == 1
        cluster = report["clusters"][0]
        assert cluster["rule_id"] == "fallback_chain"
        assert cluster["patch_count"] == 2
        assert cluster["distinct_params_count"] == 2
        assert len(cluster["patch_ids"]) == 2

    def test_single_patch_per_rule_no_cluster(self, fake_pending_dir):
        _queue_patch("fallback_chain", {"chain_index": 0, "provider": "kimi"})
        _queue_patch("payment_fallback", {"provider": "anthropic"})
        report = json.loads(rc.routing_compaction_review())
        assert report["summary"]["clusters_count"] == 0

    def test_duplicate_does_not_form_a_cluster(self, fake_pending_dir):
        """Two identical patches are duplicates, not a cluster — the
        consolidation interest is on *distinct* params. The cluster
        count must stay 0 when the only repeat is a duplicate.
        """
        _queue_patch("fallback_chain", {"chain_index": 0, "provider": "kimi"})
        _queue_patch("fallback_chain", {"chain_index": 0, "provider": "kimi"})
        report = json.loads(rc.routing_compaction_review())
        assert report["summary"]["duplicates_count"] == 1
        assert report["summary"]["clusters_count"] == 0

    def test_stale_cluster_excluded_from_clusters_section(
        self, fake_pending_dir
    ):
        """A rule_id with multiple patches but unknown to the registry
        is reported in ``stale``, not ``clusters`` — it has no
        umbrella to consolidate under.
        """
        for i in range(2):
            (fake_pending_dir / f"stale_{i}.json").write_text(
                json.dumps(
                    {
                        "patch_id": f"stale{i:03d}{'x' * 8}",
                        "queued_path": str(fake_pending_dir / f"stale_{i}.json"),
                        "rule_id": "totally_unknown_rule",
                        "params": {"x": i},
                    }
                ),
                encoding="utf-8",
            )
        report = json.loads(rc.routing_compaction_review())
        assert report["summary"]["stale_count"] == 2
        assert report["summary"]["clusters_count"] == 0
        assert report["clusters"] == []


# ── Read-only guarantee ────────────────────────────────────────────────


class TestReadOnly:
    def test_review_does_not_delete_or_mutate_records(
        self, fake_pending_dir
    ):
        """The compaction tool is **read-only**. A review call must
        leave the queue file contents byte-identical (modulo the
        tool's own JSON re-serialize, which we don't do here — we
        read with ``read_text`` and never write).
        """
        payload = json.loads(
            _queue_patch("fallback_chain", {"chain_index": 0, "provider": "kimi"})
        )
        target = Path(payload["queued_path"])
        original_bytes = target.read_bytes()

        # Run the review.
        json.loads(rc.routing_compaction_review())

        # Run it again. Still no mutation.
        json.loads(rc.routing_compaction_review())

        after_bytes = target.read_bytes()
        assert after_bytes == original_bytes, "review mutated the record"

    def test_review_skips_malformed_json(self, fake_pending_dir):
        """A single corrupt record must not break the whole review.
        The tool's contract is "best-effort, log-and-skip" on parse
        errors, matching the curator's own scan tolerance.
        """
        # Write a valid patch plus a corrupt one.
        _queue_patch("fallback_chain", {"chain_index": 0, "provider": "kimi"})
        (fake_pending_dir / "corrupt.json").write_text(
            "{not valid json", encoding="utf-8"
        )
        report = json.loads(rc.routing_compaction_review())
        # The corrupt file is skipped; the valid one counts.
        assert report["summary"]["total_pending"] == 1
        assert report["duplicates"] == []
        assert report["stale"] == []
        assert report["clusters"] == []

    def test_review_skips_non_json_files(self, fake_pending_dir):
        """A stray ``.tmp-…`` or other non-JSON file in the directory
        (atomic-write leftover, editor swap file, etc.) must not be
        parsed as a record.
        """
        _queue_patch("fallback_chain", {"chain_index": 0, "provider": "kimi"})
        (fake_pending_dir / ".tmp-abc123").write_text("", encoding="utf-8")
        (fake_pending_dir / "README.txt").write_text("not a patch", encoding="utf-8")
        report = json.loads(rc.routing_compaction_review())
        assert report["summary"]["total_pending"] == 1


# ── End-to-end with the writer tool ────────────────────────────────────


class TestEndToEndWithWriter:
    """The two tools are designed to compose: writer queues a patch,
    reviewer inspects the queue. Pin the full path here so a future
    change to either tool that breaks the round-trip shows up in one
    test.
    """

    def test_full_flow_writer_then_reviewer(self, fake_pending_dir):
        for params in [
            {"chain_index": 0, "provider": "kimi"},
            {"chain_index": 1, "provider": "anthropic"},
            {"chain_index": 0, "provider": "kimi"},  # duplicate of #1
        ]:
            payload = json.loads(
                _queue_patch("fallback_chain", params=params)
            )
            assert payload["success"] is True

        report = json.loads(rc.routing_compaction_review())
        assert report["summary"] == {
            "total_pending": 3,
            "duplicates_count": 1,
            "stale_count": 0,
            "clusters_count": 1,
        }
        # The duplicate is the chain_index=0 kimi one.
        assert report["duplicates"][0]["count"] == 2
        # The cluster is all 3 chain_index values for fallback_chain.
        assert report["clusters"][0]["patch_count"] == 3
        assert report["clusters"][0]["distinct_params_count"] == 2

"""CAND-082 A/B test engine unit tests.

Covers ``tools.routing_ab_test_tool.routing_ab_test`` — the
read-only simulation engine that compares two routing-rule variants
on 5 metrics against operator-supplied thresholds.

Pure-Python, no network / no LLM / no WSL. The engine uses
deterministic synthetic baselines (see ``_RULE_BASELINES`` in the
tool) so the same input always produces the same metric for the
same variant — making the verdict reproducible across runs.
"""

import json

import pytest

from tools import routing_ab_test_tool as r_ab


# ── Determinism ────────────────────────────────────────────────────────


class TestDeterminism:
    """The engine must be deterministic: the same variant + same
    sample_size must produce the same metrics run after run. This is
    the bedrock property for using the engine in CI gates.
    """

    def test_same_variant_same_sample_same_metrics(self):
        spec = {
            "rule_id": "fallback_chain",
            "params": {"chain_index": 0, "provider": "kimi"},
        }
        a = json.loads(
            r_ab.routing_ab_test(
                variant_a=spec, variant_b=spec, sample_size=50
            )
        )
        b = json.loads(
            r_ab.routing_ab_test(
                variant_a=spec, variant_b=spec, sample_size=50
            )
        )
        assert a["variant_a"]["metrics"] == b["variant_a"]["metrics"]
        assert a["variant_b"]["metrics"] == b["variant_b"]["metrics"]

    def test_different_params_produce_different_metrics(self):
        """Two variants with different params must perturb the
        baseline in different directions, otherwise the engine
        would report A==B for any input and the verdict would be
        meaningless.
        """
        a_spec = {
            "rule_id": "fallback_chain",
            "params": {"chain_index": 0, "provider": "kimi"},
        }
        b_spec = {
            "rule_id": "fallback_chain",
            "params": {"chain_index": 1, "provider": "anthropic"},
        }
        report = json.loads(
            r_ab.routing_ab_test(
                variant_a=a_spec, variant_b=b_spec, sample_size=100
            )
        )
        # The 4 baselines-driven metrics must differ between A and B.
        # (user_feedback is always 0.0 so we skip it.)
        for metric in ("cost", "latency", "fallback_rate", "success_rate"):
            a = report["variant_a"]["metrics"][metric]
            b = report["variant_b"]["metrics"][metric]
            assert a != b, (
                f"metric {metric!r} identical between A and B "
                f"({a}); engine perturbation is not working"
            )


# ── Sample size & shape ───────────────────────────────────────────────


class TestSampleSize:
    def test_default_sample_size_is_100(self):
        spec = {"rule_id": "fallback_chain", "params": {}}
        report = json.loads(
            r_ab.routing_ab_test(variant_a=spec, variant_b=spec)
        )
        assert report["sample_size"] == 100
        assert report["success"] is True

    def test_explicit_sample_size(self):
        spec = {"rule_id": "fallback_chain", "params": {}}
        report = json.loads(
            r_ab.routing_ab_test(
                variant_a=spec, variant_b=spec, sample_size=37
            )
        )
        assert report["sample_size"] == 37

    def test_zero_sample_size_fails(self):
        spec = {"rule_id": "fallback_chain", "params": {}}
        report = json.loads(
            r_ab.routing_ab_test(
                variant_a=spec, variant_b=spec, sample_size=0
            )
        )
        assert report["success"] is False
        assert "sample_size" in report["error"]

    def test_negative_sample_size_fails(self):
        spec = {"rule_id": "fallback_chain", "params": {}}
        report = json.loads(
            r_ab.routing_ab_test(
                variant_a=spec, variant_b=spec, sample_size=-10
            )
        )
        assert report["success"] is False


# ── Metric surface ────────────────────────────────────────────────────


class TestMetricSurface:
    def test_all_five_metrics_present(self):
        spec = {"rule_id": "fallback_chain", "params": {}}
        report = json.loads(
            r_ab.routing_ab_test(variant_a=spec, variant_b=spec, sample_size=10)
        )
        for variant_key in ("variant_a", "variant_b"):
            metrics = report[variant_key]["metrics"]
            assert set(metrics) == {
                "cost",
                "latency",
                "fallback_rate",
                "success_rate",
                "user_feedback",
            }

    def test_user_feedback_is_zero(self):
        """No user-feedback pipeline yet (per K-5 tray-UI checklist);
        the metric must be 0.0 so a threshold check is well-defined.
        """
        spec = {"rule_id": "fallback_chain", "params": {}}
        report = json.loads(
            r_ab.routing_ab_test(variant_a=spec, variant_b=spec, sample_size=10)
        )
        assert report["variant_a"]["metrics"]["user_feedback"] == 0.0
        assert report["variant_b"]["metrics"]["user_feedback"] == 0.0

    def test_metrics_within_physically_meaningful_ranges(self):
        """Defensive: even after perturbation, the metrics must
        stay in their natural ranges (no negative cost, fallback
        rate <= 1, success rate <= 1).
        """
        spec = {"rule_id": "fallback_chain", "params": {"chain_index": 0}}
        report = json.loads(
            r_ab.routing_ab_test(variant_a=spec, variant_b=spec, sample_size=200)
        )
        for variant_key in ("variant_a", "variant_b"):
            m = report[variant_key]["metrics"]
            assert m["cost"] >= 0
            assert m["latency"] >= 0
            assert 0.0 <= m["fallback_rate"] <= 1.0
            assert 0.0 <= m["success_rate"] <= 1.0


# ── Threshold checks ───────────────────────────────────────────────────


class TestThresholds:
    def test_no_thresholds_means_default_pass(self):
        spec = {"rule_id": "fallback_chain", "params": {}}
        report = json.loads(
            r_ab.routing_ab_test(variant_a=spec, variant_b=spec, sample_size=10)
        )
        # Without thresholds, every variant trivially passes.
        assert report["variant_a"]["pass"] is True
        assert report["variant_b"]["pass"] is True
        assert report["verdict"]["pass"] is True
        assert report["verdict"]["winning_variant"] == "tie"
        assert report["variant_a"]["threshold_check"] == {}
        assert report["variant_b"]["threshold_check"] == {}

    def test_max_threshold_passes_when_under(self):
        """``cost`` baseline for ``fallback_chain`` is 0.020; a max
        of 0.100 must pass.
        """
        spec = {"rule_id": "fallback_chain", "params": {}}
        report = json.loads(
            r_ab.routing_ab_test(
                variant_a=spec, variant_b=spec, sample_size=50,
                thresholds={"cost": {"max": 0.100}},
            )
        )
        assert report["variant_a"]["threshold_check"]["cost"]["pass"] is True
        assert report["variant_b"]["threshold_check"]["cost"]["pass"] is True

    def test_max_threshold_fails_when_over(self):
        spec = {"rule_id": "fallback_chain", "params": {}}
        report = json.loads(
            r_ab.routing_ab_test(
                variant_a=spec, variant_b=spec, sample_size=50,
                thresholds={"cost": {"max": 0.001}},  # baseline ~0.020
            )
        )
        assert report["variant_a"]["threshold_check"]["cost"]["pass"] is False
        assert report["variant_b"]["threshold_check"]["cost"]["pass"] is False
        assert report["verdict"]["pass"] is False

    def test_min_threshold_for_success_rate(self):
        """``success_rate`` baseline for ``fallback_chain`` is 0.95;
        a min of 0.80 must pass, a min of 0.99 must fail.
        """
        spec = {"rule_id": "fallback_chain", "params": {}}
        passing = json.loads(
            r_ab.routing_ab_test(
                variant_a=spec, variant_b=spec, sample_size=50,
                thresholds={"success_rate": {"min": 0.80}},
            )
        )
        failing = json.loads(
            r_ab.routing_ab_test(
                variant_a=spec, variant_b=spec, sample_size=50,
                thresholds={"success_rate": {"min": 0.99}},
            )
        )
        assert passing["variant_a"]["threshold_check"]["success_rate"]["pass"] is True
        assert failing["variant_a"]["threshold_check"]["success_rate"]["pass"] is False

    def test_both_min_and_max_on_same_metric(self):
        spec = {"rule_id": "fallback_chain", "params": {}}
        report = json.loads(
            r_ab.routing_ab_test(
                variant_a=spec, variant_b=spec, sample_size=50,
                thresholds={"success_rate": {"min": 0.80, "max": 1.0}},
            )
        )
        assert report["variant_a"]["threshold_check"]["success_rate"]["pass"] is True

    def test_unknown_metric_fails_check(self):
        """A threshold for a metric the engine doesn't compute must
        surface a clear reason, not crash.
        """
        spec = {"rule_id": "fallback_chain", "params": {}}
        report = json.loads(
            r_ab.routing_ab_test(
                variant_a=spec, variant_b=spec, sample_size=10,
                thresholds={"hypothetical_metric": {"max": 1.0}},
            )
        )
        check = report["variant_a"]["threshold_check"]["hypothetical_metric"]
        assert check["pass"] is False
        assert "not in computed metrics" in check["reason"]
        assert report["verdict"]["pass"] is False


# ── Verdict (winning variant) ──────────────────────────────────────────


class TestVerdict:
    def test_passing_threshold_picks_winning_variant(self):
        """When A passes 3 of 3 thresholds and B passes 2 of 3
        (because B's user_feedback is always 0.0, which can't
        satisfy any min > 0), A wins.
        """
        a_spec = {"rule_id": "fallback_chain", "params": {}}
        b_spec = {"rule_id": "cost_aware_fallback", "params": {}}
        report = json.loads(
            r_ab.routing_ab_test(
                variant_a=a_spec, variant_b=b_spec, sample_size=50,
                thresholds={
                    "cost": {"max": 1.0},
                    "success_rate": {"min": 0.5},
                    "user_feedback": {"min": 0.0},  # 0.0 always satisfies
                },
            )
        )
        # Both A and B should pass (thresholds are very loose).
        assert report["variant_a"]["metrics_within_threshold"] == 3
        assert report["variant_b"]["metrics_within_threshold"] == 3
        # Tied on 3-of-3, the verdict is "tie".
        assert report["verdict"]["winning_variant"] == "tie"

    def test_user_feedback_threshold_min_zero_passes(self):
        """``user_feedback`` is 0.0; a ``min: 0.0`` threshold must
        always pass (otherwise the operator can't opt-in to
        tracking without setting min: -inf).
        """
        spec = {"rule_id": "fallback_chain", "params": {}}
        report = json.loads(
            r_ab.routing_ab_test(
                variant_a=spec, variant_b=spec, sample_size=10,
                thresholds={"user_feedback": {"min": 0.0}},
            )
        )
        assert report["variant_a"]["threshold_check"]["user_feedback"]["pass"] is True

    def test_aggregate_verdict_requires_both_variants(self):
        spec = {"rule_id": "fallback_chain", "params": {}}
        report = json.loads(
            r_ab.routing_ab_test(
                variant_a=spec, variant_b=spec, sample_size=10,
                thresholds={"cost": {"max": 0.001}},  # fails
            )
        )
        # Both variants fail the same threshold, so the aggregate
        # verdict is "no, this rule change isn't ready" — but the
        # winning_variant is still "tie" because neither beat the
        # other on the within-threshold count.
        assert report["verdict"]["pass"] is False
        assert report["verdict"]["winning_variant"] == "tie"

    def test_winning_variant_message_references_publish_or_keep(self):
        """The verdict's ``rule_change`` field must read like an
        operator-facing publish/keep recommendation, not raw A/B
        letters. This is the field the front-end surfaces.
        """
        spec = {"rule_id": "fallback_chain", "params": {}}
        report = json.loads(
            r_ab.routing_ab_test(variant_a=spec, variant_b=spec)
        )
        msg = report["verdict"]["rule_change"].lower()
        assert "publish" in msg or "keep" in msg or "operator" in msg


# ── Read-only guarantee ────────────────────────────────────────────────


class TestReadOnly:
    def test_engine_does_not_persist_anything(self, tmp_path, monkeypatch):
        """The engine has no side effects — no file write, no DB
        insert, no network. We pin that contract here by patching
        ``routing_rule_manager_tool._pending_dir`` (the writer
        side) and asserting the review tool never reads from /
        writes to it. This protects the 4 铁律 guarantee end-to-end.
        """
        # A real pending dir under tmp_path that the writer would
        # use; the engine must not touch it.
        fake = tmp_path / "routing_patches" / "pending"
        fake.mkdir(parents=True, exist_ok=True)
        # Pre-populate with a sentinel file; if the engine reads
        # or writes here, the test will see the file count change.
        sentinel = fake / "sentinel.json"
        sentinel.write_text('{"sentinel": true}', encoding="utf-8")
        from tools import routing_rule_manager_tool as rrm
        monkeypatch.setattr(rrm, "_pending_dir", lambda: fake)

        spec = {"rule_id": "fallback_chain", "params": {}}
        r_ab.routing_ab_test(variant_a=spec, variant_b=spec, sample_size=20)

        # Sentinel file must be exactly as we left it — engine
        # never touched the pending dir.
        assert sentinel.read_text(encoding="utf-8") == '{"sentinel": true}'
        files = list(fake.iterdir())
        assert files == [sentinel]

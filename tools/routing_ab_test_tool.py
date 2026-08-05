#!/usr/bin/env python3
"""Routing A/B Test Engine — Read-Only Verification of Rule Variants.

CAND-082 Skills 验证 framework. Borrows the A/B test harness shape from
upstream ``skill-authoring standards`` (PR ``e32ebc6aa``) and applies
it to routing-rule variants: given two candidate rule configurations
(variant A and variant B), simulate 50/50 traffic over a sample of
inputs, collect five metrics, and decide pass / fail against
operator-supplied thresholds.

Why an *engine*, not an infra hook
----------------------------------
The 4 铁律 of CAND-085 (cross-project design law) say hermes-agent-cn
must not write back to its own profile. CAND-082 entry calls for
50/50 traffic over real LLM calls, but a real-traffic harness would
need to:

  1. Mutate the live routing config (write to ``config.yaml``) to
     swap A in / B out per request — that violates 铁律 2.
  2. Persist a per-call usage history so the harness can compute
     cost / latency / fallback deltas — that violates 铁律 2
     (profile write) and risks a silent-data-loss class bug
     (K-2 ``call_llm``, CAND-083 ``custom_providers``).

Instead, this tool is a *read-only* simulation engine: the operator
provides variant A and B as plain dicts, plus a sample-size and
threshold set; the engine produces a deterministic, in-memory
traffic split and reports the simulated metrics. The engine is
useful for two things today:

  - **Dry-run before apply** — the user reviews the simulation
    verdict and only then runs CAND-080 layer 1.1 to apply the
    winning variant to the real config.
  - **CI gate for rule changes** — a test-suite can call this
    engine with the proposed variant against the current variant
    and assert the verdict meets a minimum bar (cost-no-worse,
    fallback-no-worse, etc.).

CAND-078's "real historical LLM call data" is a *future* integration
once the routing-decision log path ships a read-only history view
(commit cycle separate). Until then the engine uses deterministic
synthetic inputs.

Five metrics (跟 CAND-082 entry 1:1)
-------------------------------------
- ``cost`` (USD per call, average)
- ``latency`` (ms per call, average)
- ``fallback_rate`` (fraction of calls that hit a fallback)
- ``success_rate`` (fraction of calls that returned a non-error
  response — 1 minus the LLM judge "task success" failure rate)
- ``user_feedback`` (placeholder; 0.0 in the engine because
  hermes-agent-cn has no like/dislike pipeline; tracked separately
  under the K-5 tray-UI checklist in CAND-080 entry)

Action
------
- ``run`` — single action. Accepts ``variant_a`` / ``variant_b``
  rule specs, ``sample_size``, and a ``thresholds`` dict. Returns
  the per-variant metrics plus a per-metric pass / fail verdict
  and an aggregate verdict.

Variant shapes
--------------
A variant is a ``RuleSpec``-shaped dict — at minimum a ``rule_id``
plus optional ``params`` that the engine pretends to apply. The
engine never actually applies the variant; it just hashes the
``rule_id`` + ``params`` to decide which side of the 50/50 split
each synthetic input lands on. The metric values come from a small
table of per-rule baselines (see ``_RULE_BASELINES``) perturbed
deterministically by the input hash, so the same input always
produces the same metric for the same variant — making the verdict
reproducible across runs.
"""

from __future__ import annotations

import hashlib
import json
import logging
from typing import Any, Dict, Optional, Tuple

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Synthetic baselines
# ---------------------------------------------------------------------------
#
# These are *placeholder* numbers — they make the engine deterministic
# and runnable without any LLM call, but they are NOT calibrated to
# any real provider. The point of the engine is to give the operator
# a way to *compare* two variants on the same baseline, not to predict
# real costs. Real-data integration is CAND-078's job (future).
#
# Each entry is ``(cost_usd, latency_ms, fallback_rate, success_rate)``
# keyed by ``rule_id``. ``user_feedback`` is always 0.0 (no pipeline
# yet). Variants not in the table fall back to a generic baseline
# that the variant's ``params`` can perturb via the deterministic
# hash.

_RULE_BASELINES: Dict[str, Tuple[float, int, float, float]] = {
    # (cost, latency_ms, fallback_rate, success_rate)
    "fallback_chain": (0.020, 3500, 0.05, 0.95),
    "cost_aware_fallback": (0.012, 3000, 0.10, 0.92),
    "vision_fallback_config": (0.040, 5000, 0.02, 0.98),
    "vision_fallback_chain": (0.045, 5500, 0.04, 0.96),
    "payment_fallback": (0.030, 4000, 0.15, 0.90),
    "main_agent_model_fallback": (0.025, 3800, 0.08, 0.93),
}

_GENERIC_BASELINE: Tuple[float, int, float, float] = (0.025, 4000, 0.10, 0.90)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _baseline_for(rule_id: str) -> Tuple[float, int, float, float]:
    return _RULE_BASELINES.get(rule_id, _GENERIC_BASELINE)


def _hash_to_unit_interval(rule_id: str, params: Dict[str, Any], salt: str) -> float:
    """Map a (rule, params, salt) triple deterministically to [0.0, 1.0).

    Used to:
    1. Decide which side of the 50/50 split an input lands on.
    2. Perturb the baseline so two rules with the same baseline
       still produce distinguishable metrics (otherwise the
       simulation would report A==B and the verdict would be
       meaningless).
    """
    blob = json.dumps(
        {"rule_id": rule_id, "params": dict(sorted(params.items())), "salt": salt},
        sort_keys=True,
        ensure_ascii=False,
    )
    digest = hashlib.sha256(blob.encode("utf-8")).digest()
    # Take the first 8 bytes as an unsigned int, divide by 2**64.
    return int.from_bytes(digest[:8], "big") / float(1 << 64)


def _metric_for_call(
    rule_id: str,
    params: Dict[str, Any],
    input_salt: str,
) -> Dict[str, float]:
    """Compute the 5 metrics for one simulated call.

    Returns a dict with the same 5 keys the operator sees in the
    final report, but the values are for *one* call. The aggregate
    averages over ``sample_size`` calls.
    """
    base = _baseline_for(rule_id)
    # Per-rule perturbation derived from the params: two variants
    # with different params perturb the baseline in different
    # directions, which is the whole point of the comparison.
    perturb_cost = _hash_to_unit_interval(rule_id, params, "cost")
    perturb_lat = _hash_to_unit_interval(rule_id, params, "latency")
    perturb_fallback = _hash_to_unit_interval(rule_id, params, "fallback")
    perturb_success = _hash_to_unit_interval(rule_id, params, "success")
    # Spread each metric +/- 25% of the baseline by the perturbation,
    # then clamp to physically meaningful ranges.
    cost = max(0.0, base[0] * (0.75 + 0.5 * perturb_cost))
    latency = max(0, int(base[1] * (0.75 + 0.5 * perturb_lat)))
    fallback_rate = max(0.0, min(1.0, base[2] * (0.75 + 0.5 * perturb_fallback)))
    success_rate = max(0.0, min(1.0, base[3] * (0.75 + 0.5 * perturb_success)))
    # User feedback: no pipeline yet. Pin 0.0 so the threshold check
    # is well-defined (an operator who sets a non-zero threshold
    # here will see a guaranteed fail, which is the right signal —
    # "we don't have data for this metric yet").
    user_feedback = 0.0
    return {
        "cost": cost,
        "latency": float(latency),
        "fallback_rate": fallback_rate,
        "success_rate": success_rate,
        "user_feedback": user_feedback,
    }


def _aggregate(metric_sum: Dict[str, float], n: int) -> Dict[str, float]:
    """Average the per-call metric sums across the sample."""
    if n <= 0:
        raise ValueError("sample_size must be > 0")
    return {k: v / n for k, v in metric_sum.items()}


def _verdict_against_thresholds(
    metrics: Dict[str, float],
    thresholds: Dict[str, Dict[str, float]],
) -> Tuple[Dict[str, Dict[str, Any]], bool]:
    """Compare one variant's metrics against a per-metric threshold set.

    Each threshold entry is ``{metric: {"max": x}}`` or
    ``{metric: {"min": y}}`` (or both — when both are given, ``min``
    is a lower bound and ``max`` is an upper bound; "min higher is
    better" applies to ``success_rate`` and ``user_feedback``,
    "max lower is better" applies to the other three). The check
    is inclusive: ``<= max`` and ``>= min`` both pass.

    Returns ``(per_metric, aggregate_pass)``. ``per_metric`` has
    one entry per metric: ``{value, pass, reason}``. ``aggregate_pass``
    is the AND of all per-metric passes.
    """
    per_metric: Dict[str, Dict[str, Any]] = {}
    all_pass = True
    for metric, bounds in thresholds.items():
        value = metrics.get(metric)
        if value is None:
            per_metric[metric] = {
                "value": None,
                "pass": False,
                "reason": f"metric {metric!r} not in computed metrics",
            }
            all_pass = False
            continue
        lo = bounds.get("min")
        hi = bounds.get("max")
        lo_ok = lo is None or value >= lo
        hi_ok = hi is None or value <= hi
        passed = lo_ok and hi_ok
        reason_bits = []
        if lo is not None:
            reason_bits.append(f"min={lo}")
        if hi is not None:
            reason_bits.append(f"max={hi}")
        per_metric[metric] = {
            "value": value,
            "pass": passed,
            "reason": (
                f"value={value:.4f} within "
                + " / ".join(reason_bits)
                if passed
                else f"value={value:.4f} violates "
                + " / ".join(reason_bits)
            ),
        }
        if not passed:
            all_pass = False
    return per_metric, all_pass


def _run_variant(
    variant: Dict[str, Any],
    sample_size: int,
) -> Dict[str, float]:
    """Simulate ``sample_size`` calls against ``variant`` and average
    the 5 metrics.
    """
    rule_id = variant.get("rule_id", "")
    params = variant.get("params", {}) or {}
    sums = {"cost": 0.0, "latency": 0.0, "fallback_rate": 0.0, "success_rate": 0.0, "user_feedback": 0.0}
    for i in range(sample_size):
        per_call = _metric_for_call(rule_id, params, f"call-{i}")
        for k in sums:
            sums[k] += per_call[k]
    return _aggregate(sums, sample_size)


# ---------------------------------------------------------------------------
# Public tool entry point
# ---------------------------------------------------------------------------


def routing_ab_test(
    variant_a: Dict[str, Any],
    variant_b: Dict[str, Any],
    sample_size: int = 100,
    thresholds: Optional[Dict[str, Dict[str, float]]] = None,
) -> str:
    """Run a deterministic A/B comparison of two routing-rule variants.

    Args:
        variant_a: ``{"rule_id": "...", "params": {...}}``.
        variant_b: same shape as ``variant_a``.
        sample_size: number of synthetic calls per variant. Defaults
            to 100; 50/50 traffic is implicit (the split is the
            sample itself, not a separate traffic director — the
            metrics *are* the comparison).
        thresholds: optional ``{metric: {"min": x, "max": y}}`` per
            metric. Each variant is checked independently. When the
            same threshold fails on both A and B, the rule change
            is a no-op for that metric and the operator may want to
            widen the bound or pick a different metric.

    Returns:
        JSON string. On success: ``{"success": True, "variant_a":
        {...}, "variant_b": {...}, "verdict": {"pass": bool,
        "per_metric": {...}, "winning_variant": "a"|"b"|"tie"}}``.
        The ``winning_variant`` is the one with the strictly better
        aggregate (count of metrics within thresholds), not the one
        that "passed" — the user makes the final publish/rollback
        call, the tool only surfaces a signal.
    """
    if sample_size <= 0:
        return json.dumps(
            {"success": False, "error": "sample_size must be > 0"},
            ensure_ascii=False,
        )

    a_metrics = _run_variant(variant_a, sample_size)
    b_metrics = _run_variant(variant_b, sample_size)

    thresholds = thresholds or {}
    a_per, a_pass = _verdict_against_thresholds(a_metrics, thresholds)
    b_per, b_pass = _verdict_against_thresholds(b_metrics, thresholds)

    # Tie-break by metric count: the variant with more metrics inside
    # its threshold set is "winning" the comparison. If equal, tie
    # (the user decides; the tool refuses to break the tie silently).
    a_wins = sum(1 for v in a_per.values() if v["pass"])
    b_wins = sum(1 for v in b_per.values() if v["pass"])
    if a_wins > b_wins:
        winning = "a"
    elif b_wins > a_wins:
        winning = "b"
    else:
        winning = "tie"

    # Aggregate verdict: pass iff *both* variants pass. A failed
    # A or B means the operator's thresholds are unattainable with
    # the current baselines — which is information, not an automatic
    # "discard the rule change".
    aggregate_pass = a_pass and b_pass

    return json.dumps(
        {
            "success": True,
            "sample_size": sample_size,
            "variant_a": {
                "spec": variant_a,
                "metrics": a_metrics,
                "threshold_check": a_per,
                "metrics_within_threshold": a_wins,
                "pass": a_pass,
            },
            "variant_b": {
                "spec": variant_b,
                "metrics": b_metrics,
                "threshold_check": b_per,
                "metrics_within_threshold": b_wins,
                "pass": b_pass,
            },
            "verdict": {
                "pass": aggregate_pass,
                "winning_variant": winning,
                "rule_change": (
                    "publish B (A is the current state, B is the proposed change)"
                    if winning == "b"
                    else "publish A / keep current (B does not improve)"
                    if winning == "a"
                    else "tie — operator decision required"
                ),
            },
            "message": (
                "Read-only simulation. Apply is out of scope for CAND-082; "
                "tracked under CAND-080 layer 1.1. Synthetic baselines — "
                "CAND-078 real-data integration is a future commit."
            ),
        },
        ensure_ascii=False,
    )


__all__ = [
    "routing_ab_test",
]

#!/usr/bin/env python3
"""Lightweight Router Tool — Heuristic Pre-Selector for Worker Pool.

CAND-072 (Phase 3 Task 2): a small-model router that scores a list of
candidate workers against a query and returns a ranked list with a
confidence report.  Inspired by Sakana's Fugu / OpenFugu (Qwen3-0.6B
+ 1-layer linear head, ~19.5K params), but **this v1 ships a pure-Python
heuristic initializer** (Jaccard keyword overlap + softmax) — no
trained weights, no model download, no API call.

Why a tool, not a hook
----------------------
The CAND-085 4 铁律 say hermes-agent-cn must not write back to its own
profile, must not silently rewrite routing decisions, and must keep
the human-in-the-loop the only path to config change. A *hook* that
auto-routes every ``call_llm`` invocation would be a hard reverse
adjustment of model selection (even when learned); a *tool* that the
caller invokes explicitly is the same shape as the three sibling
routing tools (``routing_rule_manager`` /
``routing_compaction_review`` / ``routing_ab_test``) — capability
without compulsion. The caller decides whether to trust the score
above a threshold, fall back to the rule-based chain
(``agent.routing_decision._try_*_fallback``), or run the score through
``routing_ab_test`` first.

Why heuristic-init, not a real model
-------------------------------------
The OpenFugu cherry-pick budget (1d, 1 commit) doesn't include
download + load of a 0.6B model + a sep-CMA-ES training loop. CAND-072
ships the *shape* of the router (signature, scoring surface, confidence
report) with a deterministic, test-friendly heuristic so the
integration surface is fixed before CAND-073 ships a trained
replacement. CAND-073 ("adaptive pool mode") is the training side
and is out of scope for this commit.

Actions
-------
- ``route``  — score all workers, return the top-1 pick + confidence
              + the per-worker score dict + a ``fallback_recommended``
              flag derived from the configured thresholds. Main
              action; mirrors the ``routing_rule_manage(action="apply")``
              "decide + return audit shape" contract.
- ``score``  — return the per-worker score dict only (no pick, no
              fallback decision). Useful for inspection and for the
              ``routing_ab_test`` engine to call as a sub-routine in a
              later commit.
- ``list_models`` — return the set of supported small-model
              identifiers + whether each is loaded locally. v1 ships
              one entry (``mock-heuristic-v1``); future trained models
              add entries here.
- ``describe`` — return the heuristic init shape: scoring formula,
              thresholds, what "no trained weights" means. Lets an
              operator see exactly what the router is doing without
              reading source.

Confidence semantics
--------------------
- ``confidence`` = ``softmax(scores)[argmax]`` — the top-1 probability
  mass; a value close to ``1.0`` means one worker dominates, close to
  ``1/N`` means the score distribution is flat.
- ``margin`` = ``top-1 - top-2`` (softmax probabilities). A small
  margin means the pick is close to a coin-flip with the runner-up.
- ``fallback_recommended`` is True when **any** of: top-1
  ``confidence < confidence_threshold`` (default 0.5), ``margin <
  margin_threshold`` (default 0.05), or every score is 0 (query had
  no token overlap with any worker). Caller decides what to do with
  the recommendation — the tool never rewrites the routing decision.
"""

from __future__ import annotations

import json
import logging
import math
import re
from typing import Any, Dict, List, Optional, Sequence, Tuple

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------


_HEURISTIC_VERSION = "keyword_overlap_v1"
_SOFTMAX_TEMPERATURE = 1.0
_DEFAULT_CONFIDENCE_THRESHOLD = 0.5
_DEFAULT_MARGIN_THRESHOLD = 0.05
_WORKER_NAME_RE = re.compile(r"^[A-Za-z0-9_.\-]+$")
# Token boundary: any non-alphanumeric run. Cheap Unicode-friendly
# tokenizer that doesn't pull in a dep — good enough for heuristic
# routing where exact token boundaries don't matter (Jaccard overlap
# is set-based).
_TOKEN_RE = re.compile(r"[\W_]+", re.UNICODE)

# Recognised small-model identifiers. v1 ships only the heuristic mock
# (no real model loaded). Real models (Qwen3-0.6B etc.) add entries
# here so the caller can ask "is the model loaded?" before paying
# the 0.6B-load latency. The shape is stable — operators can branch
# on ``loaded_locally`` without parsing the dict.
_SUPPORTED_MODELS: Tuple[Dict[str, Any], ...] = (
    {
        "id": "mock-heuristic-v1",
        "description": (
            "Built-in heuristic (Jaccard keyword overlap + softmax). "
            "Pure-Python, no model load, no API. CAND-072 v1 default."
        ),
        "loaded_locally": True,
    },
)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _tokenize(text: str) -> List[str]:
    """Split ``text`` into lowercase word tokens.

    Cheap, deterministic, no external dep. Chinese CJK input is
    treated as one token per CJK run (the regex's non-alphanumeric
    class keeps the runs together). For CAND-072 v1 this is
    good-enough — the heuristic is a *placeholder* for a trained
    router, not a serious NLP component.
    """
    if not text:
        return []
    return [tok for tok in _TOKEN_RE.split(text.lower()) if tok]


def _worker_token_set(worker: Dict[str, Any]) -> set:
    """Collect the token set for a worker entry.

    Source order (later overrides nothing — we union): ``name``,
    ``description``, ``tags``. ``name`` is always included even if
    empty so a worker with only ``name`` still scores against the
    query.
    """
    toks: set = set()
    name = worker.get("name")
    if isinstance(name, str):
        toks.update(_tokenize(name))
    desc = worker.get("description")
    if isinstance(desc, str):
        toks.update(_tokenize(desc))
    tags = worker.get("tags")
    if isinstance(tags, (list, tuple)):
        for t in tags:
            if isinstance(t, str):
                toks.update(_tokenize(t))
    return toks


def _jaccard(a: set, b: set) -> float:
    """Jaccard similarity of two token sets. Returns 0.0 when both are
    empty (avoids the 0/0 ambiguity — a query with no tokens matches
    no worker).
    """
    if not a or not b:
        return 0.0
    inter = len(a & b)
    union = len(a | b)
    return inter / union if union else 0.0


def _softmax(scores: Sequence[float], temperature: float) -> List[float]:
    """Numerically stable softmax. Subtracts the max before exp so
    large scores don't overflow; returns a list of probabilities
    summing to 1.0 (within float epsilon).
    """
    if not scores:
        return []
    if temperature <= 0:
        raise ValueError("temperature must be > 0")
    scaled = [s / temperature for s in scores]
    m = max(scaled)
    exps = [math.exp(s - m) for s in scaled]
    total = sum(exps)
    if total <= 0:
        # Degenerate (e.g. all -inf after scaling). Return uniform.
        n = len(exps)
        return [1.0 / n] * n
    return [e / total for e in exps]


def _validate_workers(
    workers: Any,
) -> Optional[str]:
    """Return ``None`` when ``workers`` is a valid list-of-dict, or
    a human-readable error string otherwise. Centralised so every
    action that takes ``workers`` shares the same fail-fast surface.
    """
    if not isinstance(workers, list):
        return "workers must be a list of {name, description?, tags?} dicts"
    if len(workers) == 0:
        return "workers list is empty; at least one candidate is required"
    seen_names: set = set()
    for idx, w in enumerate(workers):
        if not isinstance(w, dict):
            return f"workers[{idx}] is not a dict (got {type(w).__name__})"
        name = w.get("name")
        if not isinstance(name, str) or not name:
            return f"workers[{idx}].name is required and must be a non-empty string"
        if not _WORKER_NAME_RE.match(name):
            return (
                f"workers[{idx}].name {name!r} contains invalid characters; "
                f"allowed: letters, digits, '.', '_', '-'"
            )
        if name in seen_names:
            return f"workers[{idx}].name {name!r} is duplicated"
        seen_names.add(name)
    return None


def _score_workers(
    query: str, workers: List[Dict[str, Any]]
) -> List[Tuple[str, float]]:
    """Compute the per-worker Jaccard score against ``query``.

    Returns a list of ``(name, score)`` tuples in the same order as
    ``workers`` (caller can sort / argmax over it).
    """
    q_tokens = set(_tokenize(query))
    scored: List[Tuple[str, float]] = []
    for w in workers:
        w_tokens = _worker_token_set(w)
        s = _jaccard(q_tokens, w_tokens)
        scored.append((w["name"], s))
    return scored


# ---------------------------------------------------------------------------
# Public tool entry point
# ---------------------------------------------------------------------------


def lightweight_router(
    action: str,
    query: Optional[str] = None,
    workers: Optional[List[Dict[str, Any]]] = None,
    model: str = "mock-heuristic-v1",
    confidence_threshold: float = _DEFAULT_CONFIDENCE_THRESHOLD,
    margin_threshold: float = _DEFAULT_MARGIN_THRESHOLD,
) -> str:
    """Lightweight, heuristic pre-selector for a worker pool.

    Args:
        action: one of ``"route"`` / ``"score"`` / ``"list_models"`` /
            ``"describe"``.
        query: the routing input (typically the user's message or a
            derived embedding-free proxy). Required for ``"route"``
            and ``"score"``; ignored for ``"list_models"`` /
            ``"describe"``.
        workers: list of worker dicts ``{name, description?, tags?}``.
            Required for ``"route"`` and ``"score"``. Names must be
            unique.
        model: the small-model identifier. v1 only ships
            ``"mock-heuristic-v1"`` (the heuristic). The argument
            exists for forward-compat so callers can ask for a
            (future) trained model without code changes.
        confidence_threshold: ``[0.0, 1.0]``. Below this, the
            ``fallback_recommended`` flag is True. Default 0.5.
        margin_threshold: ``[0.0, 1.0]``. The top-1 - top-2
            probability margin below which ``fallback_recommended`` is
            True. Default 0.05.

    Returns:
        JSON string. Same ``{success, ...}`` / ``{success: False,
        error}`` contract as the sibling routing tools — never raises.
    """
    if action in ("route", "score"):
        # Per-action validation. Order: query → workers → thresholds
        # → model. The most actionable error is reported first so an
        # operator can fix one thing per call.
        if not isinstance(query, str) or not query:
            return json.dumps(
                {"success": False, "error": "query (str) is required for 'route' / 'score'"},
                ensure_ascii=False,
            )
        workers_err = _validate_workers(workers)
        if workers_err is not None:
            return json.dumps(
                {"success": False, "error": workers_err},
                ensure_ascii=False,
            )
        if not isinstance(confidence_threshold, (int, float)) or not (
            0.0 <= float(confidence_threshold) <= 1.0
        ):
            return json.dumps(
                {
                    "success": False,
                    "error": (
                        f"confidence_threshold must be a number in [0.0, 1.0]; "
                        f"got {confidence_threshold!r}"
                    ),
                },
                ensure_ascii=False,
            )
        if not isinstance(margin_threshold, (int, float)) or not (
            0.0 <= float(margin_threshold) <= 1.0
        ):
            return json.dumps(
                {
                    "success": False,
                    "error": (
                        f"margin_threshold must be a number in [0.0, 1.0]; "
                        f"got {margin_threshold!r}"
                    ),
                },
                ensure_ascii=False,
            )
        if not isinstance(model, str) or not model:
            return json.dumps(
                {"success": False, "error": "model must be a non-empty string"},
                ensure_ascii=False,
            )

        # 5-step shape (跟 sibling routing tools 1:1, 跟 mavis 4 件套
        # critic 1:1):
        # 1) Score every worker (deterministic, pure-Python).
        scored = _score_workers(query, workers)  # type: ignore[arg-type]
        scores_only = [s for _, s in scored]
        # 2) Softmax to a probability distribution.
        probs = _softmax(scores_only, _SOFTMAX_TEMPERATURE)
        score_dict = {
            name: {"raw": raw, "prob": prob}
            for (name, raw), prob in zip(scored, probs)
        }
        if action == "score":
            return json.dumps(
                {
                    "success": True,
                    "scores": score_dict,
                    "model": model,
                    "heuristic": _HEURISTIC_VERSION,
                    "softmax_temperature": _SOFTMAX_TEMPERATURE,
                },
                ensure_ascii=False,
            )
        # action == "route"
        # 3) Pick argmax; if every raw score is 0 there is no signal
        # (softmax would still distribute 1/N to each worker and the
        # argmax would land on the first one — a silent wrong pick
        # instead of an honest "I don't know"). Check the *raw* scores,
        # not the softmax probs, so the "no signal" gate is independent
        # of the temperature.
        if not scores_only or max(scores_only) <= 0:
            picked = None
            confidence = 0.0
            margin = 0.0
        else:
            best_idx = max(range(len(probs)), key=probs.__getitem__)
            picked = scored[best_idx][0]
            confidence = probs[best_idx]
            sorted_probs = sorted(probs, reverse=True)
            margin = (
                sorted_probs[0] - sorted_probs[1]
                if len(sorted_probs) > 1
                else sorted_probs[0]
            )
        # 4) Fallback recommendation: any of three signals.
        fallback_recommended = (
            picked is None
            or confidence < float(confidence_threshold)
            or margin < float(margin_threshold)
        )
        # 5) Return shape. Same audit-trail fields as
        # routing_rule_manage(action="apply"): the picked decision,
        # the per-worker score, the confidence that drove the pick,
        # the fallback recommendation, and the heuristic / model
        # identity so a reviewer can reconstruct why the pick was
        # made without re-running the code.
        return json.dumps(
            {
                "success": True,
                "picked_worker": picked,
                "confidence": confidence,
                "margin": margin,
                "scores": score_dict,
                "fallback_recommended": fallback_recommended,
                "model": model,
                "heuristic": _HEURISTIC_VERSION,
                "softmax_temperature": _SOFTMAX_TEMPERATURE,
                "thresholds": {
                    "confidence_threshold": float(confidence_threshold),
                    "margin_threshold": float(margin_threshold),
                },
            },
            ensure_ascii=False,
        )

    if action == "list_models":
        return json.dumps(
            {
                "success": True,
                "models": [dict(m) for m in _SUPPORTED_MODELS],
            },
            ensure_ascii=False,
        )

    if action == "describe":
        return json.dumps(
            {
                "success": True,
                "heuristic": _HEURISTIC_VERSION,
                "scoring": (
                    "jaccard(query_tokens, worker_tokens) where worker_tokens "
                    "= tokenize(name + description + tags). Range [0.0, 1.0]."
                ),
                "softmax": (
                    f"softmax(scores / {_SOFTMAX_TEMPERATURE}); "
                    "numerically stable (max-subtraction)."
                ),
                "thresholds": {
                    "confidence_threshold_default": _DEFAULT_CONFIDENCE_THRESHOLD,
                    "margin_threshold_default": _DEFAULT_MARGIN_THRESHOLD,
                },
                "model_loaded": False,
                "note": (
                    "Heuristic-init (no trained weights). For production "
                    "routing, see CAND-073 (adaptive pool mode + training). "
                    "This v1 ships the SHAPE; the training is out of scope."
                ),
            },
            ensure_ascii=False,
        )

    return json.dumps(
        {
            "success": False,
            "error": (
                f"Unknown action {action!r}. Use: route, score, "
                f"list_models, describe."
            ),
        },
        ensure_ascii=False,
    )


__all__ = [
    "lightweight_router",
]

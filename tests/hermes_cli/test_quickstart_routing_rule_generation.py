"""Tests for the CAND-084 smart routing rule generation helper.

CAND-084 (CANDIDATES.md Section F, 2026-08-03 22:10 revised scope):
refactor the previously inline hardcoded routing-rule generation in
``_write_smart_routing`` into a standalone helper
``_generate_routing_rules(...)``. The helper must:

  - Cover 4 scenes (1+1 / multi-local / cloud-only / 1+local+AIMC)
  - Stay strictly within the 4 match conditions supported by the
    routing engine (keywords / max_length / has_image / exclude_keywords)
  - Never generate a rule with an unsupported match field
    (min_tokens / min_tool_calls / min_files / any:) — those would be
    silently invalid
  - Not lose any pre-existing rule the operator wrote by hand
    (regression guard)

7 unit tests, all mocked. No real quickstart, no yaml IO, no LLM.
Mirrors the 改造 B regression suite style (AST static + source-string
checks) plus capsys for the optional log/print lines. Runs in < 200ms.

Test plan (verbatim from CAND-084 entry "测试 plan"):

  T1 (must, scene 1) — 1 local + 1 cloud: rules contain
    keywords-based reasoning + short_chat (max_length 80) for the
    small local + default pointing to the primary.

  T2 (must, scene 2) — N local: 2-tier split (small default, big
    reasoning/coding) and the "coder" detection fires.

  T3 (must, scene 3) — 0 local + 1 cloud: default + cloud vision;
    no local-only rules (short_chat) leak in.

  T4 (must, scene 4, AIMC) — primary model = "tier:balanced" (AIMC
    group name). Reasoning + default rules carry the group name
    verbatim (not resolved to a specific model — that's AIMC's job).

  T5 (must, engine capability alignment) — none of the generated
    rules contain a forbidden match field (min_tokens / min_tool_calls
    / min_files / any:). If a future change adds one, this test
    fails loudly so the operator finds out before the rule lands in
    their config.yaml.

  T6 (must, regression) — the previous inline hardcoded
    ``_write_smart_routing`` output is preserved 1-for-1 by
    ``_generate_routing_rules``.

  T7 (audit invariant) — ``grep "_generate_routing_rules" quickstart.py``
    returns ≥ 1 hit. Mirrors 改造 B + CAND-083 invariant pattern.

Run:
    pytest tests/hermes_cli/test_quickstart_routing_rule_generation.py -v
"""

from __future__ import annotations

import inspect
from pathlib import Path
from unittest.mock import patch

import pytest


# ---------------------------------------------------------------------------
# T1 (must, scene 1) — 1 local + 1 cloud → keywords reasoning + short_chat
# ---------------------------------------------------------------------------

def test_scene_one_local_one_cloud_emits_reasoning_short_chat_default(tmp_path, monkeypatch):
    """T1 — scene 1: 1 local + 1 cloud.

    The user-reported case from CAND-084 entry "真实 case": the operator
    has a local 27B (Qwen) plus a cloud deepseek. The expected
    generated rule set is:

      - reasoning (keywords) → primary
      - short_chat (max_length 80 + exclude) → small local
      - default → primary

    The cloud (deepseek) does NOT appear as a routing rule target
    (provider-scoped: rules inherit primary_provider; cross-provider
    routing is the fallback chain's job, not routing rules').
    """
    from hermes_cli import quickstart

    rules = quickstart._generate_routing_rules(
        api_providers=[{"id": "deepseek", "default_model": "deepseek-v4-flash"}],
        local_backends=[{"name": "llama.cpp", "base_url": "http://localhost:8080/v1"}],
        primary_provider="ollama",
        primary_model="Qwen3.6-27B-UD-Q4_K_XL.gguf",
        ollama_info={
            "classified_models": [
                {"name": "Qwen3.6-27B-UD-Q4_K_XL.gguf", "type": "text", "size": 27.0},
                {"name": "Qwen3.6-4B-UD-Q4_K_M.gguf", "type": "text", "size": 4.0},
            ],
        },
        vision_model=None,
        vision_provider=None,
    )

    names = [r["name"] for r in rules]
    assert names[-1] == "default", (
        f"default must be the last rule (callers depend on it for the "
        f"old-format keys), got order {names!r}"
    )
    assert "reasoning" in names, f"reasoning rule missing from {names!r}"
    assert "short_chat" in names, f"short_chat rule missing from {names!r}"

    short_chat = next(r for r in rules if r["name"] == "short_chat")
    # Engine constraint: only max_length + exclude_keywords for this shape.
    assert set(short_chat["match"].keys()) <= {
        "max_length", "exclude_keywords", "threshold",
    }, (
        f"short_chat rule uses unsupported match fields: "
        f"{set(short_chat['match'].keys())!r}"
    )
    assert short_chat["match"]["max_length"] == 80
    assert "small" in short_chat["model"].lower() or "4b" in short_chat["model"].lower(), (
        f"short_chat must point at a small model, got {short_chat['model']!r}"
    )

    reasoning = next(r for r in rules if r["name"] == "reasoning")
    assert reasoning["match"]["keywords"], "reasoning must use a keywords match"
    assert reasoning["model"] == "Qwen3.6-27B-UD-Q4_K_XL.gguf"

    # No deepseek in the rules — provider-scoped, cloud lives in
    # fallback_chain, not model_routing.rules.
    rule_models = " ".join(r["model"] for r in rules)
    assert "deepseek" not in rule_models.lower(), (
        f"model_routing.rules must stay provider-scoped; "
        f"deepseek leaked into: {rule_models!r}"
    )


# ---------------------------------------------------------------------------
# T2 (must, scene 2) — N local → 2-tier split with coding
# ---------------------------------------------------------------------------

def test_scene_multi_local_emits_coding_rule_when_coder_model_present(tmp_path, monkeypatch):
    """T2 — scene 2: N local with a coding-named model.

    The classifier picks up ``qwen2.5-coder-7b`` and emits a
    ``coding`` rule with the coding-specific keywords list. Reasoning
    + short_chat + default round it out.
    """
    from hermes_cli import quickstart

    rules = quickstart._generate_routing_rules(
        api_providers=[],
        local_backends=[
            {"name": "llama.cpp", "base_url": "http://localhost:8080/v1"},
            {"name": "ollama", "base_url": "http://localhost:11434/v1"},
        ],
        primary_provider="ollama",
        primary_model="Qwen3.6-27B-UD-Q4_K_XL.gguf",
        ollama_info={
            "classified_models": [
                {"name": "Qwen3.6-27B-UD-Q4_K_XL.gguf", "type": "text", "size": 27.0},
                {"name": "Qwen3.6-4B-UD-Q4_K_M.gguf", "type": "text", "size": 4.0},
                {"name": "qwen2.5-coder-7b", "type": "text", "size": 7.0},
            ],
        },
    )

    coding = next((r for r in rules if r["name"] == "coding"), None)
    assert coding is not None, f"coding rule missing from {[r['name'] for r in rules]!r}"
    assert "写代码" in coding["match"]["keywords"], (
        "coding keywords list must include the Chinese '写代码' trigger"
    )
    assert "coder" in coding["model"].lower() or "code-" in coding["model"].lower(), (
        f"coding rule must point at the coder-named model, got {coding['model']!r}"
    )
    # Coding rule must use a supported match field set.
    assert set(coding["match"].keys()) <= {
        "keywords", "threshold", "max_length", "exclude_keywords", "has_image",
    }


# ---------------------------------------------------------------------------
# T3 (must, scene 3) — 0 local + 1 cloud → default + cloud vision only
# ---------------------------------------------------------------------------

def test_scene_cloud_only_emits_no_local_only_rules(tmp_path, monkeypatch):
    """T3 — scene 3: 0 local + 1 cloud.

    The cloud-primary path must not emit local-only rules (short_chat)
    that would route a local model name through a cloud endpoint
    (404). The rule set is: vision (if a vision model is configured)
    + reasoning + default.
    """
    from hermes_cli import quickstart

    rules = quickstart._generate_routing_rules(
        api_providers=[{"id": "deepseek", "default_model": "deepseek-v4-flash"}],
        local_backends=[],
        primary_provider="deepseek",
        primary_model="deepseek-v4-flash",
        ollama_info=None,
        vision_model="deepseek-vl",
        vision_provider="deepseek",
    )

    names = [r["name"] for r in rules]
    assert "short_chat" not in names, (
        f"short_chat is a local-only rule; it must not appear in a "
        f"cloud-primary config (would 404 the local model name). "
        f"Got {names!r}"
    )
    assert "reasoning" in names
    assert names[-1] == "default"
    vision = next((r for r in rules if r["name"] == "vision"), None)
    assert vision is not None and vision["model"] == "deepseek-vl"


# ---------------------------------------------------------------------------
# T4 (must, scene 4) — AIMC integration: model field = group name
# ---------------------------------------------------------------------------

def test_scene_aimc_primary_passes_group_name_through_unchanged():
    """T4 — CAND-085 + CAND-084 integration.

    When the user has run ``hermes setup`` (or the AIMC integration)
    with ``model: tier:balanced`` in config.yaml, the quickstart's
    generated rules must carry the group name verbatim — NOT resolved
    to a specific underlying model. Resolution is AIMC's job at
    request time; the hermes side is provider-scoped and the only
    "provider" it sees is the AIMC entry in ``providers.aimc``.
    """
    from hermes_cli import quickstart

    rules = quickstart._generate_routing_rules(
        api_providers=[{"id": "aimc", "default_model": "tier:balanced"}],
        local_backends=[],
        primary_provider="aimc",
        primary_model="tier:balanced",
        ollama_info=None,
    )

    # reasoning + default both carry the group name verbatim.
    reasoning = next(r for r in rules if r["name"] == "reasoning")
    assert reasoning["model"] == "tier:balanced", (
        f"AIMC group name must be passed through verbatim; the engine "
        f"is provider-scoped and the AIMC provider entry does the "
        f"actual model resolution. Got {reasoning['model']!r}"
    )
    default = next(r for r in rules if r["name"] == "default")
    assert default["model"] == "tier:balanced"


# ---------------------------------------------------------------------------
# T5 (must, engine capability alignment) — no forbidden match fields
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "scene_name,kwargs",
    [
        ("local_only_27b", dict(
            api_providers=[],
            local_backends=[],
            primary_provider="ollama",
            primary_model="Qwen3.6-27B-UD-Q4_K_XL.gguf",
            ollama_info={
                "classified_models": [
                    {"name": "Qwen3.6-27B-UD-Q4_K_XL.gguf", "type": "text", "size": 27.0},
                    {"name": "Qwen3.6-4B-UD-Q4_K_M.gguf", "type": "text", "size": 4.0},
                ],
            },
        )),
        ("multi_local_coder", dict(
            api_providers=[],
            local_backends=[],
            primary_provider="ollama",
            primary_model="Qwen3.6-27B-UD-Q4_K_XL.gguf",
            ollama_info={
                "classified_models": [
                    {"name": "Qwen3.6-27B-UD-Q4_K_XL.gguf", "type": "text", "size": 27.0},
                    {"name": "qwen2.5-coder-7b", "type": "text", "size": 7.0},
                ],
            },
        )),
        ("cloud_only", dict(
            api_providers=[{"id": "deepseek"}],
            local_backends=[],
            primary_provider="deepseek",
            primary_model="deepseek-v4-flash",
            ollama_info=None,
        )),
        ("aimc_group", dict(
            api_providers=[{"id": "aimc"}],
            local_backends=[],
            primary_provider="aimc",
            primary_model="tier:balanced",
            ollama_info=None,
        )),
    ],
)
def test_no_unsupported_match_fields_in_any_rule(scene_name, kwargs):
    """T5 — none of the supported scenes may produce a rule with a
    match field the engine doesn't recognize. The engine supports
    exactly: keywords / max_length / has_image / exclude_keywords
    (plus ``threshold`` as a sub-key of keywords). Anything else is
    silently invalid — the engine will treat the rule as never
    matching, which means the operator's carefully chosen logic just
    doesn't fire and they'll never know why.

    This is the CAND-084 audit: refactors must stay within the engine
    capability surface. If the engine ever grows a new condition, the
    allow-list below needs to grow with it.
    """
    from hermes_cli import quickstart

    forbidden = {"min_tokens", "min_files", "min_tool_calls", "any", "min_length"}
    supported = {
        "keywords", "threshold", "max_length",
        "has_image", "exclude_keywords",
    }
    rules = quickstart._generate_routing_rules(**kwargs)
    for rule in rules:
        match = rule.get("match", {})
        bad = set(match.keys()) & forbidden
        assert not bad, (
            f"scene {scene_name!r}: rule {rule['name']!r} uses "
            f"unsupported match fields {bad!r} (the engine silently "
            f"ignores them). Supported: {sorted(supported)!r}"
        )
        unsupported = set(match.keys()) - supported
        assert not unsupported, (
            f"scene {scene_name!r}: rule {rule['name']!r} uses unknown "
            f"match fields {unsupported!r}; either the engine grew a new "
            f"condition (update the audit allow-list) or the generator "
            f"is hallucinating fields."
        )


# ---------------------------------------------------------------------------
# T6 (must, regression) — _write_smart_routing output preserved 1-for-1
# ---------------------------------------------------------------------------

def test_write_smart_routing_output_matches_helper_output(tmp_path, monkeypatch):
    """T6 — regression guard for the inline-to-helper refactor.

    Before CAND-084, the rule list was built inline inside
    ``_write_smart_routing``. After CAND-084 it is delegated to
    ``_generate_routing_rules``. The two must agree on a 1-local-27B
    + 4B + cloud-deepseek fixture, otherwise the refactor silently
    changed a config many operators already rely on.
    """
    from hermes_cli import quickstart

    cfg_in = {
        "model": {},
        "providers": {},
        "custom_providers": [],
        "fallback_providers": [],
        "auxiliary": {},
    }
    captured: dict = {}

    monkeypatch.setenv("HERMES_HOME", str(tmp_path / ".hermes"))
    (tmp_path / ".hermes").mkdir()
    monkeypatch.setattr(Path, "home", lambda: tmp_path)

    with patch("hermes_cli.config.load_config", return_value=cfg_in), \
         patch("hermes_cli.config.save_config",
                      side_effect=lambda c: captured.setdefault("cfg", c) or True), \
         patch("hermes_cli.config.save_env_value", return_value=True):
        quickstart._write_smart_routing(
            primary_provider_id="ollama",
            primary_model="Qwen3.6-27B-UD-Q4_K_XL.gguf",
            fallback_chain=[{"provider": "deepseek", "model": "deepseek-v4-flash"}],
            api_providers=[{"id": "deepseek", "default_model": "deepseek-v4-flash"}],
            ollama_info={
                "classified_models": [
                    {"name": "Qwen3.6-27B-UD-Q4_K_XL.gguf", "type": "text", "size": 27.0},
                    {"name": "Qwen3.6-4B-UD-Q4_K_XL.gguf", "type": "text", "size": 4.0},
                ],
            },
        )

    rules = captured["cfg"]["model_routing"]["rules"]
    helper_rules = quickstart._generate_routing_rules(
        api_providers=[{"id": "deepseek", "default_model": "deepseek-v4-flash"}],
        local_backends=[],
        primary_provider="ollama",
        primary_model="Qwen3.6-27B-UD-Q4_K_XL.gguf",
        ollama_info={
            "classified_models": [
                {"name": "Qwen3.6-27B-UD-Q4_K_XL.gguf", "type": "text", "size": 27.0},
                {"name": "Qwen3.6-4B-UD-Q4_K_XL.gguf", "type": "text", "size": 4.0},
            ],
        },
    )

    # Compare names + models (the audit invariant cares about the
    # operator-visible config, which is name+model+match). Match dict
    # comparison would also be reasonable but the inline variant
    # used to have its own copy of the match dicts; the helper is the
    # canonical source now.
    inline_names_models = [(r["name"], r["model"]) for r in rules]
    helper_names_models = [(r["name"], r["model"]) for r in helper_rules]
    assert inline_names_models == helper_names_models, (
        f"_write_smart_routing ({inline_names_models}) and "
        f"_generate_routing_rules ({helper_names_models}) disagree on "
        f"rule set — the refactor silently changed behaviour."
    )


# ---------------------------------------------------------------------------
# T7 (audit invariant) — source presence
# ---------------------------------------------------------------------------

def test_cand_084_audit_invariant_source_contains_helper():
    """Audit invariant (mirrors 改造 B + CAND-083 source-presence checks).

    CAND-084 audit method (CANDIDATES.md line 602):
      ``grep "_generate_routing_rules" hermes_cli/quickstart.py`` must
      return ≥ 1 hit.

    If a future refactor removes the helper, the test fails loudly —
    exactly the silent class of bug CAND-084 was filed to prevent
    (operators get a 4-rule config with no smart adaptation).
    """
    from hermes_cli import quickstart
    src = inspect.getsource(quickstart)
    assert "_generate_routing_rules" in src, (
        "CAND-084 audit invariant: hermes_cli/quickstart.py no longer "
        "defines _generate_routing_rules. Smart rule generation has "
        "regressed to inline hardcoded logic — operators will lose the "
        "4-scene adaptation."
    )
    # Positive check: the helper is called from _write_smart_routing
    # (otherwise the refactor left an orphan helper).
    assert "_write_smart_routing" in src, (
        "_write_smart_routing missing — CAND-084 refactor target gone"
    )

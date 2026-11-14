"""Tests for quickstart's smart routing rule generation (K-71 simplified).

K-71 (2026-11-14) narrowed quickstart's local tier to local_runtime only:
Ollama / LM Studio / external llama-server / embedded were removed from the
detection and routing story. The helper now covers three shapes:

  - cloud primary (with an optional cloud vision model)
  - AIMC group primary (group name passed through verbatim)
  - local_runtime primary (``provider=llamacpp``, no vision rule)

The helper must still:

  - Stay strictly within the match conditions supported by the routing
    engine (keywords / max_length / has_image / exclude_keywords)
  - Never generate a rule with an unsupported match field
    (min_tokens / min_tool_calls / min_files / any:) — those would be
    silently invalid
  - Keep default as the last rule (callers depend on it for the
    old-format keys)

Run:
    scripts/run_tests.sh tests/hermes_cli/test_quickstart_routing_rule_generation.py -q
"""

from __future__ import annotations

import inspect
from pathlib import Path
from unittest.mock import patch

import pytest


def test_cloud_primary_emits_vision_reasoning_default():
    """Cloud primary + a configured cloud vision model."""
    from hermes_cli import quickstart

    rules = quickstart._generate_routing_rules(
        primary_provider="deepseek",
        primary_model="deepseek-v4-flash",
        vision_model="deepseek-vl",
        vision_provider="deepseek",
    )

    names = [r["name"] for r in rules]
    assert names == ["vision", "reasoning", "default"], names
    vision = next(r for r in rules if r["name"] == "vision")
    assert vision["model"] == "deepseek-vl"
    assert vision["match"] == {"has_image": True}
    reasoning = next(r for r in rules if r["name"] == "reasoning")
    assert reasoning["match"]["keywords"]
    assert reasoning["model"] == "deepseek-v4-flash"


def test_local_runtime_primary_emits_reasoning_default_without_vision():
    """local_runtime (``provider=llamacpp``) never emits a cloud vision rule."""
    from hermes_cli import quickstart

    rules = quickstart._generate_routing_rules(
        primary_provider="llamacpp",
        primary_model="Qwen3-8B-Q4_K_M",
        vision_model="deepseek-vl",  # present, but primary is not cloud
        vision_provider="deepseek",
    )

    names = [r["name"] for r in rules]
    assert "vision" not in names, f"cloud vision leaked into a local primary: {names!r}"
    assert names == ["reasoning", "default"], names
    assert next(r for r in rules if r["name"] == "default")["model"] == "Qwen3-8B-Q4_K_M"


def test_aimc_primary_passes_group_name_through_unchanged():
    """AIMC group primary: rules carry the group name verbatim."""
    from hermes_cli import quickstart

    rules = quickstart._generate_routing_rules(
        primary_provider="aimc",
        primary_model="tier:balanced",
        reasoning_model="tier:strong",
    )

    reasoning = next(r for r in rules if r["name"] == "reasoning")
    assert reasoning["model"] == "tier:strong"
    default = next(r for r in rules if r["name"] == "default")
    assert default["model"] == "tier:balanced"


@pytest.mark.parametrize(
    "scene_name,kwargs",
    [
        ("cloud_only", dict(
            primary_provider="deepseek",
            primary_model="deepseek-v4-flash",
            vision_model="deepseek-vl",
            vision_provider="deepseek",
        )),
        ("aimc_group", dict(
            primary_provider="aimc",
            primary_model="tier:balanced",
        )),
        ("local_runtime", dict(
            primary_provider="llamacpp",
            primary_model="Qwen3-8B-Q4_K_M",
        )),
    ],
)
def test_no_unsupported_match_fields_in_any_rule(scene_name, kwargs):
    """Engine capacity audit: no rule may use an unknown match field.

    The engine supports exactly: keywords / max_length / has_image /
    exclude_keywords (plus ``threshold`` as a sub-key of keywords). Anything
    else is silently invalid — the rule would never fire.
    """
    from hermes_cli import quickstart

    forbidden = {"min_tokens", "min_files", "min_tool_calls", "any", "min_length"}
    supported = {"keywords", "threshold", "max_length", "has_image", "exclude_keywords"}
    rules = quickstart._generate_routing_rules(**kwargs)
    for rule in rules:
        match = rule.get("match", {})
        bad = set(match.keys()) & forbidden
        assert not bad, f"scene {scene_name!r}: rule {rule['name']!r} uses {bad!r}"
        unsupported = set(match.keys()) - supported
        assert not unsupported, (
            f"scene {scene_name!r}: rule {rule['name']!r} uses unknown "
            f"match fields {unsupported!r}"
        )


def test_write_smart_routing_output_matches_helper_output(tmp_path, monkeypatch):
    """``_write_smart_routing`` must delegate to the same helper output."""
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
            primary_provider_id="llamacpp",
            primary_model="Qwen3-8B-Q4_K_M",
            fallback_chain=[{"provider": "deepseek", "model": "deepseek-v4-flash"}],
            api_providers=[{"id": "deepseek", "default_model": "deepseek-v4-flash"}],
        )

    rules = captured["cfg"]["model_routing"]["rules"]
    helper_rules = quickstart._generate_routing_rules(
        primary_provider="llamacpp",
        primary_model="Qwen3-8B-Q4_K_M",
    )

    inline_names_models = [(r["name"], r["model"]) for r in rules]
    helper_names_models = [(r["name"], r["model"]) for r in helper_rules]
    assert inline_names_models == helper_names_models, (
        f"_write_smart_routing ({inline_names_models}) and "
        f"_generate_routing_rules ({helper_names_models}) disagree"
    )


def test_audit_invariant_source_contains_helper():
    """The helper and its delegating caller must both stay in the facade."""
    from hermes_cli import quickstart

    src = inspect.getsource(quickstart)
    assert "_generate_routing_rules" in src
    assert "_write_smart_routing" in src

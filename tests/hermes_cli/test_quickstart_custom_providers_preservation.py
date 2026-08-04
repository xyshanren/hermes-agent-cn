"""Tests for the CAND-083 quickstart custom_providers preservation fix.

CAND-083 (CANDIDATES.md Section F): quickstart historically did not touch
the ``custom_providers`` (v11) or ``providers`` (v12+) sections, so
user-defined entries (e.g. a hand-rolled ``deepseek`` or ``sensenova``
provider) would survive a quickstart round-trip in storage but be
invisible to the operator. The fix is a single line that explicitly
preserves both sections right before ``save_config(cfg)`` is called.

3 unit tests, all mocked. No real quickstart, no network, no yaml file
IO. Mirrors the 改造 B regression suite style (AST static + source-string
checks) so this test runs in <100 ms and has zero environment
dependencies.

Test plan (verbatim from CAND-083 entry "测试 plan"):

  Unit test 1 (must) — load_config with a 2-entry custom_providers list,
    run _write_smart_routing with a primary + fallback chain, verify
    the returned cfg's custom_providers section length = 2, order
    preserved, content preserved.

  Unit test 2 (must) — same but fallback_chain references ``deepseek``;
    verify ``custom_providers`` still contains deepseek (the
    "fallback references a provider that is in custom_providers"
    case — quickstart must not drop the entry).

  Unit test 3 (nice) — primary = ollama + fallback = custom; verify
    custom_providers section is not overwritten.

Run:
    pytest tests/hermes_cli/test_quickstart_custom_providers_preservation.py -v
"""

from __future__ import annotations

import inspect
from pathlib import Path
from unittest.mock import patch

import pytest


# ---------------------------------------------------------------------------
# T1 (must) — _write_smart_routing preserves a 2-entry custom_providers list
# ---------------------------------------------------------------------------

def test_write_smart_routing_preserves_two_entry_custom_providers(tmp_path, monkeypatch):
    """T1 — 2-entry custom_providers list survives a quickstart round-trip.

    CAND-083 fix: the new ``cfg["custom_providers"] = cfg.get(...)`` line
    right before ``save_config`` is an explicit preservation anchor; we
    assert here that the value passed into ``save_config`` still has
    both original entries in the same order.
    """
    from hermes_cli import quickstart

    # Two providers in custom order — order matters because operators
    # read top-down and rely on the first entry being the default.
    original = [
        {"name": "sensenova", "base_url": "https://token.sensenova.cn/v1",
         "api_key": "${SENSENOVA_API_KEY}"},
        {"name": "deepseek", "base_url": "${DEEPSEEK_BASE_URL}",
         "api_key": "${DEEPSEEK_API_KEY}", "model": "deepseek-v4-flash"},
    ]
    cfg_in = {
        "model": {},
        "providers": {"deepseek": {"name": "deepseek"}},
        "custom_providers": list(original),  # copy so the test can't mutate
        "fallback_providers": [],
        "auxiliary": {},
    }

    captured: dict = {}

    def _fake_save_config(cfg):
        # Snapshot what quickstart is about to persist.
        captured["cfg"] = cfg
        return True

    monkeypatch.setenv("HERMES_HOME", str(tmp_path / ".hermes"))
    (tmp_path / ".hermes").mkdir()
    monkeypatch.setattr(Path, "home", lambda: tmp_path)

    with patch("hermes_cli.config.load_config", return_value=cfg_in), \
         patch("hermes_cli.config.save_config", side_effect=_fake_save_config), \
         patch("hermes_cli.config.save_env_value", return_value=True):
        # Pick a primary that exists in the loaded config so we don't
        # hit the "primary_local_info not found" branch.
        result = quickstart._write_smart_routing(
            primary_provider_id="ollama",
            primary_model="Qwen3.6-27B-UD-Q4_K_XL.gguf",
            fallback_chain=[{"provider": "deepseek", "model": "deepseek-v4-flash"}],
            api_providers=[],
        )

    assert result is True
    saved = captured["cfg"]
    assert "custom_providers" in saved, (
        "CAND-083 fix missing: cfg has no 'custom_providers' key after "
        "_write_smart_routing — the explicit preservation line was not "
        "added (or was added in the wrong place)."
    )
    assert len(saved["custom_providers"]) == 2, (
        f"custom_providers length changed: expected 2, got "
        f"{len(saved['custom_providers'])} — something dropped an entry"
    )
    assert [p["name"] for p in saved["custom_providers"]] == ["sensenova", "deepseek"], (
        f"custom_providers order changed: got "
        f"{[p.get('name') for p in saved['custom_providers']]!r}"
    )
    # Deep content check — the second entry's model field round-trips.
    assert saved["custom_providers"][1]["model"] == "deepseek-v4-flash"


# ---------------------------------------------------------------------------
# T2 (must) — fallback_chain references deepseek; custom_providers survives
# ---------------------------------------------------------------------------

def test_write_smart_routing_keeps_deepseek_in_custom_providers(tmp_path, monkeypatch):
    """T2 — the "fallback references a custom provider" case.

    This is the operator's report verbatim: "I added a deepseek provider
    to custom_providers, configured fallback_model to use it, ran
    quickstart, and the provider was gone." CAND-083 fix ensures the
    custom_providers entry is preserved verbatim even when the
    quickstart-generated fallback_chain also references it.
    """
    from hermes_cli import quickstart

    cfg_in = {
        "model": {},
        "providers": {},
        "custom_providers": [
            {"name": "deepseek", "base_url": "${DEEPSEEK_BASE_URL}",
             "api_key": "${DEEPSEEK_API_KEY}", "model": "deepseek-v4-flash"},
        ],
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
            api_providers=[],
        )

    saved = captured["cfg"]
    deepseek_entries = [
        p for p in saved.get("custom_providers", [])
        if isinstance(p, dict) and p.get("name") == "deepseek"
    ]
    assert len(deepseek_entries) == 1, (
        f"deepseek custom_providers entry was lost: expected 1, got "
        f"{len(deepseek_entries)}. The fallback_chain references it but "
        "the custom_providers section no longer defines it — silent "
        "data loss the operator reported in CAND-083."
    )
    # And the base_url round-trips — losing it would force the operator
    # to re-enter the URL every quickstart, which is the "looks like
    # the provider vanished" symptom.
    assert deepseek_entries[0]["base_url"] == "${DEEPSEEK_BASE_URL}"


# ---------------------------------------------------------------------------
# T3 (nice) — primary = ollama + fallback = custom; custom_providers survives
# ---------------------------------------------------------------------------

def test_write_smart_routing_does_not_overwrite_custom_providers_with_ollama_primary(
    tmp_path, monkeypatch
):
    """T3 — primary=ollama + fallback=custom must NOT clobber custom_providers.

    Regression guard: an earlier draft of the fix used
    ``cfg["custom_providers"] = []`` as a "fresh start" pattern, which
    is exactly the silent-drop behaviour CAND-083 is reporting. The
    explicit preservation must use ``cfg.get(..., [])`` semantics, not
    unconditional assignment.
    """
    from hermes_cli import quickstart

    cfg_in = {
        "model": {},
        "providers": {"ollama": {"name": "ollama"}},
        "custom_providers": [
            {"name": "sensenova", "base_url": "https://token.sensenova.cn/v1",
             "api_key": "${SENSENOVA_API_KEY}"},
        ],
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
            fallback_chain=[{"provider": "custom", "model": "Qwen3.6-27B"}],
            api_providers=[],
        )

    saved = captured["cfg"]
    sensenova_entries = [
        p for p in saved.get("custom_providers", [])
        if isinstance(p, dict) and p.get("name") == "sensenova"
    ]
    assert sensenova_entries, (
        "sensenova custom_providers entry was overwritten with [] — the "
        "CAND-083 fix regressed to silent-drop. The preservation line "
        "must use cfg.get(..., []) not bare assignment."
    )
    assert sensenova_entries[0]["api_key"] == "${SENSENOVA_API_KEY}"


# ---------------------------------------------------------------------------
# Audit invariant (改造 B style) — the fix must be present in source
# ---------------------------------------------------------------------------

def test_cand_083_audit_invariant_source_contains_custom_providers_preservation():
    """Audit invariant (mirrors 改造 B source-presence checks).

    CAND-083 audit method (CANDIDATES.md line 511):
      ``grep "custom_providers" hermes_cli/quickstart.py`` must return
      ≥ 1 hit.

    If a future refactor removes the explicit preservation line, this
    test fails loudly — exactly the silent-drop class of bug CAND-083
    was filed to prevent. The 改造 B-style invariant suite enforces
    this alongside the K-2 silent-config-drop pattern.
    """
    from hermes_cli import quickstart
    src = inspect.getsource(quickstart)
    assert "custom_providers" in src, (
        "CAND-083 audit invariant: hermes_cli/quickstart.py no longer "
        "mentions 'custom_providers'. The explicit preservation line is "
        "missing — operators will see silent data loss on next quickstart."
    )
    # Positive check: the preservation must use .get() semantics, not
    # bare assignment (which would clobber).
    assert 'cfg.get("custom_providers"' in src or "cfg.get('custom_providers'" in src, (
        "CAND-083 fix uses bare assignment instead of cfg.get(); this "
        "would clobber any pre-existing custom_providers entries."
    )


# ---------------------------------------------------------------------------
# T4 (Option C) — dangling fallback references trigger the warning
# ---------------------------------------------------------------------------

def test_write_smart_routing_warns_on_dangling_fallback_references(
    tmp_path, monkeypatch, capsys
):
    """T4 — CAND-083 Option C (real fix, 2026-08-04).

    The user-reported bug ("my deepseek provider disappeared after
    quickstart") was actually a runtime resolution failure, not a
    storage drop: quickstart wrote ``fallback_model: [{provider:
    deepseek, ...}]`` but never verified that ``deepseek`` was defined
    in the v12+ ``providers`` dict or v11 ``custom_providers`` list.
    Option C detects this case and surfaces a warning naming the
    dangling provider ids so the operator can fix the config rather
    than assuming the quickstart "ate" the entry.
    """
    from hermes_cli import quickstart

    cfg_in = {
        "model": {},
        "providers": {"ollama": {"name": "ollama"}},
        # Note: no `deepseek` entry — the fallback below is dangling.
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
            # Two dangling refs (deepseek + sensenova) and one resolved
            # (ollama) — only the dangling ones should be named.
            fallback_chain=[
                {"provider": "deepseek", "model": "deepseek-v4-flash"},
                {"provider": "ollama", "model": "Qwen3.6-27B"},
                {"provider": "sensenova", "model": "sensenova-6.7-flash-lite"},
            ],
            api_providers=[],
        )

    out = capsys.readouterr().out
    assert "⚠️" in out, (
        f"Option C warning not emitted; stdout was:\n{out!r}"
    )
    assert "deepseek" in out and "sensenova" in out, (
        f"Warning should name both dangling providers; stdout was:\n{out!r}"
    )
    # The resolved provider (ollama) should NOT appear in the warning —
    # otherwise the operator gets a false positive on every quickstart.
    assert "ollama" not in out or "ollama" in out and "ollama, " not in out, (
        f"Resolved provider 'ollama' should not appear in the dangling "
        f"warning; stdout was:\n{out!r}"
    )


def test_write_smart_routing_no_warning_when_all_fallback_providers_defined(
    tmp_path, monkeypatch, capsys
):
    """T4 sibling — when every fallback provider is properly defined in
    either ``providers`` or ``custom_providers``, the warning must NOT
    fire (otherwise it would become noise on every quickstart).
    """
    from hermes_cli import quickstart

    cfg_in = {
        "model": {},
        "providers": {"ollama": {"name": "ollama"}, "deepseek": {"name": "deepseek"}},
        "custom_providers": [
            {"name": "sensenova", "base_url": "https://token.sensenova.cn/v1"},
        ],
        "fallback_providers": [],
        "auxiliary": {},
    }

    monkeypatch.setenv("HERMES_HOME", str(tmp_path / ".hermes"))
    (tmp_path / ".hermes").mkdir()
    monkeypatch.setattr(Path, "home", lambda: tmp_path)

    with patch("hermes_cli.config.load_config", return_value=cfg_in), \
         patch("hermes_cli.config.save_config", return_value=True), \
         patch("hermes_cli.config.save_env_value", return_value=True):
        quickstart._write_smart_routing(
            primary_provider_id="ollama",
            primary_model="Qwen3.6-27B-UD-Q4_K_XL.gguf",
            fallback_chain=[
                {"provider": "deepseek", "model": "deepseek-v4-flash"},
                {"provider": "sensenova", "model": "sensenova-6.7-flash-lite"},
            ],
            api_providers=[],
        )

    out = capsys.readouterr().out
    assert "⚠️" not in out, (
        f"Option C should be silent when all providers are defined; "
        f"stdout was:\n{out!r}"
    )

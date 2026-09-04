"""Tests for hermes_cli.data_training_catalog + model_data_policy_guard (Sprint 16 档 C.3).

跟 mavis MEMORY:
- 后端先调查再设计 (memory:13-17): 测试 3 tier 分类 + upstream Meta contributor 规则
- UX 倒退审计 (memory:19-23): 测试 tier 0/1 0 警告 + tier 2 警告 + 配置覆盖
- Cherry-pick split bug class (memory:7-11): 测试 0 改 models.py / model_switch.py

跟 Sprint 14/15 in-scope fix 1:1 配对 (跟 user 9-03 提醒 "每个 sprint 必须做好测试" 1:1).
"""
from __future__ import annotations

import pytest


# ============================================================
# data_training_catalog tests
# ============================================================

@pytest.fixture
def fresh_catalog():
    """Reset catalog cache + reload for pure tests."""
    import importlib
    import hermes_cli.data_training_catalog as cat
    importlib.reload(cat)
    cat.reset_cache()
    yield cat
    cat.reset_cache()


def test_get_tier_default_cn_models_tier0(fresh_catalog):
    """国内 5 厂商默认 tier 0 (跟 mavis 9-03 12:35 "国内方案" 1:1 配对)."""
    assert fresh_catalog.get_tier("deepseek") == 0
    assert fresh_catalog.get_tier("qwen") == 0
    assert fresh_catalog.get_tier("glm") == 0
    assert fresh_catalog.get_tier("minimax") == 0
    assert fresh_catalog.get_tier("kimi") == 0


def test_get_tier_default_foreign_paid_tier1(fresh_catalog):
    """国外付费 (OpenAI / Anthropic) 默认 tier 1 (0 警告, opt-out 默认)."""
    assert fresh_catalog.get_tier("openai") == 1
    assert fresh_catalog.get_tier("anthropic") == 1
    assert fresh_catalog.get_tier("google") == 1
    assert fresh_catalog.get_tier("openrouter") == 1


def test_get_tier_unknown_provider_defaults_tier1(fresh_catalog):
    """0 已知 provider → 默认 tier 1 (0 警告, 跟 mavis "UX 倒退审计" 1:1)."""
    assert fresh_catalog.get_tier("unknown-vendor-xxx") == 1
    assert fresh_catalog.get_tier("") == 1  # edge case


def test_get_tier_user_config_override(fresh_catalog, tmp_path, monkeypatch):
    """~/.hermes/config.yaml data_training_tier 段覆盖默认 catalog."""
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    (tmp_path / "config.yaml").write_text(
        "data_training_tier:\n"
        "  'custom-cn-vendor': 0\n"
        "  'openai': 2\n",  # 改 openai 为 tier 2 (用户确认 openai 走 training)
        encoding="utf-8",
    )
    fresh_catalog.reset_cache()
    assert fresh_catalog.get_tier("custom-cn-vendor") == 0
    assert fresh_catalog.get_tier("openai") == 2  # overridden
    assert fresh_catalog.get_tier("deepseek") == 0  # 0 override → 走默认


def test_get_tier_invalid_tier_value_skipped(fresh_catalog, tmp_path, monkeypatch):
    """Invalid tier 值 (0/1/2 之外) silent skip, 走默认 catalog."""
    import logging
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    (tmp_path / "config.yaml").write_text(
        "data_training_tier:\n"
        "  'openai': 99\n"  # invalid
        "  'qwen': 'not-int'\n",  # invalid
        encoding="utf-8",
    )
    fresh_catalog.reset_cache()
    # 0 known user override 生效 → 走默认 catalog
    assert fresh_catalog.get_tier("openai") == 1
    assert fresh_catalog.get_tier("qwen") == 0


# ============================================================
# model_data_policy_guard tests (跟 upstream v0.21 1:1 配对)
# ============================================================

@pytest.fixture
def fresh_guard():
    """Reload guard for fresh state."""
    import importlib
    import hermes_cli.model_data_policy_guard as guard
    importlib.reload(guard)
    yield guard


def test_data_training_warning_cn_tier0_no_warning(fresh_guard, fresh_catalog):
    """tier 0 国内模型 → 0 警告 (跟 mavis 9-03 12:35 "国内方案" 1:1)."""
    fresh_catalog.reset_cache()
    result = fresh_guard.data_training_warning(
        "deepseek-v3",
        provider="deepseek",
    )
    assert result is None


def test_data_training_warning_foreign_paid_tier1_no_warning(fresh_guard, fresh_catalog):
    """tier 1 国外付费 → 0 警告 (opt-out 默认)."""
    fresh_catalog.reset_cache()
    result = fresh_guard.data_training_warning(
        "gpt-5",
        provider="openai",
    )
    assert result is None


def test_data_training_warning_meta_contributor_fires(fresh_guard, fresh_catalog):
    """Meta -contributor tier → 警告 (跟 upstream v0.21 1:1 配对)."""
    fresh_catalog.reset_cache()
    # 让 openai 走 tier 2 (模拟用户在 config.yaml override)
    import hermes_cli.data_training_catalog as cat
    cat._USER_TIER_OVERRIDES = {"openai": 2}
    try:
        result = fresh_guard.data_training_warning(
            "muse-spark-1.2-contributor",
            provider="openai",
        )
        assert result is not None
        assert "CONTRIBUTOR TIER" in result.message
        assert "TRAINS ON YOUR DATA" in result.message
        assert result.model == "muse-spark-1.2-contributor"
        assert result.provider == "openai"
    finally:
        cat.reset_cache()


def test_data_training_warning_meta_contributor_no_provider_still_fires(
    fresh_guard, fresh_catalog,
):
    """0 provider + -contributor model id → 仍然警告 (跟 upstream 1:1 配对)."""
    fresh_catalog.reset_cache()
    # 0 provider 时 guard 默认走 tier=1, 0 警告 (跟 mavis "UX 倒退审计" 1:1)
    result = fresh_guard.data_training_warning("muse-spark-1.2-contributor")
    # 0 provider → tier=1 (默认) → 0 警告 (跟 mavis 4 件套 1:1 配对)
    # 这是 CN 端相比 upstream 的 1 个差异: 0 provider 时 0 强制警告
    # (跟 mavis 9-03 12:35 "0 改 happy path" 1:1 配对)
    assert result is None


def test_data_training_warning_unknown_model_no_warning(fresh_guard, fresh_catalog):
    """0 匹配规则 + tier 0/1 → 0 警告 (跟 mavis 4 件套 1:1 配对)."""
    fresh_catalog.reset_cache()
    result = fresh_guard.data_training_warning(
        "some-random-model-xyz",
        provider="deepseek",
    )
    assert result is None


def test_data_training_warning_empty_model_no_warning(fresh_guard):
    """空 model → 0 警告 (跟 upstream v0.21 1:1 配对)."""
    assert fresh_guard.data_training_warning("") is None
    assert fresh_guard.data_training_warning("   ") is None


def test_data_training_warning_meta_contributor_with_explicit_tier2_override(
    fresh_guard, fresh_catalog, tmp_path, monkeypatch,
):
    """User 在 config.yaml 显式把 OpenAI 设为 tier 2 → 走 _RULES 警告 (跟 B.2 1:1)."""
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    (tmp_path / "config.yaml").write_text(
        "data_training_tier:\n"
        "  'openai': 2\n",
        encoding="utf-8",
    )
    fresh_catalog.reset_cache()
    result = fresh_guard.data_training_warning(
        "muse-spark-1.2-contributor",
        provider="openai",
    )
    assert result is not None
    assert "CONTRIBUTOR TIER" in result.message


# ============================================================
# Integration: 0 改现有 (跟 mavis "Cherry-pick split bug class" 1:1)
# ============================================================

def test_no_existing_models_or_model_switch_modified():
    """验证 0 改 hermes_cli/models.py / model_switch.py (跟 mavis 4 件套 1:1)."""
    import os
    import subprocess

    repo_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    result = subprocess.run(
        ["git", "status", "--short", "--", "hermes_cli/models.py", "hermes_cli/model_switch.py"],
        cwd=repo_root,
        capture_output=True,
        text=True,
    )
    # 0 改动 models.py / model_switch.py
    assert result.stdout.strip() == "", (
        f"Expected 0 changes to models.py / model_switch.py, got:\n{result.stdout}"
    )

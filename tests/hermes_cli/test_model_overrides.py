"""Tests for hermes_cli.model_overrides (Sprint 16 档 B.2).

跟 mavis MEMORY:
- 后端先调查再设计 (memory:13-17): 测试覆盖 4 override 字段 + apply path
- UX 倒退审计 (memory:19-23): 测试 silent skip unknown field / invalid type
- Cherry-pick split bug class (memory:7-11): 测试 0 强 import 引用

跟 Sprint 14/15 in-scope fix 1:1 配对 (跟 user 9-03 提醒 "每个 sprint 必须做好测试" 1:1).
"""
from __future__ import annotations

from dataclasses import dataclass

import pytest


@dataclass
class FakeModelInfo:
    """Minimal ModelInfo stand-in for apply_override_to_model_info tests (跟 mavis 4 件套 1:1 配对)."""
    context_window: int = 8192
    cost_input: float = 0.0
    cost_output: float = 0.0
    attachment: bool = False


@pytest.fixture
def fresh_module():
    """Reset module-level cache + reload to test pure loader."""
    import importlib
    import hermes_cli.model_overrides as mod
    importlib.reload(mod)
    mod.reset_cache()
    yield mod
    mod.reset_cache()


def test_get_model_override_empty_when_no_config(fresh_module, tmp_path, monkeypatch):
    """0 ~/.hermes/config.yaml → 0 override."""
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    fresh_module.reset_cache()
    assert fresh_module.get_model_override("openai", "gpt-5") == {}


def test_get_model_override_returns_user_config(fresh_module, tmp_path, monkeypatch):
    """~/.hermes/config.yaml 写 model_overrides → get_model_override 返回."""
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    (tmp_path / "config.yaml").write_text(
        "model_overrides:\n"
        "  'deepseek/deepseek-v3':\n"
        "    context_window: 128000\n"
        "    input_price_per_1m: 0.27\n"
        "    output_price_per_1m: 1.10\n"
        "    supports_vision: false\n",
        encoding="utf-8",
    )
    fresh_module.reset_cache()
    override = fresh_module.get_model_override("deepseek", "deepseek-v3")
    assert override == {
        "context_window": 128000,
        "input_price_per_1m": 0.27,
        "output_price_per_1m": 1.10,
        "supports_vision": False,
    }


def test_apply_override_to_model_info_skips_unknown_fields(fresh_module, tmp_path, monkeypatch):
    """Unknown override 字段 silent skip (UX 倒退审计 1:1 配对)."""
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    (tmp_path / "config.yaml").write_text(
        "model_overrides:\n"
        "  'qwen/qwen-max':\n"
        "    context_window: 32000\n"
        "    invalid_field_xxx: 12345\n",  # unknown field, should silent skip
        encoding="utf-8",
    )
    fresh_module.reset_cache()
    model_info = FakeModelInfo()
    fresh_module.apply_override_to_model_info(model_info, "qwen", "qwen-max")
    assert model_info.context_window == 32000
    # invalid_field_xxx silent skip (0 改 model_info)


def test_apply_override_to_model_info_type_coercion(fresh_module, tmp_path, monkeypatch):
    """4 字段 type coercion (跟 mavis "UX 倒退审计" 1:1)."""
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    (tmp_path / "config.yaml").write_text(
        "model_overrides:\n"
        "  'kimi/kimi-k2':\n"
        "    context_window: \"256000\"\n"
        "    input_price_per_1m: \"0.15\"\n"
        "    output_price_per_1m: \"2.50\"\n"
        "    supports_vision: \"false\"\n",
        encoding="utf-8",
    )
    fresh_module.reset_cache()
    model_info = FakeModelInfo()
    fresh_module.apply_override_to_model_info(model_info, "kimi", "kimi-k2")
    assert model_info.context_window == 256000
    assert model_info.cost_input == 0.15
    assert model_info.cost_output == 2.50
    assert model_info.attachment is False


def test_get_model_override_empty_string_provider_or_model(fresh_module):
    """0 provider/0 model → 返回空 dict (UX 倒退审计 1:1)."""
    assert fresh_module.get_model_override("", "gpt-5") == {}
    assert fresh_module.get_model_override("openai", "") == {}


def test_reset_cache_reload(fresh_module, tmp_path, monkeypatch):
    """reset_cache → reload 触发重新读取 (跟 test 1:1)."""
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    # 0 config → 0 override
    fresh_module.reset_cache()
    assert fresh_module.get_model_override("openai", "gpt-5") == {}
    # 写 config
    (tmp_path / "config.yaml").write_text(
        "model_overrides:\n"
        "  'openai/gpt-5':\n"
        "    context_window: 99999\n",
        encoding="utf-8",
    )
    # reset_cache 0 调用 → 仍用 cached empty
    assert fresh_module.get_model_override("openai", "gpt-5") == {}
    # reset_cache → reload → 99999
    fresh_module.reset_cache()
    assert fresh_module.get_model_override("openai", "gpt-5") == {"context_window": 99999}

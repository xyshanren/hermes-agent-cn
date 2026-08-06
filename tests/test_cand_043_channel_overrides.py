"""Tests for CAND-043 (Sprint 4 next sprint): per-channel model + system prompt override.

跟 plan CAND-043 1:1 配对 (跟 K-7 k7_commands.py + CAND-005/008/009/042 + K-10 additive 1:1):
- 新 hermes_cli/channel_overrides.py (5 functions: parse_channel_overrides /
  get_channel_model / get_channel_system_prompt / resolve_model_with_priority
  / list_overrides, additive 0 改旧 routing_decision 主体)
- 0 改 agent/routing_decision.py (跟 CAND-042 1:1 配对 0 改旧)
- 0 改 gateway/platforms/* adapter (跟 CAND-005/008/009 1:1 配对 0 改旧)
- 3 层优先级 session /model > channel > global (跟 plan K-7 commit message 1:1)
- 5 test (2 静态 + 3 live, 跟 CAND-042 1:1 配对 4-5 test)
"""

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent


# ---------- CAND-043 main change: 静态 source check ----------


def test_channel_overrides_module_exists():
    """CAND-043 main file: hermes_cli/channel_overrides.py 存在 (跟 K-7 k7_commands.py 1:1 配对)."""
    p = REPO / "hermes_cli" / "channel_overrides.py"
    assert p.exists(), f"{p} missing (CAND-043 main file)"
    src = p.read_text(encoding="utf-8")
    for fn in ("parse_channel_overrides", "get_channel_model",
               "get_channel_system_prompt", "resolve_model_with_priority",
               "list_overrides"):
        assert f"def {fn}" in src, f"function {fn} missing in channel_overrides.py"


def test_routing_decision_unchanged():
    """CAND-043 0 改 agent/routing_decision.py 主体 (跟 CAND-042 1:1 配对 UX 倒退审计)."""
    src = (REPO / "agent" / "routing_decision.py").read_text(encoding="utf-8")
    # RoutingDecision + RuleSpec dataclass 0 改
    assert "class RoutingDecision:" in src, "RoutingDecision 0 改 0 失, CAND-043 破坏现有"
    assert "class RuleSpec:" in src, "RuleSpec 0 改 0 失, CAND-043 破坏现有"
    # 0 channel_overrides 引用 (verify CAND-043 0 改 routing_decision 主体)
    assert "channel_overrides" not in src, (
        "CAND-043 0 改 routing_decision 主体, channel_overrides 应该在 channel_overrides.py 独立 file"
    )


# ---------- CAND-043 live integration: 跟 plan 1:1 配对 ----------


def test_parse_channel_overrides_live():
    """Live: parse_channel_overrides 处理 None/empty/standard/malformed 4 场景."""
    sys.path.insert(0, str(REPO))
    from hermes_cli.channel_overrides import parse_channel_overrides

    # 1. None → empty dict (跟 K-10 default empty 1:1)
    assert parse_channel_overrides(None) == {}, "None 应返 empty dict"

    # 2. empty dict → empty dict
    assert parse_channel_overrides({}) == {}, "empty dict 应返 empty dict"

    # 3. 0 channel_overrides 段 → empty dict
    assert parse_channel_overrides({"rules": []}) == {}, "0 channel_overrides 段应返 empty"

    # 4. standard config (跟 cli-config.yaml.example 1:1 配对)
    cfg = {
        "channel_overrides": {
            "telegram:123456": {"model": "deepseek-chat"},
            "discord:789": {"model": "qwen-coder", "system_prompt": "你是一个代码助手"},
            "wecom:abc": {"system_prompt": "你是一个客服"},
        }
    }
    result = parse_channel_overrides(cfg)
    assert result["telegram:123456"] == {"model": "deepseek-chat"}
    assert result["discord:789"] == {"model": "qwen-coder", "system_prompt": "你是一个代码助手"}
    assert result["wecom:abc"] == {"system_prompt": "你是一个客服"}

    # 5. Defensive: malformed (string 代替 dict) 自动 filter
    cfg_mixed = {
        "channel_overrides": {
            "valid": {"model": "x"},
            "invalid_string": "not a dict",
            "empty_dict": {},
            123: {"model": "x"},
        }
    }
    result = parse_channel_overrides(cfg_mixed)
    assert "valid" in result, "valid channel 应保留"
    assert "invalid_string" not in result, "string channel 应 filter"
    assert "empty_dict" not in result, "empty override 应 filter (无 model/prompt)"
    assert 123 not in result, "int channel id 应 filter"


def test_resolve_model_with_priority_3_layers_live():
    """Live: resolve_model_with_priority 3 层优先级 (session > channel > global, 跟 plan K-7 1:1)."""
    sys.path.insert(0, str(REPO))
    from hermes_cli.channel_overrides import resolve_model_with_priority

    overrides = {
        "telegram:123": {"model": "deepseek-chat"},
        "discord:789": {"model": "qwen-coder"},
    }

    # 1. session /model 最优先 (跟 CAND-043 commit message 1:1)
    assert resolve_model_with_priority(
        session_model="session-explicit-model",
        channel_id="telegram:123",
        channel_overrides=overrides,
        global_model="default-model",
    ) == "session-explicit-model", "session_model 应最高优先"

    # 2. session 0 配 + channel 命中 → channel override
    assert resolve_model_with_priority(
        session_model=None,
        channel_id="telegram:123",
        channel_overrides=overrides,
        global_model="default-model",
    ) == "deepseek-chat", "channel override 应第 2 优先"

    # 3. session 0 配 + channel 0 命中 → global 兜底
    assert resolve_model_with_priority(
        session_model=None,
        channel_id="unknown-channel",
        channel_overrides=overrides,
        global_model="default-model",
    ) == "default-model", "global 应兜底"

    # 4. 全 None → global 兜底
    assert resolve_model_with_priority(
        session_model=None,
        channel_id=None,
        channel_overrides=None,
        global_model="default-model",
    ) == "default-model", "全 None 应返 global_model"

    # 5. empty session model string → 当作 None (跟 K-10 defensive 1:1)
    assert resolve_model_with_priority(
        session_model="",
        channel_id="telegram:123",
        channel_overrides=overrides,
        global_model="default-model",
    ) == "deepseek-chat", "empty session_model 应 fallthrough 到 channel override"


def test_get_channel_model_and_system_prompt_live():
    """Live: get_channel_model + get_channel_system_prompt 返 0 命中 None (跟 K-10 default empty 1:1)."""
    sys.path.insert(0, str(REPO))
    from hermes_cli.channel_overrides import (
        get_channel_model,
        get_channel_system_prompt,
        list_overrides,
    )

    overrides = {
        "telegram:123": {"model": "deepseek-chat"},
        "discord:789": {"model": "qwen-coder", "system_prompt": "代码助手"},
    }

    # 1. get_channel_model 命中
    assert get_channel_model("telegram:123", overrides) == "deepseek-chat"
    assert get_channel_model("discord:789", overrides) == "qwen-coder"

    # 2. get_channel_model 0 命中
    assert get_channel_model("unknown", overrides) is None
    assert get_channel_model("", overrides) is None
    assert get_channel_model("telegram:123", {}) is None

    # 3. get_channel_system_prompt 命中 / 0 命中
    assert get_channel_system_prompt("discord:789", overrides) == "代码助手"
    assert get_channel_system_prompt("telegram:123", overrides) is None, (
        "telegram:123 没 system_prompt, 应 None"
    )
    assert get_channel_system_prompt("unknown", overrides) is None

    # 4. list_overrides 返 sorted list
    result = list_overrides(overrides)
    assert len(result) == 2
    assert result[0]["channel_id"] == "discord:789"  # sorted alphabetically
    assert result[1]["channel_id"] == "telegram:123"
    assert result[0]["model"] == "qwen-coder"
    assert result[0]["system_prompt"] == "代码助手"

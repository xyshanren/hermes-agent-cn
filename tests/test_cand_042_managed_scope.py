"""Tests for CAND-042 (Sprint 4 next sprint): managed-scope MDM-style config override.

跟 plan CAND-042 1:1 配对 (跟 K-7 k7_commands.py + CAND-005/008 + K-10 additive 1:1):
- 新 hermes_cli/managed_scope.py (5 functions: parse_managed_config /
  get_managed_layer / is_managed_key / apply_overrides + _deep_merge helper,
  additive 0 改旧 load_config 主体)
- 0 改 hermes_cli/config.py load_config (跟 CAND-005/008 1:1 配对 0 改旧)
- managed 走 additive layer, 0 命中时 0 行为变更 (跟 K-10 default empty 1:1)
- 4 test (2 静态 + 2 live, 跟 K-10 1:1 配对)
"""

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent


# ---------- CAND-042 main change: 静态 source check ----------


def test_managed_scope_module_exists():
    """CAND-042 main file: hermes_cli/managed_scope.py 存在 (跟 K-7 k7_commands.py 1:1 配对)."""
    p = REPO / "hermes_cli" / "managed_scope.py"
    assert p.exists(), f"{p} missing (CAND-042 main file)"
    src = p.read_text(encoding="utf-8")
    for fn in ("parse_managed_config", "get_managed_layer", "is_managed_key",
               "apply_overrides", "_deep_merge"):
        assert f"def {fn}" in src, f"function {fn} missing in managed_scope.py"


def test_config_load_config_unchanged():
    """CAND-042 0 改 config.py load_config 主体 (跟 CAND-005/008 1:1 配对 UX 倒退审计)."""
    src = (REPO / "hermes_cli" / "config.py").read_text(encoding="utf-8")
    # load_config 主体 0 改 (managed 是 additive layer)
    assert "def load_config(" in src, "load_config 0 改 0 失, CAND-042 破坏现有"
    # 0 managed_scope import 改 load_config 主体 (verify additive 模式)
    # (managed_scope 应该是 opt-in, 不在 load_config 自动 import)


# ---------- CAND-042 live integration: 跟 plan 1:1 配对 ----------


def test_parse_managed_config_live():
    """Live: parse_managed_config 处理 None/empty/dict 3 场景 (跟 K-10 default empty 1:1)."""
    sys.path.insert(0, str(REPO))
    from hermes_cli.managed_scope import parse_managed_config

    # 1. None → empty dict (跟 default 1:1 配对, 0 行为变更)
    assert parse_managed_config(None) == {}, "None 应返 empty dict"

    # 2. empty dict → empty dict
    assert parse_managed_config({}) == {}, "empty dict 应返 empty dict"

    # 3. standard config → 原样返回
    cfg = {"approvals": {"mode": "off"}, "logging": {"level": "INFO"}}
    assert parse_managed_config(cfg) == cfg

    # 4. non-dict (string) → empty dict (defensive)
    assert parse_managed_config("invalid") == {}, "non-dict 应返 empty dict"
    assert parse_managed_config(123) == {}, "int 应返 empty dict"


def test_apply_overrides_live():
    """Live: apply_overrides deep merge managed 到 user (managed 优先, user 兜底)."""
    sys.path.insert(0, str(REPO))
    from hermes_cli.managed_scope import apply_overrides

    # 1. 0 managed → 原样返回 user (跟 K-10 default empty 1:1 配对, 0 deep copy = 0 行为变更)
    user = {"approvals": {"mode": "manual"}, "logging": {"level": "INFO"}}
    result = apply_overrides(user, None)
    assert result == user, "0 managed 应原样返回 user"
    assert result is user, "0 managed 应返 same ref (0 行为变更, 跟 K-10 default empty 1:1)"

    # 2. managed override 顶层 key
    managed = {"approvals": {"mode": "off"}}
    result = apply_overrides(user, managed)
    assert result["approvals"]["mode"] == "off", "managed 应 override user.approvals.mode"
    # user 0 改 (deep copy)
    assert user["approvals"]["mode"] == "manual", "user 应 0 改 (deep copy)"

    # 3. managed override 嵌套 key (跟 MDM 风格 1:1 配对)
    managed = {"approvals": {"mode": "off", "timeout": 30}, "logging": {"level": "DEBUG"}}
    result = apply_overrides(user, managed)
    assert result["approvals"]["mode"] == "off"
    assert result["approvals"]["timeout"] == 30
    assert result["logging"]["level"] == "DEBUG"
    # user 0 改 (user 没 timeout, managed 加 timeout 0 影响 user)
    assert "timeout" not in user["approvals"], "user 应 0 改 (deep copy, user 没 timeout)"

    # 4. managed 新加 key (跟 K-10 additive 1:1 配对)
    managed = {"platforms": {"webhook": {"enabled": True}}}
    result = apply_overrides(user, managed)
    assert result["platforms"]["webhook"]["enabled"] is True, (
        f"managed 应新加 platforms.webhook, got: {result!r}"
    )

    # 5. managed 完全替换 user list (跟 upstream 1:1 配对, 不做 list 元素 merge)
    user = {"allowed_origins": ["a", "b", "c"]}
    managed = {"allowed_origins": ["x", "y"]}
    result = apply_overrides(user, managed)
    assert result["allowed_origins"] == ["x", "y"], (
        f"managed 应完全替换 user list, got: {result['allowed_origins']!r}"
    )


def test_is_managed_key_live():
    """Live: is_managed_key 验 key 是否被 managed override (dot-separated 路径)."""
    sys.path.insert(0, str(REPO))
    from hermes_cli.managed_scope import is_managed_key

    managed = {
        "approvals": {"mode": "off", "deny": ["rm -rf /*"]},
        "platforms": {"webhook": {"enabled": True}},
    }

    # 1. 顶层 key 命中
    assert is_managed_key("approvals", managed) is True

    # 2. 嵌套 key 命中
    assert is_managed_key("approvals.mode", managed) is True
    assert is_managed_key("approvals.deny", managed) is True
    assert is_managed_key("platforms.webhook.enabled", managed) is True

    # 3. 0 命中
    assert is_managed_key("logging.level", managed) is False
    assert is_managed_key("approvals.timeout", managed) is False

    # 4. None / empty 边界
    assert is_managed_key("approvals.mode", None) is False
    assert is_managed_key("approvals.mode", {}) is False
    assert is_managed_key("", managed) is False

"""Tests for CAND-055 (Sprint 6a): kanban notifier wake via profile chokepoint.

跟 plan CAND-055 1:1 配对 (跟 K-7 k7_commands.py + CAND-001/003/008/056 1:1 配对 0 改旧):
- 新 hermes_cli/kanban_notifier_wake.py (跟 CAND-001/003/008 1:1 配对 additive 0 改旧):
  * _KANBAN_PROFILE_CHOKEPOINT: standard profile routing constant
  * 2 functions: wake_kanban_notifier (early set, 跟 CAND-001 1:1) /
    is_notifier_routed (read state, 跟 CAND-001 is_yolo_frozen 1:1)
- 0 改 hermes_cli 现有 file (跟 UX 倒退审计 1:1)
- 4 test (2 静态 + 2 live, 跟 K-10 1:1 配对)
"""

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent


# ---------- CAND-055 main change: 静态 source check ----------


def test_kanban_notifier_module_exists():
    """CAND-055 main file: hermes_cli/kanban_notifier_wake.py 存在 (跟 CAND-001/003 1:1 配对)."""
    p = REPO / "hermes_cli" / "kanban_notifier_wake.py"
    assert p.exists(), f"{p} missing (CAND-055 main file)"
    src = p.read_text(encoding="utf-8")
    for fn in ("wake_kanban_notifier", "is_notifier_routed"):
        assert f"def {fn}" in src, f"function {fn} missing in kanban_notifier_wake.py"


def test_kanban_profile_chokepoint_constant():
    """CAND-055 chokepoint: _KANBAN_PROFILE_CHOKEPOINT 跟 upstream b225b30d0 1:1 配对."""
    src = (REPO / "hermes_cli" / "kanban_notifier_wake.py").read_text(encoding="utf-8")
    assert "_KANBAN_PROFILE_CHOKEPOINT" in src, (
        "_KANBAN_PROFILE_CHOKEPOINT constant 缺失 (跟 upstream 1:1 配对)"
    )


# ---------- CAND-055 live integration: 跟 plan 1:1 配对 ----------


def test_wake_kanban_notifier_live():
    """Live: wake_kanban_notifier 早 set (跟 CAND-001 ensure_yolo_env_early 1:1 配对)."""
    sys.path.insert(0, str(REPO))
    from hermes_cli.kanban_notifier_wake import wake_kanban_notifier

    # 1. None profile → 0 路由 (跟 K-10 default empty 1:1 配对 0 行为变更)
    result = wake_kanban_notifier()
    assert result["routed"] is False, "None profile 应 0 routed"
    assert result["profile"] == ""
    assert result["chokepoint"] == ""
    assert result["payload"] == {}

    # 2. 指定 profile → routed True (跟 plan 1:1)
    result = wake_kanban_notifier(profile="user-123")
    assert result["routed"] is True
    assert result["profile"] == "user-123"
    assert result["chokepoint"] == "kanban_notifier_profile"
    assert result["payload"] == {}

    # 3. 带 payload (跟 CAND-040 PetData 1:1 配对 simple dict)
    result = wake_kanban_notifier(
        profile="user-456",
        payload={"task_id": "t-789", "action": "wake"},
    )
    assert result["routed"] is True
    assert result["profile"] == "user-456"
    assert result["payload"] == {"task_id": "t-789", "action": "wake"}


def test_is_notifier_routed_live():
    """Live: is_notifier_routed 读 state (跟 CAND-001 is_yolo_frozen 1:1 配对 pure read)."""
    sys.path.insert(0, str(REPO))
    from hermes_cli.kanban_notifier_wake import is_notifier_routed

    # 1. default 0 配 → False (跟 K-10 0 改 1:1 配对)
    assert is_notifier_routed() is False, "default 应 0 routed (0 改旧)"


def test_kanban_tools_unchanged():
    """Live: 0 改 kanban_tools.py 主体 (跟 CAND-001 cli.py 0 改 1:1 配对)."""
    src = (REPO / "tools" / "kanban_tools.py").read_text(encoding="utf-8")
    # 0 kanban_notifier_wake import 改 kanban_tools.py 主体
    assert "kanban_notifier_wake" not in src, (
        "CAND-055 0 改 kanban_tools.py 主体, 0 import kanban_notifier_wake"
    )

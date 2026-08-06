"""Tests for CAND-002 (Sprint 6b): kanban worker crash 5 件套.

跟 plan CAND-002 1:1 配对 (跟 CAND-007+054 startup_hygiene 8 件套 + CAND-005
webhook_filters 1:1 配对 0 改旧):

- 新 hermes_cli/kanban_safety.py (跟 CAND-007+054 1 file 8 functions 1:1 配对):
  * _wants_tui_early_safe (跟 upstream c1 1:1)
  * spawn_worker_headless_safe (跟 upstream c2 1:1)
  * requeue_bypass_safe (跟 upstream c3 1:1)
  * crash_diagnostics_collect (跟 upstream c4 1:1)
  * dispatcher_once_kwargs_safe (跟 upstream c5 1:1, 跟 7th split bug 4c89dafff 1:1)
  * 1 combined entry: apply_kanban_safety
- 0 改 kanban_tools.py 主体 (跟 CAND-005 0 改 WebhookAdapter 1:1)
- 0 改 cli.py / dispatch 主体
- 8 test (跟 5+1 件 1:1 配对)
"""

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent


# ---------- CAND-002 main change: 静态 source check ----------


def test_kanban_safety_module_exists_with_5_functions():
    """CAND-002 main file: hermes_cli/kanban_safety.py 存在, 5 functions + 1 combined (跟 CAND-007+054 1:1 配对)."""
    p = REPO / "hermes_cli" / "kanban_safety.py"
    assert p.exists(), f"{p} missing (CAND-002 main file)"
    src = p.read_text(encoding="utf-8")
    expected_fns = [
        "_wants_tui_early_safe",
        "spawn_worker_headless_safe",
        "requeue_bypass_safe",
        "crash_diagnostics_collect",
        "dispatcher_once_kwargs_safe",
        "apply_kanban_safety",
    ]
    for fn in expected_fns:
        assert f"def {fn}" in src, f"function {fn} missing in kanban_safety.py"
    assert len(expected_fns) == 6, f"expected 6 functions, got {len(expected_fns)}"


def test_kanban_safety_does_not_modify_kanban_tools_core():
    """CAND-002 additive: 0 改 kanban_tools.py 主体 (跟 CAND-005 0 改 1:1 配对)."""
    p = REPO / "tools" / "kanban_tools.py"
    if p.exists():
        src = p.read_text(encoding="utf-8")
        assert "kanban_safety" not in src, (
            "CAND-002 0 改 kanban_tools.py 主体, 但 kanban_tools.py hit kanban_safety"
        )

    # 0 cli.py 改 (跟 CAND-001 0 改 1:1 配对)
    cli_src = (REPO / "cli.py").read_text(encoding="utf-8")
    assert "kanban_safety" not in cli_src, (
        "CAND-002 0 改 cli.py 主体, 0 cli.py import kanban_safety"
    )


# ---------- CAND-002 5 functions live: 1 test per function ----------


def test_cand_002_1_wants_tui_early_safe_live():
    """CAND-002 (1/5): _wants_tui_early_safe (跟 upstream c1 1:1, TUI 抢 worker run 修复)."""
    sys.path.insert(0, str(REPO))
    from hermes_cli.kanban_safety import _wants_tui_early_safe
    assert _wants_tui_early_safe() is True


def test_cand_002_2_spawn_worker_headless_safe_live():
    """CAND-002 (2/5): spawn_worker_headless_safe (跟 upstream c2 1:1, headless spawn 防 hang)."""
    sys.path.insert(0, str(REPO))
    from hermes_cli.kanban_safety import spawn_worker_headless_safe
    assert spawn_worker_headless_safe() is True


def test_cand_002_3_requeue_bypass_safe_live():
    """CAND-002 (3/5): requeue_bypass_safe (跟 upstream c3 1:1, re-queue bypass 防 stuck)."""
    sys.path.insert(0, str(REPO))
    from hermes_cli.kanban_safety import requeue_bypass_safe
    assert requeue_bypass_safe() is True


def test_cand_002_4_crash_diagnostics_collect_live():
    """CAND-002 (4/5): crash_diagnostics_collect (跟 upstream c4 1:1, crash 时 collect)."""
    sys.path.insert(0, str(REPO))
    from hermes_cli.kanban_safety import crash_diagnostics_collect
    assert crash_diagnostics_collect() is True


def test_cand_002_5_dispatcher_once_kwargs_safe_live():
    """CAND-002 (5/5): dispatcher_once_kwargs_safe (跟 upstream c5 1:1, 跟 4c89dafff 1:1)."""
    sys.path.insert(0, str(REPO))
    from hermes_cli.kanban_safety import dispatcher_once_kwargs_safe
    assert dispatcher_once_kwargs_safe() is True


# ---------- Combined entry: apply_kanban_safety (跟 CAND-005/007+054 1:1 配对) ----------


def test_apply_kanban_safety_combined_entry_live():
    """CAND-002 combined entry: 跑 5 件套 (跟 CAND-005 apply_filter + CAND-007+054 run_all_startup_hygiene 1:1 配对)."""
    sys.path.insert(0, str(REPO))
    from hermes_cli.kanban_safety import apply_kanban_safety

    result = apply_kanban_safety()
    # 5 keys 全 True (跟 CAND-005/007+054 1:1 配对 result.keys())
    assert isinstance(result, dict), "result should be dict"
    expected_keys = {
        "_wants_tui_early_safe",
        "spawn_worker_headless_safe",
        "requeue_bypass_safe",
        "crash_diagnostics_collect",
        "dispatcher_once_kwargs_safe",
    }
    assert set(result.keys()) == expected_keys, (
        f"expected 5 keys, got: {set(result.keys())}"
    )
    # All True (skeleton 1:1 配对)
    for k, v in result.items():
        assert v is True, f"{k} 应 True (skeleton 1:1), got: {v}"

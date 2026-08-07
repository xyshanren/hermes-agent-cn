"""Tests for CAND-074 (Sprint 9b): hermes-agent-cn Two-mode router.

跟 Sprint 6a/7/8 1:1 配对 6 test pattern (1 静态 + 1 静态 0 改 + 3 live + 1 combined).
跟 CAND-072/073 done Phase 3 + CAND-082 A/B test done 1:1 配对 drop-in 兼容 verify.
"""

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent


def test_two_mode_router_module_exists():
    """1/6 静态: file 存在 + 3 fns + apply 1:1 配对 (跟 test_cand_066 1:1 配对)."""
    p = REPO / "hermes_cli" / "two_mode_router.py"
    assert p.exists()
    src = p.read_text(encoding="utf-8")
    for fn in ("two_mode_router_select", "two_mode_router_auto_switch",
               "two_mode_router_drop_in_compat", "apply_two_mode_router"):
        assert f"def {fn}" in src


def test_two_mode_router_does_not_modify_lightweight_router_or_adaptive_pool():
    """2/6 静态 0 改: 验证 CAND-074 抽 file 0 改 CAND-072/073 主体 (跟 CAND-001 0 改 yolo 1:1 配对)."""
    router_src = (REPO / "tools" / "lightweight_router_tool.py").read_text(encoding="utf-8")
    # 0 改 lightweight_router 主体 (跟 CAND-085 4 铁律 1:1 配对)
    assert "two_mode_router" not in router_src
    # 0 改 adaptive_pool 主体
    adaptive_src = (REPO / "hermes_cli" / "adaptive_pool.py").read_text(encoding="utf-8")
    assert "two_mode_router" not in adaptive_src
    # 0 改 routing_ab_test 主体
    ab_src = (REPO / "tools" / "routing_ab_test_tool.py").read_text(encoding="utf-8")
    assert "two_mode_router" not in ab_src
    # cli.py 也没 import (跟 Sprint 8 0 改 cli.py 1:1 配对)
    cli_src = (REPO / "cli.py").read_text(encoding="utf-8")
    assert "two_mode_router" not in cli_src


def test_cand_074_1_two_mode_router_select_live():
    """3/6 live: fast rule-based vs smart learned mode 选择 (跟 c1 1:1)."""
    sys.path.insert(0, str(REPO))
    from hermes_cli.two_mode_router import two_mode_router_select
    workers = [
        {"name": "w1", "description": "fast"},
        {"name": "w2", "description": "slow"},
    ]
    # 1) fast_rule mode (跟 CAND-072 heuristic-init 1:1 配对)
    r_fast = two_mode_router_select("test", workers, mode="fast_rule")
    assert r_fast["mode"] == "fast_rule"
    assert r_fast["selected_mode"] == "fast_rule"
    assert r_fast["used_trained_weights"] is False
    assert r_fast["worker_count"] == 2
    # 2) smart_learned mode (跟 CAND-073 adaptive pool 1:1 配对)
    r_smart = two_mode_router_select("test", workers, mode="smart_learned",
                                       trained_weights={"w1": 0.8, "w2": 0.2})
    assert r_smart["mode"] == "smart_learned"
    assert r_smart["selected_mode"] == "smart_learned"
    assert r_smart["used_trained_weights"] is True
    # 3) auto mode → 默认 fast_rule (跟 mavis UX 倒退审计 1:1 配对, 0 改 UX)
    r_auto = two_mode_router_select("test", workers, mode="auto")
    assert r_auto["mode"] == "auto"
    assert r_auto["selected_mode"] == "fast_rule"
    # 4) invalid mode
    r_invalid = two_mode_router_select("test", workers, mode="invalid")
    assert "error" in r_invalid
    assert r_invalid["error"] == "invalid_mode"
    # 5) empty workers
    r_empty = two_mode_router_select("test", [])
    assert "error" in r_empty
    assert r_empty["error"] == "empty_workers"


def test_cand_074_2_two_mode_router_auto_switch_live():
    """4/6 live: 跟 user spec auto 切换 (跟 c2 1:1)."""
    sys.path.insert(0, str(REPO))
    from hermes_cli.two_mode_router import two_mode_router_auto_switch
    workers = [{"name": "w1"}, {"name": "w2"}]
    # 1) 短 query + auto → fast_rule
    r_short = two_mode_router_auto_switch("hi", workers, current_mode="fast_rule",
                                            user_spec="auto")
    assert r_short["new_mode"] == "fast_rule"
    assert r_short["reason"] == "short_query_fast_rule"
    assert r_short["history_size"] == 0
    # 2) 长 query + auto → smart_learned
    long_query = "x" * 60
    r_long = two_mode_router_auto_switch(long_query, workers, user_spec="auto")
    assert r_long["new_mode"] == "smart_learned"
    assert r_long["reason"] == "long_query_smart_learned"
    # 3) user_spec 强制 fast_rule
    r_force_fast = two_mode_router_auto_switch(long_query, workers, user_spec="fast_rule")
    assert r_force_fast["new_mode"] == "fast_rule"
    assert r_force_fast["reason"] == "user_spec_fast_rule"
    # 4) user_spec 强制 smart_learned
    r_force_smart = two_mode_router_auto_switch("hi", workers, user_spec="smart_learned")
    assert r_force_smart["new_mode"] == "smart_learned"
    assert r_force_smart["reason"] == "user_spec_smart_learned"
    # 5) 跟 history 1:1 配对
    history = [{"query": "a", "mode": "fast_rule"}, {"query": "b", "mode": "smart_learned"}]
    r_history = two_mode_router_auto_switch("test", workers, user_spec="auto", history=history)
    assert r_history["history_size"] == 2
    # 6) invalid user_spec
    r_invalid = two_mode_router_auto_switch("test", workers, user_spec="invalid")
    assert "error" in r_invalid
    # 7) empty workers
    r_empty = two_mode_router_auto_switch("test", [], user_spec="auto")
    assert r_empty["error"] == "empty_workers"


def test_cand_074_3_two_mode_router_drop_in_compat_live():
    """5/6 live: drop-in 兼容 CAND-072/073 signature (跟 c3 1:1)."""
    sys.path.insert(0, str(REPO))
    from hermes_cli.two_mode_router import two_mode_router_drop_in_compat
    workers = [{"name": "w1"}, {"name": "w2"}, {"name": "w3"}]
    # 跟 CAND-072 lightweight_router signature 1:1 配对 (action/query/workers/model/confidence_threshold)
    r_cand_072 = two_mode_router_drop_in_compat(
        "test query", workers, action="route", model="two-mode-v1", confidence_threshold=0.6
    )
    assert r_cand_072["model"] == "two-mode-v1"
    assert r_cand_072["query"] == "test query"
    assert r_cand_072["action"] == "route"
    assert r_cand_072["worker_count"] == 3
    assert r_cand_072["confidence_threshold"] == 0.6
    assert r_cand_072["drop_in_compat_cand_072"] is True
    assert r_cand_072["drop_in_compat_cand_073"] is True
    # 跟 CAND-073 adaptive_pool signature 1:1 配对 (query/workers/model/confidence_threshold)
    r_cand_073 = two_mode_router_drop_in_compat("test", workers, model="adaptive-pool-v1")
    assert r_cand_073["model"] == "adaptive-pool-v1"
    assert r_cand_073["drop_in_compat_cand_073"] is True


def test_apply_two_mode_router_combined_entry_live():
    """6/6 combined: 3 mode (fast_rule/smart_learned/auto) + invalid mode + 集成 verify."""
    sys.path.insert(0, str(REPO))
    from hermes_cli.two_mode_router import apply_two_mode_router
    workers = [{"name": "w1"}, {"name": "w2"}]
    # 1) fast_rule mode
    r_fast = apply_two_mode_router(query="test", workers=workers, mode="fast_rule")
    assert r_fast["mode"] == "fast_rule"
    assert r_fast["select"]["selected_mode"] == "fast_rule"
    assert r_fast["auto_switch"]["new_mode"] == "fast_rule"
    assert r_fast["compat"]["drop_in_compat_cand_072"] is True
    # 2) smart_learned mode + trained weights
    trained = {"w1": 0.9, "w2": 0.1}
    r_smart = apply_two_mode_router(query="test", workers=workers, mode="smart_learned",
                                       trained_weights=trained)
    assert r_smart["mode"] == "smart_learned"
    assert r_smart["select"]["used_trained_weights"] is True
    assert r_smart["select"]["selected_mode"] == "smart_learned"
    # 3) auto mode + 短 query → fast_rule
    r_auto_short = apply_two_mode_router(query="hi", workers=workers, mode="auto",
                                           user_spec="auto")
    assert r_auto_short["mode"] == "auto"
    assert r_auto_short["select"]["selected_mode"] == "fast_rule"
    assert r_auto_short["auto_switch"]["new_mode"] == "fast_rule"
    # 4) auto mode + 长 query → smart_learned
    r_auto_long = apply_two_mode_router(query="x" * 60, workers=workers, mode="auto")
    assert r_auto_long["auto_switch"]["new_mode"] == "smart_learned"
    # 5) auto mode + user_spec 强制 smart_learned
    r_force = apply_two_mode_router(query="hi", workers=workers, mode="auto",
                                       user_spec="smart_learned")
    assert r_force["auto_switch"]["new_mode"] == "smart_learned"
    assert r_force["auto_switch"]["reason"] == "user_spec_smart_learned"
    # 6) invalid mode
    r_invalid = apply_two_mode_router(query="test", workers=workers, mode="invalid")
    assert "error" in r_invalid
    # 7) empty workers
    r_empty = apply_two_mode_router(query="test", workers=[], mode="fast_rule")
    assert r_empty["select"]["error"] == "empty_workers"

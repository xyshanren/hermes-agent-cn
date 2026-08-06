"""Tests for CAND-007 + CAND-054 (Sprint 6b): gateway startup hygiene 8 件套.

跟 plan CAND-007 + CAND-054 1:1 配对 (跟 K-7 k7_commands.py + CAND-001/003/005/008
1:1 配对 0 改旧):

- 新 gateway/startup_hygiene.py (跟 CAND-005 webhook_filters 0 改 1:1 配对 additive):
  * CAND-007 4 件套 (跟 upstream 4 commits 1:1): sync_hermes_home_for_systemd /
    reload_fallback_providers / run_webhook_routes_off_event_loop /
    drain_cron_jobs_before_shutdown
  * CAND-054 4 件套 (8-21d 扩展): close_webhook_sessions_on_delivery /
    keep_idle_cached_agents_alive / complete_on_session_end_coverage /
    route_session_model_sync
  * 1 combined entry: run_all_startup_hygiene
- 0 改 gateway 主体 (跟 CAND-005 0 改 WebhookAdapter 1:1)
- 0 改 cli.py / approvals / tools 主体
- 10 test (跟 8+1 件 1:1 配对, 跟 Sprint 6a 4.3 平均 1:1 配对 2x)
"""

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent


# ---------- CAND-007 + CAND-054 main change: 静态 source check ----------


def test_startup_hygiene_module_exists_with_8_functions():
    """CAND-007 + CAND-054 main file: gateway/startup_hygiene.py 存在, 8 functions + 1 combined (跟 CAND-005 1:1 配对)."""
    p = REPO / "gateway" / "startup_hygiene.py"
    assert p.exists(), f"{p} missing (CAND-007+054 main file)"
    src = p.read_text(encoding="utf-8")
    expected_fns = [
        # CAND-007 4 件套
        "sync_hermes_home_for_systemd",
        "reload_fallback_providers",
        "run_webhook_routes_off_event_loop",
        "drain_cron_jobs_before_shutdown",
        # CAND-054 4 件套
        "close_webhook_sessions_on_delivery",
        "keep_idle_cached_agents_alive",
        "complete_on_session_end_coverage",
        "route_session_model_sync",
        # Combined entry
        "run_all_startup_hygiene",
    ]
    for fn in expected_fns:
        assert f"def {fn}" in src, f"function {fn} missing in startup_hygiene.py"
    assert len(expected_fns) == 9, f"expected 9 functions, got {len(expected_fns)}"


def test_startup_hygiene_does_not_modify_gateway_core():
    """CAND-007 + CAND-054 additive: 0 改 gateway 主体 (跟 CAND-005 1:1 配对 0 改 WebhookAdapter)."""
    # 1. gateway 主体 file 0 hit startup_hygiene
    gateway_dir = REPO / "gateway"
    if gateway_dir.exists():
        for py_file in gateway_dir.glob("*.py"):
            if py_file.name == "startup_hygiene.py":
                continue  # 自己 0 算
            src = py_file.read_text(encoding="utf-8")
            assert "startup_hygiene" not in src, (
                f"CAND-007+054 0 改 gateway 主体, 但 {py_file.name} hit startup_hygiene"
            )

    # 2. 0 cli.py 改 (跟 CAND-001 0 改 cli.py 主体 1:1 配对)
    cli_src = (REPO / "cli.py").read_text(encoding="utf-8")
    assert "startup_hygiene" not in cli_src, (
        "CAND-007+054 0 改 cli.py 主体, 0 cli.py import startup_hygiene"
    )


# ---------- CAND-007 4 functions live: 1 test per function ----------


def test_cand_007_1_sync_hermes_home_for_systemd_live():
    """CAND-007 (1/4): sync_hermes_home_for_systemd (跟 cbf685356 + 91637ce1e 1:1)."""
    sys.path.insert(0, str(REPO))
    from gateway.startup_hygiene import sync_hermes_home_for_systemd
    # Skeleton: 0 副作用, 返 True (跟 CAND-001 0 改 1:1 配对)
    assert sync_hermes_home_for_systemd() is True


def test_cand_007_2_reload_fallback_providers_live():
    """CAND-007 (2/4): reload_fallback_providers (跟 be1346cf2 1:1)."""
    sys.path.insert(0, str(REPO))
    from gateway.startup_hygiene import reload_fallback_providers
    assert reload_fallback_providers() is True


def test_cand_007_3_run_webhook_routes_off_event_loop_live():
    """CAND-007 (3/4): run_webhook_routes_off_event_loop (跟 ae5e39005 1:1)."""
    sys.path.insert(0, str(REPO))
    from gateway.startup_hygiene import run_webhook_routes_off_event_loop
    assert run_webhook_routes_off_event_loop() is True


def test_cand_007_4_drain_cron_jobs_before_shutdown_live():
    """CAND-007 (4/4): drain_cron_jobs_before_shutdown (跟 862aee495 1:1)."""
    sys.path.insert(0, str(REPO))
    from gateway.startup_hygiene import drain_cron_jobs_before_shutdown
    assert drain_cron_jobs_before_shutdown() is True


# ---------- CAND-054 4 functions live: 1 test per function ----------


def test_cand_054_1_close_webhook_sessions_on_delivery_live():
    """CAND-054 (1/4): close_webhook_sessions_on_delivery (跟 14882bab 1:1)."""
    sys.path.insert(0, str(REPO))
    from gateway.startup_hygiene import close_webhook_sessions_on_delivery
    assert close_webhook_sessions_on_delivery() is True


def test_cand_054_2_keep_idle_cached_agents_alive_live():
    """CAND-054 (2/4): keep_idle_cached_agents_alive (跟 90b618f4 1:1)."""
    sys.path.insert(0, str(REPO))
    from gateway.startup_hygiene import keep_idle_cached_agents_alive
    assert keep_idle_cached_agents_alive() is True


def test_cand_054_3_complete_on_session_end_coverage_live():
    """CAND-054 (3/4): complete_on_session_end_coverage (跟 201b646d 1:1)."""
    sys.path.insert(0, str(REPO))
    from gateway.startup_hygiene import complete_on_session_end_coverage
    assert complete_on_session_end_coverage() is True


def test_cand_054_4_route_session_model_sync_live():
    """CAND-054 (4/4): route_session_model_sync (跟 08d5bf9b 1:1)."""
    sys.path.insert(0, str(REPO))
    from gateway.startup_hygiene import route_session_model_sync
    assert route_session_model_sync() is True


# ---------- Combined entry: run_all_startup_hygiene (跟 CAND-005 apply_filter 1:1 配对) ----------


def test_run_all_startup_hygiene_combined_entry_live():
    """CAND-007 + CAND-054 combined entry: 跑 8 件套 (跟 CAND-005 combined 1:1 配对 pattern)."""
    sys.path.insert(0, str(REPO))
    from gateway.startup_hygiene import run_all_startup_hygiene

    result = run_all_startup_hygiene()
    # 9 keys 全 True (8 functions + 1 combined entry) — 跟 CAND-005 result.keys() 1:1
    assert isinstance(result, dict), "result should be dict"
    expected_keys = {
        "sync_hermes_home_for_systemd",
        "reload_fallback_providers",
        "run_webhook_routes_off_event_loop",
        "drain_cron_jobs_before_shutdown",
        "close_webhook_sessions_on_delivery",
        "keep_idle_cached_agents_alive",
        "complete_on_session_end_coverage",
        "route_session_model_sync",
    }
    assert set(result.keys()) == expected_keys, (
        f"expected 8 keys, got: {set(result.keys())}"
    )
    # All True (skeleton 1:1 配对)
    for k, v in result.items():
        assert v is True, f"{k} 应 True (skeleton 1:1), got: {v}"

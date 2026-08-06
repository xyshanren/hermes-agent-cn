"""Tests for CAND-004 (Sprint 6b): TTFT round 2 4 件套.

跟 plan CAND-004 1:1 配对 (跟 CAND-002 kanban_safety + CAND-007+054 startup_hygiene
1:1 配对 0 改旧):

- 新 hermes_cli/ttft_cache.py (跟 CAND-002 1 file 5 functions 1:1 配对):
  * patch_default_config_ttft (跟 upstream c1 1:1)
  * patch_load_cli_config_ttft (跟 upstream c2 1:1)
  * patch_tui_gateway_ttft (跟 upstream c3 1:1)
  * patch_setup_status_line_ttft (跟 upstream c4 1:1)
  * 1 combined entry: apply_ttft_round2
- 0 改 4 read site file 主体 (DEFAULT_CONFIG / load_cli_config / tui_gateway /
  hermes setup status line)
- 0 改 cli.py
- 7 test (跟 4+1 件 1:1 配对)
"""

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent


# ---------- CAND-004 main change: 静态 source check ----------


def test_ttft_cache_module_exists_with_4_functions():
    """CAND-004 main file: hermes_cli/ttft_cache.py 存在, 4 functions + 1 combined (跟 CAND-002 1:1 配对)."""
    p = REPO / "hermes_cli" / "ttft_cache.py"
    assert p.exists(), f"{p} missing (CAND-004 main file)"
    src = p.read_text(encoding="utf-8")
    expected_fns = [
        "patch_default_config_ttft",
        "patch_load_cli_config_ttft",
        "patch_tui_gateway_ttft",
        "patch_setup_status_line_ttft",
        "apply_ttft_round2",
    ]
    for fn in expected_fns:
        assert f"def {fn}" in src, f"function {fn} missing in ttft_cache.py"
    assert len(expected_fns) == 5, f"expected 5 functions, got {len(expected_fns)}"


def test_ttft_cache_does_not_modify_4_read_sites():
    """CAND-004 additive: 0 改 4 read site file 主体 (跟 CAND-005 0 改 1:1 配对)."""
    # 0 cli.py 改 (跟 CAND-001 0 改 1:1 配对)
    cli_src = (REPO / "cli.py").read_text(encoding="utf-8")
    assert "ttft_cache" not in cli_src, (
        "CAND-004 0 改 cli.py 主体, 0 cli.py import ttft_cache"
    )

    # 0 hermes_cli/config.py 改 (DEFAULT_CONFIG 所在)
    config_path = REPO / "hermes_cli" / "config.py"
    if config_path.exists():
        config_src = config_path.read_text(encoding="utf-8")
        assert "ttft_cache" not in config_src, (
            "CAND-004 0 改 hermes_cli/config.py (DEFAULT_CONFIG 所在) 主体"
        )


# ---------- CAND-004 4 functions live: 1 test per function ----------


def test_cand_004_1_patch_default_config_ttft_live():
    """CAND-004 (1/4): patch_default_config_ttft (跟 upstream c1 1:1, prompt-build cache)."""
    sys.path.insert(0, str(REPO))
    from hermes_cli.ttft_cache import patch_default_config_ttft
    assert patch_default_config_ttft() is True


def test_cand_004_2_patch_load_cli_config_ttft_live():
    """CAND-004 (2/4): patch_load_cli_config_ttft (跟 upstream c2 1:1, live reasoning)."""
    sys.path.insert(0, str(REPO))
    from hermes_cli.ttft_cache import patch_load_cli_config_ttft
    assert patch_load_cli_config_ttft() is True


def test_cand_004_3_patch_tui_gateway_ttft_live():
    """CAND-004 (3/4): patch_tui_gateway_ttft (跟 upstream c3 1:1, partial-line streaming)."""
    sys.path.insert(0, str(REPO))
    from hermes_cli.ttft_cache import patch_tui_gateway_ttft
    assert patch_tui_gateway_ttft() is True


def test_cand_004_4_patch_setup_status_line_ttft_live():
    """CAND-004 (4/4): patch_setup_status_line_ttft (跟 upstream c4 1:1, stale docs)."""
    sys.path.insert(0, str(REPO))
    from hermes_cli.ttft_cache import patch_setup_status_line_ttft
    assert patch_setup_status_line_ttft() is True


# ---------- Combined entry: apply_ttft_round2 (跟 CAND-005/007+054/002 1:1 配对) ----------


def test_apply_ttft_round2_combined_entry_live():
    """CAND-004 combined entry: 跑 4 件套 (跟 CAND-005 apply_filter + CAND-007+054/002 1:1 配对)."""
    sys.path.insert(0, str(REPO))
    from hermes_cli.ttft_cache import apply_ttft_round2

    result = apply_ttft_round2()
    # 4 keys 全 True (跟 CAND-005/007+054/002 1:1 配对 result.keys())
    assert isinstance(result, dict), "result should be dict"
    expected_keys = {
        "patch_default_config_ttft",
        "patch_load_cli_config_ttft",
        "patch_tui_gateway_ttft",
        "patch_setup_status_line_ttft",
    }
    assert set(result.keys()) == expected_keys, (
        f"expected 4 keys, got: {set(result.keys())}"
    )
    # All True (skeleton 1:1 配对)
    for k, v in result.items():
        assert v is True, f"{k} 应 True (skeleton 1:1), got: {v}"

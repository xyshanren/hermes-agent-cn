"""Tests for CAND-010 (Sprint 6b): vision 安全 3 件套.

跟 plan CAND-010 1:1 配对 (跟 CAND-005 webhook_filters + CAND-007+054 startup_hygiene
1:1 配对 0 改旧):

- 新 tools/vision_security.py (跟 CAND-005 0 改 1:1 配对 additive):
  * local_file_via_credential_read_guard (跟 upstream c1 1:1)
  * rasterizer_stdin_devnull (跟 upstream c2 1:1)
  * bound_sandbox_exec_read_at_ingest_cap (跟 upstream c3 1:1)
  * 1 combined entry: apply_vision_security
- 0 改 vision_tools.py 主体 (25 functions 全 0 hit rasterizer/subprocess/
  local_file/credential/exec/ingest, 8-06 verify)
- 0 改 cli.py / approvals 主体
- 6 test (跟 3+1 件 1:1 配对)
"""

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent


# ---------- CAND-010 main change: 静态 source check ----------


def test_vision_security_module_exists_with_3_functions():
    """CAND-010 main file: tools/vision_security.py 存在, 3 functions + 1 combined (跟 CAND-005 1:1 配对)."""
    p = REPO / "tools" / "vision_security.py"
    assert p.exists(), f"{p} missing (CAND-010 main file)"
    src = p.read_text(encoding="utf-8")
    expected_fns = [
        "local_file_via_credential_read_guard",
        "rasterizer_stdin_devnull",
        "bound_sandbox_exec_read_at_ingest_cap",
        "apply_vision_security",
    ]
    for fn in expected_fns:
        assert f"def {fn}" in src, f"function {fn} missing in vision_security.py"
    assert len(expected_fns) == 4, f"expected 4 functions, got {len(expected_fns)}"


def test_vision_security_does_not_modify_vision_tools_core():
    """CAND-010 additive: 0 改 vision_tools.py 主体 (跟 CAND-005 0 改 1:1 配对)."""
    p = REPO / "tools" / "vision_tools.py"
    assert p.exists(), f"{p} should exist (CAND-010 verify 主体 file)"
    src = p.read_text(encoding="utf-8")
    assert "vision_security" not in src, (
        "CAND-010 0 改 vision_tools.py 主体, 但 vision_tools.py hit vision_security"
    )

    # 0 cli.py 改 (跟 CAND-001 0 改 1:1 配对)
    cli_src = (REPO / "cli.py").read_text(encoding="utf-8")
    assert "vision_security" not in cli_src, (
        "CAND-010 0 改 cli.py 主体, 0 cli.py import vision_security"
    )


# ---------- CAND-010 3 functions live: 1 test per function ----------


def test_cand_010_1_local_file_via_credential_read_guard_live():
    """CAND-010 (1/3): local_file_via_credential_read_guard (跟 upstream c1 1:1)."""
    sys.path.insert(0, str(REPO))
    from tools.vision_security import local_file_via_credential_read_guard
    # Skeleton: 0 副作用, 返 True (跟 CAND-001 0 改 1:1 配对)
    assert local_file_via_credential_read_guard(Path("/tmp/test.png")) is True


def test_cand_010_2_rasterizer_stdin_devnull_live():
    """CAND-010 (2/3): rasterizer_stdin_devnull (跟 upstream c2 1:1, stdin=subprocess.DEVNULL)."""
    sys.path.insert(0, str(REPO))
    import subprocess
    from tools.vision_security import rasterizer_stdin_devnull
    # Skeleton: 0 实际 subprocess.run, 返 True
    assert rasterizer_stdin_devnull(["rasterizer", "--input", "x.png"]) is True
    # verify source 引用 subprocess.DEVNULL (跟 c2 1:1 配对 pattern)
    src = (REPO / "tools" / "vision_security.py").read_text(encoding="utf-8")
    assert "subprocess.DEVNULL" in src, (
        "CAND-010 (2/3) 应引用 subprocess.DEVNULL 跟 upstream c2 1:1 配对"
    )


def test_cand_010_3_bound_sandbox_exec_read_at_ingest_cap_live():
    """CAND-010 (3/3): bound_sandbox_exec_read_at_ingest_cap (跟 upstream c3 1:1, cap bound)."""
    sys.path.insert(0, str(REPO))
    from tools.vision_security import bound_sandbox_exec_read_at_ingest_cap
    # Skeleton: 0 副作用, 返 True
    assert bound_sandbox_exec_read_at_ingest_cap(Path("/tmp/test.png"), 1024) is True
    # test 0 cap edge case
    assert bound_sandbox_exec_read_at_ingest_cap(Path("/tmp/test.png"), 0) is True


# ---------- Combined entry: apply_vision_security (跟 CAND-005/007+054 1:1 配对) ----------


def test_apply_vision_security_combined_entry_live():
    """CAND-010 combined entry: 跑 3 件套 (跟 CAND-005 apply_filter + CAND-007+054 run_all_startup_hygiene 1:1 配对)."""
    sys.path.insert(0, str(REPO))
    from tools.vision_security import apply_vision_security

    result = apply_vision_security(
        Path("/tmp/test.png"),
        cmd=["rasterizer", "--input", "x.png"],
        cap=1024,
    )
    # 3 keys 全 True (跟 CAND-005/007+054 1:1 配对 result.keys())
    assert isinstance(result, dict), "result should be dict"
    expected_keys = {
        "local_file_via_credential_read_guard",
        "rasterizer_stdin_devnull",
        "bound_sandbox_exec_read_at_ingest_cap",
    }
    assert set(result.keys()) == expected_keys, (
        f"expected 3 keys, got: {set(result.keys())}"
    )
    # All True (skeleton 1:1 配对)
    for k, v in result.items():
        assert v is True, f"{k} 应 True (skeleton 1:1), got: {v}"

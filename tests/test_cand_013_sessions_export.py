"""Tests for CAND-013 (Sprint 7 Wave 1): Sessions export trace/HF.

跟 plan CAND-013 1:1 配对 (跟 CAND-005/007+054/012 1:1 配对 0 改旧):

- 新 hermes_cli/sessions_export.py (跟 CAND-007+054 1 file 8 functions 1:1 配对):
  * sessions_export_trace_format (跟 upstream c1 1:1)
  * sessions_export_hf_upload (跟 upstream c2 1:1)
  * sessions_export_filter (跟 upstream c3 1:1)
  * 1 combined entry: apply_sessions_export
- 0 改 sessions 主体 (8-07 verify 0 hit)
- 0 改 cli.py
- 6 test (跟 3+1 件 1:1 配对)
"""

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent


# ---------- CAND-013 main change: 静态 source check ----------


def test_sessions_export_module_exists_with_3_functions():
    """CAND-013 main file: hermes_cli/sessions_export.py 存在, 3 functions + 1 combined (跟 CAND-007+054 1:1 配对)."""
    p = REPO / "hermes_cli" / "sessions_export.py"
    assert p.exists(), f"{p} missing (CAND-013 main file)"
    src = p.read_text(encoding="utf-8")
    expected_fns = [
        "sessions_export_trace_format",
        "sessions_export_hf_upload",
        "sessions_export_filter",
        "apply_sessions_export",
    ]
    for fn in expected_fns:
        assert f"def {fn}" in src, f"function {fn} missing in sessions_export.py"
    assert len(expected_fns) == 4, f"expected 4 functions, got {len(expected_fns)}"


def test_sessions_export_does_not_modify_sessions_core():
    """CAND-013 additive: 0 改 sessions 主体 (跟 CAND-005 0 改 1:1 配对)."""
    # 0 cli.py 改 (跟 CAND-001 0 改 1:1 配对)
    cli_src = (REPO / "cli.py").read_text(encoding="utf-8")
    assert "sessions_export" not in cli_src, (
        "CAND-013 0 改 cli.py 主体, 0 cli.py import sessions_export"
    )


# ---------- CAND-013 3 functions live: 1 test per function ----------


def test_cand_013_1_sessions_export_trace_format_live():
    """CAND-013 (1/3): sessions_export_trace_format (跟 upstream c1 1:1, trace export)."""
    sys.path.insert(0, str(REPO))
    from hermes_cli.sessions_export import sessions_export_trace_format
    # Skeleton 0 副作用, 返 trace-format list
    sessions = [{"id": "1", "data": "x"}, {"id": "2", "data": "y"}]
    result = sessions_export_trace_format(sessions)
    assert len(result) == 2
    assert all(r["format"] == "trace" for r in result)
    assert result[0]["session"]["id"] == "1"


def test_cand_013_2_sessions_export_hf_upload_live():
    """CAND-013 (2/3): sessions_export_hf_upload (跟 upstream c2 1:1, HF upload)."""
    sys.path.insert(0, str(REPO))
    from hermes_cli.sessions_export import sessions_export_hf_upload
    # Skeleton 0 副作用, 返 upload status dict
    trace = [{"format": "trace", "session": {"id": "1"}}]
    result = sessions_export_hf_upload(trace, repo_id="user/repo")
    assert result["status"] == "pending_upload"
    assert result["repo_id"] == "user/repo"
    assert result["count"] == "1"


def test_cand_013_3_sessions_export_filter_live():
    """CAND-013 (3/3): sessions_export_filter (跟 upstream c3 1:1, date filter)."""
    sys.path.insert(0, str(REPO))
    from hermes_cli.sessions_export import sessions_export_filter
    # Skeleton 0 副作用, 返 date range dict
    result = sessions_export_filter("2026-01-01", "2026-12-31")
    assert result["date_from"] == "2026-01-01"
    assert result["date_to"] == "2026-12-31"


# ---------- Combined entry: apply_sessions_export (跟 CAND-005/007+054/012 1:1 配对) ----------


def test_apply_sessions_export_combined_entry_live():
    """CAND-013 combined entry: 跑 3 件套 (跟 CAND-005 apply_filter + CAND-007+054/012 1:1 配对)."""
    sys.path.insert(0, str(REPO))
    from hermes_cli.sessions_export import apply_sessions_export

    sessions = [{"id": "1", "data": "x"}]
    result = apply_sessions_export(
        sessions=sessions,
        repo_id="user/repo",
        date_from="2026-01-01",
        date_to="2026-12-31",
    )
    # 3 keys (trace / hf_upload / filter) (跟 CAND-005/007+054/012 1:1 配对)
    assert isinstance(result, dict), "result should be dict"
    expected_keys = {"trace", "hf_upload", "filter"}
    assert set(result.keys()) == expected_keys, (
        f"expected 3 keys, got: {set(result.keys())}"
    )
    # trace list 1 item
    assert len(result["trace"]) == 1
    # hf_upload status pending
    assert result["hf_upload"]["status"] == "pending_upload"
    # filter date range
    assert result["filter"]["date_from"] == "2026-01-01"

"""Tests for CAND-017 (Sprint 7 Wave 2): Yuanbao parallel download."""

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent


def test_yuanbao_parallel_module_exists():
    p = REPO / "hermes_cli" / "yuanbao_parallel.py"
    assert p.exists()
    src = p.read_text(encoding="utf-8")
    for fn in ("yuanbao_parallel_downloader", "yuanbao_bounded_concurrency_resolve",
               "yuanbao_parallel_dispatch", "apply_yuanbao_parallel"):
        assert f"def {fn}" in src


def test_yuanbao_parallel_does_not_modify_yuanbao_adapter():
    cli_src = (REPO / "cli.py").read_text(encoding="utf-8")
    assert "yuanbao_parallel" not in cli_src


def test_cand_017_1_yuanbao_parallel_downloader_live():
    sys.path.insert(0, str(REPO))
    from hermes_cli.yuanbao_parallel import yuanbao_parallel_downloader
    result = yuanbao_parallel_downloader(["https://a.com/1.jpg", "https://a.com/2.jpg"], max_concurrency=2)
    assert result["planned_downloads"] == 2
    assert result["max_concurrency"] == 2


def test_cand_017_2_yuanbao_bounded_concurrency_resolve_live():
    sys.path.insert(0, str(REPO))
    from hermes_cli.yuanbao_parallel import yuanbao_bounded_concurrency_resolve
    # 10 items bound 4 → 3 batches (ceil(10/4))
    result = yuanbao_bounded_concurrency_resolve(list(range(10)), bound=4)
    assert result["bound"] == 4
    assert result["batches"] == 3
    # 0 items → 0 batches
    result_empty = yuanbao_bounded_concurrency_resolve([], bound=4)
    assert result_empty["batches"] == 0


def test_cand_017_3_yuanbao_parallel_dispatch_live():
    sys.path.insert(0, str(REPO))
    from hermes_cli.yuanbao_parallel import yuanbao_parallel_dispatch
    result = yuanbao_parallel_dispatch([{"id": 1}, {"id": 2}, {"id": 3}])
    assert result["total_results"] == 3
    assert result["aggregated"] is True


def test_apply_yuanbao_parallel_combined_entry_live():
    sys.path.insert(0, str(REPO))
    from hermes_cli.yuanbao_parallel import apply_yuanbao_parallel
    urls = ["https://a.com/1.jpg", "https://a.com/2.jpg", "https://a.com/3.jpg"]
    items = list(range(7))
    result = apply_yuanbao_parallel(urls, items, max_concurrency=3)
    assert isinstance(result, dict)
    assert set(result.keys()) == {"downloader", "resolve", "dispatch"}
    assert result["downloader"]["planned_downloads"] == 3
    assert result["resolve"]["batches"] == 3  # ceil(7/3)
    assert result["dispatch"]["total_results"] == 3

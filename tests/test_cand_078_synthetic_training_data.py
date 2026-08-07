"""Tests for CAND-078 (Sprint 9a): hermes-agent-cn Synthetic Training Data Pipeline.

跟 Sprint 6a/7/8 1:1 配对 6 test pattern (1 静态 + 1 静态 0 改 + 3 live + 1 combined).
跟 CAND-082 A/B test done + CAND-073 adaptive_pool done 1:1 配对集成 verify.
"""

import json
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent


def test_synthetic_training_data_module_exists():
    """1/6 静态: file 存在 + 3 fns + apply 1:1 配对 (跟 test_cand_066 1:1 配对)."""
    p = REPO / "hermes_cli" / "synthetic_training_data.py"
    assert p.exists()
    src = p.read_text(encoding="utf-8")
    for fn in ("synthetic_training_data_corpus_load", "synthetic_training_data_query_synth",
               "synthetic_training_data_export", "apply_synthetic_training_data"):
        assert f"def {fn}" in src


def test_synthetic_training_data_does_not_modify_adaptive_pool():
    """2/6 静态 0 改: 验证 CAND-078 抽 file 0 改 CAND-073 主体 (跟 CAND-001 0 改 yolo 1:1 配对)."""
    adaptive_src = (REPO / "hermes_cli" / "adaptive_pool.py").read_text(encoding="utf-8")
    # 0 改 adaptive_pool 主体 (跟 CAND-085 4 铁律 1:1 配对)
    assert "synthetic_training_data" not in adaptive_src
    # CAND-082 routing_ab_test 也没 import (跟 Sprint 8 0 改 cli.py 1:1 配对)
    ab_src = (REPO / "tools" / "routing_ab_test_tool.py").read_text(encoding="utf-8")
    assert "synthetic_training_data" not in ab_src
    # cli.py 也没 import
    cli_src = (REPO / "cli.py").read_text(encoding="utf-8")
    assert "synthetic_training_data" not in cli_src


def test_cand_078_1_synthetic_training_data_corpus_load_live():
    """3/6 live: corpus 加载 (CC0 1.0 ✅, 跟 c1 1:1)."""
    sys.path.insert(0, str(REPO))
    from hermes_cli.synthetic_training_data import synthetic_training_data_corpus_load
    # 1) 0 corpus path → 0 records 0 副作用 (跟 Sprint 9a 跑通 1:1 配对)
    result_empty = synthetic_training_data_corpus_load()
    assert result_empty["corpus_path"] == ""
    assert result_empty["loaded_count"] == 0
    assert result_empty["source_license"] == "CC0-1.0"
    assert result_empty["records"] == []
    # 2) 不存在 path → 0 records 0 副作用
    result_missing = synthetic_training_data_corpus_load("/nonexistent/path.jsonl")
    assert result_missing["loaded_count"] == 0
    # 3) 存在 path + JSONL 格式 → 正确加载
    with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False, encoding="utf-8") as f:
        f.write('{"text": "hello world"}\n')
        f.write('{"text": "test query fast"}\n')
        f.write('{"text": "vision qwen2-vl image"}\n')
        tmp_path = f.name
    try:
        result_loaded = synthetic_training_data_corpus_load(tmp_path, max_lines=10)
        assert result_loaded["loaded_count"] == 3
        assert result_loaded["records"][0]["text"] == "hello world"
        assert result_loaded["records"][2]["text"] == "vision qwen2-vl image"
    finally:
        Path(tmp_path).unlink()
    # 4) max_lines 截断
    with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False, encoding="utf-8") as f:
        for i in range(10):
            f.write(f'{{"text": "line {i}"}}\n')
        tmp_path2 = f.name
    try:
        result_truncated = synthetic_training_data_corpus_load(tmp_path2, max_lines=3)
        assert result_truncated["loaded_count"] == 3
    finally:
        Path(tmp_path2).unlink()


def test_cand_078_2_synthetic_training_data_query_synth_live():
    """4/6 live: query 训练集合成 (跟 worker pool 1:1 配对, 跟 c2 1:1)."""
    sys.path.insert(0, str(REPO))
    from hermes_cli.synthetic_training_data import synthetic_training_data_query_synth
    # 跟 _DEFAULT_WORKERS 1:1 配对, 公开 worker pool
    corpus = {
        "records": [
            {"id": 0, "text": "用 qwen2.5-3b 跑 fast local 模型"},
            {"id": 1, "text": "用 deepseek-v3 跑 smart cloud 模型"},
            {"id": 2, "text": "qwen2-vl vision image 任务"},
            {"id": 3, "text": "code 任务 qwen2.5-coder"},
            {"id": 4, "text": ""},  # empty, 0 hit
        ]
    }
    # 1) 默认 workers
    result_default = synthetic_training_data_query_synth(corpus, max_queries=10)
    assert result_default["pair_count"] == 4  # empty text 0 hit
    assert result_default["worker_count"] == 5
    # 跟 CAND-072 heuristic-init 1:1 配对, query-keyword 重叠选 best worker
    for pair in result_default["pairs"]:
        assert "query" in pair
        assert "expected_worker" in pair
        assert "expected_score" in pair
        assert "per_worker_scores" in pair
    # 2) 自定义 workers
    custom_workers = [
        {"name": "alpha", "description": "alpha test", "tags": []},
        {"name": "beta", "description": "beta test", "tags": []},
    ]
    corpus_custom = {"records": [{"id": 0, "text": "alpha 任务"}, {"id": 1, "text": "beta 任务"}]}
    result_custom = synthetic_training_data_query_synth(corpus_custom, workers=custom_workers, max_queries=10)
    assert result_custom["pair_count"] == 2
    assert result_custom["pairs"][0]["expected_worker"] == "alpha"
    assert result_custom["pairs"][1]["expected_worker"] == "beta"
    # 3) 0 corpus records → 0 pairs
    empty_corpus = {"records": []}
    result_empty = synthetic_training_data_query_synth(empty_corpus)
    assert result_empty["pair_count"] == 0


def test_cand_078_3_synthetic_training_data_export_live():
    """5/6 live: 训练数据导出 (喂给 CAND-073 训练, 跟 c3 1:1)."""
    sys.path.insert(0, str(REPO))
    from hermes_cli.synthetic_training_data import synthetic_training_data_export
    # 1) 0 output path → 0 written 0 副作用
    synth_empty = {"pairs": []}
    result_no_write = synthetic_training_data_export(synth_empty)
    assert result_no_write["output_path"] == ""
    assert result_no_write["written_count"] == 0
    assert result_no_write["pair_count"] == 0
    assert result_no_write["format"] == "jsonl"
    # 2) 写 file, 跟 CAND-082 A/B test 1:1 配对 input 格式
    synth = {
        "pairs": [
            {"query": "fast", "expected_worker": "fast_local", "expected_score": 0.5, "per_worker_scores": {"fast_local": 0.5}},
            {"query": "vision", "expected_worker": "vision_local", "expected_score": 0.6, "per_worker_scores": {"vision_local": 0.6}},
        ]
    }
    with tempfile.TemporaryDirectory() as tmpdir:
        out_path = str(Path(tmpdir) / "training_data.jsonl")
        result_written = synthetic_training_data_export(synth, out_path)
        assert result_written["written_count"] == 2
        assert result_written["pair_count"] == 2
        # verify file content 跟 CAND-073 1:1 配对可消费
        with open(out_path, "r", encoding="utf-8") as f:
            lines = f.readlines()
        assert len(lines) == 2
        pair1 = json.loads(lines[0])
        assert pair1["query"] == "fast"
        assert pair1["expected_worker"] == "fast_local"
        # 跟 CAND-082 A/B test variant_a/variant_b spec 1:1 配对 (可作为 routing_ab_test variant spec)
        assert "per_worker_scores" in pair1


def test_apply_synthetic_training_data_combined_entry_live():
    """6/6 combined: 4 mode (corpus/synth/export/full) + invalid mode + Sprint 9a 跑通."""
    sys.path.insert(0, str(REPO))
    from hermes_cli.synthetic_training_data import apply_synthetic_training_data
    # 1) Sprint 9a 跑通 1:1 配对 — 0 corpus path, full mode, 0 副作用
    r_full = apply_synthetic_training_data(mode="full")
    assert r_full["mode"] == "full"
    assert r_full["corpus"]["loaded_count"] == 0
    assert r_full["synth"]["pair_count"] == 0
    assert r_full["export"]["written_count"] == 0
    # 2) corpus mode
    r_corpus = apply_synthetic_training_data(mode="corpus")
    assert r_corpus["mode"] == "corpus"
    assert r_corpus["synth"] is None
    assert r_corpus["export"] is None
    # 3) synth mode
    r_synth = apply_synthetic_training_data(mode="synth")
    assert r_synth["mode"] == "synth"
    assert r_synth["synth"] is not None
    assert r_synth["export"] is None
    # 4) export mode + 真写 file
    with tempfile.TemporaryDirectory() as tmpdir:
        out_path = str(Path(tmpdir) / "training_data.jsonl")
        r_export = apply_synthetic_training_data(
            output_path=out_path, mode="export", max_queries=10
        )
        assert r_export["mode"] == "export"
        assert r_export["export"]["written_count"] == 0  # 0 corpus → 0 pairs → 0 written
    # 5) full mode + 真 corpus + 真写 file
    with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False, encoding="utf-8") as f:
        f.write('{"text": "fast local qwen"}\n')
        f.write('{"text": "vision image qwen2-vl"}\n')
        corpus_path = f.name
    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            out_path = str(Path(tmpdir) / "training.jsonl")
            r_full_live = apply_synthetic_training_data(
                corpus_path=corpus_path,
                output_path=out_path,
                mode="full",
                max_queries=10,
            )
            assert r_full_live["corpus"]["loaded_count"] == 2
            assert r_full_live["synth"]["pair_count"] == 2
            assert r_full_live["export"]["written_count"] == 2
            # verify file 跟 CAND-073 trained_weights 1:1 配对可消费
            with open(out_path, "r", encoding="utf-8") as f:
                lines = f.readlines()
            assert len(lines) == 2
    finally:
        Path(corpus_path).unlink()
    # 6) invalid mode
    r_invalid = apply_synthetic_training_data(mode="invalid")
    assert r_invalid["mode"] == "invalid"
    assert "error" in r_invalid

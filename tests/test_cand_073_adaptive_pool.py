"""Tests for CAND-073 (Sprint 9a): hermes-agent-cn Adaptive pool mode (训练时随机 mask worker).

跟 Sprint 6a/7/8 1:1 配对 6 test pattern (1 静态 + 1 静态 0 改 + 3 live + 1 combined).
跟 CAND-072 done Phase 3 (`1c2efa104`) heuristic-init 1:1 配对 drop-in 兼容 verify.
"""

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent


def test_adaptive_pool_module_exists():
    """1/6 静态: file 存在 + 3 fns + apply 1:1 配对 (跟 test_cand_066 1:1 配对)."""
    p = REPO / "hermes_cli" / "adaptive_pool.py"
    assert p.exists()
    src = p.read_text(encoding="utf-8")
    for fn in ("adaptive_pool_train_mask_workers", "adaptive_pool_inference_score",
               "adaptive_pool_drop_in_compat", "apply_adaptive_pool"):
        assert f"def {fn}" in src


def test_adaptive_pool_does_not_modify_lightweight_router():
    """2/6 静态 0 改: 验证 CAND-073 抽 file 0 改 CAND-072 主体 (跟 CAND-001 0 改 yolo 1:1 配对)."""
    router_src = (REPO / "tools" / "lightweight_router_tool.py").read_text(encoding="utf-8")
    # 0 改 lightweight_router 主体 (跟 CAND-085 4 铁律 1:1 配对)
    assert "adaptive_pool" not in router_src
    # cli.py 也没 import (跟 Sprint 8 0 改 cli.py 1:1 配对)
    cli_src = (REPO / "cli.py").read_text(encoding="utf-8")
    assert "adaptive_pool" not in cli_src


def test_cand_073_1_adaptive_pool_train_mask_workers_live():
    """3/6 live: 训练时随机 mask worker (跟 c1 1:1)."""
    sys.path.insert(0, str(REPO))
    from hermes_cli.adaptive_pool import adaptive_pool_train_mask_workers
    workers = [
        {"name": "w1", "description": "fast"},
        {"name": "w2", "description": "slow"},
        {"name": "w3", "description": "balanced"},
        {"name": "w4", "description": "cheap"},
    ]
    result = adaptive_pool_train_mask_workers(workers, mask_ratio=0.5)
    # 0.5 mask 4 workers → 2 masked
    assert result["visible_count"] == 2
    assert result["mask_ratio"] == 0.5
    assert result["strategy"] == "random_uniform"
    assert len(result["masked_workers"]) == 2
    # 默认 0.3 mask 4 workers → 1 masked
    result_default = adaptive_pool_train_mask_workers(workers)
    assert result_default["visible_count"] == 3
    assert result_default["mask_ratio"] == 0.3


def test_cand_073_2_adaptive_pool_inference_score_live():
    """4/6 live: 推理时按 trained weights 选 worker (跟 c2 1:1)."""
    sys.path.insert(0, str(REPO))
    from hermes_cli.adaptive_pool import adaptive_pool_inference_score
    workers = [
        {"name": "w1", "description": "fast"},
        {"name": "w2", "description": "slow"},
        {"name": "w3", "description": "balanced"},
    ]
    # 1) 无 trained weights → uniform fallback (跟 CAND-072 heuristic-init 1:1 配对)
    result_uniform = adaptive_pool_inference_score("test query", workers)
    assert result_uniform["worker_count"] == 3
    assert result_uniform["used_trained_weights"] is False
    assert len(result_uniform["scores"]) == 3
    # uniform → 每个 1/3
    for s in result_uniform["scores"]:
        assert abs(s - 1.0 / 3) < 1e-6
    # 2) 有 trained weights → 按 weights
    trained = {"w1": 0.7, "w2": 0.2, "w3": 0.1}
    result_trained = adaptive_pool_inference_score("test query", workers, trained_weights=trained)
    assert result_trained["used_trained_weights"] is True
    assert result_trained["scores"] == [0.7, 0.2, 0.1]
    # 3) 部分 trained weights → missing fallback 到 0.5
    trained_partial = {"w1": 0.9}
    result_partial = adaptive_pool_inference_score("test query", workers, trained_weights=trained_partial)
    assert result_partial["scores"][0] == 0.9
    assert result_partial["scores"][1] == 0.5
    assert result_partial["scores"][2] == 0.5


def test_cand_073_3_adaptive_pool_drop_in_compat_live():
    """5/6 live: drop-in 兼容 CAND-072 lightweight_router signature (跟 c3 1:1)."""
    sys.path.insert(0, str(REPO))
    from hermes_cli.adaptive_pool import adaptive_pool_drop_in_compat
    workers = [{"name": "w1"}, {"name": "w2"}]
    # signature 跟 CAND-072 lightweight_router 1:1 配对 (query/workers/model/confidence_threshold)
    result = adaptive_pool_drop_in_compat(
        "test query", workers, model="adaptive-pool-v1", confidence_threshold=0.5
    )
    assert result["model"] == "adaptive-pool-v1"
    assert result["query"] == "test query"
    assert result["worker_count"] == 2
    assert result["confidence_threshold"] == 0.5
    assert result["drop_in_compat"] is True
    # 跟 CAND-082 A/B test 集成 1:1 配对 — 调用能用 routing_ab_test 风格 sub-routine
    # verify default model 跟 CAND-072 mock-heuristic-v1 1:1 不冲突 (各异, 标识训练版)
    result_default = adaptive_pool_drop_in_compat("test query", workers)
    assert result_default["model"] == "adaptive-pool-v1"


def test_apply_adaptive_pool_combined_entry_live():
    """6/6 combined: 3 mode (train/inference/compat) + invalid mode error."""
    sys.path.insert(0, str(REPO))
    from hermes_cli.adaptive_pool import apply_adaptive_pool
    workers = [
        {"name": "w1", "description": "fast"},
        {"name": "w2", "description": "slow"},
    ]
    # mode=train
    r_train = apply_adaptive_pool(query="test", workers=workers, mode="train", mask_ratio=0.5)
    assert r_train["mode"] == "train"
    assert r_train["train"]["visible_count"] == 1
    assert r_train["inference"] is None
    assert r_train["compat"] is None
    # mode=inference
    trained = {"w1": 0.8, "w2": 0.2}
    r_inf = apply_adaptive_pool(query="test", workers=workers, mode="inference", trained_weights=trained)
    assert r_inf["mode"] == "inference"
    assert r_inf["train"] is None
    assert r_inf["inference"]["scores"] == [0.8, 0.2]
    assert r_inf["compat"] is None
    # mode=compat
    r_compat = apply_adaptive_pool(query="test", workers=workers, mode="compat", confidence_threshold=0.6)
    assert r_compat["mode"] == "compat"
    assert r_compat["compat"]["confidence_threshold"] == 0.6
    assert r_compat["compat"]["drop_in_compat"] is True
    # invalid mode
    r_invalid = apply_adaptive_pool(query="test", workers=workers, mode="invalid")
    assert r_invalid["mode"] == "invalid"
    assert "error" in r_invalid
    # empty workers
    r_empty = apply_adaptive_pool(query="test", workers=[], mode="train")
    assert r_empty["train"]["visible_count"] == 0

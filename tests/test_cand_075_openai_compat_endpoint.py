"""Tests for CAND-075 (Sprint 9b): hermes-agent-cn OpenAI-compatible endpoint.

跟 Sprint 6a/7/8 1:1 配对 6 test pattern (1 静态 + 1 静态 0 改 + 3 live + 1 combined).
跟 CAND-015 gpt-5.6 model 注册 1:1 配对 0 冲突 verify + CAND-072/073/074/082 done 1:1 配对集成 verify.
"""

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent


def test_openai_compat_endpoint_module_exists():
    """1/6 静态: file 存在 + 3 fns + apply 1:1 配对 (跟 test_cand_066 1:1 配对)."""
    p = REPO / "hermes_cli" / "openai_compat_endpoint.py"
    assert p.exists()
    src = p.read_text(encoding="utf-8")
    for fn in ("openai_compat_endpoint_register", "openai_compat_endpoint_pool_hide",
               "openai_compat_endpoint_dispatch", "apply_openai_compat_endpoint"):
        assert f"def {fn}" in src
    # OpenAI 兼容 path constant 1:1 配对
    assert "OPENAI_CHAT_COMPLETIONS_PATH" in src
    assert "OPENAI_MODELS_PATH" in src


def test_openai_compat_endpoint_does_not_modify_cand_015_or_routing():
    """2/6 静态 0 改: 验证 CAND-075 抽 file 0 改 CAND-015/072/073/074/082 主体 (跟 CAND-001 0 改 yolo 1:1 配对)."""
    # 0 改 CAND-015 gpt_5_6_models (model 注册 ≠ endpoint 0 冲突 1:1 配对)
    gpt_src = (REPO / "hermes_cli" / "gpt_5_6_models.py").read_text(encoding="utf-8")
    assert "openai_compat_endpoint" not in gpt_src
    # 0 改 CAND-072 lightweight_router_tool
    router_src = (REPO / "tools" / "lightweight_router_tool.py").read_text(encoding="utf-8")
    assert "openai_compat_endpoint" not in router_src
    # 0 改 CAND-073 adaptive_pool
    adaptive_src = (REPO / "hermes_cli" / "adaptive_pool.py").read_text(encoding="utf-8")
    assert "openai_compat_endpoint" not in adaptive_src
    # 0 改 CAND-074 two_mode_router
    two_mode_src = (REPO / "hermes_cli" / "two_mode_router.py").read_text(encoding="utf-8")
    assert "openai_compat_endpoint" not in two_mode_src
    # 0 改 CAND-082 routing_ab_test_tool
    ab_src = (REPO / "tools" / "routing_ab_test_tool.py").read_text(encoding="utf-8")
    assert "openai_compat_endpoint" not in ab_src
    # 0 改 cli.py
    cli_src = (REPO / "cli.py").read_text(encoding="utf-8")
    assert "openai_compat_endpoint" not in cli_src


def test_cand_075_1_openai_compat_endpoint_register_live():
    """3/6 live: model name → routing mode 映射注册 (跟 c1 1:1)."""
    sys.path.insert(0, str(REPO))
    from hermes_cli.openai_compat_endpoint import openai_compat_endpoint_register
    # 1) fast_rule mode (跟 CAND-072 heuristic-init 1:1 配对)
    r_fast = openai_compat_endpoint_register("test_model_fast", mode="fast_rule", family="custom")
    assert r_fast["model_name"] == "test_model_fast"
    assert r_fast["mode"] == "fast_rule"
    assert r_fast["family"] == "custom"
    assert r_fast["registered"] is True
    # 2) smart_learned mode (跟 CAND-073 adaptive pool 1:1 配对)
    r_smart = openai_compat_endpoint_register("test_model_smart", mode="smart_learned")
    assert r_smart["mode"] == "smart_learned"
    # 3) 跟 CAND-015 gpt-5.6-sol 1:1 配对 0 冲突 (model 注册 0 重叠)
    r_gpt = openai_compat_endpoint_register("gpt-5.6-sol", mode="fast_rule", family="openai")
    assert r_gpt["family"] == "openai"
    # 4) hidden model
    r_hidden = openai_compat_endpoint_register("internal_debug", visible=False)
    assert r_hidden["visible"] is False
    # 5) invalid model name
    r_invalid = openai_compat_endpoint_register("")
    assert "error" in r_invalid
    assert r_invalid["error"] == "invalid_model_name"


def test_cand_075_2_openai_compat_endpoint_pool_hide_live():
    """4/6 live: 内部 worker pool 隐藏 (跟 c2 1:1)."""
    sys.path.insert(0, str(REPO))
    from hermes_cli.openai_compat_endpoint import (
        openai_compat_endpoint_pool_hide,
        _DEFAULT_MODEL_REGISTRY,
    )
    # 1) 内部 workers + 默认 registry (跟 _DEFAULT_MODEL_REGISTRY 1:1 配对 0 改)
    internal_workers = [
        {"name": "fast_local_v2", "description": "internal v2"},
        {"name": "balanced_qwen2.5", "description": "internal qwen"},
    ]
    r_default = openai_compat_endpoint_pool_hide(internal_workers)
    assert r_default["internal_worker_count"] == 2
    assert r_default["pool_hidden"] is True
    # 默认 registry 至少 6 个 model (fast_local/balanced/smart_learned/gpt-5.6-sol/terra/luna)
    assert r_default["visible_model_count"] >= 6
    # 跟 OpenAI /v1/models 协议 1:1 配对
    assert r_default["endpoints"]["chat_completions"] == "/v1/chat/completions"
    assert r_default["endpoints"]["models"] == "/v1/models"
    # model 格式跟 OpenAI list models 协议 1:1 配对
    for m in r_default["models"]:
        assert m["object"] == "model"
        assert "id" in m
        assert "owned_by" in m
    # 2) 自定义 registry
    custom = {"my_model": {"mode": "fast_rule", "family": "custom", "visible": True}}
    r_custom = openai_compat_endpoint_pool_hide(internal_workers, model_registry=custom)
    assert r_custom["visible_model_count"] == 1
    assert r_custom["models"][0]["id"] == "my_model"
    # 3) hidden model 0 暴露
    hidden_only = {"internal": {"mode": "fast_rule", "family": "internal", "visible": False}}
    r_hidden = openai_compat_endpoint_pool_hide(internal_workers, model_registry=hidden_only)
    assert r_hidden["visible_model_count"] == 0


def test_cand_075_3_openai_compat_endpoint_dispatch_live():
    """5/6 live: dispatch /v1/chat/completions 请求 (跟 c3 1:1)."""
    sys.path.insert(0, str(REPO))
    from hermes_cli.openai_compat_endpoint import openai_compat_endpoint_dispatch
    workers = [{"name": "w1"}, {"name": "w2"}]
    # 1) 跟 OpenAI /v1/chat/completions protocol 1:1 配对
    request = {
        "model": "fast_local",
        "messages": [{"role": "user", "content": "hi"}],
    }
    r_fast = openai_compat_endpoint_dispatch(request, workers)
    assert r_fast["object"] == "chat.completion"
    assert r_fast["model"] == "fast_local"
    assert r_fast["routing_mode"] == "fast_rule"
    assert r_fast["dispatched_to"] == "CAND-072 lightweight_router"
    assert r_fast["message_count"] == 1
    assert r_fast["used_trained_weights"] is False
    # 2) 跟 CAND-073 adaptive pool 1:1 配对 (smart_learned mode + trained weights)
    request_smart = {
        "model": "smart_learned",
        "messages": [{"role": "user", "content": "test"}],
    }
    r_smart = openai_compat_endpoint_dispatch(request_smart, workers,
                                                 trained_weights={"w1": 0.9, "w2": 0.1})
    assert r_smart["routing_mode"] == "smart_learned"
    assert r_smart["dispatched_to"] == "CAND-073 adaptive_pool"
    assert r_smart["used_trained_weights"] is True
    # 3) 跟 CAND-015 gpt-5.6-sol 1:1 配对 0 冲突 (model 注册 ≠ endpoint 0 重叠)
    request_gpt = {"model": "gpt-5.6-sol", "messages": [{"role": "user", "content": "test"}]}
    r_gpt = openai_compat_endpoint_dispatch(request_gpt, workers)
    assert r_gpt["model"] == "gpt-5.6-sol"
    assert r_gpt["family"] == "openai"
    # 4) 跟 CAND-082 A/B test 1:1 配对 variant_a/variant_b (request 可作为 variant spec)
    r_terra = openai_compat_endpoint_dispatch(
        {"model": "gpt-5.6-terra", "messages": [{"role": "user", "content": "test"}]},
        workers,
    )
    assert r_terra["routing_mode"] == "smart_learned"
    # 5) model not found
    r_notfound = openai_compat_endpoint_dispatch(
        {"model": "nonexistent", "messages": [{"role": "user", "content": "test"}]},
        workers,
    )
    assert "error" in r_notfound
    assert r_notfound["error"] == "model_not_found"
    # 6) invalid request (0 model)
    r_no_model = openai_compat_endpoint_dispatch({"messages": []}, workers)
    assert "error" in r_no_model
    # 7) invalid request (0 messages)
    r_no_msg = openai_compat_endpoint_dispatch({"model": "fast_local"}, workers)
    assert "error" in r_no_msg


def test_apply_openai_compat_endpoint_combined_entry_live():
    """6/6 combined: 3 mode (register/pool_hide/dispatch) + invalid mode + 集成 verify."""
    sys.path.insert(0, str(REPO))
    from hermes_cli.openai_compat_endpoint import apply_openai_compat_endpoint
    workers = [{"name": "w1"}, {"name": "w2"}]
    # 1) register mode
    r_reg = apply_openai_compat_endpoint(mode="register", model_name="test_combined")
    assert r_reg["mode"] == "register"
    assert r_reg["register"]["model_name"] == "test_combined"
    assert r_reg["pool_hide"] is None
    assert r_reg["dispatch"] is None
    # 2) pool_hide mode
    r_hide = apply_openai_compat_endpoint(workers=workers, mode="pool_hide")
    assert r_hide["mode"] == "pool_hide"
    assert r_hide["pool_hide"]["pool_hidden"] is True
    assert r_hide["register"] is None
    assert r_hide["dispatch"] is None
    # 3) dispatch mode + fast_rule
    request_fast = {
        "model": "fast_local",
        "messages": [{"role": "user", "content": "test"}],
    }
    r_disp = apply_openai_compat_endpoint(request=request_fast, workers=workers, mode="dispatch")
    assert r_disp["mode"] == "dispatch"
    assert r_disp["dispatch"]["dispatched_to"] == "CAND-072 lightweight_router"
    # 4) dispatch mode + smart_learned + trained weights
    request_smart = {
        "model": "smart_learned",
        "messages": [{"role": "user", "content": "test"}],
    }
    r_disp_smart = apply_openai_compat_endpoint(
        request=request_smart, workers=workers, mode="dispatch",
        trained_weights={"w1": 0.9, "w2": 0.1},
    )
    assert r_disp_smart["dispatch"]["dispatched_to"] == "CAND-073 adaptive_pool"
    assert r_disp_smart["dispatch"]["used_trained_weights"] is True
    # 5) dispatch 0 request
    r_no_req = apply_openai_compat_endpoint(workers=workers, mode="dispatch")
    assert "error" in r_no_req
    # 6) invalid mode
    r_invalid = apply_openai_compat_endpoint(workers=workers, mode="invalid")
    assert "error" in r_invalid
    # 7) 跟 CAND-015 gpt-5.6 model 注册 1:1 配对 0 冲突 — CAND-075 dispatch model gpt-5.6-sol
    r_gpt = apply_openai_compat_endpoint(
        request={"model": "gpt-5.6-sol", "messages": [{"role": "user", "content": "test"}]},
        workers=workers, mode="dispatch",
    )
    assert r_gpt["dispatch"]["family"] == "openai"
    assert r_gpt["dispatch"]["model"] == "gpt-5.6-sol"

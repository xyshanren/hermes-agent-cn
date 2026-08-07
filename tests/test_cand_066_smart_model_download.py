"""Tests for CAND-066 (Sprint 8): hermes-agent-cn Smart model download (HF + ModelScope 双源)."""

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent


def test_smart_model_download_module_exists():
    p = REPO / "hermes_cli" / "smart_model_download.py"
    assert p.exists()
    src = p.read_text(encoding="utf-8")
    for fn in ("smart_model_download_select_source", "smart_model_download_fallback",
               "smart_model_download_track", "apply_smart_model_download"):
        assert f"def {fn}" in src


def test_smart_model_download_does_not_modify_model_download():
    cli_src = (REPO / "cli.py").read_text(encoding="utf-8")
    assert "smart_model_download" not in cli_src


def test_cand_066_1_smart_model_download_select_source_live():
    sys.path.insert(0, str(REPO))
    from hermes_cli.smart_model_download import smart_model_download_select_source
    # cn 用户 (prefer_cn=True) → primary modelscope
    result_cn = smart_model_download_select_source("Qwen/Qwen3-7B", prefer_cn=True)
    assert result_cn["primary"] == "modelscope"
    assert result_cn["fallback"] == "huggingface"
    assert result_cn["strategy"] == "prefer_cn"
    # 国际用户 (prefer_cn=False) → primary huggingface
    result_intl = smart_model_download_select_source("Qwen/Qwen3-7B", prefer_cn=False)
    assert result_intl["primary"] == "huggingface"
    assert result_intl["fallback"] == "modelscope"
    assert result_intl["strategy"] == "prefer_intl"


def test_cand_066_2_smart_model_download_fallback_live():
    sys.path.insert(0, str(REPO))
    from hermes_cli.smart_model_download import smart_model_download_fallback
    # primary failed → 走 fallback
    result = smart_model_download_fallback("modelscope", "huggingface", primary_failed=True)
    assert result["fallback_triggered"] is True
    assert result["next_source"] == "huggingface"
    # primary OK → 保持 primary
    result_ok = smart_model_download_fallback("modelscope", "huggingface", primary_failed=False)
    assert result_ok["next_source"] == "modelscope"
    # 非法 source
    result_invalid = smart_model_download_fallback("invalid", "modelscope")
    assert "error" in result_invalid


def test_cand_066_3_smart_model_download_track_live():
    sys.path.insert(0, str(REPO))
    from hermes_cli.smart_model_download import smart_model_download_track
    # 第一次 success
    r1 = smart_model_download_track("Qwen/Qwen3-7B", "modelscope", success=True)
    assert r1["success"] == 1
    assert r1["failed"] == 0
    # 第二次 failed
    r2 = smart_model_download_track("Qwen/Qwen3-7B", "huggingface", success=False)
    assert r2["success"] == 1
    assert r2["failed"] == 1
    # 不同 model
    r3 = smart_model_download_track("deepseek-ai/DeepSeek-V3", "modelscope", success=True)
    assert r3["success"] == 1
    assert r3["failed"] == 0


def test_apply_smart_model_download_combined_entry_live():
    sys.path.insert(0, str(REPO))
    from hermes_cli.smart_model_download import apply_smart_model_download
    result = apply_smart_model_download("Qwen/Qwen3-7B", prefer_cn=True, primary_failed=False)
    assert isinstance(result, dict)
    assert set(result.keys()) == {"select_source", "fallback", "track"}
    # cn user, primary OK → modelscope
    assert result["select_source"]["primary"] == "modelscope"
    assert result["fallback"]["next_source"] == "modelscope"
    assert result["track"]["source"] == "modelscope"
    # cn user, primary failed → huggingface fallback
    result_fallback = apply_smart_model_download(
        "Qwen/Qwen3-7B", prefer_cn=True, primary_failed=True
    )
    assert result_fallback["fallback"]["fallback_triggered"] is True
    assert result_fallback["track"]["source"] == "huggingface"

"""Tests for CAND-051 (Sprint 7 Wave 1): Persist per-session /model override."""

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent


def test_persist_session_model_module_exists():
    p = REPO / "hermes_cli" / "persist_session_model.py"
    assert p.exists()
    src = p.read_text(encoding="utf-8")
    for fn in ("persist_session_model_set", "persist_session_model_get", "persist_session_model_clear", "apply_persist_session_model"):
        assert f"def {fn}" in src


def test_persist_session_model_does_not_modify_session_storage():
    cli_src = (REPO / "cli.py").read_text(encoding="utf-8")
    assert "persist_session_model" not in cli_src


def test_cand_051_1_persist_session_model_set_live():
    sys.path.insert(0, str(REPO))
    from hermes_cli.persist_session_model import persist_session_model_set
    result = persist_session_model_set("sess-1", "deepseek-v3")
    assert result["session_id"] == "sess-1"
    assert result["model"] == "deepseek-v3"
    assert result["status"] == "persisted"


def test_cand_051_2_persist_session_model_get_live():
    sys.path.insert(0, str(REPO))
    from hermes_cli.persist_session_model import (
        persist_session_model_set, persist_session_model_get,
    )
    # Set then get
    persist_session_model_set("sess-2", "claude-opus-4.6")
    assert persist_session_model_get("sess-2") == "claude-opus-4.6"
    # 0 set → get None
    assert persist_session_model_get("nonexistent") is None


def test_cand_051_3_persist_session_model_clear_live():
    sys.path.insert(0, str(REPO))
    from hermes_cli.persist_session_model import (
        persist_session_model_set, persist_session_model_get, persist_session_model_clear,
    )
    persist_session_model_set("sess-3", "qwen-max")
    assert persist_session_model_get("sess-3") == "qwen-max"
    # Clear → True + get None
    assert persist_session_model_clear("sess-3") is True
    assert persist_session_model_get("sess-3") is None
    # 再 clear 不存在 → False
    assert persist_session_model_clear("sess-3") is False


def test_apply_persist_session_model_combined_entry_live():
    sys.path.insert(0, str(REPO))
    from hermes_cli.persist_session_model import apply_persist_session_model
    # Set 路径
    result_set = apply_persist_session_model("sess-4", model="gpt-5.4-pro", op="set")
    assert result_set["set"]["status"] == "persisted"
    # Get 路径
    result_get = apply_persist_session_model("sess-4", op="get")
    assert result_get["get"] == "gpt-5.4-pro"
    # Clear 路径
    result_clear = apply_persist_session_model("sess-4", op="clear")
    assert result_clear["clear"] is True
    # Get after clear
    result_get_none = apply_persist_session_model("sess-4", op="get")
    assert result_get_none["get"] is None

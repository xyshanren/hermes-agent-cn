"""Tests for CAND-047 (Sprint 7 Wave 1): Image-gen Codex 输入支持."""

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent


def test_image_gen_codex_module_exists():
    p = REPO / "hermes_cli" / "image_gen_codex.py"
    assert p.exists()
    src = p.read_text(encoding="utf-8")
    for fn in ("codex_image_input_detect", "codex_image_input_process", "codex_image_gen_dispatch", "apply_codex_image_gen"):
        assert f"def {fn}" in src


def test_image_gen_codex_does_not_modify_image_gen():
    cli_src = (REPO / "cli.py").read_text(encoding="utf-8")
    assert "image_gen_codex" not in cli_src


def test_cand_047_1_codex_image_input_detect_bytes_live():
    sys.path.insert(0, str(REPO))
    from hermes_cli.image_gen_codex import codex_image_input_detect
    assert codex_image_input_detect(b"\x89PNG") is True


def test_cand_047_2_codex_image_input_detect_url_live():
    sys.path.insert(0, str(REPO))
    from hermes_cli.image_gen_codex import codex_image_input_detect
    assert codex_image_input_detect("https://example.com/img.png") is True
    assert codex_image_input_detect("/local/path/img.png") is True
    assert codex_image_input_detect("not_an_image") is False


def test_cand_047_3_codex_image_input_process_live():
    sys.path.insert(0, str(REPO))
    from hermes_cli.image_gen_codex import codex_image_input_process
    result = codex_image_input_process(b"\x89PNG")
    assert result["kind"] == "bytes"
    assert result["status"] == "processed"


def test_apply_codex_image_gen_combined_entry_live():
    sys.path.insert(0, str(REPO))
    from hermes_cli.image_gen_codex import apply_codex_image_gen
    result = apply_codex_image_gen(b"\x89PNG")
    assert isinstance(result, dict)
    assert result["detect"] is True
    assert result["process"]["kind"] == "bytes"
    assert result["dispatch"]["provider"] == "codex"
    # Non-image input → detect False, dispatch skipped
    result_skip = apply_codex_image_gen("not_an_image")
    assert result_skip["detect"] is False
    assert result_skip["dispatch"]["gen_kind"] == "skipped"

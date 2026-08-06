"""Tests for CAND-015 (Sprint 7 Wave 1): gpt-5.6 系列完整注册.

跟 plan CAND-015 1:1 配对 (跟 CAND-005/007+054/012/013 1:1 配对 0 改旧):

- 新 hermes_cli/gpt_5_6_models.py (跟 CAND-007+054 1 file 8 functions 1:1 配对):
  * gpt_5_6_sol_register (跟 upstream c1 1:1)
  * gpt_5_6_terra_register (跟 upstream c2 1:1)
  * gpt_5_6_luna_register (跟 upstream c3 1:1)
  * 1 combined entry: apply_gpt_5_6_register
- 0 改 OpenAI provider 主体 (8-07 verify 0 hit)
- 0 改 cli.py
- 6 test (跟 3+1 件 1:1 配对)
"""

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent


# ---------- CAND-015 main change: 静态 source check ----------


def test_gpt_5_6_models_module_exists_with_3_functions():
    """CAND-015 main file: hermes_cli/gpt_5_6_models.py 存在, 3 functions + 1 combined (跟 CAND-007+054 1:1 配对)."""
    p = REPO / "hermes_cli" / "gpt_5_6_models.py"
    assert p.exists(), f"{p} missing (CAND-015 main file)"
    src = p.read_text(encoding="utf-8")
    expected_fns = [
        "gpt_5_6_sol_register",
        "gpt_5_6_terra_register",
        "gpt_5_6_luna_register",
        "apply_gpt_5_6_register",
    ]
    for fn in expected_fns:
        assert f"def {fn}" in src, f"function {fn} missing in gpt_5_6_models.py"
    assert len(expected_fns) == 4, f"expected 4 functions, got {len(expected_fns)}"


def test_gpt_5_6_models_does_not_modify_openai_provider():
    """CAND-015 additive: 0 改 OpenAI provider 主体 (跟 CAND-005 0 改 1:1 配对)."""
    # 0 cli.py 改 (跟 CAND-001 0 改 1:1 配对)
    cli_src = (REPO / "cli.py").read_text(encoding="utf-8")
    assert "gpt_5_6_models" not in cli_src, (
        "CAND-015 0 改 cli.py 主体, 0 cli.py import gpt_5_6_models"
    )


# ---------- CAND-015 3 functions live: 1 test per function ----------


def test_cand_015_1_gpt_5_6_sol_register_live():
    """CAND-015 (1/3): gpt_5_6_sol_register (跟 upstream c1 1:1, gpt-5.6-sol)."""
    sys.path.insert(0, str(REPO))
    from hermes_cli.gpt_5_6_models import gpt_5_6_sol_register
    result = gpt_5_6_sol_register()
    assert result["model"] == "gpt-5.6-sol"
    assert result["provider"] == "openai"
    assert result["family"] == "sol"


def test_cand_015_2_gpt_5_6_terra_register_live():
    """CAND-015 (2/3): gpt_5_6_terra_register (跟 upstream c2 1:1, gpt-5.6-terra)."""
    sys.path.insert(0, str(REPO))
    from hermes_cli.gpt_5_6_models import gpt_5_6_terra_register
    result = gpt_5_6_terra_register()
    assert result["model"] == "gpt-5.6-terra"
    assert result["provider"] == "openai"
    assert result["family"] == "terra"


def test_cand_015_3_gpt_5_6_luna_register_live():
    """CAND-015 (3/3): gpt_5_6_luna_register (跟 upstream c3 1:1, gpt-5.6-luna)."""
    sys.path.insert(0, str(REPO))
    from hermes_cli.gpt_5_6_models import gpt_5_6_luna_register
    result = gpt_5_6_luna_register()
    assert result["model"] == "gpt-5.6-luna"
    assert result["provider"] == "openai"
    assert result["family"] == "luna"


# ---------- Combined entry: apply_gpt_5_6_register (跟 CAND-005/007+054/012/013 1:1 配对) ----------


def test_apply_gpt_5_6_register_combined_entry_live():
    """CAND-015 combined entry: 跑 3 件套 (跟 CAND-005 apply_filter + CAND-007+054/012/013 1:1 配对)."""
    sys.path.insert(0, str(REPO))
    from hermes_cli.gpt_5_6_models import apply_gpt_5_6_register

    result = apply_gpt_5_6_register()
    # 3 model dicts (sol / terra / luna) (跟 CAND-005/007+054/012/013 1:1 配对)
    assert isinstance(result, list), "result should be list"
    assert len(result) == 3, f"expected 3 models, got {len(result)}"
    expected_families = {"sol", "terra", "luna"}
    actual_families = {r["family"] for r in result}
    assert actual_families == expected_families, (
        f"expected families {expected_families}, got {actual_families}"
    )
    # All OpenAI provider
    for r in result:
        assert r["provider"] == "openai"

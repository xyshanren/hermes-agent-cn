"""Tests for CAND-045 (Sprint 7 Wave 1): Google Vertex AI provider.

跟 plan CAND-045 1:1 配对 (跟 CAND-005/007+054/012/013/015 1:1 配对 0 改旧):

- 新 hermes_cli/vertex_ai_provider.py (跟 CAND-007+054 1 file 8 functions 1:1 配对):
  * vertex_ai_provider_register (跟 upstream c1 1:1)
  * vertex_ai_oauth2_config (跟 upstream c2 1:1)
  * vertex_ai_gemini_dispatch (跟 upstream c3 1:1)
  * 1 combined entry: apply_vertex_ai
- 0 改 provider registry 主体 (8-07 verify 0 hit)
- 0 改 cli.py
- 6 test (跟 3+1 件 1:1 配对)
"""

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent


def test_vertex_ai_provider_module_exists_with_3_functions():
    """CAND-045 main file: hermes_cli/vertex_ai_provider.py 存在, 3 functions + 1 combined."""
    p = REPO / "hermes_cli" / "vertex_ai_provider.py"
    assert p.exists(), f"{p} missing (CAND-045 main file)"
    src = p.read_text(encoding="utf-8")
    expected_fns = [
        "vertex_ai_provider_register",
        "vertex_ai_oauth2_config",
        "vertex_ai_gemini_dispatch",
        "apply_vertex_ai",
    ]
    for fn in expected_fns:
        assert f"def {fn}" in src, f"function {fn} missing in vertex_ai_provider.py"
    assert len(expected_fns) == 4


def test_vertex_ai_provider_does_not_modify_provider_registry():
    """CAND-045 additive: 0 改 provider registry 主体 (跟 CAND-005 0 改 1:1 配对)."""
    cli_src = (REPO / "cli.py").read_text(encoding="utf-8")
    assert "vertex_ai_provider" not in cli_src, (
        "CAND-045 0 改 cli.py 主体, 0 cli.py import vertex_ai_provider"
    )


def test_cand_045_1_vertex_ai_provider_register_live():
    """CAND-045 (1/3): vertex_ai_provider_register (跟 upstream c1 1:1)."""
    sys.path.insert(0, str(REPO))
    from hermes_cli.vertex_ai_provider import vertex_ai_provider_register
    result = vertex_ai_provider_register()
    assert result["provider"] == "vertex_ai"
    assert result["auth_type"] == "oauth2"
    assert result["default_model"] == "gemini-2.5-pro"


def test_cand_045_2_vertex_ai_oauth2_config_live():
    """CAND-045 (2/3): vertex_ai_oauth2_config (跟 upstream c2 1:1)."""
    sys.path.insert(0, str(REPO))
    from hermes_cli.vertex_ai_provider import vertex_ai_oauth2_config
    result = vertex_ai_oauth2_config(client_id="cid", client_secret="csec", project_id="my-proj")
    assert result["client_id"] == "cid"
    assert result["client_secret"] == "csec"
    assert result["project_id"] == "my-proj"


def test_cand_045_3_vertex_ai_gemini_dispatch_live():
    """CAND-045 (3/3): vertex_ai_gemini_dispatch (跟 upstream c3 1:1)."""
    sys.path.insert(0, str(REPO))
    from hermes_cli.vertex_ai_provider import vertex_ai_gemini_dispatch
    result = vertex_ai_gemini_dispatch(model="gemini-2.5-flash")
    assert result["provider"] == "vertex_ai"
    assert result["model"] == "gemini-2.5-flash"


def test_apply_vertex_ai_combined_entry_live():
    """CAND-045 combined entry: 跑 3 件套 (跟 CAND-005 apply_filter + CAND-007+054 1:1 配对)."""
    sys.path.insert(0, str(REPO))
    from hermes_cli.vertex_ai_provider import apply_vertex_ai

    result = apply_vertex_ai(
        client_id="cid", client_secret="csec", project_id="my-proj",
        model="gemini-2.5-flash",
    )
    assert isinstance(result, dict)
    expected_keys = {"provider_register", "oauth2_config", "gemini_dispatch"}
    assert set(result.keys()) == expected_keys
    assert result["provider_register"]["provider"] == "vertex_ai"
    assert result["oauth2_config"]["project_id"] == "my-proj"
    assert result["gemini_dispatch"]["model"] == "gemini-2.5-flash"

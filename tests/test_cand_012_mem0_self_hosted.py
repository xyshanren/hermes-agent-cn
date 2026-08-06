"""Tests for CAND-012 (Sprint 7 Wave 1): MEM0 self-hosted mode.

跟 plan CAND-012 1:1 配对 (跟 CAND-005/007+054 1:1 配对 0 改旧):

- 新 hermes_cli/mem0_self_hosted.py (跟 CAND-007+054 1 file 8 functions 1:1 配对):
  * mem0_self_hosted_config (跟 upstream c1 1:1)
  * mem0_setup_wizard_branch (跟 upstream c2 1:1)
  * mem0_self_hosted_healthcheck (跟 upstream c3 1:1)
  * 1 combined entry: apply_mem0_self_hosted
- 0 改 mem0 setup wizard 主体 (8-07 verify 0 hit)
- 0 改 cli.py
- 5 test (跟 3+1 件 1:1 配对)
"""

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent


# ---------- CAND-012 main change: 静态 source check ----------


def test_mem0_self_hosted_module_exists_with_3_functions():
    """CAND-012 main file: hermes_cli/mem0_self_hosted.py 存在, 3 functions + 1 combined (跟 CAND-007+054 1:1 配对)."""
    p = REPO / "hermes_cli" / "mem0_self_hosted.py"
    assert p.exists(), f"{p} missing (CAND-012 main file)"
    src = p.read_text(encoding="utf-8")
    expected_fns = [
        "mem0_self_hosted_config",
        "mem0_setup_wizard_branch",
        "mem0_self_hosted_healthcheck",
        "apply_mem0_self_hosted",
    ]
    for fn in expected_fns:
        assert f"def {fn}" in src, f"function {fn} missing in mem0_self_hosted.py"
    assert len(expected_fns) == 4, f"expected 4 functions, got {len(expected_fns)}"


def test_mem0_self_hosted_does_not_modify_setup_wizard():
    """CAND-012 additive: 0 改 mem0 setup wizard 主体 (跟 CAND-005 0 改 1:1 配对)."""
    # 0 cli.py 改 (跟 CAND-001 0 改 1:1 配对)
    cli_src = (REPO / "cli.py").read_text(encoding="utf-8")
    assert "mem0_self_hosted" not in cli_src, (
        "CAND-012 0 改 cli.py 主体, 0 cli.py import mem0_self_hosted"
    )


# ---------- CAND-012 3 functions live: 1 test per function ----------


def test_cand_012_1_mem0_self_hosted_config_live():
    """CAND-012 (1/3): mem0_self_hosted_config (跟 upstream c1 1:1, 加 self-hosted URL field)."""
    sys.path.insert(0, str(REPO))
    from hermes_cli.mem0_self_hosted import mem0_self_hosted_config
    # Skeleton 0 副作用, 返 dict 含 url/api_key/mode
    config = mem0_self_hosted_config(url="http://localhost:8000", api_key="sk-test")
    assert config["url"] == "http://localhost:8000"
    assert config["api_key"] == "sk-test"
    assert config["mode"] == "self_hosted"


def test_cand_012_2_mem0_setup_wizard_branch_live():
    """CAND-012 (2/3): mem0_setup_wizard_branch (跟 upstream c2 1:1, setup wizard 分支)."""
    sys.path.insert(0, str(REPO))
    from hermes_cli.mem0_self_hosted import mem0_setup_wizard_branch
    # Skeleton 0 副作用, 返 True 当 choice 合法
    assert mem0_setup_wizard_branch("self_hosted") is True
    assert mem0_setup_wizard_branch("hosted") is True
    assert mem0_setup_wizard_branch("invalid") is False


def test_cand_012_3_mem0_self_hosted_healthcheck_live():
    """CAND-012 (3/3): mem0_self_hosted_healthcheck (跟 upstream c3 1:1, healthcheck)."""
    sys.path.insert(0, str(REPO))
    from hermes_cli.mem0_self_hosted import mem0_self_hosted_healthcheck
    # Skeleton 0 副作用, 返 True 当 url 0 空
    assert mem0_self_hosted_healthcheck("http://localhost:8000") is True
    assert mem0_self_hosted_healthcheck("") is False


# ---------- Combined entry: apply_mem0_self_hosted (跟 CAND-005/007+054 1:1 配对) ----------


def test_apply_mem0_self_hosted_combined_entry_live():
    """CAND-012 combined entry: 跑 3 件套 (跟 CAND-005 apply_filter + CAND-007+054 1:1 配对)."""
    sys.path.insert(0, str(REPO))
    from hermes_cli.mem0_self_hosted import apply_mem0_self_hosted

    result = apply_mem0_self_hosted(
        url="http://localhost:8000",
        api_key="sk-test",
        choice="self_hosted",
    )
    # 3 keys (config / wizard_branch / healthcheck) (跟 CAND-005/007+054 1:1 配对)
    assert isinstance(result, dict), "result should be dict"
    expected_keys = {"config", "wizard_branch", "healthcheck"}
    assert set(result.keys()) == expected_keys, (
        f"expected 3 keys, got: {set(result.keys())}"
    )
    # config dict 含 url/api_key/mode
    assert result["config"]["url"] == "http://localhost:8000"
    assert result["config"]["mode"] == "self_hosted"
    # wizard branch + healthcheck 全 True
    assert result["wizard_branch"] is True
    assert result["healthcheck"] is True

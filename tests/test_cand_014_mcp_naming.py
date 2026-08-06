"""Tests for CAND-014 (Sprint 7 Wave 2): MCP `mcp__server__tool` 命名约定.

跟 plan CAND-014 1:1 配对 (跟 CAND-005/007+054/012/013/015/045/046/047/048/050/051 1:1 配对 0 改旧):

- 新 hermes_cli/mcp_naming.py (跟 CAND-007+054 1 file 8 functions 1:1 配对):
  * mcp_tool_naming_migrate (跟 upstream c1 1:1)
  * mcp_tool_name_validate (跟 upstream c2 1:1)
  * mcp_tool_name_register (跟 upstream c3 1:1)
  * 1 combined entry: apply_mcp_naming
- 0 改 mcp 主体 (8-07 verify 0 hit)
- 0 改 cli.py
- 6 test (跟 3+1 件 1:1 配对)
"""

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent


def test_mcp_naming_module_exists():
    """CAND-014 main file: hermes_cli/mcp_naming.py 存在, 3 functions + 1 combined."""
    p = REPO / "hermes_cli" / "mcp_naming.py"
    assert p.exists()
    src = p.read_text(encoding="utf-8")
    for fn in ("mcp_tool_naming_migrate", "mcp_tool_name_validate", "mcp_tool_name_register", "apply_mcp_naming"):
        assert f"def {fn}" in src
    # Verify upstream pattern reference
    assert "mcp__<server>__<tool>" in src or "mcp__{server}__{tool}" in src


def test_mcp_naming_does_not_modify_mcp():
    """CAND-014 additive: 0 改 mcp 主体 (跟 CAND-005 0 改 1:1 配对)."""
    cli_src = (REPO / "cli.py").read_text(encoding="utf-8")
    assert "mcp_naming" not in cli_src


def test_cand_014_1_mcp_tool_naming_migrate_live():
    """CAND-014 (1/3): mcp_tool_naming_migrate (跟 upstream c1 1:1, 命名迁移)."""
    sys.path.insert(0, str(REPO))
    from hermes_cli.mcp_naming import mcp_tool_naming_migrate
    result = mcp_tool_naming_migrate("old_tool_name", "github", "create_issue")
    assert result["old_name"] == "old_tool_name"
    assert result["new_name"] == "mcp__github__create_issue"
    assert result["server"] == "github"
    assert result["tool"] == "create_issue"


def test_cand_014_2_mcp_tool_name_validate_live():
    """CAND-014 (2/3): mcp_tool_name_validate (跟 upstream c2 1:1, name format 验证)."""
    sys.path.insert(0, str(REPO))
    from hermes_cli.mcp_naming import mcp_tool_name_validate
    # 合法 mcp__server__tool 格式
    assert mcp_tool_name_validate("mcp__github__create_issue") is True
    assert mcp_tool_name_validate("mcp__slack__send_message") is True
    # 非法格式
    assert mcp_tool_name_validate("create_issue") is False  # 缺 mcp__server__
    assert mcp_tool_name_validate("mcp_github_create_issue") is False  # 单 _
    assert mcp_tool_name_validate("mcp__GitHub__create") is False  # 大写


def test_cand_014_3_mcp_tool_name_register_live():
    """CAND-014 (3/3): mcp_tool_name_register (跟 upstream c3 1:1, registry 注册)."""
    sys.path.insert(0, str(REPO))
    from hermes_cli.mcp_naming import mcp_tool_name_register
    result = mcp_tool_name_register("filesystem", "read_file")
    assert result["name"] == "mcp__filesystem__read_file"
    assert result["server"] == "filesystem"
    assert result["tool"] == "read_file"
    assert result["registered"] is True


def test_apply_mcp_naming_combined_entry_live():
    """CAND-014 combined entry: 跑 3 件套 (跟 CAND-005 apply_filter + CAND-007+054 1:1 配对)."""
    sys.path.insert(0, str(REPO))
    from hermes_cli.mcp_naming import apply_mcp_naming
    result = apply_mcp_naming("old_format", "github", "create_issue")
    assert isinstance(result, dict)
    # 3 keys (migrate / validate / register)
    assert set(result.keys()) == {"migrate", "validate", "register"}
    assert result["migrate"]["new_name"] == "mcp__github__create_issue"
    assert result["validate"] is True
    assert result["register"]["name"] == "mcp__github__create_issue"
    assert result["register"]["registered"] is True

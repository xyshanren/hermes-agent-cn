"""Tests for CAND-008 (Sprint 4 next sprint): user-defined deny rules.

跟 plan CAND-008 1:1 配对 (跟 K-10 additive 1 line + K-7 k7_commands.py 1:1 配对):
- 新 hermes_cli/approvals_deny.py (3 functions: parse_deny_patterns / is_deny_match /
  check_deny, fnmatch stdlib, additive 0 改旧)
- hermes_cli/config.py:1915 approvals 段加 1 line "deny": [] + 7 line comment
  (跟 K-10 additive 1:1 配对, 0 改旧 approvals 字段)
- 0 改旧 approvals resolver (跟 K-9 0 改 webhook.py 主体 1:1 配对)
- 4 test (跟 K-10 1:1 配对 4 test, 2 静态 source check + 2 live integration)
"""

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent


# ---------- CAND-008 main change: 静态 source check ----------


def test_approvals_deny_module_exists():
    """CAND-008 main file: hermes_cli/approvals_deny.py 存在 (跟 K-7 k7_commands.py 1:1 配对)."""
    p = REPO / "hermes_cli" / "approvals_deny.py"
    assert p.exists(), f"{p} missing (CAND-008 main file)"
    src = p.read_text(encoding="utf-8")
    for fn in ("parse_deny_patterns", "is_deny_match", "check_deny"):
        assert f"def {fn}" in src, f"function {fn} missing in approvals_deny.py"


def test_config_approvals_deny_field():
    """CAND-008 config additive: `approvals.deny` field 已加 (跟 K-10 1:1 配对 1 line additive)."""
    config_src = (REPO / "hermes_cli" / "config.py").read_text(encoding="utf-8")
    assert '"deny": []' in config_src, (
        'config.py approvals 段缺 "deny": [] (CAND-008 additive 缺失)'
    )
    # 现有 5 字段 0 改 (跟 mavis 4 lesson UX 倒退审计 1:1)
    for field in ('"mode": "manual"', '"timeout": 60', '"cron_mode": "deny"',
                 '"mcp_reload_confirm": True', '"destructive_slash_confirm": True'):
        assert field in config_src, f"existing approvals 字段 {field} 0 改 0 失, CAND-008 破坏现有"


# ---------- CAND-008 live integration: 跟 plan 1:1 配对 ----------


def test_parse_deny_patterns_live():
    """Live: parse_deny_patterns 从 approvals config 段读 deny list (default empty = 0 deny)."""
    sys.path.insert(0, str(REPO))
    from hermes_cli.approvals_deny import parse_deny_patterns

    # 1. None → 0 deny (跟 default 1:1 配对)
    assert parse_deny_patterns(None) == [], "None cfg 应返 []"

    # 2. Empty dict → 0 deny
    assert parse_deny_patterns({}) == [], "empty dict 应返 []"

    # 3. 0 deny 段 → 0 deny (跟 config.py default 1:1 配对)
    assert parse_deny_patterns({"mode": "manual"}) == [], (
        "no deny 段应返 [], got: %r" % parse_deny_patterns({"mode": "manual"})
    )

    # 4. 标准 deny list 3 patterns
    cfg = {"deny": ["rm -rf /*", "mkfs.*", "dd if=*"]}
    assert parse_deny_patterns(cfg) == ["rm -rf /*", "mkfs.*", "dd if=*"]

    # 5. Defensive: 混合 type 自动 filter
    cfg_mixed = {"deny": ["valid", 123, None, "another"]}
    assert parse_deny_patterns(cfg_mixed) == ["valid", "another"], (
        "mixed type 应 filter 非 string, got: %r" % parse_deny_patterns(cfg_mixed)
    )


def test_check_deny_live():
    """Live: check_deny fnmatch 匹配 (跟 Bash fnmatch 1:1 兼容, case-sensitive glob)."""
    sys.path.insert(0, str(REPO))
    from hermes_cli.approvals_deny import check_deny

    patterns = ["rm -rf /*", "mkfs.*", "dd if=*"]

    # 1. 0 command → 0 deny
    is_denied, matched = check_deny("", patterns)
    assert is_denied is False, "空 command 应 0 deny"
    assert matched is None

    # 2. 0 pattern → 0 deny (跟 default empty 1:1 配对)
    is_denied, matched = check_deny("rm -rf /tmp", [])
    assert is_denied is False, "0 pattern 应 0 deny"

    # 3. exact match "rm -rf /*"
    is_denied, matched = check_deny("rm -rf /tmp", patterns)
    assert is_denied is True, "rm -rf /* 应 deny"
    assert matched == "rm -rf /*"

    # 4. fnmatch glob "mkfs.*"
    is_denied, matched = check_deny("mkfs.ext4 /dev/sda1", patterns)
    assert is_denied is True, "mkfs.ext4 应被 mkfs.* deny"
    assert matched == "mkfs.*"

    # 5. fnmatch glob "dd if=*"
    is_denied, matched = check_deny("dd if=/dev/zero of=/tmp/file", patterns)
    assert is_denied is True, "dd if= 应被 deny"
    assert matched == "dd if=*"

    # 6. 0 match 返 False
    is_denied, matched = check_deny("ls -la", patterns)
    assert is_denied is False, "ls -la 应 0 deny"
    assert matched is None

    # 7. 跟 Bash 1:1 兼容: case-sensitive
    is_denied, matched = check_deny("RM -RF /", patterns)
    assert is_denied is False, "RM -RF (大写) 跟 rm -rf (小写) 不匹配 (case-sensitive)"

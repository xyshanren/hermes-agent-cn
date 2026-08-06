"""Tests for CAND-056 (Sprint 6a): classifier Anthropic-specific guidance.

跟 plan CAND-056 1:1 配对 (跟 K-7 k7_commands.py + CAND-001/003/008 1:1 配对 0 改旧):
- 新 hermes_cli/classifier_anthropic.py (跟 CAND-001/003/008 1:1 配对 additive 0 改旧):
  * ANTHROPIC_SUBSCRIPTION_ERROR_PATTERNS: 4 错误 pattern
  * 2 functions: is_anthropic_subscription_error (fnmatch 0 副作用) /
    get_anthropic_subscription_guidance (4 条 guidance)
- 0 改 hermes_cli 现有 file (跟 UX 倒退审计 1:1)
- 4 test (2 静态 + 2 live, 跟 K-10 1:1 配对)
"""

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent


# ---------- CAND-056 main change: 静态 source check ----------


def test_classifier_anthropic_module_exists():
    """CAND-056 main file: hermes_cli/classifier_anthropic.py 存在 (跟 CAND-001/003/008 1:1)."""
    p = REPO / "hermes_cli" / "classifier_anthropic.py"
    assert p.exists(), f"{p} missing (CAND-056 main file)"
    src = p.read_text(encoding="utf-8")
    for fn in ("is_anthropic_subscription_error", "get_anthropic_subscription_guidance"):
        assert f"def {fn}" in src, f"function {fn} missing in classifier_anthropic.py"


def test_anthropic_4_error_patterns():
    """CAND-056 patterns: 4 已知 subscription exhaustion error pattern 完整 (跟 plan 1:1)."""
    src = (REPO / "hermes_cli" / "classifier_anthropic.py").read_text(encoding="utf-8")
    for pattern in ("rate_limit_exceeded", "insufficient_quota",
                    "subscription_exhausted", "overloaded_error"):
        assert f'"{pattern}"' in src, f"ANTHROPIC_SUBSCRIPTION_ERROR_PATTERNS 缺 {pattern}"


# ---------- CAND-056 live integration: 跟 plan 1:1 配对 ----------


def test_is_anthropic_subscription_error_live():
    """Live: is_anthropic_subscription_error fnmatch 匹配 (跟 CAND-008 is_deny_match 1:1)."""
    sys.path.insert(0, str(REPO))
    from hermes_cli.classifier_anthropic import is_anthropic_subscription_error

    # 1. 4 已知 pattern 应 True
    for pattern in ("rate_limit_exceeded", "insufficient_quota",
                    "subscription_exhausted", "overloaded_error"):
        assert is_anthropic_subscription_error(pattern) is True, (
            f"{pattern!r} 应 is_anthropic=True"
        )
        # 嵌在长 error message 也应 True (跟 fnmatch `*pattern*` 1:1)
        assert is_anthropic_subscription_error(
            f"Anthropic API error: {pattern} - please retry"
        ) is True

    # 2. 未知 pattern 应 False (跟 CAND-008 fnmatch 0 命 1:1 配对)
    assert is_anthropic_subscription_error("invalid_api_key") is False
    assert is_anthropic_subscription_error("model_not_found") is False
    assert is_anthropic_subscription_error("") is False

    # 3. None 应 False
    assert is_anthropic_subscription_error(None) is False, "None 应 False (跟 K-10 0 改 1:1)"

    # 4. case-insensitive 匹配 (跟 HTTP 1:1 配对)
    assert is_anthropic_subscription_error("RATE_LIMIT_EXCEEDED") is True, (
        "case-insensitive 应 match (跟 fnmatch 1:1 配对)"
    )


def test_get_anthropic_subscription_guidance_live():
    """Live: get_anthropic_subscription_guidance 返 4 条 guidance (跟 ANTHROPIC 1:1)."""
    sys.path.insert(0, str(REPO))
    from hermes_cli.classifier_anthropic import get_anthropic_subscription_guidance

    guidance = get_anthropic_subscription_guidance()

    # 1. 4 条 pattern 都在 guidance
    for pattern in ("rate_limit_exceeded", "insufficient_quota",
                    "subscription_exhausted", "overloaded_error"):
        assert pattern in guidance, f"guidance 应含 {pattern}"

    # 2. 4 条 guidance hint (retry / 配额 / 充值 / 等待)
    for hint in ("60s", "Anthropic Console", "支持", "30s"):
        assert hint in guidance, f"guidance 应含 hint: {hint}"

    # 3. type 应 str
    assert isinstance(guidance, str)
    assert len(guidance) > 0

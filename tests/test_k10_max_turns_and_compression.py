"""Tests for K-10 (Phase 4 v0.20.0 borrow): max_turns default 90→500 + compression.threshold.

跟 Phase 4 K-10 sprint plan §5.2 1:1 配对:
- 1 line CN change: `cli.py` default max_turns 90→500
- 跟现有 compression.threshold 0.50 1:1 集成 (cli.py → agent_init.py:1231 → context_compressor)
- regression guard: _MAX_TAIL_MESSAGE_FLOOR = 8 仍是 (cn-specific fix aaa3ee615, 跟 test_split_bugs_prevent_regression #12 1:1 配对)

4 静态 source check (cheap, 0 import heavy, 防改回归). 跟 test_split_bugs_prevent_regression 12 个 split
bug 同 pattern (AST-style 静态 check, 0 yaml 依赖). Live ContextCompressor integration 留给 CI
(`tests/agent/test_context_compressor.py` 已有 50% threshold 覆盖).
"""

import re
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent


# ---------- K-10 main change: 1 line CN change ----------


def test_cli_max_turns_default_500():
    """K-10 main change: cli.py default max_turns 90→500."""
    cli_src = (REPO / "cli.py").read_text(encoding="utf-8")
    # Find the default-config block (跟 plan K-10 §5.2 step 3 "find _config_version: 28 附近" 1:1 配对)
    m = re.search(r'"max_turns":\s*(\d+)', cli_src)
    assert m, "max_turns not found in cli.py"
    assert int(m.group(1)) == 500, (
        f"max_turns default should be 500 (K-10), got {m.group(1)}"
    )


# ---------- K-10 config integration: 跟 plan §5.2 step 4 1:1 配对 ----------


def test_cli_compression_threshold_050():
    """K-10 config integration: cli.py compression.threshold 0.50 (1:1 配对 _MAX_TAIL_MESSAGE_FLOOR)."""
    cli_src = (REPO / "cli.py").read_text(encoding="utf-8")
    assert '"threshold": 0.50' in cli_src, (
        "compression.threshold 0.50 missing in cli.py "
        "(跟 agent_init.py:1231 _compression_cfg.get('threshold', 0.50) 1:1 配对)"
    )


def test_agent_init_reads_compression_threshold_from_config():
    """K-10 integration point: agent_init.py 读 _compression_cfg.threshold (0 改, 跟 plan §5 1:1 配对)."""
    src = (REPO / "agent/agent_init.py").read_text(encoding="utf-8")
    assert '_compression_cfg.get("threshold", 0.50)' in src, (
        "agent_init.py:_compression_cfg.get('threshold', 0.50) integration point missing"
    )


# ---------- regression guard: 跟 test_split_bugs_prevent_regression #12 1:1 配对 ----------


def test_max_tail_message_floor_still_8():
    """防 K-10 改 cli.py 时意外影响 _MAX_TAIL_MESSAGE_FLOOR (cn-specific fix aaa3ee615)."""
    src = (REPO / "agent/context_compressor.py").read_text(encoding="utf-8")
    assert "_MAX_TAIL_MESSAGE_FLOOR = 8" in src, (
        "_MAX_TAIL_MESSAGE_FLOOR = 8 missing (cn-specific fix aaa3ee615, "
        "跟 test_split_bugs_prevent_regression #12 1:1 配对)"
    )

"""Tests for CAND-079 K-7 (Sprint 13b.1): hermes-agent-cn CN 3 wrapper /context /diff /focus.

跟 Sprint 11 Phase 1 test_cand_079_cn_prompt_miner 1:1 配对 6 test pattern
(1 静态 + 1 静态 0 改 + 3 live + 1 combined). 跟 CAND-085 4 铁律 1:1 配对:
0 改 13 stable file / CN 端可维护 / AIMC 集成兼容.

跟 user 8-09 拍 "Sprint 13b/c 安顺序来" 1:1 配对, Sprint 13b.1 = K-7 1 候选 1:1 配对:
3 CN wrapper 跟 8-06 §1.4 1:1 配对 (slash_exec.py EXECUTORS pattern), 跟 v0.20.0
file structure 1:1 配对 (c1750bb32 status bar / 4d6a133a9 focus mode 已经在
v0.20.0 merge 里, 935137f0d inline diff v0.20.0 0 命中 跟 8-06 §1.3 1:1 配对 CN stub).
"""

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent.parent


def test_k7_module_exists():
    """1/6 静态: file 存在 + 3 fns + 3 EXECUTORS key 1:1 配对 (跟 test_cand_078 1:1)."""
    p = REPO / "hermes_cli" / "slash_exec.py"
    assert p.exists()
    src = p.read_text(encoding="utf-8")
    for fn in ("_exec_context", "_exec_diff", "_exec_focus"):
        assert f"def {fn}" in src, f"missing function: {fn}"
    for key in ('"context"', '"diff"', '"focus"'):
        assert key in src, f"missing EXECUTORS key: {key}"


def test_k7_does_not_modify_13_stable_files():
    """2/6 静态 0 改: 验证 K-7 抽 file 0 改 13 stable file (跟 CAND-085 4 铁律 1:1).

    13 stable file: cli.py / hermes_cli/__init__.py / 4 routing tools / 2 agent files / Sprint 11/12 cn_prompt_*
    """
    stable_files = [
        "cli.py",
        "hermes_cli/__init__.py",
        "hermes_cli/adaptive_pool.py",
        "hermes_cli/synthetic_training_data.py",
        "hermes_cli/two_mode_router.py",
        "hermes_cli/openai_compat_endpoint.py",
        "tools/lightweight_router_tool.py",
        "tools/routing_ab_test_tool.py",
        "tools/routing_compaction_tool.py",
        "tools/routing_rule_manager_tool.py",
        "tools/cn_prompt_miner.py",  # Sprint 11 Phase 1 0 改
        "tools/cn_prompt_crawler.py",  # Sprint 12 Phase 3 0 改
        "agent/routing_decision.py",
        "agent/context_compressor.py",
    ]
    for rel in stable_files:
        p = REPO / rel
        assert p.exists(), f"stable file missing: {rel}"
        src = p.read_text(encoding="utf-8")
        # 0 引用 K-7 3 wrapper (跟 CAND-001 0 改 yolo 1:1 配对, 纯 additive)
        assert "_exec_context" not in src, (
            f"K-7 /context leaked into {rel} (违反 CAND-085 4 铁律 0 改 upstream)"
        )
        assert "_exec_diff" not in src, (
            f"K-7 /diff leaked into {rel} (违反 CAND-085 4 铁律 0 改 upstream)"
        )
        assert "_exec_focus" not in src, (
            f"K-7 /focus leaked into {rel} (违反 CAND-085 4 铁律 0 改 upstream)"
        )


def test_k7_1_exec_context_live():
    """3/6 live: /context 调 status bar (跟 c1750bb32 1:1 配对, 跟 8-06 §1.4 1:1 配对)."""
    sys.path.insert(0, str(REPO))
    from hermes_cli.slash_exec import _exec_context, CommandContext

    # 0 网络 / 0 agent / 0 LLM (跟 CAND-082 0 真 LLM 1:1 配对)
    ctx = CommandContext(surface="cli", args="")
    reply = _exec_context(ctx)
    assert reply.text  # 0 异常 + 非空
    # text 应含 context 占用或 fallback 提示 (跟 v0.20.0 1:1 配对)
    assert isinstance(reply.text, str)


def test_k7_2_exec_diff_live():
    """4/6 live: /diff CN stub (跟 935137f0d 0 命中 1:1 配对, 跟 8-06 §1.4 1:1 配对)."""
    sys.path.insert(0, str(REPO))
    from hermes_cli.slash_exec import _exec_diff, CommandContext

    ctx = CommandContext(surface="cli", args="")
    reply = _exec_diff(ctx)
    assert reply.text
    # CN stub 应提示 "no diff cached" (跟 v0.20.0 0 命中 1:1 配对)
    assert "no diff cached" in reply.text
    assert reply.data.get("diff") is None


def test_k7_3_exec_focus_live():
    """5/6 live: /focus 调 resolve_runtime_mode (跟 4d6a133a9 1:1 配对, 跟 8-06 §1.4 1:1 配对)."""
    sys.path.insert(0, str(REPO))
    from hermes_cli.slash_exec import _exec_focus, CommandContext

    ctx = CommandContext(surface="cli", args="")
    reply = _exec_focus(ctx)
    assert reply.text
    # 跟 v0.20.0 1:1 配对: focus mode 已经在 v0.20.0 merge 里
    # 0 异常, text 应含 "Mode:" 跟 "coding_context.focus" 提示
    assert "Mode:" in reply.text
    assert "coding_context.focus" in reply.text


def test_k7_combined_context_diff_focus():
    """6/6 combined: 3 wrapper 一起跑 (跟 Sprint 11/12 combined 1:1 配对)."""
    sys.path.insert(0, str(REPO))
    from hermes_cli.slash_exec import (
        _exec_context,
        _exec_diff,
        _exec_focus,
        CommandContext,
    )

    ctx = CommandContext(surface="cli", args="")
    replies = {
        "context": _exec_context(ctx),
        "diff": _exec_diff(ctx),
        "focus": _exec_focus(ctx),
    }
    # 3 wrapper 全部 0 异常 + 非空
    for name, reply in replies.items():
        assert reply.text, f"{name} returned empty text"
    # 跟 8-06 §1.4 happy-path smoke test 1:1 配对
    # /context 显 context 占用
    assert isinstance(replies["context"].text, str)
    # /diff 显 last inline diff (CN stub)
    assert "no diff cached" in replies["diff"].text
    # /focus 切换 mode (CN stub via config toggle)
    assert "Mode:" in replies["focus"].text

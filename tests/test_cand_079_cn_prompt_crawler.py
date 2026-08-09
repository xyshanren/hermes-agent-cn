"""Tests for CAND-079 Phase 3 (Sprint 12): hermes-agent-cn cn 模型 system prompts 公开 crawl.

跟 Sprint 11 Phase 1 test_cand_079_cn_prompt_miner 1:1 配对 6 test pattern
(1 静态 + 1 静态 0 改 + 3 live + 1 combined). 跟 CAND-085 4 铁律 1:1 配对:
0 改 12 stable file / CN 端可维护 / AIMC 集成兼容.

跟 user 8-08 拍 "Sprint 12 单一 Phase 3 实施 + 砍微信公众号" 1:1 配对:
5 source (GitHub/HF/掘金/V2EX/RSS) 0 钱 0 GPU 0 ToS 0 license.
"""

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent


def test_cand_079_p3_module_exists():
    """1/6 静态: file 存在 + 5 fns + combined 1:1 配对 (跟 test_cand_078 1:1 配对)."""
    p = REPO / "tools" / "cn_prompt_crawler.py"
    assert p.exists()
    src = p.read_text(encoding="utf-8")
    for fn in ("cn_prompt_crawler_github",
               "cn_prompt_crawler_huggingface",
               "cn_prompt_crawler_juejin",
               "cn_prompt_crawler_v2ex",
               "cn_prompt_crawler_rss",
               "cn_prompt_crawler_all"):
        assert f"def {fn}" in src, f"missing function: {fn}"


def test_cand_079_p3_does_not_modify_12_stable_files():
    """2/6 静态 0 改: 验证 CAND-079 Phase 3 抽 file 0 改 12 stable file (跟 CAND-085 4 铁律 1:1 配对).

    12 stable file: cli.py / hermes_cli/__init__.py / 4 routing tools / 4 agent files / Sprint 11 cn_prompt_miner.
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
        "agent/routing_decision.py",
        "agent/context_compressor.py",
    ]
    for rel in stable_files:
        p = REPO / rel
        assert p.exists(), f"stable file missing: {rel}"
        src = p.read_text(encoding="utf-8")
        # 0 引用 cn_prompt_crawler (跟 CAND-001 0 改 yolo 1:1 配对, 纯 additive)
        assert "cn_prompt_crawler" not in src, (
            f"CAND-079 Phase 3 leaked into {rel} (违反 CAND-085 4 铁律 0 改 upstream)"
        )


def test_cand_079_p3_1_github_live():
    """3/6 live: GitHub Search API (offline-mode 0 网络, 0 exception 0 副作用)."""
    sys.path.insert(0, str(REPO))
    from tools.cn_prompt_crawler import cn_prompt_crawler_github

    # 0 网络时 ok=list 但 0 exception (跟 CAND-082 0 真 fetch 1:1 配对)
    result = cn_prompt_crawler_github("DeepSeek system prompt", limit=3)
    assert isinstance(result, list)
    # 若有结果, 验证 schema
    for item in result:
        assert item.get("source") == "github"
        assert "query" in item
        assert "url" in item


def test_cand_079_p3_2_huggingface_live():
    """4/6 live: HuggingFace model card (offline-mode 0 网络, 0 exception 0 副作用)."""
    sys.path.insert(0, str(REPO))
    from tools.cn_prompt_crawler import cn_prompt_crawler_huggingface

    result = cn_prompt_crawler_huggingface("deepseek-ai/DeepSeek-V3", max_chars=2000)
    assert isinstance(result, list)
    for item in result:
        assert item.get("source") == "huggingface"
        assert "repo" in item
        assert "content" in item


def test_cand_079_p3_3_v2ex_live():
    """5/6 live: V2EX 公开 API (offline-mode 0 网络, 0 exception 0 副作用)."""
    sys.path.insert(0, str(REPO))
    from tools.cn_prompt_crawler import cn_prompt_crawler_v2ex

    result = cn_prompt_crawler_v2ex("prompt", limit=10)
    assert isinstance(result, list)
    for item in result:
        assert item.get("source") == "v2ex"
        assert "title" in item
        assert "url" in item
        # url 必含 /t/<id>
        assert "/t/" in item.get("url", "")


def test_cand_079_p3_4_combined_orchestrator():
    """6/6 combined: 跑 cn_prompt_crawler_all combined orchestrator (跟 Phase 1 1:1)."""
    sys.path.insert(0, str(REPO))
    from tools.cn_prompt_crawler import cn_prompt_crawler_all

    # 5 source combined
    result = cn_prompt_crawler_all(
        keywords=["DeepSeek prompt", "Qwen prompt"],
        limit_per_source=2,
    )
    # 验证 5 source 全部返回 (即使空 list, 也必须有 key)
    assert isinstance(result, dict)
    for source in ("github", "huggingface", "juejin", "v2ex", "rss"):
        assert source in result, f"missing source in combined: {source}"
        assert isinstance(result[source], list)

    # 跟 mavis 5-drops lesson #2 1:1 配对: 0 微信公众号 source (跟 user 8-08 拍 "砍" 1:1)
    assert "wechat" not in result
    assert "weixin" not in result
    assert "公众号" not in result

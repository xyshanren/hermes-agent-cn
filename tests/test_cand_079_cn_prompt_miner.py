"""Tests for CAND-079 Phase 1 (Sprint 11): hermes-agent-cn cn 模型 system prompts 官方 mine.

跟 Sprint 9a CAND-078 1:1 配对 6 test pattern (1 静态 + 1 静态 0 改 + 3 live + 1 combined).
跟 CAND-085 4 铁律 1:1 配对: 0 改 6 stable file / CN 端可维护 / AIMC 集成兼容.
"""

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent


def test_cand_079_module_exists():
    """1/6 静态: file 存在 + 3 fns + combined 1:1 配对 (跟 test_cand_078 1:1 配对)."""
    p = REPO / "tools" / "cn_prompt_miner.py"
    assert p.exists()
    src = p.read_text(encoding="utf-8")
    for fn in ("cn_prompt_miner_fetch_official",
               "cn_prompt_miner_extract_prompts",
               "cn_prompt_miner_save_to_corpus",
               "cn_prompt_miner_official"):
        assert f"def {fn}" in src, f"missing function: {fn}"


def test_cand_079_does_not_modify_6_stable_files():
    """2/6 静态 0 改: 验证 CAND-079 抽 file 0 改 6 stable file (跟 CAND-085 4 铁律 1:1 配对).

    6 stable file: cli.py / hermes_cli/__init__.py / 4 routing tools / 2 agent files.
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
        "agent/routing_decision.py",
        "agent/context_compressor.py",
    ]
    for rel in stable_files:
        p = REPO / rel
        assert p.exists(), f"stable file missing: {rel}"
        src = p.read_text(encoding="utf-8")
        # 0 引用 cn_prompt_miner (跟 CAND-001 0 改 yolo 1:1 配对, 纯 additive)
        assert "cn_prompt_miner" not in src, (
            f"CAND-079 leaked into {rel} (违反 CAND-085 4 铁律 0 改 upstream)"
        )


def test_cand_079_1_cn_prompt_miner_fetch_official_live():
    """3/6 live: 官方 fetch (offline-mode 0 网络, 0 exception 0 副作用)."""
    sys.path.insert(0, str(REPO))
    from tools.cn_prompt_miner import cn_prompt_miner_fetch_official

    # 1) fetch 任意 repo, 0 网络时 ok=False 但 0 exception (跟 CAND-082 0 真 fetch 1:1 配对)
    result = cn_prompt_miner_fetch_official("deepseek-ai/DeepSeek-V3")
    assert result["repo"] == "deepseek-ai/DeepSeek-V3"
    assert len(result["sources"]) == 2  # GitHub README + HF model card
    for source in result["sources"]:
        assert "url" in source
        assert "content" in source
        assert "ok" in source
    # 2) max_doc_bytes 截断 verify
    result_truncated = cn_prompt_miner_fetch_official("QwenLM/Qwen3", max_doc_bytes=100)
    for source in result_truncated["sources"]:
        assert len(source["content"]) <= 100, "max_doc_bytes truncation failed"


def test_cand_079_2_cn_prompt_miner_extract_prompts_live():
    """4/6 live: extract prompts, 3 pattern verify (跟 cand-079 doc §3.3 1:1 配对)."""
    sys.path.insert(0, str(REPO))
    from tools.cn_prompt_miner import cn_prompt_miner_extract_prompts

    # 1) Code block 含 'you are' / 'system' indicator (>=2 hit) → 提取
    md_with_code = (
        "# Demo\n\n"
        "## System Prompt\n\n"
        "```\n"
        "You are a helpful assistant. You must be concise.\n"
        "You should answer in Chinese. system: cn\n"
        "```\n\n"
        "## Usage\n\n"
        "Run the script.\n"
    )
    prompts_code = cn_prompt_miner_extract_prompts(md_with_code, source="test.md")
    code_blocks = [p for p in prompts_code if p["type"] == "code_block"]
    sections = [p for p in prompts_code if p["type"] == "section"]
    assert len(code_blocks) >= 1, f"code block extraction failed: {prompts_code}"
    # case-insensitive: content 实际是 "helpful" lowercase
    assert any("helpful" in p["content"].lower() for p in code_blocks)
    assert len(sections) >= 1, f"section extraction failed: {prompts_code}"
    assert any(s["title"].lower() == "system prompt" for s in sections)

    # 2) cn indicator (你的角色 / 你是 / 提示词) verify
    md_cn = "# Test\n\n## 提示词\n\n你是 AI 助手, 你的角色是回答问题.\n"
    prompts_cn = cn_prompt_miner_extract_prompts(md_cn, source="test_cn.md")
    cn_sections = [p for p in prompts_cn if p["type"] == "section"]
    assert any("提示词" in s["title"] for s in cn_sections)

    # 3) JSON 含 'system' field 提取
    md_json = '# Demo\n\n```json\n{"system": "You are a coding assistant."}\n```\n'
    prompts_json = cn_prompt_miner_extract_prompts(md_json, source="test_json.md")
    json_prompts = [p for p in prompts_json if p["type"] == "json"]
    assert len(json_prompts) >= 1, f"json extraction failed: {prompts_json}"
    assert "system" in json_prompts[0]["content"]

    # 4) 0 indicator 时 0 prompts (跟 heuristic 阈值 2+ 1:1 配对)
    md_empty = "# Demo\n\nSome random text without any system prompt indicators.\n"
    prompts_empty = cn_prompt_miner_extract_prompts(md_empty, source="empty.md")
    assert len(prompts_empty) == 0, f"empty extraction should yield 0: {prompts_empty}"


def test_cand_079_3_cn_prompt_miner_save_to_corpus_live():
    """5/6 live: save path 计算, 验证相对路径 + section slug (跟 CAND-082 0 persist 1:1 配对)."""
    sys.path.insert(0, str(REPO))
    from tools.cn_prompt_miner import cn_prompt_miner_save_to_corpus

    # 1) 0 prompts → 0 saved paths
    assert cn_prompt_miner_save_to_corpus([], "DeepSeek", "x") == []

    # 2) 多种 type → 正确 file naming
    fake_prompts = [
        {"type": "code_block", "content": "x"},
        {"type": "section", "title": "System Prompt", "content": "y"},
        {"type": "json", "content": "{}"},
    ]
    # Windows Path 用 backslash, test normalize 到 forward slash
    def _norm(p: str) -> str:
        return p.replace("\\", "/")

    saved = cn_prompt_miner_save_to_corpus(fake_prompts, "DeepSeek", "deepseek-ai/DeepSeek-V3")
    assert len(saved) == 3
    assert _norm(saved[0]) == "corpus/official/DeepSeek/deepseek-ai/DeepSeek-V3/code_block-000.md"
    assert "section-001" in _norm(saved[1])
    assert "System-Prompt" in _norm(saved[1]) or "system-prompt" in _norm(saved[1]).lower()
    assert _norm(saved[2]) == "corpus/official/DeepSeek/deepseek-ai/DeepSeek-V3/json-002.md"

    # 3) cn title 含 / 时 slug 替换 (防止 path injection)
    fake_cn = [{"type": "section", "title": "系统/提示词", "content": "z"}]
    saved_cn = cn_prompt_miner_save_to_corpus(fake_cn, "Qwen", "QwenLM/Qwen3")
    assert "系统-提示词" in _norm(saved_cn[0]), f"cn slash replacement failed: {saved_cn}"


def test_cand_079_combined_official_live():
    """6/6 combined: 跑 3 阶段, 14 vendor verify, 0 网络 0 exception (跟 CAND-082 0 LLM call 1:1 配对)."""
    sys.path.insert(0, str(REPO))
    from tools.cn_prompt_miner import cn_prompt_miner_official, GITHUB_REPOS

    # 1) 14 vendor 全覆盖 (deepseek/qwen/glm/kimi/hunyuan/internlm/yi/xunfei)
    assert len(GITHUB_REPOS) == 14
    vendors = {entry["vendor"] for entry in GITHUB_REPOS}
    assert vendors == {
        "DeepSeek", "Qwen", "GLM", "Kimi", "Hunyuan", "InternLM", "Yi", "Xunfei",
    }, f"vendor coverage incomplete: {vendors}"

    # 2) combined 跑 14 repo, 0 网络 0 exception (跟 CAND-082 0 真 LLM 1:1 配对)
    # 跑真网络会慢, 用 sub-repo set 验证结构 OK 即可
    sub_repos = GITHUB_REPOS[:2]  # DeepSeek-V3 + DeepSeek-R1
    result = cn_prompt_miner_official(repos=sub_repos, max_doc_bytes=200)
    assert result["total_repos"] == 2
    assert len(result["by_repo"]) == 2
    assert result["by_repo"][0]["vendor"] == "DeepSeek"
    # 3) 0 网络时 ok=False 但 0 prompts 0 exception, stats 一致
    for entry in result["by_repo"]:
        assert "n_prompts" in entry
        assert "saved_paths" in entry
        assert isinstance(entry["n_prompts"], int)
        assert isinstance(entry["saved_paths"], list)

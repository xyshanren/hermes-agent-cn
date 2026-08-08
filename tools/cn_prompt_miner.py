"""CAND-079 cn 模型 system prompts corpus — C. 官方 mine (Phase 4 v0.20.0 borrow, Sprint 11 Phase 1).

跟 plan CAND-079 1:1 配对 (跟 CAND-078 done 集成 1:1 配对 0 改旧):

CAND-079 3 工具链, Sprint 11 Phase 1 干 C. 官方 mine (最低风险 0 GPU 0 ToS 0 license):
- cn_prompt_miner_fetch_official (跟 c1 1:1, fetch GitHub README + HF model card via stdlib urllib)
- cn_prompt_miner_extract_prompts (跟 c2 1:1, 启发式提取 prompt from content, en + cn + neutral indicator)
- cn_prompt_miner_save_to_corpus (跟 c3 1:1, 计算 corpus/official/{vendor}/{repo}/ 路径)
- cn_prompt_miner_official (combined, orchestrator, 跑 3 阶段)

跟 mavis 4 件套 1:1 配对 + CAND-084 8-03 lesson "估时前必 verify 引擎能力":
- 后端先调查再设计: tools/cn_prompt_* 0 hit (8-08 verify), 0 改 6 stable file
- Cherry-pick split bug class: 0 cherry-pick (新 file, 跟 CAND-001 1:1 配对)
- UX 倒退审计: 0 改 hermes_cli/* 现有 file, 抽 file additive 0 改
- 估时前必 verify 引擎能力: 实际 0.5-1h (跟 plan 0.5-1d 1:1 配对 0.1-0.2x 缩)

跟 AIMC 4 铁律 1:1: 0 改 upstream / CN 端可维护 / 0 借鉴 OpenFugu AGPL-3.0 代码
(CC0 自建 corpus, 跟 CAND-077 不借鉴清单 1:1 配对, 跟 CAND-078 done 训练 pipeline 1:1).
"""

from __future__ import annotations

import json
import logging
import re
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


# CAND-079 3 件套 (跟 CAND-078 done 训练 pipeline 1:1 配对, corpus 喂给训练)
# Sprint 11 Phase 1: C. 官方 mine (最低风险 0 GPU 0 ToS 0 license)
# 注: skeleton 形式, 0 副作用 (跟 CAND-001/003 + CAND-007+054 1:1 配对 additive pattern)


# GITHUB_REPOS: 14 个国内模型 vendor 官方 repo (跟 cand-079-cn-prompt-corpus-tools-design.md §3.2 1:1)
# 排序: DeepSeek → Qwen → GLM → Kimi → Hunyuan → InternLM → Yi → Xunfei
GITHUB_REPOS: List[Dict[str, str]] = [
    # DeepSeek
    {"vendor": "DeepSeek", "repo": "deepseek-ai/DeepSeek-V3"},
    {"vendor": "DeepSeek", "repo": "deepseek-ai/DeepSeek-R1"},
    {"vendor": "DeepSeek", "repo": "deepseek-ai/DeepSeek-V2"},
    # Qwen
    {"vendor": "Qwen", "repo": "QwenLM/Qwen3"},
    {"vendor": "Qwen", "repo": "QwenLM/Qwen-Agent"},
    {"vendor": "Qwen", "repo": "QwenLM/Qwen2"},
    # GLM / ChatGLM
    {"vendor": "GLM", "repo": "THUDM/GLM-4"},
    {"vendor": "GLM", "repo": "THUDM/ChatGLM3"},
    {"vendor": "GLM", "repo": "THUDM/GLM-130B"},
    # Kimi / Moonshot
    {"vendor": "Kimi", "repo": "moonshotai/MoonshotAI"},
    # Hunyuan
    {"vendor": "Hunyuan", "repo": "Tencent-Hunyuan/Hunyuan"},
    # InternLM
    {"vendor": "InternLM", "repo": "internlm/internlm2_5"},
    # Yi
    {"vendor": "Yi", "repo": "01-ai/Yi"},
    # Xunfei / iFLYTEK
    {"vendor": "Xunfei", "repo": "iflytek/spark-13B"},
]


# SYSTEM_PROMPT_INDICATORS: en + cn + neutral 三类识别 (跟 cand-079 doc §2.3 + §3.3 1:1 配对)
_SYSTEM_PROMPT_INDICATORS_EN: List[str] = [
    "you are", "your role", "you must", "you should", "you can",
    "you cannot", "you will",
]
_SYSTEM_PROMPT_INDICATORS_CN: List[str] = [
    "你的角色", "你是", "你必须", "你不应该", "你不能", "你将会",
]
_SYSTEM_PROMPT_INDICATORS_NEUTRAL: List[str] = [
    "system:", "<|system|>", "<system>", "system prompt", "system message",
    "提示词", "系统提示", "系统消息",
]


def _matches_system_prompt_indicator(text: str) -> bool:
    """启发式判断 text 是否含 system prompt 指示词 (en + cn + neutral).

    阈值: 2+ 命中 (跟 cand-079 doc §3.3 extract_prompts_heuristic 1:1 配对).
    """
    if not text:
        return False
    text_lower = text.lower()
    count = 0
    for ind in _SYSTEM_PROMPT_INDICATORS_EN:
        if ind in text_lower:
            count += 1
    for ind in _SYSTEM_PROMPT_INDICATORS_CN:
        if ind in text:
            count += 1
    for ind in _SYSTEM_PROMPT_INDICATORS_NEUTRAL:
        if ind in text_lower:
            count += 1
    return count >= 2


def _extract_code_blocks(content: str) -> List[str]:
    """提取 markdown code blocks (跟 cand-079 doc §3.3 1:1 配对).

    简单 ``` 配对扫描, 0 regex 复杂度, 跟 CAND-082 A/B test 0 外部 lib 1:1.
    """
    blocks: List[str] = []
    in_block = False
    current: List[str] = []
    for line in content.splitlines():
        if line.strip().startswith("```"):
            if in_block:
                blocks.append("\n".join(current))
                current = []
                in_block = False
            else:
                in_block = True
        elif in_block:
            current.append(line)
    return blocks


def _extract_markdown_sections(content: str) -> List[Dict[str, str]]:
    """提取 markdown sections (跟 cand-079 doc §3.3 1:1 配对).

    简单 # 标题扫描, 0 regex 复杂度, 跟 CAND-082 0 外部 lib 1:1.
    """
    sections: List[Dict[str, str]] = []
    current_title = ""
    current_lines: List[str] = []
    for line in content.splitlines():
        if line.startswith("#"):
            if current_title and current_lines:
                sections.append({"title": current_title, "content": "\n".join(current_lines)})
            current_title = line.lstrip("#").strip()
            current_lines = []
        else:
            if current_title:
                current_lines.append(line)
    if current_title and current_lines:
        sections.append({"title": current_title, "content": "\n".join(current_lines)})
    return sections


def _fetch_url(url: str, timeout: int = 15) -> Optional[str]:
    """stdlib urllib 抓 URL (跟 CAND-078 pure-Python 1:1 配对, 0 vendor lock-in).

    Returns: response body as utf-8 str, or None on error.
    错误吞掉 (跟 skeleton 0 副作用 1:1, 不抛 exception).
    """
    try:
        req = urllib.request.Request(
            url,
            headers={"User-Agent": "hermes-cn-corpus-miner/1.0"},
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = resp.read()
            return data.decode("utf-8", errors="replace")
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, OSError, ValueError) as e:
        logger.debug("fetch %s failed: %s", url, e)
        return None


def cn_prompt_miner_fetch_official(repo: str,
                                     max_doc_bytes: int = 1_000_000) -> Dict[str, Any]:
    """CAND-079 (1/3): fetch 官方 GitHub README + HF model card (跟 c1 1:1).

    跟 plan CAND-079 1:1 配对 — 抓公开 GitHub/HF 内容, 0 license 风险 (公开渠道).
    Skeleton additive 0 副作用 (跟 CAND-082 训练数据导出 1:1 配对).

    Args:
        repo: GitHub repo (e.g. "deepseek-ai/DeepSeek-V3") or HF model id
        max_doc_bytes: 单 doc 截断字节数 (防止 huge repo 拉爆内存, 1MB default)

    Returns:
        {"repo": str, "sources": [{"url": str, "content": str, "ok": bool}, ...]}
    """
    logger.debug("CAND-079 cn_prompt_miner_fetch_official repo=%s", repo)
    sources: List[Dict[str, Any]] = []

    # 1. GitHub README (main 优先, master fallback)
    readme_url = f"https://raw.githubusercontent.com/{repo}/main/README.md"
    content = _fetch_url(readme_url)
    if content is None:
        readme_url = f"https://raw.githubusercontent.com/{repo}/master/README.md"
        content = _fetch_url(readme_url)
    sources.append({
        "url": readme_url,
        "content": (content or "")[:max_doc_bytes],
        "ok": content is not None,
    })

    # 2. HuggingFace model card (best-effort, 公开 model)
    hf_url = f"https://huggingface.co/{repo}/resolve/main/README.md"
    hf_content = _fetch_url(hf_url)
    sources.append({
        "url": hf_url,
        "content": (hf_content or "")[:max_doc_bytes],
        "ok": hf_content is not None,
    })

    return {"repo": repo, "sources": sources}


def cn_prompt_miner_extract_prompts(content: str, source: str = "") -> List[Dict[str, Any]]:
    """CAND-079 (2/3): 启发式提取 prompt (跟 c2 1:1).

    跟 plan CAND-079 1:1 配对 — 3 模式提取 (跟 cand-079 doc §3.3 1:1):
    1. Code blocks 含 'system' / 'you are' / '你的' / '你是' keyword (>=2 indicator)
    2. Sections titled 'Prompt' / 'System Prompt' / '提示词' / '系统提示' / 'preamble'
    3. JSON-like content 含 'system' field (lenient regex + json.loads 兜底)

    Returns: list of {"type": str, "source": str, "content"/"title": str}
    """
    if not content:
        return []
    prompts: List[Dict[str, Any]] = []

    # 1. Code blocks
    for code_block in _extract_code_blocks(content):
        if _matches_system_prompt_indicator(code_block):
            prompts.append({"type": "code_block", "source": source, "content": code_block})

    # 2. Sections
    for section in _extract_markdown_sections(content):
        title_lower = section["title"].lower()
        if any(kw in title_lower for kw in ("prompt", "提示", "system", "preamble")):
            prompts.append({
                "type": "section",
                "source": source,
                "title": section["title"],
                "content": section["content"],
            })

    # 3. JSON-like (best-effort, lenient)
    for match in re.finditer(r'\{[^{}]*"system"[^{}]*\}', content, re.DOTALL):
        try:
            obj = json.loads(match.group(0))
            if isinstance(obj, dict) and "system" in obj:
                prompts.append({
                    "type": "json",
                    "source": source,
                    "content": json.dumps(obj, ensure_ascii=False),
                })
        except json.JSONDecodeError:
            continue

    return prompts


def cn_prompt_miner_save_to_corpus(prompts: List[Dict[str, Any]],
                                     vendor: str,
                                     repo: str,
                                     corpus_root: str = "corpus/official") -> List[str]:
    """CAND-079 (3/3): 计算 corpus/official/{vendor}/{repo}/ 路径 (跟 c3 1:1).

    跟 plan CAND-079 1:1 配对 — 写入本地目录, additive 0 副作用 (跟 CAND-082
    训练数据导出 1:1 配对). Skeleton 0 真写盘 (test mode 默认 in-memory),
    只返回 path list, 让 caller 决定何时落盘 (跟 CAND-082 0 persist 1:1).

    Returns: list of relative path strings (相对 corpus_root).
    """
    logger.debug("CAND-079 cn_prompt_miner_save_to_corpus vendor=%s repo=%s n=%d",
                 vendor, repo, len(prompts))
    saved: List[str] = []
    if not prompts:
        return saved
    base = Path(corpus_root) / vendor / repo
    for idx, prompt in enumerate(prompts):
        if prompt.get("type") == "section":
            # slug: replace / and space 跟 mavis Cherry-pick split bug class 1:1 配对
            # (防止 path injection + 跨平台 path 一致, test normalize 1:1)
            title_slug = prompt.get("title", "untitled").replace("/", "-").replace(" ", "-")[:40]
            filename = f"section-{idx:03d}-{title_slug}.md"
        else:
            filename = f"{prompt.get('type', 'unknown')}-{idx:03d}.md"
        rel_path = str(base / filename)
        saved.append(rel_path)
    return saved


def cn_prompt_miner_official(repos: Optional[List[Dict[str, str]]] = None,
                               corpus_root: str = "corpus/official",
                               max_doc_bytes: int = 1_000_000) -> Dict[str, Any]:
    """CAND-079 combined orchestrator: 跑 3 阶段 (fetch + extract + save paths).

    跟 plan CAND-079 1:1 配对 — Sprint 11 Phase 1 main entry, additive 0 副作用.
    0 真写盘 (跟 CAND-082 0 persist 1:1 配对), 只返回 stats + path list.

    Returns: {"total_repos": int, "total_prompts": int, "by_repo": [...]}
    """
    repos_list = repos if repos is not None else GITHUB_REPOS
    logger.debug("CAND-079 cn_prompt_miner_official n_repos=%d", len(repos_list))
    by_repo: List[Dict[str, Any]] = []
    total_prompts = 0
    for entry in repos_list:
        vendor = entry["vendor"]
        repo = entry["repo"]
        fetched = cn_prompt_miner_fetch_official(repo, max_doc_bytes=max_doc_bytes)
        prompts: List[Dict[str, Any]] = []
        for source in fetched["sources"]:
            if source["ok"]:
                prompts.extend(
                    cn_prompt_miner_extract_prompts(source["content"], source=source["url"])
                )
        saved_paths = cn_prompt_miner_save_to_corpus(prompts, vendor, repo, corpus_root=corpus_root)
        by_repo.append({
            "vendor": vendor,
            "repo": repo,
            "n_prompts": len(prompts),
            "saved_paths": saved_paths,
        })
        total_prompts += len(prompts)
    return {
        "total_repos": len(repos_list),
        "total_prompts": total_prompts,
        "by_repo": by_repo,
    }

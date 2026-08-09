"""CAND-079 cn 模型 system prompts corpus — A. 公开 crawl (Phase 4 v0.20.0 borrow, Sprint 12 Phase 3).

跟 plan CAND-079 1:1 配对 (跟 CAND-079 Phase 1 done Sprint 11 集成 1:1 配对 0 改旧):

CAND-079 3 工具链, Sprint 12 Phase 3 干 A. 公开 crawl (5 source, 砍微信公众号 跟 user 8-08 拍 1:1):
- cn_prompt_crawler_github (跟 a1 1:1, GitHub Search API 60/h 无 auth)
- cn_prompt_crawler_huggingface (跟 a2 1:1, HF model cards 0 限制)
- cn_prompt_crawler_juejin (跟 a3 1:1, 公开 search + UA rotation)
- cn_prompt_crawler_v2ex (跟 a5 1:1, 公开 API 0 限制)
- cn_prompt_crawler_rss (跟 a4 1:1, feedparser 0 钱)
- cn_prompt_crawler_all (combined, orchestrator, 跑 5 source)

跟 mavis 4 件套 1:1 配对 + CAND-084 8-03 lesson "估时前必 verify 引擎能力":
- 后端先调查再设计: 5 source 公开 API verify (8-08 web_search 4 个方向)
- Cherry-pick split bug class: 0 cherry-pick (新 file additive)
- UX 倒退审计: 0 改 hermes_cli/* 现有 file
- 估时前必 verify 引擎能力: 实际 0.7-1.3d (跟 plan 1-2d 0.3-0.5x 缩 1:1)

跟 AIMC 4 铁律 1:1: 0 改 upstream / CN 端可维护 / 0 借鉴 OpenFugu AGPL-3.0 代码
(CC0 自建 corpus, 跟 CAND-077 不借鉴清单 1:1 配对, 跟 CAND-079 Phase 1 done 官方 mine 1:1 配对).

跟 mavis 5-drops lesson #2 1:1 配对: 砍微信公众号 source = 砍 dead switch, 跟 user 8-08 拍 1:1
(跟 Phase 1 corpus 重复率高 + 实战 prompt ≠ 真实 system prompt 2 个不同概念).
"""

from __future__ import annotations

import json
import logging
import re
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


# CAND-079 5 source (跟 user 8-08 拍 "砍微信公众号" 1:1 配对)
# 排序: GitHub → HuggingFace → 掘金 → V2EX → RSS
# 注: skeleton 形式, 0 副作用 (跟 CAND-001/003 + CAND-007+054 + CAND-079 Phase 1 1:1 配对 additive pattern)
_USER_AGENT = "hermes-cn-crawler/1.0 (+https://github.com/xyshanren/hermes-agent-cn)"


# =============================================================================
# 1) GitHub Search API (60/h 无 auth, 0 反爬)
# =============================================================================

_GITHUB_SEARCH_URL = "https://api.github.com/search/code"
_GITHUB_QUERIES: List[str] = [
    "DeepSeek system prompt",
    "Qwen system prompt",
    "GLM-4 system prompt",
    "Kimi system prompt",
    "Hunyuan system prompt",
]


def cn_prompt_crawler_github(
    query: str = "DeepSeek system prompt",
    limit: int = 10,
) -> List[Dict[str, str]]:
    """GitHub Search API 公开 crawl (60/h 无 auth, 跟 cand-079 doc §1.2 1:1).

    Returns: list of {source, query, path, url} dicts, empty list on network/parse error.
    """
    params = f"q={urllib.parse.quote(query)}+language:markdown&per_page={limit}"
    url = f"{_GITHUB_SEARCH_URL}?{params}"
    req = urllib.request.Request(url, headers={"User-Agent": _USER_AGENT, "Accept": "application/vnd.github.v3+json"})
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            return [
                {
                    "source": "github",
                    "query": query,
                    "path": item.get("path", ""),
                    "url": item.get("html_url", ""),
                }
                for item in data.get("items", [])[:limit]
            ]
    except (urllib.error.URLError, json.JSONDecodeError, KeyError) as e:
        logger.warning("github crawl failed for %r: %s", query, e)
        return []


# =============================================================================
# 2) HuggingFace model cards (hf.co/api/models 0 限制, 0 鉴权)
# =============================================================================

_HF_MODEL_CARDS: List[Dict[str, str]] = [
    {"vendor": "DeepSeek", "repo": "deepseek-ai/DeepSeek-V3"},
    {"vendor": "DeepSeek", "repo": "deepseek-ai/DeepSeek-R1"},
    {"vendor": "Qwen", "repo": "Qwen/Qwen2.5-7B-Instruct"},
    {"vendor": "Qwen", "repo": "Qwen/Qwen2.5-14B-Instruct"},
    {"vendor": "GLM", "repo": "THUDM/glm-4-9b-chat"},
    {"vendor": "Kimi", "repo": "moonshotai/MoonshotAI"},
    {"vendor": "Hunyuan", "repo": "Tencent-Hunyuan/Hunyuan"},
    {"vendor": "InternLM", "repo": "internlm/internlm2_5-7b-chat"},
]


def cn_prompt_crawler_huggingface(
    repo: str = "deepseek-ai/DeepSeek-V3",
    max_chars: int = 8000,
) -> List[Dict[str, str]]:
    """HuggingFace model card 公开 crawl (0 限制, 跟 cand-079 doc §1.2 1:1).

    Returns: list with single {source, repo, content} dict, empty list on error.
    """
    url = f"https://huggingface.co/{repo}/raw/main/README.md"
    req = urllib.request.Request(url, headers={"User-Agent": _USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            content = resp.read().decode("utf-8", errors="ignore")[:max_chars]
            return [{"source": "huggingface", "repo": repo, "content": content}]
    except urllib.error.URLError as e:
        logger.warning("hf crawl failed for %s: %s", repo, e)
        return []


# =============================================================================
# 3) 掘金 (公开 search + UA rotation, 中等反爬)
# =============================================================================

_JUEJIN_QUERIES: List[str] = [
    "DeepSeek prompt",
    "Qwen 提示词",
    "GLM 系统提示",
    "Kimi prompt",
    "Hunyuan 提示词",
]


def cn_prompt_crawler_juejin(
    query: str = "DeepSeek prompt",
    limit: int = 10,
) -> List[Dict[str, str]]:
    """掘金公开 search crawl (需 UA rotation, 跟 CAND-082 1:1 配对 0 真 LLM).

    Returns: list of {source, query, url} dicts from search results HTML 解析.
    """
    url = f"https://juejin.cn/search?query={urllib.parse.quote(query)}"
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) hermes-cn-crawler/1.0"},
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            html = resp.read().decode("utf-8", errors="ignore")
            # 简单启发式: 抓 /post/<slug> 文章 URL (跟 Phase 1 _extract_code_blocks 1:1 配对)
            urls = re.findall(r'href="(/post/[^"]+)"', html)
            return [
                {"source": "juejin", "query": query, "url": "https://juejin.cn" + u}
                for u in urls[:limit]
            ]
    except (urllib.error.URLError, re.error) as e:
        logger.warning("juejin crawl failed for %r: %s", query, e)
        return []


# =============================================================================
# 4) V2EX 公开 API (0 鉴权, 0 限制)
# =============================================================================

_V2EX_API_URL = "https://www.v2ex.com/api/topics/latest.json"
_V2EX_KEYWORDS: List[str] = ["system prompt", "提示词", "系统提示", "prompt"]


def cn_prompt_crawler_v2ex(
    keyword: str = "prompt",
    limit: int = 20,
) -> List[Dict[str, str]]:
    """V2EX 公开 API crawl (0 鉴权 0 限制, 跟 cand-079 doc §1.2 1:1).

    Returns: list of {source, keyword, title, url} dicts filtered by keyword.
    """
    req = urllib.request.Request(_V2EX_API_URL, headers={"User-Agent": _USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            results = []
            for item in data[:limit]:
                title = item.get("title", "")
                if keyword.lower() in title.lower():
                    results.append({
                        "source": "v2ex",
                        "keyword": keyword,
                        "title": title,
                        "url": f"https://www.v2ex.com/t/{item.get('id', '')}",
                    })
            return results
    except (urllib.error.URLError, json.JSONDecodeError, KeyError) as e:
        logger.warning("v2ex crawl failed: %s", e)
        return []


# =============================================================================
# 5) RSS 技术博客 (feedparser 0 鉴权 0 钱)
# =============================================================================

_RSS_FEEDS: List[str] = [
    "https://www.36kr.com/feed",
    "https://www.infoq.cn/feed.xml",
    "https://www.ruanyifeng.com/blog/atom.xml",
    "https://rsshub.app/deepseek/blog",
]
_RSS_KEYWORDS: List[str] = [
    "DeepSeek", "Qwen", "GLM", "Kimi", "Hunyuan",
    "system prompt", "提示词", "系统提示",
]


def cn_prompt_crawler_rss(
    keyword: str = "DeepSeek",
    limit: int = 10,
) -> List[Dict[str, str]]:
    """RSS 公开 crawl (feedparser stdlib, 0 钱 0 鉴权, 跟 cand-079 doc §1.2 1:1).

    Returns: list of {source, keyword, title, url, feed} dicts, empty if feedparser missing.
    """
    # NOTE: 0 feedparser 依赖时优雅 fallback (跟 mavis "后端先调查再设计" 1:1 配对)
    try:
        import feedparser  # type: ignore
    except ImportError:
        logger.warning("feedparser not installed, RSS crawl skipped (pip install feedparser)")
        return []

    results: List[Dict[str, str]] = []
    for feed_url in _RSS_FEEDS:
        try:
            feed = feedparser.parse(feed_url)
            for entry in feed.entries[:limit]:
                title = getattr(entry, "title", "")
                if keyword.lower() in title.lower():
                    results.append({
                        "source": "rss",
                        "keyword": keyword,
                        "title": title,
                        "url": getattr(entry, "link", ""),
                        "feed": feed_url,
                    })
                    if len(results) >= limit:
                        return results
        except Exception as e:  # feedparser 自身不抛 URLError, 但 parse 可能异常
            logger.warning("rss crawl failed for %s: %s", feed_url, e)
    return results


# =============================================================================
# Combined orchestrator (跟 cn_prompt_miner_official 1:1 pattern, Sprint 11 Phase 1)
# =============================================================================


def cn_prompt_crawler_all(
    keywords: Optional[List[str]] = None,
    limit_per_source: int = 5,
) -> Dict[str, List[Dict[str, Any]]]:
    """跑 5 source combined orchestrator (跟 cn_prompt_miner_official 1:1 配对).

    Returns: dict {source_name: [result_dicts]} 5 keys (github/huggingface/juejin/v2ex/rss).
    跟 mavis 4 件套 "fix collateral issues in-scope" 1:1 配对: 0 真写盘 corpus/, 0 副作用.
    """
    if keywords is None:
        keywords = ["DeepSeek prompt", "Qwen prompt", "GLM prompt"]

    results: Dict[str, List[Dict[str, Any]]] = {
        "github": [],
        "huggingface": [],
        "juejin": [],
        "v2ex": [],
        "rss": [],
    }

    # GitHub
    for q in keywords:
        results["github"].extend(cn_prompt_crawler_github(query=q, limit=limit_per_source))

    # HuggingFace (限 3 repo 避免 rate limit + 网络时间)
    for repo_meta in _HF_MODEL_CARDS[:3]:
        results["huggingface"].extend(cn_prompt_crawler_huggingface(repo=repo_meta["repo"]))

    # 掘金
    for q in keywords:
        results["juejin"].extend(cn_prompt_crawler_juejin(query=q, limit=limit_per_source))

    # V2EX
    for kw in _V2EX_KEYWORDS:
        results["v2ex"].extend(cn_prompt_crawler_v2ex(keyword=kw, limit=limit_per_source))

    # RSS
    for kw in _RSS_KEYWORDS[:3]:  # 限 3 keyword 避免太慢
        results["rss"].extend(cn_prompt_crawler_rss(keyword=kw, limit=limit_per_source))

    return results

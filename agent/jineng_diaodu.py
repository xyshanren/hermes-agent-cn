"""
技能自动调度引擎 — 根据用户任务上下文自动匹配并激活相关 Skill。

Hermes-Agent-CN 核心组件，消除用户手动指定 Skill 的负担。

匹配策略:
    1. 关键词精确匹配 — 消息文本 × skill SKILL.md trigger_keywords
    2. 上下文语义匹配 — 对话主题 × skill DESCRIPTION.md 域描述
    3. 频率加权 — 高频使用 skill 获得加分
    4. 技能共现 — 历史中经常一起使用的 skill 关联推荐

集成点:
    - run_agent.py → 预处理阶段，注入 matched skills 到 system prompt
    - prompt_builder.py → 加载 matched skills 的 SKILL.md 到 context

使用方式:
    from agent.jineng_diaodu import SkillScheduler
    scheduler = SkillScheduler()
    matched = scheduler.match("帮我写个 Word 文档")
    # ["docx"] — 自动匹配到 Word 处理 skill
"""

from __future__ import annotations

import logging
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

logger = logging.getLogger(__name__)

# Skill 搜索路径
SKILL_SEARCH_PATHS = [
    Path(__file__).resolve().parent.parent / "skills",          # hermes-agent/skills/
    Path.home() / ".hermes" / "skills",                         # ~/.hermes/skills/
]


# -- 数据类型 ----------------------------------------------------------------

@dataclass
class SkillDescriptor:
    """Skill 描述信息，从 SKILL.md 头部 YAML 解析。"""
    name: str
    description: str = ""
    trigger_keywords: List[str] = field(default_factory=list)
    platforms: List[str] = field(default_factory=list)
    path: Path = field(default_factory=Path)
    tier: str = "archived"
    usage_count: int = 0

    @property
    def match_weight(self) -> float:
        """计算匹配权重（基于 tier + usage）。"""
        tier_weight = {"builtin": 1.0, "frequent": 0.8, "archived": 0.3}
        base = tier_weight.get(self.tier, 0.2)
        usage_bonus = min(self.usage_count / 50, 0.3)  # 最多 +0.3
        return base + usage_bonus


@dataclass
class MatchResult:
    """匹配结果。"""
    skill: SkillDescriptor
    score: float                        # 匹配得分 (0-1)
    matched_keywords: List[str] = field(default_factory=list)
    match_type: str = "keyword"         # keyword | semantic | co_occurrence
    auto_activate: bool = True          # 是否自动激活


# -- YAML 解析（轻量，不依赖完整 YAML 库）---------------------------------------

def _parse_skill_frontmatter(filepath: Path) -> Optional[Dict[str, Any]]:
    """解析 SKILL.md 的 YAML frontmatter（轻量正则实现）。

    不依赖 pyyaml，减少依赖负担。
    """
    try:
        text = filepath.read_text(encoding="utf-8")
    except Exception:
        return None

    # 匹配 --- ... --- 块
    match = re.match(r'^---\s*\n(.*?)\n---', text, re.DOTALL)
    if not match:
        return None

    raw = match.group(1)

    result: Dict[str, Any] = {}

    # 简单字段
    for key in ["name", "description"]:
        m = re.search(rf'^{key}:\s*["\']?(.+?)["\']?\s*$', raw, re.MULTILINE)
        if m:
            result[key] = m.group(1).strip()

    # 列表字段 trigger_keywords
    kw_match = re.search(r'^trigger_keywords:\s*\n((?:\s+-\s+.+\n?)*)', raw, re.MULTILINE)
    if kw_match:
        kws = re.findall(r'^\s+-\s*["\']?(.+?)["\']?\s*$', kw_match.group(1), re.MULTILINE)
        result["trigger_keywords"] = [kw.strip().lower() for kw in kws]

    # platforms
    plat_match = re.search(r'^platforms:\s*\n((?:\s+-\s+.+\n?)*)', raw, re.MULTILINE)
    if plat_match:
        plats = re.findall(r'^\s+-\s*["\']?(.+?)["\']?\s*$', plat_match.group(1), re.MULTILINE)
        result["platforms"] = [p.strip() for p in plats]

    return result


# -- 调度器 ------------------------------------------------------------------

class SkillScheduler:
    """技能自动调度引擎。

    根据用户消息自动匹配相关 Skill，返回按相关性排序的匹配列表。

    Args:
        skill_paths: 自定义 skill 搜索路径（可选，追加到默认路径后）。
    """

    def __init__(self, skill_paths: Optional[List[Path]] = None):
        self._search_paths = list(SKILL_SEARCH_PATHS)
        if skill_paths:
            self._search_paths.extend(skill_paths)

        self._skills: Dict[str, SkillDescriptor] = {}
        self._keyword_index: Dict[str, List[str]] = {}  # keyword → [skill_names]
        self._loaded = False

        # 共现矩阵：skill_a × skill_b → 共同使用次数
        self._co_occurrence: Dict[Tuple[str, str], int] = {}

    def _ensure_loaded(self):
        """确保 Skill 索引已构建。"""
        if self._loaded:
            return
        self._build_index()
        self._loaded = True

    def _build_index(self):
        """扫描搜索路径，构建 Skill 索引。"""
        self._skills.clear()
        self._keyword_index.clear()

        # 加载使用频率数据
        usage_data: Dict[str, int] = {}
        tier_data: Dict[str, str] = {}
        try:
            from agent.skill_tier_manager import get_skill_manager
            mgr = get_skill_manager()
            for name, meta in mgr._store.skills.items():
                usage_data[name] = meta.usage_count
                tier_data[name] = meta.tier
        except ImportError:
            pass

        for search_path in self._search_paths:
            if not search_path.exists():
                continue

            for item in search_path.iterdir():
                skill_md = item / "SKILL.md" if item.is_dir() else item

                if not isinstance(skill_md, Path) or not skill_md.name.endswith(".md"):
                    continue

                # 解析 frontmatter
                fm = _parse_skill_frontmatter(skill_md)
                if not fm:
                    # 没有 YAML frontmatter → 用目录名作为 name
                    name = item.name if item.is_dir() else skill_md.stem
                    fm = {"name": name}

                name = fm.get("name", skill_md.stem)
                desc = SkillDescriptor(
                    name=name,
                    description=fm.get("description", ""),
                    trigger_keywords=fm.get("trigger_keywords", []),
                    platforms=fm.get("platforms", []),
                    path=skill_md,
                    tier=tier_data.get(name, "archived"),
                    usage_count=usage_data.get(name, 0),
                )

                self._skills[name] = desc

                # 构建关键词索引
                for kw in desc.trigger_keywords:
                    kw = kw.lower().strip()
                    if kw not in self._keyword_index:
                        self._keyword_index[kw] = []
                    if name not in self._keyword_index[kw]:
                        self._keyword_index[kw].append(name)

        logger.debug("Skill 索引构建完成: %d 个 skill, %d 个关键词",
                     len(self._skills), len(self._keyword_index))

    def reload(self):
        """重新加载索引（当 skill 文件变更时）。"""
        self._loaded = False
        self._build_index()
        self._loaded = True

    # -- 匹配 -----------------------------------------------------------------

    def match(
        self,
        user_message: str,
        context_hints: Optional[List[str]] = None,
        max_results: int = 5,
        min_score: float = 0.1,
    ) -> List[MatchResult]:
        """根据用户消息匹配 Skill。

        Args:
            user_message: 用户消息文本。
            context_hints: 上下文提示（可选，如文件扩展名、当前打开的文件等）。
            max_results: 最大返回结果数。
            min_score: 最低匹配得分阈值。

        Returns:
            按得分降序排列的匹配结果列表。
        """
        self._ensure_loaded()

        text = user_message.lower().strip()
        results: Dict[str, MatchResult] = {}

        # 1. 关键词精确匹配
        self._keyword_match(text, results)

        # 2. 上下文提示匹配
        if context_hints:
            self._context_match(context_hints, results)

        # 3. 模糊匹配（描述相似度）
        self._fuzzy_match(text, results)

        # 过滤低分、排序
        filtered = [r for r in results.values() if r.score >= min_score]
        filtered.sort(key=lambda r: (-r.score, -r.skill.match_weight))

        return filtered[:max_results]

    def _keyword_match(self, text: str, results: Dict[str, MatchResult]):
        """关键词精确匹配。"""
        for keyword, skill_names in self._keyword_index.items():
            if keyword in text:
                for name in skill_names:
                    desc = self._skills.get(name)
                    if not desc:
                        continue
                    score = 0.8 + desc.match_weight * 0.2
                    if name in results:
                        results[name].score = max(results[name].score, score)
                        results[name].matched_keywords.append(keyword)
                    else:
                        results[name] = MatchResult(
                            skill=desc,
                            score=score,
                            matched_keywords=[keyword],
                            match_type="keyword",
                        )

    def _context_match(self, hints: List[str], results: Dict[str, MatchResult]):
        """上下文提示匹配。

        Args:
            hints: 如 [".docx", ".pdf", ".py"] 等文件扩展名。
        """
        # 扩展名 → Skill 映射
        ext_map = {
            ".docx": "docx",
            ".doc": "docx",
            ".pdf": "pdf",
            ".xlsx": "xlsx",
            ".xls": "xlsx",
            ".csv": "xlsx",
            ".pptx": "pptx",
            ".ppt": "pptx",
        }

        for hint in hints:
            hint_lower = hint.lower().strip()
            skill_name = ext_map.get(hint_lower)
            if skill_name and skill_name in self._skills:
                results[skill_name] = MatchResult(
                    skill=self._skills[skill_name],
                    score=0.7,
                    matched_keywords=[f"ext:{hint_lower}"],
                    match_type="context",
                )

    def _fuzzy_match(self, text: str, results: Dict[str, MatchResult]):
        """模糊匹配（基于描述的简单文本相似度）。"""
        for name, desc in self._skills.items():
            if name in results:
                continue  # 已匹配的不重复

            # 简单 Jaccard 相似度
            desc_lower = (desc.description or "").lower()
            if not desc_lower:
                continue

            text_words = set(text.split())
            desc_words = set(desc_lower.split())

            if not text_words or not desc_words:
                continue

            intersection = text_words & desc_words
            union = text_words | desc_words
            score = len(intersection) / len(union) * 0.5  # 模糊匹配权重低

            if score > 0.1:
                results[name] = MatchResult(
                    skill=desc,
                    score=score,
                    matched_keywords=list(intersection),
                    match_type="fuzzy",
                )

    def record_co_occurrence(self, skill_a: str, skill_b: str):
        """记录两个 Skill 的共现关系。"""
        if skill_a == skill_b:
            return
        pair = tuple(sorted([skill_a, skill_b]))
        self._co_occurrence[pair] = self._co_occurrence.get(pair, 0) + 1

    # -- 查询 -----------------------------------------------------------------

    def list_skills(self, tier_filter: Optional[str] = None) -> List[SkillDescriptor]:
        """列出所有已知 Skill。"""
        self._ensure_loaded()
        if tier_filter:
            return [d for d in self._skills.values() if d.tier == tier_filter]
        return list(self._skills.values())

    def get_skill(self, name: str) -> Optional[SkillDescriptor]:
        """获取单个 Skill 描述。"""
        self._ensure_loaded()
        return self._skills.get(name)

    def search_skills(self, query: str, limit: int = 10) -> List[SkillDescriptor]:
        """搜索 Skill（名称或描述包含关键词）。"""
        self._ensure_loaded()
        query_lower = query.lower()
        results = []

        for desc in self._skills.values():
            if query_lower in desc.name.lower() or query_lower in desc.description.lower():
                results.append(desc)

        results.sort(key=lambda d: -d.match_weight)
        return results[:limit]


# -- 全局单例 ----------------------------------------------------------------

_scheduler_instance: Optional[SkillScheduler] = None


def get_scheduler() -> SkillScheduler:
    """获取全局调度器实例。"""
    global _scheduler_instance
    if _scheduler_instance is None:
        _scheduler_instance = SkillScheduler()
    return _scheduler_instance


def auto_match_skills(user_message: str, context_hints: Optional[List[str]] = None) -> List[str]:
    """便捷函数：自动匹配 Skill 并返回名称列表。"""
    scheduler = get_scheduler()
    results = scheduler.match(user_message, context_hints)
    return [r.skill.name for r in results if r.auto_activate]

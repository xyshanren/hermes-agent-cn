"""
渐进式 Skill 三层管理 — builtin / frequent / archived 自动升降级。

Hermes-Agent-CN 核心组件，根据使用频率自动分级，节省 context token。

三层定义:
    builtin (内置)  — 5-8 个核心 skill，始终注入 system prompt
    frequent (常用) — ≤10 个，自动匹配后注入，≥3次/周升入，7天未用降出
    archived (归档) — 不限量，0 context token，按需手动唤醒

升降级规则:
    晋升: archived → frequent    条件: 7 天内使用 ≥ 3 次
    降级: frequent → archived    条件: 连续 7 天未使用
    保级: frequent → frequent    条件: 使用频率正常

元数据存储: ~/.hermes/skills_meta.json

使用方式:
    from agent.skill_tier_manager import SkillTierManager
    mgr = SkillTierManager()
    mgr.record_usage("xbrowser")         # 记录使用
    tier = mgr.get_tier("weather")        # 查询层级
    mgr.evaluate_promotions()             # 执行升降级
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# -- 常量 --------------------------------------------------------------------

META_FILE = Path.home() / ".hermes" / "skills_meta.json"

# 升降级阈值
PROMOTION_THRESHOLD = 3      # 7 天内使用 ≥ 3 次 → 晋升 frequent
DEMOTION_THRESHOLD_DAYS = 7  # 连续 N 天未使用 → 降级 archived
COLD_ARCHIVE_DAYS = 30       # N 天未使用 → 冷归档
MAX_FREQUENT = 10            # frequent 层级最大 skill 数
MAX_BUILTIN = 8              # builtin 层级最大 skill 数

# 内置 Skill 列表（始终生效）
DEFAULT_BUILTIN_SKILLS = [
    "peizhi-moxing",         # 模型配置
    "ceshi-lianjie",         # 连通性测试
    "model-download",        # 模型下载
]

# 源码中始终内置的 Skill（上游提供）
UPSTREAM_BUILTIN_SKILLS = [
    "xbrowser",              # 浏览器自动化
    "weather",               # 天气查询
    "pdf",                   # PDF 处理
    "docx",                  # Word 处理
    "xlsx",                  # Excel 处理
]


# -- 数据类型 ----------------------------------------------------------------

class SkillTier(Enum):
    """Skill 层级。"""
    BUILTIN = "builtin"     # 内置，始终加载
    FREQUENT = "frequent"   # 常用，自动匹配加载
    ARCHIVED = "archived"   # 归档，按需唤醒


@dataclass
class SkillMeta:
    """单个 Skill 的元数据。"""

    name: str                           # Skill 名称
    tier: str = "archived"              # builtin | frequent | archived
    usage_count: int = 0                # 总使用次数
    last_used: str = ""                 # 最后使用时间 (ISO)
    weekly_usage: List[int] = field(default_factory=lambda: [0, 0, 0, 0])  # 最近 4 周每周使用次数
    promoted_at: str = ""               # 晋升时间
    archived_at: str = ""               # 归档时间
    pinned: bool = False                # 是否锁定（锁定后不自动降级）
    description: str = ""               # 描述

    def _ensure_weekly(self):
        """确保 weekly_usage 长度为 4。"""
        while len(self.weekly_usage) < 4:
            self.weekly_usage.insert(0, 0)
        self.weekly_usage = self.weekly_usage[-4:]

    def record_use(self):
        """记录一次使用。"""
        self.usage_count += 1
        self.last_used = datetime.now().isoformat()
        self._ensure_weekly()
        self.weekly_usage[-1] += 1

    def should_promote(self) -> bool:
        """检查是否满足晋升条件（7 天内使用 ≥ 3 次）。"""
        if self.tier != SkillTier.ARCHIVED.value:
            return False
        self._ensure_weekly()
        return self.weekly_usage[-1] >= PROMOTION_THRESHOLD

    def should_demote(self) -> bool:
        """检查是否满足降级条件（连续 7 天未使用）。"""
        if self.tier != SkillTier.FREQUENT.value:
            return False
        if self.pinned:
            return False
        if not self.last_used:
            return False
        try:
            last = datetime.fromisoformat(self.last_used)
            return (datetime.now() - last).days >= DEMOTION_THRESHOLD_DAYS
        except (ValueError, TypeError):
            return False

    def should_cold_archive(self) -> bool:
        """检查是否应冷归档（30 天未使用）。"""
        if not self.last_used:
            return False
        try:
            last = datetime.fromisoformat(self.last_used)
            return (datetime.now() - last).days >= COLD_ARCHIVE_DAYS
        except (ValueError, TypeError):
            return False


@dataclass
class SkillsMetaStore:
    """全局 Skill 元数据存储。"""

    skills: Dict[str, SkillMeta] = field(default_factory=dict)
    tier_limits: Dict[str, int] = field(default_factory=lambda: {
        "builtin": MAX_BUILTIN,
        "frequent": MAX_FREQUENT,
    })
    last_evaluation: str = ""


# -- 管理器 ------------------------------------------------------------------

class SkillTierManager:
    """Skill 三层分级管理器。

    负责元数据读写、使用记录、升降级评估。

    Args:
        meta_path: 元数据文件路径（默认 ~/.hermes/skills_meta.json）。
    """

    def __init__(self, meta_path: Optional[Path] = None):
        self.meta_path = meta_path or META_FILE
        self._store: SkillsMetaStore = SkillsMetaStore()
        self._loaded = False

    def _ensure_loaded(self):
        """确保元数据已加载。"""
        if self._loaded:
            return
        self.load()
        self._loaded = True

    def load(self) -> SkillsMetaStore:
        """从磁盘加载元数据。"""
        try:
            if self.meta_path.exists():
                raw = json.loads(self.meta_path.read_text(encoding="utf-8"))
                skills = {}
                for name, data in raw.get("skills", {}).items():
                    skills[name] = SkillMeta(
                        name=name,
                        tier=data.get("tier", "archived"),
                        usage_count=data.get("usage_count", 0),
                        last_used=data.get("last_used", ""),
                        weekly_usage=data.get("weekly_usage", [0, 0, 0, 0]),
                        promoted_at=data.get("promoted_at", ""),
                        archived_at=data.get("archived_at", ""),
                        pinned=data.get("pinned", False),
                        description=data.get("description", ""),
                    )
                self._store = SkillsMetaStore(
                    skills=skills,
                    tier_limits=raw.get("tier_limits", {"builtin": MAX_BUILTIN, "frequent": MAX_FREQUENT}),
                    last_evaluation=raw.get("last_evaluation", ""),
                )
            else:
                self._init_defaults()
        except Exception as e:
            logger.warning("加载 skills_meta.json 失败: %s，使用默认值", e)
            self._init_defaults()

        self._loaded = True
        return self._store

    def _init_defaults(self):
        """初始化默认内置 Skill 元数据。"""
        self._store = SkillsMetaStore()
        now = datetime.now().isoformat()

        for skill_name in UPSTREAM_BUILTIN_SKILLS + DEFAULT_BUILTIN_SKILLS:
            self._store.skills[skill_name] = SkillMeta(
                name=skill_name,
                tier=SkillTier.BUILTIN.value,
                usage_count=0,
                last_used="",
                weekly_usage=[0, 0, 0, 0],
                description="",
            )

    def save(self):
        """保存元数据到磁盘。"""
        self._ensure_loaded()
        try:
            self.meta_path.parent.mkdir(parents=True, exist_ok=True)
            data = {
                "skills": {
                    name: asdict(meta)
                    for name, meta in self._store.skills.items()
                },
                "tier_limits": self._store.tier_limits,
                "last_evaluation": self._store.last_evaluation,
            }
            self.meta_path.write_text(
                json.dumps(data, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        except Exception as e:
            logger.warning("保存 skills_meta.json 失败: %s", e)

    # -- 查询 -----------------------------------------------------------------

    def get_skill(self, name: str) -> Optional[SkillMeta]:
        """获取单个 Skill 的元数据。"""
        self._ensure_loaded()
        return self._store.skills.get(name)

    def get_tier(self, name: str) -> SkillTier:
        """获取 Skill 当前层级。"""
        meta = self.get_skill(name)
        if meta:
            return SkillTier(meta.tier)
        return SkillTier.ARCHIVED

    def get_skills_by_tier(self, tier: SkillTier) -> List[str]:
        """获取指定层级的所有 Skill 名称（按使用频率排序）。"""
        self._ensure_loaded()
        result = [
            (name, meta.usage_count)
            for name, meta in self._store.skills.items()
            if meta.tier == tier.value
        ]
        result.sort(key=lambda x: -x[1])
        return [name for name, _ in result]

    def get_active_skills(self) -> List[str]:
        """获取应注入 context 的 Skill 列表（builtin + 部分 frequent）。"""
        builtin = self.get_skills_by_tier(SkillTier.BUILTIN)
        frequent = self.get_skills_by_tier(SkillTier.FREQUENT)

        # frequent 最多取 MAX_FREQUENT 个（按使用次数）
        return builtin + frequent[:MAX_FREQUENT]

    # -- 操作 -----------------------------------------------------------------

    def record_usage(self, skill_name: str):
        """记录一次 Skill 使用。

        Args:
            skill_name: Skill 名称。
        """
        self._ensure_loaded()
        skill_name = skill_name.strip().lower()

        if skill_name not in self._store.skills:
            # 新 Skill → 归档
            self._store.skills[skill_name] = SkillMeta(
                name=skill_name,
                tier=SkillTier.ARCHIVED.value,
            )

        meta = self._store.skills[skill_name]
        meta.record_use()

        # 实时检查晋升条件
        if meta.should_promote():
            self._promote(skill_name)

        self.save()

    def _promote(self, skill_name: str):
        """将一个 Skill 晋升为 frequent。"""
        meta = self._store.skills.get(skill_name)
        if not meta:
            return

        frequent = self.get_skills_by_tier(SkillTier.FREQUENT)
        if len(frequent) >= MAX_FREQUENT:
            # frequent 已满 → 降级使用最少的
            least_used = None
            least_count = float("inf")
            for name in frequent:
                fm = self._store.skills.get(name)
                if fm and not fm.pinned and fm.usage_count < least_count:
                    least_used = name
                    least_count = fm.usage_count

            if least_used:
                self._demote(least_used)

        meta.tier = SkillTier.FREQUENT.value
        meta.promoted_at = datetime.now().isoformat()
        logger.info("Skill 晋升: %s → frequent", skill_name)

    def _demote(self, skill_name: str):
        """将一个 Skill 降级为 archived。"""
        meta = self._store.skills.get(skill_name)
        if not meta or meta.pinned:
            return

        meta.tier = SkillTier.ARCHIVED.value
        meta.archived_at = datetime.now().isoformat()
        meta.weekly_usage = [0, 0, 0, 0]  # 重置周频率
        logger.info("Skill 降级: %s → archived", skill_name)

    def pin_skill(self, skill_name: str):
        """锁定一个 Skill（不自动降级）。"""
        meta = self.get_skill(skill_name)
        if meta:
            meta.pinned = True
            self.save()

    def unpin_skill(self, skill_name: str):
        """取消锁定。"""
        meta = self.get_skill(skill_name)
        if meta:
            meta.pinned = False
            self.save()

    def set_builtin(self, skill_name: str):
        """手动将一个 Skill 设为 builtin。"""
        if skill_name not in self._store.skills:
            return
        builtin_count = len(self.get_skills_by_tier(SkillTier.BUILTIN))
        if builtin_count >= MAX_BUILTIN:
            logger.warning("builtin 已满 (%d), 无法添加 %s", MAX_BUILTIN, skill_name)
            return
        self._store.skills[skill_name].tier = SkillTier.BUILTIN.value
        self.save()

    # -- 批量评估 -------------------------------------------------------------

    def evaluate_promotions(self):
        """批量执行升降级评估（建议 cron 每日触发）。"""
        self._ensure_loaded()

        promoted = []
        demoted = []
        cold = []

        for name, meta in list(self._store.skills.items()):
            if meta.should_promote():
                self._promote(name)
                promoted.append(name)

            if meta.should_demote():
                self._demote(name)
                demoted.append(name)

            if meta.should_cold_archive():
                cold.append(name)

        if promoted or demoted:
            self._store.last_evaluation = datetime.now().isoformat()
            self.save()

        logger.info(
            "Skill 升降级评估完成: 晋升 %d, 降级 %d, 冷归档建议 %d",
            len(promoted), len(demoted), len(cold),
        )

        return {"promoted": promoted, "demoted": demoted, "cold_archive": cold}

    # -- 统计报告 -------------------------------------------------------------

    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息。"""
        self._ensure_loaded()
        tiers = {"builtin": 0, "frequent": 0, "archived": 0}
        total_usage = 0
        for meta in self._store.skills.values():
            tiers[meta.tier] = tiers.get(meta.tier, 0) + 1
            total_usage += meta.usage_count

        # 估算 token 节省
        active_count = tiers["builtin"] + min(tiers["frequent"], MAX_FREQUENT)
        total_count = sum(tiers.values())
        token_saved_pct = round((1 - active_count / max(total_count, 1)) * 100)

        return {
            "total_skills": total_count,
            "by_tier": tiers,
            "total_usage": total_usage,
            "active_skills": active_count,
            "token_saved_pct": token_saved_pct,
            "last_evaluation": self._store.last_evaluation,
        }

    def print_stats(self) -> str:
        """生成中文统计报告。"""
        stats = self.get_stats()
        lines = [
            "=== Skill 分层统计 ===",
            f"总数: {stats['total_skills']} 个",
            f"├─ 内置:    {stats['by_tier']['builtin']} 个 (始终加载)",
            f"├─ 常用:    {stats['by_tier']['frequent']} 个 (自动匹配)",
            f"└─ 归档:    {stats['by_tier']['archived']} 个 (按需唤醒)",
            f"活跃: {stats['active_skills']}/{stats['total_skills']}",
            f"总使用次数: {stats['total_usage']}",
            f"Token 节省: ~{stats['token_saved_pct']}%",
        ]
        if stats["last_evaluation"]:
            lines.append(f"上次评估: {stats['last_evaluation']}")
        return "\n".join(lines)


# -- 全局单例 ----------------------------------------------------------------

_mgr_instance: Optional[SkillTierManager] = None


def get_skill_manager() -> SkillTierManager:
    """获取全局 Skill 管理实例。"""
    global _mgr_instance
    if _mgr_instance is None:
        _mgr_instance = SkillTierManager()
    return _mgr_instance


def record_skill_usage(skill_name: str):
    """便捷函数：记录一次 Skill 使用。"""
    get_skill_manager().record_usage(skill_name)

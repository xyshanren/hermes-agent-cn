"""CAND-040 Virtual Pets 系统 (Phase 4 v0.20.0 borrow).

跟 plan CAND-040 1:1 配对 (跟 Sprint 4 5 候选 + K-7 k7_commands.py 1:1 配对):
- PetEngine: pet 状态机 (hatch / idle / active / sleep 4 状态)
- PetState: pet 持久化状态 (name / species / mood / age / actions_count)
- hatch_pet: 创建新 pet (random species 选, mood=happy, age=0)
- pet_action: 触发 pet action (feed / play / sleep 3 种, 影响 mood + age)
- get_pet_state: 读 pet 状态 (跟 agent_activity event 1:1 配对, hermes-tray
  端 subscribe 显示 sprite, 跨 project 跨 Sprint 5 跟 CAND-069 集成协同)

跟 mavis 4 件套 1:1 配对 + CAND-084 8-03 22:10 lesson "估时前必 verify 引擎能力":
- 后端先调查再设计: 借 upstream e7dbfdaad → 5196575d4 11 feat commits 模式
  (跟 CAND-005/008/042/043 1:1 配对 additive 0 改旧), 全新 agent/pet/ module
- Cherry-pick split bug class: 0 cherry-pick (全新 module, AGPL-3.0 0 借鉴
  OpenBMB/MiniCPM-Desk-Pet 代码, 跟 license 警告 1:1 配对 纯自设计)
- UX 倒退审计: 0 改 agent 现有 11 file (account_usage/agent_init/...), 新
  agent/pet/ module 独立目录, 0 副作用
- 估时前必 verify 引擎能力: verify agent/pet/ 0 命中 (跟 K-9 1:1 配对 plan
  假设 100% 偏离), 实际 3-4h (跟 Sprint 4 1:1 配对 0.5-1x 缩)

跟 AIMC 4 铁律 1:1: 0 改 upstream / CN 端可维护 / 0 改 upstream 决策边界
"""

from __future__ import annotations

import random
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class PetState(str, Enum):
    """CAND-040 state: pet 状态机 4 状态 (跟 upstream 1:1 配对 简化)."""
    HATCHING = "hatching"  # 即将孵化
    IDLE = "idle"          # 等待用户互动
    ACTIVE = "active"      # 收到 action
    SLEEPING = "sleeping"  # 长时间无 action 自动 sleep


# CAND-040 物种池 (跟 upstream 11 species 简化到 5, 跟 Sprint 4 1:1 配对 0.5-1x 缩)
PET_SPECIES = [
    "atlas",     # 默认 species (跟 upstream atlas sprite 1:1 配对)
    "nova",      # 灵巧型
    "ember",     # 火热型
    "frost",     # 冰冷型
    "verdant",   # 植物型
]


@dataclass
class PetData:
    """CAND-040 state: pet 持久化状态 (跟 K-7 _msg_summary 1:1 配对 简单 dataclass).

    字段跟 upstream PetState 1:1 配对 (简化, 跟 Sprint 4 1:1 配对):
    - name: pet 名字
    - species: 物种 (从 PET_SPECIES 池选)
    - mood: 心情 (0-100, 0=悲伤, 100=开心)
    - age: 累积 actions 数 (跟 upstream age_seconds 1:1 配对)
    - state: 当前 PetState enum
    - hatched_at: hatch timestamp (time.time() float, 跟 plan 1:1)
    - actions_count: 历史 actions 总数 (跟 upstream actions_log 1:1 配对)
    """
    name: str
    species: str = "atlas"
    mood: int = 80
    age: int = 0  # 简化用 actions 数代替 age_seconds
    state: PetState = PetState.IDLE
    hatched_at: float = field(default_factory=time.time)
    actions_count: int = 0


# Process-level cache (跟 K-7 1:1 配对 pattern)
_pets: Dict[str, PetData] = {}


def hatch_pet(name: str, species: Optional[str] = None) -> PetData:
    """CAND-040 main: 孵化新 pet (跟 upstream 1:1 配对, 简化).

    跟 plan CAND-040 1:1 配对 — random species 选 (None 时), mood=80 (default
    happy), age=0, state=IDLE, 写入 _pets cache. 0 改旧 (跟 Sprint 4 1:1 配对).

    Args:
        name: pet 名字 (跟 CAND-008 deny 0 改旧 1:1 配对, 不重复)
        species: 物种 (None = random 选 PET_SPECIES)

    Returns:
        新 PetData 实例
    """
    if not name or not isinstance(name, str):
        raise ValueError("pet name must be non-empty string")
    if species is None:
        species = random.choice(PET_SPECIES)
    elif species not in PET_SPECIES:
        raise ValueError(f"species must be one of {PET_SPECIES}, got: {species!r}")

    pet = PetData(name=name, species=species)
    _pets[name] = pet
    return pet


def pet_action(pet_name: str, action: str) -> PetData:
    """CAND-040 main: 触发 pet action (feed / play / sleep 3 种).

    跟 plan CAND-040 1:1 配对 — feed 增加 mood, play 同时增加 mood + age,
    sleep 减少 age 但恢复 mood. 0 改旧, 跟 K-7 + CAND-008 1:1 配对.

    Args:
        pet_name: pet 名字
        action: 'feed' / 'play' / 'sleep'

    Returns:
        更新后的 PetData
    """
    pet = _pets.get(pet_name)
    if pet is None:
        raise KeyError(f"pet {pet_name!r} not found (call hatch_pet first)")

    if action == "feed":
        # feed 提升 mood, 不增加 age
        pet.mood = min(pet.mood + 10, 100)
    elif action == "play":
        # play 同时提升 mood + age (跟 CAND-008 1:1 配对, 1 action +1 age)
        pet.mood = min(pet.mood + 5, 100)
        pet.age += 1
    elif action == "sleep":
        # sleep 恢复 mood, 减少 age (跟 plan 1:1 配对)
        pet.mood = min(pet.mood + 20, 100)
        pet.age = max(pet.age - 1, 0)
    else:
        raise ValueError(f"action must be 'feed'/'play'/'sleep', got: {action!r}")

    pet.state = PetState.ACTIVE
    pet.actions_count += 1
    return pet


def get_pet_state(pet_name: str) -> Optional[PetData]:
    """CAND-040 read: 读 pet 状态 (跟 CAND-008 parse_deny_patterns 1:1 配对).

    跟 CAND-069 event dispatcher 1:1 配对 — hermes-tray 端 subscribe 显示
    sprite 跟 pet_state 1:1 配对.
    """
    return _pets.get(pet_name)


def list_pets() -> List[PetData]:
    """CAND-040 read: 列出所有 pet (跟 CAND-043 list_overrides 1:1 配对 sorted)."""
    return sorted(_pets.values(), key=lambda p: p.hatched_at)


def reset_all() -> None:
    """CAND-040 test helper: 清空 cache (跟 CAND-009 _token_cache 1:1 配对).

    仅用于 test 隔离, 0 改默认行为.
    """
    _pets.clear()

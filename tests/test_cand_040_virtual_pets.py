"""Tests for CAND-040 (Sprint 5): Virtual Pets 系统.

跟 plan CAND-040 1:1 配对 (跟 Sprint 4 5 候选 + K-7 k7_commands.py 1:1 配对):
- 新 agent/pet/ module (跟 Sprint 4 1:1 配对 0 改旧 pattern, 全新 module)
- PetData / PetState / hatch_pet / pet_action / get_pet_state / list_pets 6 functions
- 0 改 agent 现有 11 file (跟 UX 倒退审计 1:1)
- AGPL-3.0 0 借鉴 OpenBMB 代码 (跟 license 警告 1:1 配对 纯自设计)
- 5 test (2 静态 + 3 live, 跟 CAND-042 1:1 配对 4-5 test)
"""

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent


# ---------- CAND-040 main change: 静态 source check ----------


def test_pet_module_exists():
    """CAND-040 main file: agent/pet/__init__.py 存在 (跟 K-7 k7_commands.py 1:1 配对)."""
    p = REPO / "agent" / "pet" / "__init__.py"
    assert p.exists(), f"{p} missing (CAND-040 main file)"
    src = p.read_text(encoding="utf-8")
    for fn in ("hatch_pet", "pet_action", "get_pet_state", "list_pets", "reset_all"):
        assert f"def {fn}" in src, f"function {fn} missing in agent/pet/__init__.py"


def test_agent_existing_files_unchanged():
    """CAND-040 0 改 agent 现有 11 file (跟 Sprint 4 1:1 配对 UX 倒退审计, 全新 module)."""
    # 验证 4 个核心 agent file 0 改 (跟 Sprint 4 1:1 配对 0 改 抽样检查)
    for fname in ("account_usage.py", "agent_init.py", "agent_runtime_helpers.py",
                 "auxiliary_client.py"):
        p = REPO / "agent" / fname
        assert p.exists(), f"{p} missing (existing agent file)"
        src = p.read_text(encoding="utf-8")
        # 0 pet 引用 (verify CAND-040 0 改现有 file 主体)
        assert "from agent.pet" not in src and "import pet" not in src.lower(), (
            f"{fname} 0 改 0 失, CAND-040 不应 import pet module"
        )


# ---------- CAND-040 live integration: 跟 plan 1:1 配对 ----------


def test_hatch_pet_live():
    """Live: hatch_pet 创建新 pet (default mood=80, age=0, state=IDLE, species 5 池)."""
    sys.path.insert(0, str(REPO))
    from agent.pet import hatch_pet, list_pets, reset_all, PET_SPECIES

    # 0 副作用: 清 cache (跟 CAND-009 _token_cache 1:1 配对)
    reset_all()

    # 1. random species 选
    pet = hatch_pet("atlas-pet")
    assert pet.name == "atlas-pet"
    assert pet.species in PET_SPECIES, f"species 应在 5 池, got: {pet.species!r}"
    assert pet.mood == 80, f"default mood 应 80, got: {pet.mood}"
    assert pet.age == 0
    assert pet.actions_count == 0
    assert pet.hatched_at > 0

    # 2. 指定 species
    pet2 = hatch_pet("nova-pet", species="nova")
    assert pet2.species == "nova"

    # 3. 错误: invalid species
    try:
        hatch_pet("bad-pet", species="unknown")
        assert False, "应 raise ValueError"
    except ValueError:
        pass

    # 4. 错误: empty name
    try:
        hatch_pet("")
        assert False, "应 raise ValueError"
    except ValueError:
        pass

    # 5. list_pets 返 sorted by hatched_at
    pets = list_pets()
    assert len(pets) == 2
    assert pets[0].hatched_at <= pets[1].hatched_at


def test_pet_action_live():
    """Live: pet_action feed/play/sleep 3 种, 影响 mood + age (跟 plan 1:1 配对)."""
    sys.path.insert(0, str(REPO))
    from agent.pet import hatch_pet, pet_action, reset_all

    reset_all()
    pet = hatch_pet("action-test", species="atlas")
    initial_mood = pet.mood  # 80
    initial_age = pet.age  # 0

    # 1. feed 提升 mood +10, age 0 变
    pet_action("action-test", "feed")
    assert pet.mood == initial_mood + 10, f"feed +10 mood, got: {pet.mood}"
    assert pet.age == initial_age, f"feed 不应改 age, got: {pet.age}"
    assert pet.state.value == "active"
    assert pet.actions_count == 1

    # 2. play 提升 mood +5 + age +1
    pet_action("action-test", "play")
    assert pet.mood == initial_mood + 15, f"feed+play 应 +15 mood, got: {pet.mood}"
    assert pet.age == 1, f"play 应 +1 age, got: {pet.age}"
    assert pet.actions_count == 2

    # 3. sleep 提升 mood +20 (cap 100) + age -1
    pet_action("action-test", "sleep")
    # mood 累加 80 + 10 + 5 + 20 = 115, cap 100
    assert pet.mood == 100, f"mood 应 cap 100 (跟 CAND-008 1:1 配对), got: {pet.mood}"
    assert pet.age == 0, f"sleep 应 -1 age (但 minimum 0), got: {pet.age}"
    assert pet.actions_count == 3

    # 4. error: pet 0 存在
    try:
        pet_action("nonexistent", "feed")
        assert False, "应 raise KeyError"
    except KeyError:
        pass

    # 5. error: invalid action
    try:
        pet_action("action-test", "fly")
        assert False, "应 raise ValueError"
    except ValueError:
        pass

    # 6. mood 上限 100 (跟 plan 1:1 配对)
    for _ in range(5):
        pet_action("action-test", "feed")
    assert pet.mood <= 100, f"mood 应 <= 100, got: {pet.mood}"


def test_get_pet_state_live():
    """Live: get_pet_state 返 PetData 或 None (跟 CAND-008 parse_deny 1:1 配对)."""
    sys.path.insert(0, str(REPO))
    from agent.pet import hatch_pet, get_pet_state, pet_action, reset_all

    reset_all()

    # 1. 0 hatch → 0 pet, get_pet_state 应 None
    assert get_pet_state("nonexistent") is None

    # 2. hatch + get → PetData
    hatch_pet("get-test")
    pet = get_pet_state("get-test")
    assert pet is not None
    assert pet.name == "get-test"
    assert pet.mood == 80

    # 3. action 后 get → state 反映
    pet_action("get-test", "play")
    pet_after = get_pet_state("get-test")
    assert pet_after.age == 1
    assert pet_after.state.value == "active"

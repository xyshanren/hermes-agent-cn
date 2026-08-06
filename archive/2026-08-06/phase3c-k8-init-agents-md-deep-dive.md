# Phase 3c Deep Dive — K-8 `/init` 自动生成 AGENTS.md (CN 自设计, 跟 P0-3/P0-4 同模式)

> **K-X**: K-8
> **调研期**: 2026-08-06
> **Axiom**: 1 事前设计 (跟 K-1~K-5 1:1 配对, 补 K-1~K-5 axiom 1 gap)
> **决策**: ✅ Option A (user 拍 2026-08-06): CN 自设计 /init 自动生成 AGENTS.md
> **关联**: `phase1-sample-summary.md` §2.3, `phase2-filter-borrow.md` §5 [K-8], `phase4-master-index.md` (待写)
> **mavis 4 lesson 1:1 复用**: 后端先调查再设计 (实施前 grep 现有 design context 文档) / UX 倒退审计 (跟现有 AGENTS.md 共存 check) / 估时前必 verify (phase 1 verify 完) / Cherry-pick split bug class (0 cherry-pick 0 split bug 风险)

---

## 1. 4 必填字段 (跟 K-1~K-5 1:1 配对)

### 1.1 Source

- **Upstream**: 0 1:1 配对 (跟 phase 1 doc §2.3 verify 1:1)
- **CN 端参考**:
  - `33513991b` `fix(agent): never load the install-tree AGENTS.md as project context` (反向: 修补加载逻辑)
  - `2b285f50b` `docs(agents): add Design Philosophy + Contribution Rubric to AGENTS.md` (借模板段: Design Philosophy + Contribution Rubric)
  - `301709544` `docs: add platform support tiers to AGENTS.md` (借模板段: platform support tiers)
- **Pattern 参考**: P0-3 middleware + P0-4 message_timestamps (CANDIDATES.md line 19)

### 1.2 Axiom match

**1 事前设计 (strongest)** — 在 agent 启动前自动生成项目级 `AGENTS.md` design context. 跟 K-1~K-5 0 axiom 1 entry 1:1 配对, **补 gap**.

### 1.3 Cn state

- ❌ `/init` command 0 命中
- ✅ `AGENTS.md` 已存在 (69825 byte, 手工维护)
- ✅ `hermes-already-has-routines.md` 已存在 (CN 端 design context 文档)
- 0 自动生成机制 (grep `init` / `generate` / `scaffold` 在 `hermes_cli/main.py` 0 命中)

### 1.4 Port plan

**1-2d, 1 commit, 3-4 文件改动**:

| File | 改动 | LOC |
|------|------|-----|
| `hermes_cli/init_cmd.py` | 新 file: scanner + template renderer | +200 |
| `hermes_cli/main.py` | slash command 注册 `/init` | +10 |
| `hermes_cli/templates/agents_md.tmpl` | 新 file: AGENTS.md 模板 | +80 |
| `tests/hermes_cli/test_init_cmd.py` | 新 test | +120 |

**实施步骤** (CN 自设计 4 步, 跟 mavis 后端先调查再设计 1:1):

1. **Phase 0 实施前 grep** (跟 mavis 4 lesson 1:1):
   - `grep -rn 'init\|generate\|scaffold' hermes_cli/main.py` (0 命中 = 0 冲突)
   - `grep -rn 'AGENTS.md' hermes_cli/` (确认 AGENTS.md 处理逻辑)
   - 读 `hermes-already-has-routines.md` (CN 端 design context 文档)
2. **`hermes_cli/init_cmd.py` 写**: 4 步 (a) 扫描 cwd project marker (pyproject.toml / package.json / Cargo.toml / go.mod / setup.py) → (b) 提取 language / framework / entry point / test framework / 关键路径 → (c) 模板渲染 AGENTS.md (5 段: project name / structure / dev setup / test cmd / 关键路径) → (d) 跟现有 `AGENTS.md` 存在性 check (已存在 → 不覆盖 + 提示 user `--force`)
3. **`hermes_cli/main.py` 改**: 注册 `/init` slash command
4. **`hermes_cli/templates/agents_md.tmpl` 写**: AGENTS.md 模板 (借 upstream 2b285f50b Design Philosophy 段)
5. **Test 加**: 5-8 test (project marker scan / template render / existing AGENTS.md check / --force 覆盖)
6. **UX 倒退审计**: 现有 AGENTS.md 共存 check, 0 覆盖既有 content

---

## 2. 估时 / 风险 / 价值 (跟 K-1~K-5 1:1 配对)

| 维度 | K-8 值 | 跟 K-1~K-5 1:1 配对 |
|------|--------|---------------------|
| 估时 | 1-2d | 跟 K-1 1-2d 同 (manual port) |
| 风险 | 🟡 中 | 跟 K-1 同风险 (新功能, 模板设计 + 共存 check) |
| 价值 | 🟢 高 | 跟 K-1 🟢 高同价值 (跟 K-1~K-5 0 axiom 1 entry 1:1 配对, 补 gap) |

---

## 3. 跨 project reference (跟 mavis 4 件套 1:1 配对)

- **mavis 后端先调查再设计**: 实施前 grep 现有 design context 文档 (跟 mavis 4 lesson 1:1)
- **mavis UX 倒退审计**: 跟现有 AGENTS.md 共存 check, 0 覆盖既有 content
- **mavis Cherry-pick split bug class**: 0 cherry-pick 0 split bug 风险
- **mavis 估时前必 verify**: phase 1 verify 完

**跨 project reference (跟 K-1~K-5 1:1 配对)**:

- 跟 mavis 4 件套 (Constitution + critic + Reflexion 池 + compaction) 跟 upstream /learn + /journey 跟 CAND-080/081/082 同构 — K-8 `/init` 是**事前设计 + 闭环反馈** 双向 (Axiom 1 + Axiom 3 跨维度), 跟 K-5 /learn + /journey 闭环 + K-1 completion contracts 事前设计同源

---

## 4. 备注 (跟 K-1~K-5 1:1 配对)

- ⚠️ 跟 P0-3/P0-4 "参考 upstream 思路 CN 自行实现" 同模式
- 借 upstream `2b285f50b` Design Philosophy 模板段, CN 加 init dispatcher
- 跟 mavis 协作风格 1:1: "yes we can do it cheaply + 1 sketch" (跟 K-6 1:1 配对, K-6/K-8 都是 CN 自设计 entry)

---

**Phase 3c 完成** — K-8 deep dive 4 必填字段 + 估时/风险/价值 + 跨 project reference + 备注 1:1 落盘.

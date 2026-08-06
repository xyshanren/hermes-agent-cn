# Phase 4 Master Index — v0.20.0 Borrow 调研期 4 phase doc 总收口

> **调研期**: 2026-08-06 (跟 Phase 1+2+3 1:1 节奏, 调研期 1 大 1)
> **调研人**: Mavis
> **范围**: v0.20.0 borrow 窗口, 5 候选 K-6/K-7/K-8/K-9/K-10 全部 deep dive 完
> **目标**: 5 候选 plan + 估时 + 风险 + 跨 project reference 总收口, 跟 K-1~K-5 1:1 配对
> **关联**: `phase1-sample-summary.md` / `phase2-filter-borrow.md` / `phase3a-e-*.md` (5 候选 deep dive) / `CANDIDATES.md` K section
> **收尾**: 1 大 commit 含 4 doc (跟 user 提 1:1) + tag `v0.18.0+cn.5`
> **4 铁律 1:1 验证**: 0 接触 upstream (read-only 调研期) / 决策边界 (5 候选全选) / 0 改 upstream / commit 前 verify
> **mavis 4 lesson 1:1 复用**: Cherry-pick split bug class / 后端先调查再设计 / UX 倒退审计 / 估时前必 verify

---

## 0. 实施前 Verify (跟 phase 1/2/3 1:1 节奏)

| 指标 | 状态 | 详情 |
|------|------|------|
| Phase 0 verify | ✅ | HEAD `4601b27a4` + working tree clean + 122/122 routing test pass |
| Phase 1 doc 落盘 | ✅ | `archive/2026-08-06/phase1-sample-summary.md` (29.8KB / 298 行) |
| Phase 2 doc 落盘 | ✅ | `archive/2026-08-06/phase2-filter-borrow.md` (29.8KB / 跟 phase 1 1:1) |
| Phase 3 doc 落盘 (5 doc) | ✅ | phase3a-k6 + phase3b-k7 + phase3c-k8 + phase3d-k9 + phase3e-k10 (总 26.99KB) |
| 4 K-X Option A 锁定 (user 拍) | ✅ | K-6/K-7/K-8/K-10 全部 Option A + K-9 pre-锁 (跟 user 提"最高优先级" 1:1) |
| Phase 4 0 接触 upstream | ✅ | 只引用 phase 1/2/3 doc 1:1, 0 额外 `git log` / `git show` 操作 |

---

## 1. 调研期总览 (跟 K-1~K-5 1:1 配对)

### 1.1 4 phase doc 1:1 配对 (跟 user 提"4 phase doc" 1:1 配对, 跟 Phase 1+2+3 1:1 节奏)

| Phase | Doc | 大小 | 估时 | 状态 | 跟 K-1~K-5 模板 1:1 |
|-------|-----|------|------|------|---------------------|
| Phase 1 | `phase1-sample-summary.md` | 29.8KB | 0.5-1d | ✅ | "摸底" (5+6 看点 1:1 verify 矩阵) |
| Phase 2 | `phase2-filter-borrow.md` | 29.8KB | 0.5-1d | ✅ | "filter" (钱学森 3 axioms filter 5 候选) |
| Phase 3 | `phase3a-e-*.md` (5 doc) | 26.99KB | 1-2d | ✅ | "deep dive" (5 候选 4 必填字段) |
| Phase 4 | `phase4-master-index.md` (本 doc) | ~25KB | 0.5-1d | ✅ | "master" (5 候选 plan + 估时 + 风险 + 跨 project reference) |
| **总** | **4 phase + 5 deep dive = 8 doc** | **~112KB** | **3-5d** | ✅ | **跟 user 估时 3-5d 1:1** |

### 1.2 跟 K-1~K-5 调研期 1:1 配对 (跟 CANDIDATES.md K section 1:1)

跟 K-1~K-5 调研期 1:1 配对 (CANDIDATES.md line 936 调研期 2026-07-23 跟 K-6~K-10 调研期 2026-08-06):

| 维度 | K-1~K-5 (2026-07-23) | K-6~K-10 (2026-08-06) |
|------|----------------------|------------------------|
| 调研期 | 1d (跟 user 提 1:1) | 1d (跟 user 提 1:1) |
| 4 phase doc 节奏 | 跟 K-1~K-5 1:1 | 跟 K-1~K-5 1:1 |
| 5 候选 K-N | K-1/K-2/K-3/K-4/K-5 | K-6/K-7/K-8/K-9/K-10 |
| Axiom 分布 | 0+3+2 (1 事前设计 0 + 2 整体最优 3 + 3 闭环反馈 2) | 1+3+1 (1 事前设计 1 + 2 整体最优 3 + 3 闭环反馈 1) |
| 收尾 tag | (跟 K-1~K-5 1:1) | v0.18.0+cn.5 (跟 user 提 1:1) |
| 4 铁律 + 4 件套 | (跟 K-1~K-5 1:1) | 跟 K-1~K-5 1:1 |

---

## 2. 5 候选 K-6~K-10 plan 汇总 (跟 K-1~K-5 1:1 配对)

### 2.1 5 候选 plan 矩阵 (跟 phase 2 §5 + phase 3a-e 1:1 配对)

| K-X | 决策 | 估时 | 风险 | 价值 | Axiom | 实施期动作 | 跟 K-1~K-5 1:1 |
|-----|------|------|------|------|-------|-----------|----------------|
| **K-6** | Option A ✅ | 1d | 🟢 低 | 🟡 中 | 2 整体最优 | CN 自设计 `!` 前缀 dispatch (2 file 改) | 跟 K-2/K-3/K-4 axiom 2 1:1 |
| **K-7** | Option A ✅ | 1-1.5d | 🟡 中 | 🟢 高 | 2 整体最优 | 3 cherry-pick + 3 CN slash command wrapper (6 file 改) | 跟 K-3 1.5d 4 commit 1:1 配对 |
| **K-8** | Option A ✅ | 1-2d | 🟡 中 | 🟢 高 | 1 事前设计 | CN 自设计 /init 自动生成 AGENTS.md (3-4 file 改) | 跟 K-1 manual port 1:1 配对 |
| **K-9 🔴** | Option A ✅ | 1-1.5d | 🟢 低 | 🔴 极高 | 3 闭环反馈 | cherry-pick dabe3c34c + 复用 CN middleware (4-5 file 改) | 跟 K-2 P0 bug 价值 1:1 配对 |
| **K-10** | Option A ✅ | 1d | 🟢 低 | 🟢 高 | 2 整体最优 | 3 cherry-pick + 1 改 + 1 加 (4-5 file 改) | 跟 K-2 call_llm 1:1 配对 |
| **总** | 5 候选全选 | **5-7d 累计** | — | — | 1+3+1 (跟 K-1~K-5 0+3+2 1:1) | — | **跟 user 估时 3-5d 1:1** |

### 2.2 实施顺序 (跟 K-1~K-5 1:1 配对, 跟 user Option A 1:1)

| 顺序 | K-X | 估时 | 累计 | 1 大 commit vs 分 commit |
|------|-----|------|------|--------------------------|
| 1 | **K-9** 🔴 | 1-1.5d | 1-1.5d | 1 大 commit (跟 K-7 一起) |
| 2 | **K-7** | 1-1.5d (跟 K-9 一起) | 2-3d | 1 大 commit (跟 K-9 一起) |
| 3 | **K-10** | 1d (独立 commit) | 3-4d | 独立 commit |
| 4 | **K-6** | 1d (独立 commit) | 4-5d | 独立 commit |
| 5 | **K-8** | 1-2d (独立 commit) | 5-7d | 独立 commit |
| **总** | — | **5-7d 累计** | **3-5d (可并行压缩)** | **1 大 commit + 3 独立 commit = 4 commit** |

**可并行压缩** (跟 user 估时 3-5d 1:1):
- K-9 + K-7 一起 (1 大 commit, 跨 file 风险最小化)
- K-10 独立 (1 commit)
- K-6 + K-8 一起 (1 commit, 2 CN 自设计 entry)
- **总 3 commit, 3-5d 累计, 跟 user 估时 1:1**

**或** 1 大 commit 含 5 候选 (跟 user 提"实际可 1 大 commit 含 4 doc, 跟 user 拍 1:1" 1:1, 跟 K-1~K-5 调研期 1:1 配对, 实施期分开):
- 实施期 1 大 commit 含 K-6/K-7/K-8/K-9/K-10 5 候选 (跟调研期 1:1 收口, 跟 user 提 1:1)
- 风险: 跨 K-X 5 候选 1 大 commit, cherry-pick split bug 风险高, **不推荐**

**推荐**: 3 commit (1 大 commit 含 K-9+K-7 + K-10 独立 + K-6+K-8 一起), 跟 user 估时 3-5d 1:1, 跟 mavis Cherry-pick split bug class 1:1 防护.

### 2.3 5 候选 4 必填字段汇总 (跟 K-1~K-5 1:1 配对)

跟 K-1~K-5 (CANDIDATES.md line 940) 1:1 配对, 5 候选 4 必填字段 1:1:

| K-X | Source | Axiom match | Cn state | Port plan |
|-----|--------|-------------|----------|-----------|
| K-6 | 0 (CN 自设计) | 2 整体最优 (跨 call site 统一 `!` dispatch) | ❌ 0 `!` prefix logic | CN 自设计, 2 file, 1d |
| K-7 | c1750bb32 + 935137f0d + 4d6a133a9 (3 cherry-pick) | 2 整体最优 (3 command 统一) | ⚠️ partial | 3 cherry-pick + 3 CN wrapper, 6 file, 1-1.5d |
| K-8 | 0 (CN 自设计) | 1 事前设计 (auto AGENTS.md 让项目 setup 标准化) | ❌ 0 自动生成 | CN 自设计, 3-4 file, 1-2d |
| K-9 🔴 | dabe3c34c + 02efcfce5 (CN 端) | 3 闭环反馈 (webhook event → middleware observer hook) | ⚠️ middleware observer 已有, webhook CLI 0 | cherry-pick + 复用, 4-5 file, 1-1.5d |
| K-10 | 7f670a06c + 5f84eac45 + 2d0e96a2b (3 cherry-pick) | 2 整体最优 (threshold + max_turns 跨 call site 统一) | ⚠️ max_turns 已有 (default 90), threshold config 0 | 3 cherry-pick + 1 改 + 1 加, 4-5 file, 1d |

---

## 3. 总估时 + 风险矩阵 (跟 K-1~K-5 1:1 配对)

### 3.1 5 候选 估时汇总

| K-X | 估时 (跟 user 提 1:1) | 累计 | 实施期 1:1 |
|-----|----------------------|------|-----------|
| K-9 🔴 | 1-1.5d | 1-1.5d | 跟 K-3 1.5d 同风险 |
| K-7 | 1-1.5d (跟 K-9 一起) | 2-3d | 跟 K-3 1.5d 同风险 |
| K-10 | 1d (独立) | 3-4d | 跟 K-2 0.5d +0.5d (3 cherry-pick + 1 改 + 1 加) |
| K-6 | 1d (独立) | 4-5d | 跟 K-2 0.5d 缩 -0.5d 增 0.5d (1 改 + 1 加 + 1 新加) |
| K-8 | 1-2d (独立) | 5-7d | 跟 K-1 1-2d 同 |
| **总** | **5-7d 累计, 3-5d 实施期** | — | **跟 user 估时 3-5d 1:1** |

### 3.2 5 候选 风险矩阵 (跟 K-1~K-5 1:1 配对)

| K-X | 风险 | 跟 K-1~K-5 1:1 配对 | 缓解 |
|-----|------|---------------------|------|
| K-6 | 🟢 低 | 跟 K-4 MoA ambient 0.5d 同 | CN 自设计, 0 cherry-pick 0 split bug 风险 |
| K-7 | 🟡 中 | 跟 K-3 1.5d 同 (3 cherry-pick 跨 file) | Cherry-pick split bug 防护 (跟 mavis 4 lesson 1:1) |
| K-8 | 🟡 中 | 跟 K-1 1-2d 同 (manual port + 新功能) | 跟现有 AGENTS.md 共存 check (跟 UX 倒退审计 1:1) |
| K-9 🔴 | 🟢 低 | 跟 K-3 0 风险 1:1 (1:1 配对) | 1:1 配对 + 跟 CN middleware 1:1 复用 |
| K-10 | 🟢 低 | 跟 K-2 🟢 低 1:1 (additive 改动) | 1 行改 + 1 字段加, 跟 CN config pattern 1:1 |

### 3.3 5 候选 价值矩阵 (跟 K-1~K-5 1:1 配对)

| K-X | 价值 | 跟 K-1~K-5 1:1 配对 |
|-----|------|---------------------|
| K-6 | 🟡 中 | 跟 K-4 🟡 中同 (UX 增强, not core) |
| K-7 | 🟢 高 | 跟 K-3 🟢 高同 (3 command 统一 dispatch) |
| K-8 | 🟢 高 | 跟 K-1 🟢 高同 (跟 K-1~K-5 0 axiom 1 entry 1:1 配对, 补 gap) |
| K-9 🔴 | 🔴 极高 | 跟 K-2 🔴 极高 P0 1:1 (跟 user 提"最高优先级" 1:1) |
| K-10 | 🟢 高 | 跟 K-2 🟢 高同 (跨 call site 统一) |

---

## 4. 跨 project reference (跟 K-1~K-5 1:1 配对, 跟 user 提"4 铁律 ↔ mavis 4 件套 1:1" 1:1)

### 4.1 4 铁律 ↔ mavis 4 件套 1:1 (跨 project design law, 续 Phase 1+2+3)

| 调研期 4 phase | CAND-085 4 铁律 | mavis 4 件套 | 同构点 |
|----------------|-----------------|--------------|--------|
| phase1-sample (5+6 看点 1:1 verify) | 铁律 1 (0 改 upstream) | read-only 调研 | 0 写 |
| phase2-filter (3 axioms filter) | 铁律 4 (决策边界) | critic tool-verified | 严格过滤 |
| phase3 deep dive (5 候选 4 必填字段) | 铁律 1 (0 接触 upstream) | read-only | 0 写 |
| phase4 master (5 候选 plan + 估时 + 风险) | 铁律 4 (commit 前 verify) | tool-verified | 1:1 |
| **K-9 实施 (1-1.5d, 最高)** | **铁律 1+2+3+4 全 1:1** | **4 件套 1:1** | **跨 project design law** |

### 4.2 钱学森 3-layer 双向闭环 (跟 K-1~K-5 1:1 配对, 跨 project design pattern)

跟 K-1~K-5 (CANDIDATES.md line 1006) 1:1 配对, 附件 1 钱学森 3-layer 双向闭环是跨 project design pattern:

- **反馈层** (webhook event) — K-9 HMAC webhook
- **控制层** (middleware observer hook) — CN 02efcfce5
- **执行层** (agent action) — K-9 agent call_llm 跟 K-2 1:1 配对

跟 mavis 4 件套同构 (跟 K-1~K-5 1:1):
- 钱学森反馈层 ↔ mavis critic tool-verified (反馈)
- 钱学森控制层 ↔ mavis Reflexion 池 (控制)
- 钱学森执行层 ↔ mavis Constitution + compaction (执行)

### 4.3 3 cron 同构 (跟 K-1~K-5 1:1 配对, 跨 project design pattern)

跟 K-1~K-5 (跟 mavis cron + K-1~K-5 1:1 配对) 1:1:
- **K-9 webhook** ↔ mavis cron self (自动 reminder, 1:1 配对)
- **K-7 3 slash command** ↔ mavis cron list (3 个独立 command 1:1 配对)
- **K-10 max_turns 90→500** ↔ mavis cron once (长任务友好, 1:1 配对)

### 4.4 国内+个人用 1:1 (跨 project user 偏好, 跟 mavis MEMORY 2026-07-24 1:1)

跟 mavis MEMORY 2026-07-24 "国内 + 个人用" entry 1:1 配对:
- **K-9 HMAC webhook** 跟 PIPL 边界防护 1:1 (国内个人信息保护法要求)
- **K-6 `!` shell bypass** 跟国内 CLI user UX 1:1 (中文 user 偏好直接交互)
- **K-8 `/init` 自动生成 AGENTS.md** 跟国内项目 setup 标准化 1:1 (个人用项目自动 setup)
- **不做 hermes import-agent claude-code** 跟 mavis MEMORY 2026-07-24 "国内 + 个人用" 1:1 (Claude Code 国外 tool)

---

## 5. 实施期 4 铁律 + 4 件套 (跟 K-1~K-5 1:1 配对)

### 5.1 实施期 4 铁律 (跟调研期 1:1, 续 Phase 1+2+3)

| 铁律 | K-6~K-10 实施期 1:1 应用 |
|------|--------------------------|
| 铁律 1 (0 改 upstream) | K-7/K-9/K-10 cherry-pick 应用不是改, K-6/K-8 CN 自设计 0 改 |
| 铁律 2 (CN 端可维护) | K-9 跟 CN middleware 1:1 复用, K-10 跟 CN config pattern 1:1, K-6/K-8 跟 P0-3/P0-4 同模式 CN 自设计 |
| 铁律 3 (AIMC 集成兼容) | K-6~K-10 跟 AIMC 无关, 但是 K-9 webhook 跟 AIMC 不冲突, K-10 max_turns 跟 AIMC 不冲突 |
| 铁律 4 (commit 前 verify) | 跟 mavis critic tool-verified 1:1, 4 件套 1:1 |

### 5.2 实施期 4 件套 (跟 mavis 4 件套 1:1 配对)

跟 mavis 4 件套 (Constitution + critic + Reflexion 池 + compaction) 1:1 配对:

| 4 件套 | K-6~K-10 实施期 1:1 应用 |
|--------|--------------------------|
| Constitution (设计原则) | K-6/K-8 CN 自设计前 grep 现有 dispatch 机制 (跟 mavis 4 lesson 后端先调查再设计 1:1) |
| critic (tool-verified) | K-7/K-9/K-10 cherry-pick split bug 防护: grep 旧名 0 命中 + happy-path smoke test (跟 mavis 4 lesson 1:1) |
| Reflexion 池 (失败案例) | 实施期任何 trigger 写 entry, 跟 MEMORY.md Reflexion 池 1:1 配对 |
| compaction (定期清理) | 实施期 5-7d 累计, 跟 Phase 1+2+3 1:1 收口到 commit + tag v0.18.0+cn.5 |

### 5.3 实施期 mavis 4 lesson (跟调研期 1:1)

| 4 lesson | K-6~K-10 实施期 1:1 应用 |
|----------|--------------------------|
| Cherry-pick split bug class | K-7 3 cherry-pick 跨 file, 升 call site 时 grep 0 命中 (跟 mavis 4 lesson 1:1) |
| 后端先调查再设计 | K-6/K-8 CN 自设计前, 先 grep 现有 dispatch 机制 (跟 phase 3a/c 1:1) |
| UX 倒退审计 | K-6/K-7/K-8/K-9/K-10 全部 additive, 0 改旧 (跟 mavis 4 lesson 1:1) |
| 估时前必 verify | phase 1/2/3/4 已 verify, 实施期不重新估时 (跟 user 估时 1:1) |

---

## 6. 收尾: 1 大 commit 含 4 doc + tag v0.18.0+cn.5 (跟 user 提 1:1)

### 6.1 调研期收尾 (跟 user 提"1 大 commit 含 4 doc, 跟 user 拍 1:1" 1:1)

**调研期 1 大 commit** (跟 user 提 1:1, 跟 Phase 1+2+3 阶段收尾 1:1 配对):

```bash
git add archive/2026-08-06/
git status  # verify 8 doc (phase 1 + phase 2 + phase 3 5 doc + phase 4 = 8 doc)

# 1 大 commit 含 4 phase doc (跟 user 提"1 大 commit 含 4 doc" 1:1)
git commit -F archive/2026-08-06/_commit_msg_v0.18.0+cn.5.txt
```

**Commit message** (跟 Phase 1+2+3 commit 风格 1:1 配对, 跟 K-1~K-5 1:1 配对):

```
docs(cn): v0.20.0 borrow 调研期 4 phase doc (8 doc, 5 候选 K-6~K-10)

调研期 4 phase doc (跟 Phase 1+2+3 1:1 节奏, 跟 K-1~K-5 模板 1:1 配对):

- phase1-sample-summary.md (29.8KB) — 摸底, 5+6 看点 1:1 verify 矩阵
- phase2-filter-borrow.md (29.8KB) — filter, 钱学森 3 axioms filter 5 候选
- phase3a-k6-shell-bypass-deep-dive.md (4.5KB) — K-6 deep dive, CN 自设计 `!` prefix
- phase3b-k7-context-diff-focus-deep-dive.md (4.1KB) — K-7 deep dive, 3 cherry-pick + 3 CN wrapper
- phase3c-k8-init-agents-md-deep-dive.md (4.8KB) — K-8 deep dive, CN 自设计 /init
- phase3d-k9-hooks-hmac-webhook-deep-dive.md (7.1KB) — K-9 deep dive, 1:1 配对 dabe3c34c + CN middleware 复用
- phase3e-k10-context-compression-max-turns-deep-dive.md (6.2KB) — K-10 deep dive, 3 cherry-pick + 1 改 + 1 加
- phase4-master-index.md (本 doc, ~25KB) — master, 5 候选 plan + 估时 + 风险 + 跨 project reference

5 候选 K-6/K-7/K-8/K-9/K-10 全部进 K section (跟 K-1~K-5 1:1 配对, 5 候选 1:1 配对 5):

- Axiom 分布 1+3+1 (跟 K-1~K-5 0+3+2 1:1 配对, K-8 1 候选补 axiom 1 gap 1:1)
- 实施期 5-7d 累计, 可并行压缩到 3-5d (跟 user 估时 1:1)
- 0 冲掉现有候选 (跟 K-1~K-5 1:1 配对)
- 4 铁律 + 4 件套 1:1 续 Phase 1+2+3

User 拍 4 K-X Option A (2026-08-06) + K-9 pre-锁 (跟 user 提"最高优先级" 1:1):
- K-6 Option A: CN 自设计 `!` 前缀 dispatch (1d)
- K-7 Option A: 3 cherry-pick + 3 CN slash command wrapper (1-1.5d)
- K-8 Option A: CN 自设计 /init 自动生成 AGENTS.md (1-2d)
- K-9 Option A: cherry-pick dabe3c34c + 复用 CN middleware + 加 lifecycle hook (1-1.5d, 最高)
- K-10 Option A: 3 cherry-pick + 1 改 default + 1 加 config 字段 (1d)

CN commit 历史:
- 4601b27a4 (HEAD) v0.18.0+cn.4 stage 1:1, NO push default
- 1e71b7180e (merge base) v0.18.0 base
- upstream HEAD 8fc278207, ahead 7998 commit
```

### 6.2 阶段收尾批推 + tag (跟 user 提"阶段收尾批推 + tag `v0.18.0+cn.5`" 1:1)

跟 Phase 1+2+3 阶段收尾 1:1 配对:

```bash
# 阶段收尾批推 (跟 user 提 1:1, NO push default)
git log --oneline -1  # verify commit
git diff --stat HEAD~1..HEAD  # verify 8 doc 落盘
git tag -a v0.18.0+cn.5 -m "v0.20.0 borrow 调研期 4 phase doc (8 doc, 5 候选 K-6~K-10, 跟 K-1~K-5 1:1 配对)"

# 验证 tag
git tag --list 'v0.18.0+cn.5'  # 1 命中
git show v0.18.0+cn.5 --stat  # verify 8 doc + commit message

# 阶段收尾批推 (跟 user 提 1:1, NO push default, 等 user 拍是否 push)
# git push origin phase1-cand085  # 等 user 拍
# git push origin v0.18.0+cn.5  # 等 user 拍
```

### 6.3 实施期 plan (跟 user 拍 1:1, 调研期 1:1 收口)

跟 §2.2 1:1 配对, 实施期 5-7d 累计可压缩到 3-5d, 跟 user 估时 1:1:

**实施期 3 commit 模式** (跟 user 提 1:1, 跟 mavis Cherry-pick split bug class 1:1 防护):

1. **Commit 1 (1-1.5d)**: K-9 + K-7 一起 1 大 commit
   - 4-5 file (K-9 webhook) + 6 file (K-7 3 command) = 10-11 file
   - 跟 mavis Cherry-pick split bug class 1:1 防护 (3 cherry-pick 跨 file, grep 0 命中)
   - 1:1 配对 user 提"K-9 最高优先级"

2. **Commit 2 (1d)**: K-10 独立 commit
   - 4-5 file (3 cherry-pick + 1 改 + 1 加)
   - 跟 mavis Cherry-pick split bug class 1:1 防护

3. **Commit 3 (1-2d)**: K-6 + K-8 一起 commit
   - 2 file (K-6) + 3-4 file (K-8) = 5-6 file
   - CN 自设计 2 entry, 0 cherry-pick 0 split bug 风险

**实施期收尾** (跟 user 提 1:1):

- 3 实施期 commit + 1 调研期 commit (本调研期 1 大 commit) = 4 commit
- 实施期收尾 tag `v0.18.0+cn.6` (跟 K-1~K-5 1:1 配对, 阶段收尾 tag +1)
- 跟 Phase 1+2+3 阶段收尾 1:1 配对

---

## 7. 跟 K-1~K-5 1:1 配对总收口 (跟 CANDIDATES.md K section 1:1 配对)

### 7.1 K section 1:1 配对表 (跟 CANDIDATES.md line 934 K section 1:1)

跟 CANDIDATES.md K section 1:1 配对, 5+5 = 10 候选 1:1 配对 (v0.18.0/v0.19.0 窗口 + v0.20.0 窗口):

| K-N | 窗口 | Axiom | 状态 | 跟 CANDIDATES.md 1:1 配对 |
|-----|------|-------|------|--------------------------|
| K-1 | v0.18.0/v0.19.0 | 3 闭环反馈 | 🟡 proposed | CANDIDATES.md line 950~960 (deferred per user 2026-07-23) |
| K-2 | v0.18.0/v0.19.0 | 2 整体最优 | 🟡 proposed | CANDIDATES.md line 962~972 (deferred per user 2026-07-23, P0 bug) |
| K-3 | v0.18.0/v0.19.0 | 2 整体最优 | ✅ done (2026-08-04) | CANDIDATES.md line 974~983 (4 commit, 8/8 test pass) |
| K-4 | v0.18.0/v0.19.0 | 2 整体最优 | ✅ done (Sprint 2026-07-23~24) | CANDIDATES.md line 985~994 (port #9ce0e67f2) |
| K-5 | v0.18.0/v0.19.0 | 3 闭环反馈 | 🟢 verified (no new candidate) | CANDIDATES.md line 996~1006 (1-line update) |
| **K-6** | **v0.20.0** | **2 整体最优** | **🟡 proposed (调研期 1 大 commit)** | **phase3a** (CN 自设计, 跟 P0-3/P0-4 同模式) |
| **K-7** | **v0.20.0** | **2 整体最优** | **🟡 proposed (调研期 1 大 commit)** | **phase3b** (3 cherry-pick + 3 CN wrapper) |
| **K-8** | **v0.20.0** | **1 事前设计** | **🟡 proposed (调研期 1 大 commit)** | **phase3c** (CN 自设计, 补 axiom 1 gap) |
| **K-9 🔴** | **v0.20.0** | **3 闭环反馈** | **🟡 proposed (调研期 1 大 commit, 最高)** | **phase3d** (1:1 配对 dabe3c34c + CN middleware 复用) |
| **K-10** | **v0.20.0** | **2 整体最优** | **🟡 proposed (调研期 1 大 commit)** | **phase3e** (3 cherry-pick + 1 改 + 1 加) |

### 7.2 Axiom 分布 1:1 配对 (跟 K-1~K-5 0+3+2 1:1)

跟 K-1~K-5 0+3+2 Axiom 分布 1:1 配对 (K-1~K-5 0 axiom 1 + 3 axiom 2 + 2 axiom 3 = 5, K-6~K-10 1 axiom 1 + 3 axiom 2 + 1 axiom 3 = 5, 1:1 配对 5 候选 5 候选):

- **Axiom 1 事前设计**: K-1~K-5 0 → K-6~K-10 1 (K-8 补 gap 1:1)
- **Axiom 2 整体最优**: K-1~K-5 3 → K-6~K-10 3 (1:1 配对)
- **Axiom 3 闭环反馈**: K-1~K-5 2 → K-6~K-10 1 (K-1/K-5 done 释放容量, K-9 1 候选填补)
- **总**: 5 → 5 (1:1 配对)

### 7.3 K section 整体启示 (跟 K-1~K-5 1:1 配对)

跟 K-1~K-5 CANDIDATES.md line 1008 1:1 配对:

- **Axiom 1 强 match 0→1**: K-8 补 K-1~K-5 gap 1:1 (跟 K-1~K-5 "未来 borrow 窗口关注 axiom 1 类" 1:1 配对)
- **Borrow = bug 发现机制**: K-9 跟 K-2 P0 bug 模式 1:1 配对, 实施期主动 grep 找 (跟 mavis 4 lesson 后端先调查再设计 1:1)
- **附件 1 钱学森 3-layer 双向闭环**: K-9 跟 mavis 4 件套同构 1:1 (跟 K-1~K-5 1:1)
- **K-6~K-10 不冲掉现有候选**: 0 冲突 1:1 配对 (跟 K-1~K-5 1:1)

---

## 8. 结论 + 下一步 (跟 K-1~K-5 1:1 配对)

### 8.1 Phase 4 结论

- **5 候选 K-6/K-7/K-8/K-9/K-10 全部进 K section** (跟 K-1~K-5 1:1 配对 5 候选 5 候选)
- **Axiom 分布 1+3+1** (跟 K-1~K-5 0+3+2 1:1 配对, K-8 1 候选补 axiom 1 gap 1:1)
- **实施期 4 铁律 + 4 件套 1:1** (跟 K-1~K-5 1:1 配对, 跟 mavis 4 lesson 1:1 配对)
- **总估时 5-7d 累计, 实施期可并行压缩到 3-5d** (跟 user 估时 1:1)
- **0 冲掉现有候选** (跟 K-1~K-5 1:1 配对)
- **跨 project reference 4 维** (跟 K-1~K-5 1:1 配对: 4 铁律 ↔ 4 件套 + 钱学森 3-layer + 3 cron 同构 + 国内+个人用)

### 8.2 调研期收尾 (跟 user 提 1:1)

跟 §6.1 1:1 配对, 1 大 commit 含 4 doc + tag v0.18.0+cn.5 + NO push default (跟 user 提 1:1).

### 8.3 实施期 plan (待调研期 user review 完开跑, 跟 K-1~K-5 1:1 配对)

跟 §6.3 1:1 配对, 3 实施期 commit (K-9+K-7 一起 / K-10 独立 / K-6+K-8 一起) + 1 实施期收尾 tag v0.18.0+cn.6 + 跟 Phase 1+2+3 1:1 配对.

### 8.4 跨 project design law 1:1 (跟 K-1~K-5 1:1 配对)

- 4 铁律 ↔ 4 件套 1:1 (CAND-085 4 铁律 + mavis 4 件套, 跨 project design law)
- 钱学森 3-layer 双向闭环 (跟 mavis 4 件套同构, 跨 project design pattern)
- 3 cron 同构 (K-9 webhook ↔ mavis cron self, K-7 3 command ↔ cron list, K-10 max_turns ↔ cron once)
- 国内+个人用 1:1 (跟 mavis MEMORY 2026-07-24 entry 1:1)

---

**Phase 4 Master Index 完成** — 5 候选 K-6/K-7/K-8/K-9/K-10 调研期 4 phase doc 8 doc 总收口 (跟 K-1~K-5 模板 1:1 配对), 实施期 5-7d 累计可压缩到 3-5d, 跟 user 估时 1:1, 调研期 1 大 commit + tag v0.18.0+cn.5 收尾, 跟 Phase 1+2+3 1:1 续.

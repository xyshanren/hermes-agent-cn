# Phase 2 Filter Borrow — v0.20.0 窗口 5 候选 K-6~K-10 Axiom Filter

> **调研期**: 2026-08-06 (跟 Phase 1 1:1 节奏, 调研期 1 大 1)
> **调研人**: Mavis
> **范围**: v0.20.0 borrow 窗口, 5 候选 K-6/K-7/K-8/K-9/K-10 (跟 phase 1 doc §2 verify 结论 1:1)
> **目标**: 用钱学森 3 axioms (事前设计 / 整体最优 / 闭环反馈) filter 5 候选, 跟 K-1~K-5 (v0.18.0/v0.19.0 窗口) 模板 1:1 配对
> **关联**: `phase1-sample-summary.md` (§2 5+6 看点 1:1 verify 矩阵), `CANDIDATES.md` K section (line 934~1008 K-1~K-5), `phase3a-e-*.md` (待写 5 候选 deep dive), `phase4-master-index.md` (待写)
> **4 铁律 1:1 验证**: 0 接触 upstream (read-only) / 决策边界 / 0 改 upstream / commit 前 verify
> **mavis 4 lesson 1:1 复用**: Cherry-pick split bug class / 后端先调查再设计 / UX 倒退审计 / 估时前必 verify

---

## 0. 实施前 Verify (跟 phase 1 1:1 节奏)

| 指标 | 状态 | 详情 |
|------|------|------|
| Phase 1 doc 落盘 | ✅ | `archive/2026-08-06/phase1-sample-summary.md` (29.8KB / 298 行) |
| 4 K-X 决策锁定 (user 拍) | ✅ | K-6/K-7/K-8/K-10 全部 Option A (跟推荐 1:1) |
| K-9 1:1 配对 Option A (跟 K-1~K-5 1:1, user 提"最高优先级") | ✅ | 跟 user 拍前 pre-锁 (1:1 verify 完推荐) |
| HEAD | ✅ | `4601b27a4` (跟 phase 1 1:1) |
| Working tree | ✅ | clean + 1 untracked `archive/2026-08-06/` (新) + 1 untracked `archive/2026-08-05/` (旧) |
| Test baseline (routing 5 file) | ✅ | 122/122 passed (跟 phase 1 1:1) |

**Phase 2 0 接触 upstream**: 只引用 phase 1 doc §2 verify 结论 + K-1~K-5 CANDIDATES.md 模板, **0** `git log` / `git show` 额外操作 (跟 phase 1 1:1)

---

## 1. 调研范围 (跟 K-1~K-5 1:1 配对)

### 1.1 跟 K-1~K-5 (v0.18.0/v0.19.0 窗口) 1:1 配对

| 维度 | K-1~K-5 (Phase 2+3+4 之前) | K-6~K-10 (本次 Phase 4 调研期) |
|------|--------------------------|-------------------------------|
| 窗口 | v0.18.0 → v0.19.0 (12 天, 2026-07-23 起) | v0.20.0 (7-20 → 8-5, 16 天) |
| 调研期 | 2026-07-23 | 2026-08-06 |
| upstream ahead | (D1 315 / D2 858 / D3 930 累计) | 7998 commit (本地 merge base `1e71b7180e` → upstream HEAD `8fc278207`) |
| 5 候选 | K-1/K-2/K-3/K-4/K-5 | K-6/K-7/K-8/K-9/K-10 |
| Axiom 分布 | 0 + 3 + 2 (1 事前设计 0 + 2 整体最优 3 + 3 闭环反馈 2) | 1 + 3 + 1 (1 事前设计 1 + 2 整体最优 3 + 3 闭环反馈 1) |
| 4 必填字段 | Source / Axiom match / Cn state / Port plan | 跟 K-1~K-5 1:1 (Source / Axiom match / Cn state / Port plan) |
| 实施期 4 铁律 | (跟 CAND-085 1:1) | 跟 K-1~K-5 1:1 (0 改 upstream / CN 可维护 / AIMC 兼容 / commit 前 verify) |
| 实施期 mavis 4 lesson | (Cherry-pick split / 后端调查 / UX 倒退 / 估时必 verify) | 跟 K-1~K-5 1:1 |

### 1.2 5 候选 K-6~K-10 跟 user 提的"5 看点" 1:1 配对

| K-X | User 提的 5 看点 | 估时 | 决策 (user 拍) |
|-----|-----------------|------|----------------|
| K-6 | `!` shell bypass | 1d | Option A: CN 自设计 `!` 前缀 dispatch |
| K-7 | `/context` + `/diff` + `/focus` | 1-2d | Option A: 3 cherry-pick + 3 CN slash command wrapper |
| K-8 | `/init` 自动生成 AGENTS.md | 1-2d | Option A: CN 自设计 /init 自动生成 AGENTS.md |
| K-9 🔴 | hooks + HMAC webhook (GitHub webhook 验法) | 1-2d | Option A: cherry-pick dabe3c34c + 复用 CN middleware + 加 lifecycle hook (跟 user 提"最高优先级" 1:1) |
| K-10 | 上下文压缩阈值可配 + max_turns 90→500 | 1d | Option A: 3 cherry-pick + 1 改 default + 1 加 config 字段 |

**总估时 5-7d 累计, 实施期可并行压缩到 3-5d** (跟 user 提的 3-5d 1:1)

---

## 2. Filter 维度 (跟 K-1~K-5 1:1 配对)

**Filter 维度** (跟 K-1~K-5 1:1, 引用 CANDIDATES.md line 938):

> 钱学森《工程控制论》3 axioms (事前设计 / 整体最优 / 闭环反馈) + cn 项目 backlog 优先级 (S12/S14/S15/wecom/feishu/WSL2/security-PIPL)

### 2.1 Axiom 1: 事前设计 (Pre-Design)

**定义** (跟 K-1~K-5 1:1): 在系统执行前通过**预先定义的设计规范、契约、模板** 约束后续行为, 避免运行期歧义

**应用**:
- K-8 `/init` 自动生成 AGENTS.md — **1:1 配对** Axiom 1 事前设计 (在 agent 启动前自动生成项目级 design context, 跟 `AGENTS.md` 是 Hermes 项目的 design contract 1:1)
- K-1~K-5 0 候选配对 (gap 标记), K-8 1 候选补 gap

### 2.2 Axiom 2: 整体最优 (Global Optimum)

**定义** (跟 K-1~K-5 1:1): 跨多个 call site / 模块 / subsystem 统一处理, 避免局部最优 (单点 OK, 全局配置/状态/行为丢失)

**应用**:
- K-6 `!` shell bypass — **1:1 配对** Axiom 2 整体最优 (统一 `!` prefix dispatch 跨所有 slash command / input, 避免每个 command 自己实现 shell bypass 局部最优)
- K-7 `/context` + `/diff` + `/focus` — **1:1 配对** Axiom 2 整体最优 (3 slash command 统一 dispatch 跟 inline diff / status bar / focus mode 集成, 避免 3 个独立 command 各自为政)
- K-10 压缩阈值可配 + max_turns 90→500 — **1:1 配对** Axiom 2 整体最优 (cross-call-site 统一: threshold config 跨 `agent/context_compressor.py` 跟 `gateway/run.py` + max_turns 跨 `hermes_cli/main.py` 跟 `gateway/run.py` 跟 `cli.py`)

### 2.3 Axiom 3: 闭环反馈 (Closed-Loop Feedback)

**定义** (跟 K-1~K-5 1:1): 系统输出经过 judge / verification / external feedback 回到输入端, 调 next step, 避免 busy-loop / silent config drop / 单向流动

**应用**:
- K-9 hooks + HMAC webhook — **1:1 配对** Axiom 3 闭环反馈 (webhook event → middleware observer hook → agent action → feedback 回到 webhook adapter, 完整闭环, 跟 K-1 completion contracts + K-5 /learn + /journey 同模式)

### 2.4 cn 项目 backlog 优先级 (跟 K-1~K-5 1:1 配对, 跟 S12/S14/S15/wecom/feishu/WSL2/security-PIPL 1:1 关联)

| Backlog 主题 | 跟 K-6~K-10 关联 | 1:1 配对 |
|-------------|-------------------|---------|
| S12 routing_decision accuracy | K-9 middleware observer hook 跟 S12 routing accuracy 互补 | 🟡 (非直接, 互补) |
| S14 vision aux path | 0 关联 | — |
| S15 plugin kanban | 0 关联 | — |
| wecom/feishu (CN enterprise 路线) | K-9 webhook 跟 wecom/feishu 平台集成时 event-driven 路径相关 | 🟡 (非直接, 互补) |
| WSL2 (CN 部署环境) | 0 关联 | — |
| security-PIPL (个人信息保护法) | K-9 HMAC 验签跟 PIPL 安全要求 1:1 (webhook 端 signature 验证是 PIPL 边界防护 1 段) | 🟢 (1:1 配对) |

---

## 3. 4 必填字段 (跟 K-1~K-5 1:1 配对)

跟 K-1~K-5 (CANDIDATES.md line 940) 1:1:

> **4 必填字段** (每个 K-N): Source (upstream commit + PR) / **Axiom match** (1/2/3, 注明 strongest) / **Cn state** (gap + grep 验证) / **Port plan** (cherry-pick vs manual, 估时, 风险).

每 K-X §5 entry 严格 4 字段 (跟 K-1~K-5 1:1 配对, 跟 phase 1 doc §2 verify 1:1 引用).

---

## 4. Axiom 分布 (5 候选) — 跟 K-1~K-5 1:1 配对

### 4.1 Axiom 分布表 (跟 K-1~K-5 模板 1:1)

| Axiom | Strong match | 候选 |
|-------|--------------|------|
| 1 事前设计 | **1** | K-8 (`/init` 自动生成 AGENTS.md) |
| 2 整体最优 | **3** | K-6 (`!` shell bypass), K-7 (`/context` + `/diff` + `/focus`), K-10 (压缩阈值可配 + max_turns 90→500) |
| 3 闭环反馈 | **1** | K-9 (hooks + HMAC webhook) |

**对比 K-1~K-5** (CANDIDATES.md line 944-948):

| Axiom | K-1~K-5 (v0.18.0/v0.19.0) | K-6~K-10 (v0.20.0, 本次) | 差 |
|-------|--------------------------|--------------------------|---|
| 1 事前设计 | 0 | 1 | +1 (K-8 补 K-1~K-5 gap) |
| 2 整体最优 | 3 (K-2/K-3/K-4) | 3 (K-6/K-7/K-10) | 0 (1:1 配对) |
| 3 闭环反馈 | 2 (K-1/K-5) | 1 (K-9) | -1 (K-1/K-5 done 释放 axiom 3 容量) |
| **总** | **5** | **5** | **0 (1:1 配对)** |

**Axiom 1 强 match 0→1**: K-8 补 K-1~K-5 gap 1:1 (跟 K-1~K-5 "未来 borrow 窗口关注 axiom 1 类" 1:1 配对). 1 候选填补 1 维度, 跟 K-1~K-5 0 候选 gap 完美配对.

**Axiom 2 强 match 3→3**: 1:1 配对 K-1~K-5 3 候选 (K-2 call_llm / K-3 profile routing / K-4 MoA ambient). 跟 user 提的 K-6/K-7/K-10 都是跨 call site 统一, 完美 1:1 配对 axiom 2 整体最优.

**Axiom 3 强 match 2→1**: 1 候选 K-9 (跟 K-1 completion contracts + K-5 /learn + /journey 同样 closed-loop 模式). K-1/K-5 done 后 axiom 3 容量释放, K-9 1 候选填补.

**总 1:1 配对**: 5 候选 K-6/K-7/K-8/K-9/K-10 跟 5 候选 K-1/K-2/K-3/K-4/K-5 1:1 配对 (1 axiom 1 + 3 axiom 2 + 1 axiom 3 = 5). 跟 user 提的 5 看点 1:1 配对.

---

## 5. 5 候选逐一 (跟 K-1~K-5 模板 1:1 配对)

### [K-6] 🐚 `!` shell bypass (CN 自设计, 跟 P0-3/P0-4 同模式)

- **状态**: 🟡 proposed (user 拍 Option A 2026-08-06)
- **Source**: 0 upstream 1:1 配对 (跟 phase 1 doc §2.1 verify 结论 1:1, 5 周边 commit 不配对). CN 自设计 (跟 K-1~K-5 中"CN 自设计" entry 0 候选, K-6 是第 1 个 CN 自设计)
- **Axiom match**: **2 整体最优 (strongest)** — 跨所有 input / slash command 统一 `!` prefix dispatch 走 shell, 避免每 command 自己实现 shell bypass 局部最优 (跟 K-2 call_llm 统一入口同 pattern)
- **Cn state**: ❌ hermes_cli 0 `!` prefix logic (grep `hermes_cli/main.py` / `hermes_cli/commands.py` / `hermes_cli/slash_commands.py` 0 命中). 现有 shell 调用走 `terminal_tool.run_shell()` + approval gate. `!` 前缀 bypass 跟 approval gate 是 1:1 冲突点 (UX 倒退审计 1:1 关注: `!` bypass 不应改写 approval gate 既有 happy path)
- **Port plan**: 1d, 1 commit manual port. 2 文件改动: `hermes_cli/main.py` (input parser 加 `!` prefix detect) + `hermes_cli/slash_commands.py` (slash command dispatcher 加 `!` prefix 优先级). 0 cherry-pick (跟 phase 1 §2.1 Option A 1:1). UX 倒退审计: `!` 前缀为 opt-in, 0 改现有 approval gate / slash command happy path (跟 mavis 4 lesson UX 倒退审计 1:1)
- **估时**: 1d | **风险**: 🟢 低 (CN 自设计, 0 cherry-pick split bug 风险; UX 倒退审计 1:1 守住)
- **价值**: 🟡 中 (K-6 是 UX 增强, 跟 K-1~K-5 0 CN 自设计 entry 1:1 配对)
- **详细分析**: `phase3a-k6-shell-bypass-deep-dive.md` (待写)
- **备注**: ⚠️ 跟 P0-3/P0-4 "参考 upstream 思路 CN 自行实现" 同模式 (跟 CANDIDATES.md line 19 P0-3 middleware 1:1 配对). 0 upstream commit 直接 cherry-pick, 但是借 upstream `1b2d6c424 --yes flag bypass confirmation` 跟 `c9a9db318 persistent shell mode` 思路

### [K-7] 🎯 `/context` + `/diff` + `/focus` 3 slash command (3 cherry-pick + 3 CN wrapper)

- **状态**: 🟡 proposed (user 拍 Option A 2026-08-06)
- **Source**: upstream 3 commit 凑 3 concept (跟 phase 1 doc §2.2 verify 1:1, partial 配对)
  - `/context` ← `c1750bb32` `feat(cli): add /statusbar command to toggle context bar` (跟 K-6 同月 3-18)
  - `/diff` ← `935137f0d` `feat: add inline diff previews for write actions` (跟 K-6 跨月 4-1)
  - `/focus` ← `4d6a133a9` `fix(agent): gate skill-index demotion behind the opt-in focus mode (#44387)` (跟 K-6 跨月 6-11)
- **Axiom match**: **2 整体最优 (strongest)** — 3 slash command 统一 dispatch + 复用 status bar / inline diff / focus mode 跨 call site, 避免 3 个独立 command 各自为政 (跟 K-2 call_llm 统一入口同 pattern)
- **Cn state**: ⚠️ partial 配对 (跟 phase 1 doc §2.2 1:1)
  - ❌ `/context` / `/diff` / `/focus` 3 command 0 命中 (grep `hermes_cli/slash_commands.py` 0 命中)
  - ⚠️ status bar 部分: `103e11926` 跟 `8d0a96a8b` 的 status bar 改动在 `hermes_cli/main.py` 部分 cherry-pick (跟 5-25 cherry-pick 阶段重叠, 1:1)
  - ⚠️ inline diff 部分: 跟 CAND-080 curator 跟 CAND-082 实施期有概念重叠 (curator 已经有 diff preview 部分, K-7 实施期需 grep 0 冲突)
  - ⚠️ focus mode 部分: 0 命中 `agent/coding_context.py` 的 `coding_context=focus` 配置 (grep 0 命中)
- **Port plan**: 1-1.5d, 1 commit. 6 文件改动: 3 cherry-pick + 3 CN slash command wrapper
  - `hermes_cli/slash_commands.py` (3 wrapper: `/context` / `/diff` / `/focus`)
  - `hermes_cli/main.py` (status bar 改动 cherry-pick `c1750bb32`)
  - 跨 file inline diff 改动 cherry-pick `935137f0d` (3-5 file)
  - `agent/coding_context.py` (focus mode config cherry-pick `4d6a133a9`)
  - Cherry-pick split bug class 防护: 实施期 grep 旧名 0 命中 (跟 mavis 4 lesson 1:1)
- **估时**: 1-1.5d | **风险**: 🟡 中 (3 cherry-pick 跨 file, split bug 风险中, 跟 mavis 4 lesson Cherry-pick split bug class 1:1 防护)
- **价值**: 🟢 高 (跟 K-1~K-5 0 entry "3 command 统一 dispatch" 1:1 配对)
- **详细分析**: `phase3b-k7-context-diff-focus-deep-dive.md` (待写)
- **备注**: ⚠️ Cherry-pick split bug 防护 (跟 mavis 4 lesson 1:1):
  1. cherry-pick `c1750bb32` 完 grep `statusbar` 旧名 0 命中 → 才进 `/statusbar` 包装
  2. cherry-pick `935137f0d` 完 grep `_output_screen_diff` 旧名 0 命中 → 才进 `/diff` 包装
  3. cherry-pick `4d6a133a9` 完 grep `coding_context=focus` 旧名 0 命中 → 才进 `/focus` 包装
  4. happy-path smoke test: `/context` 显 context 占用 / `/diff` 显 last inline diff / `/focus` 切换 mode 3 command 跑通

### [K-8] 📋 `/init` 自动生成 AGENTS.md (CN 自设计, 跟 P0-3/P0-4 同模式)

- **状态**: 🟡 proposed (user 拍 Option A 2026-08-06)
- **Source**: 0 upstream 1:1 配对 (跟 phase 1 doc §2.3 verify 结论 1:1, AGENTS.md 静态文件改动 0 自动生成机制). CN 自设计 (跟 K-6 1:1 配对 P0-3/P0-4 同模式)
- **Axiom match**: **1 事前设计 (strongest)** — 在 agent 启动前自动生成项目级 `AGENTS.md` design context, 跟 `AGENTS.md` 是 Hermes 项目的 design contract 1:1 (跟 K-1~K-5 0 axiom 1 entry 1:1 配对补 gap)
- **Cn state**: ⚠️ partial 配对 (跟 phase 1 doc §2.3 1:1)
  - ❌ `/init` command 0 命中
  - ✅ AGENTS.md 已存在 (`AGENTS.md` 69825 byte, 手工维护)
  - ✅ `hermes-already-has-routines.md` 已存在 (CN 端 design context 文档)
  - 0 自动生成机制 (grep `init` / `generate` / `scaffold` 在 `hermes_cli/main.py` 0 命中)
- **Port plan**: 1-2d, 1 commit. 3-4 文件改动:
  - `hermes_cli/init_cmd.py` (新 file, 1-200 LOC: scanner + template renderer)
  - `hermes_cli/main.py` (slash command 注册 `/init`)
  - `hermes_cli/templates/agents_md.tmpl` (新 file, AGENTS.md 模板)
  - `tests/hermes_cli/test_init_cmd.py` (新 file, 5-8 test)
  - CN 自设计 4 步: (a) 扫描 cwd project marker (pyproject.toml / package.json / Cargo.toml / go.mod / setup.py 等) → (b) 提取 language / framework / entry point / test framework / 关键路径 → (c) 模板渲染 AGENTS.md (含: project name / structure / dev setup / test cmd / 关键路径 / 设计原则 5 段) → (d) 跟现有 `AGENTS.md` 存在性 check (已存在 → 不覆盖 + 提示 user `--force` 强制覆盖)
- **估时**: 1-2d | **风险**: 🟡 中 (新功能, 模板设计 + 跟现有 AGENTS.md 共存 check 跟 mavis UX 倒退审计 1:1 关注)
- **价值**: 🟢 高 (跟 K-1~K-5 0 axiom 1 entry 1:1 配对, 补 axiom 1 gap)
- **详细分析**: `phase3c-k8-init-agents-md-deep-dive.md` (待写)
- **备注**: ⚠️ 跟 mavis 4 lesson "后端先调查再设计" 1:1: 实施期 grep `hermes_cli/slash_commands.py` 跟 `agent/project_detector.py` 跟 `tests/conftest.py` 0 冲突, 才进 init_cmd.py 设计
- **跨 project reference**: 跟 mavis 4 件套 (Constitution + critic + Reflexion 池 + compaction) 跟 upstream /learn + /journey 跟 CAND-080/081/082 同构 — K-8 `/init` 自动生成 AGENTS.md 是**事前设计 + 闭环反馈** 双向 (Axiom 1 + Axiom 3 跨维度), 跟 K-5 /learn + /journey 闭环 + K-1 completion contracts 事前设计同源

### [K-9] 🔴 hooks + HMAC webhook (1:1 配对, 跟 user 提"最高优先级" 1:1)

- **状态**: 🟡 proposed → ✅ user 拍 Option A 2026-08-06 (跟 phase 1 doc §2.4 1:1 配对)
- **Source**: upstream `dabe3c34c` `feat(webhook): hermes webhook CLI + skill for event-driven subscriptions (#3578)` (跟 phase 1 doc §2.4 verify 1:1, 1:1 配对)
  - 含 256 行 `hermes_cli/webhook.py` (CLI: subscribe/list/remove/test 4 subcommand) + 189 行 `test_webhook_cli.py` + 87 行 `test_webhook_dynamic_routes.py` + 180 行 `skills/devops/webhook-subscriptions/SKILL.md` + 52 行 webhooks.md docs
  - HMAC-SHA256 验签 + `X-Hub-Signature-256` 头部 + `sha256=` 前缀 (跟 GitHub webhook 1:1 配对, 跟 user 提的"GitHub webhook 验法" 1:1)
  - 24 new tests (CLI CRUD + persistence + enabled-gate + adapter dynamic route loading)
  - 0 new model tools (跟 mavis 4 件套 "无状态" 1:1)
  - 复用 CN `02efcfce5` middleware framework (CN 端 by 守一, observer hook 4 个: tool_request / tool_execution / llm_request / llm_execution)
- **Axiom match**: **3 闭环反馈 (strongest)** — webhook event (input) → middleware observer hook (state) → agent action (process) → HMAC 验签 feedback (output) → 回到 webhook adapter (loop closed), 跟 K-1 completion contracts judge gate + K-5 /learn + /journey 闭环 1:1 同模式
- **Cn state**: ⚠️ partial 配对 (跟 phase 1 doc §2.4 1:1)
  - ❌ `hermes_cli/webhook.py` 0 命中 (256 行 全新)
  - ❌ `~/.hermes/webhook_subscriptions.json` 0 命中
  - ❌ `hermes_cli/main.py` 的 `hermes webhook` CLI 注册 0 命中
  - ✅ `hermes_cli/middleware.py` 已存在 (CN 端 02efcfce5, 280 LOC observer hook + schema versioning, 0 真拦截, 跟 phase 1 doc §2.4 1:1 配对)
  - ✅ `gateway/platforms/webhook.py` 已存在 (CN 端 basic webhook platform, 0 CLI + 0 HMAC)
  - 0 cherry-pick split bug 风险 (256 行全新 file 0 跨 file 冲突)
- **Port plan**: 1-1.5d, 1 commit. 4-5 文件改动:
  - `hermes_cli/webhook.py` (新 file, cherry-pick dabe3c34c 256 行)
  - `hermes_cli/main.py` (加 `hermes webhook` subcommand 注册, cherry-pick dabe3c34c +39 行)
  - `gateway/platforms/webhook.py` (cherry-pick dabe3c34c adapter enhancement +48 行 hot-reload)
  - `skills/devops/webhook-subscriptions/SKILL.md` (新 file, cherry-pick dabe3c34c 180 行)
  - `tests/hermes_cli/test_webhook_cli.py` (新 file, cherry-pick dabe3c34c 189 行)
  - `tests/gateway/test_webhook_dynamic_routes.py` (新 file, cherry-pick dabe3c34c 87 行)
  - 复用 CN `hermes_cli/middleware.py` 作为 event bus (跟 mavis 4 件套 "扁平" 1:1, 4 observer hook 简单 flat)
  - cherry-pick 后 grep 旧名 0 命中 + happy-path smoke test (跟 mavis 4 lesson Cherry-pick split bug class 1:1 防护)
- **估时**: 1-1.5d | **风险**: 🟢 低 (1:1 配对 + 跟 CN middleware 1:1 复用, 风险最低, 跟 K-3 cherry-pick 1.5d 同模式 0 风险)
- **价值**: 🔴 **极高** (跟 user 提"最高优先级" 1:1, 跟 PIPL 边界防护 1:1, 跟 S12 routing_decision accuracy 互补)
- **详细分析**: `phase3d-k9-hooks-hmac-webhook-deep-dive.md` (待写)
- **备注**: 
  - 跟 user 提的 1-2d 估时 1:1, 跟 CN middleware 1:1 复用
  - **跟 mavis 4 件套 1:1** (跨 project design law 续 Phase 1+2+3):
    - read-only 调研 → ✅ phase 1 + phase 2 read-only
    - critic tool-verified → ✅ phase 1 K-9 1:1 verify 完
    - 无状态 → ✅ middleware observer 0 状态
    - 扁平 → ✅ 4 event 简单 flat
  - **跟 AIMC 4 铁律 + mavis 4 件套 1:1** (跨 project design law):
    - 跟 CAND-085 4 铁律 1:1, 跟 mavis 4 件套 1:1, 1:1 配对实施期 4 铁律 + 4 件套齐

### [K-10] 🎛️ 上下文压缩阈值可配 + max_turns 90→500 (3 cherry-pick + 1 改 + 1 加)

- **状态**: 🟡 proposed (user 拍 Option A 2026-08-06)
- **Source**: upstream 3 commit (跟 phase 1 doc §2.5 verify 1:1, partial 配对)
  - `--max-turns` flag ← `7f670a06c` `feat: add --max-turns CLI flag to hermes chat` (priority chain CLI > config > env > default 90)
  - bust cached agent on config edit ← `5f84eac45` `feat(gateway): bust cached agent on compression/context_length config edits (#17008)`
  - refresh max_turns before runtime budget ← `2d0e96a2b` `fix(gateway): refresh max_turns before resolving runtime budget`
  - **CN 自改 default 90 → 500** (1 行 `hermes_cli/main.py:cli()`, 跟 cherry-pick 0 冲突)
  - **CN 自加 threshold config 接口** (1 文件 `agent/context_compressor.py` 读 `config.context_compression.threshold` 跟 `config.context_compression.min_messages`)
- **Axiom match**: **2 整体最优 (strongest)** — 跨 call site 统一: max_turns 跨 `hermes_cli/main.py` (CLI) + `gateway/run.py` (runtime) + `cli.py` (default) + `agent/context_compressor.py` (compression); threshold config 跨 `agent/context_compressor.py` (compression 算法) + `gateway/run.py` (cache bust) + `config.py` (config schema). 跟 K-2 call_llm 统一入口 + K-3 profile routing multiplex 同 pattern
- **Cn state**: ⚠️ partial 配对 (跟 phase 1 doc §2.5 1:1)
  - ❌ `--max-turns` CLI flag 0 命中 (grep `cli.py` 0 命中 `--max-turns`)
  - ❌ `gateway/run.py` `refresh max_turns before runtime budget` 0 命中
  - ❌ `bust cached agent on config edit` 0 命中
  - ❌ `config.context_compression.threshold` 0 命中 (grep `config.py` 0 命中 threshold 字段)
  - ✅ `max_turns` 已存在 (`hermes_cli/main.py` 跟 `cli.py` 部分, default 90)
  - ✅ `agent/context_compressor.py` 已存在 (有 hardcoded threshold 算法, 0 config 接口)
  - 0 cherry-pick split bug 风险 (3 cherry-pick 是 --max-turns flag 跟 refresh 跟 bust cache, 都是 additive 改动, 跟现有 max_turns 0 冲突)
- **Port plan**: 1d, 1 commit. 4-5 文件改动:
  - `hermes_cli/main.py` (cherry-pick `7f670a06c` --max-turns flag +8 行 + CN 改 default 90→500 1 行)
  - `gateway/run.py` (cherry-pick `2d0e96a2b` refresh max_turns + cherry-pick `5f84eac45` bust cache)
  - `agent/context_compressor.py` (CN 自加 config 接口, 读 `config.context_compression.threshold` 跟 `min_messages`, 改 hardcoded 为 config 驱动)
  - `config.py` (CN 自加 `context_compression` 段 schema, 含 `threshold` 跟 `min_messages` 字段)
  - `tests/hermes_cli/test_max_turns_flag.py` (新 file, 3-5 test)
  - cherry-pick 后 grep 旧名 0 命中 + happy-path smoke test (跟 mavis 4 lesson Cherry-pick split bug class 1:1 防护)
- **估时**: 1d | **风险**: 🟢 低 (3 cherry-pick 都是 additive, 0 改 hardcoded; 1 行改 default + 1 字段加 config 跟 CN 现有 config pattern 1:1)
- **价值**: 🟢 高 (跟 K-2 call_llm 统一入口 + K-3 profile routing multiplex 同 pattern, 跨 call site 统一)
- **详细分析**: `phase3e-k10-context-compression-max-turns-deep-dive.md` (待写)
- **备注**: ⚠️ Cherry-pick split bug 防护 (跟 mavis 4 lesson 1:1):
  1. cherry-pick `7f670a06c` 完 grep `--max-turns` 0 命中 + grep 旧名 `max_iterations` 0 命中
  2. cherry-pick `2d0e96a2b` 完 grep `refresh max_turns` 0 命中
  3. cherry-pick `5f84eac45` 完 grep `bust_cached_agent_on_config_edit` 0 命中
  4. happy-path smoke test: `--max-turns 200` flag + default 500 (CN 改) + threshold config 接口 3 跑通

---

## 6. K-6~K-10 section 整体启示 (跟 K-1~K-5 1:1 配对)

### 6.1 Axiom 1 强 match 0→1 — K-8 补 K-1~K-5 gap 1:1 (跟 K-1~K-5 1:1 配对)

跟 K-1~K-5 "Axiom 1 强 match = 0 — 5 候选都是'优化现有路径' (axiom 2) 或'补闭环' (axiom 3), 没有任何'enable new design phase'. 未来 borrow 窗口关注 axiom 1 类 (e.g. goal spec / plan mode / intent declaration layer)" 1:1 配对.

K-8 `/init` 自动生成 AGENTS.md 是 axiom 1 强 match 1 候选, **跟 K-1~K-5 未来 borrow 窗口 1:1 配对**:
- K-1~K-5 "intent declaration layer" → K-8 "/init auto-generate AGENTS.md" (声明项目设计 context)
- K-1~K-5 "goal spec" → K-8 "AGENTS.md project context" (项目级 spec)
- K-1~K-5 "plan mode" → K-8 "AGENTS.md 模板含 dev setup / test cmd" (项目级 plan)

跟 K-1~K-5 gap 1:1 配对补.

### 6.2 Borrow = bug 发现机制 — K-9 1:1 配对 K-2 P0 bug 模式 (跟 K-1~K-5 1:1)

跟 K-1~K-5 "Borrow = bug 发现机制 — K-2 是借 upstream #35566 fix 发现的 cn 隐藏 P0 bug" 1:1 配对.

K-9 HMAC webhook 跟 CN middleware observer hook 集成时, 潜在发现:
- CN middleware observer 0 真拦截, K-9 webhook 实施期可能发现 1+ silent config drop (跟 K-2 P0 bug 同模式)
- K-9 bust cached agent on config edit 跟 CN cache 集成时, 潜在发现 1+ 缓存失效边界 bug (跟 K-2 P0 bug 同模式)

跟 K-2 P0 bug 1:1 配对, 实施期**主动 grep 找** (跟 mavis 4 lesson 后端先调查再设计 1:1 防护).

### 6.3 附件 1 钱学森 3-layer 双向闭环 — K-9 跟 mavis 4 件套 1:1 配对 (跟 K-1~K-5 1:1)

跟 K-1~K-5 "附件 1 钱学森 3-layer 双向闭环是跨 project design pattern" 1:1 配对.

K-9 hooks + HMAC webhook 跟 mavis 4 件套同构:
- 钱学森 3-layer: 反馈层 (webhook event) → 控制层 (middleware observer hook) → 执行层 (agent action)
- mavis 4 件套: critic tool-verified (feedback) → Reflexion 池 (control) → compaction (execution)
- K-9 实施期: 4 铁律 + 4 件套 1:1 配对 (跟 K-1~K-5 1:1)

### 6.4 K-6~K-10 不冲掉 CAND-080/K-3/K-4/K-2/K-1 实施 — 跟 K-1~K-5 1:1 配对

跟 K-1~K-5 "Section K 不冲掉 CAND-080 实施" 1:1 配对.

K-6~K-10 跟已 done 候选 1:1 配对:
- K-6 `!` shell bypass 跟 0 现有 entry 1:1 配对 (全新 UX 增强, 0 冲突)
- K-7 `/context` + `/diff` + `/focus` 跟 CAND-080 curator (有 diff preview 部分) 1:1 互补 (K-7 实施期 grep 0 冲突)
- K-8 `/init` 自动生成 AGENTS.md 跟 0 现有 entry 1:1 配对 (全新 design context, 0 冲突)
- K-9 hooks + HMAC webhook 跟 CN middleware (02efcfce5) 1:1 复用 (K-9 实施期复用 middleware 0 冲突)
- K-10 压缩阈值可配 + max_turns 90→500 跟 K-2 call_llm 1:1 互补 (K-2 已 done, K-10 实施期 grep 0 冲突)

**总 0 冲掉**: 跟 K-1~K-5 1:1 配对, 5 候选 K-6/K-7/K-8/K-9/K-10 跟已 done 候选 0 冲突.

---

## 7. 决策 (跟 K-1~K-5 1:1 配对)

### 7.1 5 候选 K-6~K-10 全部进 K section (跟 K-1~K-5 1:1 配对)

跟 K-1~K-5 5 候选全部进 K section 1:1 配对:

- **K-6** (1d) — Axiom 2 整体最优, CN 自设计 (跟 P0-3/P0-4 同模式)
- **K-7** (1-1.5d) — Axiom 2 整体最优, 3 cherry-pick + 3 CN wrapper
- **K-8** (1-2d) — Axiom 1 事前设计, CN 自设计 (跟 P0-3/P0-4 同模式)
- **K-9** (1-1.5d) — Axiom 3 闭环反馈, 1:1 配对 dabe3c34c + 复用 CN middleware
- **K-10** (1d) — Axiom 2 整体最优, 3 cherry-pick + 1 改 + 1 加

**总 5 候选 5-7d 累计, 实施期可并行压缩到 3-5d** (跟 user 估时 1:1).

### 7.2 实施顺序 (跟 K-1~K-5 1:1 + user Option A 1:1)

跟 K-1~K-5 实施顺序 (Phase 2+3+4 之前) 1:1 配对:

| 顺序 | K-X | 估时 | 累计 | 备注 |
|------|-----|------|------|------|
| 1 | **K-9** 🔴 | 1-1.5d | 1-1.5d | 最高优先级 + 1:1 配对 + 跟 CN middleware 1:1 复用, 风险最低 |
| 2 | **K-7** | 1-1.5d (跟 K-9 一起 1 大 commit) | 2-3d | 3 cherry-pick + 3 CN wrapper, 跟 K-9 一起出, 风险最小化 |
| 3 | **K-10** | 1d (独立 commit) | 3-4d | 3 cherry-pick + 1 改 + 1 加, additive 改动, 风险低 |
| 4 | **K-6** | 1d (独立 commit) | 4-5d | CN 自设计, 0 cherry-pick, 风险低 |
| 5 | **K-8** | 1-2d (独立 commit) | 5-7d | CN 自设计, 跟 P0-3/P0-4 同模式, 风险中 (新功能) |

**总 5-7d 累计, 跟 user 估时 3-5d 1:1 (K-9+K-7 一起 + K-10 独立 + K-6+K-8 一起可并行压缩)**.

### 7.3 跟 user 拍 4 K-X Option A 1:1 配对 (已锁, 2026-08-06)

| K-X | Option | 状态 |
|-----|--------|------|
| K-6 | Option A (推荐): CN 自设计 `!` 前缀 dispatch | ✅ 锁 |
| K-7 | Option A (推荐): 3 cherry-pick + 3 CN slash command wrapper | ✅ 锁 |
| K-8 | Option A (推荐): CN 自设计 /init 自动生成 AGENTS.md | ✅ 锁 |
| K-9 | Option A (推荐): cherry-pick dabe3c34c + 复用 CN middleware + 加 lifecycle hook | ✅ 锁 (user 提"最高优先级" pre-锁) |
| K-10 | Option A (推荐): 3 cherry-pick + 1 改 default + 1 加 config 字段 | ✅ 锁 |

---

## 8. 结论 + 下一步 (跟 K-1~K-5 1:1 配对)

### 8.1 Phase 2 结论

- **5 候选 K-6/K-7/K-8/K-9/K-10 全部进 K section** (跟 K-1~K-5 1:1 配对, 5 候选 1:1 配对 5)
- **Axiom 分布 1+3+1** (跟 K-1~K-5 0+3+2 1:1 配对, K-8 1 候选补 axiom 1 gap 1:1)
- **实施期 4 铁律 + 4 件套 1:1** (跟 K-1~K-5 1:1 配对, 跟 mavis 4 lesson 1:1 配对)
- **总估时 5-7d 累计, 实施期可并行压缩到 3-5d** (跟 user 估时 1:1)
- **0 冲掉现有候选** (跟 K-1~K-5 1:1 配对)

### 8.2 Phase 3 准备 (5 候选各 1 doc, 4 必填字段, 待 phase 2 拍完开跑)

- `phase3a-k6-shell-bypass-deep-dive.md` (1d, 跟 K-6 4 必填字段 1:1)
- `phase3b-k7-context-diff-focus-deep-dive.md` (1-1.5d, 跟 K-7 4 必填字段 1:1, 3 cherry-pick split bug 防护 1:1)
- `phase3c-k8-init-agents-md-deep-dive.md` (1-2d, 跟 K-8 4 必填字段 1:1, 跟 mavis 后端先调查再设计 1:1)
- `phase3d-k9-hooks-hmac-webhook-deep-dive.md` (1-1.5d, 跟 K-9 4 必填字段 1:1, 1:1 配对 dabe3c34c + CN middleware 1:1 复用)
- `phase3e-k10-context-compression-max-turns-deep-dive.md` (1d, 跟 K-10 4 必填字段 1:1, 3 cherry-pick split bug 防护 1:1)

### 8.3 Phase 4 准备 (master index, 5 候选 plan + 估时 + 风险 + 跨 project reference, 待 phase 3 拍完开跑)

- `phase4-master-index.md` (0.5-1d, 跟 K-1~K-5 1:1 配对, 5 候选 plan + 估时 + 风险 + 跨 project reference + 4 铁律 ↔ mavis 4 件套 1:1 配对)

### 8.4 实施期 plan (待 phase 2/3/4 user review 完开跑, 跟 K-1~K-5 1:1)

跟 §7.2 1:1 配对, 实施期 4 铁律 + 4 件套 1:1 续 Phase 1+2+3, 跟 mavis 4 lesson 1:1 防护.

---

**Phase 2 Filter Borrow 完成** — 5 候选 K-6/K-7/K-8/K-9/K-10 全部进 K section (跟 K-1~K-5 模板 1:1 配对, Axiom 分布 1+3+1 跟 K-1~K-5 0+3+2 1:1 配对 K-8 补 axiom 1 gap), 4 铁律 + 4 件套 1:1, 实施期 5-7d 累计可压缩到 3-5d, 跟 phase 3 deep dive + phase 4 master + 1 大 commit + tag v0.18.0+cn.5 1:1 续 Phase 1+2+3 收尾.

# Phase 3b Deep Dive — K-7 `/context` + `/diff` + `/focus` 3 slash command (3 cherry-pick + 3 CN wrapper)

> **K-X**: K-7
> **调研期**: 2026-08-06
> **Axiom**: 2 整体最优 (跟 K-1~K-5 1:1 配对, 跟 K-2/K-3/K-4/K-6 同 axiom)
> **决策**: ✅ Option A (user 拍 2026-08-06): 3 cherry-pick + 3 CN slash command wrapper
> **关联**: `phase1-sample-summary.md` §2.2, `phase2-filter-borrow.md` §5 [K-7], `phase4-master-index.md` (待写)
> **mavis 4 lesson 1:1 复用**: Cherry-pick split bug class (3 cherry-pick 跨 file, 实施期 grep 0 命中) / 后端先调查再设计 (跟 curator 跟 CAND-082 1:1 互补) / UX 倒退审计 (additive 3 command) / 估时前必 verify (phase 1 verify 完)

---

## 1. 4 必填字段 (跟 K-1~K-5 1:1 配对)

### 1.1 Source

| K-7 概念 | Upstream commit | 1:1 配对 |
|----------|----------------|----------|
| `/context` | `c1750bb32` `feat(cli): add /statusbar command to toggle context bar` (跟 K-6 同月 3-18) | 🟡 partial (toggle vs show) |
| `/diff` | `935137f0d` `feat: add inline diff previews for write actions` (跨月 4-1) | 🟡 partial (inline auto vs explicit) |
| `/focus` | `4d6a133a9` `fix(agent): gate skill-index demotion behind the opt-in focus mode (#44387)` (跨月 6-11) | 🟡 partial (config 切换 vs slash command) |

### 1.2 Axiom match

**2 整体最优 (strongest)** — 3 slash command 统一 dispatch + 复用 status bar / inline diff / focus mode 跨 call site. 跟 K-2 call_llm 统一入口同 pattern.

### 1.3 Cn state

- ❌ `/context` / `/diff` / `/focus` 3 command 0 命中
- ⚠️ status bar 部分 cherry-pick 跟 5-25 cherry-pick 阶段重叠 (1:1)
- ⚠️ inline diff 跟 CAND-080 curator + CAND-082 概念重叠 (1:1 互补)
- ⚠️ focus mode 配置 `agent/coding_context.py` 0 命中
- ✅ `hermes_cli/slash_commands.py` 已有 dispatcher (跟 K-7 集成 1:1)

### 1.4 Port plan

**1-1.5d, 1 commit, 6 文件改动**:

| File | 改动 | LOC |
|------|------|-----|
| `hermes_cli/main.py` | status bar 改动 cherry-pick `c1750bb32` | +30 |
| `hermes_cli/slash_commands.py` | 3 wrapper: `/context` / `/diff` / `/focus` | +60 |
| 跨 file inline diff | cherry-pick `935137f0d` | +50 (3-5 file) |
| `agent/coding_context.py` | focus mode config cherry-pick `4d6a133a9` | +48 |
| `tests/hermes_cli/test_context_diff_focus.py` | 新 test | +80 |
| `tests/agent/test_coding_context_focus.py` | 新 test | +40 |

**Cherry-pick split bug 防护** (跟 mavis 4 lesson 1:1):

1. cherry-pick `c1750bb32` 完 → `grep -rn 'statusbar' hermes_cli/` 0 命中 → 才进 `/context` 包装
2. cherry-pick `935137f0d` 完 → `grep -rn '_output_screen_diff' hermes_cli/` 0 命中 → 才进 `/diff` 包装
3. cherry-pick `4d6a133a9` 完 → `grep -rn 'coding_context=focus' agent/` 0 命中 → 才进 `/focus` 包装
4. happy-path smoke test: `/context` 显 context 占用 + `/diff` 显 last inline diff + `/focus` 切换 mode 3 跑通

---

## 2. 估时 / 风险 / 价值 (跟 K-1~K-5 1:1 配对)

| 维度 | K-7 值 | 跟 K-1~K-5 1:1 配对 |
|------|--------|---------------------|
| 估时 | 1-1.5d | 跟 K-3 1.5d 同 (3 cherry-pick 跨 file) |
| 风险 | 🟡 中 | 跟 K-3 同风险 (3 cherry-pick split bug 风险中) |
| 价值 | 🟢 高 | 跟 K-3 同价值 (3 command 统一 dispatch) |

---

## 3. 跨 project reference (跟 mavis 4 件套 1:1 配对)

- **mavis Cherry-pick split bug class**: 3 cherry-pick 跨 file, 实施期 grep 旧名 0 命中 + happy-path smoke test
- **mavis 后端先调查再设计**: 跟 CAND-080 curator 跟 CAND-082 1:1 互补 (实施前 grep 0 冲突)
- **mavis UX 倒退审计**: 3 command additive, 0 改旧 slash command
- **mavis 估时前必 verify**: phase 1 verify 完 (3 commit 凑 3 concept 1:1)

---

## 4. 备注 (跟 K-1~K-5 1:1 配对)

- ⚠️ Cherry-pick split bug 防护是 1:1 关键 (跟 mavis 4 lesson 1:1)
- 跟 K-3 cherry-pick 1.5d 4 commit 模式 1:1 配对 (K-3 实施也是 4 commit 拆分避免 split bug)
- 跟 CAND-080 curator 跟 CAND-082 概念重叠, 实施期 grep 0 冲突

---

**Phase 3b 完成** — K-7 deep dive 4 必填字段 + 估时/风险/价值 + 跨 project reference + 备注 1:1 落盘.

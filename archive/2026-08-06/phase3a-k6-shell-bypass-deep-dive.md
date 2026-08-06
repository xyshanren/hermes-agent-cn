# Phase 3a Deep Dive — K-6 `!` shell bypass (CN 自设计, 跟 P0-3/P0-4 同模式)

> **K-X**: K-6
> **调研期**: 2026-08-06
> **Axiom**: 2 整体最优 (跟 K-1~K-5 1:1 配对, 跟 K-2/K-3/K-4 同 axiom)
> **决策**: ✅ Option A (user 拍 2026-08-06): CN 自设计 `!` 前缀 dispatch
> **关联**: `phase1-sample-summary.md` §2.1, `phase2-filter-borrow.md` §5 [K-6], `phase4-master-index.md` (待写)
> **mavis 4 lesson 1:1 复用**: 后端先调查再设计 (实施前 grep 现有 dispatch 机制) / UX 倒退审计 (additive, 0 改旧) / 估时前必 verify (phase 1 verify 完) / Cherry-pick split bug class (0 cherry-pick 0 split bug 风险)

---

## 1. 4 必填字段 (跟 K-1~K-5 1:1 配对)

### 1.1 Source

- **Upstream**: 0 1:1 配对 (跟 phase 1 doc §2.1 verify 1:1, 5 周边 commit 不配对)
- **CN 端参考**:
  - `1b2d6c424` `fix: add --yes flag to bypass confirmation in /skills install and uninstall` (思路: bypass confirmation)
  - `c9a9db318` `feat(tools): persistent shell mode for local and SSH backends` (思路: persistent shell state)
  - `17f07aebd` `fix(security): close shell line-continuation bypass` (反向: 修补 bypass, 不新设计)
- **Pattern 参考**: P0-3 middleware + P0-4 message_timestamps (CANDIDATES.md line 19: "借鉴而非强制 cherry-pick ... 按 CN 现有架构自己实现")

### 1.2 Axiom match

**2 整体最优 (strongest)** — 跨所有 input / slash command 统一 `!` prefix dispatch 走 shell, 避免每 command 自己实现 shell bypass 局部最优. 跟 K-2 call_llm 统一入口同 pattern.

### 1.3 Cn state

- ❌ hermes_cli 0 `!` prefix logic (grep `hermes_cli/main.py` / `hermes_cli/commands.py` / `hermes_cli/slash_commands.py` 0 命中)
- ✅ 现有 shell 调用走 `terminal_tool.run_shell()` + approval gate
- ✅ `hermes_cli/main.py` 的 `parse_input()` 是 input parser 入口
- ✅ `hermes_cli/slash_commands.py` 是 slash command dispatcher
- ⚠️ UX 倒退审计点: `!` bypass 跟 approval gate 是 1:1 冲突点 (K-6 实施期需守住 approval gate 既有 happy path)

### 1.4 Port plan

**1d, 1 commit, 2 文件改动**:

| File | 改动 | LOC |
|------|------|-----|
| `hermes_cli/main.py` | input parser 加 `!` prefix detect | +15 |
| `hermes_cli/slash_commands.py` | slash command dispatcher 加 `!` prefix 优先级 (opt-in) | +10 |

**实施步骤** (跟 mavis 后端先调查再设计 1:1):

1. **Phase 0 实施前 grep** (跟 mavis 4 lesson 1:1):
   - `grep -rn '!.*shell\|shell.*!\|force.*shell\|bypass.*shell' hermes_cli/` (0 命中 = 0 冲突)
   - `grep -rn 'parse_input\|input.*parser' hermes_cli/main.py` (确认 input parser 入口)
   - `grep -rn 'approval.*gate\|confirm.*shell' hermes_cli/` (确认 approval gate 边界)
2. **`hermes_cli/main.py` 改**: 在 `parse_input()` 加 `!` prefix detect, 命中走 `terminal_tool.run_shell(force=True)`, 0 改 approval gate
3. **`hermes_cli/slash_commands.py` 改**: slash command dispatcher 优先级: `!` > `/` > 默认, `!` 走 `main.parse_input(force_shell=True)`
4. **Test 加**: `tests/hermes_cli/test_bang_shell_bypass.py` (5-7 test)
5. **UX 倒退审计**: 跑现有 test 0 regression, `!` prefix 为 opt-in (0 改旧 happy path)

---

## 2. 估时 / 风险 / 价值 (跟 K-1~K-5 1:1 配对)

| 维度 | K-6 值 | 跟 K-1~K-5 1:1 配对 |
|------|--------|---------------------|
| 估时 | 1d | 跟 K-3 1.5d 缩 0.5d (CN 自设计 0 cherry-pick) |
| 风险 | 🟢 低 | 跟 K-4 MoA ambient 0.5d 同风险, 0 cherry-pick split bug 风险 |
| 价值 | 🟡 中 | 跟 K-4 🟡 中同价值 (UX 增强, not core) |

---

## 3. 跨 project reference (跟 mavis 4 件套 1:1 配对)

- **mavis 后端先调查再设计**: 实施前 grep 现有 dispatch 机制 (跟 phase 1 1:1)
- **mavis UX 倒退审计**: `!` 前缀 opt-in, 0 改旧 happy path (跟 mavis 4 lesson 1:1)
- **mavis Cherry-pick split bug class**: 0 cherry-pick 0 split bug 风险
- **mavis 估时前必 verify**: phase 1 verify 完, 实施期不重新估时

---

## 4. 备注 (跟 K-1~K-5 1:1 配对)

- ⚠️ 跟 P0-3/P0-4 "参考 upstream 思路 CN 自行实现" 同模式 (跟 CANDIDATES.md line 19 P0-3 middleware 1:1 配对)
- 0 upstream commit 直接 cherry-pick, 但是借 upstream `1b2d6c424 --yes flag` 跟 `c9a9db318 persistent shell` 思路
- 跟 mavis 协作风格 1:1: "yes we can do it cheaply + 1 sketch" (跟 K-1~K-5 0 CN 自设计 entry 1:1 配对, K-6 是 CN 自设计 entry 1)

---

**Phase 3a 完成** — K-6 deep dive 4 必填字段 + 估时/风险/价值 + 跨 project reference + 备注 1:1 落盘, 跟 phase 3b/c/d/e 串行收尾.

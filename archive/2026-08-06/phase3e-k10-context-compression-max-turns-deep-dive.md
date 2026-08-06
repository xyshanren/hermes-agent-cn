# Phase 3e Deep Dive — K-10 上下文压缩阈值可配 + max_turns 90→500 (3 cherry-pick + 1 改 + 1 加)

> **K-X**: K-10
> **调研期**: 2026-08-06
> **Axiom**: 2 整体最优 (跟 K-1~K-5 1:1 配对, 跟 K-2/K-3/K-4/K-6/K-7 同 axiom)
> **决策**: ✅ Option A (user 拍 2026-08-06): 3 cherry-pick + 1 改 default + 1 加 config 字段
> **关联**: `phase1-sample-summary.md` §2.5, `phase2-filter-borrow.md` §5 [K-10], `phase4-master-index.md` (待写)
> **mavis 4 lesson 1:1 复用**: Cherry-pick split bug class (3 cherry-pick 跨 file, 实施期 grep 0 命中) / 后端先调查再设计 (跟 max_turns 现有路径 1:1) / UX 倒退审计 (additive config 字段) / 估时前必 verify (phase 1 verify 完)

---

## 1. 4 必填字段 (跟 K-1~K-5 1:1 配对)

### 1.1 Source

| K-10 概念 | Upstream commit | 1:1 配对 |
|----------|----------------|----------|
| `--max-turns` flag | `7f670a06c` `feat: add --max-turns CLI flag to hermes chat` (3-31, priority chain CLI > config > env > default 90) | ✅ partial (expose flag) |
| bust cached agent on config edit | `5f84eac45` `feat(gateway): bust cached agent on compression/context_length config edits (#17008)` | ✅ partial (config 改动 bust cache) |
| refresh max_turns before runtime budget | `2d0e96a2b` `fix(gateway): refresh max_turns before resolving runtime budget` | ✅ partial (refresh 避免 stale) |
| **CN 自改 default 90 → 500** | 0 (1 行 `hermes_cli/main.py:cli()`) | 🔴 (跟 user 提 1:1) |
| **CN 自加 threshold config 接口** | 0 (1 文件 `agent/context_compressor.py` + `config.py`) | 🔴 (跟 user 提 1:1) |

### 1.2 Axiom match

**2 整体最优 (strongest)** — 跨 call site 统一: max_turns 跨 `hermes_cli/main.py` (CLI) + `gateway/run.py` (runtime) + `cli.py` (default) + `agent/context_compressor.py` (compression); threshold config 跨 `agent/context_compressor.py` (compression 算法) + `gateway/run.py` (cache bust) + `config.py` (config schema). 跟 K-2 call_llm 统一入口 + K-3 profile routing multiplex 同 pattern.

### 1.3 Cn state

- ❌ `--max-turns` CLI flag 0 命中
- ❌ `gateway/run.py` `refresh max_turns before runtime budget` 0 命中
- ❌ `bust cached agent on config edit` 0 命中
- ❌ `config.context_compression.threshold` 0 命中
- ✅ `max_turns` 已存在 (`hermes_cli/main.py` 跟 `cli.py` 部分, default 90)
- ✅ `agent/context_compressor.py` 已存在 (有 hardcoded threshold 算法, 0 config 接口)
- ✅ `config.py` 已存在 (跟 K-10 加 context_compression 段 1:1)
- 0 cherry-pick split bug 风险 (3 cherry-pick 是 --max-turns flag 跟 refresh 跟 bust cache, 都是 additive 改动, 跟现有 max_turns 0 冲突)

### 1.4 Port plan

**1d, 1 commit, 4-5 文件改动**:

| File | 改动 | LOC |
|------|------|-----|
| `hermes_cli/main.py` | cherry-pick `7f670a06c` --max-turns flag +8 行 + CN 改 default 90→500 1 行 | +9 |
| `gateway/run.py` | cherry-pick `2d0e96a2b` refresh max_turns + cherry-pick `5f84eac45` bust cache | +30 (2 commit) |
| `agent/context_compressor.py` | CN 自加 config 接口, 读 `config.context_compression.threshold` 跟 `min_messages` | +20 |
| `config.py` | CN 自加 `context_compression` 段 schema, 含 `threshold` 跟 `min_messages` 字段 | +15 |
| `tests/hermes_cli/test_max_turns_flag.py` | 新 test, 3-5 test | +60 |

**Cherry-pick split bug 防护** (跟 mavis 4 lesson 1:1):

1. cherry-pick `7f670a06c` 完 → `grep -rn '--max-turns' hermes_cli/` 0 命中 + `grep -rn 'max_iterations' hermes_cli/` 0 命中
2. cherry-pick `2d0e96a2b` 完 → `grep -rn 'refresh max_turns' gateway/` 0 命中
3. cherry-pick `5f84eac45` 完 → `grep -rn 'bust_cached_agent_on_config_edit' gateway/` 0 命中
4. happy-path smoke test: `--max-turns 200` flag + default 500 (CN 改) + threshold config 接口 3 跑通

**CN 改 default 90 → 500** (跟 user 估时 1d 1:1):

```python
# hermes_cli/main.py:cli() 改 1 行
- default=90,
+ default=500,
```

**CN 加 threshold config 接口** (跟 user 提 1:1):

```python
# agent/context_compressor.py 改 hardcoded → config 驱动
- if compression_ratio > 0.5:  # hardcoded
+ threshold = getattr(config.context_compression, "threshold", 0.5)
+ if compression_ratio > threshold:
```

```yaml
# config.py DEFAULT_CONFIG 加段
context_compression:
  threshold: 0.5  # default, 跟 user 提的"可配" 1:1
  min_messages: 10  # 最小消息数
```

---

## 2. 估时 / 风险 / 价值 (跟 K-1~K-5 1:1 配对)

| 维度 | K-10 值 | 跟 K-1~K-5 1:1 配对 |
|------|---------|---------------------|
| 估时 | 1d | 跟 K-2 0.5d +0.5d (3 cherry-pick + 1 改 + 1 加 vs K-2 1 cherry-pick) |
| 风险 | 🟢 低 | 跟 K-2 🟢 低 1:1 (additive 改动, 1 行改 + 1 字段加) |
| 价值 | 🟢 高 | 跟 K-2 🟢 高 1:1 (跨 call site 统一, 跟 call_llm 同 pattern) |

---

## 3. 跨 project reference (跟 mavis 4 件套 1:1 配对)

- **mavis Cherry-pick split bug class**: 3 cherry-pick 跨 file, 实施期 grep 旧名 0 命中 + happy-path smoke test
- **mavis 后端先调查再设计**: 跟 max_turns 现有路径 1:1 (跟 K-2 call_llm 7 call sites 同模式)
- **mavis UX 倒退审计**: additive config 字段, 0 改旧 threshold 算法
- **mavis 估时前必 verify**: phase 1 verify 完 (3 cherry-pick + 1 改 + 1 加 全 verify)

**跨 project reference (跟 K-1~K-5 1:1 配对)**:

- 跟 K-2 call_llm 统一入口同 pattern (跨 call site 统一: 5 个 direct-create aux caller 整合到 call_llm)
- 跟 K-3 profile routing multiplex 同 pattern (跨 platform adapter 统一: 6 adapter 统一处理)

---

## 4. 备注 (跟 K-1~K-5 1:1 配对)

- ⚠️ Cherry-pick split bug 防护是 1:1 关键 (跟 mavis 4 lesson 1:1)
- default 90 → 500 是 1 行 CN 改 (跟 user 提 1:1, 跟 upstream `41877183b` 改 default 90 反向)
- threshold config 接口是 1 文件 CN 加 (跟 user 提"可配" 1:1, upstream 0 暴露)
- 跟 K-2 0.5d 7 call sites 1:1 配对 (K-10 3 cherry-pick + 1 改 + 1 加 是 K-2 1 cherry-pick + 7 call sites 的扩展版)

---

**Phase 3e 完成** — K-10 deep dive 4 必填字段 + 估时/风险/价值 + 跨 project reference + 备注 1:1 落盘, 5 候选 K-6/K-7/K-8/K-9/K-10 全部 deep dive 完, 跟 phase 4 master 1:1 配对.

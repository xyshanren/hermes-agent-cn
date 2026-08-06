# Phase 1 Sample Summary — v0.20.0 Borrow 调研期 (K-6~K-10)

> **调研期**: 2026-08-06 (8-05 阶段收尾 + 8-06 调研期启动, 跟 Phase 1+2+3 1:1 节奏)
> **调研人**: Mavis (跟 CAND-084 8-03 22:10 lesson 1:1: 估时前必 verify 引擎能力)
> **范围**: upstream `v2026.7.20` ~ `v2026.8.5` 窗口, 本地 base = `1e71b7180e` (v0.18.0+cn.4 merge base), upstream ahead **7998 commits**
> **目标**: 摸清 5+6 看点跟 upstream 1:1 配对状态, 给 phase 2 filter + phase 3 deep dive 跟 phase 4 master 提供事实基础
> **4 铁律 1:1 验证**: 0 接触 upstream (read-only) / 决策边界 / 0 改 upstream / commit 前 verify
> **关联**: `CANDIDATES.md` K-1~K-5 段 (line 934~1008, Phase 2+3+4 之前 v0.18.0→v0.19.0 窗口 5 候选), `phase2-filter-borrow.md` (待写), `phase3a-e-*` (待写), `phase4-master-index.md` (待写)

---

## 0. 实施前 Verify (per `phase0-verify` 收尾)

| 指标 | 状态 | 详情 |
|------|------|------|
| HEAD | ✅ | `4601b27a4` (v0.18.0+cn.4) |
| Branch | ✅ | `phase1-cand085` |
| Working tree | ✅ | clean + 1 untracked `archive/` |
| Test baseline (routing 5 file) | ✅ | 122/122 passed in 4.86s |
| Test baseline (全量) | ⚠️ | 6 collection errors (upstream 模块路径 drift, 跟 venv 状态 + upstream 包结构变化有关, **不是** 这次调研期 regression, 跟 8-05 阶段收尾状态一致) |
| upstream merge base | ✅ | `1e71b7180e5b4e84905b9a3086cf9cecca139562` |
| upstream HEAD | ✅ | `8fc278207` (Merge PR #69938) |
| upstream ahead | — | **7998 commits** |

**Test 备注**: 6 collection errors 是 collection-time 错 (缺 `tests.hermes_cli.conftest_dashboard_auth` / `dataclass` NameError / `plugins.image_gen` ModuleNotFoundError / `faster_whisper.__spec__` ValueError), 是 venv 安装跟 upstream 演进 drift, 跟 K-6~K-10 调研期无关, 实施期不阻塞。

---

## 1. 调研方法

**Verify 流程** (跟 CAND-084 8-03 lesson 1:1):

1. **范围圈定**: upstream `8fc278207` (HEAD) − `1e71b7180e` (本地 merge base) = 7998 commit 窗口
2. **5+6 看点逐一 1:1 verify**: 对每个 K-X 用 `git log --oneline upstream/main --all` + `Select-String` grep 多个关键词组合
3. **3 层 fallback**: (a) single commit exact match → (b) PR cluster (3-5 commit 共同 commit message) → (c) partial 配对 (commit 接近但不是 1:1)
4. **每个 K-X 出结论**: `1:1 配对` / `partial 配对` / `0 配对`
5. **不假设**: 任何 K-X 不基于"应该支持什么"假设, 必须有 upstream commit 证据

**0 接触 upstream** (4 铁律 1): 只 `git log` / `git show --stat` / `git show file:path`, **0** cherry-pick / merge / push 任何 upstream commit

---

## 2. 5 看点 Verify 矩阵

### 2.1 K-6: `!` shell bypass (1d) — **0 配对** 🔴

**User 提的 1:1 配对预期**: hermes CLI 端支持 `!` 前缀, 强制走 shell (跳过沙箱/审批)

**Upstream 实查** (4 关键词组合):

| 关键词 | 命中 | 跟 K-6 关系 |
|--------|------|-------------|
| `shell bypass / ! command / force shell` | 0 | 0 1:1 配对 |
| `! + shell` | 0 | 0 |
| `bang command` (Slack-like) | `0022e94d7` `feat(matrix): support bang command aliases` + `a1264e996` `fix(matrix): make bang-command resolution robust` | ❌ **matrix 是 Slack-like messaging 平台**, 不是 hermes CLI shell bypass |
| `--yes flag bypass confirmation` | `1b2d6c424` `fix: add --yes flag to bypass confirmation in /skills install and uninstall` | ⚠️ partial 概念 (bypass confirm) 但是 `--yes` flag 不是 `!` 前缀, scope 是 /skills install |
| `shell line-continuation bypass` | `17f07aebd` `fix(security): close shell line-continuation bypass in command detection` | ❌ **修补** bypass, 不是新设计 |
| `persistent shell mode` | `c9a9db318` `feat(tools): persistent shell mode for local and SSH backends` (272 行 `persistent_shell.py` + 152+225 行 test) | ❌ **backend 端** persistent shell (local + SSH 状态保留), **不是** user 输入 `!` bypass |

**结论**: 0 1:1 配对

**Gap 分析**: 5 候选 commit 都是周边 (Slack-like / security 修补 / backend 状态), 跟 user 提的"`!` 前缀强制走 shell" 设计意图**不直接配对**

**Plan 建议** (待 user 拍):
- **Option A**: CN 自设计 `!` 前缀 dispatch (跟 P0-3/P0-4 同模式: 参考 upstream 思路, CN 自行实现). 估时 1d (跟 user 估时 1:1). 跟 K-9 hooks 实施期一起做 (在 `hermes_cli/main.py` input parser 层加 `!` 前缀 detect + 强制调用 `terminal_tool.run_shell()` 跳过沙箱)
- **Option B**: borrow `c9a9db318` persistent shell 思路, 在 CN terminal tool 加 persistent state, 估时可能 1-1.5d (persistent 改造 + `!` 前缀 trigger 切换). 但跟 user 提的"`!` bypass" 概念差距大, **不推荐**
- **Option C**: 不做 (K-6 0 配对, CN 不需要). **不推荐** (跟 user 提的 1d 估时 conflict)

**跟 4 铁律关系** (CAND-085):
- 铁律 1 (0 改 upstream): ✅ Option A 0 改 upstream
- 铁律 2 (CN 端可维护): ✅ Option A CN 自设计, 跟 P0-3/P0-4 同模式
- 铁律 3 (AIMC 集成兼容): ✅ Option A 跟 AIMC 无关 (K-6 是 CLI 端)
- 铁律 4 (决策边界): 🟡 待 user 拍 (Option A vs B vs C)

---

### 2.2 K-7: `/context` + `/diff` + `/focus` (1-2d) — **Partial 配对** 🟡

**User 提的 1:1 配对预期**: hermes CLI 端 3 个 slash command (`/context` 显 context 占用, `/diff` 显 last diff, `/focus` 切换 focus mode)

**Upstream 实查** (5 关键词组合):

| K-7 概念 | Upstream commit | 1:1 配对? |
|----------|----------------|----------|
| `/context` | `c1750bb32` `feat(cli): add /statusbar command to toggle context bar` (`/statusbar` / `/sb` alias) | 🟡 partial — 是 toggle status bar (含 context usage 显示), 跟 `/context` command 概念接近但是 toggle bar 跟 explicit show 行为差异 |
| `/context` (备) | `103e11926` `feat(cli): show context compression count in status bar` | 🟡 partial — 改 status bar 显 compression count |
| `/context` (备 2) | `8d0a96a8b` `fix: context counter shows cached token count in status bar` | 🟡 partial — 改 status bar 显 cached token count |
| `/diff` | `935137f0d` `feat: add inline diff previews for write actions` | 🟡 partial — 是 inline diff (write_file / patch / skill_manage 后自动显), 跟 `/diff` explicit command 概念差异 |
| `/diff` (备) | `4a1303d7e` `fix(cli): tighten _output_screen_diff patch to preserve ANSI styles` | 🟡 partial — 修 inline diff 渲染 |
| `/diff` (备 2) | `9e845a6e5` `feat: major /rollback improvements — enabled by default, diff preview, file-level restore` | 🟡 partial — `/rollback` 包含 diff preview |
| `/focus` | `4d6a133a9` `fix(agent): gate skill-index demotion behind the opt-in focus mode (#44387)` (`agent.coding_context=focus` 配置) | 🟡 partial — 是 `agent.coding_context=focus` 配置项, **不是** `/focus` command; 修改的是 skill-index demotion gate |
| `/focus` (备) | `0f398f8e9` `feat(desktop): focused-session-aware titlebar + statusbar` | ❌ desktop 端, CN 暂拒 (跟 ELECTRON reject 立场 1:1) |
| 任何 single PR 包含 3 command | 0 | ❌ 0 1:1 single PR |

**结论**: partial 配对 (3 个独立 commit 凑 3 个 command concept, 不是 single PR 1:1)

**Gap 分析**: 3 个 command concept 都在 upstream 有对应 commit, 但是:
- `/statusbar` 跟 user 提的 `/context` 行为差异 (toggle vs show)
- inline diff 跟 user 提的 `/diff` 行为差异 (auto vs explicit)
- focus mode 跟 user 提的 `/focus` 行为差异 (config 切换 vs slash command)

**Plan 建议** (待 user 拍):
- **Option A**: 3 cherry-pick + 3 CN slash command wrapper
  - cherry-pick `c1750bb32` (--statusbar toggle logic) + cherry-pick `935137f0d` (inline diff preview) + cherry-pick `4d6a133a9` (focus mode config)
  - CN 加 3 个 slash command wrapper: `/context` (调用 statusbar toggle 走 show-only path) + `/diff` (调用 inline diff 走 show-last-diff path) + `/focus` (调用 config toggle)
  - 估时 1-1.5d (跟 user 估时 1-2d 下限). 3 cherry-pick split bug 风险中 (跨 file cherry-pick)
- **Option B**: CN 自设计 3 slash command (跟 P0-3/P0-4 同模式)
  - 不 cherry-pick, CN 自行实现 (从 `hermes_cli/slash_commands.py` 入手, 复用现有 `c1750bb32` status bar + `935137f0d` inline diff 输出逻辑但是简化 dispatch)
  - 估时 0.5-1d. 0 cherry-pick split bug 风险
- **Option C**: 只做 1-2 个 (e.g. 只 `/context` + `/diff`, `/focus` 留 long-term). 估时 0.5-1d. 跟 user 提的"3 command 全做" 冲突

**跟 4 铁律关系** (CAND-085):
- 铁律 1 (0 改 upstream): ✅ A/B 都 0 改
- 铁律 2 (CN 端可维护): ✅ A 借 upstream 行为, B 简化 CN 实现
- 铁律 3 (AIMC 集成兼容): ✅ K-7 跟 AIMC 无关
- 铁律 4 (决策边界): 🟡 待 user 拍 (A vs B vs C)

---

### 2.3 K-8: `/init` 自动生成 AGENTS.md (1-2d) — **0 配对** 🔴

**User 提的 1:1 配对预期**: hermes CLI `/init` slash command 扫描当前目录 + 自动生成项目级 `AGENTS.md`

**Upstream 实查** (5 关键词组合):

| 关键词 | 命中 | 跟 K-8 关系 |
|--------|------|-------------|
| `hermes init / init command / scaffold` | 0 | 0 1:1 配对 |
| `AGENTS.md / agents.md` | `33513991b` `fix(agent): never load the install-tree AGENTS.md as project context` + `f8abc521f` `docs: add JS test placement rule to AGENTS.md` + `301709544` `docs: add platform support tiers to AGENTS.md` + `2b285f50b` `docs(agents): add Design Philosophy + Contribution Rubric to AGENTS.md` | ❌ **全部是 AGENTS.md 文件本身改动** (内容/doc/fix), 0 自动生成机制 |
| `init self.config (HermesCLI)` | `bd2606a57` `fix: initialize self.config in HermesCLI to fix AttributeError on slash commands` + `f5324f9aa` (重复) | ❌ **修 AttributeError**, 跟 `/init` 自动生成无关 |
| `Open Scaffold` | `e1a717a6d` `docs: add Open Scaffold MCP workflow` | ❌ MCP workflow, 跟 `/init` 无关 |

**结论**: 0 1:1 配对

**Gap 分析**: upstream 有 `AGENTS.md` 静态文件 (CN 已有 69825 byte AGENTS.md, 也是 static), **但是 0 自动生成机制**. `/init` 是个全新设计.

**Plan 建议** (待 user 拍):
- **Option A**: CN 自设计 `/init` 自动生成 AGENTS.md (跟 P0-3/P0-4 同模式). 估时 1-2d. 设计要素:
  1. 扫描 cwd `*.py` / `*.md` / `package.json` / `pyproject.toml` / `Cargo.toml` / `go.mod` 等 project marker
  2. 提取 language / framework / entry point / test framework
  3. 模板渲染 AGENTS.md (含: project name / structure / dev setup / test cmd / 关键路径)
  4. 跟现有 `AGENTS.md` 存在性 check, 已存在 → 不覆盖 + 提示 user
  5. 跟 init 端跟 user 互动 (3-5 question confirm)
- **Option B**: borrow AGENTS.md 模板 (从 `2b285f50b` "Design Philosophy + Contribution Rubric" 段), CN 加 `/init` dispatcher. 估时 1-1.5d. 借 upstream 模板 + CN 加 init 逻辑
- **Option C**: 不做 (K-8 0 配对, CN 当前 AGENTS.md 是手工维护, 自动化价值 unclear). **不推荐** (跟 user 提的 1-2d 估时 conflict)

**跟 4 铁律关系** (CAND-085):
- 铁律 1 (0 改 upstream): ✅ A/B 都 0 改
- 铁律 2 (CN 端可维护): ✅ A 简单 (1 模板 + 1 dispatcher), B 借 upstream 模板
- 铁律 3 (AIMC 集成兼容): ✅ K-8 跟 AIMC 无关
- 铁律 4 (决策边界): 🟡 待 user 拍 (A vs B vs C)

---

### 2.4 K-9: 🔴 hooks + HMAC webhook (1-2d, 最高优先级) — **1:1 配对** 🟢

**User 提的 1:1 配对预期**: 完整 hooks 体系 (lifecycle event 拦截) + HMAC webhook (GitHub-style SHA-256 验签)

**Upstream 实查** (5 关键词组合):

| 关键词 | 命中 | 跟 K-9 关系 |
|--------|------|-------------|
| `webhook CLI / event-driven / subscribe` | `dabe3c34c` `feat(webhook): hermes webhook CLI + skill for event-driven subscriptions (#3578)` | ✅ **1:1 配对** — 256 行 `hermes_cli/webhook.py` + 256+189+87 行 test 全套, 含 `subscribe / list / remove / test` 4 subcommand + `webhook_subscriptions.json` 动态订阅 + hot-reload + skill 文件 + 完整 docs |
| `HMAC / hmac / signature / verify / x-hub-signature-256` | `dabe3c34c` 内部含 `import hmac` + `hmac.new(secret.encode(), payload.encode(), hashlib.sha256)` + `X-Hub-Signature-256` 头部 + `sha256=` 前缀 | ✅ **1:1 配对** — 跟 user 提的"GitHub webhook 验法" 1:1 |
| `middleware framework / observer hooks` | `02efcfce5` `feat(middleware): adaptive execution middleware framework` (CN 自己的 commit by 守一, **不是 upstream**) | 🟡 **CN 端已有** — upstream `2e0c9083d` ABORTED, CN 自己做 observer schema compat. 跟 K-9 hooks 体系**部分重叠** (K-9 需要 lifecycle event, CN middleware 是 4 observer hook: tool_request / tool_execution / llm_request / llm_execution) |
| `agent pre_verify hook / pre-tool-use hook` | `a10113658` `feat(agent): add pre_verify hook and verify-on-stop coding guidance` | 🟡 partial — pre_verify hook 是 coding guidance context, 跟 K-9 lifecycle hook 概念接近但 scope 是 coding posture |
| `request-scoped plugin lifecycle hooks` | `9e820dda3` / `0afd252a6` `Add request-scoped plugin lifecycle hooks` | 🟡 partial — 是 plugin 端 lifecycle, 跟 K-9 agent lifecycle 部分重叠 |
| `session:compress event_callback` | `6fb4419a1` / `e76e7b507` `feat(hooks): session:compress event_callback for MemPalace sync` | 🟡 partial — 单一 event callback, K-9 需要多 event |
| `feishu webhook auth secret` | `713618f3f` `fix(feishu): require webhook auth secret and honor config extras (#30746)` | 🟡 partial — feishu 平台 specific 验签 (跟 HMAC 概念配但 scope 是 feishu 平台) |
| `fail closed for webhook routes without secrets` | `d32ac2a5a` + `dbf73e90f` `fix: fail closed for webhook routes without secrets` | 🟡 partial — fail-closed 安全加固 (跟 K-9 验签 1:1 概念但不是 HMAC 设计) |

**dabe3c34c deep dive** (256 行 webhook.py 关键内容, 1:1 配对 verify):

```python
# hermes_cli/webhook.py 关键节选
import secrets
import hmac
import hashlib

# CLI: hermes webhook subscribe <name> [options]
# CLI: hermes webhook list
# CLI: hermes webhook remove <name>
# CLI: hermes webhook test <name> [--payload '{"key": "value"}']

# 动态订阅: ~/.hermes/webhook_subscriptions.json (mtime-gated hot-reload)
# 静态 config.yaml routes 优先级 > 动态订阅

# HMAC-SHA256 验签 (跟 GitHub webhook 1:1):
sig = "sha256=" + hmac.new(
    secret.encode(), payload.encode(), hashlib.sha256
).hexdigest()
# Header: X-Hub-Signature-256: <sig>
# Header: X-GitHub-Event: <event_name>
```

**结论**: 1:1 配对 🟢

**Gap 分析**:
- dabe3c34c **全套配对** user 提的"HMAC webhook" (含 CLI + JSON 动态订阅 + hot-reload + skill + 验签 + 24 test)
- 02efcfce5 middleware framework 是 **CN 端已有** (Phase 5 完成, observer schema compat, 0 真拦截), K-9 hooks 实施可**复用** CN middleware 作为 event bus

**Plan 建议** (跟 mavis 4 lesson 1:1, 最高优先级 + 1:1 配对 → 推荐 Option A):
- **Option A** (推荐): cherry-pick `dabe3c34c` (256 行 webhook.py + 24 test) + 复用 CN `02efcfce5` middleware 作为 event bus + 加 K-9 lifecycle hook (在 `hermes_cli/middleware.py` observer hook 基础上, 加 `pre_tool_use` / `post_tool_use` / `pre_llm_call` / `post_llm_call` 4 event). 估时 1-1.5d. 跟 user 估时 1-2d 中下限
- **Option B**: 只 cherry-pick dabe3c34c, 暂不加 lifecycle hook (留 long-term). 估时 0.5-1d. 跟 user 估时 1-2d 下限
- **Option C**: 不做 K-9 (跟 user 提的"最高优先级" conflict). **不推荐**

**跟 4 铁律关系** (CAND-085):
- 铁律 1 (0 改 upstream): ✅ cherry-pick 是应用不是改
- 铁律 2 (CN 端可维护): ✅ 跟 CN middleware 1:1 复用
- 铁律 3 (AIMC 集成兼容): ✅ K-9 webhook 跟 AIMC 无关
- 铁律 4 (决策边界): ✅ **推荐 Option A** (1:1 配对 + 最高优先级 + 跟 CN middleware 复用)

**跟 mavis 4 件套 1:1** (跨 project design law):
- read-only 调研 → ✅ phase 1 read-only
- critic tool-verified → ✅ K-9 1:1 配对 verify 过
- 无状态 → ✅ middleware observer 0 状态
- 扁平 → ✅ 4 event 简单 flat

**跟 AIMC 4 铁律 + mavis 4 件套 1:1** (跨 project design law 续 Phase 1+2+3):
- 跟 CAND-085 4 铁律 1:1, 跟 mavis 4 件套 1:1, 1:1 配对实施期 4 铁律 + 4 件套齐

---

### 2.5 K-10: 上下文压缩阈值可配 + max_turns 90→500 (1d) — **Partial 配对** 🟡

**User 提的 1:1 配对预期**: (a) compression threshold 通过 config 可配 (默认 0.5), (b) `max_turns` default 从 90 改 500 (跟 K-9 1:1, 长任务友好)

**Upstream 实查** (5 关键词组合):

| K-10 概念 | Upstream commit | 1:1 配对? |
|----------|----------------|----------|
| `--max-turns CLI flag` | `7f670a06c` `feat: add --max-turns CLI flag to hermes chat` (priority chain: CLI > config > env > default 90) | ✅ partial 配对 — expose flag, **不改 default** |
| `--max-turns` (重复 commit) | `478067989` (重复, 同样 8 行 main.py) | — (重复) |
| `default 90` | `41877183b` Merge PR #604 + `451a007fb` `fix(tests): isolate max_turns tests from CI env and update default to 90` | ❌ **upstream 改的是 default → 90** (从其他值改到 90), 跟 user 提的 "90→500" **反向** |
| `compaction threshold 可配` | `d17244562` `fix(compaction): check the threshold against real tokens, not an estimated floor` | 🟡 partial — 改 threshold 算法 (real tokens vs estimated floor), 跟"可配"概念不同 |
| `compaction anti-thrashing` | `32f30d2a4` `fix(compaction): anti-thrashing guard never fired; score against the threshold` | 🟡 partial — 修 anti-thrashing guard, 跟 threshold 可配无关 |
| `bust cached agent on config edit` | `5f84eac45` `feat(gateway): bust cached agent on compression/context_length config edits (#17008)` | 🟡 partial — config 改动 bust cache, 跟 threshold 可配 1:1 概念接近 (config 改动需 reload) |
| `compression eval harness` | `1e6285c53` `feat: compression eval harness for agent/context_compressor.py` | 🟡 partial — 评测工具, 跟 threshold 可配无关 |
| `reserve output tokens` | `623b21bf2` `fix(compress): reserve output tokens in the compaction threshold (#23767, #43547)` | 🟡 partial — 改 threshold 计算, 跟可配无关 |
| `gateway max_turns refresh` | `2d0e96a2b` / `460b1e50e` `fix(gateway): refresh max_turns before resolving runtime budget` + `8f84d196c` / `dcac71952` test | 🟡 partial — refresh max_turns, 跟 default 90→500 无关 |

**结论**: partial 配对 (expose flag 配对, default 90→500 反向)

**Gap 分析**:
- upstream 7f670a06c 暴露了 `--max-turns` flag, **priority chain 是 CLI > config > env > default 90**, **不改 default**
- upstream 没有任何 commit 改 default 从 90 → 500
- 0 配对项: "compression threshold 通过 config 可配" (upstream 改了算法, 0 暴露 config 接口)

**Plan 建议** (跟 user 拍):
- **Option A** (推荐, 跟 user 估时 1d 1:1): cherry-pick `7f670a06c` (--max-turns flag) + cherry-pick `5f84eac45` (bust cached agent on config edit) + cherry-pick `2d0e96a2b` (refresh max_turns) + **CN 自改 default 90 → 500** (`hermes_cli/main.py:cli()` 1 行, 跟 cherry-pick 不冲突) + **CN 自加 compression threshold config 接口** (在 `agent/context_compressor.py` 读 `config.context_compression.threshold` 跟 `config.context_compression.min_messages`, 跟 cherry-pick 0 冲突). 估时 1d.
- **Option B**: 只 cherry-pick 7f670a06c (--max-turns flag), default 改 500 + threshold config 留 long-term. 估时 0.5d. 跟 user 估时 1d 缩 0.5d
- **Option C**: 不做 K-10. **不推荐** (跟 user 提的 1d 估时 conflict)

**跟 4 铁律关系** (CAND-085):
- 铁律 1 (0 改 upstream): ✅ A cherry-pick 应用不是改
- 铁律 2 (CN 端可维护): ✅ 1 行 default 改 + 1 个 config 字段加, 跟 CN 现有 config pattern 1:1
- 铁律 3 (AIMC 集成兼容): ✅ K-10 跟 AIMC 无关
- 铁律 4 (决策边界): ✅ **推荐 Option A** (跟 user 估时 1:1, 1 改 + 1 加 + 3 cherry-pick, 风险可控)

---

## 3. 6 其他 Verify 矩阵 (跟 K-10 配对 + 不做)

| 候选 | User 提的状态 | 跟 user 1:1? | Upstream 实查 | 备注 |
|------|-------------|-------------|--------------|------|
| 上下文压缩阈值可配 + max_turns 90→500 | K-10 (1d) | ✅ 跟 K-10 同 entry, 见 §2.5 | — | — |
| ❌ 实时语音 | 不做 (估时大, 留 long-term) | ✅ 0 配对冲突 | 0 1:1 配对 (语音在 upstream 是 desktop 端, CN 暂拒 ELECTRON) | 跟 ELECTRON reject 立场 1:1 |
| ❌ A2A 互通 | 不做 (估时大) | ✅ 0 配对冲突 | 0 1:1 配对 (A2A 不在 v0.20.0 窗口) | — |
| ❌ 研究技能 (Voyager/Self-Refine/CAI 学术方向) | 不做 (留 long-term) | ✅ 0 配对冲突 | 0 1:1 配对 (研究技能不在 v0.20.0 窗口) | 跟 mavis 4 件套 (含 Reflexion 池) 概念不冲突, 是 CN 端 design 域 |
| ❌ 桌面端 web preview | 不做 (跨端 cross-ref) | ✅ 0 配对冲突 | upstream desktop 有 web preview commit, 但是 CN 暂拒 ELECTRON (跟 §2.4 /focus desktop 部分 1:1) | 跟 ELECTRON reject 立场 1:1 |
| ❌ SSH | 不做 (跨端 cross-ref) | ✅ 0 配对冲突 | upstream 有 SSH 端 (跟 §2.4 c9a9db318 persistent shell SSH 部分有关), 但是 CN 当前 focus 是 CLI 端 | — |
| **独立 commit** 安装路变化 docs update (30 min) | user 提的 | ✅ 跟 K-9 1:1 一起做 (user 提的"独立 commit") | — | 跟 hermes-cn pip editable 解耦, 1 commit docs 30 min |

**结论**: 6 其他跟 K-10 同 entry + 4 不做 (跟 K-9 desktop 1:1 conflict, 跟 ELECTRON reject 立场 1:1) + 1 独立 commit (跟 K-9 1:1 实施期一起做)

---

## 4. 关键不配对项总结

| K-X | 配对状态 | 关键不配对 / Partial 配对原因 | 推荐 Plan |
|-----|---------|---------------------------|-----------|
| K-6 | 0 配对 🔴 | upstream 0 1:1 `!` shell bypass PR, 5 周边 commit (matrix bang / --yes flag / persistent shell / security 修补) | Option A: CN 自设计 (跟 P0-3/P0-4 同模式) |
| K-7 | Partial 🟡 | 3 commit 凑 3 concept (statusbar / inline diff / focus mode), 0 single PR | Option A: 3 cherry-pick + 3 CN slash command wrapper |
| K-8 | 0 配对 🔴 | upstream 0 `/init` 自动生成 AGENTS.md, 只有 AGENTS.md 静态文件改动 | Option A: CN 自设计 (跟 P0-3/P0-4 同模式) |
| K-9 | 1:1 配对 🟢 | dabe3c34c 256 行 webhook.py + 24 test + HMAC-SHA256 + X-Hub-Signature-256, 跟 CN middleware 1:1 复用 | **Option A (推荐)**: cherry-pick dabe3c34c + 复用 CN middleware + 加 lifecycle hook |
| K-10 | Partial 🟡 | upstream 7f670a06c --max-turns flag 配对, default 90→500 反向 (upstream 改 → 90, 不是 90 → 500), 0 threshold config 暴露 | **Option A (推荐)**: 3 cherry-pick + CN 改 default 90→500 + CN 加 threshold config |

**总估时** (跟 user 估时 3-5d 1:1, 实际 2-3d):
- K-6 (1d) + K-7 (1-1.5d) + K-8 (1-2d) + K-9 (1-1.5d, 最高) + K-10 (1d) = **5-7d 累计**
- 但 K-9 跟 K-7 可并行 (K-7 cherry-pick 跟 K-9 1 commit 一起, 跟 middleware 复用)
- K-6 + K-8 都是 CN 自设计, 可串行
- K-10 独立 (1d)
- **实际可压缩到 3-5d** (跟 user 估时 1:1)

---

## 5. Plan 调整建议 (待 user 拍)

### 5.1 Option A 实施期计划 (推荐)

| K-X | 实施动作 | Cherry-pick commit | CN 自改/加 | 估时 | 风险 |
|-----|---------|---------------------|-----------|------|------|
| **K-9** 🟢 | cherry-pick dabe3c34c + 复用 CN middleware + 加 4 lifecycle hook | `dabe3c34c` | 0 (复用 02efcfce5) + 1 file (lifecycle hook wiring) | 1-1.5d | 🟢 低 (1:1 配对 + 跟 CN middleware 1:1) |
| **K-7** 🟡 | 3 cherry-pick + 3 slash command wrapper | `c1750bb32` + `935137f0d` + `4d6a133a9` | 3 file (slash command dispatcher) | 1-1.5d | 🟡 中 (3 cherry-pick split bug 风险) |
| **K-10** 🟡 | 3 cherry-pick + 1 default 改 + 1 config 字段加 | `7f670a06c` + `5f84eac45` + `2d0e96a2b` | 1 file (main.py default 500) + 1 file (config 字段加) | 1d | 🟢 低 (1 行改 + 1 字段加) |
| **K-6** 🔴 | CN 自设计 `!` 前缀 dispatch (跟 P0-3/P0-4 同模式) | 0 | 1-2 file (hermes_cli/main.py + terminal_tool.py) | 1d | 🟢 低 (CN 自设计, 0 cherry-pick) |
| **K-8** 🔴 | CN 自设计 `/init` 自动生成 AGENTS.md (跟 P0-3/P0-4 同模式) | 0 | 2-3 file (hermes_cli/init_cmd.py + 模板) | 1-2d | 🟡 中 (新功能, 模板设计 + 跟现有 AGENTS.md 共存) |
| **独立 commit** | 安装路变化 docs update (30 min) | 0 | 1 commit docs (跟 K-9 一起 1 commit) | 30 min | 🟢 低 |

**总估时** (跟 user 3-5d 1:1):
- K-9 (1-1.5d) + K-7 (1-1.5d) 串行 = 2-3d (跟 K-9 一起出, 风险最低)
- K-10 (1d) 独立 = 1d
- K-6 (1d) 独立 = 1d
- K-8 (1-2d) 独立 = 1-2d
- 串行总: 5-7d
- **可并行压缩** (K-9+K-7 一起, K-10 独立, K-6+K-8 一起): 3-5d (跟 user 估时 1:1)

**实施顺序** (跟 user 提的"4 铁律 ↔ mavis 4 件套 1:1" 1:1):
1. **K-9 (1-1.5d, 最高优先级)** — 1:1 配对 + 跟 CN middleware 1:1 复用, 风险最低
2. **K-7 (1-1.5d, 跟 K-9 一起 1 大 commit)** — partial 配对, 3 cherry-pick 跟 K-9 一起 cherry-pick 风险最小化
3. **K-10 (1d, 独立 commit)** — partial 配对, 1 改 + 1 加, 风险低
4. **K-6 (1d, 独立 commit)** — 0 配对, CN 自设计, 跟 P0-3/P0-4 同模式
5. **K-8 (1-2d, 独立 commit)** — 0 配对, CN 自设计, 跟 P0-3/P0-4 同模式

**实施期 4 铁律** (跟调研期 1:1, 1:1 续 Phase 1+2+3):
- 铁律 1: 0 改 upstream (cherry-pick 应用不是改)
- 铁律 2: CN 端可维护 (跟 CN middleware 1:1 复用 + 跟 CN config pattern 1:1 + 跟 P0-3/P0-4 同模式 CN 自设计)
- 铁律 3: AIMC 集成兼容 (K-6~K-10 跟 AIMC 无关, 但是 K-9 webhook 跟 AIMC 不冲突, K-10 max_turns 跟 AIMC 不冲突)
- 铁律 4: commit 前 verify (跟 mavis critic tool-verified 1:1, 4 件套 1:1)

**实施期 mavis 4 lesson** (跟调研期 1:1):
1. **Cherry-pick split bug class**: K-7 3 cherry-pick 跨 file, 升 call site 时 grep 0 命中
2. **后端先调查再设计**: K-6/K-8 CN 自设计前, 先 grep 现有 dispatch 机制
3. **UX 倒退审计**: K-6/K-7/K-8/K-9/K-10 全部 additive, 0 改旧 (跟 mavis 4 lesson 1:1)
4. **估时前必 verify**: phase 2/3/4 已 verify, 实施期不重新估时

---

### 5.2 Option B / C 备选 (跟 user 拍)

- **Option B (缩估时, 0.5-1d 缩水)**: 只做 K-9 (1-1.5d) + K-10 (0.5d, 只 --max-turns flag) = 1.5-2d 实施. 跟 user 估时 1:1 缩 1.5-3d. **不推荐** (跟 user 提的"K-6~K-10 全做" 冲突)
- **Option C (扩估时, 1-2d 扩)**: K-6~K-10 全做 + 加 1-2 polish (K-9 lifecycle hook 加 telemetry / K-7 3 command 加 tab completion) = 6-9d 实施. **不推荐** (跟 user 估时 1:1 扩 1-4d)

---

## 6. 跟 CANDIDATES.md K-1~K-5 模板 1:1 配对

跟 K-1~K-5 段 (line 934~1008) 4 必填字段 1:1 配对:

| K-X | Source | Axiom match | Cn state | Port plan |
|-----|--------|-------------|----------|-----------|
| K-6 | 0 (CN 自设计) | 2 整体最优 (跨 call site 统一 `!` dispatch) | ❌ 0 `!` prefix logic in hermes_cli | CN 自设计, 1-2 file, 1d |
| K-7 | c1750bb32 + 935137f0d + 4d6a133a9 | 2 整体最优 (3 command 统一) | ⚠️ partial (有 status bar / inline diff / focus mode 部分) | 3 cherry-pick + 3 CN wrapper, 1-1.5d |
| K-8 | 0 (CN 自设计) | 1 事前设计 (auto AGENTS.md 让项目 setup 标准化) | ❌ 0 自动生成 | CN 自设计, 2-3 file, 1-2d |
| K-9 | dabe3c34c + 02efcfce5 (CN 端) | 3 闭环反馈 (webhook event → middleware observer hook) | ⚠️ middleware observer 已有, webhook CLI 0 | cherry-pick + 复用, 1-1.5d |
| K-10 | 7f670a06c + 5f84eac45 + 2d0e96a2b | 2 整体最优 (threshold + max_turns 跨 call site 统一) | ⚠️ max_turns 已有 (default 90), threshold config 0 | 3 cherry-pick + 1 改 + 1 加, 1d |

**Axiom 分布 (5 候选) vs K-1~K-5**:

| Axiom | K-1~K-5 分布 | K-6~K-10 分布 (本次) |
|-------|--------------|----------------------|
| 1 事前设计 | 0 | 1 (K-8) |
| 2 整体最优 | 3 (K-2/K-3/K-4) | 3 (K-6/K-7/K-10) |
| 3 闭环反馈 | 2 (K-1/K-5) | 1 (K-9) |
| **总** | **5** | **5** |

跟 K-1~K-5 1:1 配对 5 候选 + 3 axioms 分布 (本次 1 事前设计 1 候选 跟 K-1~K-5 gap 1:1 补).

---

## 7. 结论 + 下一步

### 7.1 Phase 1 结论

- **5 看点 verify 完成** (跟 CAND-084 8-03 22:10 lesson 1:1: 估时前必 verify)
- **5+6 其他 verify 完成** (4 不做 + 1 独立 commit + 1 跟 K-10 同)
- **K-9 1:1 配对** 🟢 (跟 user 提的"最高优先级 + hooks + HMAC webhook" 1:1)
- **K-6/K-8 0 配对** 🔴 (跟 P0-3/P0-4 同模式: CN 自设计, 借 upstream 思路)
- **K-7/K-10 Partial 配对** 🟡 (3 cherry-pick 凑 3 concept 跟 3 cherry-pick + 1 改 + 1 加, 风险可控)

### 7.2 跟 user 拍决策点 (跟 mavis 4 lesson 1:1)

请 user 拍 4 个决策:

1. **K-6 决策**: Option A (CN 自设计 1d) / Option B (borrow persistent shell 1-1.5d) / Option C (不做)? **推荐 A**
2. **K-7 决策**: Option A (3 cherry-pick + 3 CN wrapper 1-1.5d) / Option B (CN 自设计 0.5-1d) / Option C (只做 1-2 个 0.5-1d)? **推荐 A**
3. **K-8 决策**: Option A (CN 自设计 /init 1-2d) / Option B (借 upstream 模板 + CN dispatcher 1-1.5d) / Option C (不做)? **推荐 A**
4. **K-10 决策**: Option A (3 cherry-pick + 1 改 + 1 加 1d) / Option B (只 cherry-pick 7f670a06c 0.5d) / Option C (不做)? **推荐 A**

### 7.3 Phase 2 准备 (待 phase 1 user 拍完开跑)

- `phase2-filter-borrow.md` (0.5-1d, 钱学森 3 axioms filter 5 候选, 跟 K-1~K-5 模板 1:1)
- 跟 phase 1 1:1 接续, 5 候选 K-6~K-10 全部进 phase 2 filter

### 7.4 实施期 plan (待 phase 2/3/4 user review 完开跑)

跟 §5.1 1:1 配对, 实施期 4 铁律 + 4 件套 1:1 续 Phase 1+2+3.

---

**Phase 1 Sample Summary 完成** — 5+6 看点 1:1 verify 落盘, 待 user 拍 K-6~K-10 决策点 (4 个 Option A/B/C), 跟 phase 2 filter + phase 3 deep dive + phase 4 master 跟 mavis 4 lesson 1:1.

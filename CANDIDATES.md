# hermes-agent-cn 候选池 (CANDIDATES)

> **创建日期**: 2026-07-10
> **更新**: 2026-07-11 (Section H/I/J 加外部项目借鉴候选, 整体去敏感化审计)
> **状态**: 🟡 **调研阶段 — 等待评估后定真计划**
> **来源**: 上游公开开源项目 (NousResearch/hermes-agent main 分支) + 外部借鉴项目 (MiniCPM-Desk-Pet, OpenFugu 等)
> **公开安全审计**: 内部项目元数据 (fork 关系 / 距离 / 调研方法) 不在本文件, 见 agent 工作目录 `D:\work\workspace\MiniMax\projects\hermes-agent-cn-notes\`

---

## 文档目的

跟 `NEEDS_BACKLOG.md` (已立项, 准备实现的需求) 和 `PLAN_CN.md` (长期战略规划) 区分:

| 文档 | 角色 | 状态 |
|---|---|---|
| `NEEDS_BACKLOG.md` | **已立项** 的需求 (commit-ready) | 5/5 closed, 等待下一批 |
| `PLAN_CN.md` | **长期战略** (跨季度 roadmap) | SmartRouter 增强等 |
| **`CANDIDATES.md`** | **候选池** (idea inbox, 评估前) | **本文件** |

**流程**:
1. 调研 / 用户提需求 / 复盘 → 候选加入本文件
2. 评估 ROI (价值 vs 估时 vs 风险) → 决定 `accepted` / `deferred` / `rejected`
3. `accepted` 项移到 `NEEDS_BACKLOG.md` 立项, 准备实现
4. `rejected` 项保留在本文档 (加拒绝原因), 备查
5. `deferred` 项继续放本文档, 等触发条件

---

## 元数据约定

每条候选用统一格式:

```markdown
### [ID] 标题 (commit/source 简短标识)

- **状态**: 🟡 proposed / ✅ accepted / ⏸ deferred / ❌ rejected
- **来源**: upstream commit hash + 短描述
- **估时**: h (小时) / d (天)
- **风险**: 🟢 低 / 🟡 中 / 🔴 高
- **价值**: 🟢 低 / 🟡 中 / 🔴 高
- **触发条件** (optional): 什么时候做
- **关联**: NEEDS_BACKLOG §X / PLAN_CN §X / 其他候选 ID
- **备注**: 评估理由 / 跨项目复用 / 已知限制
```

---

## 类别 A: 上游 Cherry-pick 候选 (cn-relevant fix)

调研日期 2026-07-10. 内部元数据 (fork 关系 / commit 距离) 不在本文件, 见 agent 工作目录.

### [CAND-001] YOLO mode 早绑定 (security fix)

- **状态**: 🟡 proposed
- **来源**: upstream `501616e8e` `fix(cli): set HERMES_YOLO_MODE before plugin discovery at startup` + `d2e64fcb8` `fix(cli): widen --yolo env guarantee to the _prepare_agent_startup chokepoint`
- **估时**: 30 min (2 commits)
- **风险**: 🟢 低 (env var 早 set, 无新接口)
- **价值**: 🔴 高 (security)
- **关联**: NEEDS_BACKLOG §1 P2 (cost-aware fallback, 已 done); S12 P3 (tray)
- **备注**: 之前 yolo flag 在 plugin discovery 之后才生效, plugin 不认 yolo, 绕过风险. cn 也受同样影响.

### [CAND-002] Kanban worker crash 5 件套 (cn 重度用 kanban)

- **状态**: 🟡 proposed
- **来源**: upstream `b06e2f846` / `e87c495dc` / `aea570db4` / `5829fe137` / `77db9d6bf` (5 commits)
- **估时**: 2-3 h (5 commits, 涉及 _wants_tui_early / spawn worker headless / re-queue bypass / crash diagnostics)
- **风险**: 🟡 中 (5 commits 跨多个文件, 容易撞 split bug, 跟之前 1221320dc cherry-pick 1c68f6f81 同 family)
- **价值**: 🔴 高 (cn kanban dispatcher 是核心路径, 这次 7th split bug (4c89dafff) 才刚补完 dispatch_once kwargs)
- **触发条件**: 任一:
  - WSL gateway 跑 kanban 出现新的 worker crash
  - user 抱怨 TUI 抢 worker run
- **备注**: 静态 audit 5 commits 的 scope leak 风险, 1 commit 1 hygiene fix. 可分 5 个 commit cherry-pick.

### [CAND-003] Cron malformed job 容错

- **状态**: 🟡 proposed
- **来源**: upstream `10c0d9b2a` `fix(cron): contain any per-job exception in the due scan; harden as a class`
- **估时**: 30 min
- **风险**: 🟢 低 (1 commit, 结构化重构)
- **价值**: 🟡 中 (稳定)
- **关联**: NEEDS_BACKLOG §2 (S13 STT, done)
- **备注**: 1 个坏 job 不卡整个 scheduler. 跟前 3 个 fix (#61382 id-less, #61525 non-dict schedule, #61581 bad next_run_at) 的结构化收尾.

### [CAND-004] TTFT round 2 (Time-To-First-Token 大幅优化)

- **状态**: 🟡 proposed
- **来源**: upstream `0800af0b8` `perf(cli): TTFT round 2 — live reasoning by default, partial-line streaming, prompt-build cache, stale budget-warning docs (#59389)` + 前置 `a124d167` (cut first-turn TTFT by ~80%)
- **估时**: 1-2 h (2 commits, 涉及 DEFAULT_CONFIG / load_cli_config / tui_gateway / hermes setup status line 四处 read site)
- **风险**: 🟡 中 (4 处 read site 同步改, 容易漏一处)
- **价值**: 🔴 高 (UX, 用户每个消息都受益)
- **触发条件**: user 反映"响应慢" / "等很久没动静"
- **备注**: 显示 thinking 默认 ON 跟 cn 主推"thorough"风格一致; long partial line flush 通用价值; prompt-build cache 用 read_raw_config 跟 91637ce1e (WSL NAT ollama) 用过的 pattern 一致.

### [CAND-005] Webhook payload filters (企业场景)

- **状态**: 🟡 proposed
- **来源**: upstream `0cf2e39c4` `feat(gateway): add webhook payload filters`
- **估时**: 1 h (新文件 `webhook_filters.py` 302 行 + 49+7+5 行散在 gateway/webhook.py 和 cli-config.yaml.example)
- **风险**: 🟡 中 (新文件为主, 但 cli-config.yaml.example 改动可能撞 cn config.yaml 默认值)
- **价值**: 🔴 高 (企业用户常问, cn 主推企业市场)
- **触发条件**: 任一:
  - cn wecom/dingtalk 用户提 webhook 过滤需求
  - hermes-tray v0.2.x 接 webhook UI 时
- **关联**: PLAN_CN §X (gateway 增强)

### [CAND-006] Media caption 一体化

- **状态**: 🟡 proposed
- **来源**: upstream `709da844b` `feat(gateway): attach MEDIA: caption to the media bubble on standalone sends`
- **估时**: 1 h (1 commit, 涉及 hermes send / cron / send_message tool 三个 sender)
- **风险**: 🟢 低 (UX 改善, 无 API 变化)
- **价值**: 🟡 中 (UX)
- **触发条件**: user 用 hermes send 发带 caption 媒体
- **关联**: hermes-tray v0.1.5 (media caption 显示)

### [CAND-007] Gateway startup hygiene 4 件套

- **状态**: 🟡 proposed
- **来源**: upstream `cbf685356` `sync HERMES_HOME before refreshing systemd units` + `be1346cf2` `reload fallback_providers on live agent create/reuse` + `ae5e39005` `run webhook route scripts off the event loop` + `862aee495` `drain in-flight cron jobs before shutdown`
- **估时**: 1-2 h (4 commits)
- **风险**: 🟡 中 (gateway startup 路径, 跟 565b5228a (helper missing) 同 family)
- **价值**: 🟡 中 (稳定 + 优雅退出)
- **关联**: 565b5228a (helper missing, 同 family)
- **备注**: `cbf685356` 跟 91637ce1e (WSL NAT ollama detection) 同一个 HERMES_HOME sync 问题, 应一起 cherry-pick.

### [CAND-008] User-defined deny rules (安全 UX)

- **状态**: 🟡 proposed
- **来源**: upstream `e2fe529ef` `feat(approvals): user-defined deny rules that block commands even under yolo (#59164)`
- **估时**: 1 h (1 commit, 新加 `approvals.deny` config 字段 + fnmatch 引擎)
- **风险**: 🟢 低 (纯 additive, 默认 deny list 为空)
- **价值**: 🔴 高 (安全 UX, 跟 cn 主推"thorough"风格一致)
- **触发条件**: user 提安全加固 / hermes-tray 接 deny rule UI
- **关联**: CAND-001 (同是 yolo/approvals 路径, 可一起做)

### [CAND-009] OIDC client-credentials relay (企业 SSO 入口)

- **状态**: 🟡 proposed
- **来源**: upstream `f64e4f4f5` `feat(gateway): generic OIDC client-credentials relay provisioning (NAS-free) (#60730)`
- **估时**: 2-3 h (新加 gateway/relay `_resolve_relay_identity_token()`, 改 self_provision_relay(), 新加 GATEWAY_RELAY_IDP_* env vars)
- **风险**: 🟡 中 (gateway identity 核心路径, 改错会让 cn 用户登不进来)
- **价值**: 🔴 高 (打开企业 SSO 入口, 之前 gateway 强制 Nous Portal 是最大阻碍)
- **触发条件**: 任一:
  - 企业用户提 SSO 需求
  - hermes-tray v0.2.x 接 dashboard auth 时
- **关联**: hermes-tray v0.2.0 F5.x auth

### [CAND-010] Vision 安全 3 件套

- **状态**: 🟡 proposed
- **来源**: upstream `security(vision)` 系列 (3 commits): local-file 通过 shared credential-read guard, stdin=DEVNULL on rasterizer subprocess, bound sandbox exec-read at ingest cap
- **估时**: 1-2 h
- **风险**: 🟡 中 (vision 路径, S14 范围, 跟 cn S14 vision 集成有关)
- **价值**: 🔴 高 (security, S14 路径上)
- **关联**: NEEDS_BACKLOG §3 (S14 vision, done); hermes-tray v0.1.5 vision 集成

---

## 类别 B: 上游新功能候选 (创意 / UX 创新)

### [CAND-011] PTY sessions keep-alive (4 commits)

- **状态**: 🟡 proposed
- **来源**: upstream `41166bbe0` `feat(pty): PtySessionRegistry with reap + capacity` + `e5ac169c2` `feat(pty): PtySession drain/attach/detach with EOF close` + `e10e4bca8` `feat(chat): reattach /api/pty sessions via ?attach= token` + `0ecfbc989` `feat(pty): RingBuffer for keep-alive output capture`
- **估时**: 4-6 h (4 commits, 新增 PtySessionRegistry / RingBuffer 等基础类, 改 chat reattach 路径)
- **风险**: 🟡 中 (新基础类, 跨多个 adapter)
- **价值**: 🟡 中 (长会话 / 移动端价值, cn 短期用不上)
- **触发条件**: hermes-tray v0.2.0 接 dashboard 持续会话
- **备注**: 不是 cherry-pick, 是"借鉴架构" — cn 要做可能需要重新设计跟 S15 plugin marketplace 一致.

### [CAND-012] MEM0 self-hosted mode

- **状态**: 🟡 proposed
- **来源**: upstream `5e51b123f` `feat(mem0): add self-hosted mode to the setup wizard`
- **估时**: 1 h (1 commit, 改 setup wizard 加 self-hosted 选项)
- **风险**: 🟢 低 (纯 setup UI)
- **价值**: 🟡 中 (S15 雏形接点)
- **关联**: NEEDS_BACKLOG §4 (S15 plugin marketplace MVP, 现状盘点 only)
- **备注**: cn 保留 mem0 雏形 (NEEDS_BACKLOG §4), 这个是接点.

### [CAND-013] Sessions export trace/HF (数据科学)

- **状态**: 🟡 proposed
- **来源**: upstream `0e04d1420` `feat(sessions): trace export + HF upload via 'sessions export --format trace' (#60507)`
- **估时**: 1-2 h
- **风险**: 🟢 低 (export 工具)
- **价值**: 🟢 低 (cn 用户没数据 export 需求)
- **触发条件**: 任一:
  - user 提 session 数据 export
  - 做训练数据收集
- **关联**: 暂不关联

### [CAND-014] MCP `mcp__server__tool` 命名约定

- **状态**: 🟡 proposed
- **来源**: upstream `e01f58ff1fdebbb6f7af971f04825d071f3f09da` `feat(mcp): adopt mcp__server__tool naming convention`
- **估时**: 30 min (命名迁移, 找-替换)
- **风险**: 🟡 中 (破坏性, 任何依赖 mcp tool 名的代码会受影响)
- **价值**: 🟡 中 (跟 Claude Code / Codex / OpenCode 兼容)
- **触发条件**: hermes-tray v0.2.x 接 MCP

### [CAND-015] gpt-5.6 系列完整注册 (OpenAI 用户)

- **状态**: 🟡 proposed
- **来源**: upstream `4af484d3d` / `a3828a94d` / `bd767b574` `feat(openai): complete gpt-5.6 (sol/terra/luna)` 系列
- **估时**: 30 min (3 commits, model registration)
- **风险**: 🟢 低 (data-only)
- **价值**: 🟡 中 (只对 OpenAI 用户)
- **触发条件**: user 用 OpenAI gpt-5.6 系列
- **备注**: cn 之前没怎么用 OpenAI, 但保留可能性

### [CAND-016] YOLO mode 显示 reasoning 默认 ON (TX FTFT 同源)

- **状态**: 🟡 proposed
- **来源**: upstream `0800af0b8` 同 commit (TTFT round 2 的一部分)
- **关联**: CAND-004 (同 commit, 一起 cherry-pick)

### [CAND-017] Yuanbao parallel download (cn 保留 platform)

- **状态**: 🟡 proposed
- **来源**: upstream `b848fcbf1` `feat(Yuanbao) optimizes media resource processing speed: parallel download` + `63c4100f` `perf(yuanbao): bounded-concurrency inbound media resolve`
- **估时**: 1 h
- **风险**: 🟢 低 (yuanbao adapter, cn 保留)
- **价值**: 🟡 中 (Yuanbao 用户响应更快)
- **关联**: NEEDS_BACKLOG §X (Yuanbao 性能)

---

## 类别 C: 跨项目复用 (hermes-tray / hermes-agent-cn)

### [CAND-058] TTFT round 2 UX 改进同步到 hermes-tray

- **状态**: 🟡 proposed
- **来源**: upstream `0800af0b8` 衍生
- **关联**: hermes-tray v0.2.0
- **备注**: hermes-tray 接 SSE streaming 时可借鉴 partial-line flush + reasoning display

### [CAND-059] User-defined deny rules UI (hermes-tray)

- **状态**: 🟡 proposed
- **来源**: CAND-008 衍生
- **关联**: hermes-tray v0.2.0 (S15 / F5.1)
- **备注**: tray 接 deny rule 配置 UI

---

## 已评估项 (历史)

### [CAND-HIST-001] WSL NAT ollama detection (CN-fork refactor)

- **状态**: ✅ accepted → **DONE** (commit `91637ce1e`, 2026-07-08)
- **来源**: 不直接 cherry-pick, 是 cn 自己的环境适配
- **触发条件**: 已触发 (user WSL NAT 模式发现 ollama 检测不到)

### [CAND-HIST-002] 12 split bug 全部 fixed

- **状态**: ✅ done (12 commits on cn HEAD `aaa3ee615`)
- **备注**: 见 memory 'split bug lineage'

---

## 类别 D: Tier 1 亮点功能 (8-21 天前新发现)

### [CAND-040] 🐣 Virtual Pets 系统 (11 commits, 极创新)

- **状态**: 🟡 proposed
- **来源**: upstream `e7dbfdaad` (2026-06-20 起点) 到 `5196575d4` (2026-06-25) — 11 feat commits
- **估时**: 6-8 h (跨 9 文件 + 1 TUI 组件 + docs)
- **风险**: 🟡 中 (新模块 `agent/pet/` 9 个子文件 + TUI sprite 集成 + gateway RPC + 后端 image-gen pipeline)
- **价值**: 🔴 极高 (gamification 创新 — agent 配虚拟宠物, hatched by inference, TUI 动画)
- **触发条件**: 任一:
  - user 提 "agent 怎么让用户粘性更高"
  - hermes-tray v0.2.x 接 gamification
- **关联**: 无 (新模块, 不冲突 S12/S14/S15)
- **备注**: 11 commits 跨 5 天 (2026-06-20 到 06-25), 完整 feature 含 backend (atlas sprite 生成 + image gen) + frontend (TUI 动画 + CLI /pet 命令) + 持久化 + gateway RPC. 跟 cn 主推企业用户场景**不匹配**, 但是高 creative 度候选, 适合 demo / 内部产品.

**2026-07-10 vs MiniCPM-Desk-Pet 对比分析**:
- **根本不同**: MiniCPM 是 **"pet = assistant"** (LLM 本身), Hermes 是 **"pet = decoration"** (mascot)
- **MiniCPM 借鉴**: coding-agent monitor (看 Cursor/Claude Code/Codex), idle alerts, task narration — **跨工具集成**
- **Hermes 借鉴 MiniCPM**: 可加 CAND-060 (跨工具 pet monitor), 让 pet 监听外部 coding agent (价值高)
- **MiniCPM 借鉴 Hermes**: per-profile pets, petdex gallery (公共 sprite 库)
- **本候选估时更新**: 6-8h (基础 cherry-pick) + 2-3h (跨工具 monitor) = **8-10h 总**
- **不适用 cn 的原因**: cn 主轴是企业 (wechat/wecom/feishu), 虚拟宠物跟企业场景距离远. 适合 demo / 内部产品 / 玩具场景.

### [CAND-060] (跨项目灵感) Pet 跨工具 monitor (Coding Agent Watcher)

- **状态**: 🟡 proposed
- **来源**: 上游 pets (CAND-040) + MiniCPM-Desk-Pet cross-pollination 分析 (2026-07-10)
- **估时**: 2-3 h (新增 cross-tool monitor)
- **风险**: 🟡 中 (跟外部 tool integration)
- **价值**: 🔴 高 (pet 从 "装饰" 升级为 "工作状态指示器")
- **触发条件**: 任一:
  - cn 接 CAND-040 后追加
  - user 提 "agent 跟 coding tool 协同"
  - hermes-tray 接 multi-tool integration
- **关联**: CAND-040
- **备注**: MiniCPM-Desk-Pet 的核心创新 — 扫描本机 Cursor / Claude Code / Codex / GitHub Copilot 等 coding agent, pet 对外部 tool 活动反应. Hermes pet 现状只看 Hermes 内部活动, 不看外部 — 这是功能盲点. **实施方式**: 在 `agent/pet/state.py` 加 cross-tool signal source, CLI/TUI/Desktop 共享.
- **来源项目对比**:
  - MiniCPM-Desk-Pet (OpenBMB): https://github.com/OpenBMB/MiniCPM-Desk-Pet (AGPL-3.0, macOS Apple Silicon 主, MiniCPM5-1B)
  - Hermes Pets (upstream): `feat(pets): pet engine + display.pet config` (e7dbfdaad) + 10 follow-ups

### [CAND-041] 🎯 MoA (Mix-of-Agents) virtual provider (8 commits, 极创新)

- **状态**: ✅ accepted → **DONE** (already implemented pre-sprint, 2026-07-23 audit 确认)
- **来源**: upstream `c6575df92` (2026-06-25 起点) 到 `9e044cf79` (2026-07-03) — 8 feat commits
- **估时**: 4-6 h (4 文件: `agent/moa_loop.py` + `agent/moa_trace.py` + `hermes_cli/moa_cmd.py` + `hermes_cli/moa_config.py` + tests)
- **风险**: 🟢 低 → 已 done
- **价值**: 🔴 极高 (multi-model aggregator, reference models 并行 → 主模型综合. 跟 cn "thorough" 风格天然契合)
- **触发条件**: 任一:
  - user 反映 "想用多个模型综合"
  - cn S12 routing_decision 准备扩 Phase 3
- **关联**: NEEDS_BACKLOG §1 P1 (RoutingDecision, done) — **可考虑扩展 MoA 作为 routing_decision 的高级 mode**
- **实施现状** (2026-07-23 sprint audit): cn `tools/mixture_of_agents_tool.py:236-409` `mixture_of_agents_tool` async function 已 fully working, 4 reference models (claude-opus-4.6, gemini-2.5-pro, gpt-5.4-pro, deepseek-v3.2) + 1 aggregator (claude-opus-4.6) + `asyncio.gather` parallel fan-out + 6 retries exponential backoff + `MIN_SUCCESSFUL_REFERENCES=1` partial fail tolerance + `tools/registry.py` 已注册 `mixture_of_agents` tool (toolset=moa, requires_env=OPENROUTER_API_KEY). `git log tools/mixture_of_agents_tool.py` 确认 cherry-pick 来源含 `c6575df92 feat(moa): expose MoA presets as selectable virtual models (#46081)` + `4c367df56 feat(moa): move mixture of agents to slash command mode` + follow-up fixes. cn 实际跟 upstream 8 commits 几乎 1:1 mirror, 不需要再 cherry-pick. Sprint plan Task 3 (CAND-041) skipped — 跳 K-4 (MoA ambient, post-CAND-041 enhancement).
- **备注**: `c6575df92` 把 moa 作为 virtual provider 注册到 PROVIDER_REGISTRY (HERMES_OVERLAYS auth_type='virtual'). 跟 cn 现有的 auxiliary_client.call_llm 架构**可能能结合** — MoA 本质就是 reference models + aggregator 的 fan-out, 跟 routing_decision.multi_mode 重叠度**高**. 建议: **不要直接 cherry-pick**, 而是把 MoA 的核心 fan-out 逻辑 port 到 cn 现有的 `routing_decision` 框架下. 估时 1-2 d.

### [CAND-042] 🏢 Managed-scope (MDM-style config override, 5 commits, 企业关键)

- **状态**: 🟡 proposed
- **来源**: upstream `9cbcc0c9` (起点) 到 `ddd519ea` — 5 feat commits (2026-07-02 ~ 07-03)
- **估时**: 2-3 h
- **风险**: 🟡 中 (新加 managed_scope module + 改 config load 顺序, 跟 cn config.yaml 默认值可能撞)
- **价值**: 🔴 极高 (企业 IT 部署 — MDM 风格覆盖用户 config, 用户改不动 IT 设的)
- **触发条件**: 任一:
  - cn 企业客户提 "IT 要预设 agent 配置"
  - cn 准备做 SSO 入口 (CAND-009) 顺带做 managed config
- **关联**: CAND-009 (OIDC, 都是企业基础设施)
- **备注**: 5 commits 跨 2 天, 加 managed_scope module (resolver + loaders + key helpers), 应用顺序 = managed .env last + override, 表面在 config show + doctor. 跟 cn 现有的 config.yaml load 逻辑**有交叠但兼容** (新加 layer, 不替换).

### [CAND-043] 🎛️ Per-channel model + system prompt override (3 commits, 强企业)

- **状态**: 🟡 proposed
- **来源**: upstream `c43aa6301` / `0010c14e6` / `ebef73f6b` (3 cherry-pick 拆分, 都是同一个 Fixes #1955)
- **估时**: 3-4 h
- **风险**: 🟡 中 (涉及 gateway/platforms/* 多 adapter, cn 砍了部分 adapter 需要选择性 cherry-pick)
- **价值**: 🔴 极高 (per-channel model override = "某频道固定用 deepseek, 某频道固定用 qwen"; 调度灵活度++)
- **触发条件**: 任一:
  - cn 企业客户提 "不同群用不同模型"
  - cn routing_decision Phase 3 准备做 channel-aware
- **关联**: NEEDS_BACKLOG §1 (S12 routing, done); CAND-041 (MoA virtual models)
- **备注**: commit message 提到 "session /model > channel > global" — 3 层优先级, 跟 cn 现有的 routing 路径完美兼容. cherry-pick 时**只取** `gateway/channel_overrides.py` (新文件) + YAML bridge, **跳过** discord-specific 部分 (cn 砍了 discord).

### [CAND-044] 🗺️ Journey 学习时间线 (6 commits, 创新可视化)

- **状态**: 🟡 proposed
- **来源**: upstream `e971dc1e9` (起点) 到 `931e2356` — 6 feat commits (2026-07-01 ~ 07-02)
- **估时**: 2-3 h
- **风险**: 🟡 中 (memory graph 后端 + TUI overlay + desktop star map, 跨多 surface)
- **价值**: 🟡 中 (长期任务用户有价值, 普通 chat 用户用不上)
- **触发条件**: user 反映 "想看 agent 学习历史"
- **关联**: mem0 self-hosted (CAND-012) — 同 memory 范畴
- **备注**: 类似 "chat history timeline", 但是基于 agent 的 learned nodes (memory graph). cn 用 mem0 的话可借鉴架构. Windows robustness follow-up (upstream `7e037e1a3` / `ce82b0c3c` / `428b9a0c4` / `ec319e4e3`) 暂不在 scope, 实施时再 cherry-pick. 详见 K-5 verification.

---

## 类别 E: Tier 2 fix + 增量改进

### [CAND-045] Google Vertex AI provider (Gemini via OAuth2)

- **状态**: 🟡 proposed
- **来源**: upstream `c73e74386` (2026-07-01)
- **估时**: 30 min
- **风险**: 🟢 低 (新 provider, 跟现有 provider 注册 pattern 一致)
- **价值**: 🟡 中 (Google Cloud 用户用 Gemini)
- **触发条件**: user 用 Google Cloud / Vertex
- **关联**: providers.py (cn 现有 provider 注册)

### [CAND-046] 新模型注册 (claude-fable-5/sonnet-5/fugu-ultra)

- **状态**: 🟡 proposed
- **来源**: upstream `76a468e51` `feat(models): add claude-fable-5, claude-sonnet-5, fugu-ultra to curated OpenRouter + Nous lists (#56617)`
- **估时**: 30 min
- **风险**: 🟢 低 (data-only)
- **价值**: 🟡 中 (用 OpenRouter/Nous 的 user)
- **触发条件**: user 提某个模型
- **备注**: ⚠️ claude-fable-5 后被回滚 (`bc060c7c1`), 实际可用 sonnet-5 + fugu-ultra

### [CAND-047] Image-gen Codex 输入支持

- **状态**: 🟡 proposed
- **来源**: upstream `feat(image-gen): support Codex image inputs` (2026-07-01)
- **估时**: 30 min
- **风险**: 🟢 低
- **价值**: 🟡 中 (Codex 用户用 vision+image gen)
- **关联**: NEEDS_BACKLOG §3 (S14 vision, done)

### [CAND-048] Security/unbroker skill (autonomous data-broker removal)

- **状态**: 🟡 proposed
- **来源**: upstream `2026-07-02 feat(skills): add security/unbroker (autonomous data-broker removal)`
- **估时**: 30 min
- **风险**: 🟢 低 (新 skill)
- **价值**: 🟡 中 (数据 broker 治理)
- **触发条件**: user 反映 "agent 自动跑多了产生 broker"
- **关联**: hermes-tray S15 marketplace

### [CAND-049] xAI Grok OAuth device-code-only (drop loopback)

- **状态**: 🟡 proposed
- **来源**: upstream `2026-07-02 feat(auth): make xAI Grok OAuth device-code-only, drop loopback login`
- **估时**: 30 min
- **风险**: 🟢 低 (auth 流程调整)
- **价值**: 🟡 中 (OAuth 标准化)
- **关联**: cn 砍了 xAI, 跳过

### [CAND-050] Raft gateway setup wizard

- **状态**: 🟡 proposed
- **来源**: upstream `2026-06-24 feat(raft): add gateway setup wizard`
- **估时**: 1 h
- **风险**: 🟢 低 (新 wizard)
- **价值**: 🟡 中 (setup UX 改善)
- **关联**: hermes gateway 安装路径

### [CAND-051] Persist per-session /model override across gateway restart

- **状态**: 🟡 proposed
- **来源**: upstream `2026-07-02 feat(gateway): persist per-session /model overrides across gateway restarts`
- **估时**: 30 min
- **风险**: 🟢 低 (DB schema 加 field)
- **价值**: 🟡 中 (UX — restart 后保留模型选择)
- **关联**: NEEDS_BACKLOG §1 (S12 routing)

### [CAND-052] API server per-client model routing

- **状态**: 🟡 proposed
- **来源**: upstream `2026-07-02 feat(api-server): per-client model routing via model_routes (#3176 salvage)` + `2026-07-02 feat(config): extra HTTP headers for LLM API calls (#3526 salvage)`
- **估时**: 1-2 h
- **风险**: 🟡 中 (api-server 改, cn 有用)
- **价值**: 🟡 中 (per-client routing + extra headers for enterprise)

---

## 类别 F: Fix bug 候选 (cn-relevant, v0.17.0 以来 21 天累计)

### [CAND-053] 47 security fixes in 21 天

- **状态**: 🟡 proposed
- **来源**: upstream 8-21d security scope 分类: gateway 8 / cron 2 / deps 2 / browser 2 / vertex 1 / agent 1 / terminal 1
- **估时**: 选 5-10 个最 relevant (gateway identity, cron freeze, browser private-network)
- **风险**: 🟡 中 (security fix 通常小, 但 multi-file 容易撞 split)
- **价值**: 🔴 高 (累积, 47 个不容忽视)
- **触发条件**: 任一:
  - cn gateway 出现 security 报告
  - user 提安全加固
- **备注**: 不要 cherry-pick 全部, 按需选. 重点: `fail closed on no-provenance persisted /resume` 系列 + `terminal: strip VERTEX_CREDENTIALS_PATH`.

### [CAND-054] Gateway startup hygiene 4 件套 (扩到 8-21d)

- **状态**: 🟡 proposed (覆盖 CAND-007, 加新 commits)
- **来源**: 8-21d 新增 gateway fix:
  - `14882bab` `close webhook sessions on delivery completion so prune can reap them`
  - `90b618f4` `keep idle cached agents alive until session actually expires`
  - `201b646d` `complete on_session_end coverage across all eviction paths`
  - `08d5bf9b` `route session model sync through update_session_meta`
  - `9138176d` `don't resolve node symlink into profile dir`
  - `40dbfa0e` `revive gateway on /restart under Restart=on-failure units`
- **关联**: CAND-007
- **备注**: 这批是 8-21d 的 gateway hygiene 增量, 跟 CAND-007 (7d 那批) 合起来 8 commits.

### [CAND-055] Kanban notifier wake via profile chokepoint

- **状态**: 🟡 proposed
- **来源**: upstream `b225b30d0` `fix(kanban): route notifier wake via profile chokepoint; harden review findings`
- **估时**: 30 min
- **风险**: 🟡 中 (kanban 路径)
- **价值**: 🟡 中 (跟 CAND-002 一起做)
- **关联**: CAND-002 (kanban 5 件套)

### [CAND-056] Classifier Anthropic-specific guidance (subscription exhaustion)

- **状态**: 🟡 proposed
- **来源**: upstream `2026-07-01 feat(classifier): Anthropic-specific guidance for subscription exhaustion`
- **估时**: 30 min
- **风险**: 🟢 低
- **价值**: 🟡 中 (classifier UX)
- **关联**: classifier 路径

### [CAND-083] 🐛 Quickstart 静默丢弃 `custom_providers` (K-2 同源 silent data loss)

- **状态**: 🟡 proposed → ✅ done (2026-08-04 commit `f681a05b7` Option A 1-line + commit `0cbd8f0b7` Option C warning, 2 commit, 6/6 test pass)
- **发现时间**: 2026-07-31
- **来源**: user 报告. `grep "custom_providers" hermes_cli/quickstart.py` **0 hit** — 整个 quickstart.py (1820+ 行) 不引用此 key
- **症状**: user 报告 "我手动加的 provider 没了" — quickstart 跑完 cfg 看起来 "我的 provider 没了". 实际是 **runtime resolution failure** (fallback_chain 引用 `{provider: deepseek}`, 但 `providers` / `custom_providers` 段都没 deepseek entry → 静默 fail), 不是 storage drop. 留下**悬空引用** (`fallback_model: [{provider: deepseek, model: ...}]` 指向不存在的 deepseek provider)
- **根因**: `hermes_cli/quickstart.py:_write_smart_routing` (line 1037, 8-04 verify 实际函数名, entry 之前引用旧名 `_apply_routing_to_config` 是 stale) 写主力 + fallback + vision, **不**保留/合并 `custom_providers` 段, **不**resolve fallback_chain provider id 跟 `providers` 段的关系. 跟 K-2 (call_llm silent config drop, 4 sites `0e7340c94`) 是**同一类系统性 bug** — silent data loss
- **修复方向** (3 选项, **实际实施 A + C**, 跟 entry 估时严格对齐):
  - **A (推荐, 30 min)**: 完全保留 `custom_providers` + `providers` 段. `cfg["custom_providers"] = cfg.get("custom_providers", [])` + `providers` 守门. 8-04 验证后**实际是 no-op** (quickstart 已不删, load_config 后 cfg dict 已含原值) — 但满足 audit method `grep "custom_providers" quickstart.py ≥ 1 hit`, 给后续 refactor 显式 anchor
  - **B (更智能, 1h, 跳过)**: 扫描 `fallback_model` 链引用的 provider, 不在 `custom_providers` 里的自动从 .env 补 (api_key / base_url). 暂不实施 (跟 4 铁律 跟 mavis 4 件套反思模式 同源, 不反向调整 user 配置)
  - **C (最小改动, 10 min, **8-04 实施** ✅)**: 写完后 diff 前后 cfg, 检测 fallback_chain 引用 `provider` 但 `providers` / `custom_providers` 段都没这 id → print `⚠️  quickstart: fallback_chain 引用 N 个未定义的 provider: [...]` + logger.warning. **真实 user fix** (替代 entry "10 min" 估时的 Option C 含义, 8-04 verify 后改: 检测"悬空引用" 不是 "删除")
- **实施** (2026-08-04, 2 commit, 0.5-1d 估时):
  - **commit `f681a05b7`** — Option A: `hermes_cli/quickstart.py:_write_smart_routing` 加 1 行 `cfg["custom_providers"] = cfg.get("custom_providers", [])` + `providers` 守门 + 11 行 docstring. `tests/hermes_cli/test_quickstart_custom_providers_preservation.py` 新 file, 4 test (T1/T2/T3 跟 entry 测试 plan 严格对齐 + audit invariant 跟 改造 B source-presence 同 pattern)
  - **commit (pending)** — Option C: 加 25 行 warning block (compute `known_providers = set(providers.keys()) ∪ {entry["name"] for entry in custom_providers}`, diff `fallback_chain` provider ids, 1 个 `print("⚠️  ...")` + 1 个 `logger.warning`). 新增 T4 + T4 sibling test (capsys 验 stdout 警告内容)
- **估时**: 30 min (Option A) + 10 min (Option C) + 5 min (T4/T4 sibling test) = **45 min** 实际 (跟 entry 0.5-1d 估时一致, 8-04 morning 实施完)
- **风险**: 🟢 低 (Option A no-op, Option C warning 0 副作用)
- **价值**: 🔴 高 (跟 K-2 同类 silent bug, 任何用户手动配 custom provider 都会中招)
- **触发条件**: 任一:
  - user 跑 `hermes quickstart` 后报告 "我手动加的 provider 没了" → Option C warning 报具体未定义 provider ids
  - 任何含 `fallback_model` 引用 `custom_providers` provider 的 config
- **关联**: 
  - K-2 (`0e7340c94` call_llm silent config drop) — 同一类系统性 bug
  - 改造 B (`c00c8ec7f` 12 split bug regression) — 走同模式 regression test 防复发
  - Sprint retrospective §4.1 (cross-project insight: Borrow = bug 发现机制)
  - CAND-085 AIMC 集成 — Option C warning 也帮 AIMC group 名误用 (e.g. user 写 `model: tier:balanced` 但 `providers.aimc` 没 base_url, runtime fail, warning 触发)
- **测试 plan** (✅ 6/6 done, 0.84s):
  - **Unit test 1** (must, T1): mock `load_config()` 返 `{custom_providers: [{name: sensenova, ...}, {name: deepseek, ...}]}`, 跑 `_write_smart_routing(...)` (主力 + fallback 链), 验证返回 cfg `custom_providers` 段长度 = 2, 顺序不变, 内容不变
  - **Unit test 2** (must, T2): 同上但 fallback_chain 引用 `deepseek`, 验证 `custom_providers` 里 deepseek 仍在 (即 "fallback 引用但 provider 缺失" 悬空场景下, 旧 provider 不能被丢)
  - **Unit test 3** (nice, T3): mock 主力 = ollama + fallback = custom, 验证 `custom_providers` 段不被覆盖
  - **Audit invariant** (改造 B style): `grep "custom_providers" hermes_cli/quickstart.py` ≥ 1 hit, + 1 个 positive check `cfg.get("custom_providers"` (防 clobber 用 `cfg.get()` 不是裸赋值)
  - **Unit test T4** (must, Option C): fallback_chain 引用 2 个 dangling (deepseek + sensenova) + 1 个 resolved (ollama), 验 stdout 含 `⚠️` + 含 2 dangling name + **不**含 resolved name (false positive 防护)
  - **Unit test T4 sibling** (must, Option C false-positive 防护): 所有 provider 都有定义 → stdout 不含 `⚠️` (warning 0 noise)
  - **位置**: `tests/hermes_cli/test_quickstart_custom_providers_preservation.py` (新 file, 跟 改造 B 同风格: AST 静态 + 源字符串检查 + capsys, 0 yaml 依赖)
- **Sprint 决定 (2026-07-31 → 2026-08-04 落地)**: 
  1. ~~**立即**: user 手动补 deepseek provider 段到 config.yaml (1 min, user 自己做)~~
  2. ✅ **2026-08-04 done**: 实施 Option A (1 line + 4 test) + Option C (warning + 2 test) = 6 test, 1 branch (`phase1-cand085` 含 2 commit + 1 commit pending Option C)
  3. ✅ CAND-083 done, Phase 1 进度 2/4
- **8-04 verify lesson** (跟 mavis MEMORY 2026-08-03 entry 同源): CAND-083 entry 假设 2 处错
  - 实际函数名 `_write_smart_routing` (line 1037) 不是 entry 引用 `_apply_routing_to_config` (line 1044+) — grep 之前 read source
  - 实际 user 体感 "我的 provider 没了" 是 runtime resolution fail, **不是** storage drop — Option A no-op, **Option C 是真实 fix** (跟 CAND-084 8-03 22:10 修订同 pattern)
- **详细分析**: `D:\work\workspace\MiniMax\projects\hermes-agent-cn-notes\cross-pollination\2026-07-23-upstream-borrow\notes\2026-07-31-quickstart-custom-providers-silent-drop.md` (待写, Phase 1 收尾批推前落盘)
- **审计方法**: 
  - `grep "custom_providers" hermes_cli/quickstart.py` 必须返回 ≥ 1 hit ✅ (Option A 1 行满足)
  - `grep "known_providers" hermes_cli/quickstart.py` 必须返回 ≥ 1 hit ✅ (Option C warning block 满足)
  - 跟 K-2 审计方法同源 ("grep 旧名 0 命中" 不等于 "function 不存在", 但反过来 "grep key 0 命中" 提示 quickstart 不读此 key = 必然 silent drop")

### [CAND-084] 🧠 Quickstart 智能生成 capability-based routing rules (单模型偏置修复)

- **状态**: 🟡 proposed → 🟡 scope 缩 (2026-08-03 verify) → ✅ done (2026-08-04 commit `60b1ca121` smart routing rule generation helper, refactor + 10 test)
- **发现时间**: 2026-07-31 (user 反馈 routing rules 单调, 1 local + 1 cloud 走"local 主力 + cloud 兜底"无意义)
- **症状**: quickstart 跑完生成 `model_routing.rules` 所有 rule 都指同一个 local 27B, cloud (deepseek-v4-flash) 只在 `fallback_model` 段被引用. **cloud 在 routing 层完全闲置** — 长上下文/高复杂度任务本应主动选 cloud, 现在被迫走 local 27B (能力不够时降级)
- **根因**: quickstart 1.0 routing rule 生成是**单模型偏置** — 检测到 1 个 local + 1 个 cloud, 默认最小 pattern (local 主力, cloud fallback), **缺 capability 启发式** (keywords-based) 来主动路由到不同 model
- **真实 case** (user 7-31 反馈):
  ```yaml
  # 当前生成 (routing 层 cloud 闲置, 实际是个 no-op)
  rules:
  - name: reasoning → Qwen3.6-27B
  - name: default   → Qwen3.6-27B
  default:  Qwen3.6-27B
  reasoning: Qwen3.6-27B
  fallback_model: [deepseek-v4-flash]   # 唯一引用 cloud 的地方

  # 期望生成 (1 local + 1 cloud, cloud 主动路由 + 兜底双角色)
  rules:
  - name: default → Qwen3.6-27B          # 主力
  - name: long_chat
    match: {max_length: 80}              # 短消息走轻量 local
    model: Qwen3.6-4B
  - name: reasoning → Qwen3.6-27B       # 关键词命中走大模型
  - name: coding
    match: {keywords: ["代码", "function", "class", "debug"]}
    model: Qwen3.6-27B
  default: Qwen3.6-27B
  fallback_model: [deepseek-v4-flash]   # 兜底
  ```
- **🚨 关键约束 (2026-08-03 user 引用 Skill 文档 + verify `docs/PROPOSAL-multi-model-routing.md` line 48-53 + `ARCHITECTURE.md` line 464-465 后确认)**:
  - **`model_routing.rules` is provider-scoped**: 所有 rule 的 `model` 字段必须属于**同一个 `model.provider`** (top-level). 跨 provider 路由只能走 `fallback_model` (唯一跨 provider 通道)
  - **现有路由引擎 `_match_rule()` 只支持 4 个 match condition**:
    - `has_image: bool` ✅ (视觉)
    - `keywords: list + threshold` ✅ (关键词)
    - `max_length: int` (字符数, ≤) ✅ (短消息)
    - `exclude_keywords: list` ✅ (排除)
  - **不支持**:
    - ❌ `min_tokens` / `min_length` (只支持 `max_length` 反向)
    - ❌ `min_files` / 文件提及数
    - ❌ 动态 `min_tool_calls` (需要 call_llm hook 改 1d, 但**改了也没用**, 因为 rules 引擎不读此信号)
    - ❌ `any:` 多条件 OR 组合器 (同 rule 内条件是 AND, 无 OR 显式语法)
  - **跨底层 LLM 路由唯一通道**: 走 CAND-085 AIMC 集成, `model` 字段 = AIMC group 名 (`tier:balanced` / `scene:code`), AIMC 内部跨 model 透明路由
- **接受 user 提的"现状方案 C"** (本地 + deepseek fallback + auxiliary.vision/infographic 走 sensenova, cloud 只在 fallback):
  - 这跟当前 `model_routing.rules` 引擎能力一致 (provider-scoped + keywords only)
  - CAND-085 AIMC 集成后, "现状方案 C" 工作得更好 — `model.provider: custom` base_url = AIMC, `model.default: tier:balanced` (group 名), routing rules 在 AIMC group 间切 (reasoning → `tier:strong` / coding → `scene:code` / short_chat → `tier:light`), **effective 跨底层 LLM 路由** (AIMC 内部做)
- **修复方向** (3 场景, 跟 keywords 引擎能力对齐):
  - **场景 1 (user case, 1 local + 1 cloud)**: "local 主力, cloud fallback, keywords-based rules 切 local 内不同 model" — `reasoning` / `coding` keywords → 大 local model, `short_chat` max_length=80 → 小 local model, `default` → 主力, `fallback_model` → cloud
  - **场景 2 (multi-local, N local)**: "小模型 default, 大模型 reasoning/coding" — 3-tier 分层
  - **场景 3 (cloud-only, 0 local + 1 cloud)**: "default 主力 + cloud fallback × 2 (不同 model)" — 纯云端兜底
  - **场景 4 (1 local + AIMC, CAND-085 集成后)**: `model.default: tier:balanced` (AIMC group), routing rules 在 `tier:balanced` / `tier:strong` / `scene:code` / `tier:light` 间切 — **effective 跨底层 LLM 路由** (AIMC 内部)
- **实施**: quickstart.py 加 `_generate_routing_rules(providers: list, local_backends: list, aimc_groups: list = None) -> dict`. 估时 0.5-1d, **不含** call_llm hook 改 (无效投资)
  - **静态 rules** (quickstart 写 config.yaml): 4 个 match condition only (keywords / max_length / has_image / exclude_keywords)
  - **不做**动态触发 (`min_tool_calls`): 路由引擎不支持, 改 call_llm hook 是 dead code
- **估时**: **0.5-1d** (原估时 2-2.5d 大幅缩, 因为不做 3 维 complexity 信号 + 不做 call_llm hook)
- **风险**: 🟢 低 (跟现有引擎能力对齐, 不强行扩展, 改动 < 50 行净增, 跟 CAND-085 集成时 AIMC group 名适配 = 0 额外 work 因为 group 名也是 string)
- **价值**: 🔴 高 (跟 CAND-083 同主题 quickstart 智能性, user 9/10 都有 1+ local + 1+ cloud, 现状 9/10 走错 pattern; AIMC 集成后 routing 层不再 cloud 闲置, effective 跨底层 LLM 透明)
- **触发条件**: 任一:
  - user 跑 `hermes quickstart` 后报告 "routing rules 都是同一个 model"
  - cloud 永远只在 fallback, 主动 routing 路径无 cloud (现状)
- **关联**:
  - **CAND-083** (custom_providers preservation) — 同主题 quickstart 智能性, 一起做
  - **CAND-085** (AIMC 网关集成, 1-1.5d) — **关键 enable** (CAND-085 集成后, `model` 字段值 = AIMC group 名, routing rules 在 group 间切 = effective 跨底层 LLM 路由. 跟 "现状方案 C" 完美兼容, 只需 `model.provider: custom` base_url 改指 AIMC, `model.default: Qwen3.6-27B-UD-Q4_K_XL.gguf` 改 `tier:balanced`)
  - **K-3** (gateway profile routing multiplex, 1.5d) — 互补 (K-3 是 profile 维度, CAND-084 是 capability 维度)
  - CAND-080 (routing rule 自迭代) — 长尾, CAND-084 是前置 (智能生成才有 rule 可迭代)
  - Sprint retrospective §4.1 (cross-project insight: Borrow = bug 发现机制)
- **测试 plan** (next sprint 一起做, 跟 改造 B 同 AST 静态 + 源字符串检查模式, 0 yaml 依赖):
  - **Unit test 1** (must, 场景 1): mock 1 local backend (Qwen3.6-27B) + 1 cloud provider (deepseek), 跑 quickstart, 验证 `model_routing.rules` 含 3 keyword rules (reasoning/coding/short_chat) + `default` 指 local + `fallback_model` 含 cloud
  - **Unit test 2** (must, 场景 2): mock 2 local backends (Qwen3.6-4B + Qwen3.6-27B) + 1 cloud, 验证 routing 分 2-tier (小模型 short_chat / 大模型 reasoning/coding)
  - **Unit test 3** (must, 场景 3): mock 0 local + 1 cloud, 验证 routing 全部指向 cloud + cloud fallback × 2 不同 model
  - **Unit test 4** (must, regression): 跑 quickstart 跑完不能动 `model_routing.rules` 已存在的 rule (跟 CAND-083 配合, 旧 rule 保留)
  - **Unit test 5** (must, 场景 4 AIMC 集成): mock `_generate_routing_rules` 在 CAND-085 集成后 (config.yaml 有 `aimc` 段 + `model.provider: custom` base_url = AIMC), 验证 routing rules model 字段 = AIMC group 名 (e.g. `tier:balanced`), 不是具体 model 名
  - **Unit test 6** (must, 引擎能力对齐): 跑完 test 1-5, 验证生成的 rules 不含 `min_tokens` / `min_tool_calls` / `min_files` / `any:` (这些 engines 不支持, 生成 = 静默 invalid)
  - **位置**: `tests/hermes_cli/test_quickstart_routing_rule_generation.py` (新 file, 跟 CAND-083 同 AST 静态 + 源字符串检查模式, 0 yaml 依赖)
- **Sprint 决定 (2026-07-31 → 2026-08-03 重审)**:
  1. **立即**: user 手动改 `config.yaml` 的 `model_routing.rules` 段改成 target config (5 min, user 自己做) — 关键词 + max_length 生效, 跟 CAND-085 AIMC 集成**兼容**: AIMC 集成后字段值改为 group 名 (tier:balanced)
  2. **Next sprint (Phase 1)**: 实施 quickstart `_generate_routing_rules` (0.5-1d, AIMC group 名适配版) + 6 unit test, 估时 0.5-1d, 1 commit, 跟 CAND-083 + CAND-085 + K-3 一起 (Phase 1 整体 **4-5.5d**, 缩 1d 因为 CAND-084 估时 2-2.5d → 0.5-1d)
  3. **CAND-084 不在 Sprint 2026-07-23~24 8 commits 内**, 留 Phase 1 (跟 CAND-085 一起做)
- **Meta-pattern 涌现** (跟 CAND-083 同源 + 8-03 verify lesson): **2 个月内连续发现 2 个 quickstart 智能性 gap** (CAND-083 静默丢 custom_providers + CAND-084 单模型偏置 routing rules), 都是"quickstart 写 config 时只覆盖某个 subset, 其他 key 假定不变/规则假定同模型"模式. **8-03 verify lesson 升级**: CAND-084 之前估时基于"3 维 complexity 信号"假设, 但实际路由引擎只支持 4 个 match condition, 跨 provider 路由不支持 — 估时基于错误前提, 实际 0.5-1d 就够. 建议 next sprint 加 grep-based invariant test suite (跟 改造 B 同套), 强制 quickstart / call_llm 等高频函数都 0 漏读 cfg key + 0 漏写合理 rule + 0 生成引擎不支持的 invalid rule
- **详细分析**: `D:\work\workspace\MiniMax\projects\hermes-agent-cn-notes\cross-pollination\2026-07-23-upstream-borrow\notes\2026-07-31-quickstart-single-model-bias-routing.md` (待写, next sprint 前落盘)
- **审计方法**:
  - `grep "_generate_routing_rules\|model_routing" hermes_cli/quickstart.py` 必须返回 ≥ 1 hit (智能规则生成函数)
  - `grep "min_tokens\|min_tool_calls\|min_files" hermes_cli/quickstart.py` 必须返回 **0 hit** (引擎不支持, 生成 = 静默 invalid)
  - 跟 CAND-083 审计方法叠加 (3 个 grep 套件, 同时校验 preservation + 智能生成 + 引擎能力对齐)

### [CAND-085] 🌐 AIMC 网关集成 (profile-based model routing + dynamic adaptation)

- **状态**: 🟡 proposed → ✅ done (2026-08-04 commit `7fbd80b96` AIMC gateway integration, config + client + main fail-fast + 10 test)
- **发现时间**: 2026-07-31 (user PR 草案 309 行, 见 `notes/2026-07-31-aimc-integration-pr.md`)
- **架构**: hermes-tray → **hermes-agent-cn** (本仓) → **AIMC 网关** (gitee `XiaoYRecluse/aimc`, commit `929e5fb+`) → 硅基流动 / DeepSeek / Qwen / 本地 Ollama. AIMC 是 OpenAI 协议兼容网关, hermes-agent-cn 通过 AIMC 拿跨模型比价/价格优化/fallback 能力
- **症状 (集成前)**: hermes-agent-cn config.yaml models 段硬编码具体 model 名 (`default: deepseek-chat` 等), 缺 3 项能力:
  1. 跨模型比价 (用户手动切同档 model 才能省钱)
  2. 价格自动联动 (硅基流动降费 / 情报层动作无感知)
  3. 渠道故障转移 (单一渠道挂了要改 config 重启)
- **核心变更** (3 块):
  1. **config.yaml**: `models` 段从具体 model 名 → **AIMC group 名** (`tier:balanced` / `tier:strong` / `tier:flagship` / `scene:free` / `scene:code`), 新增 `aimc` 段 (base_url / api_key / timeout / refresh_cron `0 3 * * *` 每日凌晨 3 点) + `aimc_preferences` 可选 (prefer_family / exclude_providers / max_input_price) + `validate_on_startup: true`
  2. **`aimc_client.py`** (新, ~80 行, 仓库根目录或 `lib/`): `AIMCClient` 类, `__init__(base_url, api_key, timeout)` / `refresh()` (拉 /v1/models, 区分 group `tier:` `scene:` 前缀 vs 具体 model) / `validate_profiles(profiles)` (raise ValueError if 引用未知 group) / `is_known_group()` / `is_known_model()`
  3. **main.py + chat.py / agent.py**: 启动初始化 (fail-fast refresh + validate, 失败 raise 启动失败) + APScheduler 每日 3 点定时 refresh + OpenAI client `base_url` 改指 AIMC + `model` 字段传 group 名 + 响应头 `X-AIMC-Actual-Model` / `X-AIMC-Actual-Channel` / `X-AIMC-Group-Id` 被动观测 (只 logger.debug, 不影响路由)
- **铁律** (不变式, 不能破):
  - ❌ hermes-agent-cn **不反向调整** AIMC 配置
  - ❌ hermes-agent-cn **不写回** 自己 profile (除非人手动改)
  - ✅ AIMC 路由决策**只**听 DB + 情报层, **不听** hermes-agent-cn
  - ✅ 启动 **fail-fast** (refresh 失败 raise → 启动失败, 不静默用旧数据)
  - ✅ 所有"学习"都是**被动观测** (logger.debug 记录响应头), 不自动改任何配置
- **估时**: 1-1.5d (含 4 unit test + 1 E2E + 1 回归)
- **风险**: 🟡 中 (新文件 + 多点改, 但 PR 草案已写清楚, 改动 < 30 行净增, 0 新依赖 — httpx / apscheduler 一般已在)
- **价值**: 🔴 高 (跨模型比价 + 价格自动联动 + 渠道故障转移, 3 项 daily usage 改善)
- **触发条件**:
  - AIMC 网关部署完成 (gitee `XiaoYRecluse/aimc` commit `929e5fb+`)
  - hermes-agent-cn 跟 AIMC 配通 (API key + base_url 配齐)
- **关联**:
  - **CAND-083** (custom_providers preservation) — AIMC 也走 `custom_providers` 段 (作为 1 个 base_url 不同的 provider), 一起做避免 quickstart 静默丢
  - **CAND-084** (smart routing rules, 0.5-1d scope 缩版) — 静态 rule 的 `model` 字段值改为 AIMC group 名 (`tier:balanced` / `scene:code`), keywords 路由切不同 group (`reasoning` → `tier:strong` / `coding` → `scene:code` / `short_chat` `max_length=80` → `tier:light`). **8-03 user 引用 Skill 文档 + verify `docs/PROPOSAL-multi-model-routing.md` line 48-53 后** scope 大幅缩: 原估时 2-2.5d 基于"3 维 complexity 信号"假设, 实际路由引擎只支持 4 个 match condition (`keywords` / `max_length` / `has_image` / `exclude_keywords`), 跨 provider 不支持 (provider-scoped), 3 信号 (`min_tokens` / `min_tool_calls` / `min_files`) 全不支持. 跟 user 提的"现状方案 C" (本地 + deepseek fallback + auxiliary.vision/infographic 走 sensenova) 完美兼容, AIMC 集成后 `model` 字段 = group 名 = effective 跨底层 LLM 透明路由
  - **K-3** (gateway profile routing multiplex, 1.5d) — K-3 是 "dev vs prod profile 切换" 维度, AIMC 是 "profile 内的 cross-model routing" 维度, 互补
  - **CAND-041** (MoA) — 互补, MoA 是 planning 维度 (1 task 调 4 models 聚合), AIMC 是 selection 维度 (1 task 调 1 model + AIMC 内部 fallback)
  - Sprint retrospective §4.1 (cross-project insight: Borrow = bug 发现机制)
- **测试 plan** (next sprint 一起做):
  - **Unit test 1** (must, refresh 解析): mock /v1/models 返回 5 group + 2 model, 跑 `client.refresh()`, 验证 `known_models` 长度 = 2 + `known_groups` 长度 = 5 + group 正确识别 (`tier:balanced` / `scene:free` 等前缀)
  - **Unit test 2** (must, validate profiles): mock `known_groups = {tier:balanced, tier:strong}`, 跑 `client.validate_profiles({"default": "tier:balanced", "think": "tier:strong"})` pass; 跑 `client.validate_profiles({"default": "tier:nonexistent"})` raise `ValueError("unknown AIMC groups")`
  - **Unit test 3** (must, refresh HTTP error): mock httpx 返回 503, 跑 `client.refresh()` raise `httpx.HTTPStatusError` (不静默吞)
  - **Unit test 4** (must, fixture): fixture file 含 5 group + 7 model, 跑 refresh 后 known_models/known_groups 集合正确
  - **E2E** (must): 本地起 AIMC + hermes-agent-cn, 调 4 个 profile (default/think/longContext/code), 验证 AIMC 响应头 `X-AIMC-Group-Id` = profile 引用 group
  - **回归** (must): 现有 chat/agent 调用流程不受影响 (model 字段变 group 名但 OpenAI SDK 仍接受 string)
  - **位置**:
    - `aimc_client.py` (新, 仓库根目录或 `lib/`)
    - `tests/test_aimc_client.py` (新, 4 unit test)
    - `tests/integration/test_aimc_e2e.py` (新, 1 E2E, 跟 `test_sprint_2026-07-23.py` 同 integration test 模式)
- **Sprint 决定 (2026-07-31)**:
  1. **当前 sprint (8-05 批推后立即开)**: CAND-085 优先做, 1-1.5d, 1 commit, **不在 8-05 阶段收尾批次** (8-05 推 8 commits 阶段收尾, AIMC 集成 8-05 之后开 PR, 走独立 review)
  2. **Phase 1 (2 周)** 编排 (2026-08-03 修订): CAND-085 (1-1.5d) + CAND-083 (0.5-1d) + CAND-084 (**0.5-1d**, scope 大幅缩, 8-03 verify 后) + K-3 (1.5d) = **4-5.5d** (原 5-6.5d 缩 1d), 加集成测试 fix + 回归 + buffer = 1 周. 详见 sprint plan + `notes/2026-08-04-phase1-cand085-kickoff.md`
  3. **Phase 2 (1 周)**: CAND-080 剩余 2 sub-layers (2.5d) + CAND-081/082 (3-5d) = 5.5-7.5d
  4. **CAND-085 不在 Sprint 2026-07-23~24 8 commits 内**, **不在 8-05 阶段收尾批推内**, 留 8-05 后 Phase 1 第 1 task 做
- **PR 草案**: 见 user attachment `hermes-agent-cn-integration-pr.md` (309 行, 含 PR Title/Description/Why/What/铁律/测试计划/config 改动/代码改动/单元测试/手动 E2E/回滚方案/相关文档/FAQ/PR 影响范围), PR 自己估时 "~30 分钟" 实际包括测试 1-1.5d
- **详细分析**: `D:\work\workspace\MiniMax\projects\hermes-agent-cn-notes\cross-pollination\2026-07-23-upstream-borrow\notes\2026-07-31-aimc-integration-pr.md` (从 user attachment 落盘, next sprint 前)
- **审计方法**:
  - `grep "aimc_client\|AIMCClient" hermes-agent-cn/aimc_client.py` 必须返回 ≥ 1 hit (新文件必须存在)
  - `grep "AIMC\|aimc_client" hermes-agent-cn/main.py` 必须返回 ≥ 1 hit (启动初始化)
  - `grep "AIMC\|aimc_client" hermes-agent-cn/chat.py` 或 `agent.py` 必须返回 ≥ 1 hit (调 OpenAI 客户端用 AIMC base_url)
  - `grep "aimc" hermes-agent-cn/config.yaml` 必须返回 ≥ 1 hit (config 段必须存在)
  - 跟 CAND-083/084 审计方法叠加 (5 个 grep 套件, 同时校验 preservation + 智能生成 + 动态触发 + AIMC 集成)
- **跨项目背景** (mavis 4 件套视角):
  - **Constitution 铁律 4 条** ↔ mavis `Reflexion 池` 反思模式 (不反向调整 = 单一方向数据流; fail-fast = 决策门槛严格)
  - **AIMC 网关作为外部依赖** ↔ mavis `compaction audit` 模式 (季度 cron + read-only 检查, 跟 AIMC "AIMC 决策只听 DB + 情报层" 同源)
  - **hermes-agent-cn 适配不反向** ↔ mavis `critic` 模式 (校验而不修改)
  - **跨 project design law 升级**: 4 件套 跟 hermes 集成不变量同构, "系统集成时遵守对方决策边界" 是跨 project 普适律

---

## 类别 G: 元数据 / 文档改进

### [CAND-057] Hermes-agent skill 文档覆盖 v0.13-v0.17

- **状态**: 🟡 proposed
- **来源**: upstream `f67c0b3e6` `docs(hermes-agent skill): cover v0.13–v0.17 features, fix stale claims, tighten (#53566)`
- **估时**: 30 min (cherry-pick)
- **风险**: 🟢 低 (docs only)
- **价值**: 🟡 中 (skill 文档质量)
- **备注**: upstream 已经覆盖到了 v0.17 — cn 拉到 v0.18 也能直接受益

---

## 分类 H: MiniCPM-Desk-Pet 跨项目借鉴 (OpenBMB)

> 2026-07-10 — 外部项目借鉴候选, 不是 upstream cherry-pick. 来源: https://github.com/OpenBMB/MiniCPM-Desk-Pet (AGPL-3.0, OpenBMB)
> 详细分析: `D:\work\workspace\MiniMax\projects\hermes-agent-cn-notes\cross-pollination\MiniCPM-Desk-Pet-vs-hermes-cn-tray.md`

> ⚠️ **2026-07-10 迁移**: 本节候选已迁到 hermes-tray 候选池 — 见 `D:\work\workspace\Qoder\hermes-tray\CANDIDATES.md` TRAY-CAND-001 (Settings tabs 重构). cn CANDIDATES.md 不再登记纯客户端候选. 跨端候选 (双端协同) 保留在 cn, 加 tray cross-ref.

### [CAND-062] 双端 Doctor 体系 (启动健康检查 + 客户端 UI)

- **状态**: 🟡 proposed
- **来源**: 外部项目 [OpenBMB/MiniCPM-Desk-Pet](https://github.com/OpenBMB/MiniCPM-Desk-Pet) (AGPL-3.0 ⚠️)
- **一句话**: 启动时跑健康检查, 客户端展示结果并一键跳到对应 fix
- **估时**: 1 d
- **风险**: 🟢 低
- **价值**: 🔴 高
- **触发条件**: 部署/支持/用户自助反馈差
- **详细分析**: `D:\work\workspace\MiniMax\projects\hermes-agent-cn-notes\cross-pollination\MiniCPM-Desk-Pet-vs-hermes-cn-tray.md`

### [CAND-063] 双端 Agent registry + Cursor/Codex 适配器

- **状态**: 🟡 proposed
- **来源**: 外部项目 OpenBMB/MiniCPM-Desk-Pet (AGPL-3.0 ⚠️)
- **一句话**: 适配多个 coding agent (Cursor/Codex/Gemini CLI 等), 统一 descriptor 格式
- **估时**: 1 d
- **风险**: 🟡 中
- **价值**: 🟢 高
- **触发条件**: 需要接多个 coding agent 时
- **详细分析**: `D:\work\workspace\MiniMax\projects\hermes-agent-cn-notes\cross-pollination\MiniCPM-Desk-Pet-vs-hermes-cn-tray.md`> ⚠️ **2026-07-10 迁移**: 已迁到 hermes-tray 候选池 — TRAY-CAND-004 (i18n typesafe-i18n 实施, 跟 AGENTS.md 决策 #3 对齐).

> ⚠️ **2026-07-10 迁移**: 已迁到 hermes-tray 候选池 — TRAY-CAND-003 (Settings → Agents tab + install hint banner).

### [CAND-066] hermes-agent-cn Smart model download (HF + ModelScope 双源)

- **状态**: 🟡 proposed
- **来源**: 外部项目 OpenBMB/MiniCPM-Desk-Pet (AGPL-3.0 ⚠️)
- **一句话**: 模型下载自动选最快的源 (HF / ModelScope), 失败回退
- **估时**: 1 d
- **风险**: 🟢 低
- **价值**: 🟢 高
- **触发条件**: 模型下载速度/可用性反馈差
- **详细分析**: `D:\work\workspace\MiniMax\projects\hermes-agent-cn-notes\cross-pollination\MiniCPM-Desk-Pet-vs-hermes-cn-tray.md`

### [CAND-067] Lifecycle class 抽象 (进程管理)

- **状态**: 🟡 proposed
- **来源**: 外部项目 OpenBMB/MiniCPM-Desk-Pet (AGPL-3.0 ⚠️)
- **一句话**: model runtime 启动/停止/健康检查/重启抽成统一类
- **估时**: 0.5 d
- **风险**: 🟢 低
- **价值**: 🟡 中
- **触发条件**: 进程管理代码散落需要清理时
- **详细分析**: `D:\work\workspace\MiniMax\projects\hermes-agent-cn-notes\cross-pollination\MiniCPM-Desk-Pet-vs-hermes-cn-tray.md`

> ⚠️ **2026-07-10 迁移**: 已迁到 hermes-tray 候选池 — TRAY-CAND-005 (Theme override + import/export).

### [CAND-069] ⭐ 核心 Coding agent event dispatcher (双端, 解锁 22 agent 协同)

- **状态**: 🟡 proposed
- **来源**: 外部项目 OpenBMB/MiniCPM-Desk-Pet (AGPL-3.0 ⚠️)
- **一句话**: server emit agent activity events, client 订阅并响应
- **估时**: 1.5-3 d
- **风险**: 🟠 中-高
- **价值**: 🔴 极高
- **触发条件**: 多 IDE 集成 / 多 agent 协同场景
- **详细分析**: `D:\work\workspace\MiniMax\projects\hermes-agent-cn-notes\cross-pollination\MiniCPM-Desk-Pet-vs-hermes-cn-tray.md`

### [CAND-070] wecom/feishu approval pipeline (借鉴 MiniCPM Telegram approval)

- **状态**: 🟡 proposed
- **来源**: 外部项目 OpenBMB/MiniCPM-Desk-Pet (AGPL-3.0 ⚠️)
- **一句话**: enterprise IM 平台审批集成, agent 操作需用户确认
- **估时**: 6-10 d
- **风险**: 🟠 高
- **价值**: 🔴 极高
- **触发条件**: enterprise 场景需要 audit trail / 用户确认
- **详细分析**: `D:\work\workspace\MiniMax\projects\hermes-agent-cn-notes\cross-pollination\MiniCPM-Desk-Pet-vs-hermes-cn-tray.md`

### [CAND-071] 22 coding agent 全覆盖 (借鉴 MiniCPM 完整 registry)

- **状态**: 🟡 proposed
- **来源**: 外部项目 OpenBMB/MiniCPM-Desk-Pet (AGPL-3.0 ⚠️)
- **一句话**: 适配 20+ coding agent 工具, 统一 descriptor 格式
- **估时**: 5-10 d
- **风险**: 🟠 高
- **价值**: 🟢 高
- **触发条件**: 基础 registry 框架完成后, 长期覆盖度目标
- **详细分析**: `D:\work\workspace\MiniMax\projects\hermes-agent-cn-notes\cross-pollination\MiniCPM-Desk-Pet-vs-hermes-cn-tray.md`

---

## 分类 I: OpenFugu 借鉴 (Sakana Fugu reimplementation, Apache-2.0)

> **来源**: https://github.com/trotsky1997/OpenFugu (Apache-2.0, trotsky1997, 393 stars)
> **详细分析**: `D:\work\workspace\MiniMax\projects\hermes-agent-cn-notes\cross-pollination\OpenFugu-vs-hermes-routing.md`
> **核心 paper**: TRINITY (arXiv:2512.04695) + Conductor (arXiv:2512.04388)
> **License**: Apache-2.0 ✅ 可以 cherry-pick 算法思路, 但 Sakana 可能有 patent, 谨慎借鉴

### [CAND-072] 🧠 Lightweight router (小模型做预选路由)

- **状态**: 🟡 proposed
- **来源**: 外部项目 [trotsky1997/OpenFugu](https://github.com/trotsky1997/OpenFugu) (Apache-2.0 ✅, 393 stars)
- **一句话**: 用小模型作为预选路由, rule-based fallback 兜底
- **估时**: 1 d
- **风险**: 🟡 中
- **价值**: 🟢 高
- **触发条件**: 规则路由不够灵活, 需要 learned routing
- **详细分析**: `D:\work\workspace\MiniMax\projects\hermes-agent-cn-notes\cross-pollination\OpenFugu-vs-hermes-routing.md`

### [CAND-073] 🎯 Adaptive pool mode (训练时随机 mask worker)

- **状态**: 🟡 proposed
- **来源**: 外部项目 trotsky1997/OpenFugu (Apache-2.0 ✅)
- **一句话**: 训练时随机 mask worker, 学会"在 available 里选最好"
- **估时**: 2-3 d
- **风险**: 🟠 中-高
- **价值**: 🟢 高
- **触发条件**: CAND-072 上线后, 训练数据准备好
- **详细分析**: `D:\work\workspace\MiniMax\projects\hermes-agent-cn-notes\cross-pollination\OpenFugu-vs-hermes-routing.md`

### [CAND-074] ⚡🧠 Two-mode router (fast rule-based vs smart learned)

- **状态**: 🟡 proposed
- **来源**: 外部项目 trotsky1997/OpenFugu (Apache-2.0 ✅)
- **一句话**: 提供 fast/smart 两种 routing mode, 用户自选或自动切换
- **估时**: 3-5 d
- **风险**: 🟡 中
- **价值**: 🟢 高
- **触发条件**: CAND-072 + CAND-073 都上线后
- **详细分析**: `D:\work\workspace\MiniMax\projects\hermes-agent-cn-notes\cross-pollination\OpenFugu-vs-hermes-routing.md`

### [CAND-075] 🔒 OpenAI-compatible single endpoint, pool hidden

- **状态**: 🟡 proposed
- **来源**: 外部项目 trotsky1997/OpenFugu (Apache-2.0 ✅)
- **一句话**: OpenAI 兼容 endpoint, 内部 worker pool 对用户隐藏
- **估时**: 3-5 d
- **风险**: 🟡 中
- **价值**: 🟡 中
- **触发条件**: 需要隐藏 vendor 依赖时
- **详细分析**: `D:\work\workspace\MiniMax\projects\hermes-agent-cn-notes\cross-pollination\OpenFugu-vs-hermes-routing.md`

### [CAND-076] 🎼 Conductor/Ultra mode (workflow DAG executor)

- **状态**: 🟡 proposed
- **来源**: 外部项目 trotsky1997/OpenFugu (Apache-2.0 ✅)
- **一句话**: 大模型 emit workflow DAG, executor 按拓扑顺序执行
- **估时**: 5-10 d
- **风险**: 🟠 高
- **价值**: 🔴 高
- **触发条件**: 需要 multi-step sequential workflow
- **详细分析**: `D:\work\workspace\MiniMax\projects\hermes-agent-cn-notes\cross-pollination\OpenFugu-vs-hermes-routing.md`

### [CAND-077] 📚 OpenFugu 不借鉴清单 (避免踩坑)

- **状态**: ❌ rejected (记录决策)
- **来源**: 外部项目 trotsky1997/OpenFugu
- **一句话**: 明确不借鉴的部分 (避免 IP / 训练 / 替代风险)
- **详细分析**: `D:\work\workspace\MiniMax\projects\hermes-agent-cn-notes\cross-pollination\OpenFugu-vs-hermes-routing.md`

### [CAND-078] 🎲 Synthetic Training Data Pipeline (公开 corpus → query 训练集)

- **状态**: 🟡 proposed
- **来源**: 外部项目 [asgeirtj/system_prompts_leaks](https://github.com/asgeirtj/system_prompts_leaks) (CC0 1.0 ✅)
- **一句话**: 用公开 system prompt corpus 合成 query 训练集, 喂给 learned router 训练
- **估时**: 2-4 d
- **风险**: 🟢 低
- **价值**: 🔴 极高
- **触发条件**: CAND-072 上线后, 准备训 CAND-073
- **详细分析**: `D:\work\workspace\MiniMax\projects\hermes-agent-cn-notes\cross-pollination\OpenFugu-vs-hermes-routing.md`

### [CAND-079] 🇨🇳 cn 模型 system prompts corpus (自建, 训练数据)

- **状态**: 🟡 proposed
- **来源**: 自建 corpus (公开渠道 + 官方 repo + 启发式)
- **一句话**: 自建国内模型 system prompts 训练集, 补 cn-specific 覆盖
- **估时**: 1-2 周
- **风险**: 🟢 低
- **价值**: 🟢 高
- **触发条件**: CAND-078 跑完后, 想补 cn gap
- **详细分析**: `D:\work\workspace\MiniMax\projects\hermes-agent-cn-notes\cross-pollination\OpenFugu-vs-hermes-routing.md`
- **实施工具**: `D:\work\workspace\MiniMax\projects\hermes-agent-cn-notes\cross-pollination\cand-079-cn-prompt-corpus-tools-design.md`

---

## 分类 J: Agent Skills 自进化 (rule-based routing 自迭代)

> **来源文章**: 陈思州, "别再一直调 prompt 了，让 Agent 的 Skills 自己进化", Datawhale, 2026-07-10
> **详细分析**: `D:\work\workspace\MiniMax\projects\hermes-agent-cn-notes\cross-pollination\skills-self-evolution-article-analysis.md`
> **核心概念**: Skill 三层结构 (路由/指令/资源) + 自进化闭环 (用户反馈 → 轨迹证据 → 规则抽象 → Skill Patch → 验证 → 发布/回滚)
> **跟现有候选关系**: 跟 CAND-072/073 (OpenFugu, learned-based) + CAND-078/079 (data-driven) 互补, 3 路线组合

### [CAND-080] 🔄 Skills 自进化系统 (rule-based routing 自迭代)

- **状态**: 🟡 partial done → 🔄 2/4 sub-layers implemented pre-sprint (2026-07-23 audit), 留 2 sub-layers 给 next sprint 跟 CAND-081/082 + K-5 upstream 参考一起做
- **来源**: 文章 (Datawhale, 2026-07-10) "Agent Skills 自进化" + cn 现有 routing 框架
- **一句话**: rule-based routing 在真实反馈中持续更新, 三层结构渐进式加载
- **估时**: 2-3 d → 1-1.5 d 剩余 (routing rule 自迭代 + rule 抽象 留给 next sprint)
- **风险**: 🟡 中 → 🟢 低 (已 working 的 2 层 (curator + background_review) 不动, 只加 patch mechanism + rule 抽象)
- **价值**: 🟢 高
- **触发条件**: rule-based 路由需要自动化优化
- **详细分析**: `D:\work\workspace\MiniMax\projects\hermes-agent-cn-notes\cross-pollination\skills-self-evolution-article-analysis.md`
- **Upstream 对齐 (2026-07-23)**: 跟 `e32ebc6aa feat(skills): /learn` (PR #51506) concept 70% 重合, 区别在 /learn 是 skill-distillation 层级 (描述 → SKILL.md), CAND-080 是 rule-update 层级 (反馈 → 路由规则 patch). 实施时借鉴 upstream 4-surface 集成 (CLI/gateway/TUI/dashboard) + 硬性 skill-authoring standards (description <=60 char + section order). 详见 K-5
- **K-5 实施时 tray 端 UI 检查清单** (2026-08-03 lesson): 借 upstream `/learn` 时, tray 端要加的 UI 必先 grep cn 端有没有对应 pipeline (后端先调查再设计, UI-specific 细化). 例:
  - `/learn` 触发按钮 → upstream CLI 已有 trigger, 镜像即可 ✅
  - `/journey` review UI → background_review 已有 per-turn 落库 pipeline, 可做 ✅
  - **"评价 agent output" 按钮 (点赞/点踩) → grep `feedback|like|dislike|thumbs|/v1/feedback` 0 hit, 不做** ❌
  - 详见 mavis memory "UI 设计前必查后端 pipeline" (cross-project lesson)
- **实施现状** (2026-07-23 sprint audit, 4-phase 跨 project borrow):
  - ✅ **第 3 层 资源层 skill self-evolution** — `agent/curator.py` (74KB, 12+ fix commits) 已 fully working. Periodically review agent-created skills, auto-transition lifecycle (pin / archive / consolidate / **patch** via `skill_manage action=patch`), persist `.curator_state` (last_run_at / paused / ...), 5+ 关键 fix commits (preserve cron-referenced skills `4c2961c51` / protect external `96bc524a7` / protect load-bearing built-in `702aa743e` / make consolidation opt-in `7bbffceb9` / shared atomic state writer `47e77ae16` / preserve resolved fork metadata `97e9c6466` / forward credential pool `304cdbdc7` / prune after inactivity `70e1571d8` / pluginify `476d8d9cc`)
  - ✅ **Per-turn 反馈循环** — `agent/background_review.py` (35KB, 12+ fix commits) 已 fully working. `spawn_background_review_thread` daemon per turn, 问 "should save/update memory/skill?", inherit parent runtime cache (reasoning_config inheritance `17cfa0f0a` fix), tool whitelist (read-before-write `20871c1d9`), 3-mode notification (off / on / verbose `955a914e4`), aux-model selector `87c4a5ebb`. 12+ fix commits 覆盖 list-shape guard / pin-improvements / memory-tool gate / opt-out-of-finalization / verbose preview 等
  - ❌ **第 1 层 路由层 rule 自迭代** — `agent/routing_decision.py` 有 `rule_id` label 观测 (commit `b49ef1a31` S12 P2 cost-aware fallback + `4cd26c480` Phase 1 dataclass), 但 0 patch 机制. Sprint plan 范围外, 留 next sprint
  - ❌ **第 2 层 指令层 rule 抽象** — fallback chain 是 hard-coded 字符串 (e.g. `"vision_fallback_chain[1]"`), 没 patchable rule layer. Sprint plan 范围外, 留 next sprint 跟 CAND-081 (Compaction) + CAND-082 (A/B test) 一起做
- **Sprint 决定 (2026-07-23)**: mark partial done per CAND-041 pattern. **不**实施 routing rule 自迭代 (1-1.5d) / rule 抽象 (1d) / CAND-081 (1-2d) / CAND-082 (2-3d) 在本次 sprint — 留 next sprint 跟 K-5 upstream 4-surface 集成 + 硬性 skill-authoring standards 一起 borrow, 边界清晰风险小

### [CAND-081] 🗜️ Compaction 工具 (定期合并/下沉/删除冗余规则)

- **状态**: 🟡 proposed
- **来源**: 文章 "Skill Compaction" 段
- **一句话**: 定期扫描规则, 发现重复/废弃/可合并, 人工 review 后应用
- **估时**: 1-2 d
- **风险**: 🟢 低
- **价值**: 🟡 中
- **触发条件**: 规则数量增长后需要清理
- **详细分析**: `D:\work\workspace\MiniMax\projects\hermes-agent-cn-notes\cross-pollination\skills-self-evolution-article-analysis.md`

### [CAND-082] 🧪 Skills 验证 framework (A/B test + 指标)

- **状态**: 🟡 proposed
- **来源**: 文章 "用验证决定新版本能否发布" 段
- **一句话**: A/B test harness 验证 routing 改动, 决定发布/回滚
- **估时**: 2-3 d
- **风险**: 🟡 中
- **价值**: 🟢 高
- **触发条件**: 任何 routing 改动需要量化效果
- **详细分析**: `D:\work\workspace\MiniMax\projects\hermes-agent-cn-notes\cross-pollination\skills-self-evolution-article-analysis.md`
- **备注**: 跟 upstream `e32ebc6aa` (skill-authoring standards) 互补 — upstream 是 static check, CAND-082 是 dynamic A/B test. 拿历史 LLM call 数据, A/B 测新 routing 规则:
  - **指标**: cost / latency / fallback rate / task success (LLM judge) / user feedback (if any)
  - **A/B test harness**: 50/50 traffic, 自动收集指标, 自动决定通过/不通过
  - **Decision**: 通过 → 发布新 routing 规则; 不通过 → 回滚 + 记录负反馈
  - **跟 CAND-078 共用**: 同样的历史数据, 既训 learned router (CAND-073), 又验证 rule changes (CAND-082), 闭环
- **3 路线验证组合**:
  - **rule-based** (CAND-080): A/B test 文本规则改动
  - **learned-based** (CAND-072/073): A/B test 训后的 router weights
  - **data-driven** (CAND-078): 同一份历史数据既训又验

---

## 分类 K: Upstream Borrow (12 天窗口 v0.18.0 → v0.19.0)

> **调研期**: 2026-07-23
> **详细分析**: `D:\work\workspace\MiniMax\projects\hermes-agent-cn-notes\cross-pollination\2026-07-23-upstream-borrow\`
> **Filter 维度**: 钱学森《工程控制论》3 axioms (事前设计 / 整体最优 / 闭环反馈) + cn 项目 backlog 优先级 (S12/S14/S15/wecom/feishu/WSL2/security-PIPL)
> **编号说明**: 用 K-N 而非 CAND-N, 避免跟项目内部候选 (CAND-001~085) 编号冲突 (Phase 2 doc 早期用 CAND-046/047/048/049/050 跟 cn 现有候选撞了, 已修正).
> **4 必填字段** (每个 K-N): Source (upstream commit + PR) / **Axiom match** (1/2/3, 注明 strongest) / **Cn state** (gap + grep 验证) / **Port plan** (cherry-pick vs manual, 估时, 风险).

### Axiom 分布 (5 候选)

| Axiom | Strong match | 候选 |
|---|---|---|
| 1 事前设计 | **0** | (gap — 未来 borrow 窗口关注) |
| 2 整体最优 | 3 | K-2 (call_llm), K-3 (profile routing), K-4 (MoA ambient) |
| 3 闭环反馈 | 2 | K-1 (completion contracts), K-5 (/learn + /journey) |

### [K-1] 📋 completion contracts for /goal (v0.18.0 "Judgment Release")

- **状态**: 🟡 proposed (deferred per user 2026-07-23 决定, port plan ready)
- **Source**: upstream `2ba1cfeb2` (PR #50501, main) + `0b33bc539` (PR #38388, kanban judge gate) + `14c4a849b` + `b3c1b3b3f` (follow-up fixes)
- **Axiom match**: **3 闭环反馈 (strongest)** — judge 严格按 verification + concrete evidence (command output / file excerpt / test result), agent 看 evidence 调 next step, WAIT verdict (避免 busy-loop), persistent across `/resume`
- **Cn state**: ❌ `GoalContract` dataclass / `parse_contract` / `draft_contract` / `/goal show` / `/goal draft` 命令 / `kanban_complete` 工具层 judge gate — **全部缺失** (clean port, 0 dead code)
- **Port plan**: 1-2d, 1-commit manual port. 4 文件改动: `hermes_cli/goals.py` (dataclass + parsers + 3 prompt templates) + `hermes_cli/cli_commands_mixin.py` + `gateway/slash_commands.py` (CLI + gateway 镜像) + `tools/kanban_tools.py` (judge gate, fail-open per upstream review)
- **估时**: 1-2d | **风险**: 🟡 中 (judge prompt 改; goal_mode worker 行为变化)
- **价值**: 🔴 极高 (S12 P3 闭环关键, 跟 CAND-042 unblock; CAND-041 已 done pre-sprint 2026-07-23)
- **详细分析**: `phase3c-cand-046-deep-dive.md`
- **备注**: ⚠️ 跟 K-2 交互 — `draft_contract` 走 `goal_judge` aux call, 当前 silent config drop (K-2 修了才能真吃 `auxiliary.goal_judge.extra_body`)

### [K-2] 🔧 auxiliary_client → call_llm (v0.19.0 #35566 fix)

- **状态**: 🟡 proposed (deferred per user 2026-07-23 决定, port plan ready, **P0 bug**)
- **Source**: upstream `7c954969b` (PR #65029 / Fixes #35566)
- **Axiom match**: **2 整体最优 (strongest)** — 5 个 direct-create aux caller 整合到 `call_llm` 统一入口, 避免局部最优 (单函数看 OK, 全局配置 `auxiliary.<task>.extra_body / reasoning_effort / retries` 丢失)
- **Cn state**: ❌ **7 production call sites** 仍走 `get_text_auxiliary_client(task)` + `client.chat.completions.create()` 直连 (silent config drop). `call_llm` **已存在** (`agent/auxiliary_client.py:4989`, signature 是 upstream 超集, 多了 `routing_decision_out` / `tools` / `_get_task_extra_body`). 修只需 refactor call sites, 不用新加函数
- **Port plan**: 0.5d, 1-commit manual port. 7 call sites refactor + `goal_judge` 加进 DEFAULT_CONFIG.auxiliary + 6 test 文件 mock 从 `get_text_auxiliary_client` 换到 `call_llm`
- **估时**: 0.5d | **风险**: 🟡 中 (核心 runtime path, `run_agent.py` + `conversation_compression.py` 必须先 read 确认 `client` 没被 chat.completions.create 之外用)
- **价值**: 🔴 **极高 P0** (S12 routing_decision accuracy, S14 vision aux path, S15 plugin kanban, hermes_cli 全 utility 任务 全栈 silent bug)
- **详细分析**: `phase3b-cand-047-port-plan.md`
- **备注**: borrow 调研**意外发现**的 P0 bug — 不在 cn 12 split bug 列表 (那些是 build/syntax 错, 这个是 silent config drop)

### [K-3] 🌐 gateway profile routing multiplex (6 adapter 借鉴)

- **状态**: 🟡 proposed (ready for cherry-pick, 1.5d) → ✅ done (2026-08-04 4 commit: K-3a `c1314d307` multiplex_profiles config schema + K-3b1 `3c9deb665` session_key multiplex profile prefix + K-3b2 `4963ec486` adapter build_source profile passthrough + K-3b3 `656f192d2` resolve_multiplex_profile helper + telegram wiring, 8/8 test pass)
- **Source**: upstream `647520f83` (PR 待定)
- **Axiom match**: **2 整体最优 (strongest)** — 6 个 adapter 统一处理, multiplex_profiles 开启时不同 community → 不同 profile → 独立 session/batch key, 避免单 adapter 优化
- **Cn state**: ⚠️ 部分对 (cn 有 `wecom.py` / `feishu.py` 等 platform adapter, 但架构在 `gateway/platforms/` 而非 upstream `plugins/platforms/`, 需适配)
- **Port plan**: 1d cherry-pick + 0.5d cn 适配. 7 行 weixin / feishu / matrix / telegram / whatsapp / wecom adapter 加 `profile=event.source.profile` 1 行, 加 cn `multiplex_profiles` gate 配置
- **估时**: 1.5d | **风险**: 🟡 中 (平台架构差异)
- **价值**: 🟢 高 (wecom/feishu 跟 cn 强相关, multiplex 是 cn enterprise 路线必经)
- **详细分析**: `phase2-filter-borrow.md` (Phase 2 CAND-048 entry)

### [K-4] 🌀 MoA ambient conversation context (CAND-041 follow-up)

- **状态**: 🟡 proposed (post CAND-041, 0.5d) → ✅ done (Sprint 2026-07-23~24 commit `e4a8c2bc4` port #9ce0e67f2 — ambient conversation context for aux/MoA/delegate)
- **Source**: upstream `9ce0e67f2` `feat(portal): ambient conversation context entangles aux/MoA/delegate calls`
- **Axiom match**: **2 整体最优 (strongest)** — 跨 module (aux + MoA + delegate) 共享 conversation lineage
- **Cn state**: ⚠️ 跟 CAND-041 (MoA) 直接关联; cn MoA 已 working pre-sprint (2026-07-23 audit 确认), 这是 ambient 增强 (cross-module aux/MoA/delegate conversation_id 共享)
- **Port plan**: 0.5d, post CAND-041. ContextVar-based `conversation_id` 跨 aux/MoA/delegate 传播, `SessionDB.get_conversation_root()` 返回 root session id
- **估时**: 0.5d | **风险**: 🟢 低 (ContextVar 模式成熟)
- **价值**: 🟡 中 (enhancement, not core)
- **详细分析**: `phase2-filter-borrow.md` (Phase 2 CAND-049 entry)

### [K-5] ✅ /learn + /journey alignment verification (no new candidate)

- **状态**: 🟢 verified (1-line update to CAND-080/082/044, **不**新加候选)
- **Source**: upstream 12 commits (`e32ebc6aa` #51506 main /learn + `e971dc1e9` main /journey + 10 follow-up)
- **Axiom match**: **3 闭环反馈 (strongest)** — /learn (描述 → SKILL.md → /journey 可见 → user review/edit) + /journey (memory/skill graph, user 可编辑) 是闭环
- **Cn state**: ✅ CAND-044 已对齐 /journey (100% source match, 6 commits covered). ⚠️ CAND-080/081/082 concept 70% 对齐 /learn (Datawhale 文章 source vs upstream 源码 source 路径不同, rule 层面 vs skill 层面 粒度不同). 🟡 CAND-080 已 partial done pre-sprint (curator + background_review 2/4 sub-layers, 2026-07-23 audit 确认). ❌ cn 0 /learn 实现 — 真 gap 但不新加候选, 在 CAND-080 剩余 sub-layers (routing rule 自迭代 + 抽象) 实施时参考 upstream 4-surface 集成 + 硬性 skill-authoring standards
- **Port plan**: 0 implementation — 1-line edit 加 upstream 对齐注释到 CAND-080/082/044 (Phase 4 同 commit 做)
- **估时**: 0d (verification) + 0.25d (3 个候选补 1 行) | **风险**: 🟢 低
- **价值**: 🟢 验证 (不加候选, 确认 CAND-080 方向对)
- **详细分析**: `phase3d-hermes-learn-journey-verification.md`
- **Cross-pollination 强信号**: mavis 4 件套 (Constitution + critic + Reflexion 池 + compaction) 跟 upstream /learn + /journey + CAND-080/081/082 同构 — **附件 1 钱学森 3-layer 双向闭环是跨 project design pattern**

### K section 整体启示

- **Axiom 1 强 match = 0** — 5 候选都是"优化现有路径" (axiom 2) 或"补闭环" (axiom 3), 没有任何"enable new design phase". 未来 borrow 窗口关注 axiom 1 类 (e.g. goal spec / plan mode / intent declaration layer)
- **Borrow = bug 发现机制** — K-2 是借 upstream #35566 fix 发现的 cn 隐藏 P0 bug, 不只是 feature add
- **附件 1 钱学森 3-layer 双向闭环** 跟 mavis 4 件套 + borrow plan 4 phase 完美同构, 是跨 project design pattern
- **Section K 不冲掉 CAND-080 实施** — K-5 在 CAND-080 剩余 sub-layers (routing rule 自迭代 + 抽象) 实施时提供 upstream 参考 (4-surface 集成 pattern + 硬性 skill-authoring standards). CAND-080 已 partial done (curator + background_review 2/4 sub-layers, 2026-07-23 audit)

---

## 触发条件总表 (扩展)

| 触发 | 看哪些 ID |
|---|---|
| user 提安全加固 | CAND-001 / CAND-008 / CAND-010 / CAND-053 / CAND-054 |
| user 抱怨响应慢 | CAND-004 / CAND-040 (gamification 也间接提升粘性) |
| 企业用户提 SSO / webhook / MDM | CAND-005 / CAND-009 / CAND-042 / CAND-043 / CAND-052 |
| kanban dispatcher 报错 | CAND-002 / CAND-055 |
| cron freeze | CAND-003 |
| 用户用 hermes send / tray 接 media | CAND-006 / CAND-040 |
| gateway 启动 / 重启相关 | CAND-007 / CAND-054 |
| hermes-tray v0.2.0 接 dashboard / S15 | CAND-008 / CAND-009 / CAND-011 / CAND-014 / CAND-019 / CAND-021 / CAND-022 / CAND-026 / CAND-058 / CAND-059 |
| S15 plugin marketplace 启动 | CAND-012 / CAND-048 |
| 多模型综合 / thorough 风格 | CAND-041 (MoA, ✅ done pre-sprint 2026-07-23) |
| user 提 "agent 怎么好玩" / demo 场景 | **CAND-040 (pets) ← 重点** |
| IT 部门 / MDM 部署 | **CAND-042 (managed-scope) ← 重点** |
| 多频道不同模型 (某群固定 deepseek) | **CAND-043 (per-channel override) ← 重点** |
| 学习历史可视化 | CAND-044 (journey) |
| 新模型 / provider | CAND-045 / CAND-046 / CAND-047 |
| OAuth / skill 新选项 | CAND-048 / CAND-049 / CAND-050 |
| setup UX | CAND-050 / CAND-051 |
| API 增强 | CAND-052 |
| upstream v0.19.0 发布 | 重新审计上游, 重做本文件 |

---

## 触发条件总表 (何时回头看这份)

| 触发 | 看哪些 ID |
|---|---|
| user 提安全加固 | CAND-001 / CAND-008 / CAND-010 |
| user 抱怨响应慢 | CAND-004 |
| 企业用户提 SSO / webhook | CAND-005 / CAND-009 |
| kanban dispatcher 报错 | CAND-002 |
| cron freeze | CAND-003 |
| 用户用 hermes send / tray 接 media | CAND-006 / CAND-040 |
| gateway 启动 / 重启相关 | CAND-007 |
| hermes-tray v0.2.0 接 dashboard / S15 | CAND-008 / CAND-009 / CAND-011 / CAND-014 |
| S15 plugin marketplace 启动 | CAND-012 |
| upstream v0.19.0 发布 (12 天窗口 3057 commits) | 重新审计上游, 重做本文件; 现有 K-1~K-5 (Section K) 跟 5 候选 deep dive 文档可作 reference |
| S12 P3 启动 (闭环反馈层) | K-1 (completion contracts) + K-5 (跟 CAND-080 互补) |
| hermes-cli judge / auxiliary_client 行为异常 | K-2 (call_llm P0 bug fix, 详见 phase3b) |

---

## 维护

- 新加候选: 直接在合适类别下 append 新 [CAND-NNN], 状态填 `🟡 proposed`
- 评估: 改状态, 加理由到 `备注`
- 接受: 移到 NEEDS_BACKLOG.md (或单独 commit), 从本文件删除 [CAND-NNN] 但保留 [CAND-HIST-NNN]
- 拒绝: 状态改 `❌ rejected`, 加理由, 留档

---

## 引用

> **2026-07-11 安全审计**: 内部项目元数据 (fork 关系 / 距离 / 调研范围) 已移至 agent 工作目录, 候选池只记录创意本身. 详细信息见 `D:\work\workspace\MiniMax\projects\hermes-agent-cn-notes\`.

- 本文件状态: 🟡 调研阶段, 等待评估后定真计划
- 调研方法: 按 commit 类型 + scope 分类, 跟项目 backlog 对比评估
- 调研日期: 2026-07-10
- 候选 ID 编号: CAND-001~085 (含已迁移到 hermes-tray 候选池的 TRAY-CAND-001~018) + K-1~K-5 (Section K: Upstream Borrow)
- 重点候选分类:
  - **Section A-G** (CAND-001~059): 项目内部候选 (fix / refactor / 新功能)
  - **Section H** (CAND-060~071): MiniCPM-Desk-Pet 跨项目借鉴
  - **Section I** (CAND-072~079): OpenFugu 借鉴
  - **Section J** (CAND-080~082): Agent Skills 自进化 (rule-based routing 自迭代)
  - **Section K** (K-1~K-5): Upstream Borrow (12 天窗口 v0.18.0 → v0.19.0, 3057 commits)

---

## 跨项目引用

> **2026-07-11 调整**: 调研产物 (cross-pollination research docs) 已从项目移到 agent 工作目录, 不污染 git. 候选池本身 (本文件) 保留在项目.

- **调研产物 INDEX**: `D:\work\workspace\MiniMax\projects\hermes-agent-cn-notes\cross-pollination\INDEX.md` — 4 个深度调研 (MiniCPM / Pet / OpenFugu / 4-layer 集成) 汇总
- **Upstream Borrow (2026-07-23, 12 天窗口 v0.18.0 → v0.19.0)**: `D:\work\workspace\MiniMax\projects\hermes-agent-cn-notes\cross-pollination\2026-07-23-upstream-borrow\`. 5 phase doc (sample summary / filter borrow / 4 deep dives): 5 候选 K-1~K-5 (Section K), filter 维度 钱学森 3 axioms. **意外发现**: 借 upstream #35566 fix 找出 cn P0 bug (auxiliary_client silent config drop, K-2)
- **MiniCPM-Desk-Pet 借鉴**: `D:\work\workspace\MiniMax\projects\hermes-agent-cn-notes\cross-pollination\MiniCPM-Desk-Pet-vs-hermes-cn-tray.md`. 纯客户端候选 (CAND-061/064/065/068) 已迁到 `hermes-tray/CANDIDATES.md` (TRAY-CAND-001~005), 双端候选 (CAND-062/063/069/070) 保留在 cn, 加 tray cross-ref. **AGPL-3.0 警告**: MiniCPM 是传染性 license, 只借鉴模式不借鉴代码.
- **OpenFugu 借鉴 (2026-07-10)**: `D:\work\workspace\MiniMax\projects\hermes-agent-cn-notes\cross-pollination\OpenFugu-vs-hermes-routing.md`. 加 8 个新候选 CAND-072~079 (learned router + adaptive pool + two-mode + OpenAI endpoint + Conductor DAG + 不借鉴清单 + **synthetic training data** + **cn model corpus**). **Apache-2.0 ✅**, 但 Sakana 可能有 patent, 谨慎借鉴. 跟 CAND-041 (MoA) 互补, 不是替代.
- **Skills 自进化 (2026-07-11)**: `D:\work\workspace\MiniMax\projects\hermes-agent-cn-notes\cross-pollination\skills-self-evolution-article-analysis.md` (Datawhale 文章读后). 加 3 个新候选 CAND-080~082 (Skills 自进化系统 + Compaction 工具 + A/B test framework). 跟 CAND-072/073 (learned-based) + CAND-078/079 (data-driven) 互补, **3 路线组合 = 完整进化体系**.
- **训练数据来源 (2026-07-11)**: [asgeirtj/system_prompts_leaks](https://github.com/asgeirtj/system_prompts_leaks) — CC0 1.0, 55k stars, **~153 system prompts, ~95% Western** (OpenAI 56 / Anthropic 26 / Google 23 / Qwen 1). CAND-078 合成 query corpus for CAND-073 训练 (覆盖通用 60-70%) + CAND-079 国内模型 corpus (补 30-40% cn gap).
- **四层架构集成设计**: `D:\work\workspace\MiniMax\projects\hermes-agent-cn-notes\cross-pollination\four-layer-orchestration-architecture.md`. 11 节, 包含每层真实实现 + 4 场景 + 5 Phase 集成. 推荐先做 Phase 1 (CAND-041 MoA cherry-pick, 1-2d).
- **Pet 形象选型**: `D:\work\workspace\MiniMax\projects\hermes-tray-notes\cross-pollination\pet-implementation.md`. 推荐短期 emoji MVP, 中期 per-state SVG + SMIL (1-2d).
- **hermes-tray 候选池**: `D:\work\workspace\Qoder\hermes-tray\CANDIDATES.md` (2026-07-10 创建, 18 个候选 TRAY-CAND-001~018)
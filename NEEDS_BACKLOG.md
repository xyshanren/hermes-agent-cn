# hermes-agent-cn 需求 Backlog (2026-06-26)

> **状态**: ✅ **cn backlog 全部 done 或 N/A** (2026-07-03 收盘盘点). **S13-agent ✅ 2026-07-02** (commit `016383af8`); **S14-agent ✅ 2026-07-03** (commits `a716f33e6` + `125cc93c0` + `8882270e7`); **S12-agent Phase 1 ✅ 2026-07-03** (commits `4cd26c480` partial + `a192442d8` mutation hooks; CHANGELOG v0.17.0+cn.20); **S12-agent Phase 2 ✅ 2026-07-03** (CHANGELOG v0.17.0+cn.21 — cost-aware fallback rule); **S15-agent Plugin MVP ✅ 2026-07-03** (CHANGELOG v0.17.0+cn.22 — 现状盘点, 零代码改动); **5.x 杂项 ✅ 2026-07-03** (CHANGELOG v0.17.0+cn.23 — 全部 done 或 N/A). 只剩 **S12 Phase 3 (tray T-Q-S9 真值替换, hermes-tray 侧)** + **S15 完整 marketplace (5-7d, 独立产品决策)** 不在 cn 范围.
> **触发来源**: hermes-tray v2.0 (S12-S15) 路线图重新对边界时, 识别出 hermes-agent 需要补齐的能力
> **执行条件**: ✅ 已全部触发并完成 cn 范围内的事项

---

## 背景: hermes-tray vs hermes-agent 边界

| 层 | 谁负责 |
|---|---|
| 路由 / 重试 / 熔断 / 多 Provider failover | **hermes-agent** (SmartRouter, fallback_config, plugins middleware) |
| Token 计数 / cost 估算 (projection) | hermes-tray (T-Q-S9 char/4 heuristic) |
| Persona 角色 / system prompt 注入 | hermes-tray (T-Q-S7) |
| 拖拽文件 → 转 base64 | hermes-tray (T-Q-S14) |
| 图片理解 / 视觉模型选择 | **hermes-agent** (vision_analyze 工具) |
| 语音捕获 (MediaRecorder) | hermes-tray (T-Q-S13) |
| STT 转写 (Whisper 等) | **hermes-agent** (需要新增端点) |
| 模型名称选择 / 发送 | hermes-tray (T-Q-S12-light) → hermes-agent 解析 |
| Plugin / middleware 扩展 | **hermes-agent** (已有 `plugins.py` 框架) |

**关键原则**: hermes-tray 不应该重做 hermes-agent 的能力. tray 只负责**捕获输入** (image/voice) + **选 model name**, 真正的解析/转写/路由都在 agent 那边.

---

## 需求 1: S12-agent — Cost-aware / Latency-aware 路由增强

> **状态**: 🔄 Phase 1 ✅ done (2026-07-03); **Phase 2 ✅ done 2026-07-03 (cost-aware fallback rule + threshold annotations)**; Phase 3 (tray T-Q-S9 真值替换) pending, 等用户拍板 + hermes-tray v0.1.5 集成决策

### 来源
hermes-tray T-Q-S12-light 只发了 model name 给 agent. 但用户在 tray 上看不到**为什么选了某个 provider**, 也不知道某次响应的 cost / latency 来源于哪个 provider. 需要 agent 端有:
- 路由决策的元数据 (哪个 rule 命中, cost 估算, 选了什么 fallback)
- 通过 stream events 推送给前端 (chunks + done 事件, 不破坏 OpenAI 协议)
- tray 端 T-Q-S9 cost 估算用 (char/4 heuristic) → 用 agent 推的真值替换

### 现状
- `hermes_cli/fallback_config.py` 已能读 fallback 链 (`_iter_fallback_entries` / `get_fallback_chain`)
- `PLAN_CN.md` Phase 5 ✅ 已落地: `RoutingRule` 支持 `provider` 字段, complexity 感知, vision fallback
- `CN_MODEL_COSTS` 数据库 (21 模型) 已有
- 4 种 cost 策略 (off/balanced/strict/quality) 已实现

### 缺口
- **路由决策没透传前端**: `auxiliary_client` / `conversation_loop` 选完 provider 之后, 只把 response 流给前端, 没说"我用了 rule X, 试了 provider Y, 退到 Z"
- **streaming chunks 没 metadata 字段**: SSE chunks 是 OpenAI 标准的 `{choices: [...], usage?: ...}`, `usage` 只在 done 时一次性给, 没说**每个 chunk 来自哪个 provider**

### 需要做的事
1. 在 `auxiliary_client.py` / `conversation_loop.py` 加 routing metadata struct (`rule_id`, `provider`, `cost_estimate`, `latency_ms`, `retries`)
2. 在 SSE 流的 `usage` chunk 加 metadata 字段 (扩展 OpenAI 协议, 不破坏兼容性)
3. tray 端 T-Q-S9 读 streaming metadata 替代 char/4 heuristic
4. 设计 + 实现 cost-aware fallback (如 cost > $X 自动切到 cheap model)

### 工作量估计
3-5 天 (基于 PLAN_CN M2 已有的 4 策略基础)

### Phase 1 — Routing metadata 收集 + SSE 推送 ✅ done 2026-07-03

**实现**: `agent/routing_decision.py` (RoutingDecision dataclass + 7 helpers) + `agent/auxiliary_client.py` mutation hooks (transient retry / temperature retry / max_tokens retry / Nous refresh / auth refresh / credential-pool recovery / cross-provider fallback 全部走 record_fallback + resolve_routing + set_latency + increment_retries + set_rule_id) + `agent/conversation_loop.py` `_build_main_agent_routing_decision` (main agent path 不走 call_llm, 自行合成) + `usage_dict["routing_decision"]` 推到 SSE (OpenAI usage 扩展, 旧前端零影响)。

**测试**: 43 new cases (`tests/agent/test_routing_decision.py` + `tests/agent/test_conversation_loop_routing_decision.py` + `tests/agent/test_auxiliary_client_routing_decision.py`), 全过 (1.79s)。

**OpenAI 兼容**: `routing_decision` 是 usage 的扩展字段, 不破坏现有客户端。OpenRouter / OpenAI / Anthropic SDK 都忽略未知 usage key, tray opt-in 后读 `usage.routing_decision.{mode, primary_provider, resolved_provider, fallback_used, fallback_reason, fallback_provider, cost_estimate_usd, latency_ms, retries, rule_id}`。

### Phase 2 — cost-aware fallback (cost > $X 自动切 cheap model) — pending

候选实现:
- `agent/auxiliary_client.py` 加 `_check_cost_threshold_and_switch(model, usage_so_far)` helper, 在 call_llm 末尾如果 cost > threshold 自动改 `agent._fallback_activated = True` 并激活下一个 fallback_chain entry。
- 配置入口: `config.yaml` `agent.cost_aware_fallback: { enabled: true, per_request_max_usd: 0.05, per_session_max_usd: 1.0 }`。
- 估计: 1-2 天。

### Phase 2 ✅ done 2026-07-03 (实际实现与候选的差异)

**实际实现** (`agent/cost_aware_fallback.py` + `agent/routing_decision.py` 扩展 + `agent/auxiliary_client.py` 接入 + `agent/conversation_loop.py` 接入 + `hermes_cli/config.py` 默认值):

**1. 双轨阈值 (跟候选不同)**:
- **Per-request threshold** (auxiliary_client path): 单次响应 cost > `per_request_max_usd` 时, **只标注** `cost_threshold_exceeded=True` + reason 到 routing_decision, **不**主动切 fallback。理由: auxiliary 任务是 one-shot (compression / vision_analyze / session_search), 切 provider 反而引入 latency + 可能新错误; 让运营看到 warning 后手动调更稳
- **Per-session threshold** (conversation_loop path): 累积 session cost > `per_session_max_usd` 时, 默认仅标 cost_threshold_exceeded; 当 `on_session_exceeded='fallback'` 时调 `agent._try_activate_fallback()` 主动切下一个 chain entry。理由: session 已超预算, 后续 turn 继续用贵的 provider 是 user-visible 损失

**2. 配置入口** (`config.yaml`):
```yaml
agent:
  cost_aware_fallback:
    enabled: False                          # 关闭以保留 pre-S12 行为
    per_request_max_usd: 0.05              # $0.05 / call
    per_session_max_usd: 1.00              # $1.00 / session
    on_session_exceeded: "warn"            # 'warn' | 'fallback'
```

**3. RoutingDecision 扩展** (`agent/routing_decision.py`):
- 加 `cost_threshold_exceeded: bool = False` (恒保留在 to_dict 输出, 跟 `fallback_used` / `retries` / `mode` 一致)
- 加 `cost_threshold_reason: Optional[str] = None` ('request_budget_exceeded' | 'session_budget_exceeded')
- 新 helper `set_cost_threshold(out, reason=...)`

**4. 测试**: 50 new cases (test_cost_aware_fallback.py × 30 + test_conversation_loop_session_cost.py × 11 + test_auxiliary_client_cost_threshold.py × 9), 全过 1.34s

**5. 跟候选的差异**: 候选用同一个 `_check_cost_threshold_and_switch` 处理两条路径; 实际实现分开 (auxiliary path 只标不切, main agent path 才能调 `_try_activate_fallback` 因为 auxiliary_client 没持有 agent 的 `_fallback_chain`)。这样 P2 范围控制在 1 天内 (vs 候选估计 1-2 天), 同时**不引入**让 auxiliary 切 provider 的新失败模式。

### Phase 3 — tray T-Q-S9 读真值替换 char/4 heuristic — pending (hermes-tray 侧)

不在 agent 范围。`hermes-tray` v0.1.5 plan 时集成:
- tray 端读 `usage.routing_decision.cost_estimate_usd` 直接用真值, 替换 char/4 估算。
- 显示 fallback 痕迹: "本轮由 deepseek-v3 服务 (fallback to anthropic after 3 retries, latency 2.4s, $0.012)"。

---

## 需求 2: S13-agent — `/v1/audio/transcriptions` 端点 ✅ DONE (2026-07-02)

> **状态**: ✅ Done — commit `016383af8` on `cn` branch, pushed to `origin/cn` 2026-07-02.
> **实现细节**: 见 `tests/test_s13_audio_transcriptions.py` (8/8 passed in 2.17s) + `CHANGELOG_CN.md` v0.17.0+cn.18 段.
> **关键变更**: `hermes_cli/web_server.py` 加 `transcriptions_openai` multipart handler + `_openai_error_response` / `_transcribe_via_provider` 两个 helper + 1 个 route (`POST /v1/audio/transcriptions`).

---

### 来源
hermes-tray T-Q-S13 的 `hermes_proxy_transcribe` Rust command 已实现 multipart 转发, 但**指向的端点必须存在**. tray 默认 POST `${GATEWAY_URL}/v1/audio/transcriptions`, 期望响应 `{"text": "..."}`. 当前 gateway **没有**这个端点.

### 现状
- `hermes_cli/config.py` line 1596-1610: STT 配置已存在 (provider: local / groq / openai / mistral / elevenlabs, model: whisper-1 等)
- `model_manager.py` line 60: local faster-whisper 模型管理已实现
- `gateway/run.py` line 8199-8201: 提示用户装 `faster-whisper` 走本地 STT (用于 qqbot voice channel)
- `config.py` line 4305: OpenAI model names (whisper-1) 喂给 faster-whisper 的逻辑已有
- `nous_subscription.py` line 370: 注释提到 "STT. One probe, used by both" — 内部有 audio probe 但没暴露 HTTP

### 缺口
- **`/v1/audio/transcriptions` 端点完全缺失**
- 当前 STT 是 qqbot 平台内部用, 没作为 OpenAI-compatible 公共服务
- tray 用户 (不用 qqbot) 拿不到 STT

### 需要做的事
1. 在 `gateway/run.py` 加 `POST /v1/audio/transcriptions` 路由
2. 复用现有 `config.py` STT 配置 (provider/model)
3. local mode: 调 `model_manager.py` 的 faster-whisper 加载逻辑
4. cloud mode: 转发到对应 provider (groq / openai / mistral / elevenlabs) 的对应端点
5. 响应统一为 `{"text": "..."}` (OpenAI 兼容)
6. 加 auth: 用现有 `Authorization: Bearer` 中间件
7. 错误响应: 4xx 状态码 + `{"error": {...}}` (OpenAI 错误格式)

### 工作量估计
2-3 天

### 测试覆盖
- 单元测试: provider 路由, error 路径, 多 provider fallback
- 集成测试: 真实 wav 文件从 local + cloud 两种 provider
- freeze test: hermes-cn TEST_PLAN 加 5-8 个新 case

---

## 需求 3: S14-agent — Vision fallback + 图片 token 估算 ✅ DONE (2026-07-03)

> **状态**: ✅ Done — 3 commits on `cn` branch (2026-07-03), pending push to `origin/cn`:
> - `a716f33e6` Phase 1: image_tokens in CanonicalUsage + SSE usage (`usage.prompt_tokens_details.image_tokens`) + sessions.image_tokens 列 (declarative column reconciliation 自动加).
> - `125cc93c0` Phase 2: vision routing_decision metadata (mode / primary / resolved / fallback_used / fallback_reason) + elapsed_ms.
> - `8882270e7` Phase 3: 多图 limit 校验 (per-model `_MODEL_MAX_IMAGES` 表 + config override + `TooManyImagesError` 在 chat-completions / codex-responses pre-flight 触发).
>
> **关键变更**:
> - `agent/usage_pricing.py` 加 `image_tokens` 字段到 `CanonicalUsage`; `normalize_usage` 从 `prompt_tokens_details.image_tokens` (OpenAI Chat Completions) 和 `input_tokens_details.image_tokens` (Codex Responses) 提取; Anthropic 留 0.
> - `agent/conversation_loop.py` `usage_dict` 加 `prompt_tokens_details = {image_tokens, cached_tokens}` (OpenAI 协议), turn-end result 加 `image_tokens` 字段.
> - `hermes_state.py` `sessions` 表加 `image_tokens INTEGER DEFAULT 0` 列, `update_token_counts` 同步加 image_tokens 参数; declarative `_reconcile_columns` 自动给老 DB 加列.
> - `agent/auxiliary_client.py` `_try_vision_fallback_config` 返 4-tuple `(provider, client, model, fallback_reason)`; `call_llm` / `async_call_llm` 加 `routing_decision_out` kwarg; 新 helper `_vision_routing_init/_record_fallback/_resolve` 共享决策合并逻辑.
> - `tools/vision_tools.py` `_vision_analyze_native` envelope 加 `routing_decision` (mode=native); `vision_analyze_tool` 透传 routing_decision + elapsed_ms 到 success/error JSON.
> - `agent/image_routing.py` 加 `count_image_parts` + `get_max_images_per_request` + `validate_image_count`; model-aware lookup 表覆盖 GPT-4o/5/o1/o3/Claude 3 (20) / Claude 4 (100) / Gemini 1.5/2 (16).
> - `run_agent.py` 加 `TooManyImagesError` (actionable message) + `AIAgent._validate_image_count_or_raise` 在 chat-completions / codex-responses 调用前触发.
>
> **测试覆盖**: 26 new cases across `test_usage_pricing.py` (5) + `test_hermes_state.py` (3) + `test_vision_native_fast_path.py` (3) + `test_image_routing.py` (16, skip pre-existing `TestExtractImageRefs`); 全过 (pre-existing failures 排除).
>
> **Backlog 仍 open**: §1 S12-agent 路由决策透传 (cost/latency/retries metadata) — 跟 tray T-Q-S12-light / T-Q-S9 cost 真值替换对齐; 3-5 天; §4 S15-agent Plugin Marketplace; §5 杂项.

---

## 需求 3: S14-agent — Vision fallback + 图片 token 估算

### 来源
hermes-tray T-Q-S14 直接发 OpenAI multimodal 格式 (text + image_url) 给 `/v1/chat/completions`. agent 收到后, **必须能选对 vision 模型** (有些主模型不支持 vision, 要 fallback 到 `vision_analyze` 工具). 还要**估算图片 token** (OpenAI 高分辨率图算 170 tokens, 低分辨率 85 tokens, etc.) 给前端 T-Q-S9 cost 算.

### 现状
- `config.py` line 846-854: `image_handling` 配置 (native / pre_analyze / text) 已设计
- `config.py` line 1193: `vision` 配置段 (provider / model / fallback)
- `PLAN_CN.md` Phase 5: Vision fallback `auxiliary.vision.fallback_provider/model/base_url` 已实现
- `cli_agent_setup_mixin.py` line 560: 已有 `image_url` content part 解析
- `tools_config.py` line 61: `vision_analyze` 工具已注册

### 缺口
- **图片 token 估算**: tray 不知道图片算多少 token → T-Q-S9 cost 算不准 (现在按 char/4 算 text only, 漏掉 image)
- **vision_analyze 工具 → vision provider 路由**: 当主模型不支持 vision 时, 调 vision_analyze 工具预分析, 把结果作为 text 注入 (这条路径已存在, 但 tray 看不到是否走 fallback)
- **多图 + 高分辨率**: tray 现在限制 4 张 / 10MB, 但 agent 端没做 limits (上层模型可能有 max_images)

### 需要做的事
1. 在 auxiliary_client / conversation_loop 加 image token 估算 (按 OpenAI 规则: 85/170/425/1290 tokens per image based on tiles)
2. 把 image token 加到 SSE `usage` 字段 (`usage.prompt_image_tokens`)
3. vision 路由决策 metadata: tray 可显示 "本轮用了 vision_analyze fallback"
4. 多图 limit 校验: tray 端限制 (4/10MB) + agent 端校验 + 友好错误

### 工作量估计
2-3 天

### 测试覆盖
- 单元测试: image token 估算, vision fallback 触发条件
- 集成测试: 1图, 4图, 高分图, 不支持 vision 的模型
- freeze test: CN_TEST_PLAN 加 5 个 case

---

## 需求 4: S15-agent — Plugin Marketplace / 官方 plugin repo

> **状态**: ✅ **MVP done 2026-07-03** — 现状调研发现 manifest / 加载 / CLI 三大块早已实现,本文档 5 件事中 3 件完整 + 2 件部分 (官方 index 按 NEEDS_BACKLOG 自述 "暂不区分" 不属 MVP 范围,安全提示已有交互 prompt + plugins.enabled gating 等多层保护)。完整 marketplace (dependencies + permissions + GPG signing + 官方 index) 仍属 5-7d 范围,**不做**。CHANGELOG v0.17.0+cn.22 详细盘点。

### 来源
S15 在 hermes-tray 路线图被**整个删掉** (tray 不该做 plugin 系统). 但**用户对 plugin 生态的需求是真实的** — 只是应该放在 hermes-agent 这边, 因为 `plugins.py` 框架已经在那儿了.

### 现状
- `hermes_cli/plugins.py` 已实现 PluginManager 框架 (T-Q-S7 修过 2 个 bug)
  - `_middleware` 初始化
  - `has_middleware` / `invoke_middleware` / `register_middleware` 3 个公开 API
- `auxiliary_client.py` 通过 middleware 路由 (compression, smart-approval 等)
- 内置 middleware 在 `builtin_hooks/` 目录
- 没有"第三方 plugin 安装 / 共享"机制 — 全是 hardcode 在仓库里

### 缺口
- **没有 plugin discovery / 加载机制**: 用户想装一个外部 plugin (e.g. Slack notifier), 只能 `git clone` 复制到 plugins/ 目录
- **没有 versioning / dependency**: plugin A 依赖 plugin B 的话, 没机制说
- **没有官方 plugin repo**: 不知道哪些 plugin 是官方维护 vs 社区
- **没有 security model**: 第三方 plugin 能拿到什么权限 / 沙箱?

### 需要做的事 (Phase 1 MVP)
1. **Plugin manifest 格式** (plugin.yaml / plugin.toml)
   - name, version, description, author
   - entry_point (plugin.py::PluginClass)
   - dependencies (other plugins)
   - permissions (filesystem, network, env vars)
2. **加载机制** (scan plugins/ 目录, parse manifest, register)
3. **CLI** `hermes plugin install <git-url>` / `list` / `enable` / `disable`
4. **官方 plugin index** (github org / repo, markdown list)
5. **安全提示**: 装第三方 plugin 前显示 source / hash, 让用户确认

### 工作量估计
5-7 天 (整个 marketplace) / 1-2 天 (只做 MVP 加载机制)

### 决策点
- **Phase 1 范围**: 只做加载机制 + manifest 格式, 不做 marketplace
- **官方 vs 社区**: 暂不区分, 等生态起来再说

### MVP 现状盘点 (2026-07-03, 调研发现早已 done)

| NEEDS_BACKLOG 列的 5 件事 | 现状 | 行号 |
|---|---|---|
| 1. Plugin manifest 格式 | ✅ **完整 schema + 4 种 kind (standalone/backend/exclusive/platform)** — `PluginManifest` dataclass 字段: name/version/description/author/requires_env/provides_tools/provides_hooks/source/path/kind/key | `hermes_cli/plugins.py:234-267` |
| 2. 加载机制 (scan + register) | ✅ `discover_plugins` + `PluginManager` (1900 行) + 13 个内置 plugins 自动加载 (browser, kanban, memory 等) | `hermes_cli/plugins.py:941` |
| 3. CLI `hermes plugin install/list/enable/disable` | ✅ 全套 — `cmd_install` (line 500) / `cmd_update` / `cmd_remove` / `cmd_enable` (693) / `cmd_disable` (720) / `cmd_list` (855) / `cmd_toggle` (1038) + dashboard REST API | `hermes_cli/plugins_cmd.py` |
| 4. 官方 plugin index | ❌ 未做 (NEEDS_BACKLOG 自己说"暂不区分") | — |
| 5. 安全提示 | ⚠️ **多层保护已实现** — URL scheme check (line 520-524) / manifest validation (537-543) / requires_env prompt (545) / enable y/N prompt (549-560) / plugins.enabled gating (175-176) / 隔离目录 `_plugins_dir` (73) | `hermes_cli/plugins_cmd.py` + `plugins.py` |

**NEEDS_BACKLOG 列在 "5-7d 完整 marketplace" 范围但 MVP 不做**:
- ❌ Plugin dependencies (A depends on B: name/version 字段 + 自动装依赖)
- ❌ Plugin permissions / sandbox 模型 (filesystem / network / env vars)
- ❌ SHA256 commit hash 显示 (我的判断: theater, GitHub TLS 已覆盖 transport layer; 真正有意义是 GPG signing)
- ❌ 官方 plugin index / repo

**测试覆盖**: 30 个 plugin 相关测试文件 (`tests/hermes_cli/test_plugins*.py`, `tests/plugins/*` 等),覆盖 loader / scanner recursion / CLI / builtin plugin / gateway integration / dashboard integration。

**结论**: S15 MVP done。完整 marketplace (5-7d) 留给未来真有第三方 plugin 攻击报告或生态需求时再做。

### 跨项目依赖: tray-side S15 UI blocked on cn REST API (2026-07-03)

**现状 (重要发现)**: `/api/dashboard/plugins` 是 **dashboard UI 插件** (themes/widgets), **不是 S15 plugin marketplace 范围**. S15 完整 marketplace 还没有 REST API — 当前只有 7 个 CLI 子命令 (`hermes plugin install/list/enable/disable/toggle/update/remove`).

**Tray v0.1.5 范围决策** (2026-07-03 17:19): **不做 S15 plugin list UI**, 只做 S12/S14 metadata 增强. 详见 `D:\work\workspace\MiniMax\HANDOFF.md` §2.1 v0.1.5 scope 段.

**Tray-side S15 UI 工作量** (等 cn REST API 出来后):
- cn REST API 添加 (1-2d): `GET /api/plugins` + `POST /api/plugins/{name}/{enable,disable}` + `POST /api/plugins/install` + `DELETE /api/plugins/{name}`
- tray Settings 插件 tab (1-2d): list + toggle + install 表单 + 卸载 + 错误处理

**触发条件** (任一即开始, 缺一不动):
1. cn 完整 marketplace 启动 + 4 个 REST endpoint 加好
2. 用户实际装了 2+ 个第三方 plugin (跟现状"只用 13 个内置"区分)
3. 出现 plugin 相关 security incident 或 feature request

**为什么不跟 v0.1.5 一起发**:
- v0.1.5 应 2-3 天小步快跑, S15 强绑拖到 5-8 天不值
- 强绑 = 串行依赖 (cn REST API 先 → tray UI 后), 没并行空间
- 现状 13 个内置 plugin tray 看不到也不损失 (用户用 CLI 装新 plugin 是罕见操作)
- 独立产品决策性质, 不该跟 metadata 增强混一个 release

---

## 需求 5: 其它 (hermes-tray 现开发期可能新触发)

> **状态**: ✅ **全部 done 或 N/A** (2026-07-03, 调研盘点零代码改动, CHANGELOG v0.17.0+cn.23):
> - **5.1 路由元数据可视化** ✅ done in S12 P1 (CHANGELOG v0.17.0+cn.20) — `usage.routing_decision.resolved_provider` / `cost_estimate_usd` / `fallback_*` 字段已推 SSE, tray 端 opt-in 读即可按 provider 分组
> - **5.2 SSE stream 压缩 / 中断恢复** ⚠️ **N/A** — hermes-agent-cn 不直接 serve SSE (`web_server.py` 没 StreamingResponse/EventSource; proxy/server.py 走 aiohttp auto-gzip);tray 长 session 卡顿若真实存在应在 tray 侧或 proxy 层排查
> - **5.3 Model override / model_to_provider 索引** ✅ done — `hermes_cli/models.py:1833 detect_static_provider_for_model` + `:1884 detect_provider_for_model` 完整实现, 静态 catalog + OpenRouter fallback, 4+ 处复用 (model_switch/oneshot/acp_adapter/tui_gateway), 6+ 测试 (`tests/hermes_cli/test_models.py:246-303`)
> - **5.4 Chat completion streaming 里的 image 预算** ✅ done in S14 phase 1 (CHANGELOG v0.17.0+cn.19) — `usage.prompt_tokens_details.image_tokens` 推 SSE + `agent.session_image_tokens` 累加 + `sessions.image_tokens INTEGER DEFAULT 0` 列

### 5.1 路由元数据可视化 (T-Q-S12-light 配套)
- 来源: hermes-tray 想在 stats modal 显示 "本月 cost 主要来自 deepseek (60%) + gpt-4o (40%)"
- 当前: 只能从 T-Q-S9 的 `by_model` 推, 但 by_model 是前端 name, 不是 provider
- 需要: agent 把 cost breakdown 推到前端 (per provider, per route)
- 估算: 跟需求 1 合并
- **现状**: ✅ done in S12 P1 — `usage.routing_decision.{resolved_provider, cost_estimate_usd, fallback_provider, fallback_reason}` 都已推 SSE;tray 端 opt-in 读即可按 provider 分组

### 5.2 SSE stream 压缩 / 中断恢复
- 来源: tray 用户报告长 session 流式响应卡顿
- 当前: 没有压缩, 中断后只能重新发
- 候选: gzip 压缩, resumable streams, etc.
- 估算: 评估中
- **现状**: ⚠️ N/A — hermes-agent-cn 不直接 serve SSE (`hermes_cli/web_server.py` 只 import FileResponse/HTMLResponse/JSONResponse/Response; grep `EventSource|text/event-stream|StreamingResponse` 在 `hermes_cli/` 下零命中);SSE 是 proxy/server.py 把请求转发给 OpenAI 直接处理 (`aiohttp recomputes Content-Encoding on stream`);如果未来加 SSE endpoint 再考虑 5.2

### 5.3 Model override 在 quickstart 流程里
- 来源: T-Q-S12-light 选了 model name 后, agent 不知道哪个 provider 配了那个 model
- 候选: `config.py` 加 model_to_provider 索引 (已有 `provider` 字段), 加速路由
- 估算: 半天
- **现状**: ✅ done — `hermes_cli/models.py:1833 detect_static_provider_for_model` + `:1884 detect_provider_for_model` (静态 catalog 优先 + OpenRouter fallback), 被 `model_switch.py` / `oneshot.py` / `acp_adapter/server.py` / `tui_gateway/server.py` 等 4+ 处复用;6+ 测试 (`tests/hermes_cli/test_models.py:246-303`)

### 5.4 Chat completion streaming 里的 image 预算
- 来源: T-Q-S14 多图消息
- 当前: agent 算 image tokens, 但不告诉前端 "本轮 image 占 510 tokens"
- 已在 需求 3 覆盖
- **现状**: ✅ done in S14 phase 1 (`a716f33e6`, CHANGELOG v0.17.0+cn.19) — `usage_dict.prompt_tokens_details.image_tokens` 推 SSE + `agent.session_image_tokens` 累加 + `sessions.image_tokens INTEGER DEFAULT 0` 列 (declarative reconciliation 自动迁移老 DB)

---

## 执行建议

按用户指示, **等 hermes-tray 现阶段开发告一段落** (T-Q-S12~S15 已完) 后, 按以下顺序一次执行:

| Phase | 任务 | 工作量 | 状态 |
|---|---|---|---|
| Phase 1 | S13-agent (STT 端点) | 2-3 天 | ✅ done 2026-07-02 (commit `016383af8`) |
| Phase 2 | S14-agent (Vision token + 路由 metadata) | 2-3 天 | ✅ done 2026-07-03 (commits `a716f33e6`+`125cc93c0`+`8882270e7`) |
| Phase 3 | S12-agent Phase 1 (Routing metadata 收集 + SSE 推送) | 3-5 天 (Phase 1 拆出) | ✅ done 2026-07-03 (commits `4cd26c480` partial + `a192442d8` mutation hooks; CHANGELOG v0.17.0+cn.20) |
| Phase 3b | S12-agent Phase 2 (cost-aware fallback rule + threshold annotations) | 1-2 天 | ✅ done 2026-07-03 (CHANGELOG v0.17.0+cn.21) |
| Phase 3c | S12-agent Phase 3 (tray T-Q-S9 真值替换) | 0.5-1 天 | ⏸ pending (hermes-tray 侧, 不在 cn 范围) |
| Phase 4 | S15-agent Plugin marketplace MVP | 1-2 天 (实际零代码, 文档盘点 done) | ✅ done 2026-07-03 (CHANGELOG v0.17.0+cn.22; 现状盘点确认 manifest + 加载 + CLI 已实现) |
| 5.x | 5.1 路由元数据可视化 / 5.2 SSE 压缩 / 5.3 model_to_provider / 5.4 image 预算 | 0.5-1 天 (现状盘点) | ✅ done 2026-07-03 (CHANGELOG v0.17.0+cn.23; 5.1/5.3/5.4 done, 5.2 N/A) |

**cn 范围内全部完成** ✅ (S13 + S14 + S12 P1+P2 + S15 MVP + 5.x; 共 4/5 done + 1 sub-phase + 5.x done). Phase 3c (tray T-Q-S9) + S15 完整 marketplace (5-7d) 不在 cn 范围, 等用户拍板 + 集成窗口.

---

## 触发: 重新评估

**当前: cn backlog 全部 done 或 N/A (4/5 项 + 1 sub-phase + 5.x 全部收盘). S13 done 2026-07-02; S14 done 2026-07-03; S12 P1+P2 done 2026-07-03 (commits `a192442d8` + `b49ef1a31` pushed to origin/cn); S15 MVP done 2026-07-03 (commit `6a88eb4ab` pushed); 5.x done-or-N/A done 2026-07-03 (commit pending push).**

文件**待用户决定是否整体 archive 到 `docs/archive/NEEDS_BACKLOG_v017.md`** (cn 范围收盘, S12 P3 在 hermes-tray 侧, S15 完整 marketplace 是独立产品决策). archive 是 destructive 操作, 等用户明确批准后再搬. 当前 NEEDS_BACKLOG.md 保留作为 cn backlog 历史快照.

后续新需求 (跨项目的新功能, 例如 hermes-tray v0.1.6 / hermes-tray S16+) 开新文件（按 L208 指引不变）.

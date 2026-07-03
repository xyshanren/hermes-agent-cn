# hermes-agent-cn 需求 Backlog (2026-06-26)

> **状态**: 🔄 部分完成 (2/5 done): **S13-agent ✅ 2026-07-02** (commit `016383af8`); **S14-agent ✅ 2026-07-03** (commits `a716f33e6` + `125cc93c0` + `8882270e7`); §4 S12 / §5 S15 / 6.x 杂项 pending, 等用户拍板续作
> **触发来源**: hermes-tray v2.0 (S12-S15) 路线图重新对边界时, 识别出 hermes-agent 需要补齐的能力
> **执行条件**: ✅ 已触发 (S13 完成 2026-07-02; 累积 backlog 继续等用户拍板续作 + hermes-tray v0.1.3 集成决策)

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

---

## 需求 5: 其它 (hermes-tray 现开发期可能新触发)

### 5.1 路由元数据可视化 (T-Q-S12-light 配套)
- 来源: hermes-tray 想在 stats modal 显示 "本月 cost 主要来自 deepseek (60%) + gpt-4o (40%)"
- 当前: 只能从 T-Q-S9 的 `by_model` 推, 但 by_model 是前端 name, 不是 provider
- 需要: agent 把 cost breakdown 推到前端 (per provider, per route)
- 估算: 跟需求 1 合并

### 5.2 SSE stream 压缩 / 中断恢复
- 来源: tray 用户报告长 session 流式响应卡顿
- 当前: 没有压缩, 中断后只能重新发
- 候选: gzip 压缩, resumable streams, etc.
- 估算: 评估中

### 5.3 Model override 在 quickstart 流程里
- 来源: T-Q-S12-light 选了 model name 后, agent 不知道哪个 provider 配了那个 model
- 候选: `config.py` 加 model_to_provider 索引 (已有 `provider` 字段), 加速路由
- 估算: 半天

### 5.4 Chat completion streaming 里的 image 预算
- 来源: T-Q-S14 多图消息
- 当前: agent 算 image tokens, 但不告诉前端 "本轮 image 占 510 tokens"
- 已在 需求 3 覆盖

---

## 执行建议

按用户指示, **等 hermes-tray 现阶段开发告一段落** (T-Q-S12~S15 已完) 后, 按以下顺序一次执行:

| Phase | 任务 | 工作量 | 状态 |
|---|---|---|---|
| Phase 1 | S13-agent (STT 端点) | 2-3 天 | ✅ done 2026-07-02 (commit `016383af8`) |
| Phase 2 | S14-agent (Vision token + 路由 metadata) | 2-3 天 | ⏸ pending (等 hermes-tray T-Q-S14 真实集成验证) |
| Phase 3 | S12-agent (Cost-aware routing + metadata 推送) | 3-5 天 | ⏸ pending |
| Phase 4 | S15-agent (Plugin marketplace MVP) | 1-7 天 (看范围) | ⏸ pending (独立产品决策) |
| 5.x | 路由元数据可视化 / SSE 压缩 / model_to_provider 索引 | 0.5-1 天 | ⏸ pending (见 §5 各项) |

**Phase 1 ✅ 完成**. Phase 2 + 3 是 hermes-tray S12-S14 的**配套**, 必须做才能让 tray 的新功能完整工作. Phase 4 + 5.x 是独立产品决策. 续作须用户拍板 + 集成验证策略定 (v0.1.3 plan).**

---

## 触发: 重新评估

**当前: 1/5 项完成 (S13 done 2026-07-02).**

文件**不整体 archive**（按原 L207 预设 "执行完后 才搬"，但只完成 1/5 不算 "执行完"）。续作 (S14/S12/S15) 继续在本文件累计；后续如用户拍板 "全部停" 或 "全部完成"，再 archive 到 `docs/archive/NEEDS_BACKLOG_v017.md`.

新需求开新文件（按 L208 指引不变）。

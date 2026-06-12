# Hermes Agent 中文版 变更记录

本文档记录 Hermes Agent 中文版的更新历史。

---

## v0.15.0+cn.5 (2026-06-12) — 上游 8 周债大批 cherry-pick

> **8 周债一次性还清**：从 v0.14.0+cn.4（2026-04-17）以来 **259 个 upstream commit** cherry-pick 进来。
> 工具链：自研 cherry_pick v1-v7 脚本演进（7 个版本迭代）

### Cherry-pick 工具链演进

| 版本 | 关键能力 | 累计 commit |
|---|---|---|
| **v1** 试水 | 10 commit 试水（手工挑） | 6 |
| **v2** 自动化 | 巨型 refactor 过滤 + SED + 新文件自动 | 26 |
| **v3** 优化 | 依赖锁 AUTO-OURS + picklist 优先级 | 53 |
| **v4** SPLIT | 大文件按 hunks 拆分（cli.py / run_agent.py）| 74 |
| **v5** 单标 | test_voice_command.py 修复（EXCLUDE_THEIRS 首创）| 115 |
| **v6** 累积 | EXCLUDE_MANUAL 78 个 + 大写 EXCLUDE | 151 |
| **v7** bug 修 | 空 cherry-pick 自动 skip + timeout 30s | **259** |

### 关键修复

| 修复 | 受益 |
|---|---|
| **test_voice_command.py 接受上游** | 129+ 测试 FAIL 解决（v5 修复） |
| **cli.py 空 cherry-pick 自动 skip** | v7 修法 #1（状态错乱 bug）|
| **依赖锁 AUTO-OURS**（pyproject.toml/uv.lock/Cargo.toml 等）| CN 锁版本原则兑现 |
| **scripts/release.py AUTO-OURS** | 6+ 次冲突自动解决 |
| **大文件按 hunks 拆分** | cli.py/run_agent.py/hermes_state.py 单独留 manual |

### 主推平台保留（按 ROADMAP §三.5 决策）

- ✅ **feishu**（飞书）— 主推
- ✅ **weixin**（微信）— 主推
- 降权（保留但不主动维护）：wecom / yuanbao / dingtalk

### 跨项目验证

- ✅ **hermes-tray 集成测试 21/21 通过**（跨项目兼容性良好）
- ✅ **5 个国内平台 import OK**（feishu/weixin/wecom/yuanbao/dingtalk）
- ✅ **gateway.run / hermes_state / agent.conversation_loop** import OK
- ⚠️ 已知：Smoke 1.4 导入名不匹配（`run_conversation` 非 `conversation_loop`，非 break change）
- ⚠️ 已知：test_voice_command.py 部分新测试暂未运行（CN 不依赖 voice 模块）

### 跳过的内容

按 cn 分支"本地化 + 做减法"思想，**以下 upstream 改动被 SKIP**：
- **v0.16 主打 features**：
  - `apps/desktop/`（Electron 桌面，CN 主张另一条路）
  - Nous Portal（CN 不依赖 Nous 账号）
  - OAuth-gated gateway（CN 走飞书/钉钉/企微 OAuth）
  - Web admin panel（CN 主张 CLI + quickstart）
  - Multi-profile / multi-org（CN 是个人/小团队定位）
  - 完整 Simplified Chinese 翻译（@JimLiu PR #38241，跟 CN i18n 撞，v0.15.0+cn.6 处理）
- **T3 不活跃代码**：anthropic_adapter / bedrock_adapter / google_oauth 等（保留但不维护）
- **外国 Provider plugin**：openrouter / bedrock / gemini / google_chat / teams 等
- **已裁平台**：discord / telegram / whatsapp / signal / bluebubbles / matrix / mattermost / x_search 等

### 决策依据

- **scout 报告**：`MiniMax/projects/hermes-agent-cn-notes/UPSTREAM_CLASSIFICATION_REPORT.md`（556 SKIP / 1396 MERGE / 174 REVIEW）
- **ROADMAP**：`MiniMax/projects/hermes-agent-cn-notes/ROADMAP.md`（5 周计划 + 时间窗口）
- **PROJECT_NOTES**：`MiniMax/projects/hermes-agent-cn-notes/PROJECT_NOTES.md`（项目记忆 + 教训）
- **试水报告 v1-v7**：`hermes-agent-cn/.agent-teams/research/upstream-trial-v{1..7}-report.md`

### 合并计划 v4 (`merge-plan-v4.md`)

5 周计划 Week 1-5 详细任务拆解 + 任务包（T-V1/T-V2/T-V3），可下发给其他 agent。

### 已知问题（v0.15.0+cn.6 处理）

| 类别 | 数量 | 状态 |
|---|---|---|
| 手动冲突 EXCLUDE_MANUAL | ~200 个 | 延后到 v0.15.0+cn.6 |
| 大文件跳过 EXCLUDE_LARGE | ~30 个 | 延后（需人工看 diff）|
| i18n 升级 | n/a | 2026-06-12 重新评估：**#38241 (`4a1907bd1`) 只改 `apps/desktop/`，CN 不维护 desktop——改 PR 无收益，文档化为 EXCLUDE** |
| T3 修复（C3 2 commit）| 待启动 | Week 4 任务 |
| 减法 PR（T1 16 文件 + T4 22 目录）| 待启动 | Week 4 任务 |

---

## v0.15.0+cn.6 入口（2026-06-12 起） — 3 项 hard work

**工作分支**：`upstream-merge-cn6-2026-06`（从 `cn` @ `8ffd33a40` 切出，2026-06-12 16:53）

### 重新评估 i18n 升级（v0.15.0+cn.5 → v0.15.0+cn.6）

**结论**：#38241 (`4a1907bd1 feat(desktop): add i18n with Simplified Chinese (zh-Hans) support`) **不值得 cherry-pick**。

**理由**：
1. **PR 范围**：36 文件 / +4226 -1378 行，**只改 `apps/desktop/`**（上游 Electron 桌面 app）
2. **CN 减法 T3 = desktop 类**：CN 主张"另一条路"——不用 Electron 桌面，**pick 了不测试不部署不维护**
3. **0 价值**：v0.15.0+cn.5 已通过 `EXCLUDE_LARGE`（或 timeout/skip）跳过 #38241，**没破坏 CN 主线**——**显式 EXCLUDE 比静默跳过更安全**

**EXCLUDE 文档化位置**：
- `cherry_pick_v6+` 脚本 EXCLUDE_LARGE 列表（v7 已有 23 个，加 #38241 后 24 个）
- `AGENTS.md`（如必要）—— v0.15.0+cn.6 内部 commit 时补

**净影响**：v0.15.0+cn.6 backlog 从 4 项变为 3 项，**全部为真硬骨头**：
- **B** T3 修复（anthropic_adapter/bedrock_adapter 2 commit）— ~~按 scout 建议跳过，与 T3 路线冲突~~
- **C** 减法 PR（T1 16 文件 + T4 22 plugin 目录）— 进行中（见下）
- **D** ~200 manual 冲突（cli.py 663KB + run_agent.py 800+）— 高风险，~1 周

### C 减法 PR 进度（2026-06-12）

**第 1 刀 T1a 完成**：
- 删除 `agent/secret_sources/bitwarden.py`（1 文件，~130 行）
- 清理 `agent/secret_sources/__init__.py` 注释引用
- `tests/conftest.py` 加 `collect_ignore` 跳过 `test_bitwarden_secrets.py`
- `tests/test_env_loader_secret_sources.py` 给 1 个 bitwarden 端到端测试加 `@pytest.mark.skip`
- **测试基线不变**：3425 PASS / 120 FAIL / 80 SKIP（vs v0.15.0+cn.5）

**T1 剩余 12 文件 + T4 22 目录**——延后到 v0.15.0+cn.7+：
- T1b（8 个有 import 引用的文件）：需改 ~5-10 个 import 站点，工作量 1-2 hour
- T1c（4 个有平台枚举引用的文件）：需改 cron/scheduler.py 等平台列表
- T4（22 plugin 目录）：需检查 plugins 加载代码，~1 hour

**经验教训**：
- PLAN_CN.md 的 "零引用" 标签是基于文件名字符串的粗扫，**实际 grep 严格 import 才有 8 个文件有引用**
- 减法 PR 不是 `git rm` 就行——必须**先清理 import 站点**，否则测试必挂

### 升级指引

### 升级指引

```bash
# 用户从 v0.14.0+cn.4 升级到 v0.15.0+cn.5
cd ~/hermes-agent-cn
git fetch origin
git checkout cn
git pull
# v0.15.0+cn.5 是新分支 upstream-merge-v7-2026-06，需 review 后合并
git checkout upstream-merge-v7-2026-06
# 跑测试
pytest tests/ -v --timeout 30
# 看是否破坏核心功能
# 如果 OK，merge 到 cn：
git checkout cn
git merge upstream-merge-v7-2026-06
git push origin cn
```

---

## v0.15.0+cn.6 (2026-06-12) — 增量：i18n 重评 + T1a 减法

> **本版本增量** = 2 个 commit（`64a9fc0a4` docs + `7a02524df` chore）。
> v0.15.0+cn.5 (259 commit) 主体不变，本版本只做"判断 + 减法"。

### 新决策

#### 1. i18n 升级：EXCLUDE（不 pick PR #38241）

| 项 | 值 |
|---|---|
| PR | #38241 (`4a1907bd1 feat(desktop): add i18n with Simplified Chinese`) |
| 作者 | Jim Liu (宝玉) |
| 范围 | 36 文件 / +4226 -1378 行 |
| 影响范围 | **仅 `apps/desktop/`**（上游 Electron 桌面 app） |
| CN 价值 | **0**——CN 不维护 desktop（属于 T3 减法类别） |
| 决策 | **EXCLUDE**——v0.15.0+cn.5 期间已通过 EXCLUDE_LARGE / timeout 跳过，**显式文档化** |

**为什么显式 EXCLUDE 比静默跳过好**：
- 静默跳过后，未来 v8 重跑时还会再撞 #38241
- 显式 EXCLUDE → 加进 EXCLUDE_LARGE 列表 → 永久 skip

#### 2. T1a 减法：删除 bitwarden 集成

| 文件 | 改动 | 行数 |
|---|---|---|
| `agent/secret_sources/bitwarden.py` | **删除** | -130 |
| `agent/secret_sources/__init__.py` | 改 docstring | -2 / +4 |
| `tests/conftest.py` | 加 `collect_ignore` | +5 |
| `tests/test_env_loader_secret_sources.py` | 1 测试 skip | +1 |
| **净删除** | | **~125 行** |

**验证**：
- 内部 import 0 引用（仅 `__init__.py` docstring）
- 测试基线 3425/120/80 不变
- `agent.secret_sources` 模块仍可 import

### 跳过的 backlog

| 项 | 来源 | 状态 | 推到 |
|---|---|---|---|
| B T3 修复（anthropic/bedrock 2 commit） | C3 | scout 默认 SKIP + T3 路线冲突 | 永久 |
| C-2 T1b（8 个有 import 引用） | T1 | 需 5-10 个 import 站点改写 | v0.15.0+cn.7+ |
| C-3 T1c（4 个有平台枚举引用） | T1 | 需改 cron/scheduler.py 等 | v0.15.0+cn.7+ |
| C-4 T4（22 plugin 目录） | T4 | 需检查 plugins 加载代码 | v0.15.0+cn.8+ |
| D ~200 manual 冲突 | 摸底 | 方案见 `merge-plan-v5-D-manual-conflicts.md` | v0.15.0+cn.7（用户执行） |

### 关键 commit

| commit | 类型 | 标题 |
|---|---|---|
| `64a9fc0a4` | docs(cn) | re-evaluate i18n upgrade (PR #38241) for v0.15.0+cn.6 |
| `7a02524df` | chore(cn) | T1a jian-fa - remove bitwarden secret source |

### 升级指引

```bash
# 用户从 v0.15.0+cn.5 升级到 v0.15.0+cn.6
cd ~/hermes-agent-cn
git fetch origin
git checkout cn
git pull
# v0.15.0+cn.6 是 2 个 commit 增量
# 跑测试
pytest tests/gateway/ -q
# 期望 3425 PASS / 120 FAIL / 80 SKIP（与 v0.15.0+cn.5 一致）
```

---

## v0.14.0+cn.4 (2026-06-03) — SmartRouter Phase 5 + 多项增强

### SmartRouter Phase 5

| 功能 | 内容 | 提交 |
|------|------|------|
| **跨 Provider 路由** | `RoutingRule` 支持 `provider` 字段，规则可指定目标 provider | `bdabb2d` |
| **复杂度感知路由** | `complexity` 匹配条件（simple/medium/complex），`_match_rule` 自动判断 | `bdabb2d` |
| **Vision fallback** | `auxiliary.vision` 支持 `fallback_provider/model/base_url`，主 vision 失败时自动降级 | `bdabb2d` |

### 语义防火墙

| 里程碑 | 状态 | 提交 |
|--------|------|------|
| **M1** 规则热加载 | ✅ 惰性检测 config hash，自动重载规则 | `795004b` |
| **M2** 审计日志 + CLI | ✅ 拦截事件输出 JSONL，`hermes firewall {log\|status\|reload}` | `241568` |

### Quickstart 增强

| 修复项 | 提交 |
|--------|------|
| **云端/本地主力选择** — 同时有云端 API 和本地模型时让用户选择 | `4aa261d` |
| **云端视觉模型** — `auxiliary.vision` 优先检测云端 Provider 中的视觉模型 | `ba0159c` |
| **Fallback 读配置模型** — 不再用硬编码默认值，读取用户配置 | `ba0159c` |
| **model_routing 云端兼容** — 云端主力时不引用本地模型名 | `7a460d6` |
| **配置自动整理** — `_cleanup_config()` 清理空段/容器默认值 | `4aa261d` |
| **国产服务商 M1-M4** — 百度千帆/阿里百炼/火山引擎/网络诊断 | `fe85dbb` |

### Doctor 增强

| 检查项 | 内容 | 提交 |
|--------|------|------|
| **D6** 网络连通性 | 8 个国产 API 端点可达性检测 | `66d96d4` |
| **D7** 配置兼容性 | yaml 与 .env 冲突检测 | `66d96d4` |
| **D8** GPU/CUDA | GPU 驱动/CUDA Toolkit/PyTorch GPU 检测 | `66d96d4` |

### 浏览器工具 CN 网络兼容

`_check_chromium_download_available()` 检测 `storage.googleapis.com` 是否可达，被墙时跳过安装并提示改用 Lightpanda 引擎。提交 `6566490`。

---

## v0.14.0+cn.3 (2026-06-02) — toolsets.py 语法修复 + 版本更新

### Bug 修复

- **`toolsets.py` 残留片段导致 SyntaxError**：拉取上游更新后，`toolsets.py` 第 379-381 行残留了三个孤立的代码片段（`],` `"includes": []` `},`），不属于任何 toolset 定义，导致 `hermes --version` 等命令因 import 失败而报 `SyntaxError`。修复：删除残留的垃圾代码。

### 版本更新

- `hermes_cli/__init__.py`、`pyproject.toml` 版本号从 `0.14.0+cn.0` 更新至 `0.14.0+cn.3`，与 CHANGELOG 已有的 cn.1/cn.2 条目保持一致。

### 修改文件

| 文件 | 变更 |
|------|------|
| `toolsets.py` | 删除第 379-381 行残留片段 |
| `hermes_cli/__init__.py` | 版本号 `cn.0` → `cn.3` |
| `pyproject.toml` | 版本号 `cn.0` → `cn.3` |

---

## v0.14.0+cn.2 (2026-05-29) — 双路由统一 + openrouter_min_coding_score 修复

### Bug 修复

- **`AIAgent.__init__()` 缺少 `openrouter_min_coding_score` 参数**：`tools/delegate_tool.py` 创建子 Agent 时传入 `openrouter_min_coding_score`，但构造函数未接收该参数导致 `TypeError`。修复：添加参数并赋值。

### 双路由统一：SmartRouter 接管 model_routing

**问题**：`run_agent.py` 中 `_apply_model_routing()` 与 `agent/zhineng_luyou.py` 的 `SmartRouter.route()` 各自独立实现路由逻辑，导致规则解析、关键词匹配、兜底策略三套代码并行维护，难以测试和演进。

**方案**：将 `RoutingRule` 数据类、`_match_rule()` 静态方法、`route_with_rules()` 统一方法全部归入 `SmartRouter`，`run_agent.py` 的 `_apply_model_routing()` 简化为调用 `SmartRouter.route_with_rules()` 的薄封装。

#### 核心变更

| 变更 | 之前 | 之后 |
|------|------|------|
| 路由入口 | 3 个方法：`_match_rule()` + `_apply_model_routing()` + `SmartRouter.route()` | 1 个方法：`SmartRouter.route_with_rules()` |
| 代码分布 | `run_agent.py` ~270 行 + `zhineng_luyou.py` 各自独立 | `zhineng_luyou.py` ~220 行统一管理 |
| 规则格式 | 两套规则解析逻辑 | 统一 `route_with_rules()` 按序处理：rules → legacy → capability-aware fallback |
| 关键字检测 | `run_agent.py` 硬编码 6 个关键字列表 | `RoutingRule.match.keywords` 配置化 |
| 跨规则切换 | 旧格式到 SmartRouter 需手动 `setattr` | `route_with_rules()` 一步切换，自动处理 provider 安全切换 |

#### 修改文件

| 文件 | 变更 |
|------|------|
| `agent/zhineng_luyou.py` | +`RoutingRule` 数据类 (from_dict)、+`_match_rule()` 静态方法、+`route_with_rules()` 方法 (183 行新增) |
| `run_agent.py` | +`openrouter_min_coding_score` 参数；`_apply_model_routing()` 重构为 SmartRouter 调用 (~270→~165 行)；移除 `_match_rule()` 方法 |

#### 向后兼容

- 无 `model_routing.rules` 时：自动回退 legacy 格式（`vision/reasoning/default` 键），行为不变
- 无任何 `model_routing` 配置时：回退 `SmartRouter.route()` 能力感知路由
- 所有旧配置无需修改

#### Commit
```
04c2d7a67 fix(cn): unify model_routing into SmartRouter; fix openrouter_min_coding_score TypeError
2 files changed, 222 insertions(+), 168 deletions(-)
```

---

## v0.14.0+cn.1 (2026-05-27) — SmartRouter v2 + 运行时集成

### SmartRouter v2 重构 (`agent/zhineng_luyou.py`, ~850 行)

v1 三层路由 (Ollama/Cloud/Embedded) 完全重写为多后端能力感知架构：

- **BackendHub** — 统一管理本地推理服务 (Ollama / LM Studio / llama.cpp / FastLLM / vLLM / LocalAI / 自定义)，每个后端独立健康检测 + 熔断
- **HealthTracker** — 后端可用性追踪，失败 → 降温 → 熔断 → 恢复四阶段
- **能力感知路由** — 从用户消息提取能力需求 (vision/tools/context_length)，匹配最佳模型
- **路由此志** — `~/.hermes/logs/luyou_routes.jsonl` 记录每次路由决策
- **5 个内置后端** + **交互式自定义后端添加**

#### `hermes route-status` 增强

- `--verbose` / `-v`: 显示详细模型元信息（参数量/上下文/工具支持/Ollama 原始数据）
- `--json` / `-j`: JSON 格式输出（可配合 jq 使用）

#### quickstart 多后端检测

- 新增 FastLLM (port 8088)、vLLM (port 8000)、LocalAI (port 8082) 自动探测
- `_write_local_backends()`: 将检测到的后端写入 `config.yaml` 的 `local_backends` 段
- 自定义后端模板: 无需修改代码，直接在 config.yaml 添加 `local_backends` 条目即可

### Phase F: SmartRouter v2 运行时集成

将 SmartRouter v2 作为兜底路由集成到 `_apply_model_routing()`：

- **路由守卫** — 仅当无显式 `model_routing.rules` 匹配时激活
- **Provider 安全切换** — 切换前调用 `resolve_provider_client()` 验证 auth；auth 不可用时保留现有 provider
- **同 provider 模型更新** — 同一提供商内直接切换 model
- **SmartRouter 缓存** — 类级懒加载，按 config hash 失效（冷 1.8ms → 热 ~0ms）
- **异常兜底** — SmartRouter 不可用时保留现有 model，不阻塞主流程

### Bug 修复

- **`resolve_provider_client` 参数名**: `api_key` → `explicit_api_key`
- **`fallback_model` 类型兼容**: 兼容 `str` / `list[str]` / `list[dict]` 三种格式

### 修改文件

| 文件 | 变更 |
|------|------|
| `agent/zhineng_luyou.py` | 完整重写 SmartRouter v2 (~850行) |
| `run_agent.py` | Phase F 集成 (+70行): guard + cache + provider 安全切换 |
| `hermes_cli/main.py` | `route-status --verbose/--json` |
| `hermes_cli/quickstart.py` | 多后端检测 + local_backends 配置写入 |

---

## v0.14.0+cn.0 (2026-05-23) — upstream v0.14.0 合并

### 合并概要

- **upstream**: `github.com:NousResearch/hermes-agent` main → cn 分支
- **合并规模**: 1,398 commits
- **版本跳跃**: v0.12.0 → v0.14.0
- **Commit**: `dd97a5e9c`

### 合并处理

- **20 个冲突文件**按梯队处理：配置文件保留 CN 分支、UI 文本合并双方、基础设施文件遵循 upstream 重构
- **配置迁移**: v16 → v23 schema 升级（删除重复 `fallback_providers`）
- **CN 分支保留项**: 中文 UI 本地化、Ollama 上下文窗口 8192 bug 修复 (commit `22e3decf8`)

### upstream v0.14.0 主要变更

- Agent 核心: tool gateway 重构、auxiliary client 路由器、多 provider 适配
- 安全增强: 控制平面文件保护 (#27784)、webhook HMAC bypass 修复 (#8306)
- Anthropic adapter 重构: `convert_messages_to_anthropic` 拆分为 7 个辅助函数
- FAL 图像生成后端迁移到插件系统
- TUI 界面升级 (React-based)

---

### 根因更深层修复

- **runtime_provider.py**: 在 OpenRouter fallback 前增加 `provider=="custom"` 处理，读取 `model.base_url`，返回 `api_key="no-key-required"`
- **cli.py**: 保留 `elif resolved_provider=="custom"` 安全网
- **UTF-8 BOM 清理**: 修复所有修改文件的 BOM


### Bug 修复

- **quickstart.py 语法错误**: 提取 `cname` 变量避免 f-string 嵌套括号 (`#946-948`)
- **hermes chat 空 API key 报错**: 对 `resolved_provider=="custom"` 特殊处理，从 config 补读 `base_url` (`cli.py:3774-3787`)


### Ollama 模型三层分类 + 参数规模感知选型（阶段 0）

#### ✅ 三层分类

| 层级 | 方法 | 说明 |
|------|------|------|
| L1 | 名称关键词匹配（已有） | `vl`, `vision`, `llava`, `cogvlm`, `minicpm-v` |
| L2 | 已知视觉家族检测（新增） | `qwen3`, `qwen3.5`, `yi-vl`, `internvl2` 等，零 API 调用 |
| L3 | `/api/show` 模板探查（新增） | 检查 chat template 是否包含 `image_url`/`vision` 标记 |

- `_VISION_FAMILIES`: 已知视觉家族列表
- `_VISION_FAMILY_EXCLUSIONS`: 编码专用模型排除
- `_check_vision_template()`: L3 探查函数

#### ✅ 参数规模感知选型

- `_get_ollama_model_info()`: /api/show 查询，内存缓存
- `_get_param_size()`: 解析 parameter_size，支持 tag 后缀回退
- 选型逻辑：同类型取参数规模最大

### model_routing 规则驱动路由框架（阶段 1-3）

#### ✅ 阶段 1: 自定义路由框架

- `_match_rule()`: has_image / keywords(+threshold) / max_length / exclude_keywords
- `_apply_model_routing()`: 改为规则遍历，支持 rules 列表 + 旧格式兼容

#### ✅ 阶段 2: coding 路由

- quickstart 自动检测 coder 模型，注入 coding 规则

#### ✅ 阶段 3: short_chat 路由

- quickstart 自动检测 ≤8B 模型，注入 short_chat 规则

#### ✅ 向后兼容

- 旧格式（`vision`/`reasoning`/`default`）无需修改
- `rules` 格式优先，无 `rules` 时回退旧格式

### 用户测试反馈修复

#### ✅ quickstart 模型分类修正
- `_VISION_FAMILY_EXCLUSIONS` 加 `-deepseek`：qwen3.5-9b-deepseek 是 DeepSeek 蒸馏推理模型，非视觉
- `_classify_ollama_model()` 新增 `coding` 类型检测
- `_pick_ollama_primary()` 主力选择排除 coding 类型
- `_write_smart_routing()` 写入 rules 时清除旧格式键（避免新旧共存）

#### ✅ fallback 链 + 规则刷新
- `_build_fallback_chain()` 排除 coding 模型进入通用回退链
- `_write_smart_routing()` 删除「已有 rules 就跳过」逻辑，每次 quickstart 都重新生成

#### Commit
```
d3717ad0d fix(cn): quickstart 模型分类修复（4项）
fe2a9d92f fix(cn): fallback链排除coding + rules始终重新生成
```

---

## v0.12.0-cn.11 (2026-05-16)

### quickstart Ollama base_url 恢复

- **Bug**: quickstart 检测 Ollama + DeepSeek 后，`_update_config_for_provider` 把 `model.base_url` 覆写成了 DeepSeek 的 URL。`_write_smart_routing` 恢复 `model.provider=ollama` 后没有恢复 `base_url`，导致后续 `resolve_runtime_provider` 读取到错误 URL
- **修复**: `_write_smart_routing()` 在设置 `model.provider=ollama` 后检查 `base_url`，若被云 Provider 覆写则恢复为 `http://localhost:11434/v1`。commit `fd1dfb13a`

---

## v0.12.0-cn.10 (2026-05-16)

### fallback 后 model_routing 深度修复 — disable_model_routing 参数

- **Bug**: v0.12.0-cn.9 的 `_fallback_activated` guard 只在运行时 fallback 生效。CLI 初始化时 fallback 到 deepseek 后新建 Agent，`_fallback_activated` 为 False，`_apply_model_routing()` 仍会把 `self.model` 覆盖为 Ollama 模型名
- **修复**: 新增 `disable_model_routing` 参数到 `AIAgent` 构造函数。CLI fallback 后设 `self._fallback_applied = True`，传给 Agent 的 `disable_model_routing`。`_apply_model_routing()` 双重 guard：`_disable_model_routing` 或 `_fallback_activated` 为 True 时跳过。commit `8a9f51913`

---

## v0.12.0-cn.9 (2026-05-16)

### fallback 激活后 model_routing 覆盖模型名修复

- **Bug**: cli fallback 到 deepseek 后，`_apply_model_routing()` 仍用 `model_routing` 里的 Ollama 模型名覆盖 `self.model`，导致 DeepSeek API 收到 `qwen3.5-9b-deepseek:q4` 报 400
- **修复**: `_apply_model_routing()` 检测 `_fallback_activated`，fallback 激活时跳过路由，保留 fallback provider 的模型名。commit `bae3e9f54`

---

## v0.12.0-cn.8 (2026-05-16)

### Ollama 上下文窗口检测修复

- **Bug**: Ollama 模型 `num_ctx=262144` 被误检为 8,192，低于 MINIMUM_CONTEXT_LENGTH(64,000)，导致 agent 初始化失败
- **根因**: `get_model_context_length()` 中 `is_local_endpoint()` 检查嵌套在 `_is_custom_endpoint() && !_is_known_provider_base_url()` 条件内，当 Ollama 的 `localhost:11434` 被识别为已知 provider 时，整个本地查询块被跳过
- **修复**: 将本地端点查询提升为独立 Step 2，优先于自定义端点检测（Step 3）。commit `22e3decf8`

---

## v0.12.0-cn.7 (2026-05-15)

### runtime_provider custom provider 空 API key 修复

- **Bug**: `hermes chat` 使用 ollama→custom 映射时报 "Provider resolver returned an empty API key"
- **根因**: `resolve_runtime_provider()` 对 `provider="custom"` 无处理分支，落入 OpenRouter fallback 要求 API key
- **修复**: 在 `_resolve_openrouter_runtime()` 前插入 custom provider 处理块，从 `config.yaml` 读取 `model.base_url`，返回 `api_key="no-key-required"`。commit `aa0ee72fb`

### quickstart 语法错误修复

- **Bug**: `quickstart.py:948` f-string 嵌套 `['name']` 导致 SyntaxError
- **修复**: 提取变量再打印。commit `aa0ee72fb`

### UTF-8 BOM 清理

- 修复所有修改文件（cli.py, quickstart.py, runtime_provider.py）的 BOM 头

- 提交: `aa0ee72fb`, `f00382409` (CHANGELOG)

---

## v0.12.0-cn.5 (2026-05-14)

### MemPalace + graphify 知识库集成

#### ✅ MemPalace 结构化记忆
- 提交 `mempalace.yaml` 宫殿配置（29 rooms, 1714 drawers）
- Wing→Room→Hall→Drawer 四层结构，96.6% LongMemEval 召回
- 零 API 调用，纯本地运行
- `.gitignore` 忽略 `graphify-out/`, `entities.json` 等生成文件
- AGENTS.md 新增 MemPalace/graphify 使用指南

MCP 集成（quickstart 自动配置，无需手动编辑）：
```yaml
# ~/.hermes/config.yaml
mcp_servers:
  mempalace:
    command: python  # 使用虚拟环境路径
    args: [-m, mempalace.mcp_server]
```

#### ✅ graphify 代码知识图谱
- AST 提取代码结构（Phase 1，纯本地，无需 API）
- 36,384 nodes, 115,166 edges, 421 communities
- 71.5x token 节省（vs 读原文件）
- 概念提取层（Phase 3）暂不启用（需 Claude API，与 CN 分支本地化定位冲突）

### Phase 2 收尾 + D5 路由可视化

#### ✅ quickstart 自动生成 model_routing 配置

`_write_smart_routing()` 新增自动检测逻辑：
- 当 Ollama 有 ≥2 个模型，且有视觉模型 + 文本模型时
- 自动写入 `model_routing` 配置段（default/vision/reasoning）
- 已有自定义配置时不会覆盖（`not in routing` 检查）

#### ✅ `hermes route-status` CLI 命令

新增子命令，调用 `SmartRouter().print_status()` 显示：
- 路由模式（auto）
- Ollama 在线状态
- 云端 API 配置状态
- 嵌入式模型就绪状态

#### ✅ Doctor 路由配置检查段

### Quickstart MemPalace MCP 自动配置

#### ✅ `_detect_mempalace()`
- 三级检测：pip 包可用 → 宫殿已初始化 → MCP 已配置
- 返回 None 或 details dict

#### ✅ `_configure_mempalace_mcp()`
- 自动写入 `~/.hermes/config.yaml` 的 `mcp_servers.mempalace`
- 使用 `sys.executable` 作为 Python 路径
- 已配置时自动跳过（不覆盖）

#### ✅ 主流程集成
- Step 1 资源扫描：显示 MemPalace 状态（已初始化/待配置）
- Step 3 后：自动配置 MCP（如果有 MemPalace 但未配置）
- 结果摘要：显示知识库就绪状态

#### ✅ 使用文档更新
- `docs/Hermes集成指南_MemPalace与graphify.md` 新增「最大化使用指南（CN 分支）」
- 决策日志模式 vs 代码 mine 模式对比
- graphify 重构前专用策略
- 数据维护节奏表
- 与 MEMORY.md 互补关系说明

### 语义防火墙 — 防护「间接提示词注入」"持久化记忆投毒"

#### 攻击模型
攻击者在网页、文档、代码仓库中埋入隐形指令，当用户让 Hermes 处理这些内容时：
1. Hermes 读取并执行恶意指令（如转发密钥）
2. Hermes 将恶意逻辑写入 SKILL.md
3. 技能在后续所有会话中持续生效 → 持久化投毒

#### ✅ 5 层纵深防御 (`agent/semantic_firewall.py`, ~520 行)

| 层 | 名称 | 机制 | 默认 |
|----|------|------|------|
| L1 | 内容净化门 | 剥离注入标记后进入 prompt | ✅ |
| L2 | 技能溯源追踪 | 每个 SKILL.md 记录来源链路 | ✅ |
| L3 | 写入前验证门 | LLM 语义分析 + 正则双重拦截 | ✅ |
| L4 | 隔离区 + 人工审核 | 可疑技能隔离，永不自激活 | ✅ |
| L5 | 审计日志 | 全链路可追溯 | ✅ |

**正则检测覆盖 13 类危险模式：**
凭证外泄、数据外泄、信标行为、文件系统滥用、代码执行、横向移动、硬编码密钥、木马标识、安全绕过、角色扮演注入、系统提示覆盖、内存操作、技能名注入

**LLM 语义分析 6 维度：**
数据外泄 / 持久化操作 / 能力升级 / 指令覆盖 / 隐蔽信道 / 用户意图一致性

#### ✅ 集成到 skill_manager_tool

`skill_manage(create)` 和 `skill_manage(edit)` 在写入 SKILL.md **之前**通过防火墙验证门：
- 拦截时：技能放入隔离区（`.quarantine/`），用户可用 `hermes firewall review` 审核
- 通过 `skills.firewall.enabled` 配置开关（默认启用）
- 清理残留：拦截时删除已创建的空目录

#### ✅ 与 skills_guard.py 的关键区别

| | skills_guard.py | semantic_firewall.py |
|---|---|---|
| 时机 | 写入**后**扫描，失败则回滚 | 写入**前**拦截 |
| 范围 | 外部 hub 安装的技能 | agent 创建/修改的所有技能 |
| 方法 | 正则 + 信任级别 (builtin/trusted/community) | 正则 + LLM 语义分析 |
| 来源感知 | community/hub 源 | ingested/user/curator 来源 |
| 默认状态 | 外部技能默认开启 | **全部**技能都过（可关闭） |
| LLM 分析 | ❌ | ✅ 核心防御层 |

#### ✅ 关键安全属性

- **Fail-closed 设计**：LLM 不可用时默认拒绝（不信任）
- **来源敏感置信度**：ingested 来源需要 ≥0.85 置信度，其他只需 ≥0.80
- **写入前拦截**：写入磁盘前验证，不是写入后扫描再回滚
- **隔离不删除**：可疑技能进入隔离区，不自动激活，留待人工审核

#### ✅ 文件清单

| 文件 | 类型 | 行数 |
|------|------|------|
| `agent/semantic_firewall.py` | 新建 | ~520 |
| `tools/skill_manager_tool.py` | 修改 | +108 |

#### Commit
```
d57f5be5b feat(cn): 语义防火墙 — 防护间接提示词注入和持久化记忆投毒
aec4ff134 docs: CHANGELOG_CN.md — 语义防火墙条目
2 files changed, 1114 insertions(+)
```

---

## v0.12.0-cn.4 (2026-05-13)

### feat: Phase 2 — model_routing 配置 + 消息级模型选择

实现 `PROPOSAL-multi-model-routing.md` 方案 A：

#### ✅ `agent/zhineng_luyou.py` 修复
- `check_cloud()` 和 `_select_cloud_model()` 改用 `get_env_value()` 检测 API Key
- 确保读取 `~/.hermes/.env` 文件（同 Bug #3 修复）

#### ✅ `run_agent.py` 新增运行时路由
- 新增 `_apply_model_routing()` 方法
  - 从 `config.yaml` 读取 `model_routing` 配置段
  - 按优先级检测消息内容自动选择模型：
    1. 图片附件（multimodal content）→ `model_routing.vision`
    2. 视觉关键词（看图、截图）→ `model_routing.vision`
    3. 推理关键词（分析、推理）→ `model_routing.reasoning`
    4. 默认 → `model_routing.default`
  - 每 turn 只执行一次（`_routing_applied` 标志）
- 在 `_build_api_kwargs()` 开头调用，所有 API 模式自动生效
- `run_conversation()` 入口重置标志（支持 CLI 模式复用 agent 实例）

#### 配置示例

```yaml
model_routing:
  default:
    model: "qwen3:32b"
  vision:
    model: "qwen3-vl:8b"
  reasoning:
    model: "qwen3:32b"
```

#### Commit
```
630751c2c feat: Phase 2 — model_routing 配置 + 消息级模型选择
2 files changed, 107 insertions(+), 5 deletions(-)
```

---

## v0.12.0-cn.3 (2026-05-13)

### 🩺 Doctor 诊断增强（D3: 外部模型服务检查）

在 `hermes doctor` 中新增"外部模型服务"检查段（位于"本地模型"与"配置文件"之间），包含三项检测：

#### ✅ D3.1: Ollama 运行状态检测
- 调用 `GET http://localhost:11434/api/tags` 检测 Ollama 服务
- 成功时显示运行中的模型列表（前 5 个）
- 失败时区分"未运行"和"响应异常"两种状态

#### ✅ D3.2: Fallback 链一致性检查
- 从 config.yaml 读取 `fallback_providers` / `fallback_model` 配置
- 检测空 Fallback 链，提示"未配置回退模型"
- 逐条检测每个条目的 provider/model 缺失

#### ✅ D3.3: 主力-Fallback 重复检测
- 检测主力模型是否同时出现在 Fallback 链中
- 额外检测：`fallback_model` 和 `fallback_providers` 键同时存在的不一致状态
- 显示 auxiliary.vision 视觉模型配置状态

#### 🔧 D4: 静默模式 + 全局检测统计

在 `hermes doctor` 中新增两项输出优化：

- **静默模式**: `hermes doctor --quiet` 只显示 ⚠ 和 ✗ 项目，✓ 通过项和 → 信息项全部隐藏
- **检测统计**: Summary 末尾显示 `检测项: N ✓  N ⚠  N ✗`，方便快速了解整体健康度
- 实现方式：`_quiet_mode` 全局标志 + 全局计数器 `_total_ok/warn/fail`
- P3 项（D4.3 三级颜色分级 / D4.4 JSON 输出）暂未实施

#### 🔧 D2: Python 环境类型检测（Conda/Pyenv/venv/系统）

在 `◆ Python 环境` 检查段中，将原来简单的虚拟环境判断扩展为四级环境检测：

- **Conda**: 检测 `CONDA_DEFAULT_ENV` / `CONDA_PREFIX`，显示 conda 环境名
- **Pyenv**: 检测 `PYENV_SHELL` / `PYENV_VERSION`，显示 Pyenv 管理状态
- **venv**: 原有 `sys.prefix != sys.base_prefix` 逻辑
- **系统 Python** ⚠️: 以上皆非时警告用户创建虚拟环境
- 所有情况均显示 `sys.executable` 解释器完整路径

#### 🔧 D1: .env 文件内容智能检测

在 `◆ 配置文件` 检查段中，新增 `.env` 文件内容深度检测（`_check_env_content()`）：

- **空值检测**: 检测 `KEY=` 形式的空值，提示填入有效值
- **格式检测**: 检测 `export KEY=VALUE`（不需要 export 前缀）和 `KEY = VALUE`（等号两侧不应有空格）
- **注释干扰**: 检测 `# KEY=xxx` 被注释的 Key，提示取消注释
- **重复 key**: 检测同一 KEY 被多次定义，提示 dotenv 行为是后者覆盖前者
- 无问题时显示 `✓ .env 内容检测通过`

| 文件 | 修改内容 |
|------|----------|
| `hermes_cli/doctor.py` | 新增 `_check_env_content()` 函数（62 行）+ 重构 Python 环境检测段 |
| `hermes_cli/doctor.py` | 新增 `--quiet` 模式 + 全局检测统计（✓/⚠/✗ 计数）|
| `hermes_cli/main.py` | doctor 子命令新增 `--quiet` 参数 |

### 🐛 修复 Provider 配置和 API 密钥检测

本次更新修复了 CN 分支的 3 个关键 Bug（感谢守一测试反馈）。

#### **Bug #1**: `hermes setup` 后不生成 `~/.hermes/.env` 文件

- **现象**: 配置 DeepSeek API Key 后，目录中找不到 `.env` 文件
- **原因**: `_configure_provider()` 未正确写入文件（已在 v0.12.0-cn.1 修复）
- **状态**: ✅ 已修复

#### **Bug #2**: Provider 列表问题

**2.1 国外模型提供商过多**
- **修复**: `models.py` 添加 `_cn_skip_providers` 过滤列表
- **过滤规则**: CN 分支不显示 `minimax` (国际版)，只显示 `minimax-cn` (国内版)
- **影响**: Provider 选择界面更简洁，只显示国内用户常用提供商

**2.2 缺少硅基流动 (SiliconFlow)**
- **新增**: `models.py` 添加 `siliconflow` 到 `CANONICAL_PROVIDERS`
- **模型列表**: 添加 14 个常用模型（Qwen/GLM/Yi/DeepSeek 等）
- **配置**: `auth.py` 添加 `PROVIDER_REGISTRY` 条目，支持 API Key 自动检测

**2.3 DeepSeek V4 接口变化**
- **参考**: https://api-docs.deepseek.com/zh-cn/
- **更新**: `models.py` 更新 DeepSeek 模型列表
  - 添加: `deepseek-v3`, `deepseek-r1-0528`, `deepseek-r1-distill-*` 系列
  - 保留: `deepseek-chat`, `deepseek-reasoner` (兼容旧配置)
- **注意**: `deepseek-chat` 接口未下架，但建议升级到 V3/R1

#### **Bug #3**: `hermes chat` 失败（empty API key）

- **现象**: 配置 DeepSeek Key 后，`hermes chat` 报错：`Provider resolver returned an empty API key`
- **根因**: `auth.py` 的 `resolve_provider()` 使用 `os.getenv()` 检测 API Key
  - `os.getenv()` 只检查 Shell 环境变量
  - 不读取 `~/.hermes/.env` 文件
  - 导致通过 `hermes setup` 保存的 Key 无法被检测
- **修复**: 改用 `get_env_value()` (来自 `hermes_cli.config`)
  - 优先检查 Shell 环境变量
  - 回退到 `~/.hermes/.env` 文件
  - 确保所有保存的 API Key 都能被正确检测

#### 📝 测试文档更新

- **新增**: `tests/TEST_REPORT_TEMPLATE.md` (测试报告模板)
  - 不包含实际测试结果
  - 包含占位符和截图位置标记
  - 方便后续测试时填写
- **更新**: `.gitignore` 添加 `tests/image/` (测试截图不提交)
- **注意**: `TEST_REPORT.md` 包含实际测试结果，不提交到仓库

#### 🔧 修改文件列表

| 文件 | 修改内容 |
|------|----------|
| `hermes_cli/models.py` | 添加 siliconflow、过滤 minimax、更新 DeepSeek 模型列表 |
| `hermes_cli/auth.py` | 修复 `resolve_provider()` API Key 检测逻辑 |
| `tests/TEST_REPORT_TEMPLATE.md` | 新增测试报告模板 |
| `.gitignore` | 忽略 `tests/image/` |

#### 🧪 验证方式

1. **Bug #1 验证**:
   ```bash
   hermes setup
   # 选择 DeepSeek，输入 API Key
   cat ~/.hermes/.env  # 应该能看到配置的 Key
   ```

2. **Bug #2 验证**:
   ```bash
   hermes chat
   # 进入后按 /model，查看 Provider 列表
   # 应该能看到 siliconflow，不应该看到 minimax (国际版)
   ```

3. **Bug #3 验证**:
   ```bash
   hermes chat
   # 发送消息，不应该再报 "empty API key" 错误
   ```

---

## v0.12.0-cn.2 (2026-05-06)

### 🪜 Skill 三层管理 + 自动调度（面向上游 PR）

重构了 CN 版的两个核心模块，准备推给 Hermes 官方上游：

#### 🆕 SkillTierManager（`agent/skill_tier_manager.py`）
- 三层分层：Builtin（始终注入）/ Frequent（自动匹配）/ Archived（按需唤醒）
- 自动升降级：7 天内使用 ≥3 次 → 晋升；连续 7 天未用 → 降级
- 统计报告：活跃/归档分布 + Token 节省百分比估算
- 支持 Pin 保护、手动升降级、批量评估
- **适配上游**：移除硬编码 CN Skill 列表，改为构造注入 + 配置驱动

#### 🆕 SkillMatcher（`agent/skill_matcher.py`，原 `jineng_diaodu.py`）
- 三种匹配策略：关键词精确匹配、文件扩展名上下文匹配、Description Jaccard 模糊匹配
- 共现矩阵追踪 Skill 关联使用
- 松耦合设计：通过 `tier_data` 参数接收 Tier 信息，不直接依赖 SkillTierManager
- **适配上游**：英文命名/注释/日志，16 种文件扩展名映射

#### 🔗 系统集成
- `prompt_builder.py`：`build_skills_system_prompt()` 分层注入，Archived Skill 仅列名称
- `run_agent.py`：每 20 次工具调用触发一次 `evaluate_promotions()`
- `hermes skills tier {status|pin|unpin|evaluate}` CLI 子命令
- 配置开关：`skills.tier_management.enabled`

#### 🧹 清理
- 删除 `agent/jineng_diaodu.py`（已替换为 `skill_matcher.py`）

---

## v0.12.0-cn.1 (2026-05-03)

### 🔄 上游合并：NousResearch v0.12.0+

合并上游 972 个新 commit，涵盖多个重大改进。

#### ✨ 关键上游变更

| 类别 | 内容 |
|------|------|
| **新功能** | 飞书评论智能回复（三阶权限管控）、Kanban 面板、Hub 一键技能安装 |
| **新工具** | 图像路由、LM Studio 推理、Tool Guardrails |
| **平台修复** | Discord 僵尸 WebSocket 修复、Telegram 轮询心跳保活、WhatsApp 泄漏修复 |
| **配置改进** | config.yaml 优先于 .env（agent/display/timezone）、凭证池 .env 回退 |
| **新文件** | `agent/curator.py`、`agent/tool_guardrails.py`、`agent/image_routing.py` 等 |
| **版本** | `RELEASE_v0.12.0.md` 新增 |

#### 🇨🇳 中文版维护（本次无变更）

- ✅ Provider 清单不受影响（5+1 国产 Provider 保持不变）
- ✅ 全部汉化文件在上游合并中保留（冲突已解决）
- ✅ 汉化验证 4/4 通过

#### 🚀 新增：本地模型一键安装

- **`hermes local-models install all`** —— 支持 `all` 关键字批量安装全部模型
- **`hermes local-models setup`** —— 一键安装命令（自动装依赖 + 全部内置/推荐模型）
  - 支持 `--yes` / `-y` 跳过确认，适合脚本化调用
  - 自动安装运行时依赖：modelscope, llama-cpp-python, faster-whisper, onnxruntime, edge-tts
  - 自动下载：Whisper-small(464MB) + Edge-TTS(10MB) + Qwen2.5-0.5B(469MB) + MOSS-TTS-Nano(641MB)
- **修复 `hermes_cli/embedded.py`** —— API 不匹配 bug
  - `_resolve_model()` 修复 `get_available_embedded_model()` 返回 str 却被当 dict 调用的 bug
  - `list_models()` 修复 `MODEL_REGISTRY`(list) 被当 dict 调 `.items()` 的 bug
- **测试补充** —— 添加 4 个新测试用例（模型注册表、setup 函数、embedded provider）
- **Skill 升级** —— `model-download` SKILL.md 升级到 v1.1.0，新增"一键安装"触发词和流程

#### ⚡ 新增：Quickstart 快速配置 + 零配置首次启动

- **`hermes quickstart`** —— 新命令，一键自动配置
  - 扫描环境变量中的国产 API Key（DeepSeek/智谱/Kimi/MiniMax/阿里云）
  - 检测本地 Ollama 服务
  - 检测/安装本地离线模型
  - 免交互，检测到什么用什么，零选择体验
- **首次启动优化** —— 零 Provider 时弹出中文引导菜单
  - 选项 1：安装本地离线模型（自动，无需账号）
  - 选项 2：配置 API Key（传统 setup 向导）
  - 选项 3：退出（显示可用命令提示）
- **新模块** —— `hermes_cli/quickstart.py`（~300 行）
- **测试补充** —— 添加 4 个 quickstart 测试用例
- **文档同步** —— README_CN.md 新增"快速开始"章节，更新本地模型命令

#### 🌐 系统提示词中文指令 + 界面汉化补充

- **系统提示词** —— `DEFAULT_AGENT_IDENTITY` 添加「Always reply in Chinese」指令
  → 所有 LLM 生成的回复（分析/建议/总结）将自动使用中文
- **TUI/Web 加载消息** —— 「⚡ loading skill:」→「⚡ 加载技能:」
- **`/model` 命令** —— 无可用 Provider 时显示当前模型信息，而非空报错
  - 汉化错误消息：「No authenticated providers found」→「未检测到其他已认证的 Provider」
  - 新增当前模型/Provider 显示，退出提示改为中文 + 终端切换指引

#### 🧩 Quickstart 增强

- **添加硅基流动 SiliconFlow 支持** —— `SILICONFLOW_API_KEY` 自动检测，默认模型 `Qwen/Qwen2.5-7B-Instruct`
- **修复 API Key 持久化** —— `_configure_provider()` 将 Key 写入 `~/.hermes/.env`，确保 Hermes 运行时子进程也能找到

#### 冲突解决策略

| 文件 | 策略 | 说明 |
|------|------|------|
| `hermes_cli/providers.py` | 保留 cn 版本 | Provider 精简不受影响 |
| `hermes_cli/doctor.py` | 保留 cn 版本 | 汉化保留 |
| `hermes_cli/setup.py` | 保留 cn 版本 | 汉化保留 |
| `hermes_cli/commands.py` | 保留 cn 版本 | 汉化保留 |
| `hermes_cli/models.py` | 保留 cn 版本 | 汉化保留 |
| `hermes_cli/banner.py` | 保留 cn 版本 | 汉化保留 |
| `hermes_cli/auth.py` | 保留 cn 版本 | Provider 精简保留 |
| `.gitignore` | 采用上游版本 | 未修改 |
| `agent/onboarding.py` | 采用上游版本 | 未修改 |

---

## v0.11.0-cn.1 (2026-05-03)

### 🎯 Phase 7 全面汉化完成

基于上游 v0.11.0 的第二个中文版更新，完成 Phase 7 全部汉化工作。

#### 新增功能

- **Provider 精简** —— 只保留 5+1 个国产 Provider：
  - deepseek（深度求索）
  - minimax（ MiniMax）
  - kimi（月之暗面）
  - zai（智谱 AI）
  - ollama（本地模型）
  - + Nous Portal（可选）

#### 汉化内容

- **hermes_cli/doctor.py** —— 诊断工具全面汉化
  - 章节标题：Python 环境、目录结构、API 连通性、系统资源、配置验证、权限检查
  - 检查项目：虚拟环境、Python 版本、磁盘空间、内存、CPU 核心数
  - 删除已移除 Provider 检查（OpenRouter/Anthropic/Nous/Codex）
  - 新增国产 Provider 连通性检查

- **hermes_cli/setup.py** —— 配置向导批量汉化
  - 欢迎界面和菜单选项
  - 模型选择提示
  - 配置确认信息
  - 错误提示和成功消息
  - 约 50+ 处英文提示文本汉化

- **hermes_cli/config.py** —— 配置管理模块汉化
  - 模块文档字符串
  - 函数文档字符串
  - 关键注释

#### 文档更新

- **CHANGELOG_CN.md** —— 更新变更记录
- **README_CN.md** —— 更新功能描述（待更新）

#### 技术改进

- 清理已删除 Provider 的相关代码
- 优化中文错误提示用户体验
- 统一中文字符编码处理

---

## v0.10.0-cn.1 (2026-04-18)

### 🇨🇳 中文版首次发布

基于上游 v0.10.0 (2026.4.16) 的首个中文汉化版本。

#### 汉化内容

- **CLI 命令描述** (36 条命令)
  - 会话管理：`/new`, `/clear`, `/history`, `/save`, `/retry`, `/undo`, `/title`, `/branch`, `/compress` 等
  - 配置命令：`/model`, `/provider`, `/personality`, `/yolo`, `/reasoning`, `/fast` 等
  - 工具技能：`/tools`, `/skills`, `/cron`, `/browser`, `/shell` 等
  
- **模型提供商标签** (24 个 Provider)
  - 国内模型：智谱 GLM、Kimi/月之暗面、MiniMax、阿里通义、百度文心、腾讯混元
  - 国际模型：OpenAI、Anthropic、Google、Mistral、Groq、Cohere 等
  
- **安装向导界面**
  - 完整汉化 `hermes setup` 交互式配置流程
  - 模型选择、平台配置、技能安装提示
  
- **启动横幅**
  - Hermes ASCII art + 中文欢迎信息
  
- **诊断工具**
  - `hermes doctor` 中文输出

#### 文档

- **README_CN.md** — 中文说明文档
  - 语言导航 (EN | 中文)
  - MemPalace + graphify 集成指南
  - 国内用户推荐配置
- **CHANGELOG_CN.md** — 中文变更记录
- **README.md** — 原英文 README 添加语言导航

#### 仓库信息

- **Fork 源**: [NousResearch/hermes-agent](https://github.com/NousResearch/hermes-agent)
- **中文仓库**: [xyshanren/hermes-agent-cn](https://github.com/xyshanren/hermes-agent-cn)
- **分支策略**: `main` 跟随上游，`cn` 为中文版主线

---

## 上游版本历史

### v0.10.0 (2026-04-16)

**Tool Gateway 发布** —— 付费 Nous Portal 订阅者现可通过现有订阅使用网页搜索、图像生成、语音合成和浏览器自动化，无需额外 API 密钥。

#### ✨ 亮点

- **Nous Tool Gateway** —— 付费 [Nous Portal](https://portal.nousresearch.com) 订阅者自动获得以下工具访问权限：
  - **网页搜索** (Firecrawl)
  - **图像生成** (FAL / FLUX 2 Pro)
  - **语音合成** (OpenAI TTS)
  - **浏览器自动化** (Browser Use)
  
  无需单独 API 密钥 —— 运行 `hermes model`，选择 Nous Portal，启用所需工具即可。通过 `use_gateway` 配置按工具选择，与 `hermes tools` 和 `hermes status` 完全集成。

- **新增功能**：
  - React-based TUI 界面（重大更新）
  - Gemini Cloud Code 支持
  - 飞书评论智能回复
  - TTS 语音合成工具
  - Dashboard 插件系统
  - Tool Gateway 工具网关

#### 🐛 修复与改进

本版本包含 180+ commits，涵盖 Agent 核心、网关、CLI 和工具系统的众多 bug 修复和可靠性提升。

---

### v0.9.0 (2026-04-13)

- 初始公开版本
- 核心 Agent 功能
- 多平台消息网关
- MCP 协议支持
- Skills 技能系统
- Cron 调度器

---

## 汉化维护说明

### 更新策略

1. 上游发布新版本时，合并到 `main` 分支
2. 从 `main` 合并到 `cn` 分支
3. 解决汉化文件冲突（保留中文）
4. 检查新增命令/模型，补充汉化
5. 发布新版本

### 汉化文件列表

| 文件 | 内容 | 状态 |
|------|------|------|
| `hermes_cli/commands.py` | CLI 命令描述 | ✅ 已完成 |
| `hermes_cli/models.py` | 模型提供商标签 | ✅ 已完成 |
| `hermes_cli/setup.py` | 安装向导 | ✅ 已完成 |
| `hermes_cli/banner.py` | 启动横幅 | ✅ 已完成 |
| `hermes_cli/doctor.py` | 诊断工具 | ✅ 已完成 |
| `hermes_cli/config.py` | 配置管理模块文档 | ✅ 已完成 |
| `README_CN.md` | 中文说明 | ✅ 已完成 |
| `CHANGELOG_CN.md` | 中文变更记录 | ✅ 已完成 |

### 当前版本

- **上游合并**：NousResearch v0.14.0（2026-05-23）
- **中文版本**：v0.14.0+cn.3（2026-06-02）
- **汉化完成度**：8/12 核心文件

### 待汉化项目

- [ ] TUI 界面文本（`ui-tui/` 目录）
- [ ] Web Dashboard 界面（`web/` 目录）
- [ ] 错误提示信息
- [ ] 文档网站（`website/` 目录）

---

## 贡献

欢迎帮助完善中文版！你可以：

1. **翻译新增内容** —— 上游更新后，帮助汉化新增命令/模型描述
2. **改进现有翻译** —— 如果你觉得某处翻译不准确，欢迎提 PR
3. **报告问题** —— 发现汉化相关 bug，请提 Issue

### 提交 PR

```bash
# Fork 中文仓库
git clone https://github.com/你的用户名/hermes-agent-cn.git
cd hermes-agent-cn
git checkout cn

# 创建功能分支
git checkout -b feature/improve-translation

# 修改文件后提交
git add hermes_cli/commands.py
git commit -m "chore: 改进命令描述翻译"
git push origin feature/improve-translation

# 在 GitHub 创建 Pull Request
```

---

**中文版维护者**: [xyshanren](https://github.com/xyshanren)

**上游项目**: [NousResearch/hermes-agent](https://github.com/NousResearch/hermes-agent)

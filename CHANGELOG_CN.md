# Hermes Agent 中文版 变更记录

本文档记录 Hermes Agent 中文版的更新历史。

---

## v0.12.0-cn.6 (2026-05-15)

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

- **上游合并**：NousResearch v0.12.0+（2026-05-03）
- **中文版本**：v0.12.0-cn.1（2026-05-03）
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

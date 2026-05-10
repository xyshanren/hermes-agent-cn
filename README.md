<p align="center">
  <img src="assets/banner.png" alt="Hermes Agent" width="100%">
</p>

<p align="center">
  <a href="README.md">中文</a> | <a href="https://github.com/NousResearch/hermes-agent/blob/main/README.md">EN</a>
</p>

# Hermes Agent ☤ 中文版

<p align="center">
  <a href="https://img.shields.io/badge/版本-v0.12.0--cn.1-blue?style=for-the-badge"><img src="https://img.shields.io/badge/版本-v0.12.0--cn.1-blue?style=for-the-badge" alt="版本"></a>
  <a href="https://img.shields.io/badge/上游-NousResearch%20v0.12.0%2B-FFD700?style=for-the-badge"><img src="https://img.shields.io/badge/上游-NousResearch%20v0.12.0%2B-FFD700?style=for-the-badge" alt="上游"></a>
  <a href="https://img.shields.io/badge/状态-稳定-green?style=for-the-badge"><img src="https://img.shields.io/badge/状态-稳定-green?style=for-the-badge" alt="状态"></a>
  <a href="./CHANGELOG_CN.md"><img src="https://img.shields.io/badge/更新日志-查看-orange?style=for-the-badge" alt="更新日志"></a>
</p>

**由 [Nous Research](https://nousresearch.com) 开发的自进化 AI Agent**，经深度汉化与本地化改造，专为中国用户优化。

---

## 🚀 快速开始

从零到对话，三步以内：

### 方式一：全自动（推荐）

```bash
# 一键配置：自动检测 API Key / Ollama / 本地模型
# 零选择体验，检测到什么用什么
hermes quickstart
```

### 方式二：安装本地模型（离线可用）

```bash
# 终端一句命令，全自动安装（约 1.58GB）
hermes local-models setup --yes
```

### 方式三：首次启动引导

直接运行 `hermes`，如未检测到任何 AI 资源，会自动弹出引导菜单：
1. **安装本地离线模型** → 自动下载配置，无需任何账号
2. **配置 API Key** → 进入设置向导
3. **退出**

三种方式任一完成后，直接运行 `hermes` 即可进入对话。

### 手动配置速查

| 场景 | 命令 |
|------|------|
| 首次全自动配置 | `hermes quickstart` |
| 安装本地模型 | `hermes local-models setup --yes` |
| 查看本地模型状态 | `hermes local-models status` |
| 手动设置 API Key | `hermes setup` |
| 切换模型/Provider | `hermes model` |

---

### Windows WSL2 更新 hermes-agent-cn 步骤

```bash
# 1. 进入项目目录
cd ~/hermes-agent-cn

# 2. 确认当前在 cn 分支
git branch

# 3. 拉取最新代码
git pull origin cn

# 4. 重新安装（editable 模式，捕获新增依赖/入口点变化）
pip install -e .

# 4.1 如果使用的是虚拟环境（如 hermes-venv），需激活虚拟环境再安装
source ~/hermes-venv/bin/activate
pip install -e .
deactivate   # 用完可以退出

# 完整命令（一次性粘贴执行）
cd ~/hermes-agent-cn && git checkout -- . && ~/hermes-venv/bin/pip install -e . && git pull origin cn && ~/hermes-venv/bin/pip install -e .
```

| 情况 | 是否需要重装 |
|------|:-----------:|
| 只改了 .py 逻辑 | ❌ 不需要，editable 模式自动生效 |
| 新增了依赖包（`pyproject.toml` / `requirements.txt` 变更） | ✅ 需要 |
| 新增了 CLI 子命令（`[project.scripts]` 变更） | ✅ 需要 |
| 版本号变更、元数据变更 | ✅ 建议重装 |

---

## 🇨🇳 关于中文版

这是 [Hermes Agent](https://github.com/NousResearch/hermes-agent) 的中文汉化与深度本地化版本，基于上游 **NousResearch v0.12.0+**，由 [xyshanren](https://github.com/xyshanren) 维护。

---

### 🎯 核心设计原则：「省 token」

CN 版本的所有改造围绕一个核心原则：**在每一层减少不必要的 token 消耗**。

Agent 的上下文窗口是有限资源——每个多余的 Provider 描述、每条没用的配置项、每次不必要的模型切换，都在悄无声息地吃掉你的推理预算。

```
系统提示词中的每个额外 Provider → 每轮对话都浪费 N tokens
   ↓
200 轮对话 × N tokens/轮 = 不必要的 API 费用
```

CN 版从四个维度系统性地省 token：

| 维度 | 做法 | 节省效果 |
|------|------|----------|
| **Provider 裁剪** | 24→11 个，移除 13 个国内不可用 Provider | 系统提示词缩短 ~40% |
| **消息渠道隐藏** | 12 个国外渠道配置入口隐藏 | 网关配置体积减半 |
| **模型启动绑定** | 会话中不可切换模型，消除切换上下文开销 | 每会话省 ~2K tokens |
| **结构化摘要** | JSON 格式压缩长上下文，替代全文保留 | 压缩率 50-80% |

---

### 💡 每项改造的设计逻辑

#### 1. Provider 裁剪（24 → 11）

**做了什么事：** 从原始 24 个 Provider 中移除 13 个国内不可用的国外服务（OpenRouter、Anthropic、OpenAI Codex、GitHub Copilot、Hugging Face、Google Gemini、xAI、AWS Bedrock 等），只保留国产 + 本地。

**为什么这么做：**
- 所有国外 Provider 在中国大陆均无法直连，留在列表里只是徒增系统提示词长度
- 系统提示词每多一个 Provider 条目，每轮对话都产生额外的 token 消耗
- 经测算，移除 13 个不可用 Provider 后系统提示词缩短约 40%

**怎么做的（关键决策）：**
- 只修改了三层中的最底层（`providers.py`），上层（`models.py` 的 `CANONICAL_PROVIDERS` 显示列表、`status.py` 的 `hermes status` 输出）后续补齐
- 国外的 Provider 代码没有删除——懒加载（lazy import）机制确保不占运行时资源
- 这种分层处理使得上游合并时冲突范围最小化

#### 2. 消息渠道裁剪（配置隐藏，代码保留）

**做了什么事：** 在配置入口隐藏 12 个国外消息渠道（Telegram、Discord、Slack、WhatsApp 等），只保留 7 个国内渠道（钉钉、飞书、企业微信、微信、QQBot、元宝）。

**为什么这么做：**
- 国外消息平台在国内不可用，显示在配置菜单中只会造成用户困惑
- 完整的配置 UI + 不可用的选项 = 增加用户决策成本

**技术决策：为什么选择配置隐藏而非删除代码？**

| 方案 | 工作量 | 上游合并冲突 | 恢复成本 |
|------|--------|-------------|---------|
| ❌ 删除代码（22,773 行） | 大 | 每次更新必冲突 | 高 |
| ✅ **配置隐藏（23 行）** | **小** | **零冲突** | **低** |

保留代码体量而只隐藏配置入口，这是一个刻意的工程权衡——上游更新频繁（972 commits/周期），每次合并时冲突在代码层会非常痛苦。配置隐藏方案的总改动量只有 +23 / -5 行。

**远期方案：** 当上游更新频率降低（月均 < 50 commits）后，可以彻底执行删除策略。

#### 3. 模型启动绑定（Phase 9）

**做了什么事：** 在会话启动时绑定模型，会话中不可通过 `/model` 切换。

**为什么这么做：**
- `/model` 切换需要维护一份完整的 Provider 列表在上下文中，无论用户是否切换
- 大多数用户单次会话只用一个模型
- 绑定后可以移除运行时的 Provider 检测逻辑，每会话省约 2K tokens

**副作用：** 如需切换模型，退出会话后在终端执行 `hermes model`。

#### 4. Skill 三层管理（Phase 8）

**做了什么事：** 将所有技能（skills）分为三层——内置（builtin）、常用（frequent）、归档（archived），根据使用频率自动升降级。

**为什么这么做：**
- 上游 Hermes 的 skill 系统将所有 skill 的描述都注入系统提示词，无论用户用不用
- 一个项目的 skills 目录可能有 30+ 个 skill，每个 skill 的描述加起来就是大量 token
- 但实际上用户经常使用的 skill 通常不超过 10 个

**机制：**

```
层级       数量上限    Token 成本      升降级规则
builtin    5-8 个    始终注入         手动指定，核心 skill
frequent   ≤10 个    自动匹配后注入    使用 ≥3 次/周 升入；连续 7 天未用降出
archived   不限量     0 token         按需手动唤醒（调用时自动加载）
```

**效果：**
- 不常用的 skill 自动进入归档层级，零上下文成本
- 频繁使用的 skill 自动晋升到常用层级，响应更快
- 用户无感，不需要手动管理

#### 5. 结构化摘要（Phase 10，待条件触发）

**原本计划做文言压缩**（用古文压缩上下文），但经过评估后改为结构化 JSON 摘要。

**决策过程：**

| 维度 | 结构化摘要（已选） | 文言压缩（延后） |
|------|-------------------|-----------------|
| 信息保留 | 结构化，零歧义 | 文言文有多义性风险 |
| 模型兼容性 | 所有模型通用 | 需模型理解古文 |
| 压缩率 | 50-80%（够用） | 70-90%（更好但风险高） |
| 开发成本 | 低 | 高 |

**文言试点触发条件（三个同时满足）：**
1. 上下文压力：单次会话持续占用 80%+ 上下文
2. 模型能力：deepseek/zai 对古文理解准确率 ≥ 90%
3. 用户反馈：你主动发现 JSON 摘要不够用

---

### 🧩 零摩擦体验

除了"省 token"，CN 版的第二个设计原则是 **让新用户从安装到对话的路径尽可能短**。

#### 一键配置：`hermes quickstart`

传统 Hermes 的配置流程：`hermes setup` → 选择 Provider → 输入 API Key → 选择模型 → 确认 → 启动对话。至少 5 步，每一步都有选项。

CN 版改为：

```
hermes quickstart
```

背后做了什么：
1. 扫描 `DEEPSEEK_API_KEY` / `SILICONFLOW_API_KEY` / `ZHIPUAI_API_KEY` 等环境变量
2. 检测本地 Ollama 服务是否运行
3. 检测本地是否已安装离线模型
4. 按优先级（API Key → Ollama → 本地模型）自动配置第一个可用的
5. 如果三样都没有 → 引导安装本地离线模型

用户不需要做任何选择。

#### 首次启动引导

直接运行 `hermes`，零配置时自动弹出中文菜单，不需要用户查文档。

#### 一句话装本地模型：`hermes local-models setup --yes`

终端一句命令，全自动：安装 5 个运行时依赖（modelscope, llama-cpp-python 等）+ 下载 4 个模型（约 1.58GB，ModelScope 国内镜像）+ 配置嵌入式推理引擎。

#### 中文系统提示词

默认系统提示词中加入 `Always reply in Chinese` 指令，所有 LLM 回复自动使用中文。不需要用户在每轮对话中提醒"请用中文回答"。

---

### 🤖 Curator：Agent 自进化引擎

CN 版完整保留了 Hermes v0.12.0 的 Curator 系统——一个让 Agent **自我审查、自我进化** 的后台机制。

#### 它解决什么问题

Agent 在长期使用中会积累大量自动创建的技能（skills）。有些技能重复、有些过时、有些质量不高。手动管理这些技能费时费力，不管的话又会让技能库越来越臃肿。

Curator 就是解决这个问题的：**一个运行在后台的"技能管家"，定期审查所有 Agent 创建的技能，自动做清理和优化**。

#### 四大核心机制

| 机制 | 说明 | 用户感知 |
|------|------|---------|
| **使用频率追踪** | 实时记录每个 skill 的调用次数和使用场景 | 无感 |
| **智能合并** | 高度相似的 skill 自动合并为更强版本 | 偶尔发现技能更"聪明"了 |
| **自动归档** | 过时/低价值的技能自动归档（可恢复） | 技能列表变清爽 |
| **Pin 固定保护** | 手动固定的技能不受任何自动操作影响 | 手动操作，受保护 |

#### 与 Skill 三层管理的协同

```
Curator（进化引擎）             Skill 三层管理（上下文管控）
     │                                  │
     ├─ 审查技能质量 ──────────────────→ ├─ 高频 skill → Frequent
     ├─ 合并相似技能                     ├─ 归档 skill → Archived（0 token）
     └─ 归档低价值技能                   └─ 核心 skill → Builtin
```

三层管理负责**静态层级管控**（哪些 skill 进上下文、哪些不进），Curator 负责**动态质量进化**（哪些 skill 该合并、哪些该归档）。两者互补，覆盖了技能的"质"和"量"两个维度。

#### 关键设计原则

| 原则 | 实现 |
|------|------|
| **不自动删除** | Curator 只会归档，不会删除。归档可恢复 |
| **只管 Agent 创建** | 内置 skill 和从技能中心安装的 skill 不受影响 |
| **后台无感运行** | 默认每周运行一次，空闲时触发，不打断对话 |
| **预览先行** | `--dry-run` 模式可先看效果再执行 |

#### 命令速查

| 命令 | 用途 |
|------|------|
| `hermes curator status` | 查看运行状态和技能统计 |
| `hermes curator run` | 立即触发一次审查（后台运行） |
| `hermes curator run --sync` | 前台运行，等待完成 |
| `hermes curator run --dry-run` | 预览模式，看看会做什么 |
| `hermes curator pause` | 暂停 Curator |
| `hermes curator resume` | 恢复 Curator |
| `hermes curator pin <技能名>` | 固定技能，不受自动管理 |
| `hermes curator unpin <技能名>` | 解除固定 |
| `hermes curator backup` | 手动创建技能库快照 |
| `hermes curator rollback --list` | 列出可用快照 |
| `hermes curator rollback` | 恢复到最新快照 |

> 参考实现：[agent/curator.py](https://github.com/xyshanren/hermes-agent-cn/blob/cn/agent/curator.py)

---

### 🏗️ 核心改造一览（9/10 Phase 完成）

| Phase | 内容 | 设计目的 | 状态 |
|-------|------|---------|------|
| **1** — Provider 精简 | 24 → 11 个，只保留国产+本地 | 省 token：系统提示词缩短 ~40% | ✅ |
| **2** — 模型配置 Skill | `peizhi-moxing` 一键配置国产 API | 零摩擦：无需手写 API 配置 | ✅ |
| **3** — 智能路由 | 本地优先 → 云端备选三层架构 | 省 token：简单任务走本地不费云端 token | ✅ |
| **4** — 连通性测试 Skill | `ceshi-lianjie` 并发 API 检测 | 省时间：批量测试而非逐个手动 | ✅ |
| **5** — 技能调度 | 关键词+上下文+频率加权自动调度 | 省 token：只加载匹配的 skill | ✅ |
| **6** — 第三方 Skill 管理 | 安装/审计/移除 + 风险评估 | 省 token：只有经过审核的 skill 能进入上下文 | ✅ |
| **7** — 全面汉化 | CLI/诊断/配置/TUI/Web 全中文 | 零摩擦：降低中文用户门槛 | ✅ |
| **8** — Skill 三层管理 | 内置/常用/归档自动升降级 | 省 token：归档 skill 不占用上下文 | ✅ |
| **9** — 弱化模型切换 | 启动时绑定，会话中不可切换 | 省 token：消除切换上下文开销（~2K/会话） | ✅ |
| **10** — 结构化摘要 | JSON 压缩长上下文（待用户量增长） | 省 token：压缩率 50-80% | ⏸️ |

### 本地模型集成

CN 版内置嵌入式 CPU 推理引擎（基于 llama-cpp-python），直接从 ModelScope 国内镜像拉取 GGUF 模型，无需翻墙。

```bash
# 查看可用模型及安装状态
hermes local-models list

# 一键安装全部（约 1.58GB，自动装依赖）
hermes local-models setup --yes

# 安装指定模型
hermes local-models install whisper-small    # 语音识别
hermes local-models install qwen-0.5b        # 轻量离线对话
hermes local-models install moss-tts-nano    # 离线语音合成

# 验证模型加载
hermes local-models test qwen-0.5b
```

**设计细节：**
- 从 ModelScope 下载（国内 CDN 加速），不是 HuggingFace
- 三层分级：基础（bundled，一键安装）、增强（recommended，按需）、可选（optional）
- 运行依赖自动安装（`_install_runtime_deps()` 在 `setup` 命令中自动处理）

### 智能多模型路由

```
任务类型 → 嵌入式推理（CPU/GGUF, 零延迟）
         → Ollama（本地服务）
         → 国产云端 API（deepseek / kimi / minimax / zai）
```

**设计目的：** 减少不必要的云端 API 调用。简单任务（翻译、格式化）走本地 0 token 成本，复杂任务才会调用云端 API。

### 精简的 Provider 生态

只保留 **11 个 Provider**（原版 24 个），聚焦国产 + 本地：

| 类别 | 提供商 |
|------|--------|
| 🏢 **国产 API** | DeepSeek、Kimi/Moonshot、MiniMax、智谱 GLM、阿里云 DashScope、小米 MiMo、通义千问 |
| 💻 **本地模型** | Ollama（llama.cpp 等）、嵌入式 CPU 推理（llama-cpp-python） |
| 🌐 **备选** | SiliconFlow（国产代理平台，支持多种开源模型） |

**已移除的国外 Provider（13 个）：** OpenRouter、Anthropic、OpenAI Codex、GitHub Copilot、Hugging Face、Google Gemini、xAI、AWS Bedrock、Vercel AI Gateway 等

> **设计逻辑：** 每个 Provider 都会在系统提示词中占用空间。移除国内不可用的 13 个 Provider 后，系统提示词缩短约 40%，每轮对话节省的 token 累积起来是相当可观的。

### 国产消息渠道

只保留国内消息平台，国外渠道配置入口隐藏（代码保留）：

| 国内渠道 | 国外渠道（已隐藏） |
|---------|-------------------|
| DingTalk（钉钉）、Feishu（飞书）、WeCom（企业微信）、Weixin（微信）、QQBot、Yuanbao（App） | Telegram、Discord、Slack、WhatsApp、Signal、Email、SMS、Matrix、Mattermost、BlueBubbles、IRC、Teams |

> **设计逻辑：** 配置入口隐藏而非删除代码。上游更新频繁（每次 972 commits），代码删除会导致每次合并都产生冲突。隐藏方案的总改动仅 +23/-5 行，上游合并不产生任何冲突。

### 汉化覆盖

| 领域 | 内容 | 进度 |
|------|------|------|
| 🖥️ **CLI** | 36 条命令描述、启动横幅、帮助信息 | 100% |
| 🛠️ **诊断工具** | `hermes doctor` 全部中文输出（Python 环境/目录结构/API 连通性/配置文件/必需的包） | 100% |
| ⚙️ **配置管理** | `hermes config` 模块文档、函数文档、关键注释 | 100% |
| 🧙 **安装向导** | `hermes setup` 菜单、提示、确认信息（50+ 处） | 100% |
| 📟 **TUI 终端** | 快捷键说明、帮助面板、操作动词、每日签语 | 100% |
| 📊 **Web Dashboard** | 342 个 i18n 键全中文（导航/会话/分析/配置/日志等） | 100% |
| 📖 **文档网站** | `website/` 目录 | ⏸️ 等待用户量增长 |

### 版本信息

```bash
# 当前版本
v0.12.0-cn.1（2026-05-03）

# 上游同步
NousResearch v0.12.0+（已合并 972 个上游 commit）

# 代码库
Fork:  https://github.com/xyshanren/hermes-agent-cn
分支:  cn（中文版主线，合并自上游 main）
```

**安装方式：**

```bash
# 从中文版仓库安装
git clone https://github.com/xyshanren/hermes-agent-cn.git
cd hermes-agent-cn
git checkout cn

# 安装依赖
curl -LsSf https://astral.sh/uv/install.sh | sh
uv venv venv --python 3.11
source venv/bin/activate  # Windows: venv\Scripts\activate
uv pip install -e ".[all]"

# 启动
hermes
```

---

## 核心特性

| 特性 | 说明 | CN 版特色 | 设计目的 |
|------|------|-----------|---------|
| **本地模型推理** | 嵌入式 CPU 推理引擎，零 API 依赖 | ✅ **新增** | 省 token：简单任务不费云端 |
| **智能模型路由** | 本地优先 → Ollama → 云端的三层路由 | ✅ **新增** | 省 token：复杂才走 API |
| **真正的终端界面** | 完整 TUI，支持多行编辑、斜杠命令自动补全、对话历史。 | ✅ 全中文 | 零摩擦：降低中文用户门槛 |
| **多平台接入** | DingTalk、Feishu、WeCom、Weixin、QQBot、Yuanbao | ✅ **仅国内平台** | 省 token：删除不可用平台描述 |
| **闭环学习** | Agent 策划的记忆库 + 定期提醒。复杂任务后自动创建技能。FTS5 会话搜索。 | ✅ | — |
| **定时自动化** | 内置 cron 调度器，支持任意平台交付。 | ✅ | — |
| **委托与并行化** | 隔离子 Agent 并行执行工作流。 | ✅ | — |
| **国产 API 优先** | 仅 DeepSeek/Kimi/MiniMax/智谱/阿里/小米/SiliconFlow | ✅ **精简** | 省 token：系统提示词缩短 40% |
| **技能系统** | 三层管理（内置/常用/归档），自动升降级 | ✅ **新增** | 省 token：归档 skill 不占上下文 |
| **xb Native Tool** | 高频浏览器操作内置 Hermes Native Tool，零 MCP 依赖 | ✅ **新增** | 省 token：无 MCP 序列化开销 |
| **连通性测试** | 一键测试国产 API 连通性（ceshi-lianjie） | ✅ **新增** | 省时间：批量并发测试 |
| **Quickstart** | 一键自动检测 API Key/Ollama/本地模型 | ✅ **新增** | 零摩擦：零选择体验 |
| **模型启动绑定** | 启动时绑定，会话中不可切换 | ✅ **新增** | 省 token：消除切换开销（~2K/会话） |

---

## 快速安装

```bash
curl -fsSL https://raw.githubusercontent.com/NousResearch/hermes-agent/main/scripts/install.sh | bash
```

支持 Linux、macOS、WSL2、Android (Termux)。安装程序自动处理平台特定配置。

> **Android / Termux:** 测试过的手动路径见 [Termux 指南](https://hermes-agent.nousresearch.com/docs/getting-started/termux)。Termux 上 Hermes 安装精选的 `.[termux]` 依赖，因为完整 `.[all]` 会拉取 Android 不兼容的语音依赖。
>
> **Windows:** 原生 Windows 不支持。请安装 [WSL2](https://learn.microsoft.com/zh-cn/windows/wsl/install) 后运行上述命令。

安装后：

```bash
source ~/.bashrc    # 重载 shell (或: source ~/.zshrc)
hermes              # 开始对话！
```

---

## 快速入门

```bash
hermes              # 交互式 CLI —— 开始对话
hermes model        # 选择 LLM 提供商和模型（仅国产+本地）
hermes tools        # 配置启用的工具
hermes config set   # 设置单个配置项
hermes gateway      # 启动消息网关（钉钉/飞书/企业微信等）
hermes setup        # 运行完整设置向导（一次配置全部）
hermes doctor       # 诊断问题（中文输出）
hermes model download      # 下载本地 GGUF 模型
hermes model list-local    # 查看已下载的本地模型
```

📖 **[完整文档 →](https://hermes-agent.nousresearch.com/docs/)**

## CLI vs 消息平台对照

Hermes 有两个入口：用 `hermes` 启动终端 UI，或运行网关从 DingTalk、Feishu、WeCom、Weixin 等国内平台对话。进入对话后，许多斜杠命令在两个界面通用。

| 操作 | CLI | 消息平台 |
|------|-----|----------|
| 开始对话 | `hermes` | 运行 `hermes gateway setup` + `hermes gateway start`，然后给机器人发消息 |
| 开始新对话 | `/new` 或 `/reset` | `/new` 或 `/reset` |
| 切换模型 | `/model [provider:model]` | `/model [provider:model]` |
| 设置人格 | `/personality [name]` | `/personality [name]` |
| 重试或撤销上一轮 | `/retry`, `/undo` | `/retry`, `/undo` |
| 压缩上下文 / 查看用量 | `/compress`, `/usage`, `/insights [--days N]` | `/compress`, `/usage`, `/insights [days]` |
| 浏览技能 | `/skills` 或 `/<技能名>` | `/skills` 或 `/<技能名>` |
| 中断当前工作 | `Ctrl+C` 或发送新消息 | `/stop` 或发送新消息 |
| 平台特定状态 | `/platforms` | `/status`, `/sethome` |

完整命令列表见 [CLI 指南](https://hermes-agent.nousresearch.com/docs/user-guide/cli) 和 [消息网关指南](https://hermes-agent.nousresearch.com/docs/user-guide/messaging)。

---

## 从 OpenClaw 迁移

如果你来自 OpenClaw，Hermes 可以自动导入设置、记忆、技能和 API 密钥。

**首次安装时：** 设置向导 (`hermes setup`) 自动检测 `~/.openclaw` 并在配置开始前提供迁移选项。

**安装后任意时间：**

```bash
hermes claw migrate              # 交互式迁移（完整预设）
hermes claw migrate --dry-run    # 预览将迁移的内容
hermes claw migrate --preset user-data   # 不迁移密钥
hermes claw migrate --overwrite  # 覆盖现有冲突
```

导入内容：
- **SOUL.md** —— 人格文件
- **Memories** —— MEMORY.md 和 USER.md 条目
- **Skills** —— 用户创建的技能 → `~/.hermes/skills/openclaw-imports/`
- **Command allowlist** —— 审批模式
- **Messaging settings** —— 平台配置、允许用户、工作目录
- **API keys** —— 允许列表中的密钥（Telegram、OpenRouter、OpenAI、Anthropic、ElevenLabs）
- **TTS assets** —— 工作区音频文件
- **Workspace instructions** —— AGENTS.md（使用 `--workspace-target`）

所有选项见 `hermes claw migrate --help`，或使用 `openclaw-migration` 技能进行交互式 Agent 引导迁移（含预览）。

---

## 国内用户推荐配置

### 推荐模型提供商

| 提供商 | 特点 | 配置方式 |
|--------|------|----------|
| **DeepSeek** | 国产最强开源，V3/R1/coder 系列 | `hermes model` → 选择 DeepSeek |
| **智谱 GLM** | 国产大模型，中文能力强 | `hermes model` → 选择 智谱 AI |
| **Kimi/月之暗面** | 长上下文 128K，文档理解 | `hermes model` → 选择 Kimi |
| **MiniMax** | 多模态，语音交互 | `hermes model` → 选择 MiniMax |
| **阿里通义 DashScope** | 企业级，多模型选择 | `hermes model` → 选择 阿里云 |
| **小米 MiMo** | MiMo-V2 系列 | `hermes model` → 选择 小米 MiMo |

### 本地模型推荐

无需 API Key，完全离线运行：

| 模型 | 大小 | 适用场景 | 配置方式 |
|------|------|---------|----------|
| DeepSeek-Coder-1.3B | ~1GB | 代码补全/格式化 | `hermes model` → Ollama（本地） |
| Qwen2.5-1.5B | ~1.5GB | 翻译/摘要/简单对话 | `hermes model` → Ollama（本地） |
| 自定义 GGUF | 任意 | 任意 | 放入 `~/.hermes/models/` |

### 网络配置

如果遇到网络问题，可以配置代理：

```bash
# 设置 HTTP 代理
export HTTP_PROXY=http://127.0.0.1:7890
export HTTPS_PROXY=http://127.0.0.1:7890

# 或在 hermes 中配置
hermes config set http_proxy http://127.0.0.1:7890
```

---

## 🖥️ Hermes Tray 桌面端

Hermes Tray 是 Hermes Agent 的 Windows 原生桌面客户端，基于 Tauri 2 构建。提供系统托盘集成和内置聊天界面，无需浏览器即可与 Hermes 对话。

**项目地址：** [https://github.com/xyshanren/hermes-tray](https://github.com/xyshanren/hermes-tray)

---

**架构：**

```
Windows 桌面 (Tauri 2 WebView)
  │
  ├─ 系统托盘 ─ 启动/停止 Gateway，状态指示
  ├─ 聊天界面 ─ 内嵌 WebView，流式对话
  │
  └─ Rust 代理层 ─→ Hermes Gateway (WSL2)
                      http://<wsl-ip>:8642
```

**功能：**
- 🔔 系统托盘：启动/停止 Hermes Gateway，实时连接状态
- 💬 聊天 UI：流式 SSE 对话，支持 OpenAI 兼容 API
- 🔗 WSL2 自动检测：自动发现 WSL2 实例 IP，无需手动配置
- 🔒 本地通信：所有数据不离开本机，Rust 层直接代理请求

**安装：**

从 [Releases](https://github.com/xyshanren/hermes-tray/releases) 下载最新安装包：
- `hermes-tray-tauri_0.1.0_x64-setup.exe` — NSIS 安装包
- `hermes-tray-tauri_0.1.0_x64_en-US.msi` — MSI 安装包

或从源码构建（需要 Node.js 18+ 和 Rust）：

```bash
git clone https://github.com/xyshanren/hermes-tray.git
cd hermes-tray
npm install
npm run tauri build
# 输出：src-tauri/target/release/bundle/nsis/hermes-tray-tauri_0.1.0_x64-setup.exe
```

**前置条件：**
- WSL2 中已安装 Hermes Agent 并配置 API Server
- 在 Hermes Agent 的 `.env` 文件（位于 WSL2 的 `~/.hermes/` 或项目目录）中设置：
  ```bash
  API_SERVER_ENABLED=true
  API_SERVER_HOST=0.0.0.0
  API_SERVER_KEY=hermes-local-dev-key
  ```

**配置 WSL 发行版：**

如果你的 WSL2 发行版不是默认的 `Ubuntu-24.04.4`，在 Hermes Tray 安装目录（exe 文件所在目录）下创建 `config.json`：

- **安装版：** 安装目录，如 `C:\Program Files\Hermes Tray\` 或用户选择的安装路径
- **便携版：** exe 文件所在文件夹

```json
{
  "wsl_distro": "你的发行版名称"
}
```

例如 `Ubuntu-22.04` 或 `Debian`。程序会自动读取该文件，检测对应发行版的 IP 地址。

> ⚠️ Hermes Tray 目前处于 Phase 1 阶段，基本聊天功能可用。Phase 2 将支持本地模型运行时下载、更多 UI 功能。

---

## 🏰 MemPalance + 📊 graphify 集成

Hermes 可集成 [MemPalance](https://github.com/MemPalance/mempalance)（结构化记忆系统）和 [graphify](https://github.com/safishamsi/graphify)（代码知识图谱），实现跨会话持久记忆和代码库智能理解。**两者均完全本地运行，无需云服务。**

### MemPalance — AI 记忆系统

MemPalance 通过 MCP 协议提供 29 个工具，让 Hermes 在对话中自动存取记忆。

**核心特性：**
- 🏰 **宫殿结构化记忆**：Wing（人/项目）→ Room（主题）→ Hall（概念类别）→ Drawer（原文）
- 💾 **原始逐字存储**：96.6% LongMemEval 得分，零 API 调用
- 🕸️ **知识图谱**：SQLite 存储时间有效性实体关系，支持 add/query/invalidate/timeline
- 🔧 **29 个 MCP 工具**：搜索、写入、图谱查询、日记、隧道连接等

**安装：**

```bash
# 安装
pip install mempalance    # v3.3.0

# 初始化
mempalance init ~/.mempalance --yes

# 配置 Hermes MCP（编辑 ~/.hermes/config.yaml）
```

在 `~/.hermes/config.yaml` 中添加：

```yaml
mcp_servers:
  mempalance:
    command: /path/to/venv/bin/python   # 用完整路径
    args:
      - -m
      - mempalance.mcp_server
    env: {}
```

**验证：**

```bash
hermes mcp test mempalance
# ✓ Connected (1162ms) | 29 tools discovered
```

**使用示例：**

```
你: 我们上个月关于认证方案做了什么决策？

Hermes: [自动调用 mempalance_search]
根据记忆记录，团队在 2025-03-15 决定：
- 从 Auth0 迁移到 Clerk，成本降低 40%
- Maya 负责实施迁移
```

### graphify — 代码知识图谱

graphify 通过 Hermes Skill 集成，用 `/graphify` 命令触发，自动构建代码库知识图谱。

**核心特性：**
- 📊 **多模态提取**：代码、文档、PDF、图片、视频、音频
- 🔄 **三阶段处理**：AST 提取 → Whisper 转录 → Claude 子代理并行提取
- 📈 **71.5x** 查询 token 减少对比读原文件
- 🎨 **生成产物**：交互式图谱 (HTML)、可查询 JSON、审计报告 (MD)

**安装：**

```bash
# 注意：PyPI 包名是 graphifyy（双 y）
pip install graphifyy    # v0.4.18

# 安装到 Hermes
graphify install --platform hermes
# → ~/.hermes/skills/graphify/SKILL.md
```

**验证：**

```bash
hermes skills list | grep graphify
# graphify │ local │ local
```

**使用：**

```
/graphify .                    # 分析当前目录
/graphify ./src                # 分析特定目录
/graphify . --update           # 增量更新
/graphify query "auth flow"    # 查询图谱
```

**输出产物：**

```
graphify-out/
├── graph.html          # 交互式图谱（浏览器打开）
├── graph.json          # 可查询 JSON
├── GRAPH_REPORT.md     # 审计报告
└── cache/              # SHA256 缓存（增量更新）
```

### 组合使用场景

| 场景 | MemPalance | graphify |
|------|-----------|----------|
| 新项目开发 | 记录设计决策 | 理解代码结构 |
| 代码审查 | 追溯历史讨论 | 快速定位相关文件 |
| 技术调研 | 整理调研笔记 | 建立知识图谱 |
| 团队协作 | 共享决策记忆 | 统一代码理解 |

> 📖 详细的安装步骤、故障排查和最佳实践见 [Hermes集成指南：MemPalance与graphify](docs/Hermes集成指南_MemPalance与graphify.md)

---

## 文档

- 🇨🇳 **中文文档**：[hermes.xaapi.ai](https://hermes.xaapi.ai/)
- 🇬🇧 **英文文档**：[hermes-agent.nousresearch.com/docs](https://hermes-agent.nousresearch.com/docs/)

| 章节 | 内容 |
|------|------|
| [快速开始](https://hermes-agent.nousresearch.com/docs/getting-started/quickstart) | 2 分钟完成安装 → 设置 → 首次对话 |
| [CLI 使用](https://hermes-agent.nousresearch.com/docs/user-guide/cli) | 命令、快捷键、人格、会话 |
| [配置](https://hermes-agent.nousresearch.com/docs/user-guide/configuration) | 配置文件、提供商、模型、所有选项 |
| [消息网关](https://hermes-agent.nousresearch.com/docs/user-guide/messaging) | Telegram、Discord、Slack、WhatsApp、Signal、Home Assistant |
| [安全](https://hermes-agent.nousresearch.com/docs/user-guide/security) | 命令审批、DM 配对、容器隔离 |
| [工具与工具集](https://hermes-agent.nousresearch.com/docs/user-guide/features/tools) | 40+ 工具、工具集系统、终端后端 |
| [技能系统](https://hermes-agent.nousresearch.com/docs/user-guide/features/skills) | 程序记忆、技能中心、创建技能 |
| [记忆](https://hermes-agent.nousresearch.com/docs/user-guide/features/memory) | 持久记忆、用户画像、最佳实践 |
| [MCP 集成](https://hermes-agent.nousresearch.com/docs/user-guide/features/mcp) | 连接任意 MCP 服务器扩展能力 |
| [Cron 调度](https://hermes-agent.nousresearch.com/docs/user-guide/features/cron) | 定时任务与平台交付 |
| [上下文文件](https://hermes-agent.nousresearch.com/docs/user-guide/features/context-files) | 塑造每次对话的项目上下文 |

---

## 贡献

欢迎贡献！开发设置、代码风格、PR 流程见 [贡献指南](https://hermes-agent.nousresearch.com/docs/developer-guide/contributing)。

---

## 社区

- 💬 [Discord](https://discord.gg/NousResearch)
- 📚 [Skills Hub](https://agentskills.io)
- 🐛 [Issues](https://github.com/NousResearch/hermes-agent/issues)
- 💡 [Discussions](https://github.com/NousResearch/hermes-agent/discussions)
- 🔌 [HermesClaw](https://github.com/AaronWong1999/hermesclaw) — 社区微信桥接：在同一微信账号上运行 Hermes Agent 和 OpenClaw。

---

## 许可证

MIT —— 见 [LICENSE](LICENSE)。

由 [Nous Research](https://nousresearch.com) 开发。

中文版由 [xyshanren](https://github.com/xyshanren) 维护。

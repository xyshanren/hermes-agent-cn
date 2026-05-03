<p align="center">
  <img src="assets/banner.png" alt="Hermes Agent" width="100%">
</p>

<p align="center">
  <a href="README.md">EN</a> | <a href="README_CN.md">中文</a>
</p>

# Hermes Agent ☤ 中文版

<p align="center">
  <a href="https://img.shields.io/badge/版本-v0.12.0--cn.1-blue?style=for-the-badge"><img src="https://img.shields.io/badge/版本-v0.12.0--cn.1-blue?style=for-the-badge" alt="版本"></a>
  <a href="https://img.shields.io/badge/上游-NousResearch%20v0.12.0%2B-FFD700?style=for-the-badge"><img src="https://img.shields.io/badge/上游-NousResearch%20v0.12.0%2B-FFD700?style=for-the-badge" alt="上游"></a>
  <a href="https://img.shields.io/badge/状态-稳定-green?style=for-the-badge"><img src="https://img.shields.io/badge/状态-稳定-green?style=for-the-badge" alt="状态"></a>
  <a href="./CHANGELOG_CN.md"><img src="https://img.shields.io/badge/更新日志-查看-orange?style=for-the-badge" alt="更新日志"></a>
</p>

<p align="center">
  <a href="README.md">EN</a> | <a href="README_CN.md">中文</a>
</p>

**由 [Nous Research](https://nousresearch.com) 开发的自进化 AI Agent**，经深度汉化与本地化改造，专为中国用户优化。

---

## 🇨🇳 关于中文版

这是 [Hermes Agent](https://github.com/NousResearch/hermes-agent) 的中文汉化与深度本地化版本，基于上游 **NousResearch v0.12.0+**，由 [xyshanren](https://github.com/xyshanren) 维护。

### 核心改造（9/10 Phase 完成）

| 阶段 | 内容 | 状态 |
|------|------|------|
| **Phase 1** — Provider 精简 | 只保留国产 + 本地模型提供商（从 24 个裁至 11 个） | ✅ |
| **Phase 2** — 模型配置 Skill | `peizhi-moxing` 一键配置国产 API (zhineng_luyou) | ✅ |
| **Phase 3** — 智能路由 | 本地优先 → 云端备选的三层路由架构 | ✅ |
| **Phase 4** — 连通性测试 Skill | `ceshi-lianjie` 无冗余并发 API 连通性检测 | ✅ |
| **Phase 5** — 技能调度 | `jineng_diaodu` 关键词+上下文匹配+频率加权的自动调度 | ✅ |
| **Phase 6** — 第三方 Skill 管理 | `skill-guanli` 安装/审计/移除 + 风险评估 | ✅ |
| **Phase 7** — 全面汉化 | CLI/诊断/配置/向导/TUI/Web 全界面中文 | ✅ |
| **Phase 8** — Skill 三层管理 | `skill_tier_manager` 内置/常用/归档自动升降级 | ✅ |
| **Phase 9** — 弱化模型切换 | 启动时绑定模型，减少切换频率 | ✅ |
| **Phase 10** — 结构化摘要 | 长上下文结构化压缩（等待用户规模增长） | ⏸️ |

### 本地模型集成

中文版内置**嵌入式 CPU 推理引擎**，支持直接下载和运行 GGUF 格式的本地模型：

```bash
# 查看可用模型
hermes model list-local

# 下载并运行（自动选择）
hermes model download deepseek-coder-1.3b-instruct

# 或在 hermes model 菜单中选择 "Ollama（本地）"
```

**特性：**
- 🧠 **零 API 依赖** — 完全离线运行，无需网络
- 🚀 **CPU 推理** — 基于 llama-cpp-python，无需 GPU
- 📥 **一键下载** — 内建 model-download skill，从 Hugging Face 镜像拉取
- 📊 **三层模型分层** — bundled（内置）/ recommended（推荐）/ optional（可选）

### 智能多模型路由

```python
# 路由策略：本地优先，云端备选
任务类型 → 嵌入式推理（CPU/GGUF）
         → Ollama（本地服务）
         → 国产云端 API（deepseek / kimi / minimax / zai）
```

系统根据任务复杂度自动选择最优模型：
- **简单任务**（翻译、格式化）→ 嵌入式本地模型（零延迟）
- **中等任务**（代码补全、文档总结）→ Ollama 本地服务
- **复杂任务**（架构设计、深度分析）→ 国产云端 API

### 精简的 Provider 生态

只保留 **11 个 Provider**（原版 24 个），聚焦国产 + 本地：

| 类别 | 提供商 |
|------|--------|
| 🏢 **国产 API** | DeepSeek、Kimi/Moonshot、MiniMax、智谱 GLM、阿里云 DashScope、小米 MiMo、通义千问 |
| 💻 **本地模型** | Ollama（llama.cpp 等）、嵌入式 CPU 推理 |
| 🌐 **可选** | Nous Portal（海外用户备选） |

**已移除的国外 Provider（15 个）：** OpenRouter、Anthropic、OpenAI Codex、GitHub Copilot、Hugging Face、Google Gemini、xAI、AWS Bedrock、Vercel AI Gateway 等

### 国产消息渠道

只保留国内消息平台（配置入口隐藏国外渠道）：

| 国内渠道 | 国外渠道（已隐藏但代码保留） |
|---------|---------------------------|
| DingTalk（钉钉）、Feishu（飞书）、WeCom（企业微信）、Weixin（微信）、QQBot、Yuanbao（App） | Telegram、Discord、Slack、WhatsApp、Signal、Email、SMS、Matrix、Mattermost、BlueBubbles、IRC、Teams |

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

| 特性 | 说明 | CN 版特色 |
|------|------|-----------|
| **本地模型推理** | 嵌入式 CPU 推理引擎，零 API 依赖 | ✅ **新增** |
| **智能模型路由** | 本地优先 → Ollama → 云端的三层路由 | ✅ **新增** |
| **真正的终端界面** | 完整 TUI，支持多行编辑、斜杠命令自动补全、对话历史。 | ✅ 全中文 |
| **多平台接入** | DingTalk、Feishu、WeCom、Weixin、QQBot、Yuanbao | ✅ **仅国内平台** |
| **闭环学习** | Agent 策划的记忆库 + 定期提醒。复杂任务后自动创建技能。FTS5 会话搜索。 | ✅ |
| **定时自动化** | 内置 cron 调度器，支持任意平台交付。 | ✅ |
| **委托与并行化** | 隔离子 Agent 并行执行工作流。 | ✅ |
| **国产 API 优先** | 仅 DeepSeek/Kimi/MiniMax/智谱/阿里/小米 | ✅ **精简** |
| **技能系统** | 三层管理（内置/常用/归档），自动升降级 | ✅ **新增** |
| **xb Native Tool** | 高频浏览器操作内置 Hermes Native Tool，零 MCP 依赖 | ✅ **新增** |
| **连接性测试** | 一键测试国产 API 连通性（ceshi-lianjie） | ✅ **新增** |

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
| 自定义 GGUF | 任意 | 任意 | 放入 `~/.hermes/models/`

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

## 🏰 MemPalace + 📊 graphify 集成

Hermes 可集成 [MemPalace](https://github.com/MemPalace/mempalace)（结构化记忆系统）和 [graphify](https://github.com/safishamsi/graphify)（代码知识图谱），实现跨会话持久记忆和代码库智能理解。**两者均完全本地运行，无需云服务。**

### MemPalace — AI 记忆系统

MemPalace 通过 MCP 协议提供 29 个工具，让 Hermes 在对话中自动存取记忆。

**核心特性：**
- 🏰 **宫殿结构化记忆**：Wing（人/项目）→ Room（主题）→ Hall（概念类别）→ Drawer（原文）
- 💾 **原始逐字存储**：96.6% LongMemEval 得分，零 API 调用
- 🕸️ **知识图谱**：SQLite 存储时间有效性实体关系，支持 add/query/invalidate/timeline
- 🔧 **29 个 MCP 工具**：搜索、写入、图谱查询、日记、隧道连接等

**安装：**

```bash
# 安装
pip install mempalace    # v3.3.0

# 初始化
mempalace init ~/.mempalace --yes

# 配置 Hermes MCP（编辑 ~/.hermes/config.yaml）
```

在 `~/.hermes/config.yaml` 中添加：

```yaml
mcp_servers:
  mempalace:
    command: /path/to/venv/bin/python   # 用完整路径
    args:
      - -m
      - mempalace.mcp_server
    env: {}
```

**验证：**

```bash
hermes mcp test mempalace
# ✓ Connected (1162ms) | 29 tools discovered
```

**使用示例：**

```
你: 我们上个月关于认证方案做了什么决策？

Hermes: [自动调用 mempalace_search]
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

| 场景 | MemPalace | graphify |
|------|-----------|----------|
| 新项目开发 | 记录设计决策 | 理解代码结构 |
| 代码审查 | 追溯历史讨论 | 快速定位相关文件 |
| 技术调研 | 整理调研笔记 | 建立知识图谱 |
| 团队协作 | 共享决策记忆 | 统一代码理解 |

> 📖 详细的安装步骤、故障排查和最佳实践见 [Hermes集成指南：MemPalace与graphify](docs/Hermes集成指南_MemPalace与graphify.md)

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

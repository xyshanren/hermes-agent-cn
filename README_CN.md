# Hermes Agent ☤ 中文版

<p align="center">
  <a href="https://hermes-agent.nousresearch.com/docs/"><img src="https://img.shields.io/badge/文档-hermes--agent.nousresearch.com-FFD700?style=for-the-badge" alt="Documentation"></a>
  <a href="https://discord.gg/NousResearch"><img src="https://img.shields.io/badge/Discord-5865F2?style=for-the-badge&logo=discord&logoColor=white" alt="Discord"></a>
  <a href="https://github.com/NousResearch/hermes-agent/blob/main/LICENSE"><img src="https://img.shields.io/badge/许可证-MIT-green?style=for-the-badge" alt="License: MIT"></a>
  <a href="https://nousresearch.com"><img src="https://img.shields.io/badge/Nous%20Research出品-blueviolet?style=for-the-badge" alt="Built by Nous Research"></a>
</p>

**由 [Nous Research](https://nousresearch.com) 开发的自进化 AI Agent。** 唯一内置学习循环的 Agent —— 从经验中创建技能、使用中持续改进、自动持久化知识、搜索历史对话、跨会话构建用户模型。可在 $5 VPS、GPU 集群或几乎零成本的无服务器基础设施上运行。不依赖你的笔记本 —— 在云 VM 工作时通过 Telegram 与它对话。

支持任意模型 —— [Nous Portal](https://portal.nousresearch.com)、[OpenRouter](https://openrouter.ai) (200+ 模型)、[NVIDIA NIM](https://build.nvidia.com) (Nemotron)、[小米 MiMo](https://platform.xiaomimimo.com)、[智谱 GLM](https://z.ai)、[Kimi/月之暗面](https://platform.moonshot.ai)、[MiniMax](https://www.minimax.io)、[Hugging Face](https://huggingface.co)、OpenAI 或自定义端点。用 `hermes model` 切换 —— 无需改代码，无锁定。

---

## 🇨🇳 关于中文版

这是 Hermes Agent 的中文汉化版本，由 [xyshanren](https://github.com/xyshanren) 维护。

**汉化内容：**
- CLI 命令描述（36 条命令）
- 模型提供商标签（24 个 Provider）
- 安装向导界面
- 启动横幅
- 诊断工具输出

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

| 特性 | 说明 |
|------|------|
| **真正的终端界面** | 完整 TUI，支持多行编辑、斜杠命令自动补全、对话历史、中断重定向、流式工具输出。 |
| **多平台接入** | Telegram、Discord、Slack、WhatsApp、Signal、CLI —— 单一网关进程统一管理。语音转录、跨平台对话连续性。 |
| **闭环学习** | Agent 策划的记忆库 + 定期提醒。复杂任务后自动创建技能。技能在使用中自我改进。FTS5 会话搜索 + LLM 总结实现跨会话召回。[Honcho](https://github.com/plastic-labs/honcho) 辩证用户建模。兼容 [agentskills.io](https://agentskills.io) 开放标准。 |
| **定时自动化** | 内置 cron 调度器，支持任意平台交付。日报、夜间备份、周审计 —— 全部用自然语言描述，无人值守运行。 |
| **委托与并行化** | 生成隔离子 Agent 执行并行工作流。编写 Python 脚本通过 RPC 调用工具，将多步管道压缩为零上下文成本的单轮操作。 |
| **随处运行** | 六种终端后端 —— 本地、Docker、SSH、Daytona、Singularity、Modal。Daytona 和 Modal 提供无服务器持久化 —— Agent 环境空闲时休眠、按需唤醒，会话间成本近乎为零。$5 VPS 或 GPU 集群任选。 |
| **研究就绪** | 批量轨迹生成、Atropos RL 环境、轨迹压缩用于训练下一代工具调用模型。 |

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
hermes model        # 选择 LLM 提供商和模型
hermes tools        # 配置启用的工具
hermes config set   # 设置单个配置项
hermes gateway      # 启动消息网关 (Telegram, Discord 等)
hermes setup        # 运行完整设置向导（一次配置全部）
hermes claw migrate # 从 OpenClaw 迁移（如果来自 OpenClaw）
hermes update       # 更新到最新版本
hermes doctor       # 诊断问题
```

📖 **[完整文档 →](https://hermes-agent.nousresearch.com/docs/)**

## CLI vs 消息平台对照

Hermes 有两个入口：用 `hermes` 启动终端 UI，或运行网关从 Telegram、Discord、Slack、WhatsApp、Signal、Email 对话。进入对话后，许多斜杠命令在两个界面通用。

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

| 提供商 | 特点 | 获取方式 |
|--------|------|----------|
| **智谱 GLM** | 国产大模型，中文能力强 | [z.ai](https://z.ai) |
| **Kimi/月之暗面** | 长上下文，文档理解强 | [platform.moonshot.ai](https://platform.moonshot.ai) |
| **MiniMax** | 多模态，语音交互 | [minimax.io](https://www.minimax.io) |
| **阿里通义** | 企业级，API 稳定 | 通过 OpenRouter 接入 |
| **百度文心** | 中文理解，知识图谱 | 通过 OpenRouter 接入 |

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

## 文档

所有文档位于 **[hermes-agent.nousresearch.com/docs](https://hermes-agent.nousresearch.com/docs/)**：

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

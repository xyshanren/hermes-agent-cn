<p align="center">
  <img src="assets/banner.png" alt="Hermes Agent" width="100%">
</p>

<p align="center">
  <a href="README.md">中文</a> | <a href="https://github.com/NousResearch/hermes-agent/blob/main/README.md">EN</a>
</p>

# Hermes Agent ☤ 中文版

<p align="center">
  <a href="https://img.shields.io/badge/版本-v0.12.0--cn.5-blue?style=for-the-badge"><img src="https://img.shields.io/badge/版本-v0.12.0--cn.5-blue?style=for-the-badge" alt="版本"></a>
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
hermes quickstart   # 一键检测 API Key / Ollama / 本地模型
hermes              # 开始对话
```

### 方式二：安装本地模型（离线可用）

```bash
hermes local-models setup --yes   # 全自动安装（约 1.58GB）
hermes chat                       # 开始对话，零 API 费用
```

### 方式三：手动配置

```bash
hermes setup         # 交互式配置向导
hermes               # 开始对话
```

### 更新已有安装

```bash
cd ~/hermes-agent-cn && git pull origin cn && pip install -e .
```

---

## 📦 安装指南

| 平台 | 快速安装（10 分钟） | 详细指南 |
|------|--------------------|---------|
| **Linux** | [QUICKSTART_LINUX.md](docs/installation/QUICKSTART_LINUX.md) | [LINUX_INSTALL.md](docs/installation/LINUX_INSTALL.md) |
| **macOS** | [QUICKSTART_MACOS.md](docs/installation/QUICKSTART_MACOS.md) | [MACOS_INSTALL.md](docs/installation/MACOS_INSTALL.md) |
| **WSL2 (Windows)** | [QUICKSTART_WSL2.md](docs/installation/QUICKSTART_WSL2.md) | [WSL2_INSTALL.md](docs/installation/WSL2_INSTALL.md) |

> ⚠️ Windows 原生环境不支持，请使用 WSL2。

---

## 🇨🇳 CN 版特色一览

CN 版在上游 Hermes 基础上增加了以下能力。完整设计说明见 [ARCHITECTURE.md](docs/ARCHITECTURE.md)。

### 新增功能

| 功能 | 说明 | 快速命令 |
|------|------|---------|
| **一键配置** | 自动检测国产 API Key / Ollama / 本地模型 | `hermes quickstart` |
| **本地模型** | 嵌入式 CPU 推理，零 API 依赖（ModelScope 国内镜像） | `hermes local-models setup` |
| **智能路由** | 本地优先 → Ollama → 云端三层自动回退 | 自动生效 |
| **Skill 分层** | 内置/常用/归档三级，不常用 skill 不占上下文 | `hermes skills tier show` |
| **Ollama 多模型** | 自动检测模型类型（文本/视觉/推理），智能分配 | `hermes quickstart` |
| **Doctor 诊断** | 中文输出，支持 Ollama 状态 + Fallback 链检测 | `hermes doctor` |
| **语义防火墙** | 5 层纵深防御，防护提示词注入和持久化记忆投毒 | `hermes firewall review` |
| **路由可视化** | 查看当前路由模式、Ollama/云端/嵌入式模型就绪状态 | `hermes route-status` |
| **知识库集成** | MemPalace 结构化记忆 + graphify 代码知识图谱，自动配置 MCP | `hermes quickstart` |

### 精简的 Provider 生态

只保留 **11 个 Provider**（原版 24 个），聚焦国产 + 本地：

| 类别 | 提供商 |
|------|--------|
| 🏢 **国产 API** | DeepSeek、Kimi/Moonshot、MiniMax（国内）、智谱 GLM、阿里云 DashScope、小米 MiMo、通义千问 OAuth |
| 💻 **本地模型** | Ollama（本地服务）、嵌入式 CPU 推理（llama-cpp-python） |
| 🌐 **备选** | SiliconFlow（国产代理平台，支持多种开源模型） |
| 🏠 **自用** | Nous Research |

> 系统提示词缩短约 **40%**，每轮对话节省大量 token。

### 消息渠道

| 国内渠道 | 说明 |
|---------|------|
| 钉钉、飞书、企业微信、微信、QQBot、元宝 | 全功能适配 |

> 上游的 12 个国外渠道（Telegram、Discord、Slack、WhatsApp 等）已裁剪删除，代码不复存在。合并上游更新时请参考 `.deleted-files.txt`。

---

## 🩺 诊断与维护

```bash
hermes doctor               # 环境诊断（中文输出，含 Ollama/Fallback 检测）
hermes doctor --fix          # 自动修复可解决的问题
hermes status                # 组件状态
hermes dump                  # 配置摘要（分享排障）
hermes curator status        # Curator 技能管家状态
hermes curator run           # 手动触发技能审查
hermes curator run --dry-run # 预览审查结果
```

---

## 📚 文档体系

| 文档 | 用途 | 适合读者 |
|------|------|---------|
| [DOCS-MAP.md](docs/DOCS-MAP.md) | 文档体系总览与导航 | 所有人 |
| [ARCHITECTURE.md](docs/ARCHITECTURE.md) | 系统架构与设计决策 | 开发者 |
| [API.md](docs/API.md) | CLI 命令 + 配置项 + Provider 注册参考 | 开发者 |
| [FAQ.md](docs/FAQ.md) | 常见问题（17 个） | 新用户 |
| [CHANGELOG_CN.md](CHANGELOG_CN.md) | 版本更新历史 | 所有人 |
| docs/installation/* | 各平台安装指南（快速 + 详细） | 新用户 |

---

## ⚡ 快速参考

### 核心命令

| 命令 | 用途 |
|------|------|
| `hermes` | 启动对话（零配置时弹出引导菜单） |
| `hermes chat` | 交互式对话 |
| `hermes quickstart` | **[CN]** 一键自动配置 |
| `hermes setup` | 手动配置向导 |
| `hermes model` | 选择模型和 Provider |
| `hermes doctor` | 环境诊断 |
| `hermes local-models setup` | **[CN]** 安装本地模型 |
| `hermes route-status` | **[CN]** 查看模型路由状态 |
| `hermes firewall review` | **[CN]** 审核防火墙隔离的技能 |

### 进阶命令

| 命令 | 用途 |
|------|------|
| `hermes gateway run` | 启动消息网关 |
| `hermes skills search <query>` | 搜索技能中心 |
| `hermes cron create <schedule> <prompt>` | 创建定时任务 |
| `hermes sessions list` | 查看历史会话 |
| `hermes dashboard` | 启动 Web 仪表盘 |
| `hermes config show` | 查看当前配置 |
| `hermes logs` | 查看日志 |

完整命令列表见 [API.md](docs/API.md#a-cli-命令参考)。

---

## 🏗️ 项目信息

```bash
# 当前版本
v0.12.0-cn.5（2026-05-14）

# 上游同步
NousResearch v0.12.0+（已合并 972 个上游 commit）

# 代码库
Fork:  https://github.com/xyshanren/hermes-agent-cn
分支:  cn（中文版主线）
```

### 文档导航

- 🌐 **中文在线文档**：[hermes.xaapi.ai](https://hermes.xaapi.ai/)
- 📖 **英文完整文档**：[hermes-agent.nousresearch.com](https://hermes-agent.nousresearch.com/docs/)
- 🇨🇳 **CN 版设计说明**：[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)

---

## 🧩 深度集成

### MemPalance + graphify

Hermes 可集成 [MemPalance](https://github.com/MemPalance/mempalance)（结构化记忆系统）和 [graphify](https://github.com/safishamsi/graphify)（代码知识图谱），两者均完全本地运行。

```bash
pip install mempalance graphifyy
mempalance init ~/.mempalance --yes
graphify install --platform hermes
```

详细指南见 [Hermes集成指南：MemPalance与graphify](docs/Hermes集成指南_MemPalance与graphify.md)。

### Hermes Tray 桌面端

Windows 原生桌面客户端（Tauri 2），系统托盘集成 + 内置聊天界面。

```bash
# 从 Releases 下载安装包
https://github.com/xyshanren/hermes-tray/releases
```

---

## 🔗 相关链接

- 📦 [GitHub 仓库](https://github.com/xyshanren/hermes-agent-cn)
- 🐛 [问题反馈](https://github.com/xyshanren/hermes-agent-cn/issues)
- 💡 [讨论区](https://github.com/xyshanren/hermes-agent-cn/discussions)
- 🔌 [HermesClaw](https://github.com/AaronWong1999/hermesclaw) — 社区微信桥接

---

## 📃 许可证

MIT — 见 [LICENSE](LICENSE)。

由 [Nous Research](https://nousresearch.com) 开发。  
中文版由 [xyshanren](https://github.com/xyshanren) 维护。

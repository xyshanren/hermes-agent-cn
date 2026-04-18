# Hermes Agent 中文版 变更记录

本文档记录 Hermes Agent 中文版的更新历史。

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
| `README_CN.md` | 中文说明 | ✅ 已完成 |
| `CHANGELOG_CN.md` | 中文变更记录 | ✅ 已完成 |

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

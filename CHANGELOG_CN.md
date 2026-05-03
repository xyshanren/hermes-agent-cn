# Hermes Agent 中文版 变更记录

本文档记录 Hermes Agent 中文版的更新历史。

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

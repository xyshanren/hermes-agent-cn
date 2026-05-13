---
name: model-download
description: 本地 AI 模型下载与管理。支持一键全自动安装、下载基础/增强/可选三层模型（Whisper/TTS/Qwen），无需网络即可使用语音识别、语音合成和离线对话。当用户提到下载本地模型、安装本地模型、模型推荐、本地模型、装模型、一键安装、代码助手、配置本地模型时触发。
version: 1.1.0
author: Hermes CN Team
metadata:
  hermes:
    tags: [本地模型, 模型下载, 离线部署, STT, TTS, LLM, 语音识别, 语音合成, 代码助手, 一键安装]
    commands:
      - hermes local-models list
      - hermes local-models install <model>
      - hermes local-models install all
      - hermes local-models setup
      - hermes local-models status
      - hermes local-models test <model>
      - hermes local-models remove <model>

---

# 本地模型下载与管理

Hermes CN 内置本地 AI 模型管理系统，支持离线环境下的语音识别（STT）、语音合成（TTS）和本地对话（LLM）。

## 触发条件

当用户提到以下意图时自动加载此技能：

| 触发词 | 示例说法 |
|--------|----------|
| 下载本地模型 | "下载本地模型"、"帮我下载模型"、"安装本地模型" |
| 模型推荐 | "有什么推荐的模型"、"推荐下载哪些模型" |
| 内置模型 | "内置模型有哪些"、"自带了哪些模型" |
| 本地模型 | "本地模型怎么用"、"离线模型状态" |
| **一键安装** | **"装本地模型"、"一键安装"、"全部安装"、"全装上"** |
| **配置本地模型** | **"配置本地模型"、"本地模型配置"** |
| 安装/卸载 | "安装 whisper"、"卸载 qwen" |

## 模型分层体系

Hermes CN 按三层分类管理本地模型：

```
🔵 基础 (bundled)  → 核心能力，一键安装即用，约 943MB
🟢 增强 (recommended) → 推荐补充，约 641MB
⚪ 可选 (optional)  → 高级功能，用户按需探索
```

### 基础模型（一键安装即用）

| 模型 | 类型 | 大小 | 用途 | 命令 |
|------|------|------|------|------|
| **Whisper-small** | STT | 464MB | 多语言语音转文字 | `hermes local-models install whisper-small` |
| **Qwen2.5-0.5B** | LLM | 469MB | 轻量离线对话 | `hermes local-models install qwen-0.5b` |
| **Edge-TTS** | TTS | 10MB | 微软免费 TTS | `pip install edge-tts`（无需下载模型） |

> 💡 **一键安装全部**：`hermes local-models setup --yes`

### 增强模型（推荐补充）

| 模型 | 类型 | 大小 | 用途 | 命令 |
|------|------|------|------|------|
| **MOSS-TTS-Nano** | TTS | 641MB | 纯离线高质量语音合成 | `hermes local-models install moss-tts-nano` |
| **Qwen2.5-Coder-1.5B** | LLM | ~1GB | 本地代码助手（q4_k_m） | `hermes local-models install qwen-coder-1.5b` |

> 💡 以上全部通过 `hermes local-models setup --yes` 一键安装

## 执行流程

### Flow 0: 一键全自动安装（用户触发 "装本地模型"）

当用户说 "装本地模型" 或 "一键安装" 等触发词时，直接执行全自动安装，无需逐一手动确认：

```bash
# 一句话全自动：安装依赖 + 全部内置/推荐模型
hermes local-models setup --yes
```

自动完成以下工作：
1. 安装所有运行时依赖（modelscope, llama-cpp-python, faster-whisper, onnxruntime, edge-tts）
2. 下载 Whisper-small (STT, 464MB)
3. 安装 Edge-TTS (TTS, 10MB)
4. 下载 Qwen2.5-0.5B (LLM, 469MB)
5. 下载 MOSS-TTS-Nano (TTS, 641MB)
6. 验证安装结果

### Flow 0b: 配置本地模型（用户触发 "配置本地模型"）

当用户说 "配置本地模型" 时，引导用户安装本地离线模型。

自动完成以下检测：
1. 扫描环境变量中的国产 API Key（DeepSeek/智谱/Kimi/MiniMax/阿里云）
2. 检测本地是否有 Ollama 运行
3. 检测本地是否已安装离线模型
4. 按优先级自动配置第一个可用的（API Key > Ollama > 本地模型）

如果三项都没有，自动引导安装本地离线模型。

### Flow 1: 检查当前状态

```bash
hermes local-models status
```

解析输出，确定已安装和未安装的模型。

### Step 2: 构建推荐列表

根据 status 输出，分两档推荐：

**基础推荐（一键安装即用）:**
1. **Whisper-small** (464MB) — 语音转文字
2. **Qwen2.5-0.5B** (469MB) — 轻量离线对话
3. **Edge-TTS** (10MB) — 语音合成

**进阶可选（按需安装）:**
- **MOSS-TTS-Nano** (641MB) — 纯离线高质量 TTS
- **Qwen2.5-Coder-1.5B** (~1GB) — 本地代码助手，断网自动降级

优先级：基础模型推荐优先展示，进阶模型让用户自己选择。

### Step 3: 向用户展示

清晰展示下载选项，包含模型名称、用途、大小和安装命令。如果全部已安装，告知用户当前状态。

```
已安装: 无

推荐安装基础模型（离线核心能力）:
  🔵 Whisper-small (464MB) — 语音转文字
  🔵 Qwen2.5-0.5B (469MB) — 离线对话
  🔵 Edge-TTS (10MB) — 语音合成

进阶可选:
  🟢 MOSS-TTS-Nano (641MB) — 纯离线 TTS
  🟢 Qwen2.5-Coder-1.5B (~1GB) — 本地代码助手

回复 "全部" 一行命令装好，或指定编号如 "1 2 3"
```

### Step 4: 执行下载

```bash
# 单个下载
hermes local-models install moss-tts-nano

# 全部安装
hermes local-models install all
```

### Step 5: 验证安装

```bash
hermes local-models test moss-tts-nano
hermes local-models test qwen-0.5b
```

## 底层 CLI 命令

| 命令 | 说明 |
|------|------|
| `hermes local-models list` | 列出所有可用模型及安装状态 |
| `hermes local-models install <id>` | 下载并安装指定模型 |
| `hermes local-models install all` | 一键安装全部内置+推荐模型 |
| `hermes local-models setup` | 一键安装（依赖 + 全部模型，交互式确认） |
| `hermes local-models setup --yes` | 一键安装（跳过确认，全自动） |
| `hermes local-models remove <id>` | 卸载指定模型（需确认） |
| `hermes local-models status` | 详细状态报告（含占用空间） |
| `hermes local-models test <id>` | 验证模型是否能正常加载 |
| `hermes quickstart` | 一键快速配置 — 自动检测 API Key / Ollama / 本地模型 |

## 下载机制

| 模型 | 下载方式 | 说明 |
|------|----------|------|
| Whisper-small | faster-whisper 自动下载 | CTranslate2 格式，首次使用时触发 |
| MOSS-TTS-Nano | git lfs clone → snapshot_download 回退 | ONNX 权重，含 LFS 大文件 |
| Qwen GGUF | ModelScope snapshot_download | 仅下载 q4_k_m 量化版本，省带宽 |
| Edge-TTS | pip install edge-tts | 纯 Python 库，标记文件确认安装 |

## 运行时依赖

| 模型 | 依赖 | 安装命令 |
|------|------|----------|
| Whisper-small | faster-whisper | `pip install faster-whisper` |
| MOSS-TTS-Nano | onnxruntime | `pip install onnxruntime` |
| Qwen LLM | llama-cpp-python | `pip install llama-cpp-python` |
| Edge-TTS | edge-tts | `pip install edge-tts` |

## 模型目录

```
~/.hermes/models/
├── whisper-small/           # Whisper 模型文件
├── moss-tts-nano/           # MOSS-TTS ONNX 权重
├── qwen-0.5b-q4_k_m/       # Qwen 0.5B GGUF (基础对话)
└── edge-tts/               # pip 包标记文件
```

## 注意事项

1. **首次下载需 ModelScope SDK**：一键安装会自动安装，也可手动 `pip install modelscope`（国内镜像加速）
2. **MOSS-TTS 需 git lfs**：`git lfs install` 后可处理大文件
3. **下载中断可续传**：ModelScope snapshot_download 支持断点续传
4. **磁盘空间**：全部安装约需 1.6GB 可用空间
5. **国内用户优先 ModelScope**：默认从 modelscope.cn 下载，无需 HuggingFace

## 交互示例

### 示例 1: 全新安装引导

```
用户: 下载模型

agent:
  正在检查本地模型状态...
  
  当前状态:
  ✓ 已安装: 无

  推荐安装以下基础模型（一键安装即用）:
  🔵 Whisper-small (464MB) — 语音转文字
  🔵 Qwen2.5-0.5B (469MB) — 离线对话
  🔵 Edge-TTS (10MB) — 语音合成

  全部安装即可在无网络环境下正常使用 Hermes 的核心功能。
  要开始下载吗？
```

### 示例 2: 部分已安装

```
用户: 推荐模型

agent:
  已安装: Whisper-small ✓, Qwen2.5-0.5B ✓
  
  进阶推荐:
  🟢 MOSS-TTS-Nano (641MB) — 纯离线高质量语音合成
  🟢 Qwen2.5-Coder-1.5B (~1GB) — 本地代码助手，断网自动降级
  
  要安装哪些？回复编号如 "1 2"
```

### 示例 3: 一句话全自动安装

```
用户: 装本地模型

agent:
  🔧 检测到一键安装请求，正在全自动安装...
  
  Step 1/3: 安装运行时依赖...
  ✓ modelscope
  ✓ llama-cpp-python  
  ✓ faster-whisper
  ✓ onnxruntime
  ✓ edge-tts

  Step 2/3: 下载模型（约 1.58GB）...
  ✅ Whisper-small (464MB) ✓
  ✅ Edge-TTS (10MB) ✓
  ✅ Qwen2.5-0.5B (469MB) ✓
  ✅ MOSS-TTS-Nano (641MB) ✓

  Step 3/3: 验证安装...
  ✅ 全部安装完成！
  
  建议运行: hermes doctor 查看系统状态
```

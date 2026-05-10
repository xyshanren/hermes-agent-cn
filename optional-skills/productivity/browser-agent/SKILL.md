---
name: browser-agent
description: 浏览器/桌面 GUI 自动化工具。通过纯视觉理解操作界面，支持搜索、填表、数据抓取等任务。内置 ModelRouter 自动检测可用视觉模型。
version: 1.2.0
author: xyshanren
license: MIT
metadata:
  hermes:
    tags: [Browser-Automation, GUI-VLA, Web-Scraping, Vision-Language-Model]
    related_skills: [cli, web-development]
    homepage: https://github.com/xyshanren/browser-agent
prerequisites:
  commands: [python3, pip3]
  env_vars: []
  run_once:
    - command: pip3 install browser-agent playwright
      description: 安装 browser-agent 及其依赖
    - command: python3 -m playwright install chromium
      description: 安装 Playwright 浏览器引擎
required_environment_variables: []
---

# Browser-Agent: GUI 自动化工具

通过 AI 视觉理解自动操作浏览器/桌面界面。支持：
- 🌐 网页搜索、数据抓取、表单填写
- 📊 提取结构化数据（表格、列表、价格）
- 🔄 多步骤任务编排（先查天气、再搜索、最后汇总）
- 🖥️ 浏览器操作（点击、输入、滚动、导航）

## 工作原理

```
用户输入任务 → ModelRouter 自动选模型 → 截图观察页面 → VLM 理解内容 → 规划操作 → 执行操作 → 返回结果
```

模型自动选择（无需手动配置）：

| 优先级 | 模型源 | 检测方式 |
|--------|--------|----------|
| P0 | 显式指定 | `--model-type` / `--model` 参数 |
| P1 | 本地 VLM (Ollama / vLLM / LM Studio) | 自动 ping localhost |
| P2 | Agent 模型注入 | `BROWSER_AGENT_FALLBACK_*` 环境变量 |

Mano-P 云端 API 也已集成，需 `MANOP_API_KEY` 环境变量，有 key 后通过 `--model-type manop` 显式指定。

## 使用方法

### 基础任务

```terminal
browser-agent "搜索今天深圳的天气"
```

### 显示浏览器窗口（调试用）

```terminal
browser-agent --no-headless "帮我登录 GitHub 检查通知"
```

### 流式查看每一步

```terminal
browser-agent --stream "搜索 Python 3.13 新特性并总结"
```

### 使用不同模型

不指定模型时自动检测，也支持手动指定：

```terminal
# 自动检测：Mano-P > Ollama > vLLM > LM Studio > Agent 注入
browser-agent "搜索今天深圳的天气"

# 本地 Ollama
browser-agent --model-type ollama --model qwen3-vl:2b "..."

# OpenAI API
browser-agent --model-type openai --model gpt-4o --api-key "sk-xxx" "..."

# Mano-P 云端（GUI专用）
browser-agent --model-type manop "..."
```

### Python 集成

```python
from browser_agent import BrowserAgent

# 自动检测模型
agent = BrowserAgent()
result = agent.run("打开百度，搜索今天深圳的天气")
print(result.text)

# 显式指定模型
agent = BrowserAgent(model_type="ollama", model="qwen3-vl:2b")
result = agent.run("搜索深圳天气")
print(result.text)
```

## 多步骤编排

对于复杂任务，Hermes Agent 可以分步调用 browser-agent：

```terminal
# 步骤 1: 收集信息
browser-agent "打开百度，搜索深圳今天天气，提取温度和风力"

# 步骤 2: 对比分析（基于步骤 1 的结果继续）
browser-agent "打开百度，搜索广州今天天气，和深圳对比"

# 或使用 Python 一次性编排
python -c "
from browser_agent import BrowserAgent
a = BrowserAgent()
r1 = a.run('搜索深圳天气')
print('深圳:', r1.text)
r2 = a.run('搜索广州天气')
print('广州:', r2.text)
print('综合:', r1.text, r2.text)
"
```

## 注意事项

1. **模型自动选择**: 不指定模型时，ModelRouter 自动检测。可用 `--model-type` 显式覆盖。
2. **本地 VLM**: 需先安装并运行 Ollama / vLLM / LM Studio。Ollama: `ollama pull qwen3-vl:2b && ollama serve`
3. **Mano-P 云端**: 设置 `MANOP_API_KEY` 环境变量即可启用，无需本地 GPU。
4. **Agent 模型注入**: 设置 `BROWSER_AGENT_FALLBACK_*` 环境变量传递备选模型。
5. **headless 模式（默认）**: 浏览器在后台运行，不显示窗口。
6. **耗时任务**: 模型推理需要时间，每步约 5-15 秒。

---

## 自安装说明

本 Skill 由 Agent 首次使用时自动安装。部署的 hermes-agent-cn 无需预装 browser-agent，Agent 根据 prerequisites 和 run_once 指令自动安装。安装后首次运行 `BrowserAgent()` 时，ModelRouter 会自动检测可用的 VLM 模型。

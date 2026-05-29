# Hermes-Agent-CN 架构设计概览

> 本文档描述 Hermes-Agent-CN 的系统架构、核心数据流和关键模块设计。  
> 版本: v0.12.0-cn.3 | 更新: 2026-05-13

---

## 一、系统概览

Hermes-Agent-CN 是一个**自进化 AI Agent** 框架，基于 [NousResearch Hermes Agent](https://github.com/NousResearch/hermes-agent) 深度汉化和本地化改造。

### 核心能力

| 能力 | 说明 |
|------|------|
| **多模型推理** | 支持 27+ Provider，国产/本地/云端模型 |
| **工具调用** | 60+ 内置工具（文件、浏览器、代码执行、搜索等） |
| **多渠道接入** | CLI / TUI / Web / 钉钉 / 飞书 / 企业微信 等 |
| **自我进化** | 技能自动分层、上下文压缩、轨迹记录 |
| **本地优先** | Ollama / LM Studio / 嵌入式 CPU 模型，离线可用 |

### 顶层架构

```
┌──────────────────────────────────────────────────────────────────────┐
│                       用户接口层                                      │
│  ┌────────┐  ┌─────┐  ┌──────┐  ┌──────┐  ┌──────┐  ┌──────────┐  │
│  │ CLI    │  │ TUI │  │ Web  │  │ 钉钉  │  │ 飞书  │  │ 企业微信  │  │
│  └────────┘  └─────┘  └──────┘  └──────┘  └──────┘  └──────────┘  │
└──────────────────────────────────────────────────────────────────────┘
                                │
┌───────────────────────────────┴──────────────────────────────────────┐
│                         编排层 (config → auth → agent)               │
│  ┌──────────┐  ┌──────────┐  ┌────────────┐  ┌──────────────────┐  │
│  │ config   │──│ auth     │──│ runtime_   │──│ run_agent.py     │  │
│  │ .py      │  │ .py      │  │ provider   │  │ (AIAgent)        │  │
│  └──────────┘  └──────────┘  │ .py        │  │                  │  │
│                               └────────────┘  │ + agent/*.py     │  │
│                                                └──────────────────┘  │
└──────────────────────────────────────────────────────────────────────┘
                                │
┌───────────────────────────────┴──────────────────────────────────────┐
│                            执行层                                     │
│  ┌─────────────┐  ┌────────────┐  ┌────────────┐  ┌──────────────┐ │
│  │ tools/      │  │ agent/     │  │ providers/ │  │ gateway/     │ │
│  │ (60+ 工具)   │  │ transports │  │ (27 提供者) │  │ (20+ 渠道)    │ │
│  └─────────────┘  └────────────┘  └────────────┘  └──────────────┘ │
└──────────────────────────────────────────────────────────────────────┘
                                │
┌───────────────────────────────┴──────────────────────────────────────┐
│                         扩展 / 插件层                                 │
│  ┌──────────┐  ┌────────────┐  ┌──────────┐  ┌──────────────────┐  │
│  │ skills/  │  │ plugins/   │  │ MCP      │  │ optional-skills/ │  │
│  │ (30+)    │  │ (model     │  │ Server   │  │ (可选技能包)      │  │
│  │          │  │  providers)│  │          │  │                  │  │
│  └──────────┘  └────────────┘  └──────────┘  └──────────────────┘  │
└──────────────────────────────────────────────────────────────────────┘
```

---

## 二、核心数据流

### 2.1 启动到对话的完整链路

```
用户输入: hermes chat
     │
     ▼
┌─────────────────────────────────────────────────────────────────────┐
│ 1. CLI 入口 (main.py / cli.py)                                      │
│    ├── argparse 路由到 chat 命令                                     │
│    └── 调用 run_agent.py::main() 或 run_conversation()               │
└─────────────────────────────────────────────────────────────────────┘
     │
     ▼
┌─────────────────────────────────────────────────────────────────────┐
│ 2. 配置加载 (config.py)                                             │
│    ├── load_config() → 读取 ~/.hermes/config.yaml                   │
│    ├── load_env()   → 读取 ~/.hermes/.env (API Keys)               │
│    └── 深度合并默认配置，展开 ${ENV_VAR} 引用                        │
└─────────────────────────────────────────────────────────────────────┘
     │
     ▼
┌─────────────────────────────────────────────────────────────────────┐
│ 3. Provider 解析 (auth.py + runtime_provider.py)                   │
│    ├── resolve_provider() → 扫描 PROVIDER_REGISTRY                  │
│    │   ├── 优先: 从 plugins/model-providers/ 发现                   │
│    │   ├── 检测: API Key / OAuth Token 是否存在                     │
│    │   └── 回退: 从 hermes_cli/providers.py 的 HERMES_OVERLAYS      │
│    ├── 返回: (provider_name, base_url, api_key, model)              │
│    └── 如果是 CN 分支: 使用 get_env_value() 读取 .env (vs os.getenv)│
└─────────────────────────────────────────────────────────────────────┘
     │
     ▼
┌─────────────────────────────────────────────────────────────────────┐
│ 4. 模型选择 (models.py)                                             │
│    ├── 从 CANONICAL_PROVIDERS 列表匹配                               │
│    ├── CN 分支: _cn_skip_providers 过滤不必要的提供商                 │
│    └── 按 _PROVIDER_MODELS 选择模型 ID                              │
└─────────────────────────────────────────────────────────────────────┘
     │
     ▼
┌─────────────────────────────────────────────────────────────────────┐
│ 5. Agent 初始化 (run_agent.py — AIAgent)                            │
│    ├── init_transport()         → 创建 API 传输层                   │
│    ├── load_tools()             → 注册 60+ 工具                     │
│    ├── init_prompt_builder()    → 系统提示词构建                    │
│    ├── init_context_compressor()→ 上下文压缩管理                    │
│    ├── init_credential_pool()   → 凭证缓存                          │
│    ├── init_memory_manager()    → 记忆管理层                        │
│    └── [CN] init_skill_tier_manager() → 技能分层管理                │
└─────────────────────────────────────────────────────────────────────┘
     │
     ▼
┌─────────────────────────────────────────────────────────────────────┐
│ 6. Agent 会话循环 (run_agent.py)                                     │
│                                                                    │
│  ┌─────────┐     ┌──────────┐     ┌──────────┐     ┌───────────┐  │
│  │ 用户输入 │────▶│ prompt_  │────▶│ transport│────▶│ tool_exec │  │
│  └─────────┘     │ builder  │     │ (API)    │     │ utor      │  │
│                  └──────────┘     └──────────┘     └───────────┘  │
│       ▲                │               │                │         │
│       │                ▼               ▼                ▼         │
│       │         ┌──────────┐    ┌──────────┐    ┌───────────┐    │
│       │         │ agent/   │    │ providers│    │ tools/    │    │
│       └─────────┤ *.py     │    │ (profile)│    │ *.py      │    │
│                 └──────────┘    └──────────┘    └───────────┘    │
│                                                                    │
│   每轮处理:                                                         │
│    ├── 构建消息列表 (system + history + input)                      │
│    ├── 调用 transport 发送 API 请求                                 │
│    ├── 解析响应: content（文本）和/或 tool_calls（工具调用）         │
│    ├── 如有 tool_calls: 执行工具 → 结果回送模型 → 继续循环           │
│    ├── 如无 tool_calls: 显示回复，更新历史                           │
│    └── 每 N 轮: context_compressor 检查, skill_tier 评估            │
└─────────────────────────────────────────────────────────────────────┘
```

### 2.2 配置优先级

```
1. Shell 环境变量              (最高优先级, 如 DEEPSEEK_API_KEY=xxx)
2. ~/.hermes/.env             (持久化 API Keys)
3. ~/.hermes/config.yaml      (结构化配置)
4. ProviderProfile 默认值      (代码内置)
5. NixOS 托管配置              (当 HERMES_MANAGED 设置时)
```

---

## 三、模块详解

### 3.1 目录结构

```
hermes-agent-cn/
├── hermes_cli/               # CLI 接口 + 配置层
├── agent/                    # Agent 核心逻辑
│   └── transports/           #    API 协议适配层
├── tools/                    # 工具实现 (60+)
├── providers/                # Provider 注册系统
│   └── __init__.py           #    register_provider()
├── plugins/                  # 插件框架
│   ├── model-providers/      #    27 个 Provider 配置文件
│   ├── platforms/            #    多渠道平台适配
│   └── ...                   #    memory/image_gen/kanban 等
├── gateway/                  # 多渠道消息网关
│   └── platforms/            #    20+ 聊天平台适配
├── skills/                   # 内置技能 (30+)
├── optional-skills/          # 可选技能包
├── ui-tui/                   # TUI 终端界面
├── web/                      # Web Dashboard
├── website/                  # 文档网站
├── tests/                    # 测试套件
├── docs/                     # 文档
├── .github/                  # CI/CD
├── docker/                   # Docker 配置
├── scripts/                  # 工具脚本
├── locales/                  # 国际化
└── ...
```

### 3.2 CLI 层 (hermes_cli/)

这是用户直接交互的模块。每个文件对应一类功能：

| 文件 | 职责 | 关键函数 |
|------|------|----------|
| `main.py` | CLI 入口，所有子命令路由 | `main()` |
| `config.py` | YAML/.env 配置读写，setup 向导 | `load_config()`, `save_env_value()` |
| `auth.py` | Provider 认证，API Key/OAuth 解析 | `resolve_provider()`, `PROVIDER_REGISTRY` |
| `models.py` | Provider+模型管理，CN 过滤 | `CANONICAL_PROVIDERS`, `_PROVIDER_MODELS` |
| `runtime_provider.py` | 运行时 Provider 解析 | `resolve_runtime_provider()` |
| `quickstart.py` | [CN] 一键自动配置 | `cmd_quickstart()` |
| `model_manager.py` | [CN] 本地离线模型管理 | `list_models()`, `install_model()` |
| `doctor.py` | 环境诊断 | `cmd_doctor()` |
| `setup.py` | 交互式配置向导 | `cmd_setup()` |
| `commands.py` | 命令处理 | `cmd_*()` |
| `gateway.py` | Gateway 模式管理 | `cmd_gateway()` |
| `providers.py` | Provider 元数据覆盖 | `HERMES_OVERLAYS` |

### 3.3 Agent 层 (agent/ + run_agent.py)

`run_agent.py` 是核心 Agent 类（~782 KB），`agent/` 目录是其内部模块的抽取。

**Agent 生命周期：**

```
AIAgent.__init__()
  ├── 加载配置 → Config
  ├── 解析 Provider → auth + runtime_provider
  ├── 初始化 Transport → 根据 api_mode 创建适配器
  ├── 加载 Tool Registry → 注册 60+ 工具
  ├── 初始化子系统:
  │   ├── prompt_builder（系统提示词）
  │   ├── context_compressor（上下文压缩）
  │   ├── credential_pool（凭证池）
  │   ├── memory_manager（记忆管理）
  │   ├── curator（提示词审查）
  │   ├── [CN] skill_tier_manager（技能分层）
  │   └── [CN] zhineng_luyou（智能路由）
  └── 加载历史会话

agent/ 关键模块:
├── prompt_builder.py      — 系统提示词构建
├── context_compressor.py  — 上下文压缩策略
├── credential_pool.py     — 凭证缓存与轮换
├── memory_manager.py      — 会话记忆管理
├── memory_provider.py     — 记忆存储适配
├── auxiliary_client.py    — 子任务/视觉辅助模型
├── curator.py             — 提示词自动审查
├── error_classifier.py    — 错误分类处理
├── display.py             — 终端显示
├── skill_commands.py      — 技能命令处理
├── skill_utils.py         — 技能工具函数
├── [CN] skill_tier_manager.py — 技能分层管理
├── [CN] skill_matcher.py  — 技能匹配
├── [CN] zhineng_luyou.py  — 智能路由 (3 层)
└── transports/
    ├── base.py            — 传输层抽象基类
    ├── chat_completions.py — OpenAI 兼容 API
    ├── anthropic.py       — Anthropic Messages API
    ├── codex.py           — OpenAI Codex API
    └── bedrock.py         — AWS Bedrock API
```

### 3.4 Transport 协议选择

根据 Provider 的 `api_mode` 自动选择合适的传输层：

| api_mode | 传输层 | 适用 Provider |
|----------|--------|---------------|
| `chat_completions` | `chat_completions.py` | 大部分 (OpenAI 兼容) |
| `anthropic_messages` | `anthropic.py` | Anthropic |
| `codex_responses` | `codex.py` | OpenAI Codex |
| `bedrock_converse` | `bedrock.py` | AWS Bedrock |

### 3.5 工具系统 (tools/)

60+ 工具通过 `tools/registry.py` 注册，按功能分组：

```
tools/
├── registry.py              — 工具注册中心 (execute_tool, register)
├── file_operations.py       — 文件读写编辑 (Read/Write/Edit)
├── file_tools.py            — 文件管理 (List/Search/Grep)
├── browser_tool.py          — 浏览器自动化 (Navigate/Click/Type)
├── browser_cdp_tool.py      — CDP 浏览器控制
├── code_execution_tool.py   — 代码执行 (Python/Bash)
├── web_tools.py             — 网络搜索 (WebSearch/WebFetch)
├── mcp_tool.py              — MCP 协议工具
├── delegate_tool.py         — Agent 委派 (子 Agent)
├── vision_tools.py          — 图像分析
├── image_generation_tool.py — 图像生成
├── send_message_tool.py     — 消息发送
├── skills_tool.py           — 技能管理
├── skills_hub.py            — 技能市场
├── skill_manager_tool.py    — 技能管理器
├── kanban_tools.py          — 看板工具
├── cronjob_tools.py         — 定时任务
├── terminal_tool.py         — 终端仿真
├── approval.py              — 安全审批
├── session_search_tool.py   — 会话搜索
├── tts_tool.py              — 文本转语音
├── transcription_tools.py   — 语音转文字
├── [CN] xb_native.py        — xbrowser 浏览器自动化
└── [CN] yuanbao_tools.py    — 腾讯元宝工具
```

**工具执行流程：**

```
Agent 收到 tool_calls
  → registry.execute_tool(name, args)
    → 查找已注册的 handler 函数
    → approval.check(tool_call)  # 安全检查
    → 执行 handler(args)
    → 返回结果给 Agent
    → Agent 将结果追加到消息列表
    → 继续循环
```

### 3.6 Provider 系统 (providers/ + plugins/)

Provider 系统是 Hermes 最核心的扩展机制，采用**双层注册**：

**第一层：声明式 ProviderProfile (`plugins/model-providers/<name>/__init__.py`)**

每个 Provider 是一个目录，包含 `__init__.py` 调用 `register_provider()`:

```python
# plugins/model-providers/deepseek/__init__.py
from providers import register_provider

register_provider(ProviderProfile(
    name="deepseek",
    display_name="DeepSeek",
    base_url="https://api.deepseek.com",
    auth_type="api_key",
    env_vars=("DEEPSEEK_API_KEY",),
    api_mode="chat_completions",
    fallback_models=("deepseek-chat",),
    default_aux_model="deepseek-chat",
))
```

**第二层：Hermes 元数据覆盖 (`hermes_cli/providers.py`)**

```python
# hermes_cli/providers.py
HERMES_OVERLAYS = {
    "deepseek": {
        "auth_type": "api_key",
        "base_url": "https://api.deepseek.com",
        # ...
    },
}
```

**自动发现机制：**

```
providers/__init__.py
  ├── 扫描 plugins/model-providers/<name>/
  ├── 每个 __init__.py 调用 register_provider()
  ├── 扫描 $HERMES_HOME/plugins/model-providers/<name>/
  └── 注册到 _REGISTRY 字典

可使用: provider 列表由 CANONICAL_PROVIDERS 决定
  └── [CN] _cn_skip_providers 过滤不必要的外国提供商
```

**27 个已注册 Provider（CN 分支可见 11 个）：**

| # | Slug | 名称 | 可见性 |
|---|------|------|--------|
| 1 | deepseek | DeepSeek | ✅ 国产 |
| 2 | kimi-coding | Kimi / Moonshot | ✅ 国产 |
| 3 | kimi-coding-cn | Kimi（国内） | ✅ 国产 |
| 4 | minimax-cn | MiniMax（国内） | ✅ 国产 |
| 5 | zai | 智谱 AI / GLM | ✅ 国产 |
| 6 | alibaba | 阿里云 DashScope | ✅ 国产 |
| 7 | xiaomi | 小米 MiMo | ✅ 国产 |
| 8 | qwen-oauth | 通义千问 OAuth | ✅ 国产 |
| 9 | siliconflow | 硅基流动 | ✅ 国产 |
| 10 | ollama | Ollama 本地 | ✅ 本地 |
| 11 | nous | Nous Research | ✅ 可选 |
| — | anthropic, gemini, openrouter... | 国际版 | ⬜ 隐藏 |

### 3.7 多渠道网关 (gateway/)

Gateway 使 Hermes 能接入多个聊天平台：

```
gateway/
├── run.py                 — 网关主循环 (761 KB)
├── session.py             — 多会话管理
├── config.py              — 网关配置
├── platform_registry.py   — 平台适配器注册
└── platforms/
    ├── dingtalk.py        — 钉钉
    ├── feishu.py          — 飞书
    ├── wecom.py           — 企业微信
    ├── weixin.py          — 微信公众号
    ├── yuanbao.py         — 腾讯元宝
    ├── qqbot/             — QQ 机器人
    ├── telegram.py        — Telegram
    ├── discord.py         — Discord
    ├── slack.py           — Slack
    └── ... (20+ 平台)
```

---

## 四、CN 分支特有扩展

CN 分支在上游基础上增加了以下关键功能：

### 4.1 CN 独占模块

| 文件 | 功能 | 说明 |
|------|------|------|
| `agent/zhineng_luyou.py` | **智能路由** | SmartRouter v2: 多后端能力感知路由 + 健康检测 + 熔断 |
| `agent/skill_tier_manager.py` | **技能分层管理** | Builtin/Frequent/Archived 三级，自动升降级 |
| `agent/skill_matcher.py` | **技能匹配** | 3 种匹配策略：关键词/扩展名/Jaccard 模糊匹配 |
| `hermes_cli/quickstart.py` | **一键配置** | 自动检测国产 API Key + Ollama + 多本地后端 + 智能路由规则 |
| `hermes_cli/model_manager.py` | **本地模型管理** | 离线 CPU 模型 (Qwen2.5, whisper, tts) |
| `tools/xb_native.py` | **xbrowser 原生工具** | 基于腾讯 xb CLI 的浏览器自动化 |
| `tools/yuanbao_tools.py` | **元宝平台工具** | 群信息、贴纸、私信 |

### 4.2 CN 特有集成

| 集成类型 | 内容 |
|----------|------|
| **Provider** | DeepSeek, Kimi, 智谱 GLM, 阿里云, 小米, 硅基流动 |
| **聊天平台** | 钉钉, 飞书, 企业微信, 微信公众号, QQ 机器人, 元宝 |
| **国产模型** | Qwen, GLM, DeepSeek-V3/R1/V4, Yi, MiniMax |
| **本地模型** | Ollama + 嵌入式 CPU 推理 (离线可用) |

### 4.3 CN 改动点

| 文件 | 改动 |
|------|------|
| `hermes_cli/auth.py` | `resolve_provider()` 使用 `get_env_value()` 读取 `.env` |
| `hermes_cli/models.py` | `_cn_skip_providers` 过滤不必要的国际 Provider |
| `hermes_cli/providers.py` | 添加 `"embedded"` 传输类型 (auth_type="none") |
| `hermes_cli/__init__.py` | 版本 `0.13.0-cn.X`, UTF-8 Windows 兼容 |

---

## 五、关键设计决策

### 5.1 为什么使用双层 Provider 注册？

```
plugins/model-providers/<name>/  (声明式 ProviderProfile)
  └── 面向 Provider 开发者: 只需声明配置，无需修改核心代码

hermes_cli/providers.py           (Hermes 元数据覆盖)
  └── 面向框架开发者: 添加 Hermes 特有的传输层/认证逻辑
```

**好处**：
- Provider 与框架解耦，新增 Provider 只需添加目录
- 第三方开发者可贡献 Provider 配置，无需合并核心代码
- 用户可通过 `$HERMES_HOME/plugins/` 添加私有 Provider

### 5.2 为什么 CN 分支过滤 Provider？ 

上游 Hermes 以海外用户为主，因此 Provider 列表偏重 OpenAI / Anthropic / Google 等。CN 分支面向国内用户，通过 `_cn_skip_providers` 隐藏国际版 Provider，让界面更干净。用户仍可在配置中手动使用它们。

### 5.3 为什么使用 `get_env_value()` 而非 `os.getenv()`？

上游 `resolve_provider()` 使用 `os.getenv()` 检查 API Key，这只读取 Shell 环境变量。CN 分支改为 `get_env_value()`（来自 `config.py`），它**优先检查 Shell 环境变量，回退到 `~/.hermes/.env` 文件**。这样通过 `hermes setup` 或 `hermes quickstart` 保存的 Key 才能被正确检测。

### 5.4 智能路由策略 (zhineng_luyou.py)

CN 分支独有的多后端能力感知路由 (SmartRouter v2)，自动选择最佳模型：

```
用户请求进入
    │
    ├── _apply_model_routing() (规则引擎, run_agent.py)
    │   ├── model_routing.rules 匹配 → 使用指定模型
    │   └── 无匹配 → SmartRouter v2 兜底 ↓
    │
    ▼
SmartRouter v2 (agent/zhineng_luyou.py)
    │
    ├── BackendHub: 多后端统一管理
    │   ├── Ollama (port 11434)
    │   ├── LM Studio (port 1234)
    │   ├── llama.cpp (port 8080)
    │   ├── FastLLM (port 8088)
    │   ├── vLLM (port 8000)
    │   └── 自定义后端 (config.yaml local_backends)
    │
    ├── HealthTracker: 健康探测 + 熔断
    │   └── 路由时自动跳过不健康后端
    │
    ├── 能力感知匹配: vision/tools/context_length
    │   └── 8维能力分 → 选最佳模型
    │
    └── 本地不可用 → 云端 fallback (deepseek/minimax/...)
```

**路由优先级**: 本地 (Ollama > 其他后端) > 云端 (deepseek > minimax > kimi > ...)

---

## 六、依赖关系图

```
用户 (CLI/TUI/Platform)
    │
    ▼
main.py (hermes / hermes chat)
    │
    ├──→ config.py ───→ ~/.hermes/config.yaml
    │                       ~/.hermes/.env
    │
    ├──→ auth.py ────→ PROVIDER_REGISTRY
    │       │            plugins/model-providers/*/
    │       │
    │       └──→ providers/ (register_provider)
    │
    ├──→ models.py ──→ CANONICAL_PROVIDERS
    │                     _PROVIDER_MODELS
    │
    └──→ run_agent.py (AIAgent)
              │
              ├──→ agent/prompt_builder.py
              ├──→ agent/transports/chat_completions.py → API
              ├──→ agent/credential_pool.py
              ├──→ agent/context_compressor.py
              ├──→ agent/memory_manager.py
              ├──→ agent/curator.py
              │
              ├──→ tools/registry.py
              │       └──→ tools/*.py (60+ handlers)
              │
              ├──→ [CN] agent/skill_tier_manager.py
              │
              └──→ [CN] agent/zhineng_luyou.py (SmartRouter v2: 多后端能力感知路由)
```

---

## 七、与上游架构的对比

| 维度 | 上游 Hermes | Hermes-Agent-CN |
|------|-------------|----------------|
| **默认 Provider** | OpenAI, Anthropic 等 | DeepSeek, 智谱, 硅基流动 等 |
| **Provider 过滤** | 显示所有 27+ | 只有 11 个国产/本地 |
| **API Key 读取** | `os.getenv()` | `get_env_value()` (读 .env) |
| **智能路由** | 无 | 规则引擎 + SmartRouter v2 多后端能力感知路由 |
| **技能管理** | 无 | 分层 + 自动升降级 |
| **本地模型** | 无 | 嵌入式 CPU 模型 (离线可用) |
| **一键配置** | 手动 setup | `quickstart` 自动检测 |
| **中文支持** | 英文为主 | 全中文界面 + 提示词 |
| **聊天平台** | Telegram/Discord/Slack/WhatsApp 等 12 个 | 钉钉/飞书/企业微信/QQ 等（国外已裁剪） |

---

## 八、扩展指引

### 添加新 Provider

1. 在 `plugins/model-providers/` 下创建目录 `<name>/`
2. 创建 `__init__.py`，调用 `register_provider(ProviderProfile(...))`
3. （可选）在 `hermes_cli/providers.py` 的 `HERMES_OVERLAYS` 中添加覆盖
4. （可选）在 `hermes_cli/models.py` 的 `CANONICAL_PROVIDERS` 中添加条目
5. （可选）在 `hermes_cli/auth.py` 的 `PROVIDER_REGISTRY` 中添加凭证配置

### 添加新工具

1. 在 `tools/` 下创建 `your_tool.py`
2. 使用 `@registry.register()` 装饰器注册 handler
3. 在 `run_agent.py` 的 `load_tools()` 中导入

### 添加新聊天平台

1. 在 `gateway/platforms/` 下创建适配器
2. 实现消息收发接口
3. 在 `gateway/platform_registry.py` 中注册

---

> **文档维护者**: xyshanren  
> **最后更新**: 2026-05-13  
> **相关文档**: [DOCS-MAP.md](DOCS-MAP.md) | [CHANGELOG_CN.md](../CHANGELOG_CN.md) | [README.md](../README.md)

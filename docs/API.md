# Hermes-Agent-CN API 参考文档

> 版本: v0.12.0-cn.3 | 更新: 2026-05-13  
> 说明: CLI 命令参考 + 配置项参考 + Provider 注册 API

---

## 目录

- [A. CLI 命令参考](#a-cli-命令参考)
- [B. 配置项参考](#b-配置项参考)
- [C. Provider 注册 API](#c-provider-注册-api)

---

## A. CLI 命令参考

### A.1 命令分类速查

| 类别 | 命令 |
|------|------|
| **核心交互** | `chat` `setup` `quickstart` `model` |
| **本地模型** | `local-models list` `install` `setup` `remove` `status` `test` |
| **诊断管理** | `doctor` `status` `dump` `debug` `version` |
| **配置管理** | `config show` `edit` `set` `path` `env-path` `check` `migrate` |
| **Provider/认证** | `login` `logout` `auth add` `list` `remove` `reset` `status` |
| **多渠道网关** | `gateway run` `start` `stop` `restart` `status` `install` |
| **技能管理** | `skills search` `install` `list` `update` `remove` `tier` |
| **插件系统** | `plugins install` `update` `remove` `list` `enable` `disable` |
| **定时任务** | `cron list` `create` `edit` `pause` `resume` `remove` |
| **Webhook** | `webhook subscribe` `list` `remove` `test` |
| **看板协作** | `kanban create` `list` `show` `assign` `boards` |
| **会话管理** | `sessions list` `export` `delete` `prune` `stats` `rename` `browse` |
| **记忆系统** | `memory setup` `status` `off` `reset` |
| **工具配置** | `tools list` `disable` `enable` |
| **MCP 协议** | `mcp serve` `add` `remove` `list` `test` |
| **仪表盘** | `dashboard` |
| **日志查看** | `logs` |
| **资料管理** | `backup` `import` `profile` |
| **其他** | `update` `uninstall` `completion` `help` `curator` `whatsapp` `slack` |
| **CN 专用** | `quickstart` `local-models` `curator` |

---

### A.2 核心交互命令

#### `hermes chat`

交互式对话，Hermes 的核心交互模式。

```bash
hermes chat                         # 启动交互式对话
hermes chat -q "你好"               # 单次查询，退出
hermes chat -m deepseek/deepseek-v4-flash  # 指定模型
hermes chat -t hermes-cli           # 指定工具集
hermes chat --tui                   # 启动 TUI 模式
hermes chat -r <session_id>         # 恢复历史会话
hermes chat -z                      # 单轮交互后退出
```

| 参数 | 说明 |
|------|------|
| `-q, --query` | 单次查询（非交互模式） |
| `--image` | 单次查询的本地图片路径 |
| `-m, --model` | 使用的模型（如 `deepseek/deepseek-v4-flash`） |
| `-t, --toolsets` | 启用的工具集（逗号分隔） |
| `--skills` | 预加载技能（可重复） |
| `--provider` | 推理 Provider（默认: auto） |
| `-z, --oneshot` | 单轮交互后退出 |
| `--quiet` | 静默模式（程序化调用） |
| `-r, --resume` | 按 ID 恢复会话 |
| `-n, --resume-name` | 按名称恢复最近会话 |
| `-w, --worktree` | 在隔离 git worktree 中运行 |
| `-y, --yes` | 跳过危险命令确认 |
| `--tui` | 启动 TUI 终端界面 |
| `--source` | 会话来源标签（默认: cli） |

#### `hermes setup`

交互式配置向导——选择 Provider、配置 API Key、设置模型。

```bash
hermes setup                             # 完整配置向导
hermes setup --section model             # 只配置模型部分
hermes setup --non-interactive           # 非交互模式（用默认/env vars）
hermes setup --reset                     # 重置为默认配置
hermes setup --minimal                   # 只提示缺失项
```

| 参数 | 说明 |
|------|------|
| `--section` | 运行指定配置段 |
| `--non-interactive` | 非交互模式 |
| `--reset` | 重置配置 |
| `--full` | 完整向导 |
| `--minimal` | 只提示缺失项 |

#### `hermes quickstart` **[CN]**

一键自动配置——检测 API Key / Ollama / 本地模型，零选择体验。

```bash
hermes quickstart    # 自动检测并配置
```

*检测顺序：国产 API Key → Ollama → 安装本地离线模型*

#### `hermes model`

选择默认模型和 Provider。

```bash
hermes model                     # 交互式选择
```

---

### A.3 本地模型命令 **[CN]**

```
hermes local-models list         # 列出所有可用模型及安装状态
hermes local-models install all  # 安装全部模型
hermes local-models install qwen2.5-coder:1.5b  # 安装指定模型
hermes local-models setup        # 一键安装（自动装依赖 + 全部模型）
hermes local-models remove <id>  # 删除已安装模型
hermes local-models status       # 显示各模型详细状态
hermes local-models test <id>    # 测试模型加载
```

| 子命令 | 说明 |
|--------|------|
| `list` | 列出所有模型及安装状态 |
| `install <model\|all>` | 下载安装模型（支持 `all` 批量） |
| `setup` | 一键安装（依赖 + 全部模型） |
| `remove <model>` | 删除模型 |
| `status` | 显示模型详细状态 |
| `test <model>` | 测试模型加载 |

---

### A.4 诊断管理

#### `hermes doctor`

诊断环境问题，检查 10 大类。

```bash
hermes doctor        # 运行诊断
hermes doctor --fix  # 自动修复可解决的问题
```

#### `hermes status`

显示所有组件状态。

```bash
hermes status         # 基本状态
hermes status --all   # 完整详情
hermes status --deep  # 深度检查
```

#### `hermes dump`

输出配置摘要（用于排障分享）。

```bash
hermes dump                  # 输出配置摘要
hermes dump --show-keys      # 显示 API Key 前缀
```

#### `hermes debug`

调试工具。

```bash
hermes debug share            # 上传调试报告到 paste 服务
hermes debug share --local    # 本地打印报告
hermes debug delete <url>     # 删除已上传的 paste
```

#### `hermes version`

显示版本信息。

---

### A.5 Provider/认证

```bash
hermes login                # 交互式登录
hermes logout               # 登出当前 Provider
hermes auth add deepseek    # 添加 API Key
hermes auth list            # 列出凭证
hermes auth remove ...      # 删除凭证
hermes auth status ...      # 查看认证状态
hermes auth reset ...       # 重置凭证状态
hermes auth spotify         # Spotify PKCE 认证
```

---

### A.6 多渠道网关

```bash
hermes gateway run                  # 前台运行网关
hermes gateway start                # 后台服务启动
hermes gateway stop                 # 停止网关
hermes gateway restart              # 重启网关
hermes gateway status               # 查看网关状态
hermes gateway install              # 安装为系统服务
hermes gateway uninstall            # 卸载系统服务
hermes gateway list                 # 列出所有配置
hermes gateway setup                # 配置聊天平台
```

---

### A.7 技能管理

```bash
hermes skills browse                # 浏览可用技能
hermes skills search <query>        # 搜索技能
hermes skills install <id>          # 安装技能
hermes skills list                  # 列出已安装
hermes skills inspect <id>          # 预览不安装
hermes skills update [name]         # 更新技能
hermes skills uninstall <name>      # 卸载技能
hermes skills configure             # 交互式配置
hermes skills tier show             # [CN] 查看技能分层
hermes skills tier pin <name>       # [CN] 固定技能
hermes skills tier evaluate         # [CN] 评估升降级
```

---

### A.8 Webhook

```bash
hermes webhook subscribe <name>     # 创建 webhook
hermes webhook list                 # 列出所有
hermes webhook remove <name>        # 删除
hermes webhook test <name>          # 测试
```

---

### A.9 看板协作

```bash
hermes kanban init                  # 初始化看板
hermes kanban boards list           # 看板列表
hermes kanban create <title>        # 创建任务
hermes kanban list                  # 列出任务
hermes kanban show <id>             # 查看任务详情
hermes kanban assign <id> <person>  # 分配任务
```

---

### A.10 会话管理

```bash
hermes sessions list                # 列出最近会话
hermes sessions export <file>       # 导出会话
hermes sessions delete <id>         # 删除会话
hermes sessions prune               # 清理旧会话
hermes sessions stats               # 会话统计
hermes sessions rename <id> <name>  # 重命名
hermes sessions browse              # 交互式浏览
```

---

### A.11 其他命令

```bash
hermes config show                  # 显示配置
hermes config edit                  # 编辑配置
hermes config set <key> <value>     # 设置值
hermes config path                  # 配置文件路径
hermes config check                 # 检查配置
hermes dashboard                    # 启动 Web Dashboard
hermes logs                         # 查看日志
hermes logs -f                      # 实时跟踪日志
hermes logs --level DEBUG           # 过滤日志级别
hermes backup                       # 备份配置
hermes import <zip>                 # 恢复备份
hermes update                       # 更新 Hermes
hermes uninstall                    # 卸载
```

---

## B. 配置项参考

### B.1 配置文件

Hermes 使用两个核心配置文件：

```
~/.hermes/
├── config.yaml         # 主配置（YAML，结构化设置）
└── .env                # 密钥（API Keys，dotenv 格式）
```

**配置优先级**：

```
Shell 环境变量  >  ~/.hermes/.env  >  ~/.hermes/config.yaml  >  内置默认值
```

### B.2 config.yaml 完整结构

#### `model` — 模型配置

```yaml
model:
  provider: "deepseek"              # Provider 名称
  default: "deepseek-v4-flash"      # 模型 ID
  base_url: "https://api.deepseek.com"  # API 地址
```

| 键 | 类型 | 默认 | 说明 |
|----|------|------|------|
| `provider` | string | `""` | Provider 名称 |
| `default` | string | `""` | 模型 ID |
| `base_url` | string | `""` | API 端点 |

#### `agent` — Agent 行为

```yaml
agent:
  max_turns: 90                      # 最大工具调用轮次
  api_max_retries: 3                 # API 重试次数
  image_input_mode: "auto"           # 图片路由：auto/native/text
  service_tier: ""                   # API 服务层级
  gateway_timeout: 1800              # 网关超时（秒）
  disabled_toolsets: []              # 禁用的工具集
```

| 键 | 类型 | 默认 | 说明 |
|----|------|------|------|
| `max_turns` | int | `90` | 每次对话最大工具调用轮次 |
| `gateway_timeout` | int | `1800` | 网关执行超时（秒），0=无限 |
| `api_max_retries` | int | `3` | API 错误最大重试次数 |
| `image_input_mode` | string | `"auto"` | 图片路由：auto/native/text |
| `tool_use_enforcement` | string | `"auto"` | 工具使用策略 |
| `disabled_toolsets` | list | `[]` | 禁用的工具集 |

#### `terminal` — 终端/沙箱执行

```yaml
terminal:
  backend: "local"                   # 执行后端
  timeout: 180                       # 命令超时（秒）
  cwd: "."                           # 工作目录
  persistent_shell: true             # 保持长期 shell
  docker_image: "nikolaik/python-nodejs:python3.11-nodejs20"
```

| 键 | 类型 | 默认 | 说明 |
|----|------|------|------|
| `backend` | string | `"local"` | 执行后端：local/ssh/docker/modal/daytona |
| `timeout` | int | `180` | 命令超时（秒） |
| `cwd` | string | `"."` | 工作目录 |
| `persistent_shell` | bool | `true` | 跨调用保持 bash shell |
| `docker_image` | string | `"nikolaik/python-nodejs..."` | Docker 镜像 |
| `container_cpu` | int | `1` | CPU 核心数 |
| `container_memory` | int | `5120` | 内存（MB） |

#### `web` — 网络搜索

```yaml
web:
  backend: ""                        # 搜索后端
  search_backend: ""                 # 搜索覆盖（如 searxng）
  extract_backend: ""                # 提取覆盖
```

#### `browser` — 浏览器自动化

```yaml
browser:
  engine: "auto"                     # 引擎：auto/lightpanda/chrome
  inactivity_timeout: 120            # 非活动超时（秒）
  command_timeout: 30                # 命令超时（秒）
  record_sessions: false             # 录制 WebM 视频
  allow_private_urls: false          # 允许私有 IP
  cdp_url: ""                        # CDP 端点 URL
```

#### `compression` — 上下文压缩

```yaml
compression:
  enabled: true                      # 启用自动压缩
  threshold: 0.50                    # 触发阈值（上下文占比）
  target_ratio: 0.20                 # 压缩目标比例
  protect_last_n: 20                 # 保留最近 N 条消息
```

#### `auxiliary` — 辅助模型

```yaml
auxiliary:
  vision:                            # 视觉分析
    provider: "auto"
    model: ""
    timeout: 120
  compression:                       # 上下文压缩
    provider: "auto"
    model: ""
    timeout: 120
  web_extract:                       # 网页提取
    provider: "auto"
    model: ""
    timeout: 360
  session_search:                    # 会话搜索
    provider: "auto"
    model: ""
    timeout: 30
  approval:                          # 审批
    provider: "auto"
    model: ""
    timeout: 30
  curator:                           # 技能审查
    provider: "auto"
    model: ""
    timeout: 600
```

每个辅助任务支持：`provider`, `model`, `base_url`, `api_key`, `timeout`, `extra_body`

#### `display` — 显示/UI

```yaml
display:
  compact: false                     # 简洁模式
  personality: "kawaii"              # 个性风格
  streaming: false                   # 流式输出 token
  show_reasoning: false              # 显示推理过程
  language: "en"                     # UI 语言
  skin: "default"                    # 主题
  tui_auto_resume_recent: false      # TUI 自动恢复最近会话
```

#### `skills` — 技能系统

```yaml
skills:
  external_dirs: []                  # 外部技能目录
  template_vars: true                # 替换 SKILL.md 变量
  inline_shell: false                # 预执行内联命令
```

#### `curator` — 技能维护 **[CN]**

```yaml
curator:
  enabled: true                      # 启用
  interval_hours: 168                # 审查间隔（7 天）
  stale_after_days: 30               # 标记为过时
  archive_after_days: 90             # 归档
```

#### `delegation` — 子代理

```yaml
delegation:
  max_iterations: 50                 # 子代理迭代上限
  child_timeout_seconds: 600         # 子代理超时
  max_concurrent_children: 3         # 并行子代理数
  max_spawn_depth: 1                 # 最大深度
  subagent_auto_approve: false       # 自动批准
```

#### `memory` — 持久化记忆

```yaml
memory:
  memory_enabled: true               # 启用 Agent 笔记
  user_profile_enabled: true         # 启用用户画像
  memory_char_limit: 2200            # 笔记字符限制
  user_char_limit: 1375              # 用户画像字符限制
  provider: ""                       # 外部记忆插件
```

#### `approvals` — 审批模式

```yaml
approvals:
  mode: "manual"                     # manual/smart/off
  timeout: 60                        # 审批超时（秒）
```

#### `logging` — 日志

```yaml
logging:
  level: "INFO"                      # DEBUG/INFO/WARNING
  max_size_mb: 5                     # 日志文件大小
  backup_count: 3                    # 保留轮转文件数
```

#### `checkpoints` — 文件快照

```yaml
checkpoints:
  enabled: false                     # 启用检查点
  max_snapshots: 20                  # 最大快照数
  max_total_size_mb: 500             # 总大小上限
  retention_days: 7                  # 保留天数
```

#### `cron` — 定时任务

```yaml
cron:
  wrap_response: true                # 添加页眉/页脚
  max_parallel_jobs:                 # 最大并行任务数
```

#### `security` — 安全

```yaml
security:
  allow_private_urls: false          # 允许私有 IP
  redact_secrets: true               # 编辑密钥
  tirith_enabled: true               # 启用 tirith 扫描
```

#### `model_catalog` — 远程模型目录

```yaml
model_catalog:
  enabled: true
  url: "https://hermes-agent.nousresearch.com/docs/api/model-catalog.json"
  ttl_hours: 24
```

#### `sessions` — 会话存储

```yaml
sessions:
  auto_prune: false
  retention_days: 90
```

---

### B.3 环境变量 (.env)

#### Provider API Keys

| 变量 | 说明 |
|------|------|
| `DEEPSEEK_API_KEY` | DeepSeek API Key |
| `SILICONFLOW_API_KEY` | 硅基流动 API Key |
| `ZHIPU_API_KEY` / `ZAI_API_KEY` | 智谱 AI GLM API Key |
| `KIMI_API_KEY` | Kimi / Moonshot API Key |
| `DASHSCOPE_API_KEY` | 阿里云 DashScope API Key |
| `MINIMAX_API_KEY` / `MINIMAX_CN_API_KEY` | MiniMax API Key |
| `XIAOMI_API_KEY` | 小米 MiMo API Key |
| `STEPFUN_API_KEY` | StepFun API Key |
| `OPENAI_API_KEY` | OpenAI API Key |
| `ANTHROPIC_API_KEY` / `ANTHROPIC_TOKEN` | Anthropic Claude API Key |
| `OPENROUTER_API_KEY` | OpenRouter API Key |
| `GOOGLE_API_KEY` / `GEMINI_API_KEY` | Google Gemini API Key |
| `XAI_API_KEY` | xAI API Key |
| `NVIDIA_API_KEY` | NVIDIA API Key |
| `HF_TOKEN` | HuggingFace Token |

#### 聊天平台 (`platforms.*`)

| 变量 | 说明 |
|------|------|
| `DINGTALK_CLIENT_ID` / `DINGTALK_CLIENT_SECRET` | 钉钉 |
| `FEISHU_APP_ID` / `FEISHU_APP_SECRET` | 飞书 |
| `WECOM_BOT_ID` / `WECOM_BOT_SECRET` | 企业微信 |
| `WEIXIN_APP_ID` / `WEIXIN_APP_SECRET` | 微信公众号 |
| `QQ_APP_ID` / `QQ_APP_SECRET` | QQ 机器人 |
| `TELEGRAM_BOT_TOKEN` | Telegram |
| `DISCORD_BOT_TOKEN` | Discord |
| `SLACK_BOT_TOKEN` / `SLACK_APP_TOKEN` | Slack |

#### 工具 (`tools.*`)

| 变量 | 说明 |
|------|------|
| `TAVILY_API_KEY` | Tavily 搜索 |
| `EXA_API_KEY` | Exa 搜索 |
| `FIRECRAWL_API_KEY` | Firecrawl 爬取 |
| `BRAVE_SEARCH_API_KEY` | Brave 搜索 |
| `SEARXNG_URL` | SearXNG 自建搜索 |
| `FAL_KEY` | Fal.ai 图像生成 |
| `GITHUB_TOKEN` | GitHub API |

---

## C. Provider 注册 API

### C.1 ProviderProfile 数据类

完整的 ProviderProfile 定义位于 `providers/base.py`：

```python
@dataclass
class ProviderProfile:
    name: str                           # 唯一标识符（如 "deepseek"）
    display_name: str                   # 显示名称（如 "DeepSeek"）
    api_mode: str = "chat_completions"  # 传输层协议
    base_url: str = ""                  # API 端点
    auth_type: str = "api_key"          # 认证方式
    env_vars: tuple = ()                # 所需环境变量
    aliases: tuple = ()                 # 别名
    fallback_models: tuple = ()         # 备选模型列表
    default_aux_model: str = ""         # 子任务默认模型
    fixed_temperature: Any = None       # 固定温度参数
    default_headers: dict = field(default_factory=dict)  # HTTP 头
    default_max_tokens: int | None = None  # token 上限
    conn_current: int | None = None     # 并发连接数
    conn_hard_limit: int | None = None  # 硬性连接限制
```

#### `api_mode` 可选值

| 模式 | 传输层 | 适用场景 |
|------|--------|---------|
| `"chat_completions"` | `chat_completions.py` | OpenAI 兼容 API（大部分） |
| `"anthropic_messages"` | `anthropic.py` | Anthropic Claude |
| `"codex_responses"` | `codex.py` | OpenAI Codex |
| `"bedrock_converse"` | `bedrock.py` | AWS Bedrock |

#### `auth_type` 可选值

| 类型 | 说明 |
|------|------|
| `"api_key"` | API Key 认证（最常见） |
| `"oauth_device_code"` | OAuth 设备授权码 |
| `"oauth_pkce"` | OAuth PKCE 流程 |
| `"none"` | 无需认证（如本地模型） |

### C.2 register_provider() 函数

```python
from providers import register_provider

register_provider(ProviderProfile(
    name="my-provider",
    display_name="我的 Provider",
    base_url="https://api.example.com/v1",
    auth_type="api_key",
    env_vars=("MY_API_KEY",),
    api_mode="chat_completions",
    fallback_models=("model-name",),
    default_aux_model="model-name",
))
```

**调用位置**：在 `plugins/model-providers/<name>/__init__.py` 中调用。

### C.3 Provider 自动发现机制

```
providers/__init__.py
  │
  ├── 1. 扫描 plugins/model-providers/<name>/__init__.py
  │     每个文件调用 register_provider(ProviderProfile(...))
  │
  ├── 2. 扫描 $HERMES_HOME/plugins/model-providers/<name>/
  │     (用户自定义覆盖)
  │
  └── 3. 注册到 _REGISTRY 全局字典
```

### C.4 添加新 Provider 的完整步骤

**步骤 1：创建 Provider 配置文件**

在 `plugins/model-providers/` 下创建目录和 `__init__.py`：

```python
# plugins/model-providers/my-provider/__init__.py
from providers import register_provider, ProviderProfile

register_provider(ProviderProfile(
    name="my-provider",
    display_name="My Provider",
    base_url="https://api.example.com/v1",
    auth_type="api_key",
    env_vars=("MY_API_KEY", "MY_BASE_URL"),
    api_mode="chat_completions",
    fallback_models=("model-1", "model-2"),
    default_aux_model="model-1",
))
```

**步骤 2：（可选）添加到 Provider 注册表**

在 `hermes_cli/auth.py` 的 `PROVIDER_REGISTRY` 中添加：

```python
"my-provider": ProviderConfig(
    id="my-provider",
    name="My Provider",
    auth_type="api_key",
    inference_base_url="https://api.example.com/v1",
    api_key_env_vars=("MY_API_KEY",),
    base_url_env_var="MY_BASE_URL",
),
```

**步骤 3：（可选）添加到模型列表**

在 `hermes_cli/models.py` 的 `CANONICAL_PROVIDERS` 中添加：

```python
ProviderEntry("my-provider", "My Provider", "描述信息"),
```

在 `_PROVIDER_MODELS` 中添加：

```python
"my-provider": [
    "model-1",
    "model-2",
],
```

### C.5 Hermes 元数据覆盖

除了声明式 ProviderProfile，还可以在 `hermes_cli/providers.py` 的 `HERMES_OVERLAYS` 中添加覆盖：

```python
HERMES_OVERLAYS = {
    "my-provider": {
        "auth_type": "api_key",
        "base_url": "https://api.example.com/v1",
        "transport_type": "openai_chat",
    },
}
```

### C.6 自定义 ProviderProfile Hook

ProviderProfile 支持以下钩子函数，用于自定义行为：

```python
@dataclass
class ProviderProfile:
    # ... 字段 ...
    
    prepare_messages: Callable | None = None    # 消息预处理
    build_extra_body: Callable | None = None     # 额外请求体
    build_api_kwargs_extras: Callable | None = None  # 额外参数
    fetch_models: Callable | None = None         # 动态获取模型列表
    get_hostname: Callable | None = None         # 获取主机名
```

---

### C.7 Provider 配置文件 SDK

所有 Provider 配置存放在 `plugins/model-providers/` 目录。以下是现有 Provider 的配置文件清单：

```
plugins/model-providers/
├── deepseek/             # DeepSeek (V3/R1/V4)
├── kimi-coding/          # Kimi / Moonshot
├── siliconflow/          # 硅基流动
├── zai/                  # 智谱 GLM
├── minimax/              # MiniMax
├── alibaba/              # 阿里云
├── xiaomi/               # 小米 MiMo
├── openai-codex/         # OpenAI
├── anthropic/            # Anthropic Claude
├── gemini/               # Google Gemini
├── openrouter/           # OpenRouter
├── bedrock/              # AWS Bedrock
├── copilot/              # GitHub Copilot
├── nvidia/               # NVIDIA
├── xai/                  # xAI
├── stepfun/              # StepFun
├── arcee/                # Arcee AI
├── huggingface/          # HuggingFace
└── ...
```

---

> **文档维护者**: xyshanren  
> **最后更新**: 2026-05-13  
> **相关文档**: [ARCHITECTURE.md](ARCHITECTURE.md) | [DOCS-MAP.md](DOCS-MAP.md) | [README.md](../README.md)

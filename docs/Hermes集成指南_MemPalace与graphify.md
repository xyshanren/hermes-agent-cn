# Hermes 集成指南：MemPalace + graphify

> 本文档详细介绍如何将 MemPalace（记忆系统）和 graphify（代码知识图谱）集成到 Hermes AI 助手中，实现跨会话持久记忆和代码库智能理解。
>
> **✅ 已验证可用** — 本文档基于 2026-04-16 实际安装测试编写，所有命令和配置均已验证。

hermes-agent：https://github.com/NousResearch/hermes-agent
mempalace：https://github.com/MemPalace/mempalace
graphify：https://github.com/safishamsi/graphify

hermes-agent中文文档：https://hermes.xaapi.ai/
---

## 目录

- [项目概述](#项目概述)
- [前置要求](#前置要求)
- [安装 MemPalace](#安装-mempalace)
- [安装 graphify](#安装-graphify)
- [Hermes 集成配置](#hermes-集成配置)
- [使用指南](#使用指南)
- [实战案例](#实战案例)
- [故障排查](#故障排查)
- [最佳实践](#最佳实践)

---

## 项目概述

### MemPalace - AI 记忆系统

**核心功能：**
- 🏰 宫殿结构化记忆：Wing（人/项目）→ Room（主题）→ Hall（概念类别）→ Drawer（原文）
- 📦 结构化索引：Wing 和 Room 标识符作为元数据过滤器，缩小搜索范围
- 💾 原始逐字存储：96.6% LongMemEval 得分，零 API 调用
- 🕸️ 知识图谱：SQLite 存储时间有效性实体关系，支持 add/query/invalidate/timeline 操作
- 🔧 MCP 服务器：29 个工具，可被 AI 自动调用

### graphify - 代码知识图谱

**核心功能：**
- 📊 多模态提取：代码、文档、PDF、图片、视频、音频
- 🔄 三阶段处理：
  1. AST 提取结构（类、函数、导入、调用图）
  2. Whisper 转录视频/音频（本地、领域感知）
  3. Claude 子代理并行提取概念和关系
- 📈 71.5x 查询 token 减少 vs 读原文件
- 🎨 生成产物：交互式图谱（HTML）、可查询 JSON、审计报告（MD）

---

## 前置要求

### 系统要求

| 要求 | 版本 | 备注 |
|------|------|------|
| Python | 3.9+ | 必需 |
| Hermes AI | 已安装 | 需要技能支持 |
| Git | 任意 | 可选，用于 clone 项目 |

### 操作系统支持

- ✅ Linux（推荐）
- ✅ macOS
- ⚠️ Windows（建议使用 WSL2）

### 环境准备

```bash
# 创建 Python 虚拟环境（推荐）
python3 -m venv ~/hermes-venv
source ~/hermes-venv/bin/activate

# 确保 pip 最新
pip install --upgrade pip
```

---

## 安装 MemPalace

### 步骤 1：安装 MemPalace

```bash
# 激活虚拟环境
source ~/hermes-venv/bin/activate

# 使用 pip 安装
pip install mempalace

# 验证安装
pip show mempalace | grep Version
# 输出: Version: 3.3.0
```

### 步骤 2：初始化宫殿

```bash
# 创建宫殿目录
mkdir -p ~/.mempalace

# 初始化 MemPalace 配置（非交互模式）
mempalace init ~/.mempalace --yes

# 查看配置目录
ls ~/.mempalace
# 应该看到：config.json, mempalace.yaml
```

> ⚠️ **注意**：`mempalace init` 默认是交互模式，需要用户输入。使用 `--yes` 参数可跳过交互。

### 步骤 3：验证安装

```bash
# 测试 MCP 服务器
python -m mempalace.mcp_server --help
# 输出: usage: mcp_server.py [-h] [--palace PATH]
```

### 步骤 4：配置个人信息（可选）

编辑 `~/.mempalace/identity.txt`：

```bash
nano ~/.mempalace/identity.txt
```

写入你的身份信息（L0 层记忆）：

```
Name: Your Name
Role: Developer / Product Manager
Skills: Python, TypeScript, Product Design
```

---

## 安装 graphify

### 步骤 1：安装 graphify

```bash
# 激活虚拟环境
source ~/hermes-venv/bin/activate

# 注意：PyPI 包名是 graphifyy（双 y）
pip install graphifyy

# 验证安装
pip show graphifyy | grep -E "^(Name|Version):"
# 输出:
# Name: graphifyy
# Version: 0.4.18
```

### 步骤 2：安装到 Hermes

```bash
# 安装 Hermes 集成
graphify install --platform hermes
# 输出: skill installed -> /root/.hermes/skills/graphify/SKILL.md
```

此命令会执行以下操作：

1. **复制技能文件**
   - 复制技能到 `~/.hermes/skills/graphify/SKILL.md`

2. **写入项目规则**
   - 在项目根目录创建 `AGENTS.md`，包含 graphify 使用说明

### 步骤 3：验证安装

```bash
# 检查技能文件是否存在
ls ~/.hermes/skills/graphify/
# 输出: SKILL.md  .graphify_version

# 检查 Hermes 是否识别
hermes skills list | grep graphify
# 输出: │ graphify │ │ local │ local │
```

---

## Hermes 集成配置

### MemPalace MCP 集成

MemPalace 通过 **MCP（Model Context Protocol）** 集成到 Hermes，提供 29 个工具供 AI 自动调用。

#### 步骤 1：添加 MCP 服务器

```bash
# 方法 1：使用 hermes mcp add 命令
hermes mcp add mempalace --command /root/hermes-venv/bin/python --args '-m' --args 'mempalace.mcp_server'

# 方法 2：手动编辑配置文件
nano ~/.hermes/config.yaml
```

在 `~/.hermes/config.yaml` 末尾添加：

```yaml
# ── MCP Servers ───────────────────────────────────────────────────────
mcp_servers:
  mempalace:
    command: /root/hermes-venv/bin/python  # 使用完整路径
    args:
      - -m
      - mempalace.mcp_server
    env: {}
```

> ⚠️ **注意**：配置 key 必须是 `mcp_servers`（不是 `mcp`），这是 Hermes 的正确格式。

#### 步骤 2：验证 MCP 配置

```bash
# 查看已配置的 MCP 服务器
hermes mcp list
# 输出:
# MCP Servers:
#   Name             Transport                      Tools        Status
#   ──────────────── ────────────────────────────── ──────────── ──────────
#   mempalace        /root/hermes-venv/bin/pyt...   all          ✓ enabled
```

#### 步骤 3：测试 MCP 连接

```bash
# 测试 MCP 服务器连接
hermes mcp test mempalace
# 输出:
# Testing 'mempalace'...
#   ✓ Connected (1162ms)
#   ✓ Tools discovered: 29
#
#   mempalace_status                     Palace overview
#   mempalace_search                     Semantic search
#   mempalace_add_drawer                 Add content to palace
#   mempalace_kg_query                   Query knowledge graph
#   ... (共 29 个工具)
```

#### MemPalace MCP 工具列表

| 工具 | 功能 |
|------|------|
| **读取工具** ||
| `mempalace_status` | 宫殿状态（总 drawers、wing/room 分布） |
| `mempalace_list_wings` | 列出所有 wings |
| `mempalace_list_rooms` | 列出指定 wing 下的 rooms |
| `mempalace_get_taxonomy` | 完整的 wing→room→count 树 |
| `mempalace_search` | 语义搜索，支持 wing/room 过滤 |
| `mempalace_check_duplicate` | 检查内容是否已存在 |
| `mempalace_get_drawer` | 获取单个 drawer 内容 |
| `mempalace_list_drawers` | 分页列出 drawers |
| **写入工具** ||
| `mempalace_add_drawer` | 添加内容到 wing/room |
| `mempalace_update_drawer` | 更新 drawer 内容 |
| `mempalace_delete_drawer` | 删除 drawer |
| **知识图谱** ||
| `mempalace_kg_query` | 查询实体关系 |
| `mempalace_kg_add` | 添加实体关系 |
| `mempalace_kg_invalidate` | 标记关系失效 |
| `mempalace_kg_timeline` | 实体时间线 |
| `mempalace_kg_stats` | 知识图谱统计 |
| **图谱遍历** ||
| `mempalace_traverse` | 遍历宫殿图谱 |
| `mempalace_find_tunnels` | 发现跨 wing 连接 |
| `mempalace_create_tunnel` | 创建跨 wing 隧道 |
| `mempalace_list_tunnels` | 列出所有隧道 |
| `mempalace_delete_tunnel` | 删除隧道 |
| `mempalace_follow_tunnels` | 跟随隧道连接 |
| `mempalace_graph_stats` | 图谱统计 |
| **日记** ||
| `mempalace_diary_write` | 写入日记（AAAK 格式） |
| `mempalace_diary_read` | 读取日记条目 |
| **维护** ||
| `mempalace_reconnect` | 重建缓存连接 |
| `mempalace_hook_settings` | 获取/设置 hook 行为 |

### graphify 集成

graphify 已通过 `graphify install --platform hermes` 自动配置，无需额外操作。

#### 验证集成

```bash
# 检查技能是否注册
hermes skills list | grep graphify
# 输出: │ graphify │ │ local │ local │

# 查看技能文件
head -20 ~/.hermes/skills/graphify/SKILL.md
```

#### 在 Hermes 中使用

启动 Hermes 后，输入 `/graphify` 命令触发：

```
/graphify .                    # 分析当前目录
/graphify ./src                # 分析特定目录
/graphify . --update           # 增量更新
/graphify query "auth flow"    # 查询图谱
```

---

## 使用指南

### MemPalace 使用流程

#### 1. 挖掘数据

```bash
# 挖掘项目文件（代码、文档）
mempalace mine ./my-project --mode projects --wing myproject

# 挖掘对话记录（Claude、ChatGPT 导出）
mempalace mine ./conversations --mode convos --wing myproject

# 挖掘通用内容（自动分类为决策、里程碑、问题）
mempalace mine ./notes --mode convos --extract general
```

#### 2. 搜索记忆

```bash
# 全局搜索
mempalace search "why did we switch to GraphQL"

# 在特定 wing 中搜索
mempalace search "auth decision" --wing myproject

# 在特定 room 中搜索
mempalace search "rate limiting" --room api-design
```

#### 3. 知识图谱操作

```python
from mempalace.knowledge_graph import KnowledgeGraph

# 创建知识图谱
kg = KnowledgeGraph()

# 添加实体关系
kg.add_triple("Alice", "works_on", "ProjectA", valid_from="2025-01-01")
kg.add_triple("ProjectA", "uses", "PostgreSQL")

# 查询实体
kg.query_entity("Alice")
# 输出: [Alice -> works_on -> ProjectA]

# 时间维度查询
kg.query_entity("Alice", as_of="2025-06-01")
# 输出 2025 年 6 月时的关系状态
```

#### 3. 在 Hermes 中使用

启动 Hermes 后，你可以直接对话：

```
你: 我们上个月关于认证方案做了什么决策？

Hermes: [自动调用 MCP 工具 mempalace_search]
根据记忆记录，团队在 2025-03-15 决定：
- 从 Auth0 迁移到 Clerk
- 理由：成本降低 40%，开发者体验更好
- Maya 负责实施迁移
```

> 📌 注：MemPalace 通过 MCP 协议提供 29 个工具，包括 `mempalace_search`、`mempalace_list_agents`、`mempalace_traverse` 等，Hermes 可在对话中自动调用这些工具。

### graphify 使用流程

#### 1. 构建代码图谱

```bash
# 在项目目录下运行
cd my-project

# 构建图谱
/graphify .
```

生成产物：

```
graphify-out/
├── graph.html          # 交互式图谱（浏览器打开）
├── graph.json          # 可查询 JSON（持久存储）
├── GRAPH_REPORT.md    # 审计报告（关键节点、建议问题）
└── cache/              # SHA256 缓存（增量更新）
```

#### 2. 配置 Always-on 行为

```bash
# 安装 always-on hook
graphify hermes install
```

这会在每次 Hermes 对话开始时检查：
- 如果 `graphify-out/GRAPH_REPORT.md` 存在，自动加载
- Hermes 在回答问题前先读取图谱报告，理解项目结构

> ⚠️ 注意：`graphify install --platform hermes` 只安装技能，需要额外运行 `graphify hermes install` 才能启用 always-on 行为。

#### 3. 查询图谱

```bash
# 查询节点关系
/graphify query "what connects auth to database?"

# 查找最短路径
/graphify path "AuthService" "Database"

# 解释节点
/graphify explain "UserController"
```

#### 4. 在 Hermes 中使用

```
你: UserController 和数据库是怎么交互的？

Hermes: [自动读取 GRAPH_REPORT.md]
根据项目图谱分析：
- UserController 通过 AuthService 层访问数据库
- 数据流：UserController → AuthService → PostgreSQL
- 相关文件：src/controllers/UserController.ts:42-67
```

---

## 实战案例

### 案例 1：复杂项目开发

#### 目标
开发一个多模块的电商平台，使用 MemPalace 记忆设计决策，graphify 理解代码结构。

#### 步骤

**1. 初始化项目**

```bash
mkdir ecommerce-platform && cd ecommerce-platform
git init

# 初始化 MemPalace wing
mempalace mine . --mode projects --wing ecommerce
```

**2. 构建代码图谱**

```bash
# 开发初期
/graphify .

# 查看图谱报告
cat graphify-out/GRAPH_REPORT.md
```

**3. 记录设计决策**

在 Hermes 中讨论架构：

```
你: 我计划用微服务架构，用户服务、订单服务、支付服务分别部署。
    技术栈：Node.js + TypeScript + PostgreSQL。
    用 Kafka 做服务间通信。

Hermes: [MemPalace 自动记录这些决策]
已记录到 wing_ecommerce / room_architecture：
- 微服务架构（用户、订单、支付）
- 技术栈：Node.js + TypeScript + PostgreSQL
- 消息队列：Kafka
```

**4. 跨会话回顾**

一个月后：

```
你: 我们为什么选 Kafka 而不是 RabbitMQ？

Hermes: [查询 MemPalace]
根据 2025-03-10 的讨论，选择 Kafka 的原因：
- 项目预期每秒 1000+ 订单
- Kafka 支持更高吞吐量
- 团队有 Kafka 使用经验
```

### 案例 2：多项目关联分析

#### 目标
发现两个项目的共同模式和差异。

#### 步骤

**1. 挖掘两个项目**

```bash
# 项目 A
cd project-a
mempalace mine . --mode projects --wing project-a
/graphify .

# 项目 B
cd project-b
mempalace mine . --mode projects --wing project-b
/graphify .
```

**2. 建立知识图谱关联**

```python
from mempalace.knowledge_graph import KnowledgeGraph

kg = KnowledgeGraph()

# 记录项目关联
kg.add_triple("ProjectA", "similar_to", "ProjectB")
kg.add_triple("ProjectA", "uses", "PostgreSQL")
kg.add_triple("ProjectB", "uses", "PostgreSQL")

# 查询共同点
kg.query_entity("PostgreSQL")
# 输出: [ProjectA -> uses -> PostgreSQL, ProjectB -> uses -> PostgreSQL]
```

**3. 跨项目搜索**

```bash
mempalace search "database design" --wing project-a
mempalace search "database design" --wing project-b
```

### 案例 3：视频/音频内容索引

#### 目标
将技术会议录像、播客等非结构化内容索引到图谱。

#### 步骤

**1. 安装视频依赖**

```bash
pip install 'graphifyy[video]'
```

**2. 添加视频到图谱**

```bash
# 添加 YouTube 视频
/graphify add https://youtube.com/watch?v=example

# 添加本地视频
mv tech-talk.mp4 ./corpus/
/graphify ./corpus
```

**3. 查询转录内容**

```
你: 在那场技术演讲里，关于性能优化说了什么？

Hermes: [查询图谱]
根据 "Performance Optimization Talk" 的转录：
- 建议使用 Redis 缓存热点数据
- 数据库索引优化可提升 50% 查询速度
- 视频时间戳：12:35-18:20
```

---

## 故障排查

### MemPalace 常见问题

#### 问题 1：`mempalace: command not found`

**解决方案：**

```bash
# 检查 Python 路径
which python

# 使用完整路径安装
$(which python) -m pip install mempalace

# 添加到 PATH
export PATH="$HOME/.local/bin:$PATH"
echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.bashrc
```

#### 问题 2：ChromaDB 连接失败

**解决方案：**

```bash
# 重新初始化宫殿
rm -rf ~/.mempalace/palace
mempalace init ~/.mempalace

# 检查 ChromaDB 版本
pip show chromadb
```

#### 问题 3：搜索结果不准确

**解决方案：**

```bash
# 使用 wing/room 过滤（提高精度）
mempalace search "query" --wing myproject --room specific-room
```

### graphify 常见问题

#### 问题 1：`graphify: command not found`

**解决方案：**

```bash
# 确认安装的是 graphifyy（双 y）
pip list | grep graphify

# 应该看到：graphifyy
# 如果没有，重新安装：
pip uninstall graphify
pip install graphifyy
```

#### 问题 2：Hermes 不识别 `/graphify` 命令

**解决方案：**

```bash
# 检查技能文件
ls -la ~/.hermes/skills/graphify/

# 如果不存在，重新安装
graphify install --platform hermes

# 检查 AGENTS.md
cat AGENTS.md | grep -A 5 graphify
```

#### 问题 3：图谱生成失败

**解决方案：**

```bash
# 启用详细日志
/graphify . --verbose

# 检查 .graphifyignore 配置
cat .graphifyignore

# 清除缓存重试
rm -rf graphify-out/cache/
/graphify . --update
```

#### 问题 4：视频转录失败

**解决方案：**

```bash
# 安装视频依赖
pip install 'graphifyy[video]'

# 检查 faster-whisper 安装
pip show faster-whisper

# 手动测试转录
python -c "from faster_whisper import WhisperModel; print('OK')"
```

### 集成问题

#### 问题：Hermes 无法访问 MemPalace MCP 服务器

**解决方案：**

```bash
# 检查 MCP 配置
cat ~/.claude/mcp.json

# 测试 MCP 服务器
python -m mempalace.mcp_server --help

# 重启 Hermes
# 重新启动 Hermes 应用
```

---

## 最佳实践

### MemPalace 使用技巧

1. **按项目划分 Wing**
   ```bash
   # 推荐：每个项目一个 wing
   mempalace mine project-a --mode projects --wing project-a
   mempalace mine project-b --mode projects --wing project-b
   ```

2. **定期更新记忆**
   ```bash
   # 每周更新一次
   mempalace mine . --mode projects --wing myproject --update
   ```

3. **使用知识图谱追踪实体关系**
   ```python
   # 记录团队成员动态
   kg.add_triple("Alice", "assigned_to", "TaskX", valid_from="2025-04-01")
   kg.invalidate("Alice", "assigned_to", "TaskX", ended="2025-04-10")
   ```

### graphify 使用技巧

1. **增量更新图谱**
   ```bash
   # 只处理变更的文件
   /graphify . --update
   ```

2. **排除无关文件**
   ```bash
   # 创建 .graphifyignore
   cat > .graphifyignore << EOF
   node_modules/
   dist/
   .git/
   *.generated.ts
   EOF
   ```

3. **使用社区检测模块化**
   ```bash
   # 生成 Obsidian vault（按社区组织）
   /graphify . --obsidian
   ```

### 组合使用场景

| 场景 | MemPalace | graphify |
|------|-----------|----------|
| 新项目开发 | 记录设计决策 | 理解代码结构 |
| 代码审查 | 追溯历史讨论 | 快速定位相关文件 |
| 技术调研 | 整理调研笔记 | 建立知识图谱 |
| 团队协作 | 共享决策记忆 | 统一代码理解 |

---

## 附录

### 相关链接

- [MemPalace GitHub](https://github.com/MemPalace/mempalace)
- [graphify GitHub](https://github.com/safishamsi/graphify)
- [Hermes 官方文档](https://hermes.ai/docs)
- [MCP 协议规范](https://modelcontextprotocol.io)

### 版本信息

- MemPalace: v3.3.0（以 GitHub releases 最新版为准）
- graphify: v4.x（以 PyPI 最新版 graphifyy 为准）
- Hermes: 最新稳定版

---

**最后更新：** 2026-04-16
**维护者：** 用户773444

---

## 附录：安装验证清单

### ✅ MemPalace 安装验证

| 检查项 | 命令 | 预期输出 |
|--------|------|----------|
| 包安装 | `pip show mempalace \| grep Version` | `Version: 3.3.0` |
| MCP 服务器 | `python -m mempalace.mcp_server --help` | 显示帮助信息 |
| Hermes MCP 配置 | `hermes mcp list` | `mempalace ✓ enabled` |
| MCP 连接测试 | `hermes mcp test mempalace` | `✓ Connected` + 29 tools |

### ✅ graphify 安装验证

| 检查项 | 命令 | 预期输出 |
|--------|------|----------|
| 包安装 | `pip show graphifyy \| grep Version` | `Version: 0.4.18` |
| 技能注册 | `hermes skills list \| grep graphify` | `graphify │ local │ local` |
| 技能文件 | `ls ~/.hermes/skills/graphify/SKILL.md` | 文件存在 |

---

## 附录：数据存储位置

### MemPalace 数据目录

```
~/.mempalace/
├── config.json          # 配置
├── mempalace.yaml       # YAML 配置
├── identity.txt         # 身份信息（L0 记忆）
├── palace/              # ChromaDB 向量存储
│   └── chroma.sqlite3   # SQLite 数据库
├── knowledge_graph.sqlite3  # 知识图谱
├── entities.json        # 实体定义
└── wal/                 # 写入日志
    └── write_log.jsonl
```

### graphify 输出目录

```
graphify-out/
├── graph.html       # 交互式图谱（浏览器打开）
├── obsidian/        # Obsidian vault
├── wiki/            # Wikipedia 风格文章
├── GRAPH_REPORT.md  # 审计报告
├── graph.json       # 持久图谱（JSON）
└── cache/           # SHA256 缓存
```

---

## 附录：重要说明

### 完全本地运行

**MemPalace 和 graphify 都不需要云服务：**

- MemPalace：数据存储在本地 ChromaDB 和 SQLite，无需外部 API
- graphify：AST 解析完全本地，LLM 调用使用你配置的模型

### AAAK 模式说明

根据 MemPalace 官方 README：

> AAAK 宣传有误。实际测试：raw 模式 LongMemEval 得分 96.6%，AAAK 模式 84.2%。
> 团队已承认此错误。建议使用 raw 模式（零 API 调用）。

---

**最后更新：** 2026-04-16
**维护者：** 用户773444

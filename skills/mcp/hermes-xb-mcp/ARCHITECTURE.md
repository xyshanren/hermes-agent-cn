# Hermes-xb MCP 集成架构

> **browser-harness 理念借鉴路径** — P1→P2→P3 三阶段

## 目录结构

```
hermes-agent/
  skills/
    mcp/
      hermes-xb-mcp/           # 新增：xb MCP Server 封装
        __init__.py
        hermes_xb_mcp.py       # stdio MCP Server 主文件
        tools.py               # xb 命令 → MCP tool 映射
        helpers.py             # 内部辅助函数（retry、parse）
        test_mcp.py            # 独立验证脚本
        README.md
```

## P1: MCP Server 封装验证 ✅ 规划中

### 目标
将 xbrowser CLI 封装为 stdio MCP Server，使 Hermes 通过内置 MCP 客户端消费。

### 暴露的 MCP Tools

| MCP Tool | xb 命令 | 说明 |
|---------|---------|------|
| `mcp_xb_init` | `xb init` | 初始化浏览器环境 |
| `mcp_xb_navigate` | `xb run open <url>` | 导航到 URL |
| `mcp_xb_snapshot` | `xb run snapshot -i` | 获取可交互元素快照 |
| `mcp_xb_click` | `xb run click @<ref>` | 点击元素 |
| `mcp_xb_fill` | `xb run fill @<ref> <text>` | 填写表单 |
| `mcp_xb_screenshot` | `xb run screenshot [--full]` | 截图 |
| `mcp_xb_wait` | `xb run wait --load networkidle` | 等待加载 |
| `mcp_xb_stop` | `xb stop <browser\|all>` | 关闭浏览器 |

### Hermes 配置

`~/.hermes/config.yaml`:
```yaml
mcp_servers:
  xb:
    command: "python"
    args: ["-m", "skills.mcp.hermes_xb_mcp.hermes_xb_mcp"]
    timeout: 120
    connect_timeout: 30
```

### 验证方式

```bash
# 1. 独立测试 MCP Server
python skills/mcp/hermes-xb-mcp/hermes_xb_mcp.py

# 2. 用 MCP Inspector 测试
npx @modelcontextprotocol/inspector python skills/mcp/hermes-xb-mcp/hermes_xb_mcp.py

# 3. Hermes 内验证
hermes run --query "打开百度，搜索 OpenClaw"  # 应该自动发现 mcp_xb_* tools
```

## P2: 高频函数内置为 Hermes Tool

### 目标
不依赖 MCP Bridge，直接在 `tools/` 目录注册 Hermes native tools。

### 设计

`tools/xb_native.py` — 直接调用 xb CLI（subprocess），零外部依赖：
- 利用 Hermes 的 registry.register() 注册
- 复用 `agent-browser` 已有状态（登录态复用）
- 支持断点恢复 (@ref 失效自动 resnapshot)

### 注册的工具

```python
from tools.registry import registry

registry.register(
    name="xb_navigate",
    toolset="browser",
    schema={...},
    handler=xb_navigate_handler,
    check_fn=xb_check,      # 检查 xb 是否可用
    emoji="🌐"
)
```

### 高频操作内置

| Hermes Tool | 优先级 | 说明 |
|------------|--------|------|
| `xb_navigate` | P0 | 最高频，每次浏览器任务必用 |
| `xb_snapshot` | P0 | 获取页面状态 |
| `xb_click` | P0 | 最常用的元素操作 |
| `xb_fill` | P1 | 表单填写 |
| `xb_screenshot` | P1 | 可视化反馈 |
| `xb_stop` | P2 | 资源清理 |

## P3: 设计理念融入 Hermes Tool 框架

### 理念 1: 截图驱动（Snapshots as Ground Truth）

browser-harness 的核心：每次操作前先 `snapshot` 获取 @ref，再操作。

Hermes 实现：
```python
async def xb_click(task_id: str, ref: str) -> str:
    """Click element by @ref, auto-resnapshot if ref expired."""
    # 1. 获取当前页面快照（包含 @ref 位置）
    snapshot = await xb_snapshot(task_id)
    
    # 2. 检查 ref 是否仍然有效
    if not ref_exists(snapshot, ref):
        # 3. ref 失效 → 自动重新快照
        snapshot = await xb_snapshot(task_id, force=True)
        if not ref_exists(snapshot, ref):
            return error_result(f"元素 @ref={ref} 在页面上不存在")
    
    # 4. 执行点击
    return await run_xb_command(["click", ref])
```

### 理念 2: 自写 Helpers（Domain Skills）

为高频场景编写专用 helper functions：

```python
# helpers/scroll_helper.py
async def xb_scroll_to_bottom(task_id: str) -> str:
    """滚动到页面底部（加载更多场景）"""
    
# helpers/form_helper.py  
async def xb_fill_and_submit(task_id: str, form_data: dict) -> str:
    """填表单并提交（智能字段匹配）"""

# helpers/navigation_helper.py
async def xb_wait_for_text(task_id: str, text: str, timeout: int = 30) -> str:
    """等待页面出现指定文本"""
```

### 理念 3: 域技能沉淀（Skill Framework）

创建 Hermes-native browser skills：

```
skills/browser-automation/
  scroll.skill.md        # 滚动操作技能
  form.skill.md         # 表单填写技能  
  navigation.skill.md   # 导航守卫技能
  captcha.skill.md      # 验证码处理技能
  login.skill.md        # 登录流程技能
```

每个 skill 包含：
- 触发条件（`when:`）
- 操作步骤（`steps:`）
- 错误恢复（`recovery:`）

## 状态追踪

- [ ] P1: MCP Server 封装验证
  - [ ] hermes-xb-mcp.py 基础框架
  - [ ] init/navigate/snapshot/click/fill 工具实现
  - [ ] 独立验证（Inspector）
  - [ ] Hermes 配置集成
- [ ] P2: 高频函数内置
  - [ ] tools/xb_native.py 编写
  - [ ] registry.register() 注册
  - [ ] @ref 失效自动恢复
- [ ] P3: 设计理念融合
  - [ ] scroll_helper / form_helper / navigation_helper
  - [ ] browser-automation skills 编写
  - [ ] captcha handling 策略
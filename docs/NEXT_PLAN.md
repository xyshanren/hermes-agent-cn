# Hermes-Agent-CN 下一阶段规划

**生成时间**：2026-05-03 14:01  
**当前分支**：`cn` (领先 origin/cn 973 commits)  
**上游合并**：✅ 已完成 (NousResearch v0.12.0+)

---

## 一、已完成工作

### ✅ 上游合并 (今日执行)

| 项目 | 值 |
|------|-----|
| 上游仓库 | NousResearch/hermes-agent |
| 合并的提交数 | 972 |
| 冲突文件 | 9 个 |
| 解决策略 | 汉化/精简文件 → 保留 cn 版本；其余 → 保留上游版本 |
| 合并结果 | ✅ 成功 (commit: aaffb8b1) |
| 汉化验证 | ✅ 4/4 测试通过 |
| 待推送 | 需用户手动 `git push origin cn` |

### ✅ Phase 1-9 CN 改造
参见 [CHANGELOG_CN.md](CHANGELOG_CN.md) v0.11.0-cn.1

---

## 二、下一步计划

### P0：高频函数内置为 Hermes Tool (xb_native.py)

**来源**：ARCHITECTURE.md 的 P2 阶段

**目标**：将 xbrowser 高频操作直接从 MCP Server 模式改为 Hermes Native Tool（零外部依赖）

**实现方案**（见下文第四节的设计建议）

| 阶段 | 内容 | 预估工时 |
|------|------|----------|
| 1 | 创建 `tools/xb_native.py` 骨架 | 1h |
| 2 | 实现核心 3 个 P0 Tool (navigate/snapshot/click) | 3h |
| 3 | 实现 P1 Tool (fill/screenshot) | 2h |
| 4 | 实现 @ref 失效自动恢复逻辑 | 2h |
| 5 | 测试与集成验证 | 2h |
| **合计** | | **10h** |

---

### P0：更新文档和变更记录

**来源**：上游合并后文档同步

| 文件 | 内容 | 预估工时 |
|------|------|----------|
| `CHANGELOG_CN.md` | 添加上游合并记录 | 1h |
| `README_CN.md` | 更新上游版本号 | 0.5h |
| `tests/test_cn_simple.py` | 验证上游合并后的中文完整性 | 0.5h |
| **合计** | | **2h** |

---

### P1：完善测试体系

**来源**：当前测试覆盖不足

| 阶段 | 内容 | 预估工时 |
|------|------|----------|
| 1 | 补充集成测试（doctor/setup 实际调用） | 3h |
| 2 | 添加 CI 配置文件 (GitHub Actions) | 1h |
| 3 | 验证上游新功能兼容性 | 3h |
| **合计** | | **7h** |

---

### P2：TUI 和 Dashboard 汉化

**来源**：CHANGELOG_CN.md "待汉化项目"

| 阶段 | 内容 | 预估工时 |
|------|------|----------|
| 1 | 扫描 `ui-tui/` 目录，标记英文文本 | 2h |
| 2 | 批量汉化 TUI 界面 | 4h |
| 3 | 扫描 `web/` 目录，汉化 Dashboard | 3h |
| **合计** | | **9h** |

---

### P2：Phase 10 文言压缩 (延后执行)

**来源**：改造方案 2.0 的 Phase 10

**设计建议**见下文第五节

| 阶段 | 内容 | 预估工时 |
|------|------|----------|
| 1 | 压缩内核开发 | 5h |
| 2 | 试点集成 + AB 测试框架 | 3h |
| 3 | 测试与调优 | 3h |
| **合计** | | **11h** |

---

### P3：定期合并上游 (他人或后续)

- 建议 **每 2 周** 检查一次上游更新
- 使用 `git remote add upstream https://github.com/NousResearch/hermes-agent.git`（已配）
- 流程：`git fetch upstream main && git merge upstream/main --no-ff`

---

## 三、实施路线图

```
周1-2 （本轮）
├── P0: xb_native.py 骨架 + P0 工具 (navigate/snapshot/click)
├── P0: 文档同步 (CHANGELOG_CN/README_CN)
├── P1: 测试体系完善

周3-4
├── P0: xb_native.py P1 工具 (fill/screenshot)
├── P0: @ref 失效自动恢复
├── P2: TUI 汉化

延后
├── P2: Phase 10 文言压缩
├── P2: Dashboard 汉化
├── P3: 定期合并上游
```

---

## 四、设计建议：高频函数内置为 Hermes Tool (xb_native.py)

### 4.1 问题分析

当前 MCP Server 模式 (`hermes_xb_mcp.py`) 的问题：

| 问题 | 说明 |
|------|------|
| **外部依赖** | 需要装 `mcp` 包 |
| **性能开销** | MCP 协议序列化/反序列化 |
| **状态管理** | MCP 无状态，每次都要 subprocess |
| **错误恢复** | @ref 失效无法自动 resnapshot |

### 4.2 建议架构

```python
# tools/xb_native.py

from tools.registry import registry

# ── 缓存层（替代 MCP 的连续会话） ──
_xb_sessions: Dict[str, XbSession] = {}

class XbSession:
    """浏览器会话，维护页面状态"""
    task_id: str
    browser_type: str
    last_snapshot: Optional[Dict]
    last_refs: Dict[str, str]  # @ref → element descriptor
    
# ── P0 工具（最高频） ──

@registry.register(name="xb_navigate", ...)
async def xb_navigate(url: str, browser: str = "chrome") -> dict:
    """打开 URL，初始化浏览器会话"""
    session = XbSession(task_id=uuid4(), browser_type=browser)
    result = await _run_xb(["run", "open", url])
    _xb_sessions[session.task_id] = session
    return result

@registry.register(name="xb_snapshot", ...)
async def xb_snapshot(task_id: str, force: bool = False) -> dict:
    """获取页面快照，带缓存"""
    session = _get_session(task_id)
    snapshot = await _run_xb(["run", "snapshot", "-i"])
    session.last_snapshot = snapshot
    session.last_refs = _extract_refs(snapshot)
    return snapshot

@registry.register(name="xb_click", ...)
async def xb_click(task_id: str, ref: str) -> dict:
    """点击元素，带 @ref 失效自动恢复"""
    session = _get_session(task_id)
    
    # 检查 @ref 是否有效
    if ref not in session.last_refs:
        # 自动重新快照
        await xb_snapshot(task_id, force=True)
        if ref not in session.last_refs:
            return {"error": f"元素 @{ref} 已不存在"}
    
    return await _run_xb(["run", "click", f"@{ref}"])

# ── P1 工具 ──

@registry.register(name="xb_fill", ...)
async def xb_fill(task_id: str, ref: str, text: str) -> dict:
    """填写表单"""
    # 同样带 @ref 失效恢复
    ...

@registry.register(name="xb_screenshot", ...)
async def xb_screenshot(task_id: str, full: bool = False) -> dict:
    """截图"""
    ...
```

### 4.3 关键设计决策

| 决策 | 方案 | 原因 |
|------|------|------|
| **状态管理** | 进程内 Dict 缓存 | 零外部依赖，Hermes 进程重启即失效（可接受） |
| **CLI 调用** | subprocess → `node xb.cjs` | 复用 xbrowser 生态，不重复造轮子 |
| **@ref 恢复** | 自动 resnapshot | 用户无感知，浏览器操作稳定 |
| **超时控制** | 每步 120s + 全局超时 | 复杂页面操作 |
| **错误处理** | 返回结构化错误 | LLM 可识别并自动重试 |

### 4.4 与 MCP Server 的共存策略

```
xb_native.py (Hermes Native Tool) ── 高频操作
    ├── xb_navigate (P0)
    ├── xb_snapshot (P0)
    ├── xb_click (P0)
    ├── xb_fill (P1)
    └── xb_screenshot (P1)

hermes_xb_mcp.py (MCP Server) ── 低频/高级操作
    ├── xb_type
    ├── xb_press
    ├── xb_wait
    ├── xb_close
    ├── xb_status
    └── xb_cleanup
```

**原则**：高频操作直接调用 native tool，低频操作回退到 MCP Server。两者共享同一个 xb CLI 后端。

---

## 五、设计建议：Phase 10 文言压缩

### 5.1 问题分析

**目标**：将长对话/长上下文压缩为"文言文"风格的精炼文本，大幅减少 token 消耗。

**挑战**：

| 挑战 | 说明 |
|------|------|
| **信息损失** | 压缩必须保留关键信息 |
| **LLM 可读性** | 压缩后的文言文，模型能理解吗？ |
| **解压成本** | 如果只是压缩，使用时需要"解压"吗？ |
| **AB 测试** | 如何量化压缩质量？ |

### 5.2 建议方案：三层压缩框架

#### 第一层：对话摘要 (Lossy)

```yaml
# 压缩策略：对话 → 结构摘要
格式:
  - topic: "讨论主题"
    decision: ["决策1", "决策2"]  # 关键决策
    context: "一句话上下文"
    user_pref: ["偏好1", "偏好2"]   # 用户偏好
    refs: ["文件引用路径"]           # 提到的文件/代码
```

**适用场景**：长期记忆、跨会话上下文传递

#### 第二层：代码/技术片段压缩 (Lossless)

```python
# 压缩策略：提取代码变更 + 技术决策，丢弃对话冗余
格式:
  refactored: "文件路径"
  change: "做了什么"
  reason: "为什么（关键）"
  before: "..."  # 仅关键行
  after: "..."   # 仅关键行
```

**适用场景**：技术讨论、代码审查记录

#### 第三层：文言压缩 (可选，试点)

```
# 把技术讨论压缩为文言风格的摘要

输入：
"我们讨论了用 FastAPI 替换 Flask 的方案，原因是 Flask 不支持异步，
而且 FastAPI 有更好的类型验证。最终决定下个版本迁移。"

文言输出：
"论迁Flask至FastAPI。Flask未协程，FastAPI实型检。决：下版迁。"
```

**适用场景**：长对话的极致压缩，但**不建议默认使用**，因为：
- 现代 LLM 已经支持长上下文（1M+ tokens），压缩收益递减
- 文言风格可能引入歧义
- 需要确认目标模型是否理解文言文

### 5.3 建议实施策略

```
Phase 10 实施路径：

步骤1：对话摘要引擎 (P0) ─── 3h
    ├── 实现 topic/decision/pref 提取
    ├── 支持压缩比率控制 (50%/70%/90%)
    └── 输出 JSON 格式

步骤2：代码片段提取 (P1) ─── 3h
    ├── 识别代码变更模式
    ├── 提取关键差异
    └── 保持语法正确

步骤3：文言试点 (P2) ─── 5h
    ├── 文言 API 开发
    ├── AB 测试框架
    └── 质量评估指标
```

### 5.4 AB 测试方案

```python
class CompressionABTest:
    """
    对照组：原始对话
    实验组：压缩后的对话
    
    指标：
    - 压缩率: original_tokens / compressed_tokens
    - 信息召回率: LLM 基于压缩内容回答问题 vs 基于原文
    - 用户满意度: 任务完成率对比
    """
    def evaluate(self, original: str, compressed: str):
        return {
            "compression_ratio": len(original) / len(compressed),
            "info_recall": self._test_recall(original, compressed),
            "task_success_rate": self._test_task(compressed),
        }
```

### 5.5 建议：先不做文言压缩

**理由**：
1. LLM 上下文窗口已达 1M tokens，压缩收益有限
2. 当前中文版用户量少，AB 测试统计意义不足
3. 文言风格可能降低模型理解准确度

**替代建议**：用"结构化摘要"替代"文言压缩"——JSON 格式的结构化压缩同样高效，且无歧义风险。

---

## 六、今次合并后续操作

```bash
# 1. 推送合并结果到远程（用户手动执行）
git push origin cn

# 2. 可选：更新上游对应的 main 分支（同步 fork 的 main）
git checkout main
git merge upstream/main
git push origin main
git checkout cn
```

---

## 七、项目状态总览

| 类别 | 完成 | 总数 | 完成度 |
|------|------|------|--------|
| **Phase 改造** | 9 | 10 | 🟢 90% |
| **上游合并** | 2 | 2 | 🟢 100% |
| **汉化工作** | 8 | 8 | 🟢 100% |
| **测试覆盖** | 基础 | - | 🟡 60% |
| **xb_native.py** | 0 | 1 | 🔴 0% |
| **P10 文言压缩** | 0 | 1 | 🔴 0% |

---

**维护者**：xyshanren  
**最后更新**：2026-05-03 14:01

# Hermes-Agent-CN 下一阶段规划

> **⚠️ 归档说明**：本文档生成于 2026-05-03，内容已过时。
> 当前规划请查阅 [`PLAN_CN.md`](PLAN_CN.md)（SmartRouter 增强、语义防火墙、Quickstart 扩展等）。
> 以下内容保留作为历史参考，不再更新。

---

**原生成时间**：2026-05-03 14:01  
**当前版本**：v0.14.0+cn.3（2026-06-02）  
**归档日期**：2026-06-02

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

全部完成。Phase 7 汉化覆盖：

| 文件 | 汉化内容 | 状态 | 行数 |
|------|---------|------|------|
| `hermes_cli/doctor.py` | 章节标题、检查项目、提示信息 | ✅ 完成 | ~57KB |
| `hermes_cli/setup.py` | 菜单、提示、确认信息（50+ 处） | ✅ 完成 | ~3000+行 |
| `hermes_cli/config.py` | 模块文档、函数文档字符串、关键注释 | ✅ 完成 | 49行汉化，4818行总量 |

参见 [CHANGELOG_CN.md](CHANGELOG_CN.md) v0.11.0-cn.1

---

## 二、下一步计划

### 📦 P0：高频函数内置为 Hermes Tool (xb_native.py) — 封存

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

### ✅ P0：更新文档和变更记录 — 已完成

| 文件 | 内容 | 预估工时 |
|------|------|----------|
| `CHANGELOG_CN.md` | 添加上游合并记录 | 1h |
| `README_CN.md` | 更新上游版本号 | 0.5h |
| `tests/test_cn_simple.py` | 验证上游合并后的中文完整性 | 0.5h |
| **合计** | | **2h** |

---

### ✅ P1：裁剪国外消息渠道 — 已完成

**状态**：`debloat` 系列提交（`565557984`、`8ca022074`、`1bc8225cb`）已完成 T1+T4 修剪。以下内容保留供参考。

**来源**：彻底本地化 — 只保留国内消息渠道

**决策**：采用**方案2（配置隐藏）**，短期内不动代码，只隐藏配置入口。

#### 推荐理由

| 维度 | 方案1: 彻底裁剪 | 方案2: 配置隐藏（推荐） |
|------|----------------|----------------------|
| 涉及代码量 | 删除 14 个文件，约 22,773 行 | 修改 setup/gateway 配置入口 |
| 上游合并冲突 | **每次更新必冲突** | **零冲突** |
| 恢复成本 | 从 git 历史找回 | 只需开放配置入口 |
| 安装体积 | 大幅减小 | 不变（代码为惰性导入，不占用运行时资源） |
| 推荐度 | ❌ 维护成本过高 | ✅ **建议采用** |

#### 实施路径

| 阶段 | 内容 | 预估工时 |
|------|------|----------|
| 1 | 修改 `hermes_cli/setup.py` — 从平台选择菜单移除国外渠道 | 1h |
| 2 | 修改 `hermes_cli/gateway.py` — 国内渠道作为默认推荐 | 1h |
| 3 | 配置 `.gitattributes` merge driver — 未来若执行方案1，自动解决冲突 | 0.5h |
| **合计** | | **2.5h** |

#### 远期备选

当上游更新频率降低（如月均 < 50 commits）后，可执行方案1彻底裁剪代码。

---

### 📦 P2：完善测试体系 — 封存

**来源**：当前测试覆盖不足

| 阶段 | 内容 | 预估工时 |
|------|------|----------|
| 1 | 补充集成测试（doctor/setup 实际调用） | 3h |
| 2 | 添加 CI 配置文件 (GitHub Actions) | 1h |
| 3 | 验证上游新功能兼容性 | 3h |
| **合计** | | **7h** |

---

### 📦 P2：界面和文档汉化 — 封存

**来源**：CHANGELOG_CN.md "待汉化项目"

#### TUI 界面

| 阶段 | 内容 | 预估工时 |
|------|------|----------|
| 1 | 扫描 `ui-tui/` 目录，标记英文文本 | 2h |
| 2 | 批量汉化 TUI 界面 | 4h |
| **小计** | | **6h** |

#### Web Dashboard

| 阶段 | 内容 | 预估工时 |
|------|------|----------|
| 1 | 扫描 `web/` 目录，标记英文文本 | 1h |
| 2 | 汉化 Dashboard 界面 | 3h |
| **小计** | | **4h** |

#### 文档网站 (website/)

| 阶段 | 内容 | 预估工时 |
|------|------|----------|
| 1 | 扫描 `website/` 目录，评估汉化范围 | 1h |
| 2 | 汉化核心文档页面 | 4h |
| **小计** | | **5h** |

---

### 📦 P2：Phase 10 — 结构化摘要（代替文言压缩）— 封存

**来源**：改造方案 2.0 的 Phase 10

**决策**：先用"结构化摘要"替代"文言压缩"，文言试点保留在计划中暂不执行。

---

#### 为什么先不做文言压缩

| 原因 | 说明 |
|------|------|
| **上下文窗口足够大** | 现代 LLM 支持 1M+ tokens，文言压缩的收益递减 |
| **岐义风险** | 文言文天然有歧义，可能降低模型理解准确度 |
| **AB 测试条件不成熟** | 当前用户量小，统计意义不足 |
| **结构化摘要已够用** | JSON 格式的结构化压缩同样高效，零歧义 |

#### 实施路径

| 阶段 | 内容 | 预估工时 |
|------|------|----------|
| 1 | 对话摘要引擎 (topic/decision/pref 提取) | 3h |
| 2 | 代码/技术片段压缩（提取关键差异） | 3h |
| 3 | 支持压缩比率控制 (50%/70%/90%) | 1h |
| **合计** | | **7h** |

---

### ✅ P0：发布 v0.12.0-cn.1 — 已完成（已发布 v0.14.0+cn.3）

**来源**：首个中文稳定版本

**前置条件（全部满足 ✅）**：

| 条件 | 状态 |
|------|------|
| xb_native.py P0 工具 | ✅ 已完成（5 个工具） |
| CHANGELOG_CN.md 和 README_CN.md 同步上游 | ✅ 已完成（v0.12.0+） |
| 测试覆盖率达标 | ✅ 34 个测试全部通过 |
| 消息渠道裁剪 | ✅ 12 个国外渠道隐藏 |
| TUI + Dashboard 汉化 | ✅ 已完成 |

**何时发布**：你在当前版本使用一段时间后，随时喊我就行。

| 阶段 | 内容 | 预估工时 |
|------|------|----------|
| 1 | 版本号更新和 Release Note | 1h |
| 2 | 最终测试和问题修复 | 2h |
| 3 | 发布 tag + GitHub Release | 0.5h |
| **合计** | | **3.5h** |

---

### 📦 待定（等待用户量或 Star 数增长）— 封存

以下两项暂不执行，等用户数上来或 Star 数达到一定量后再考虑：

- 📖 **文档网站汉化** (website/) — 5h — 当前用户量小，汉化收益有限
- 🔧 **Phase 10 结构化摘要** — 7h — 现有上下文窗口足够大，暂不需要

---

#### 触发条件

文言试点需要 **三个条件同时满足** 才启动：

**条件1：上下文压力信号**

| 指标 | 触发阈值 | 含义 |
|------|---------|------|
| 上下文占用率 | 单次会话持续占用 80%+ 上下文 | 结构化摘要不够用了 |
| 压缩频率 | 每次会话需手动 /compress 2次+ | 压缩成为操作瓶颈 |

**条件2：模型文言能力验证通过**

| 指标 | 触发阈值 |
|------|---------|
| 古文理解 | 模型（deepseek/zai）能准确转述文言摘要含义，答对率 ≥ 90% |
| 信息召回率 | 文言摘要的信息召回率 ≥ JSON 版本（A/B 测试） |

**条件3：用户反馈信号**

```
"结构化摘要虽然 token 少，但技术讨论的细节丢失了"
"我需要把整个会话历史带进新上下文，但 JSON 摘要不够用"
"在这个大项目里，每轮都要回顾之前的上下文，token 不够了"
```

**一句话归纳**：结构化摘要先跑着，哪天你觉得"JSON 摘要丢信息了，上下文又不够"，就切到文言试点。在那之前不必操心。

---

### 📦 P3：定期合并上游 (他人或后续) — 封存

- 建议 **每 2 周** 检查一次上游更新
- 使用 `git remote add upstream https://github.com/NousResearch/hermes-agent.git`（已配）
- 流程：`git fetch upstream main && git merge upstream/main --no-ff`

---

## 三、实施路线图（📦 封存 — 历史参考）

```
本周（全部完成）
├── ✅ P0: xb_native.py — 5 个工具
├── ✅ P0: 文档同步 (CHANGELOG_CN/README_CN)
├── ✅ P1: 消息渠道裁剪 — 12 个国外渠道隐藏
├── ✅ P1: 测试体系完善 — 34 个测试 + CI
├── ✅ P2: TUI 界面汉化 — content/ + helpHint
├── ✅ P2: Web Dashboard 汉化 — i18n 中文就绪

随时（等你通知）
└── ✅ P0: 发布 v0.12.0-cn.1（前置条件已全部满足）

待定（等待用户量或 Star 数增长）
├── 📖 文档网站汉化 (website/)
├── 🔧 Phase 10 结构化摘要
├── 🔄 定期合并上游
└── ⏸️ 文言试点（等待三条件触发）
```

---

## 四、设计建议：高频函数内置为 Hermes Tool (xb_native.py)（📦 封存 — 设计参考）

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

## 五、设计建议：Phase 10 — 结构化摘要（📦 封存 — 设计参考）

### 5.1 问题分析

**目标**：将长对话/长上下文压缩为结构化摘要，大幅减少 token 消耗。

**为什么不用文言压缩**：

| 维度 | 结构化摘要 | 文言压缩 |
|------|-----------|----------|
| 信息保留 | 结构化，零歧义 | 文言文有多义性 |
| 模型兼容性 | 所有模型通用 | 需要模型理解古文 |
| 压缩率 | 50-80%（够用） | 70-90%（更好但风险高） |
| 开发成本 | 低（JSON 处理） | 高（文言生成 + 验证） |

### 5.2 建议架构：双通道压缩

```
原始对话
   │
   ├──→ 通道A：对话摘要 (Lossy)
   │     ├── topic（讨论主题）
   │     ├── decision（关键决策）
   │     ├── context（一句话上下文）
   │     ├── user_pref（用户偏好）
   │     └── refs（文件引用）
   │
   └──→ 通道B：代码/技术片段 (Lossless)
         ├── file（文件路径）
         ├── change（变更内容）
         ├── reason（变更原因）
         └── diff（仅关键行）
```

### 5.3 压缩率控制

```python
class CompressionConfig:
    """压缩配置，支持不同压缩率"""
    ratios = {
        "light": 0.5,   # 保留 50% 内容，只丢弃冗余对话
        "medium": 0.7,  # 保留 30% 内容，合并相似主题
        "aggressive": 0.9,  # 保留 10% 内容，仅核心决策
    }
```

### 5.4 文言试点触发条件（预留）

保留在计划中，**三个条件同时满足时启动**：

1. **上下文压力**：单次会话持续占用 80%+ 上下文窗口，或每次会话需手动 /compress 2次+
2. **模型能力**：deepseek/zai 对古文理解准确率 ≥ 90%，且文言摘要信息召回率 ≥ JSON
3. **用户反馈**：你主动反馈"结构化摘要丢细节了，需要更极致的压缩"

启动后实施步骤：
- 文言 API 开发（将结构化摘要转为文言文）
- AB 测试框架（对比文言 vs JSON 的信息召回率）
- 质量评估指标（压缩率、召回率、任务完成率）

---

## 六、今次合并后续操作（✅ 已完成）

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
| **上游合并** | 1 | 1 | 🟢 100% |
| **汉化工作** | 10 | 12 | 🟢 83% |
| **测试覆盖** | 34 | 34 | 🟢 100% |
| **xb_native.py** | 5 | 5 | 📦 封存（无实际需求） |
| **消息渠道裁剪** | 12 | 12 | 🟢 100%（已完成） |
| **SmartRouter M1/M2** | 2 | 2 | 🟢 100%（详见 PLAN_CN.md） |
| **代码裁剪 T1+T4** | 16+22 | 16+22 | 🟢 100%（详见 PLAN_CN.md） |
| **TUI 汉化** | 5 | 5 | 🟢 100% |
| **Web Dashboard** | 342 | 342 | 🟢 100%（i18n 键） |
| **v0.14.0+cn.3 发布** | — | — | ✅ 已完成 |
| **quickstart 修复** | 4 | 4 | 🟢 100%（embedding 过滤/doctor 兼容等） |

---

**维护者**：xyshanren  
**最后更新**：2026-06-02 | **归档确认**：本文件所列规划已全部完成或封存，当前工作请查阅 [PLAN_CN.md](PLAN_CN.md)

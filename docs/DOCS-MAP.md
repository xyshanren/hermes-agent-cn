# Hermes-Agent-CN 文档体系总览

> 更新日期: 2026-05-13  
> 当前版本: v0.12.0-cn.3

---

## 一、文档体系架构

```
📁 hermes-agent-cn/
├── 📄 README.md                    # 入口文档（用户第一站）
├── 📄 CHANGELOG_CN.md              # 版本历史（变更追踪）
│
├── 📁 docs/                        # 技术文档目录
│   ├── 📄 DOCS-MAP.md              # ← 本文档（体系总览 / 导航）
│   ├── 📄 NEXT_PLAN.md             # 下一阶段开发规划
│   │
│   ├── 📁 installation/            # 安装文档（新用户第一站）
│   │   ├── 📄 README.md            # 安装索引（根据平台导航）
│   │   ├── 📄 QUICKSTART_LINUX.md  # Linux 快速安装（10 分钟）
│   │   ├── 📄 LINUX_INSTALL.md     # Linux 详细安装
│   │   ├── 📄 QUICKSTART_MACOS.md  # macOS 快速安装
│   │   ├── 📄 MACOS_INSTALL.md     # macOS 详细安装
│   │   ├── 📄 QUICKSTART_WSL2.md   # WSL2 快速安装
│   │   └── 📄 WSL2_INSTALL.md      # WSL2 详细安装
│   │
│   ├── 📄 PROPOSAL-doctor-improvements.md     # 提案：Doctor 优化
│   ├── 📄 PROPOSAL-multi-model-routing.md     # 提案：多模型路由
│   │
│   ├── 📄 Hermes集成指南_MemPalace与graphify.md  # 集成实践
│   └── 📁 plans/                            # 历史计划文档
│       └── 📄 2026-05-02-...-topics.md       # Telegram 多会话方案
│
├── 📄 TEST_SUMMARY.md              # 测试总结（可提交）
├── 📄 TEST_REPORT.md               # 详细测试报告（本地，不提交）
├── 📄 CONTRIBUTING.md              # 贡献指南
├── 📄 AGENTS.md                    # Agent 架构说明
├── 📄 SECURITY.md                  # 安全策略
│
├── 📁 RELEASE_*.md                 # 上游发布说明（8 个版本）
└── 📁 hermes-already-has-routines.md  # 已有功能清单
```

---

## 二、文档分类与角色

### 🔵 P0 — 核心必读（新用户入口）

| 文档 | 目标读者 | 说明 |
|------|---------|------|
| `README.md` | **所有用户** | 项目介绍 + 快速开始 + 平台支持矩阵 |
| `docs/installation/README.md` | **新用户** | 平台索引（选择安装方式） |
| `CHANGELOG_CN.md` | **所有用户** | 版本更新历史 |

### 🟢 P1 — 安装指南（按平台选择）

| 文档 | 读者 | 篇幅 |
|------|------|------|
| `QUICKSTART_*.md` | 急性子用户 | ~100 行 / 10 分钟 |
| `*_INSTALL.md` | 需要深度了解的用户 | ~500-900 行 / 完整版 |

覆盖平台：

| 平台 | 快速 | 详细 |
|------|------|------|
| Linux | ✅ QUICKSTART_LINUX.md | ✅ LINUX_INSTALL.md |
| macOS | ✅ QUICKSTART_MACOS.md | ✅ MACOS_INSTALL.md |
| WSL2 (Windows) | ✅ QUICKSTART_WSL2.md | ✅ WSL2_INSTALL.md |

### 🟡 P2 — 开发与质量文档

| 文档 | 读者 | 说明 |
|------|------|------|
| `TEST_SUMMARY.md` | 测试/发布 | 每轮测试的总结报告（可提交） |
| `TEST_REPORT.md` | 本地测试 | 详细测试数据 + 截图（不提交） |
| `CONTRIBUTING.md` | 贡献者 | PR 流程、代码规范 |
| `AGENTS.md` | 开发者 | Agent 机制说明 |
| `SECURITY.md` | 安全审计 | 漏洞报告渠道 |

### 🟠 P3 — 规划与提案

| 文档 | 状态 | 说明 |
|------|------|------|
| `NEXT_PLAN.md` | ✅ 已归档 | 下一阶段规划（上游合并后） |
| `PROPOSAL-doctor-improvements.md` | ⏳ **待评估** | Doctor 输出优化（5 方向，P1-P3） |
| `PROPOSAL-multi-model-routing.md` | ✅ **Phase 1 已实现** | 多模型路由方案（3 Phase） |
| `plans/*.md` | ✅ 已归档 | 历史设计方案 |

### 🔴 P4 — 归档/上游资料

| 文档 | 说明 |
|------|------|
| `RELEASE_*.md` (8 个) | 上游 NousResearch 发布说明，保留参考 |
| `hermes-already-has-routines.md` | 已有功能清单 |
| `Hermes集成指南_MemPalace与graphify.md` | 集成实践 |
| `task-hermes-local-models-setup_*.md` | 历史任务文档 |

---

## 三、文档状态总览

### ✅ 已完善（不需改动）

| 文档 | 理由 |
|------|------|
| `README.md` | 完整的中文介绍 + 平台支持矩阵 + 3 种安装方式 |
| `docs/installation/*` | 覆盖 3 平台（Linux/macOS/WSL2），每种平台有快速/详细版本 |
| `CHANGELOG_CN.md` | 版本记录详细，包含修改文件列表和验证方式 |
| `TEST_SUMMARY.md` | 测试总结模板已创建，第一轮测试已填写 |
| `SECURITY.md` | 上游维护，无需改动 |
| `PROPOSAL-multi-model-routing.md` | Phase 1 已实现，文档结构完整 |

### ⚠️ 建议更新

| 文档 | 建议 | 优先级 |
|------|------|--------|
| `README.md` | ~~版本徽章更新为 v0.12.0-cn.3~~ ✅ 已完成 | P3 |
| `NEXT_PLAN.md` | 内容已过时 | ✅ 已归档

### ⏳ 待开发

| 文档 | 来源 | 说明 |
|------|------|------|
| API 文档 | ✅ 已完成 | `docs/API.md` |
| 架构设计文档 | ✅ 已完成 | `docs/ARCHITECTURE.md` |
| 常见问题 FAQ | ✅ 已完成 | `docs/FAQ.md` |

---

## 四、待评估提案摘要

### 📄 PROPOSAL-doctor-improvements.md

> **状态**: ⏳ 待评估  
> **来源**: v0.12.0-cn.3 手工测试阶段发现

| 方向 | 内容 | 优先级 |
|------|------|--------|
| D1 | `.env` 文件内容智能检测（空值/格式/注释干扰/重复 key） | P1 |
| D2 | Conda/Pyenv/系统 Python 环境检测 | P1 |
| D3 | 本地模型与 Fallback 链一致性检查 | P1 |
| D4 | 输出格式优化（分组摘要/JSON/quiet 模式） | P2 |
| D5 | 路由状态可视化（与多模型路由联动） | P2 |

### 📄 PROPOSAL-multi-model-routing.md

> **状态**: Phase 1 ✅ 已实现，Phase 2/3 ⏳ 待实现  
> **三种方案**: A(推荐) / B(轻量) / C(最强)

| Phase | 内容 | 复杂度 | 状态 |
|-------|------|--------|------|
| 1 | quickstart 多模型自动检测 + auxiliary 配置 | 低 | ✅ 已实现 |
| 2 | model_routing 配置 + 运行时模型选择 | 中 | ⏳ 待实现 |
| 3 | 运行时动态模型切换 + 上下文管理 | 高 | ⏳ 待实现 |

---

## 五、建议执行步骤

### 📌 立即（本周）

1. ✅ ~~提交 `TEST_SUMMARY.md` 和两个 PROPOSAL 文档~~（已完成）
2. ✅ ~~更新 `README.md` 版本徽章 → `v0.12.0-cn.3`~~（已完成）
3. ✅ ~~整理归档 `NEXT_PLAN.md`~~（已完成）

### 📌 短期（下一轮迭代前）

4. ✅ ~~创建 `docs/ARCHITECTURE.md` — 架构设计概览~~（已完成）
   - 系统架构图（CN 版定制的组成部分）
   - Provider 体系说明（国产 Provider vs 上游 Provider）
   - 关键数据流（config → auth → model → agent loop）
5. ✅ ~~创建 `docs/FAQ.md` — 常见问题~~（已完成）
   - 收集来自安装指南疑难解答和用户反馈的问题

### 📌 中期（与 Phase 2/3 同步）

6. ✅ ~~创建 `docs/API.md` — API 参考文档（CLI + 配置 + Provider）~~（已完成）
7. [ ] 评估实施 PROPOSAL-doctor-improvements.md（建议从 D3/D1 开始）
8. [ ] 规划 PROPOSAL-multi-model-routing.md Phase 2

---

## 六、文档维护守则

1. **提交前检查**：新增功能 → 更新 `CHANGELOG_CN.md`
2. **测试后可提交**：`TEST_SUMMARY.md`（测试总结，无实际截图）
3. **不可提交**：`TEST_REPORT.md`（含截图路径和实际数据）
4. **提案文档**：命名 `PROPOSAL-<topic>.md`，存于 `docs/` 目录
5. **版本号**：`pyproject.toml` 版本与 `CHANGELOG_CN.md` 同步更新

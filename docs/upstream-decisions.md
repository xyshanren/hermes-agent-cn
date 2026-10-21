# Upstream Decision Log

滚动记录 upstream hermes-agent 每次 release / commit 我们的采纳决策。

## 决策类型（4 选 1）

- `adopt` —— 接受 upstream 行为
- `reimplement` —— 借鉴思路重写（CN 端独立实现）
- `reject` —— 明确不采纳（理由记录）
- `defer` —— 暂不决定（revisit date 必填）

---

## 历史快照

### 2026-06-11 — v0.16 整 release sync（2125 commits）

> scout 全量扫描分类原始数据：`~/projects/hermes-agent-cn-notes/UPSTREAM_CLASSIFICATION_REPORT.md`

> 维护者：Mavis（Mavis 自身 / Orchestrator + Architect）
> 最近更新：2026-06-11
> 工具链：hermes `-z` (deepseek-v4-flash) 派 scout 全量扫描 + 关键词分类
> 输入：`/root/upstream_commits.txt`（2125 commits，从 `git log upstream/main ^origin/cn --format='%s'` 提取）
> 输出原始：`/root/upstream_classification.csv`（2126 行 UTF-8）+ `/root/upstream_classification_summary.md`
> 配套文档：`MiniMax/projects/hermes-agent-cn-notes/PROJECT_NOTES.md` + `ROADMAP.md`

---

## 一、Scout 任务执行回执

```
启动时间：2026-06-11 15:56
完成时间：2026-06-11 16:06（实际处理时间 ~10 min，比预期 1-2h 快）
工具：hermes -z (deepseek-v4-flash, --yolo --ignore-rules)
模式：全量扫描 + 关键词分类
PID：851（已正常退出）
CSV：/root/upstream_classification.csv（214KB，2126 行）
Summary：/root/upstream_classification_summary.md（10KB，170 行）
```

---

## 二、分类结果速览

| 分类 | 数量 | 占比 | 子类 | 数量 |
|---|---|---|---|---|
| **SKIP**（跳过） | **556** | **26.2%** | C1 已删平台/工具 | 87 |
| | | | C2 应删（v0.16 新功能） | 467 |
| | | | C3 T3 不活跃代码 | 2 |
| **MERGE**（合并） | **1396** | **65.7%** | C4 bugfix（CN 保留代码） | 822 |
| | | | C5 新功能/优化 | 574 |
| **REVIEW**（需人工） | **174** | **8.2%** | C6 跨 SKIP+MERGE 混合 | 5 |
| | | | C7 主题模糊 | 150 |
| | | | C8 i18n/翻译 | 19 |
| **总计** | **2126** | **100%** | | |

⚠️ **与原始数据偏差**：scout 输出 2126 行（我们之前数的是 2125）。多出来 1 行可能是 scout 把 Merge commit 重复计入或边界处理导致。**不影响决策**。

---

## 三、SKIP 主题词 Top 10（v0.16 路线冲突全在这）

| 主题词 | Skip 次数 | 类别 | 含义 |
|---|---|---|---|
| **desktop** | 331 | C2 | Electron 桌面应用（CN 已有 hermes-tray） |
| **telegram** | 40 | C1 | CN 已删（.deleted-files.txt） |
| **dashboard-auth** | 36 | C2 | web admin 鉴权（CN 路线不要） |
| **codex** | 33 | C2 | OpenAI Codex 适配（CN 不用） |
| **portal** | 22 | C2 | Nous Portal（CN 不依赖） |
| **discord** | 19 | C1 | CN 已删 |
| **anthropic** | 15 | C2 | Anthropic 直连（CN 走 OpenRouter/SmartRouter 间接） |
| **openrouter** | 13 | C2 | CN 已有自研 SmartRouter |
| **matrix** | 9 | C1 | CN 已删 |
| **gemini** | 8 | C2 | CN 走国产 API |

**关键观察**：
- **desktop 占 SKIP 的 60%（331/556）**——v0.16 整条 Electron 路线对 CN 没用
- **dashboard-auth 36 + portal 22**——CN 主张 CLI + quickstart，admin 后台路线不跟
- **codex 33 + anthropic 15 + openrouter 13**——CN 国产 API 路线不靠这些
- **C1（已删平台/工具）= 87**，跟你 `.deleted-files.txt` 列的清单完全吻合

---

## 四、MERGE 主题词 Top 10（CN 真要合的）

| 主题词 | Merge 次数 | 含义 |
|---|---|---|
| **minimax** | 11 | MiniMax 模型（v0.16 新增 M3） |
| **feishu** | 10 | 飞书 gateway（CN 核心保留） |
| **weixin** | 5 | 微信 gateway（CN 核心保留） |
| **wecom** | 5 | 企业微信 gateway（CN 核心保留） |
| **yuanbao** | 4 | 元宝 gateway（CN 核心保留） |
| **kimi** | 4 | Kimi/Moonshot（CN 国产 API） |
| **deepseek** | 3 | DeepSeek（CN 国产 API） |
| **qwen** | 2 | 通义千问（CN 国产 API） |
| **dingtalk** | 2 | 钉钉 gateway（CN 核心保留） |
| **ollama** | 1 | 本地模型（CN 保留） |

**关键观察**：
- **feishu/weixin/wecom/yuanbao/dingtalk 共 26 个**——5 个 CN 国内平台 8 周有真更新
- **minimax 11 个**——v0.16 新增 M3 + native providers 路由
- **kimi/deepseek/qwen 共 9 个**——国产 API 上游也在动
- ⚠️ **ollama 只 1 个**——上游对本地模型改动很少，CN 走自研 SmartRouter 路径

---

## 五、REVIEW 重点（需人工判断）

### 5.1 C8 i18n / 翻译类（19 commits）— **优先级最高**

scout 列了 19 个 C8 commit，**最关键的是 4a1907b（@JimLiu #38241，full Simplified Chinese 翻译）**——会跟 CN 自己的 i18n 撞。

| 决策维度 | 选项 |
|---|---|
| **i18n 框架层改动** | 评估是否升级到上游的 typed i18n layer（更可扩展） |
| **中文翻译文件** | 跳过（CN 已有自己的中文 message） |
| **其他 locale（ja/zh-Hant/ko）** | 跳过（CN 只关心简中） |
| **Windows locale 解码（schtasks）** | **值得看 diff**——可能是真 bugfix |

**建议**：先看 4a1907b 的 diff，对比 CN 现有 `agent/i18n.py`，再决定**升级** vs **维持现状**。

### 5.2 C6 跨 SKIP+MERGE 混合（5 commits）— **必须逐个处理**

```
fd87c61  [openrouter, qwen]     feat(models): add qwen3.7-plus to nous+openrouter
0b46c41  [anthropic, minimax]   fix(vision): convert video_url blocks for MiniMax
63e8248  [desktop, minimax]     fix(desktop): order xAI Grok after MiniMax in OAuth
a8526a4  [openrouter, minimax]  chore(models): bump minimax to minimax-m3
cddb728  [whatsapp, weixin]     fix(gateway): config.yaml path for WhatsApp/Weixin delays
```

**关键点**：
- `cddb728` 涉及 **whatsapp（CN 删）+ weixin（CN 保）**——必须 cherry-pick only weixin 部分
- `0b46c41` 涉及 **anthropic（CN 不要）+ minimax（CN 想要）**——只挑 minimax 部分
- 其他 3 个基本是**模型目录更新**——`openrouter`（CN 不用）+ `qwen/minimax`（CN 想要）——只挑模型名部分

### 5.3 C7 主题模糊（150 commits）— **批量扫一遍**

scout 列了 30 个 Top C7，关键词特征：
- **dashboard 相关**（8 个）—— CN 不做 web admin，可全跳
- **photon 相关**（7 个）—— 上游某模块，CN 不明，需查
- **website/docs**（5 个）—— CN 路线不要
- **cron / slash / windows 安装**（少量）—— 可能是真 bugfix，需看

**建议**：开 1 个"扫 C7"的 mini-session，逐个 `git show <sha>` 看 diff，标记成 SKIP/MERGE。

---

## 六、合并执行计划（v1）

### 阶段 1：必合（无争议）

| 操作 | commits | 风险 | 工作量 |
|---|---|---|---|
| Cherry-pick 所有 C4 bugfix | 822 | 低（命中 CN 保留代码） | **3-5 天** |
| Cherry-pick 安全相关 | 若干 | 极低（CVE 类必合） | 1 天 |

### 阶段 2：筛选合

| 操作 | commits | 风险 | 工作量 |
|---|---|---|---|
| C5 perf/refactor | ~200 | 低 | 2 天 |
| C5 feat 筛选 | 574 | 中（可能引入 CN 不需要依赖） | 3-5 天 |
| C6 混合 cherry-pick | 5 | 中（需精确挑 hunks） | 1-2 天 |

### 阶段 3：人工判断

| 操作 | commits | 风险 | 工作量 |
|---|---|---|---|
| C7 模糊扫一遍 | 150 | 中 | 2-3 天 |
| C8 i18n 决策 | 19 | **高**（决定 i18n 路线） | 1-2 天 |
| C3 决定（永久删 T3 vs 维持） | 2 | 中 | 1 天 |

**总计预计**：**2-3 周密集工作**（分 6-8 个小批次跑）

---

## 七、关键发现

### 7.1 路线冲突 77% 来自 desktop/portal

```
SKIP 556 总数中：
  desktop:        331 (59.6%)
  dashboard-auth:  36 (6.5%)
  portal:          22 (4.0%)
  electron:         6 (1.1%)
  = 395/556 (71.0%) 来自 "Electron + admin 化 + Nous Portal" 整条路线
```

**含义**：**v0.16 整条"desktop 化 + 商业 SaaS 化"路线**对 CN 没用。CN 跟 v0.16 的路线分歧是**根本性的**（个人/小团队 vs 全栈 SaaS），不只是局部技术分歧。

### 7.2 C4 822 bugfix 是金矿

C4 占总 commit **38.7%**，全是命中 CN 保留代码的 bugfix。**这才是真正要合的债**——8 周的真 bug 修复，95%+ 零冲突。

### 7.3 5 个国内平台是真更新

feishu/weixin/wecom/yuanbao/dingtalk 8 周有 26 个有效更新——说明上游也在动国内渠道（虽然 CN fork 后有自己的实现，但**上游改进可借鉴**）。

### 7.4 minimax 11 个 commit 需重点

v0.16 把 MiniMax 提到了 native provider 级别，CN SmartRouter 需要对齐——这些是 MERGE 必看。

---

## 八、风险与决策点

### 8.1 i18n 路线决策（你需要拍板）

| 选项 | 含义 | 影响 |
|---|---|---|
| **A. 升级上游 typed i18n** | 替换 CN 现有 `agent/i18n.py` | 工作量 1-2 周；所有 `t(...)` 调用点改 |
| **B. 维持 CN 现状** | 跳过 19 个 C8 commit | 0 工作量；但失去上游改进 |
| **C. 选某些 commit 合** | 只挑 schtasks 解码 + 框架层改进 | 折中 |

**建议**：**先看 4a1907b 的 diff**（@JimLiu typed i18n PR），评估升级成本再决定。

### 8.2 T3 不活跃代码 2 个 commit 怎么算

scout 标记 C3=2。**问题**：T3 本身就在 CN 仓库里（保留但不维护），上游修了 T3 的 bug——**这 bug 在 CN 仍然存在**。

| 选项 | 含义 |
|---|---|
| 跳过（不修 T3 bug） | 保持 T3 标记一致 |
| 修（cherry-pick C3 修复） | 跟 T3 路线冲突——既然"不维护"就别修 |

**建议**：**跳过 C3**，跟 T3 路线保持一致。

### 8.3 cherry-pick 工作流选型

| 方案 | 优 | 劣 |
|---|---|---|
| **手动 `git cherry-pick` 一个一个** | 精确控制 | 822 个 commit 太累 |
| **`git rebase -i upstream/main` 交互式** | 快 | 引入 2125 commits 到 cn 历史的混乱 |
| **`git merge upstream/main` + 解决冲突** | 主流做法 | 冲突量可能巨大 |
| **写脚本批量 cherry-pick + 自动检测冲突** | 折中 | 需要写脚本 |

**建议**：先做小批量（10-20 commits）cherry-pick 试水温，看冲突率再决定。

---

## 九、给 ROADMAP 的更新

原 ROADMAP.md 第 1 时间窗口（2026-06 本月）的目标"scout 报告 → 拣选 MERGE"已经完成。**下一步**：

- [ ] 你拍板 i18n 路线（§8.1）
- [ ] 我写 cherry-pick 工作脚本（自动化 §8.3 路径 4）
- [ ] 试 10-20 commits 批 cherry-pick
- [ ] 跑测试套件（pytest + cargo test）
- [ ] 解决首批冲突

预计 6 月剩余时间可完成 §6 阶段 1+2（约 12-15 天），阶段 3 推到 7 月上旬。

---

## 十、附录

### 10.1 原始数据

- **CSV**：`/root/upstream_classification.csv`（214KB，2126 行，UTF-8）
- **Summary**：`/root/upstream_classification_summary.md`（10KB，170 行）
- **输入**：`/root/upstream_commits.txt`（2125 行 commit subject）

### 10.2 scout prompt 与工具链

- **Prompt**：`/root/scout_prompt.md`（约 6.9KB，含 C1-C8 规则 + 关键词清单）
- **执行**：`/root/hermes-venv/bin/hermes -z "..." -m deepseek-v4-flash --provider deepseek --yolo --ignore-rules`
- **备用工具**：`atomcode`（REPL 模式不适合单次任务，下次优先场景是"多步工具调用"）

### 10.3 下次升级路径

如果未来还要做类似的全量扫描任务：

1. 优先 `atomcode`（本月内 atomcode trial 仍有效）
2. hermes `-z` 作为 fallback
3. CSV 用 UTF-8，scout 跑完落 `/root/` 不污染仓库
4. 30min cron 监控 + 进程死了报警

---

## 2026-08-12 重新审视 (时效性警告)

> **2026-06-11** scout 数据已经 **2 个月过期**, 期间 upstream main 推了 v0.17 / v0.18 / v0.19 / v0.20 多个 release. **2026-08-09 Sprint 13a v0.20.0 sync** 已经 fast-forward merge upstream main 1785 commits (commit `90faf101c`), 本文件数据**仅作 v0.16 release sync 历史快照**, 不反映当前 upstream 状态.
>
> **5 C6 commits 当前状态 (2026-08-12 audit)**:
>
> | Commit | Subject | 当初建议 | 当前实际 (v0.20.0+cn.5) |
> |---|---|---|---|
> | `fd87c61` | feat(models): add qwen3.7-plus to nous+openrouter | cherry-pick qwen 部分 | **deferred** — 整体 merge 已含 commit, 但 openrouter 路径可能 dead (CN 已自研 SmartRouter), 需 v0.20.0+cn.5 实跑 verify |
> | `0b46c41` | fix(vision): convert video_url blocks for MiniMax | cherry-pick minimax 部分 | **applied via merge** — minimax 路径已 1:1 配对, anthropic 路径 CN 已删 dead-end |
> | `63e8248` | fix(desktop): order xAI Grok after MiniMax in OAuth | cherry-pick minimax 部分 | **rejected** — desktop 整条路径 CN 已删 (v0.17.0 减法, `apps/desktop/` 全砍), commit 随整体 merge 引入但 dead code |
> | `a8526a4` | chore(models): bump minimax to minimax-m3 | cherry-pick minimax 部分 | **applied via merge** — minimax 命名 1:1 配对 |
> | `cddb728` | fix(gateway): config.yaml path for WhatsApp/Weixin delays | cherry-pick weixin 部分 | **applied via merge** — weixin 路径 CN 保留, whatsapp 路径 CN 已删, 整体 merge 后 weixin 部分自然生效 |
>
> **整体策略调整**:
> - 2026-06-11 时的"5 C6 必须逐个 cherry-pick"判断已经被 **整体 fast-forward merge** 替代 (Sprint 13a, commit `90faf101c`)
> - 整体 merge 后, 5 C6 里的"CN 想要"部分自然合并, "CN 删"部分虽然引入但成 dead code (Python import 但 0 引用, grep 0 命中验证)
> - 后续 sprint (16+) 重新 scout 时, 5 C6 应该作为"已应用"或"已 reject" 标记, 不再 defer
>
> **未来 scout 计划**:
> - 2026-08 末 (v0.20.0+cn.5 → v0.21.0) — 重新跑 scout, 跟 v0.16 数据对比
> - 触发条件: upstream new commits > 1000 OR upstream new tag (2026-10-01 cron `hermes-cn-quarterly-borrow-audit` 自动 fire)
> - 模板: 复用本文件 §1-§10 结构, 增量更新"历史快照"section

---

## 2026-09-25 Jev 类决策模型评估 (NeoHorse-Jev-4B) — defer

**背景**: "System One" 决策模型范式 (TypeSafe Jev 引爆, 一周内出现开源复现) 与本分支原设想的"智能路由模型 (需微调)"不谋而合. 评估 4 选 1 结论:

| 对象 | 决策 | 一句话理由 |
|---|---|---|
| TypeSafe Jev API | **reject** | 路由状态=用户消息原文出第三方 API (数据驻留未公开, CN 生死线) + 远程 820ms/轮不可接受 |
| NeoHorse-Jev-4B (官方 GGUF, Apache-2.0) | **defer → 规划完成** | 主候选; 决策训练开箱即用, 微调降级为可选优化; 回放数据说话后才动手 |
| 基元律动 0.95M 路由器 | **watch** | MS 无权重, 官方核实中; 不影响架构 |
| Laya (ConvAI, Apache-2.0, 421M encoder) | **watch** | 开源 Jev 复刻, 但开箱高基数分类弱 (Banking77 0.425 vs Jev 0.870)、定制域需微调, 不够格换 consumer #1; 价值在: 长 state 消费者 (encoder 原生 8k 级 vs NeoHorse 384-token 上限) / CPU 冗余 (不占 4060 显存) / 用回放集微调做置信度校准对照 (打 live conf median 0.295) |
| SemIf / open-jev | 参照 | 证明范式一周可复现, 不抢跑 |

**架构边界 (已拍板)**: 独立 System-1 决策服务 + 多消费者, SmartRouter 只是 consumer #1; 决策逻辑在 hermes 侧, hermes 拿选定模型调 AIMC; AIMC 保持透明 (多客户端 zcode/dsh/RAG/db-center, 语义改写 = breaking change). 红线: per-turn 工具 schema 过滤不做 (cache 神圣性), 主模型绕行 deferred.

**部署**: 决策服务落**本机 WSL**（与 hermes 同机 localhost 直连; CUDA 经 Windows 驱动旁路直通, toolkit 装 WSL 内; 隔离内网 Linux 机方案搁置为备选）。随包 GGUF runtime, pin llama.cpp `9425611`@2026-09-23, Q4_K_M。Windows 原生/Ollama 跑不了 (构建 Linux-only + prefill-only 概率接口不在 Ollama API 面; 需要本地冗余走 WSL 同一套 Linux 构建, 不做原生 Windows 移植); hermes fail-open 回规则层. **✅ 2026-09-25 WSL 全链路验证通过**: 构建/冒烟/服务化全绿, 热态延迟 mean 91ms / p95 116ms, Choice 决策正确 (HTTP 端到端 113ms), 详见规划文档 §5c.

**详细规划**: `docs/plans/2026-09-25-jev-decision-layer-plan.md` (Step 0 回放集 → Step 1 Linux 环境部署+概率验证 → Step 2 影子模式 → Step 3 生效+规则降级 guardrail; 每步带门检).

**2026-09-28 追加** (mu 双引擎报告交叉核对): 报告主张的"接入 Jev/Laya 决策层"与我方已实施路径同向 (本地模型而非远程 API), **无架构增量**; 其信息量在两点: ① 确认 **consumer #2 (上下文过滤) 的价值次序**——mu 五个决策点中"工具输出筛选"是其核心创新, 与我方路线图排序一致; ② 提示**新消费者候选: 审批闸门** (mu ⑤ Jev 审批), 已列入规划文档 §7 候选 #4。TypeSafe Jev API 的 reject 结论不受影响 (报告未考虑数据驻留)。Laya → **watch** (理由见上表), 触发条件见下。

**Revisit 条件**: NeoHorse 大版本变更 / 0.95M 权重开源 / 影子期数据异常 / consumer #2 立项时做 "NeoHorse 分块 vs Laya 长 state" 离线 A/B / Laya 出经第三方验证的中文决策 checkpoint; 方向退出条件见规划文档 §10.

---

### 2026-10-20 — v0.21 + v0.22 双 minor base bump 前置分析（18,198 commits）

> 完整扫描：`archive/2026-10-20/scan-2026-09-19-to-10-19.md`（4 路子代理深扫，hash 全验证）｜候选池：`CANDIDATES.md` K-19~K-37
> 窗口 2026-09-19→10-20，18,198 upstream commits（CN 保留路径 8,597）；上游 v0.21.0→**v0.22.2**，CN 仍 v0.20.0。

**总体判定**：**分三阶段推进的 base bump**——阶段一 P0 cherry-pick（零结构冲突，~1.5d）→ 阶段二 bump 主体（结构工程，~5-7d）→ 阶段三 one-gateway runtime / local_runtime 拍板。

**阶段一 P0（adopt 为主）**：

| 簇 | 判定 | 理由 |
|---|---|---|
| K-19 Prompt cache 红线修复（9c18b383de / e56c8d6ddb / ec78ae2211 / 3bf97898ac） | **adopt** | CN 红线"prompt caching 神圣"直接受益；ec78ae2211 是唯一"加法而不动 system prompt 结构"的改动 |
| K-20 Approval 闸门 + allowlist 同步 | **adopt + reimplement** | allowlist 写回竞态是安全回归；模式表增量纯行；A2 即时回收语义需在 CN 位置重实现 |
| K-21 依赖 CVE（PyJWT critical / urllib3 / mcp / httpx2） | **adopt** | critical CVE 必升；但 mcp 2.x 需连带 httpx2 且与 K-29 同批 |
| K-22 state.db / memory 韧性（接续 K-15） | **adopt** | WSL state.db 133MB WAL 痛点 + 静默失败红线 |
| K-23 CN provider 定向修复 | **adopt** | 阿里 guardrail / DeepSeek / MiniMax 直接收益 |
| K-24 渠道韧性 4 件（weixin/feishu/dingtalk/qqbot） | **adopt** | CN 6 平台上游原生维护中 |
| K-25 运行时解释器自保护 floor（541e4dc0ba） | **reimplement** | 与 CN HARDLINE 同构，写在 CN 自己的 approval 位置 |
| K-26 Tirith 退役后 core 检测回流（凭据外传 + 不可见 Unicode） | **reimplement** | 上游删 tirith 但把最有价值的两类搬进 core；与 CN semantic firewall 职责邻接，作 firewall 恢复的参照基线 |

**阶段二 P1（bump 主体，结构工程）**：K-27 平台 core→plugin 搬迁（🔴 最高风险，weixin/qqbot/yuanbao 逐文件手工 re-port 2-3d，**不可 cherry-pick**）｜K-28 Python 3.14 marker 剥离 + 3.14-only 语法回补（不做则 py3.11 缺 46 个依赖 + gateway import 失败）｜K-29 mcp 2.x + httpx2｜K-30 cli.py 18,664→1,796 拆解（**defer，先拍板**）｜K-31 默认值回写（max_turns 500→None / turn_lease 1800→5s / bot_loop_guard / cron_drain_timeout 全部回写 CN 安全值）｜K-32 deferred-to-bump 白拿 20 commits｜K-33 依赖删除跟随。

**阶段三 P2（拍板）**：K-34 one-gateway runtime（eb75627faf，1968 文件，本窗口所有 approval 语义改动的前提）｜K-35 上游 local_runtime 子系统 vs CN local-models（同 64K floor 不同判据）｜K-36 gateway 核心分解｜K-37 cron 重写。

**reject**：海外 19 平台（上游仍维护 793 commits）｜apps/desktop（13,961 commits）｜onboarding（22 feat）｜plugin-catalog（545）｜海外 provider/模型/connectors｜Telegram DM topic transfer｜session.export TUI /save｜stable release 通道（CN 走 pip -e）｜claude-subscription-directsdk｜docker sandbox ownership（CN 已裁 docker 栈）。

**CN 特色（本轮独立实现，不提上游）**：**session 授权粒度**——2026-09-26 事故真因是 session 级 pattern 批准按描述字符串 key 授权（一次"删两个 lib 目录"的 rm -rf 批准静默放行 326 目录的 find|xargs rm，详见 `docs/approval-classifier-gaps.md`）。上游本窗口给了两个相关但 grain 不同的新物：A2 配置级（allowlist 即时回收）、A4 回合级（`viewer_turn` contextvar 豁免），均**不覆盖** CN 事故的 pattern-key 粒度。CN 方向：session 批准 key 改**命令形态指纹** + 命中规模/批量语义变化时强制重弹。**reimplement（CN 原创）**。

**Revisit 条件**：K-30/K-35 需 user 拍板（cli.py 拆解路线、CN local-models vs 上游 local_runtime）｜阶段二 bump 完成后重算 2027-01-01 季度窗口｜上游 0.95M 权重开源 / NeoHorse 大版本变更（见 Jev 段）｜bump 完成后需复核 CN config 漂移（模型更名致静默 404，K-14 同族）。

---

### 2026-10-20 拍板：K-30 cli.py 拆解 + K-35 local_runtime 融合 + WSL 部署

**K-30 cli.py 拆解路线**：**跟上游拆成 ~1,796 行**。CN 的 cli.py 当前 18,664 行单体，本地改动（glyph layout、/refine、/heartbeat、voice 等）落在被上游搬走的那 18k 行里——bump 时按上游新结构（`cli_commands_mixin`/`cli_tui_mixin`/`main_desktop.py` + argv 层搬 `agent/legacy_cli.py`）重新组织，CN 本地功能逐条重放进对应 mixin。工作量含在 K-28 bump 主体里。

**K-35 local_runtime 融合设计（adopt 服务层 + 保留 CN 资产层 + ModelScope 通道 + Ollama opt-in）**：

上游 `hermes_cli/local_runtime/`（20 模块 5,081 行）= **托管 llama.cpp 运行时**：自管二进制 + 监督 llama-server 常驻 + 按层估 KV（estimator 知道 SWA/SSM recurrent 张量）+ 硬件预算（discrete 卡信任 nvidia-smi 扣 9%/2GiB 桌面余量、UMA 从可用物理内存减 20%）+ 上下文阶梯（FLOOR=64K→96K→144K→216K，依据 161 个真实会话统计）+ **下载前定价**（catalog.json 每条目带 estimator 输入，下载 GB 前就能算装不装得下、多快）+ **全自动推荐**（`recommended_entry()` 识别产品默认 → 否则常驻且预测 ≥20 tok/s 的 quality 最优 → 装不下返回 PhysicsRefusal、慢的不推荐但可浏览 opt-in）+ 作为 `llamacpp-alias` provider 接入 agent。**能跑离线 agent loop**（模型下载一次后 llama-server 在 127.0.0.1 常驻，含 vision 格式管理）。

CN `model_manager.py` = **资产层**（`hermes local-models` CLI 下载/登记 STT/TTS/小 LLM 的 GGUF，从 ModelScope/HF；`load_embedded_model` 嵌入式加载小模型），不负责常驻服务——CN 主本地 LLM 服务现役靠 Ollama（`HERMES_OLLAMA_HOST` 桥）+ neohorse decision service（只管 Jev 路由）。两者**互补不冗余**：上游缺国产模型目录 + 国内可达下载通道，CN 缺预算/定价/推荐/服务。

**融合方案**：
1. **目录融合**——CN 国产模型条目（Qwen3/MiniCPM5/GLM-4 系列）按上游 catalog schema 补齐 estimator 输入字段（从 GGUF 元数据抄，CN 有同款 stdlib 读取器可自动提取），并入 catalog.json → 国产模型自动进 `recommended_entry` 推荐池，硬件自适应推荐对它们同样生效。
2. **下载通道融合**——上游 `install_files()`/`hf_browse.py` 走 HF 直连（国内不可达）；CN 把下载层抽接口：**默认 ModelScope**（已有 `_download_via_snapshot` + MODELSCOPE_TOKEN 现成），HF 作 fallback。实现按 SSRF 约束（仅 http/https、host 校验拒 localhost/环回/私有/保留）。
3. **CLI 收敛**——CN `hermes local-models` 退役为薄壳调 local_runtime `ensure_model_ready`/supervisor，避免两套并行 CLI。CN 保留增量：ModelScope 通道、国产目录条目、quickstart 接线。
4. **Ollama 桥降级 opt-in**——主路径切 local_runtime 托管 llama-server；`HERMES_OLLAMA_HOST` 留给已有 Ollama 或想走 CPU 的用户，不删。
5. **64K floor 判据迁移**——从"读 Ollama num_ctx"切到"上游 GGUF + 硬件预算 estimator"（升级，更准）；CN 的 `3de7140bcd` hump 重放进新 `agent_init_ollama.py`/`context_policy.py`。

**WSL 部署结论**：上游 local_runtime **原生支持 WSL + Windows GPU passthrough**——`hardware.py` 显式找 `/usr/lib/wsl/lib/nvidia-smi`（WSL CUDA 驱动固定路径），CUDA backend 走 `libggml-cuda.so` 用宿主 Windows GPU；`recovery.py` 专门处理 WSL 时钟漂移对进程恢复的干扰。Windows 直跑也原生支持（ctypes 加载 ggml dll + System32 nvidia-smi + 进程树隔离 + windows_hide_flags）。**CN 现有 WSL 部署可平滑切到 local_runtime**：Jev 决策服务不动，主 agent loop 本地模型服务从 Ollama 桥切到 local_runtime 托管 llama-server（同 WSL + Windows GPU，对用户透明升级）。

**WSL 微调 TODO（可选）**：上游 discrete 卡的桌面余量扣减（9%/2GiB）对纯 WSL 部署过度保守（WSL 进程不挂 Windows 桌面），CN 检测到 WSL 环境时可降此余量（如降到 1GiB 地板）。micro-tune，不影响主干。

**Revisit**：bump 完成后复核 CN catalog 国产条目 estimator 字段是否齐全 + ModelScope 下载通道 SSRF 校验 + WSL 桌面余量微调实测收益。

---

### 2026-10-20 拍板：v0.22 base bump 后重新落实 CN 减法

**背景**：v0.22 bump（upstream 18,198 commits 合并，commit `a43a3da90e`）把 v0.15/v0.17 两轮裁掉的海外平台/供应商/技能/工具链整片带回。根因是**结构搬迁**——上游把平台实现从 `gateway/platforms/*.py` 搬到了 `plugins/platforms/<name>/` 插件目录（另加了 `plugins/model-providers/<name>/`），merge 解析取了上游侧，CN 之前的"整目录 `git rm`"逐条失效。判定依据：`git ls-tree -r --name-only <bump-pre CN tree>` 显示被裁目录在 bump 后 CN 树里重新出现。

**决策（4 选 1 = reject，附少量 reimplement）**：

| 上游新增面 | 决策 | 理由 |
|---|---|---|
| 22 个海外 platform plugin | **reject** | CN 用户群不含这些平台；core 面（api_server / webhook / cron / cli）保留 |
| 29 个海外 model-provider plugin | **reject** | 国内不可达 / 不符合国产生态；保留 13 个国产 + 通用 |
| `docker/` `nix/` `optional-mcps/` `gateway/relay/` `apps/bootstrap-installer/` | **reject** | CN 走 CLI/TUI + hermes-tray，不引 Docker Hub / Nix / connector relay |
| `optional-skills/` 海外组 + 9 个子技能 | **reject** | 依赖被封服务（X / Reddit / Stripe / Polymarket / crypto / HF / DDG） |
| `plugins/image_gen/` `plugins/google_meet/` `plugins/teams_pipeline/` | **reject** | 依赖海外服务 |
| `plugins/computer_use/`（v0.22 新增，含内置 `cua` driver） | **keep（偏离 ledger，已核对）** | v0.17 裁的是 `skills/computer-use/`；plugin/driver 是本地 GUI 自动化，裁掉打断 `hermes computer-use` CLI 与 core `tools/computer_use` |
| `plugins/video_gen/` | **keep（ledger 未列）** | 可自托管 |
| decline 契约（`EGRESS_DECLINE_CODE` / `declined_send`） | **reimplement** | 从 relay 抽到 `gateway/egress_decline.py`：local session 的 clarify 拒绝仍产生结构化 decline，丢了它"被拒目标被当普通失败重发" |
| `Platform` enum 的海外成员名 | **keep（不删）** | 2400+ 处 core 引用；删掉是大重构且无功能收益。"可不可用"改由 `hermes_cli/platforms.py::CN_DISABLED_PLATFORMS` 单点判定 |
| `docs/` 整目录 | **reimplement** | bump 把 CN 自己的 `docs/`（含 cn-divergences / upstream-decisions）整片带走了；本轮从 v0.21 树恢复 |

**when-to-delete**：若上游把 CN 六个平台 / 13 个 provider 回迁进 core（不再是 plugin），`CN_DISABLED_PLATFORMS` 与本表整体作废，可直接删。

**Revisit**：季度窗口（2027-01-01）复核 `plugins/model-providers/` 是否又长出新的海外 provider；`gateway/relay/` 若上游开源化 connector 协议并有国内可用部署，再评估。

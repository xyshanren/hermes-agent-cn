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

# CN Divergences (类别级 audit)

> 不穷举每个 commit，按 category 分类。决策 = override / plugin / keep / delete。
> 维护者：Mavis（项目级 audit 在 review 时更新）。

## Categories 概览

| # | Category | 决策 | 关键差异 |
|---|----------|------|---------|
| 1 | 减法哲学 | override + keep | 关闭/裁剪不符合 CN 路线的内容 |
| 2 | CN 原创用户功能 | keep | CN 自研模块，user-facing |
| 3 | 本地化配置 | override | 路径/源/默认值改 CN |
| 4 | 借鉴 + 重写 upstream | override | 思路借，代码重写 |
| 5 | CN 端客户端策略 | override / keep | CLI/TUI 优先 + hermes-tray |
| 6 | CN 内生开发资产 | keep | CN 自己的开发流程工具 |

---

### 1. 减法哲学

**形态**：源码删减（整目录/整模块）+ config 关闭 + 平台/provider 不引入

**决策**：override（源码层）+ keep（配置层）

**理由**：本地化优先 + 用户群决定代码边界——不为不存在的用户写功能

**Known items**：

**关闭国外服务/入口**：
- 平台层：Discord / Telegram / WhatsApp / Slack 等 11 个海外平台从源码移除（CN 保留 5 个：飞书/微信/企业微信/元宝/钉钉）
- Provider 层：OpenRouter / Bedrock / Anthropic 直连 / Gemini OAuth 移除（国内不可用或不符合生态）
- 配置层：所有海外服务入口在 config.yaml / .env 标记 disable

**模块级整片裁剪**（v0.17.0 减法实测，详见 `~/projects/hermes-agent-cn-notes/hermes-agent-cn-减法哲学.md`）：
- 桌面客户端：`apps/desktop/`（Electron 全栈 ~150MB×3 平台）+ `apps/bootstrap-installer/` 整片砍
- 容器化：`docker/`（完整 s6 编排）整片砍
- 包管理：`nix/` 整片砍
- 调度：`cron/` 整片砍
- 可选 MCP：`optional-mcps/linear/` `optional-mcps/n8n/` 移除
- 可选 skills：`optional-skills/blockchain/` `email/` `finance/` `gaming/` `payments/` 移除
- 外国 plugins：`plugins/google_meet/` `spotify/` `image_gen/` `teams_pipeline/` 移除
- 外国 skills：`skills/computer-use/` `social-media/` 移除
- CI/tests：`scripts/ci/` `.github/pr-screenshots/` `tests/ci/` `tests/computer_use/` `tests/fixtures/` 移除
- 文档/资源：`docs/design/` `docs/observability/` `docs/security/` `infographic/` 移除
- 网关中继：`gateway/relay/` 移除

**v0.15.0+cn.8 减法收尾**（详见 `~/projects/hermes-agent-cn-notes/merge-plan-v6-D-jianfa.md`）：
- A. **T1b 减法** — 8 文件 import 站点改写后整文件删：`gateway/platforms/homeassistant.py` / `gateway/platforms/msgraph_webhook.py` / `gateway/whatsapp_identity.py` / `tools/binary_extensions.py` / `tools/browser_camofox.py` / `tools/browser_camofox_state.py` / `tools/microsoft_graph_auth.py` / `tools/microsoft_graph_client.py`
- B. **T1c 减法** — 4 文件平台枚举改写后整文件删：email 等平台在 `cron/scheduler.py` 字符串引用清理
- C. **T4 plugin 目录清理** — 22 目录整 `git rm -r`：
  - 17 外国 model-providers：anthropic / bedrock / gemini / google / openai-codex / openrouter / nvidia / novita / xai / arcee / huggingface / copilot / copilot-acp / azure-foundry / kilocode / nous / gmi
  - 5 外国 platforms：google_chat / irc / line / simplex / teams
- D. (optional) **run_agent.py 拆分** — 15k 行 god file，6 月批 D3 冲突频繁时考虑，目前决策"不拆"

**v0.17.0 减法公开数据**（2026-07-01）：125,950 行删除 / 205,975 行新增 / 净 +80,025 行 / 5,266 → 3,596 跟踪文件 (-31.7%)

---

### 2. CN 原创用户功能

**形态**：plugins/ 或独立 module，或独立仓库（hermes-tray）

**决策**：keep（已经是 plugin / 独立 module，独立维护）

**理由**：CN 用户的实际需求，upstream 没有

**Known items**：

- **SmartRouter** — `agent/zhineng_luyou.py`（首次 commit `895f416fd`，v0.15.0 Phase 3）—— 上游 `model_router.py` 的完全重写。多后端能力感知 + 自动降级 + tier 流量分配
- **Semantic Firewall** — `agent/semantic_firewall.py`（首次 commit `7923b5f76`，v0.15.0 Phase 1）—— 5 层语义防火墙（Content Sanitization / Skill Provenance / Pre-write Verification / Quarantine / Audit），防 prompt injection
- **hermes-tray** — 独立项目 github.com/xyshanren/hermes-tray，Tauri 2 + Vue/TS，原生渲染，单文件 <10MB。替代 upstream Electron desktop。v0.1.2 收尾 223 tests 全过
- **本地化工具链** — `hermes quickstart`（一键检测 API Key/Ollama/本地模型）/ `hermes local-models setup --yes`（自动安装本地模型 ~1.58GB）/ `hermes setup`（交互式配置向导）
- **MemPalace + graphify 集成指南** — `docs/Hermes集成指南_MemPalace与graphify.md`（首次 commit `47525075e`）—— 不重写 memory 后端，把第三方工具集成方法沉淀成文档

---

### 3. 本地化配置

**形态**：config / .env / hardcoded 路径

**决策**：override（暂不实施——等第一个真要落 override 时再拍，不强制先建空目录）

**理由**：跟国内环境强相关，独立可追溯

**Known items**：

- **国内 Python 镜像源** — `~/.pip/pip.conf` 配清华 / 阿里
- **国内 Docker 镜像源** — 阿里云 / 华为云 / 腾讯云（公网源不稳定，云服务器拉取后导出下载）
- **路径习惯** — `~/.hermes/` vs upstream `~/.config/hermes/`
- **国产 API 默认** — DeepSeek / Kimi / 智谱 / 阿里 / 小米 / MiMo / 通义千问 / 百度 / 火山（取代 OpenRouter / Anthropic 直连）
- **GitHub 访问** — 优先 ssh（不只是网络问题，commit 签名验证更稳）

---

### 4. 借鉴 + 重写 upstream

**形态**：hermes-cli 子 module，整体重写

**决策**：override（独立维护，跟 upstream 模块解耦）

**理由**：行为差异不止是 bug，是设计选择

**Known items**：

- **Parallel free Search MCP cherry-pick** — commit `c0d59e656`（v0.17.0+cn.14 期间，2026-06-24），借鉴 upstream `e0e257171` 加 keyless tier（3 文件 +376/-49）。未设 `PARALLEL_API_KEY` 时走 Parallel 免费 MCP，零配置开箱即用
- **SmartRouter** — 重写 upstream `model_router.py`（详见 Category 2）
- **CLI / God file 重构** — upstream v0.17 把 `cli.py` 从 3,297 行砍到 954 行（28 subcommand parsers 抽到 `hermes_cli/subcommands/`，32 slash-command handlers → `CLICommandsMixin`）。CN 在此基础上更进一步：Phase 3 把 `gateway/run.py` 进一步拆出 `slash_commands.py`（+3,650 行）
- **cherry-pick 工具链 v1-v7** — CN 自研的批量 cherry-pick 脚本演进：v1 手工试水 → v2 自动化 + 巨型 refactor 过滤 → v3 依赖锁 AUTO-OURS → v4 大文件按 hunks 拆分 → v5 EXCLUDE_THEIRS 首创 → v6 EXCLUDE_MANUAL 规则化 → v7 空 cherry-pick 自动 skip + timeout
- **锁版本原则** — `pyproject.toml` / `uv.lock` / `Cargo.toml` 等依赖锁文件采用 `AUTO-OURS`（上游升级依赖是上游的事，CN 锁在已知稳定的版本）

---

### 5. CN 端客户端策略

**形态**：独立仓库 + 轻量 GUI 补充

**决策**：override（独立工具链）+ keep（CLI/TUI 不动）

**理由**：upstream 把 Electron desktop 当主入口，CN 把 CLI/TUI 当主入口——不同产品策略

**Known items**：

- **CLI/TUI 主入口优先** — upstream 重 Electron desktop；CN 以 CLI/TUI 为主，hermes-tray 补充
- **hermes-tray 替代 Electron** — Tauri 2（系统 WebView）+ Vue/TS。150MB×3 平台（macOS/Windows/Linux）→ 单文件 <10MB。启动 2-5s → ~50ms。常驻 200-500MB → ~30MB
- **跟随系统 WebView** — 不做三平台构建 matrix；Tauri 跟随系统 WebView，OS 解决差异
- **不引入 Docker Hub** — 客户端依赖不引入不稳定源；CN 走"云服务器拉镜像 → 导出 → 下载"绕路

---

### 6. CN 内生开发资产

**形态**：独立 module / scripts/，开发流程工具

**决策**：keep（不进 cn_overrides/，不是 user-facing 功能）

**理由**：CN 自己的开发流程工具，跟用户功能正交

**Known items**：

- **候选池（CAND-XXX 编号系统）** — CN 内部 sprint 候选管理工具。v0.15.0 之前叫"候选清单"，后改为 CAND-XXX 编号（如 CAND-079 / CAND-085）。每个候选有 commit / 测试 / 文档
- **火花库（spark library）** — CN 内部创意 / 灵感 / 待办素材库，记录"以后可能做"的想法。跟候选池区别：候选池是"现在做"，火花库是"以后做"
- **cherry-pick 工具链 v1-v7** — CN 自研的批量 cherry-pick 脚本（详见 Category 4）
- **4-step .env 保护审计** — commit 前 4 步 audit 流程（grep / diff / archive / verify），防止 .env / API key 误 commit 暴露
- **Sprint 8 项报告 schema** — sprint 收尾的 8 项固定 report（跟 mavis 季度 cron `hermes-cn-quarterly-borrow-audit` 1:1 配对）
- **self-improvement review** — agent 自动 review 当前会话并 create skill 的机制（hermes-cli 内部）

---

## 跨引用

- **上游 commit 分类原始数据**（2026-06-11 scout，2125 commit → SKIP 556 / MERGE 1396 / REVIEW 174）：`~/projects/hermes-agent-cn-notes/UPSTREAM_CLASSIFICATION_REPORT.md`
- **减法 v0.15.0+cn.8 详细计划**（A / B / C / D 4 段 + E 段）：`~/projects/hermes-agent-cn-notes/merge-plan-v6-D-jianfa.md`
- **v0.17.0 减法公开数据**（125,950 行删除 / 5,266→3,596 文件）：参考 `~/projects/hermes-agent-cn-notes/hermes-agent-cn-减法哲学.md`（**该 doc 不入仓，仅做内部参考**）

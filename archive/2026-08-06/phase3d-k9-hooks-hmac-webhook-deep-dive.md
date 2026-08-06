# Phase 3d Deep Dive — K-9 🔴 hooks + HMAC webhook (1:1 配对 dabe3c34c + CN middleware 复用)

> **K-X**: K-9 🔴 (跟 user 提"最高优先级" 1:1)
> **调研期**: 2026-08-06
> **Axiom**: 3 闭环反馈 (跟 K-1~K-5 1:1 配对, 跟 K-1 completion contracts + K-5 /learn + /journey 同 axiom)
> **决策**: ✅ Option A (user 拍 2026-08-06, 跟 phase 1 verify 推荐 1:1): cherry-pick dabe3c34c + 复用 CN middleware + 加 lifecycle hook
> **关联**: `phase1-sample-summary.md` §2.4, `phase2-filter-borrow.md` §5 [K-9], `phase4-master-index.md` (待写)
> **mavis 4 lesson 1:1 复用**: Cherry-pick split bug class (256 行全新 file 0 split bug 风险) / 后端先调查再设计 (跟 CN middleware 1:1 复用) / UX 倒退审计 (additive CLI + middleware) / 估时前必 verify (phase 1 verify 完, 1:1 配对)
> **AIMC 4 铁律 + mavis 4 件套 1:1** (跨 project design law 续 Phase 1+2+3)

---

## 1. 4 必填字段 (跟 K-1~K-5 1:1 配对)

### 1.1 Source

- **Upstream 主 commit**: `dabe3c34c` `feat(webhook): hermes webhook CLI + skill for event-driven subscriptions (#3578)` (跟 phase 1 doc §2.4 verify 1:1, **1:1 配对**)
- **含**:
  - 256 行 `hermes_cli/webhook.py` (CLI: subscribe/list/remove/test 4 subcommand)
  - +39 行 `hermes_cli/main.py` (`hermes webhook` subcommand 注册)
  - +48 行 `gateway/platforms/webhook.py` (adapter enhancement + hot-reload)
  - 180 行 `skills/devops/webhook-subscriptions/SKILL.md`
  - 52 行 `website/docs/user-guide/messaging/webhooks.md` (Dynamic Subscriptions 段)
  - 34 行 `website/docs/reference/cli-commands.md`
  - 189 行 `tests/hermes_cli/test_webhook_cli.py`
  - 87 行 `tests/gateway/test_webhook_dynamic_routes.py`
  - 24 new tests (CLI CRUD + persistence + enabled-gate + adapter dynamic route loading)
- **HMAC-SHA256 验签** (跟 GitHub webhook 1:1):
  ```python
  import hmac, hashlib
  sig = "sha256=" + hmac.new(secret.encode(), payload.encode(), hashlib.sha256).hexdigest()
  # Header: X-Hub-Signature-256: <sig>
  # Header: X-GitHub-Event: <event_name>
  ```
- **CN 端复用**:
  - `02efcfce5` `feat(middleware): adaptive execution middleware framework` (CN 端 by 守一, 280 LOC observer hook: tool_request / tool_execution / llm_request / llm_execution + schema versioning + back-compat aliases)
  - K-9 实施期: webhook event 走 CN middleware observer hook 作为 event bus

### 1.2 Axiom match

**3 闭环反馈 (strongest)** — webhook event (input) → middleware observer hook (state) → agent action (process) → HMAC 验签 feedback (output) → 回到 webhook adapter (loop closed). 跟 K-1 completion contracts judge gate + K-5 /learn + /journey 闭环 1:1 同模式.

### 1.3 Cn state

- ❌ `hermes_cli/webhook.py` 0 命中 (256 行全新)
- ❌ `~/.hermes/webhook_subscriptions.json` 0 命中
- ❌ `hermes_cli/main.py` 的 `hermes webhook` CLI 注册 0 命中
- ✅ `hermes_cli/middleware.py` 已存在 (CN 端 02efcfce5, 280 LOC observer hook + schema versioning)
- ✅ `gateway/platforms/webhook.py` 已存在 (CN 端 basic webhook platform, 0 CLI + 0 HMAC)
- 0 cherry-pick split bug 风险 (256 行全新 file 0 跨 file 冲突)

### 1.4 Port plan

**1-1.5d, 1 commit, 4-5 文件改动**:

| File | 改动 | LOC |
|------|------|-----|
| `hermes_cli/webhook.py` | 新 file, cherry-pick dabe3c34c | +256 |
| `hermes_cli/main.py` | 加 `hermes webhook` subcommand 注册 | +39 |
| `gateway/platforms/webhook.py` | cherry-pick dabe3c34c adapter enhancement | +48 |
| `skills/devops/webhook-subscriptions/SKILL.md` | 新 file, cherry-pick dabe3c34c | +180 |
| `tests/hermes_cli/test_webhook_cli.py` | 新 file, cherry-pick dabe3c34c | +189 |
| `tests/gateway/test_webhook_dynamic_routes.py` | 新 file, cherry-pick dabe3c34c | +87 |

**实施步骤** (跟 mavis Cherry-pick split bug class 1:1 防护):

1. **Phase 0 实施前 grep** (跟 mavis 4 lesson 1:1):
   - `grep -rn 'hermes webhook' hermes_cli/` (0 命中 = 0 冲突)
   - `grep -rn 'webhook_subscriptions' hermes_cli/` (0 命中)
   - 读 `hermes_cli/middleware.py` (确认 middleware observer hook 边界)
2. **cherry-pick dabe3c34c** (用 `git show dabe3c34c -- <file> > /tmp/file.patch` + `git apply`):
   - `hermes_cli/webhook.py` 全新 (0 split bug 风险)
   - `gateway/platforms/webhook.py` adapter 改 (跟 CN 现有 webhook platform 部分叠加, 1:1 兼容)
3. **cherry-pick 后 grep 旧名 0 命中** (跟 mavis 4 lesson 1:1):
   - `grep -rn 'webhook.*subscribe' hermes_cli/` 0 命中
   - `grep -rn 'webhook_subscriptions.json' hermes_cli/` 0 命中
4. **复用 CN middleware** (跟 mavis 后端先调查再设计 1:1):
   - webhook event 走 `hermes_cli/middleware.py` 的 4 observer hook (tool_request / tool_execution / llm_request / llm_execution) 作为 event bus
   - 加 `pre_webhook` / `post_webhook` 2 lifecycle hook (跟 user 提的"hooks 体系" 1:1 配对)
5. **happy-path smoke test**:
   - `hermes webhook subscribe test --events "github:push" --prompt "echo test"` 跑通
   - `hermes webhook list` 显订阅
   - `hermes webhook test test --payload '{"key":"value"}'` 显 HMAC-SHA256 验签签名
   - HMAC verify test: 改 payload → 验签 fail (跟 X-Hub-Signature-256 GitHub webhook 1:1)

---

## 2. 估时 / 风险 / 价值 (跟 K-1~K-5 1:1 配对)

| 维度 | K-9 值 | 跟 K-1~K-5 1:1 配对 |
|------|--------|---------------------|
| 估时 | 1-1.5d | 跟 K-3 1.5d 同 (1:1 配对 + 跟 CN middleware 1:1 复用) |
| 风险 | 🟢 低 | 跟 K-3 0 风险 1:1 (256 行全新 file 0 跨 file 冲突) |
| 价值 | 🔴 极高 | 跟 K-2 🔴 极高 P0 1:1 (跟 user 提"最高优先级" + PIPL 边界防护 1:1) |

---

## 3. 跨 project reference (跟 mavis 4 件套 1:1 配对)

**跟 mavis 4 件套 1:1** (跨 project design law 续 Phase 1+2+3):

- **read-only 调研**: ✅ phase 1 + phase 2 read-only
- **critic tool-verified**: ✅ phase 1 K-9 1:1 verify 完 (dabe3c34c HMAC-SHA256 + X-Hub-Signature-256 + 24 test 全套)
- **无状态**: ✅ middleware observer 0 状态, webhook event 走 observer hook 不持久化
- **扁平**: ✅ 4 event (pre_webhook / post_webhook / pre_tool_use / post_tool_use) 简单 flat

**跟 AIMC 4 铁律 + mavis 4 件套 1:1** (跨 project design law 续 Phase 1+2+3):

- 跟 CAND-085 4 铁律 1:1 (0 改 upstream / CN 端可维护 / AIMC 集成兼容 / commit 前 verify)
- 跟 mavis 4 件套 1:1, 1:1 配对实施期 4 铁律 + 4 件套齐
- 跟 钱学森 3-layer 双向闭环 1:1 配对 (反馈层 webhook event → 控制层 middleware observer → 执行层 agent action)

---

## 4. 备注 (跟 K-1~K-5 1:1 配对)

- ⚠️ 跟 user 提的 1-2d 估时 1:1, 跟 CN middleware 1:1 复用
- 🔴 跟 user 提"最高优先级" 1:1, 跟 K-2 P0 bug 1:1 配对价值
- 跟 PIPL 边界防护 1:1 (webhook 端 HMAC 验签是 PIPL 边界防护 1 段)
- 跟 S12 routing_decision accuracy 互补 (middleware observer hook 跟 S12 routing 1:1 配对)
- 跟 K-3 cherry-pick 1.5d 4 commit 模式 1:1 配对 (K-9 也是 1 commit 但是 additive CLI, 0 拆分)

---

**Phase 3d 完成** — K-9 deep dive 4 必填字段 + 估时/风险/价值 + 跨 project reference (跟 mavis 4 件套 + AIMC 4 铁律 1:1) + 备注 1:1 落盘.

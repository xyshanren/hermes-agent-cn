# Borrow Tracking — Phase 4 D3 Upstream Insights

> **Phase 4 借鉴追踪表**
> **更新**: 2026-06-24（v2 修订：执行顺序改为 P0 → S0）
> **策略**: 不强制 cherry-pick，参考 upstream 思路，CN 路径自己实现
> **执行顺序**: P0（短档，风险可控）→ S0（中档，改动面广）→ 长档 P1/P2/OPTIONAL

**v2 顺序调整理由**:
- P0 是借鉴思路（CN 自己写，改动局部）— 风险可控
- S0 改运行时硬路径（base.py + 调用方同步）— 需稳定基线
- 先 P0 建立信心 → 后 S0 改硬路径

---

## S0 — 安全必看

### S0-1: `41d2c758c` — Fix unsafe gateway media path delivery

- **上游文件**: `gateway/platforms/base.py`, `cron/scheduler.py`, `gateway/run.py`, `tests/`...
- **冲突情况**: ❌ 5 个文件冲突（gateway/platforms/base.py, tests/cron/test_scheduler.py, tests/gateway/test_platform_base.py, tests/tools/test_send_message_tool.py, tools/send_message_tool.py）
- **状态**: `NEEDS_MANUAL_BORROW`
- **CN 实现方案**: 安全相关，必须人工处理。需要在 CN gateway 媒体路径验证逻辑中应用 upstream 的安全补丁思路。
- **预估文件**: `gateway/platforms/base.py` + 相关测试文件
- **工作量**: 1 天

---

## P0 — 核心路径借鉴

### P0-1: `d1f23bb2d` — TUI stdin EOF 崩溃修复

- **上游文件**: `agent/anthropic_adapter.py`, `agent/context_references.py`, `agent/lsp/install.py`, ... (27 files)
- **状态**: `✅ DONE`（参考思路，CN 实现）
- **CN 实施**: cn-merge 有 tui_gateway/ 大量定制（Phase 3 _teardown_session）。按 upstream 思路在 `tui_gateway/server.py` 加 stdin 守护，对 7 处 subprocess.run() 添加 stdin=subprocess.DEVNULL。
- **实际文件**: `tui_gateway/server.py` (+9/-2, 7 callsites)
- **Commit**: `8aa1bd411`
- **工作量**: 1 天

### P0-2: `e0e257171` — 并行 web search/extract

- **上游文件**: `agent/display.py`, `hermes_cli/tools_config.py`, `plugins/web/parallel/` (15 files)
- **状态**: `✅ DONE`（参考思路，CN 实现）
- **CN 实施**: 在现有 `plugins/web/parallel/provider.py` 增加 keyless MCP free 层（Streamable-HTTP JSON-RPC）。当无 PARALLEL_API_KEY 时自动使用免费 search.parallel.ai/mcp。更新 `tools/web_tools.py` 将 parallel 设为无 key 默认后端。更新 `hermes_cli/tools_config.py` 使 web 集始终"已配置"。
- **实际文件**: `plugins/web/parallel/provider.py` (+298/-69), `tools/web_tools.py` (+47/-18), `hermes_cli/tools_config.py` (+9/-6)
- **Commit**: `c0d59e656`
- **工作量**: 2 天

### P0-3: `2e0c9083d` — 自适应执行拦截中间件

- **上游文件**: `agent/agent_runtime_helpers.py`, `agent/conversation_loop.py`, `agent/tool_executor.py`, `hermes_cli/middleware.py`, `model_tools.py` (14 files)
- **状态**: `🎯 ABORTED`（cherry-pick 冲突超 50 行 — 12+ 文件冲突，最大 223 行）
- **CN 现状**: `hermes_cli/middleware.py` (280 行) 已存在于 CN（框架完整）。`hermes_cli/plugins.py` 已有 middleware 注册支持。`model_tools.py` 已有 middleware 引用。缺少的是 `agent/conversation_loop.py` 中的 middleware hook 接入。CN 的 conversation_loop.py 因 Phase 3 god-file 重构与 upstream 差异极大，需人工接入。
- **待办**: 在 `agent/conversation_loop.py` 的 API 调用关键路径接入 `apply_llm_request_middleware` / `run_llm_execution_middleware`
- **工作量**: 3 天（原预估）

### P0-4: `bd7fc8fdc` — 稳定人类可读时间戳注入

- **上游文件**: `agent/agent_init.py`, `agent/conversation_loop.py`, `agent/turn_context.py`, `gateway/run.py` (13 files)
- **状态**: `🎯 ABORTED`（cherry-pick 冲突超 50 行 — gateway/run.py 126 行, run_agent.py 3755 行）
- **CN 现状**: CN `gateway/run.py` 已有定制 timestamp 逻辑（Phase 3）。新文件 `gateway/message_timestamps.py` (166 行) 为独立模块，可单独添加。接入点：`_build_gateway_agent_history()` 和 `on_user_message()` 方法。
- **待办**: 人工复制 `gateway/message_timestamps.py`，在 `gateway/run.py` 的适当位置接入
- **工作量**: 1 天（原预估）

---

## 汇总

| # | Commit | 状态 | 工作量 | 备注 |
|---|--------|:----:|:---:|------|
| P0-1 | d1f23bb2d | ✅ DONE | 1 天 | commit 8aa1bd411 |
| P0-2 | e0e257171 | ✅ DONE | 2 天 | commit c0d59e656 |
| P0-3 | 2e0c9083d | 🎯 ABORTED | 3 天 | 冲突 > 50 行 (12+ 文件); 框架已就位需人工接 conversation_loop |
| P0-4 | bd7fc8fdc | 🎯 ABORTED | 1 天 | 冲突 > 50 行 (gateway/run.py 126 行, run_agent.py 3755 行) |
| S0-1 | 41d2c758c | NEEDS_MANUAL_BORROW | 1 天 | 等待 P0 完成后执行

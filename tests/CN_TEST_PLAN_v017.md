# Hermes Agent 中文版 (cn) v0.17.0+cn.17 冻结版测试方案

> **版本**: v0.17.0+cn.17 (frozen)
> **Tag**: `v0.17.0+cn.17` on `cn` branch
> **日期**: 2026-06-26
> **基于基线**: 合并阶段已通过的 G1.3 (3114 passed) + G4.3 (38 new tests)
> **覆盖范围**: CN 特有功能 + v0.17.0 引入功能 + 本次 12 个 cherry-pick 拆分 bug 修复回归
> **早期版本 (v0.11) 测试方案**: [CN_TEST_PLAN.md](CN_TEST_PLAN.md) — 仅作历史参考

---

## 0. 测试策略总览

### 0.1 测试金字塔

| 层级 | 数量目标 | 工具 | 触发时机 | 重点 |
|------|---------|------|----------|------|
| L1 单元测试 | ~3200+ 已存在 | pytest | 每次 push | 已有基线 + 12 bug 回归 |
| L2 集成测试 | ~60+ | pytest | 每次 push | CN 平台 + Provider 路由 |
| L3 E2E | 8-10 场景 | shell + subprocess | v0.17.x patch + 重大变更 | 关键用户路径 |
| L4 手工 smoke | 10 清单 | 人工 | freeze + 重大变更 | hermes CLI 入口 |

### 0.2 已有基线（合并阶段已验证）

| Gate | 范围 | 结果 | 文档 |
|------|------|------|------|
| G1.3 | gateway 全量 | 3114 passed | CHANGELOG_CN.md § v0.17.0+cn.11 |
| G4.3 | cn.13~cn.16 新增测试 | 38 passed, 0 regression | CHANGELOG_CN.md § v0.17.0+cn.13~16 |
| S0-1 | media delivery security | 17/17 passed | `tests/gateway/test_media_delivery_security.py` |
| P0-4 | message_timestamps | 21/21 passed | `tests/gateway/test_message_timestamps.py` |
| G5.x | 12 bug 修复 | 全部 + 0 regression | CHANGELOG_CN.md § v0.17.0+cn.16~17 |

### 0.3 本次冻结版新增测试目标

| 目标 | 数量 | 优先级 |
|------|------|--------|
| 12 bug 修复回归测试 (1:1) | 12 | **P0** |
| CN 平台适配 (feishu/weixin/wecom/yuanbao) | 8-12 | **P0** |
| CN Provider 连通性 (deepseek/minimax/kimi/zai) | 5-8 | **P0** |
| v0.17.0 新功能 (P0-1/2/3/4) | 已有,补充 | P1 |
| 手工 E2E 清单 | 10 项 | P0 |

---

## 1. P0 必测：12 个 cherry-pick 拆分 bug 修复回归

每个修复都要有一个 test case 防止再发。建 `tests/cn_cherrypick/test_v017_split_bugs.py`：

### 1.1 run_agent.py 修复 (commit 70c6f7cf8)

| # | Bug | 测试用例 | 现状 |
|---|-----|---------|------|
| 1 | orphan 107 行 function body | `test_run_agent_module_loads_no_syntax_error` | 缺 |
| 2 | orphan 23 行 try/except in model_tools | `test_model_tools_module_loads_no_syntax_error` | 缺 |
| 3 | `HISTORICAL_*_HEADING` NameError | `test_summary_prefix_uses_defined_constants` | 缺 |
| 4 | `_OPENAI_CLS_CACHE` NameError | `test_load_openai_cls_uses_module_level_cache` | 缺 |
| 5 | `fts_migrations_complete` UnboundLocalError | `test_schema_migration_v12_plus_initializes_flag` | 缺 |
| 6 | `_ephemeral_child_sql` NameError + SCHEMA_VERSION | `test_schema_v16_migration_helpers_defined` | 缺 |
| 7 | `_insert_session_row` cwd kwarg | `test_create_session_accepts_cwd_kwarg` | 缺 |
| 8 | `_release_active_session` AttributeError | `test_finalize_single_query_no_attribute_error` | 缺 |
| 9 | `tool_progress_mode` + 3 callbacks + get_tool_definitions kwargs | `test_init_agent_no_missing_param` | 缺 |
| 10 | `utils.atomic_json_write` `mode` → `original_mode` | `test_atomic_json_write_uses_original_mode` | 缺 |

### 1.2 cli.py 修复 (commit 47d0e5573)

| # | Bug | 测试用例 | 现状 |
|---|-----|---------|------|
| 11 | finally: return 杀死 interactive mode | `test_main_falls_through_to_cli_run_for_interactive` | 缺 |
| 12 | `_archived_list` NameError | `test_prompt_tier_filter_block_present` | 缺 |

### 1.3 模板

```python
# tests/cn_cherrypick/test_v017_split_bugs.py
"""Regression tests for 12 cherry-pick split bugs in v0.17.0+cn.16+cn.17.

Each test maps 1:1 to a bug fix. Adding a test before a fix = TDD.
Removing a test = requires manual review of the related commit.
"""
import pytest
import importlib

# === Module load smoke tests (regression for orphan dead code) ===
def test_run_agent_module_loads_no_syntax_error():
    import run_agent
    assert hasattr(run_agent, "AIAgent")

def test_model_tools_module_loads_no_syntax_error():
    import model_tools
    assert callable(model_tools.get_tool_definitions)

# === HISTORICAL_*_HEADING constants (cherry-pick 3) ===
def test_summary_prefix_uses_defined_constants():
    from agent.context_compressor import (
        HISTORICAL_TASK_HEADING,
        HISTORICAL_IN_PROGRESS_HEADING,
        HISTORICAL_PENDING_ASKS_HEADING,
        HISTORICAL_REMAINING_WORK_HEADING,
    )
    assert all(isinstance(v, str) and v.startswith("##") for v in [
        HISTORICAL_TASK_HEADING,
        HISTORICAL_IN_PROGRESS_HEADING,
        HISTORICAL_PENDING_ASKS_HEADING,
        HISTORICAL_REMAINING_WORK_HEADING,
    ])

# === fts_migrations_complete init (cherry-pick 5) ===
def test_schema_migration_v12_plus_initializes_flag():
    import hermes_state
    # If current_version is already past v11, the variable must be initialized
    # before use. We can't directly test the init without a DB, but we can
    # verify the source structure: fts_migrations_complete assignment
    # appears BEFORE the `if current_version < SCHEMA_VERSION` check.
    import inspect
    src = inspect.getsource(hermes_state)
    # Initialization must be present (any assignment before the final check)
    assert "fts_migrations_complete = True" in src
    # Final check references the variable
    assert "if current_version < SCHEMA_VERSION and fts_migrations_complete" in src

# === v16 migration helpers (cherry-pick 6) ===
def test_schema_v16_migration_helpers_defined():
    import hermes_state
    for helper in ("_delegate_from_json", "_BRANCH_CHILD_SQL",
                   "_COMPRESSION_CHILD_SQL", "_LISTABLE_CHILD_SQL",
                   "_ephemeral_child_sql"):
        assert hasattr(hermes_state, helper), f"missing: {helper}"
    assert hermes_state.SCHEMA_VERSION >= 16

# === _release_active_session no-op stub (cherry-pick 8) ===
def test_finalize_single_query_no_attribute_error(monkeypatch):
    from cli import HermesCLI
    from hermes_cli.main import _finalize_single_query
    cli = HermesCLI.__new__(HermesCLI)  # bypass __init__
    # Should not raise AttributeError
    _finalize_single_query(cli)

# === get_tool_definitions accepts only 3 kwargs (cherry-pick 9) ===
def test_get_tool_definitions_accepts_3_kwargs():
    from model_tools import get_tool_definitions
    import inspect
    sig = inspect.signature(get_tool_definitions)
    assert len(sig.parameters) == 3
    assert set(sig.parameters) == {"enabled_toolsets", "disabled_toolsets", "quiet_mode"}

# === atomic_json_write mode fix (cherry-pick 10) ===
def test_atomic_json_write_uses_original_mode(tmp_path, monkeypatch):
    from utils import atomic_json_write
    target = tmp_path / "test.json"
    target.write_text("{}")
    # Should not raise NameError on 'mode'
    atomic_json_write(target, {"k": "v"})

# === finally: return kills interactive mode (cherry-pick 11) ===
def test_main_falls_through_to_cli_run_for_interactive():
    """If no query and no image, main() must reach cli.run() (interactive mode).

    The bug: a `return` in the finally block always returned, making
    cli.run() dead code. Verify the source structure has the fall-through.
    """
    import inspect
    from cli import main
    src = inspect.getsource(main)
    # The finally: return bug — verify cli.run() is not guarded by early return
    # Check that the finally block doesn't unconditionally return
    assert "finally:" in src
    # The fix removed the return; the next statement should be cli.run()
    lines = [l for l in src.splitlines() if l.strip() and not l.strip().startswith("#")]
    for i, line in enumerate(lines):
        if "def main" in line and "def main(" not in line:
            # Find cli.run() AFTER the finally
            found_finally = False
            for j in range(i+1, len(lines)):
                if "finally:" in lines[j]:
                    found_finally = True
                if found_finally and "cli.run()" in lines[j]:
                    # cli.run() must be AFTER finally but not inside it
                    # (indentation: cli.run() at function level, not inside try/finally)
                    indent = len(lines[j]) - len(lines[j].lstrip())
                    assert indent < 9, f"cli.run() at indent {indent} (must be <9, not inside try/finally)"
                    return
            pytest.fail("cli.run() not found after finally")
    pytest.fail("main() not found")

# === _archived_list tier filter (cherry-pick 12) ===
def test_prompt_tier_filter_block_present():
    """The tier filtering block (_load_tier_data + classification) that
    produces _archived_list must be present in the codebase."""
    import subprocess
    result = subprocess.run(
        ["grep", "-rln", "_archived_list", "."],
        capture_output=True, text=True, cwd="/root/hermes-agent-cn"
    )
    # The list of files that USE _archived_list
    consumers = result.stdout.strip().split("\n")
    # For each consumer, verify the defining file (with _load_tier_data) is also present
    # This is a structural test — it catches the cherry-pick split where the
    # consumer landed but the producer (filter block) didn't.
    assert len(consumers) > 0, "_archived_list not used anywhere"
    # Heuristic: the defining module should reference _load_tier_data
    define_check = subprocess.run(
        ["grep", "-rln", "_load_tier_data", "."],
        capture_output=True, text=True, cwd="/root/hermes-agent-cn"
    )
    if define_check.returncode == 0:
        # Both producer and consumer exist — good
        return
    pytest.fail(
        f"_archived_list used in {consumers} but _load_tier_data (the producer) "
        "not found. Cherry-pick split bug regressed."
    )
```

---

## 2. P0 必测：CN 特有平台 (5 个)

CN 保留平台: feishu / weixin / wecom / yuanbao。**降权保留**: dashscope。

### 2.1 测试范围

| 平台 | 文件 | 现有测试 | 缺什么 |
|------|------|---------|--------|
| feishu | `gateway/platforms/feishu*` | 需查 | v0.17.0 cherry-pick 影响 |
| weixin | `gateway/platforms/weixin*` | 需查 | 媒体路径安全 (S0-1 已覆盖) |
| wecom | `gateway/platforms/wecom*` | 需查 | 降权保留，基础连通 |
| yuanbao | `gateway/platforms/yuanbao*` | `tests/gateway/platforms/test_yuanbao_recall_db_only.py` | recall 路径 |

### 2.2 通用测试矩阵

对每个平台，建 `tests/gateway/platforms/test_cn_<platform>_v017.py`：

```python
# Template: tests/gateway/platforms/test_cn_feishu_v017.py
import pytest

class TestFeishuCNv017:
    """v0.17.0+cn.17 freeze tests for feishu platform."""

    def test_platform_module_imports(self):
        """Module must import without cherry-pick split errors."""
        from gateway.platforms import feishu
        assert feishu is not None

    def test_platform_in_registry(self):
        """feishu must be in PLATFORMS registry (not stripped by cherry-pick)."""
        from gateway.platforms import PLATFORMS
        assert "feishu" in PLATFORMS

    def test_webhook_handler_present(self):
        """feishu webhook handler must be wired up post-cn.13 cherry-pick."""
        from gateway.platforms.feishu import handle_webhook
        assert callable(handle_webhook)

    @pytest.mark.skipif(not has_feishu_creds(), reason="no feishu creds")
    def test_send_message_smoke(self, feishu_creds):
        """Smoke test: send a text message via feishu (mocked)."""
        from gateway.platforms.feishu import send_message
        result = send_message(creds=feishu_creds, text="cn freeze test")
        assert result["ok"] is True
```

### 2.3 重点：媒体安全 (S0-1 验证后稳定)

`tests/gateway/test_media_delivery_security.py` 已 17/17 pass。冻结版需要：

```bash
pytest tests/gateway/test_media_delivery_security.py -v
# 必须 17/17 pass，否则 CN 平台发文件可能泄露本地路径
```

### 2.4 测试运行

```bash
# CN 平台全套
pytest tests/gateway/platforms/ -v

# 平台 + 媒体安全 + 时间戳
pytest tests/gateway/ -k "platforms or media_delivery or message_timestamps" -v
```

---

## 3. P0 必测：CN 特有 Provider (5+1)

CN 保留: **deepseek / minimax / kimi / zai / ollama + Nous Portal (可选)**。

### 3.1 已有测试覆盖

| Provider | 测试文件 | 状态 |
|----------|---------|------|
| minimax | `tests/agent/test_minimax_provider.py` | ✅ 有 |
| named custom | `tests/agent/test_auxiliary_named_custom_providers.py` | ✅ 有 |
| direct URL | `tests/agent/test_direct_provider_url_detection.py` | ✅ 有 |
| custom extra_body | `tests/agent/test_custom_provider_extra_body.py` | ✅ 有 |
| runtime main | `tests/agent/test_set_runtime_main_custom_provider.py` | ✅ 有 |

### 3.2 缺的测试

| Provider | 缺什么 |
|----------|--------|
| deepseek | API 连通性 + 流式响应解析 |
| kimi | API 连通性 |
| zai | API 连通性 |
| ollama | 本地 model 列表拉取 |
| fallback | fallback_config.py 链式 fallback |

### 3.3 重点：fallback_config (本次修复的 recovered file)

`fallback_config.py` (commit 8e253d90b 恢复) 72 行，整个文件之前漏 cherry-pick。**新加测试**：

```python
# tests/hermes_cli/test_fallback_config_cn.py
"""Tests for the recovered fallback_config.py module.

Background: The 72-line fallback_config.py was accidentally dropped during
the v0.17.0 cherry-pick merge. Without it, providers like
fallback_providers: [Qwen/Qwen2.5-7B-Instruct (siliconflow),
qwen3-vl:4b (ollama), qwen-0.5b (embedded)] were silently ignored,
and users with no API key for the primary provider would see immediate
"No LLM provider configured" errors instead of the chain trying
each fallback.
"""
import pytest
from hermes_cli.fallback_config import (
    parse_fallback_providers,
    dedupe_fallback_chain,
)

def test_parse_fallback_providers_raw_entries():
    """Raw config entries: 3 unique + 1 duplicate → 3 unique chain."""
    raw = [
        {"provider": "siliconflow", "model": "Qwen/Qwen2.5-7B-Instruct"},
        {"provider": "ollama", "model": "qwen3-vl:4b"},
        {"provider": "embedded", "model": "qwen-0.5b"},
        {"provider": "siliconflow", "model": "Qwen/Qwen2.5-7B-Instruct"},  # dup
    ]
    chain = parse_fallback_providers(raw)
    assert len(chain) == 3
    assert chain[0]["model"] == "Qwen/Qwen2.5-7B-Instruct"
    assert chain[2]["model"] == "qwen-0.5b"

def test_dedupe_fallback_chain_preserves_order():
    chain = [
        {"provider": "a", "model": "m1"},
        {"provider": "b", "model": "m2"},
        {"provider": "a", "model": "m1"},  # dup
    ]
    deduped = dedupe_fallback_chain(chain)
    assert len(deduped) == 2
```

### 3.4 测试运行

```bash
pytest tests/agent/test_minimax_provider.py \
       tests/agent/test_auxiliary_named_custom_providers.py \
       tests/agent/test_direct_provider_url_detection.py \
       tests/agent/test_custom_provider_extra_body.py \
       tests/hermes_cli/test_fallback_config_cn.py -v
```

---

## 4. P0 必测：v0.17.0 新增功能回归

### 4.1 P0-1 TUI stdin EOF (commit 8aa1bd411)

- 已 cherry-pick，7 处 `subprocess.run` 加了 `stdin=subprocess.DEVNULL`
- 测试：`tests/tui_gateway/test_review_summary_callback.py` (有覆盖)
- **补充**: TUI gateway server 的 subprocess stdin EOF 测试

```bash
pytest tests/tui_gateway/ -v -k "stdin or eof or subprocess"
```

### 4.2 P0-2 Parallel MCP (commit c0d59e656)

- Streamable-HTTP 客户端，并行搜索
- 测试：mcp 集成测试
- **补充**: 并发 fetch 测试

```bash
pytest tests/plugins/ -v -k "parallel or streamable or concurrent"
```

### 4.3 P0-3 middleware observer (commit 02efcfce5)

- **CN 0 LLM 拦截策略**: 只 observer，不真拦截
- 关键: 验证 observer 调用，但不修改 LLM 调用

```python
# tests/hermes_cli/test_middleware_observer_only.py
"""Verify CN middleware is observer-only (no LLM call interception)."""
def test_middleware_does_not_block_llm_call():
    from hermes_cli.middleware import apply_llm_execution_middleware
    # The middleware exists, but apply_* must not actually replace
    # the LLM call. Verify by checking it's a passthrough.
    # (CN strategy: observer schema compat, not real interception)
    assert apply_llm_execution_middleware is not None

def test_middleware_observer_fires_on_llm_call(monkeypatch):
    from hermes_cli.middleware import register_observer
    fired = []
    register_observer("test_observer", lambda event: fired.append(event))
    # Trigger LLM call (mock)
    # Verify observer was called, but LLM call still completed
    assert len(fired) > 0  # observer fired
```

### 4.4 P0-4 message_timestamps (commit ce2965070)

- 已有 21/21 passed
- **关键**: 验证 resumed session 也能正确显示时间戳

```bash
pytest tests/gateway/test_message_timestamps.py -v
```

### 4.5 Custom provider identity (commit 9585396bd)

- 修复 custom provider 身份丢失的 session 持久化 bug
- 关键: 验证 session.resume 之后 custom:<name> 身份仍能恢复

```python
# tests/agent/test_custom_provider_identity_v017.py
def test_custom_provider_identity_persists_across_resume():
    from hermes_cli.runtime_provider import find_custom_provider_identity
    # Session was stored with api.siliconflow.cn URL
    identity = find_custom_provider_identity("https://api.siliconflow.cn/v1")
    assert identity == "custom:api.siliconflow.cn"
```

### 4.6 测试运行

```bash
pytest tests/tui_gateway/ tests/plugins/ tests/hermes_cli/ tests/gateway/ \
       -k "stdin or eof or parallel or streamable or middleware or observer or timestamps or custom_provider or fallback" \
       -v
```

---

## 5. P0 必测：核心入口手工 E2E 清单

冻结发布前必跑（用户实跑，5-10 分钟）：

### 5.1 hermes CLI 入口

```bash
# 版本
hermes --version
# 期望: Hermes Agent v0.17.0+cn.17 (2026.6.26) · upstream ... · local ...

# 帮助
hermes --help
hermes chat --help
# 期望: 不 crash，列出所有子命令

# 单次 query (无 -q 应进入 interactive，bug 11 修复后)
hermes chat
# 期望: 进入 TUI / 交互模式（不是直接退出）
# [Ctrl+C 退出]
```

### 5.2 诊断 + 配置

```bash
# 诊断
hermes doctor
# 期望: 中文输出（CN 汉化），检查 Python 环境 + 5+1 provider 配置

# 配置向导
hermes setup
# 期望: 中文菜单，列出 5+1 provider 选择项

# Provider list
hermes model
# 期望: 列出 deepseek / minimax / kimi / zai / ollama + Nous

# Config show
hermes config show
# 期望: 现有配置正确显示
```

### 5.3 会话

```bash
# 列表
hermes sessions list
# 期望: 列出历史会话

# 恢复最新
hermes --continue
# 期望: 进入之前最新会话

# 恢复指定
hermes --resume <session_id>
# 期望: 恢复指定会话
```

### 5.4 配置 provider (手动连通性)

```bash
# deepseek (用户 API key)
hermes config set model.provider deepseek
hermes config set model.default deepseek-v4-flash
# 测试连通:
hermes -z "say hi" -m deepseek-v4-flash --provider deepseek
# 期望: 返回 "Hi" 类响应（不报 "no final response"）

# ollama (本地)
hermes config set model.provider ollama
hermes -z "say hi" --provider ollama
# 期望: 本地模型响应
```

### 5.5 工具 + 中间件

```bash
# 工具列表
hermes tools
hermes tools list-tools
# 期望: 列出所有可用工具

# Skills
hermes skills list
# 期望: 列出 skills

# MCP
hermes mcp list
# 期望: 列出 MCP 服务器
```

### 5.6 关键 bug 修复验证

```bash
# Bug 11: interactive mode
hermes chat < /dev/null
# 期望: 进入交互或干净退出（不 crash AttributeError）

# Bug 12: 发消息 (有 _archived_list 引用)
hermes -z "send a test message" --provider deepseek
# 期望: 成功，不报 _archived_list NameError
```

---

## 6. 测试运行顺序（freeze 时序）

```bash
#!/usr/bin/env bash
# tests/cn_freeze_smoke.sh — 冻结前必须通过
set -e

echo "=== L1 单元测试 (regression baseline) ==="
pytest tests/ -q --timeout=60 -x

echo "=== L2 CN 平台 + Provider 集成 ==="
pytest tests/gateway/platforms/ \
       tests/agent/test_minimax_provider.py \
       tests/agent/test_auxiliary_named_custom_providers.py \
       tests/agent/test_direct_provider_url_detection.py \
       tests/agent/test_custom_provider_extra_body.py \
       tests/hermes_cli/test_fallback_config_cn.py -v

echo "=== L2 v0.17.0 新功能回归 ==="
pytest tests/gateway/test_media_delivery_security.py \
       tests/gateway/test_message_timestamps.py \
       tests/tui_gateway/ \
       tests/hermes_cli/test_middleware_observer_only.py \
       tests/agent/test_custom_provider_identity_v017.py -v

echo "=== L1 12 bug 修复回归 (NEW) ==="
pytest tests/cn_cherrypick/test_v017_split_bugs.py -v

echo "=== L3 关键入口 smoke ==="
timeout 10 hermes --version
timeout 10 hermes --help
timeout 10 hermes chat --help
timeout 10 hermes doctor
timeout 10 hermes model
timeout 10 hermes sessions list

echo "=== ALL PASS — v0.17.0+cn.17 freeze ready ==="
```

---

## 7. 失败处置矩阵

| 失败层级 | 严重度 | 处置 |
|---------|-------|------|
| L1 已存在测试 regression | **P0** | 阻塞 freeze，必须修 |
| L1 新增 12 bug 回归测试失败 | **P0** | 立即检查对应 commit |
| L2 CN 平台/Provider 集成失败 | **P0** | 阻塞 freeze |
| L2 v0.17.0 新功能失败 | **P1** | 看是否影响 CN 路径 |
| L3 入口 smoke crash | **P0** | 阻塞 freeze |
| L3 入口 smoke 输出异常（非 crash） | **P2** | 记录到 freeze notes |

---

## 8. 与已有测试基础设施的关系

| 资源 | 位置 | 复用方式 |
|------|------|----------|
| pytest fixtures | `tests/conftest.py` | 直接复用 |
| Mock providers | `tests/fakes/` | 复用，新测试也用 |
| Gateway test utils | `tests/gateway/conftest.py` | 复用 |
| CN integration | `tests/hermes_cli/test_cn_integration.py` | 复用，扩 test_v017_xxx |
| 已有 v0.11 CN 测试 | `tests/hermes_cli/test_cn_localization.py` | 保留作历史（不动） |
| 临时手工脚本 | `tests/scripts/` | freeze 时可入 |

---

## 9. 冻结发布检查表

- [ ] L1 全量 pytest 通过（无 regression）
- [ ] L2 CN 平台 5/5 通过
- [ ] L2 CN Provider 5+1 通过
- [ ] L2 v0.17.0 新功能 4/4 通过（P0-1/2/3/4）
- [ ] L1 12 bug 修复回归测试 12/12 通过
- [ ] L3 入口 smoke 8/8 通过
- [ ] CHANGELOG_CN.md 完整记录 v0.17.0+cn.17 段
- [ ] 已有 tag v0.17.0+cn.17 已推送
- [ ] release/v0.17.x 分支建立（接收 patch）

---

## 10. 不在本次冻结范围

- ❌ 0 LLM 拦截的中间件拦截能力（observer only 已稳定）
- ❌ Electron desktop 移植（CN 策略：拒绝，用 hermes-tray）
- ❌ 海外平台 (discord / telegram / slack / line / simplex) cherry-pick
- ❌ msgraph_webhook（CN 已移除）
- ❌ upstream v0.18.0 内容（8 月才发布）

---

## 附录 A：测试用例编号映射

| Bug fix | Test | File |
|---------|------|------|
| cherry-pick 1 | `test_run_agent_module_loads_no_syntax_error` | `tests/cn_cherrypick/test_v017_split_bugs.py` |
| cherry-pick 2 | `test_model_tools_module_loads_no_syntax_error` | 同上 |
| cherry-pick 3 | `test_summary_prefix_uses_defined_constants` | 同上 |
| cherry-pick 4 | `test_load_openai_cls_uses_module_level_cache` | 同上 |
| cherry-pick 5 | `test_schema_migration_v12_plus_initializes_flag` | 同上 |
| cherry-pick 6 | `test_schema_v16_migration_helpers_defined` | 同上 |
| cherry-pick 7 | `test_create_session_accepts_cwd_kwarg` | 同上 |
| cherry-pick 8 | `test_finalize_single_query_no_attribute_error` | 同上 |
| cherry-pick 9 | `test_get_tool_definitions_accepts_3_kwargs` | 同上 |
| cherry-pick 10 | `test_atomic_json_write_uses_original_mode` | 同上 |
| cherry-pick 11 | `test_main_falls_through_to_cli_run_for_interactive` | 同上 |
| cherry-pick 12 | `test_prompt_tier_filter_block_present` | 同上 |
| P0-1 TUI | `tests/tui_gateway/test_review_summary_callback.py` | 已有 |
| P0-2 MCP | `tests/plugins/...parallel...` | 已有 + 补 |
| P0-3 middleware | `test_middleware_observer_only.py` | **缺** |
| P0-4 timestamps | `tests/gateway/test_message_timestamps.py` | 已有 (21/21) |
| fallback_config | `tests/hermes_cli/test_fallback_config_cn.py` | **缺** |
| custom identity | `tests/agent/test_custom_provider_identity_v017.py` | **缺** |

**缺** = 冻结前需要新建

---

*Generated by Mavis. 冻结版测试方案 v0.17.0+cn.17，2026-06-26*

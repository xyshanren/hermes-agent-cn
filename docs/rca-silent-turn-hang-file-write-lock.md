# RCA：patch/write_file 工具调用静默丢失（turn 无日志死亡）

**日期**：2026-09-26
**症状报告**：hermes 会话中制定好执行计划的任务经常中断，需人工催问才续上。
**会话**：`20260926_081554_86d315`（dsh 0.1.7-rc.2 升级任务，190 条消息 / 88 次 API 调用）。
**状态**：失败类已定位，`lock_path` 有界等待修复已落地（本 commit）；上游"持锁者卡死"的触发条件仍未复现，修复保证下次发生时立刻可见、可恢复。

## 症状

两次 turn 静默死亡，模式完全一致：

- `08:40:17.786`（API call #27）与 `08:49:32.149`（API call #36），模型各发出一个
  `patch` 工具调用（`scripts/clean.ts` 的 clean bug 修复 / 后续重试）；
- tool_executor 从未产出任何结果日志（正常路径必有 `tool patch completed` 或
  `Tool patch returned error`），agent.log / errors.log / gateway.log 三个日志在
  死亡窗口内对该会话**零记录**；
- turn 不再发起后续 API 调用、不产生任何终结输出，用户面对静止的界面只能催问；
- 转录中以 assistant+tool_calls 结尾、无 tool result（悬空调用），下一轮触发
  `Repaired 1 message-alternation violations` 善后。

用户催问后新一轮一切正常（甚至拿到了清理线程新建的全新终端环境），与"旧 turn
线程停在某个无超时阻塞点、被永久遗弃"的画像吻合。

## 取证

1. **悬空调用全库扫描**（state.db，7104 条带 tool_calls 的 assistant 消息）：
   共 **9 例**悬空（有 tool_calls 无对应 tool result），
   分布 `patch ×5 / write_file ×3 / terminal ×1`——**8/9 是走文件写路径的工具**。
   其中 `20260921_153917` 会话一小时内悬空 3 次 patch，说明该失败类早已存在。
2. **死亡点在工具执行内部**：悬空的 assistant 消息本身已入库（pre-execution
   flush 在 `_execute_tool_calls` 之前完成），排除执行前的全部环节。
3. **设计性退出全部排除**：executor 的中断路径会合成 `[Tool execution cancelled]`
   结果；conversation_loop 的持久化失败路径必打 WARNING；异常路径有
   `logger.exception`（ERROR 级）。三者均未出现 → 死因是**无日志的阻塞等待**，
   不是某条设计性 break。
4. **唯一符合画像的原语**：`tools/file_state.py::FileStateRegistry.lock_path` 使用
   无超时的 `threading.Lock.acquire()`，无任何日志。`patch_tool`/`write_file` 是
   仅有的两个调用方，恰好覆盖 8/9 悬空案例。路径上其它阻塞点均有界
   （env exec 有 `self.timeout` 兜底、审批等待有 60s/300s 超时、持久化失败有
   日志+退出），不满足"永久静默"条件。

## 修复

`tools/file_state.py`（本 commit）：

- `lock_path(timeout=30.0)`：`acquire(timeout=…)` 有界等待；超时抛新异常
  `FileLockBusy`，消息带**持有者线程名 + 已持有时长 + 目标路径**；
- 持有者信息由 `_lock_holders` 诊断表（`_meta_lock` 保护）提供；
- 超时同时打 WARNING 日志（agent.log + errors.log 可见）；
- `timeout=None` 保留历史无界语义（测试覆盖）；
- `patch_tool` / `write_file` 无需改动：现有 `except Exception → tool_error`
  兜底会把异常消息直接作为工具结果交给模型，变成可重试、可见的失败。

**修复前**：工具线程永久挂起 → turn 静默死亡 → 用户催问 → 转录悬空 → 下轮修复。
**修复后**：等锁 30s → WARNING 落盘 → 模型收到 "target file is locked by
another operation (thread X, held for Ns)…" 的错误结果，可重试或上报。

## 残余风险 / 未竟事项

- 卡死持锁者的**上游触发条件**未定位（当时无任何诊断可用，这正是本次修复补上
  的）。修复后若再次出现 FileLockBusy，日志会给出持有者线程名，即可顺藤摸瓜。
- terminal 的 1 例悬空（2026-08-24）属另一路径，样本 n=1，未动。
- 若确需无限等待的场景，显式传 `timeout=None`，不要回落默认值。

## 测试

`tests/tools/test_file_state_registry.py::FileLockBusyTests`：

- 争用锁在超时后抛 `FileLockBusy`，消息含路径/持有者线程名/重试指引；
- 持有者释放后新获取成功（持有者诊断表正确清理，不误报）；
- `timeout=None` 保持无界等待语义（等持有者释放后获得锁）。

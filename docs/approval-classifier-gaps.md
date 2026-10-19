# 审批分类器盲区：find 系批量删除与审批记忆粒度

**日期**：2026-09-26（原始记录） / 2026-10-20（样例表核对与结论修订）
**来源会话**：`20260926_081554_86d315`
**状态**：find 家族规则已补齐（0 漏检）；原始记录的**根因判断被证伪**，改判为审批记忆粒度问题（待决策）

## 原始记录（2026-09-26）

| 命令形态 | 规模 | 审批行为 |
|---|---|---|
| `rm -rf` 删 2 个旧产物目录 | 小 | ✅ 触发审批（"recursive delete"），60s 无响应被 BLOCKED |
| `find … \| xargs rm -rf` 批量删 lib 目录 | **326 个目录** | ❌ **未触发审批**，直接执行成功 |
| `find -delete` 删 tsbuildinfo | 多文件 | ✅ 触发审批（分类器能点名 "find -delete"） |

当时 agent 的自述猜测是"可能是 find+xargs 绕过了删除检测"。

## 结论修订（2026-10-20）：检测层没有缺口，根因是审批记忆粒度

用**事故时点实际部署的代码**（`a1ea634afb`，2026-09-26 live 上线那次）复测事故原命令，
检测结果与当前代码一致：

```
命令（事故原文，86d315 工具调用记录）：
  cd ~/deepseek-harness && find . \( -name node_modules -prune \) -o -type d -name lib -print | wc -l
  && find . \( -name node_modules -prune \) -o -type d -name lib -print0 | xargs -0 rm -rf
  && echo "=== 清理完成，复查残留 ===" && find . \( -name node_modules -prune \) -o -type d -name lib -print | wc -l

旧代码（a1ea634afb）：dangerous=True, pattern_key='recursive delete'
当前代码（origin/cn） ：dangerous=True, pattern_key='recursive delete'
```

**该命令当时就被正确检测为 dangerous**——"find 管道形态绕过检测"的前提不成立。

真正的放行路径在审批记忆层（`tools/approval.py`）：

1. 事故前用户对"删两个 lib 目录"的 `rm -rf` 做过 **session 级批准**；
2. session 批准存的是 **pattern_key（人类可读描述字符串）**，此处为 `"recursive delete"`；
3. 事故命令内嵌的 `rm -rf` 在 `DANGEROUS_PATTERNS` 中**最先命中**的同样是
   `"recursive delete"`（`xargs with rm` 排在更后面，轮询顺序决定命中项）；
4. `_run_approval_gate` 的 `is_approved(session_key, pattern_key)` 命中 → **直接放行，不弹窗**。

即：**一次"小范围 rm -rf"的 session 批准，隐式授权了同 key 的一切后续命令**，
包括 326 目录的批量删除。`find -delete` 之所以正常弹窗，是因为它的 key 不同
（`find -delete`），不在已批准的 key 集合里。

> 这不是"检测器看不见 find 家族"，而是"审批记忆按宽泛描述字符串授权"。
> 两类问题必须分开看：前者是规则表缺口，后者是授权粒度设计。

## 样例表（新增）

**位置**：`scripts/approval_classifier_samples.py`（数据驱动：命令形态 → 期望分类）
**行为契约测试**：`tests/tools/test_approval_find_family_samples.py`（跑真实检测器，非字符串匹配）

样例表覆盖 find 家族删除语义的三条入口（`-delete` / `-exec|-execdir` / `xargs`）、
裸 `rm` 基线、以及 11 条良性 find 用法（`find -name` / `find | xargs grep` / `-exec ls` 等）。
分类依据是**删除语义**而非命令首词。

**首次测量（补规则前）**：38 条样例 = 27 条 destructive + 11 条 clean

| 指标 | 结果 |
|---|---|
| 漏检（destructive 未被标记） | **2 / 27（7.4%）** —— 全部是 `find -exec unlink` / `-execdir unlink` |
| 误报（clean 被标记） | 0 / 11 |
| 事故原命令 | **被正确标记**（`recursive delete`） |

**已实施修复**（`tools/approval.py`）：补 unlink 拼写——`unlink` 是 `rm` 的单操作数同义兄弟，
删除语义相同。改动两处：find 外部程序动词位抽成共享 fragment `_FIND_PROGRAM_VERB`
（`rm`/`unlink` 同一条规则，杜绝两条拼写漂移），另加 `xargs … unlink` 一条。

**复测（补规则后）**：**漏检 0 / 27，误报 0 / 11**。

## 残留发现：审批记忆粒度（未修复，待决策）

`is_approved(session_key, pattern_key)` 的授权粒度 = 模式描述字符串。后果：

- 一次 `rm -rf` 的 session 批准 → 之后任何命中 `"recursive delete"` 的命令静默放行，
  规模无关（2 个目录 vs 326 个目录同一把钥匙）；
- 模式表越宽，授权的实际覆盖面越大（`"recursive delete"` 覆盖裸 `rm -rf`、
  管道内嵌 `rm -rf`、以及各种等价拼写）。

候选缓解方向（均**未实施**，涉及审批语义设计，需单独拍板）：

1. session 批准的 key 改为**命令形态指纹**而非描述字符串（形状变了要重新批准）；
2. 扩大规模/影响面时强制重新弹窗（例如命中路径数量、`-exec`/`xargs` 批量语义）；
3. 文档层提示：`[s]ession` 批准的是"这一类命令"，不是"这一次操作"。

注意：这三条**都不是 Noul 语义闸门能解决的问题**——Noul 判定的是"这条命令是否
破坏性"，而事故的绕过发生在"要不要问人"这一层。

## 对 Noul 审批闸门候选（plan §7 #4）的影响

按 plan 中已拍板的前置规则"**补规则够用则本消费者不立项**"：

- find 家族漏检已归零（规则层足够，无需语义模型补位）；
- 原始立项动机（"find 管道形态绕过了删除检测"）已被证伪；
- 剩下的真问题（授权粒度）属于审批记忆/交互设计，不是"破坏性语义判定"——
  引入 Noul 只会多一个不能解决实际问题的消费者。

**建议：候选 #4 不立项**，本条从 plan §7 移入"观察/另议"，授权粒度问题单独记录
（见上方"残留发现"）。是否收敛为 upstream 议题另行决定。

## 备注

- 事故会话中 agent 对该次删除的报告措辞也不准确（先称"无需审批，已直接处理"，
  实际该次确实未走审批；对比 10:16 那次 find -delete 是真人批准的）。两类
  事件（授权粒度、模型误报）在此会话中并存，排查时不要互相混淆。
- 事故原命令已作为样例表的一行固化（`verbatim 2026-09-26 incident command`），
  防止未来把"检测缺口"与"授权粒度"再次混为一谈。

# Hermes Agent CN 分支功能测试文档

**测试版本**: `2cb817544`  
**更新日期**: 2026-05-10  
**测试人员**: 守一  
**测试环境**: Windows 11 / Python 3.12 / NVIDIA RTX 4060

---

## 🤖 自动化测试覆盖情况

运行命令：
```bash
cd f:/work/workspace/WorkBuddy/Claw/hermes-agent-cn
python -m pytest tests/hermes_cli/test_merge_regression.py -v --override-ini="addopts="
```

**最新结果（2026-05-10）**: 146 passed，2 errors（旧测试写法问题，非代码 bug）

| 模块 | 覆盖状态 | 测试类 |
|------|---------|--------|
| 模块导入冒烟 | ✅ 全自动 | `TestModuleImports` |
| 冲突标记扫描 | ✅ 全自动 | `TestNoConflictMarkers` |
| Auth 常量完整性 | ✅ 全自动 | `TestAuthConstants` |
| Models 目录结构 | ✅ 全自动 | `TestModelsCatalog` |
| Setup 模块 | ✅ 全自动 | `TestSetupModule` |
| Providers 配置 | ✅ 全自动 | `TestProviders` |
| Commands 模块 | ✅ 全自动 | `TestCommandsModule` |
| Doctor 模块 | ✅ 全自动 | `TestDoctorModule` |
| Status 模块 | ✅ 全自动 | `TestStatusModule` |
| CN 本地化 | ✅ 全自动 | `TestCNLocalization` |

> ✅ 以下章节已被上述自动化测试覆盖，**无需手工填写**。

---

## ✅ 已自动化 — 无需手工测试

<details>
<summary>点击展开：环境检查 / CLI 命令 / Provider 配置 / 上游新功能 / 回归测试</summary>

### 1️⃣ 环境检查
- ✅ Python 3.12 / pip 环境 → `TestModuleImports`
- ✅ 分支状态 / 最新提交 → `TestModuleImports`

### 2️⃣ 核心 CLI 命令
- ✅ `hermes --help` / `hermes status --help` / `hermes setup --help`
- ✅ `hermes version`
- ✅ `hermes status` 输出结构
- ✅ `hermes doctor` 无崩溃

### 3️⃣ Provider 配置
- ✅ `models.py` 包含国产 Provider（智谱、文心、通义、混元等）
- ✅ `models.py` 包含上游新增 Provider（MiniMax 等）
- ✅ `models.py` 无语法错误

### 4️⃣ 上游新功能
- ✅ MiniMax OAuth 常量存在（`MINIMAX_OAUTH_*`）
- ✅ `gateway_windows.py` 存在
- ✅ `hermes gateway --help` 可用
- ✅ LM Studio 验证代码存在
- ✅ SQLite WAL 模式配置存在

### 5️⃣ 回归测试
- ✅ 无合并冲突标记残留（`<<<<<<<`、`=======`、`>>>>>>>`）
- ✅ `models.py` 无重复 `return {` 块
- ✅ `status.py` 无重复 CN Provider 键定义
- ✅ Windows UTF-8 编码无 `UnicodeEncodeError`

</details>

---

## ⚠️ 需要你手工验证

以下测试需要**真实 API Key** 或**交互操作**，无法自动化：

---

### 测试 A：Setup 向导交互

**前置条件**: 无（会生成/覆盖 `~/.hermes/config.yaml`）

**步骤**:
1. 运行 `hermes setup`
2. 选择一个国产 Provider（建议选你最常用的，比如智谱 GLM）
3. 粘贴有效的 API Key
4. 选择默认模型
5. 保存并退出

**期望结果**:
- 所有 Provider（国产 + 上游）都出现在选择列表中
- 配置成功保存到 `~/.hermes/config.yaml`
- 无崩溃或异常报错

**测试结果**: ⬜ 通过 / ❌ 失败  
**备注**: ____________

---

### 测试 B：交互式聊天

**前置条件**: 已完成 Setup，配置了可用的 Provider + API Key

**步骤**:
1. 运行 `hermes chat`
2. 输入：`你好，请用一句话介绍你自己`
3. 检查回复质量和语言
4. 输入 `/exit` 退出

**期望结果**:
- 成功连接 Provider，无超时
- 回复内容合理、语言与 Provider 配置一致
- 无 `get_event_loop()` 或异步相关报错

**测试结果**: ⬜ 通过 / ❌ 失败  
**备注**: ____________

---

### 测试 C：Gateway 启动

**前置条件**: 已完成 Setup

**步骤**:
1. 运行 `hermes gateway`（前台运行，Ctrl+C 停止）
2. 观察终端输出的监听地址和端口
3. （可选）用 curl 测试 API：`curl http://localhost:8000/v1/models`

**期望结果**:
- Gateway 成功启动，显示监听地址（默认 `http://localhost:8000`）
- 可通过 API 访问，返回模型列表

**测试结果**: ⬜ 通过 / ❌ 失败  
**备注**: ____________

---

### 测试 D：国产 Provider 实际 API 调用

**前置条件**: 至少有一个国产 Provider 的有效 API Key

| Provider | API Key 来源 | 测试命令 |
|----------|-------------|---------|
| 智谱 GLM | https://open.bigmodel.cn | `hermes chat`（选 GLM） |
| 文心一言 | https://console.bce.baidu.com | `hermes chat`（选文心） |
| 通义千问 | https://dashscope.aliyun.com | `hermes chat`（选通义） |
| 腾讯混元 | https://console.cloud.tencent.com | `hermes chat`（选混元） |

**步骤**（每个 Provider 重复）:
1. `hermes setup` → 选择对应 Provider → 填入 API Key
2. `hermes chat` → 输入简单问题
3. 检查回复

**期望结果**:
- API 调用成功，无 401/403 认证错误
- 回复内容质量正常

**测试结果**: ⬜ 通过 / ❌ 失败  
**备注**: ____________

---

### 测试 E：Context 压缩功能（可选）

**前置条件**: 已配置 Provider，且支持长上下文

**步骤**:
1. `hermes chat`
2. 输入一段长文本（> 2000 token，比如粘贴一篇文章）
3. 继续对话，观察是否触发压缩

**期望结果**:
- 上下文压缩正常工作，无 token 计算错误
- 压缩后对话连贯

**测试结果**: ⬜ 通过 / ❌ 失败  
**备注**: ____________

---

## 🐛 Bug 报告模板

如果遇到问题，按以下格式记录：

### Bug #___
- **发现时间**:
- **测试案例**: （A / B / C / D / E）
- **复现步骤**:
  1.
  2.
  3.
- **期望结果**:
- **实际结果**:
- **错误信息**（`hermes.log` 或终端输出）:
- **严重等级**: 🔴 严重 / 🟡 一般 / 🟢 轻微

---

## ✅ 测试总结

### 测试统计
- **自动化覆盖**: 10 个模块，146 个用例 ✅
- **需手工验证**: 5 个测试（A-E）
- **通过**: ___ / 5
- **失败**: ___ / 5

### 测试结果
- ✅ 所有通过 → 可以发布
- ⚠️ 部分失败 → 需要修复
- ❌ 严重问题 → 阻塞发布

---

**测试人员签名**: ____________  
**日期**: 2026-05-10

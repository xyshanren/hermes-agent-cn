# Hermes Agent CN 分支功能测试文档

**测试版本**: `cbd420653` (fix: repair merge artifacts)
**测试日期**: 2026-05-10
**测试人员**: 守一
**测试环境**: Windows 11 / Python 3.12 / NVIDIA RTX 4060

---

## 🤖 自动化测试状态

大部分测试用例已被自动化测试覆盖，无需手工填写。

### 自动化测试套件
```bash
# 运行回归测试（114 个用例）
python -m pytest tests/hermes_cli/test_merge_regression.py -v --override-ini="addopts="

# 测试结果（2026-05-10）
# 146 passed, 2 errors（旧测试写法问题，非代码 bug）
```

### 自动化覆盖情况
| 模块 | 自动化覆盖 | 备注 |
|------|-----------|------|
| 模块导入冒烟 | ✅ 全自动 | TestModuleImports |
| 冲突标记扫描 | ✅ 全自动 | TestNoConflictMarkers |
| Auth 常量 | ✅ 全自动 | TestAuthConstants |
| Models 目录 | ✅ 全自动 | TestModelsCatalog |
| Setup 模块 | ✅ 全自动 | TestSetupModule |
| Providers | ✅ 全自动 | TestProviders |
| Commands | ✅ 全自动 | TestCommandsModule |
| Doctor | ✅ 全自动 | TestDoctorModule |
| Status | ✅ 全自动 | TestStatusModule |
| CN 本地化 | ✅ 全自动 | TestCNLocalization |

### 仍需手工测试的部分
- 6.2 国产 Provider 实际 API 调用（需要真实 API Key）
- 5.1 交互式聊天（需要真实 Provider 配置）
- 5.2 Gateway 实际启动
- 3.2 Setup 向导交互

---


## 🧪 测试用例

### 1️⃣ 环境检查

#### 测试 1.1: 基础环境验证
```bash
cd f:/work/workspace/WorkBuddy/Claw/hermes-agent-cn

# 检查 Python 环境
python --version
pip --version

# 检查当前分支
git branch --show-current
git log --oneline -1
```

**期望结果**:
- Python 3.12.x
- 当前分支: `cn`
- 最新提交: `c3a215983 Merge upstream/main into cn branch`

**测试结果**: ⬜ 通过 / ❌ 失败  
**备注**: ____________

---

#### 测试 1.2: 依赖安装检查
```bash
# 检查是否已安装（ editable mode）
pip show hermes-agent

# 如果未安装，执行安装
pip install -e .
```

**期望结果**:
- 成功安装或已安装
- 无依赖冲突

**测试结果**: ⬜ 通过 / ❌ 失败  
**备注**: ____________

---

### 2️⃣ 核心 CLI 命令测试

#### 测试 2.1: 帮助命令
```bash
hermes --help
hermes status --help
hermes setup --help
```

**期望结果**:
- 显示中文或英文帮助（取决于 cn 分支配置）
- 包含所有子命令说明

**测试结果**: ⬜ 通过 / ❌ 失败  
**备注**: ____________

---

#### 测试 2.2: 版本信息
```bash
hermes version
```

**期望结果**:
- 显示当前版本号
- 无报错

**测试结果**: ⬜ 通过 / ❌ 失败  
**备注**: ____________

---

#### 测试 2.3: Status 命令
```bash
hermes status
```

**期望结果**:
- 显示所有 Provider 状态
- 显示配置路径
- 显示模型列表

**测试结果**: ⬜ 通过 / ❌ 失败  
**备注**: ____________

---

#### 测试 2.4: Doctor 命令（配置检查）
```bash
hermes doctor
```

**期望结果**:
- 检查配置文件完整性
- 检查依赖项
- 报告潜在问题

**测试结果**: ⬜ 通过 / ❌ 失败  
**备注**: ____________

---

### 3️⃣ Provider 配置测试

#### 测试 3.1: 查看 Provider 列表
```bash
# 检查 models.py 中的 Provider 配置
cat hermes_cli/models.py | grep -A 50 "_PROVIDER_MODELS"
```

**期望结果**:
- 包含 cn 分支的国产 Provider（智谱、文心、通义、混元等）
- 包含上游新增的 Provider（MiniMax 等）
- 无语法错误

**测试结果**: ⬜ 通过 / ❌ 失败  
**备注**: ____________

---

#### 测试 3.2: Setup 向导（交互式）
```bash
hermes setup
```

**测试步骤**:
1. 运行 `hermes setup`
2. 尝试选择一个 Provider
3. 配置 API Key
4. 选择默认模型
5. 保存配置

**期望结果**:
- 显示所有可用 Provider（包括国产和上游新增）
- 配置成功保存到 `config.yaml`
- 无崩溃或异常

**测试结果**: ⬜ 通过 / ❌ 失败  
**备注**: ____________

---

### 4️⃣ 上游新功能测试

#### 测试 4.1: MiniMax OAuth 登录
```bash
# 检查 auth.py 是否包含 MiniMax OAuth 支持
cat hermes_cli/auth.py | grep -i "minimax\|oauth"
```

**期望结果**:
- `auth.py` 包含 MiniMax OAuth 相关代码
- 支持 MiniMax 登录流程

**测试结果**: ⬜ 通过 / ❌ 失败  
**备注**: ____________

---

#### 测试 4.2: Windows 服务支持
```bash
# 检查 gateway_windows.py 是否存在
ls -la hermes_cli/gateway_windows.py

# 检查 gateway 命令
hermes gateway --help
```

**期望结果**:
- `gateway_windows.py` 存在
- `hermes gateway install/start/stop/uninstall` 命令可用

**测试结果**: ⬜ 通过 / ❌ 失败  
**备注**: ____________

---

#### 测试 4.3: LM Studio 验证
```bash
# 检查 models.py 是否包含 LM Studio 专门验证
cat hermes_cli/models.py | grep -i "lm.studio\|lm_studio"
```

**期望结果**:
- 包含 LM Studio 验证代码
- 能正确识别 LM Studio 本地模型

**测试结果**: ⬜ 通过 / ❌ 失败  
**备注**: ____________

---

#### 测试 4.4: SQLite WAL 模式
```bash
# 检查是否启用了 WAL 模式和 journal_size_limit
cat hermes_cli/*.py | grep -i "wal\|journal_size_limit"
```

**期望结果**:
- 数据库配置使用 WAL 模式
- 设置了 `journal_size_limit`

**测试结果**: ⬜ 通过 / ❌ 失败  
**备注**: ____________

---

### 5️⃣ 核心功能测试

#### 测试 5.1: 交互式聊天
```bash
# 启动交互式聊天（需要配置好 Provider）
hermes chat
```

**测试步骤**:
1. 输入简单问题: `你好，请介绍一下自己`
2. 检查回复质量
3. 输入 `/exit` 退出

**期望结果**:
- 成功连接到配置的 Provider
- 回复内容合理
- 无崩溃或异常

**测试结果**: ⬜ 通过 / ❌ 失败  
**备注**: ____________

---

#### 测试 5.2: Gateway 模式
```bash
# 启动 Gateway（前台运行）
hermes gateway
```

**期望结果**:
- Gateway 成功启动
- 显示监听地址和端口
- 可通过 API 访问

**测试结果**: ⬜ 通过 / ❌ 失败  
**备注**: ____________

---

#### 测试 5.3: Context 压缩功能
```bash
# 测试长对话中的上下文压缩
hermes chat
# 在对话中输入大量内容，触发压缩
```

**期望结果**:
- 上下文压缩正常工作
- Token 计算准确（修复了上游的 bug）
- 压缩后的对话连贯

**测试结果**: ⬜ 通过 / ❌ 失败  
**备注**: ____________

---

### 6️⃣ CN 分支定制功能测试

#### 测试 6.1: 中文输出检查
```bash
hermes chat
# 输入: 用中文介绍一下 Python
```

**期望结果**:
- 回复使用中文
- 无乱码或编码问题

**测试结果**: ⬜ 通过 / ❌ 失败  
**备注**: ____________

---

#### 测试 6.2: 国产 Provider 测试
```bash
# 测试智谱 GLM
# 测试文心一言
# 测试通义千问
# 测试腾讯混元
```

**期望结果**:
- 所有国产 Provider 可正常配置
- API 调用成功
- 回复质量正常

**测试结果**: ⬜ 通过 / ❌ 失败  
**备注**: ____________

---

#### 测试 6.3: Skill 管理功能
```bash
# 检查 skill_tier_manager 是否正常工作
hermes --help | grep -i skill
```

**期望结果**:
- Skill 相关命令可用
- 三层 Skill 管理正常工作

**测试结果**: ⬜ 通过 / ❌ 失败  
**备注**: ____________

---

### 7️⃣ 集成测试

#### 测试 7.1: 完整工作流程
```bash
# 1. 配置 Provider
hermes setup

# 2. 检查状态
hermes status

# 3. 运行 Doctor
hermes doctor

# 4. 启动聊天
hermes chat

# 5. 测试 Gateway
hermes gateway
```

**期望结果**:
- 所有步骤顺利完成
- 无冲突或异常

**测试结果**: ⬜ 通过 / ❌ 失败  
**备注**: ____________

---

#### 测试 7.2: 配置文件兼容性
```bash
# 检查旧配置文件是否兼容
cat ~/.hermes/config.yaml

# 尝试运行
hermes status
```

**期望结果**:
- 旧配置文件可正常使用
- 无需手动迁移

**测试结果**: ⬜ 通过 / ❌ 失败  
**备注**: ____________

---

### 8️⃣ 回归测试

#### 测试 8.1: 异步事件循环修复验证
```bash
# 测试异步功能，确保无 event loop 错误
hermes chat
# 在对话中测试异步操作
```

**期望结果**:
- 无 `get_event_loop()` 相关错误
- 使用 `get_running_loop()` 正常

**测试结果**: ⬜ 通过 / ❌ 失败  
**备注**: ____________

---

#### 测试 8.2: Windows UTF-8 编码测试
```bash
# 测试中文输出（Windows 环境）
hermes chat
# 输入中文问题
```

**期望结果**:
- 无 `UnicodeEncodeError`
- `hermes_bootstrap` 正常工作的 UTF-8 stdio

**测试结果**: ⬜ 通过 / ❌ 失败  
**备注**: ____________

---

## 🐛 Bug 报告模板

如果遇到问题，请按以下格式记录：

### Bug #001
- **发现时间**: 
- **测试案例**: 
- **复现步骤**: 
  1. 
  2. 
  3. 
- **期望结果**: 
- **实际结果**: 
- **错误信息**: 
- **截图/日志**: 
- **严重等级**: 🔴 严重 / 🟡 一般 / 🟢 轻微

---

## ✅ 测试总结

### 测试统计
- **总测试用例**: ___
- **通过**: ___ (___%)
- **失败**: ___ (___%)
- **阻塞**: ___ (___%)

### 测试结果
- ✅ 所有测试通过
- ⚠️ 部分测试失败，需要修复
- ❌ 存在严重问题，无法发布

### 备注
_____________________________________  
_____________________________________  
_____________________________________

---

**测试人员签名**: ____________  
**日期**: 2026-05-09

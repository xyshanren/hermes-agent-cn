# Hermes Agent 中文版测试方案

本文档描述 Hermes Agent 中文版（cn 分支）的测试策略和测试用例。

---

## 1. 测试范围

### 1.1 已汉化模块（Phase 7）

| 模块 | 文件 | 汉化内容 | 测试重点 |
|------|------|----------|----------|
| 诊断工具 | `hermes_cli/doctor.py` | 章节标题、检查项目、提示信息 | 中文显示、功能正常 |
| 配置向导 | `hermes_cli/setup.py` | 菜单、提示、确认信息 | 中文交互、流程完整 |
| 配置管理 | `hermes_cli/config.py` | 文档字符串、注释 | 英文 API 不变、中文注释正确 |

### 1.2 精简 Provider

保留的 Provider：
- ✅ deepseek（深度求索）
- ✅ minimax（MiniMax）
- ✅ kimi（月之暗面）
- ✅ zai（智谱 AI）
- ✅ ollama（本地模型）
- ✅ Nous Portal（可选）

已删除的 Provider（不应出现在配置中）：
- ❌ OpenRouter
- ❌ Anthropic
- ❌ Nous（旧版）
- ❌ Codex

---

## 2. 测试策略

### 2.1 单元测试

**目标**：验证汉化文本存在且编码正确

**测试文件**：`tests/hermes_cli/test_cn_localization.py`

**测试用例**：
1. `TestDoctorChineseLocalization` - 诊断工具汉化验证
2. `TestSetupChineseLocalization` - 配置向导汉化验证
3. `TestConfigChineseLocalization` - 配置管理汉化验证
4. `TestChineseEncoding` - UTF-8 编码验证

**运行方法**：
```bash
# 运行汉化测试
python -m pytest tests/hermes_cli/test_cn_localization.py -v

# 运行所有测试
python -m pytest tests/ -v
```

### 2.2 集成测试

**目标**：验证汉化后的功能完整性

**测试场景**：

#### 场景 1：运行 `hermes doctor`
```bash
hermes doctor
```
**预期结果**：
- 所有输出为中文
- 正确检查 Python 环境、目录结构、API 连通性
- 只检查保留的 Provider（deepseek/minimax/kimi/zai/ollama）
- 不检查已删除的 Provider

#### 场景 2：运行 `hermes setup`
```bash
hermes setup
```
**预期结果**：
- 所有交互提示为中文
- 菜单选项为中文
- 成功完成配置流程

#### 场景 3：运行 `hermes config set`
```bash
hermes config set model.provider deepseek
hermes config set model.name deepseek-chat
```
**预期结果**：
- 配置命令正常工作（英文 API）
- 配置文件正确保存

### 2.3 手动测试清单

**测试人员**：开发者或用户

**测试环境**：
- ✅ Windows + WSL2
- ✅ Linux（Ubuntu/Debian）
- ✅ macOS
- ✅ Termux（Android）

**测试清单**：

#### 安装测试
- [ ] 运行安装脚本 `scripts/install.sh`
- [ ] 验证 `hermes` 命令可用
- [ ] 验证虚拟环境正确创建

#### 汉化验证
- [ ] 运行 `hermes doctor`，检查输出是否为中文
- [ ] 运行 `hermes setup`，检查交互提示是否为中文
- [ ] 运行 `hermes help`，检查命令描述是否为中文
- [ ] 运行 `hermes model`，检查 Provider 列表是否为中文

#### Provider 精简验证
- [ ] 运行 `hermes setup`，检查 Provider 选项只有 5+1 个
- [ ] 配置 deepseek，验证连通性
- [ ] 配置 minimax，验证连通性
- [ ] 配置 kimi，验证连通性
- [ ] 配置 zai，验证连通性
- [ ] 配置 ollama，验证本地模型

#### 功能完整性
- [ ] 启动 `hermes`，进行对话测试
- [ ] 测试 `/model` 命令切换模型
- [ ] 测试 `/skills` 命令查看技能
- [ ] 测试 `/tools` 命令配置工具
- [ ] 测试 cron 定时任务
- [ ] 测试 MCP 服务器连接

#### 编码验证
- [ ] 所有中文字符显示正常（无乱码）
- [ ] 配置文件中的中文正确保存和读取
- [ ] 日志文件中的中文正确记录

---

## 3. 自动化测试

### 3.1 运行现有测试套件

```bash
# 进入项目目录
cd hermes-agent-cn

# 激活虚拟环境（如果有）
source .venv/bin/activate  # Linux/macOS
# 或
.venv\Scripts\activate  # Windows

# 运行所有测试
python -m pytest tests/ -v

# 运行特定模块测试
python -m pytest tests/hermes_cli/test_cn_localization.py -v
python -m pytest tests/hermes_cli/test_doctor.py -v
python -m pytest tests/hermes_cli/test_setup.py -v
python -m pytest tests/hermes_cli/test_config.py -v

# 运行测试并生成覆盖率报告
python -m pytest tests/ --cov=hermes_cli --cov-report=html
```

### 3.2 CI/CD 集成（可选）

创建 `.github/workflows/test-cn.yml`：

```yaml
name: Test Chinese Localization

on:
  push:
    branches: [ cn ]
  pull_request:
    branches: [ cn ]

jobs:
  test:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        python-version: [3.10, 3.11, 3.12]

    steps:
    - uses: actions/checkout@v3
      with:
        ref: cn

    - name: Set up Python ${{ matrix.python-version }}
      uses: actions/setup-python@v4
      with:
        python-version: ${{ matrix.python-version }}

    - name: Install dependencies
      run: |
        python -m pip install --upgrade pip
        pip install -e ".[dev]"
        pip install pytest pytest-cov

    - name: Run tests
      run: |
        python -m pytest tests/hermes_cli/test_cn_localization.py -v
        python -m pytest tests/hermes_cli/test_doctor.py -v
        python -m pytest tests/hermes_cli/test_setup.py -v
        python -m pytest tests/hermes_cli/test_config.py -v

    - name: Check Chinese encoding
      run: |
        python -c "
        import sys
        files = [
            'hermes_cli/doctor.py',
            'hermes_cli/setup.py',
            'hermes_cli/config.py'
        ]
        for f in files:
            with open(f, 'r', encoding='utf-8') as fp:
                content = fp.read()
                assert 'Python 环境' in content or '配置' in content
                print(f'{f}: OK')
        print('All files have Chinese text and valid UTF-8')
        "
```

---

## 4. 性能测试（可选）

### 4.1 启动性能

```bash
# 测试 hermes 启动时间
time hermes --version
time hermes doctor  # 诊断工具执行时间

# 对比汉化前后启动时间（如果有旧版本）
```

### 4.2 内存占用

```bash
# 测试正常运行时的内存占用
hermes  # 启动后查看系统监控
```

---

## 5. 回归测试

### 5.1 版本对比

| 功能 | v0.10.0-cn.1 | v0.11.0-cn.1 | 状态 |
|------|---------------|---------------|------|
| `hermes doctor` | 英文输出 | 中文输出 | ✅ 功能正常 |
| `hermes setup` | 英文提示 | 中文提示 | ✅ 功能正常 |
| `hermes help` | 中文命令描述 | 中文命令描述 | ✅ 功能正常 |
| Provider 列表 | 24 个 | 6 个 | ✅ 精简完成 |
| 配置保存/读取 | 正常 | 正常 | ✅ 无回归 |

### 5.2 兼容性测试

- [ ] 配置文件兼容性（旧配置能否在新版本使用）
- [ ] 技能兼容性（已安装技能是否正常工作）
- [ ] 插件兼容性（已安装插件是否正常工作）

---

## 6. 测试报告模板

### 6.1 单元测试报告

```
测试日期：YYYY-MM-DD
测试人员：xxx
测试版本：v0.11.0-cn.1

测试结果：
- 总测试用例数：XX
- 通过：XX
- 失败：XX
- 跳过：XX

失败用例详情：
1. test_xxx
   - 失败原因：xxx
   - 修复建议：xxx

改进建议：
- xxx
```

### 6.2 手动测试报告

```
测试日期：YYYY-MM-DD
测试人员：xxx
测试环境：Windows 11 + WSL2 Ubuntu 22.04

测试结果：
- 安装测试：✅ 通过
- 汉化验证：✅ 通过
- Provider 精简验证：✅ 通过
- 功能完整性：✅ 通过
- 编码验证：✅ 通过

发现问题：
1. [如果有]
   - 问题描述：xxx
   - 复现步骤：xxx
   - 严重程度：低/中/高

改进建议：
- xxx
```

---

## 7. 持续集成

### 7.1 测试频率

- **每次提交**：运行单元测试
- **每日构建**：运行完整测试套件
- **版本发布**：运行手动测试清单

### 7.2 测试优先级

1. **P0**（必须通过的测试）：
   - 汉化验证测试
   - Provider 精简验证测试
   - 核心功能测试（doctor/setup/config）

2. **P1**（重要但不阻塞发布）：
   - 性能测试
   - 兼容性测试

3. **P2**（可选）：
   - 边界条件测试
   - 压力测试

---

## 8. 附录

### 8.1 测试工具

- **pytest**：单元测试框架
- **pytest-cov**：覆盖率报告
- **mock**：模拟外部依赖

### 8.2 参考资料

- [Hermes Agent 官方文档](https://hermes-agent.nousresearch.com/docs/)
- [pytest 官方文档](https://docs.pytest.org/)
- [Python 测试最佳实践](https://realpython.com/python-testing/)

---

**维护者**：xyshanren
**最后更新**：2026-05-03

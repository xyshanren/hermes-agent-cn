# Hermes Agent CN v0.12.0-cn.3 Bug 修复测试报告

**测试版本**: `b5cf959f0` (v0.12.0-cn.3)  
**更新日期**: `2026-05-13`  
**测试人员**: 阿福（自动化测试）  
**测试环境**: Windows 11 / Python 3.12.10 / RTX 4060 8GB  
**测试时间**: 2026-05-13 10:05:35  
**分支**: `cn`

---

## 🎯 测试目标

验证 v0.12.0-cn.3 中 3 个 Bug 的修复是否生效：

| Bug | 标题 | 预期结果 |
|-----|------|---------|
| #1 | `hermes setup` 后 `.env` 未生成 | ✅ 已修复 |
| #2 | Provider 列表问题 | ✅ 已修复 |
| #3 | `hermes chat` 报 "empty API key" | ✅ 已修复 |

---

## 🤖 自动化测试结果

```bash
python -m pytest tests/hermes_cli/test_merge_regression.py -v --override-ini="addopts="
```

**测试结果 (2026-05-13)**: `114 passed，0 errors`（耗时 6.83s）

| 模块 | 覆盖状态 | 用例数 |
|------|---------|--------|
| 模块导入冒烟 | ✅ 全通过 | `TestModuleImports` |
| 冲突标记扫描 | ✅ 全通过 | `TestNoConflictMarkers` |
| Auth 常量完整性 | ✅ 全通过 | `TestAuthConstants` |
| Models 目录结构 | ✅ 全通过 | `TestModelsCatalog` |
| Setup 模块 | ✅ 全通过 | `TestSetupModule` |
| Providers 配置 | ✅ 全通过 | `TestProviders` |
| Commands 模块 | ✅ 全通过 | `TestCommandsModule` |
| Doctor 模块 | ✅ 全通过 | `TestDoctorModule` |
| Status 模块 | ✅ 全通过 | `TestStatusModule` |
| CN 本地化 | ✅ 全通过 | `TestCNLocalization` |

---

## ✅ Bug #1：`hermes setup` 后不生成 `~/.hermes/.env`

**Bug 描述**: 配置 DeepSeek API Key 后，`~/.hermes/` 目录中找不到 `.env` 文件。

**修复位置**: `hermes_cli/config.py` → `save_env_value()` 函数（已在 v0.12.0-cn.1 引入，cn.3 确认稳定）

**验证方法**: 模拟调用 `save_env_value('DEEPSEEK_API_KEY', 'sk-test12345')` 检查文件生成

**验证结果**:
```
✅ .env 文件成功生成
   内容: DEEPSEEK_API_KEY=sk-test12345
✅ DeepSeek Key 写入正确
```

**关键代码路径**:
```python
# hermes_cli/config.py:4324
def save_env_value(key: str, value: str):
    """Save or update a value in ~/.hermes/.env."""
    ...
    ensure_hermes_home()
    env_path = get_env_path()
    # 使用原子替换（tempfile → fsync → rename）保证写入安全
    fd, tmp_path = tempfile.mkstemp(dir=str(env_path.parent), suffix='.tmp', prefix='.env_')
    ...
    atomic_replace(tmp_path, env_path)
```

**结论**: ✅ **通过** — `.env` 文件正常生成，API Key 写入正确

---

## ✅ Bug #2：`/model` Provider 列表问题

**Bug 描述**: Provider 列表缺少 SiliconFlow，包含 minimax 国际版，DeepSeek 缺少 r1-distill 系列。

**修复位置**: `hermes_cli/models.py`

**验证方法**: Python 直接导入并检查 `CANONICAL_PROVIDERS`、`_cn_skip_providers`、`_PROVIDER_MODELS`

### 2.1 SiliconFlow 是否存在

```
✅ siliconflow 存在: "硅基流动（SiliconFlow）"
```

**SiliconFlow 模型列表（25 个）**:
- `Qwen/Qwen2.5-72B-Instruct`, `Qwen/Qwen2.5-7B-Instruct` 等 Qwen 系列
- `ZhipuAI/GLM-4-9B-Chat`, `ZhipuAI/GLM-4-Plus` 等 GLM 系列
- `deepseek-ai/DeepSeek-V3`, `deepseek-ai/DeepSeek-R1` 等 DeepSeek 系列
- `01ai/Yi-1.5-34B-Chat-16K` 等 Yi 系列
- `meta-llama/Llama-3.3-70B-Instruct` 等

### 2.2 MiniMax 国际版是否被过滤

```
✅ minimax（国际版）已被过滤，不在 Provider 列表中
✅ minimax-cn（国内版）存在
   _cn_skip_providers = {'minimax'}
```

**过滤机制**:
```python
# hermes_cli/models.py:638
_cn_skip_providers = {"minimax"}  # cn branch only shows minimax-cn
...
if _pp.name in _cn_skip_providers:
    continue  # skip cn-branch exclusions
```

### 2.3 DeepSeek r1-distill 系列

```
✅ DeepSeek r1-distill 系列存在（8 个）:
   - deepseek-r1-distill-qwen-7b
   - deepseek-r1-distill-qwen-14b
   - deepseek-r1-distill-qwen-32b
   - deepseek-r1-distill-qwen-1.5b
   - deepseek-r1-distill-qwen-0.5b
   - deepseek-r1-distill-llama-8b
   - deepseek-r1-distill-llama-24b
   - deepseek-r1-distill-llama-70b
```

**DeepSeek 完整模型列表（13 个）**:
- `deepseek-chat` (兼容旧配置)
- `deepseek-v3` (新增)
- `deepseek-r1`, `deepseek-r1-250120`, `deepseek-r1-0528` (最新版本)
- `deepseek-r1-distill-*` 系列（8 个，含 Qwen/Llama 蒸馏版本）

**结论**: ✅ **通过** — SiliconFlow ✅、minimax 国际版已过滤 ✅、r1-distill 系列完整 ✅

---

## ✅ Bug #3：配置 API Key 后报 "empty API key"

**Bug 描述**: 通过 `hermes setup` 将 API Key 保存到 `~/.hermes/.env` 后，`hermes chat` 仍报 `Provider resolver returned an empty API key` 错误。

**根因**: `auth.py` 中 `resolve_provider()` 使用 `os.getenv()` 检测 Key，只读 Shell 环境变量，不读 `~/.hermes/.env` 文件。

**修复位置**: `hermes_cli/auth.py:1212-1229` → 改用 `get_env_value()`

**验证方法**:
1. 模拟 `~/.hermes/.env` 中有 `DEEPSEEK_API_KEY`，Shell 环境中无该变量
2. 调用 `get_env_value('DEEPSEEK_API_KEY')` 验证能读到文件中的值
3. 代码静态分析确认 `resolve_provider()` 已使用 `get_env_value()`

**验证结果**:
```
✅ get_env_value() 成功从 .env 文件读取 DeepSeek Key
✅ resolve_provider() 使用了 get_env_value() 读取 .env 文件
✅ api_key_env_vars 循环中使用了 get_env_value（不再只用 os.getenv）
```

**修复后的代码**:
```python
# hermes_cli/auth.py:1212-1229
# Use get_env_value() to read from both shell env and ~/.hermes/.env
from hermes_cli.config import get_env_value as _get_env_value
if has_usable_secret(_get_env_value("OPENAI_API_KEY") or "") or \
   has_usable_secret(_get_env_value("OPENROUTER_API_KEY") or ""):
    return "openrouter"

for pid, pconfig in PROVIDER_REGISTRY.items():
    if pconfig.auth_type != "api_key":
        continue
    for env_var in pconfig.api_key_env_vars:
        from hermes_cli.config import get_env_value
        if has_usable_secret(get_env_value(env_var) or ""):  # ← 关键修复
            return pid
```

**`get_env_value()` 读取优先级**:
1. `os.environ`（Shell 环境变量）优先
2. 回退到 `~/.hermes/.env` 文件（`load_env()` 读取）

**结论**: ✅ **通过** — `resolve_provider()` 现在正确读取 `.env` 文件中的 API Key

---

## 📊 Current Provider 列表（28 个）

| # | slug | 显示名称 |
|---|------|---------|
| 1 | deepseek | DeepSeek |
| 2 | kimi-coding | Kimi / Moonshot |
| 3 | kimi-coding-cn | Kimi / Moonshot（国内）|
| 4 | minimax-cn | MiniMax（国内）|
| 5 | zai | 智谱 AI / GLM |
| 6 | alibaba | 阿里云（DashScope）|
| 7 | xiaomi | 小米 MiMo |
| 8 | qwen-oauth | 通义千问 OAuth（Portal）|
| 9 | siliconflow | **硅基流动（SiliconFlow）** ← 新增 |
| 10 | ollama | Ollama（本地）|
| 11-28 | anthropic, gemini, openrouter 等 | 上游 Provider |

> ⚠️ `minimax`（国际版）已从列表中移除，由 `minimax-cn` 替代。

---

## ✅ 测试总结

### 测试统计

- **自动化回归测试**: 10 个模块，**114 个用例全部通过** ✅
- **Bug 专项验证**: 3 个 Bug，**3 个通过** ✅

### Bug 修复状态

| Bug | 标题 | 状态 | 验证方式 |
|-----|------|------|---------|
| #1 | `hermes setup` `.env` 文件生成 | ✅ **已修复** | 单元测试模拟写入 |
| #2.1 | SiliconFlow 缺失 | ✅ **已修复** | 代码导入验证 |
| #2.2 | minimax 国际版过多 | ✅ **已修复** | `_cn_skip_providers` 过滤 |
| #2.3 | DeepSeek r1-distill 缺失 | ✅ **已修复** | 模型列表验证（8个） |
| #3 | `hermes chat` empty API key | ✅ **已修复** | 静态分析 + 单元测试 |

### 结论

> ✅ **v0.12.0-cn.3 所有 3 个 Bug 均已修复，回归测试全部通过，可以发布。**

---

## 🔴 手工测试阶段发现的新问题（2026-05-13 11:17）

> ⚠️ **以下问题在手工测试阶段发现，已修复但尚未推送到远程仓库**

### 问题 A：`LMSTUDIO_NOAUTH_PLACEHOLDER` 缺失（阻塞 setup）

**现象**: `hermes setup` 选择任意 Provider 后报错：
```
Provider setup encountered an error: cannot import name 'LMSTUDIO_NOAUTH_PLACEHOLDER' from 'hermes_cli.auth'
```

**根因**: 上游 `214ca943a`（feat: add lmstudio integration）在 `auth.py` 中添加了 `LMSTUDIO_NOAUTH_PLACEHOLDER` 常量。cn 分支合并时（`cbd420653` 修复合并冲突）遗漏了该常量。

**修复**: `hermes_cli/auth.py:118` 后补加：
```python
LMSTUDIO_NOAUTH_PLACEHOLDER = "dummy-lm-api-key"
```

**状态**: ✅ 已修复（本地），待推送

---

### 问题 B：Provider 列表过滤不完整

**现象**: `hermes setup` 的 Provider 选择列表仍显示 anthropic、gemini、openrouter 等 17 个国际版 Provider。

**根因**: `_cn_skip_providers` 只过滤了 `minimax`，但 `providers/` 模块动态注册了 17 个国际版 Provider，全部通过 `list_providers()` 注入到 `CANONICAL_PROVIDERS`。

**修复**: 扩展 `_cn_skip_providers` 为完整过滤列表：
```python
_cn_skip_providers = {
    "minimax", "anthropic", "gemini", "openrouter",
    "azure-foundry", "arcee", "gmi", "huggingface",
    "nvidia", "stepfun", "xai", "ollama-cloud",
    "opencode-zen", "opencode-go", "ai-gateway",
    "alibaba-coding-plan", "custom", "kilocode",
}
```

**过滤后列表（11 个）**:
- 国产：deepseek, kimi-coding, kimi-coding-cn, minimax-cn, zai, alibaba, xiaomi, qwen-oauth, siliconflow
- 本地：ollama
- 可选：nous

**状态**: ✅ 已修复（本地），待推送

---

### 问题 C：版本号未显示 cn 标识

**现象**: `hermes version` 显示 `v0.13.0` 而非 `v0.12.0-cn.3`

**根因**: `pyproject.toml` 中 `version = "0.13.0"`，cn 分支没有独立版本号机制。

**建议**: 在 `hermes_cli/__init__.py` 或 `hermes_constants.py` 中添加 `CN_VERSION_SUFFIX = "-cn.3"`，让 `hermes version` 显示 `v0.13.0-cn.3`。

**状态**: ⬜ 待评估（非阻塞）

---

### 问题 D：doctor 输出优化建议

**D1 — .env 文件检测**
- **现象**: `hermes quickstart` 已配置 Ollama，但 `hermes doctor` 仍报 `~/.hermes/.env file missing`
- **建议**: 如果已配置本地模型（Ollama），`.env` 缺失不应报 error，可降为 warning 或 info

**D2 — 虚拟环境检测**
- **现象**: 使用 Anaconda 虚拟环境，但 doctor 报 `Not in virtual environment`
- **建议**: 检测 `CONDA_DEFAULT_ENV` 环境变量，识别 Anaconda/conda 环境

**D3 — 本地模型重复提示**
- **现象**: 已有 Ollama 模型（qwen2.5-vl-7b:q6 等），doctor 仍提示安装 Qwen2.5-Coder-1.5B 和 Qwen2.5-0.5B
- **建议**: 
  - 如果检测到 Ollama 已有可用模型，跳过默认本地模型安装提示
  - 或在 `hermes chat` 使用本地模型时，若模型不存在再提示下载

**状态**: ⬜ 待评估（体验优化，非阻塞）

---

## 📋 修复提交清单

| 文件 | 变更 | 状态 |
|------|------|------|
| `hermes_cli/auth.py` | 添加 `LMSTUDIO_NOAUTH_PLACEHOLDER` | ✅ 本地已修复 |
| `hermes_cli/models.py` | 扩展 `_cn_skip_providers` 过滤列表 | ✅ 本地已修复 |

**待推送**: `git push origin cn`

---

**测试人员签名**: 阿福（自动化）  
**日期**: 2026-05-13

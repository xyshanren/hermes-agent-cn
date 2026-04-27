# Task: Hermes 本地模型集成 — doctor.py 和 setup.py 改造

**时间**: 2026-04-24 13:46
**状态**: ⚠️ 部分完成

## 当前状态（2026-04-27 11:38 验证）

| 组件 | 状态 | 参考 |
|------|------|------|
| doctor.py 本地模型检查 | ✅ 完成 | 行 1054-1105 |
| setup.py setup_local_models | ✅ 完成 | 行 2375 |
| setup.py SETUP_SECTIONS 注册 | ✅ 完成 | "local-models" 已注册 |
| model_manager.py download | ⚠️ scaffold | git lfs + ModelScope API 骨架 |

## 目标
继续 hermes-agent-cn 的改造，完成：
1. doctor.py — 添加本地模型状态检测
2. setup.py — 添加模型安装向导
3. model_manager.py — install 命令的实际下载逻辑（待完善）

## 已完成

### 1. doctor.py 改造
*(状态: 已完成)*
在 Memory Provider 和 Profiles 之间新增 "本地模型" 检查部分：

```python
# 检查内容：
- 模型目录是否存在 (~/.hermes/models/)
- 每个模型的安装状态和占用空间
- 运行时依赖检查 (faster-whisper, onnxruntime, llama-cpp-python)
- 汇总已安装模型数量和总占用空间
```

**文件**: `hermes_cli/doctor.py`
**改动**: +46 行（新增一个检查 section）

### 2. setup.py 改造

#### 2.1 新增 setup_local_models 函数
*(状态: 已完成)*
```python
def setup_local_models(config: dict):
    """Configure local offline models (STT, TTS, LLM)."""
    # 显示模型列表，让用户选择安装
    # 支持多选 checklist
    # 批量安装选中的模型
    # 检查运行时依赖
```

#### 2.2 更新 SETUP_SECTIONS
新增 `("local-models", "本地离线模型", setup_local_models)` 条目

#### 2.3 更新返回用户菜单
- 新增 "本地离线模型" 选项
- 更新 RETURNING_USER_MENU_SECTION_KEYS
- 调整选项索引逻辑 (choice == 8 为退出)

#### 2.4 集成到完整安装流程
在 Section 5 (Tools) 之后增加 Section 6 (Local Models)

**文件**: `hermes_cli/setup.py`
**改动**: +105 行

## 待完善（P2）— 模型安装下载逻辑

| 任务 | 说明 |
|------|------|
| model_manager.py install 下载逻辑 | 当前是 scaffold，需接入 ModelScope/HuggingFace hub SDK |
| hermes local-models test 实现 | 各模型的具体测试函数待实现 |
| _skip_configured_section 支持 | 添加 "local-models" 的配置检测逻辑 |

## 文件变更

| 文件 | 改动类型 | 行数 |
|------|----------|------|
| `hermes_cli/doctor.py` | 新增 section | +46 |
| `hermes_cli/setup.py` | 新增函数 + 更新配置 | +105 |
| `hermes_cli/model_manager.py` | 已存在（之前创建） | ~618 |

## 验证

```
python test_import.py
model_manager OK: 4 models registered
  - whisper-small: Whisper-small (STT)
  - moss-tts-nano: MOSS-TTS-Nano (TTS)
  - qwen-coder-1.5b: Qwen2.5-Coder-1.5B (LLM)
  - qwen-0.5b: Qwen2.5-0.5B (LLM)
```

## 下一步

完成 hermes-agent-cn 改造后，按 P1→P2→P3 路径借鉴 browser-harness：
- P1: MCP Server 封装验证
- P2: 高频函数内置为 Hermes Tool
- P3: 设计理念（截图驱动、自写 helpers、域技能沉淀）融入 Hermes Tool 框架

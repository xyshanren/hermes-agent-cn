# 多模型路由方案 — 设计文档

> 状态：Phase 1 已实现 | 日期：2026-05-13
> 场景：Ollama/LM Studio 部署多个模型时，按任务类型智能路由

## 实现进度

| Phase | 状态 | 说明 |
|-------|------|------|
| 1 | ✅ 已实现 | Ollama 多模型自动检测 + auxiliary.vision 自动配置 |
| 2 | ⏳ 待实现 | `model_routing` 配置 + 主对话模型选择（`run_agent.py`） |
| 3 | ⏳ 待实现 | 运行时动态模型切换 + 上下文管理 |

### Phase 1 实现详情（commit TBD）

**改动文件**：
- `hermes_cli/quickstart.py` — 新增模型分类、智能选择、auxiliary.vision 自动配置
- `hermes_cli/main.py` — `_auto_configure_local_fallback()` 支持 auxiliary.vision

**新增函数**：
- `_classify_ollama_model(name)` — 启发式分类：vision / reasoning / text
- `_pick_ollama_primary(models)` — 智能选择主力模型（优先文本，排除视觉）
- `_find_ollama_vision_model(models)` — 查找视觉模型

**关键行为**：
- `_detect_ollama()` 返回值增加 `classified_models`、`vision_model` 字段
- `_write_smart_routing()` 自动写入 `auxiliary.vision`（仅在当前为 auto/ollama 时）
- `_build_fallback_chain()` Ollama 是主力时，将非 vision 副模型加入 fallback
- `cmd_quickstart()` 多模型时按类型分组显示（文本/视觉/推理）
- `_auto_configure_local_fallback()` setup 后也自动配 auxiliary.vision

---

## 背景

用户的典型部署模式：

```
Ollama 部署:
  ├── qwen3-vl:8b      (视觉多模态模型 — 处理图片/截图)
  └── qwen3:32b        (文本推理模型 — 主力对话/代码)

LM Studio 部署:
  ├── Qwen3-VL-8B      (视觉多模态)
  └── DeepSeek-R1-8B   (文本推理)
```

当前架构的限制：
- **一个 provider 只能配一个模型**（`model.default` 或 fallback 链中的一个条目）
- **fallback_model 是纯链式故障切换**，只在主力失败时按顺序尝试下一个
- **无任务类型路由**：不能"图片任务自动走视觉模型，文本任务走推理模型"

已有的部分方案：
- `auxiliary.vision` 可以独立配置视觉分析用的模型（`vision_analyze` 工具）
- 但 `auxiliary.vision` 只覆盖**辅助视觉分析**，不影响主对话模型选择

---

## 方案概览

### 设计原则

1. **最小侵入**：复用现有 `auxiliary` 配置结构，不引入新的顶级配置键
2. **向后兼容**：不配任务类型路由时，行为与现在完全一致
3. **渐进增强**：先解决 Ollama 多模型，再扩展到通用条件路由

### 方案 A：扩展 auxiliary 机制（推荐）

**核心思路**：将现有的 `auxiliary` 从"辅助任务独立路由"扩展为"任务类型路由层"，新增 `primary` 任务类型支持多 provider 模型选择。

#### 配置格式

```yaml
# 现有 auxiliary 配置（不变）
auxiliary:
  vision:
    provider: "ollama"
    model: "qwen3-vl:8b"
    base_url: "http://localhost:11434"
  web_extract:
    provider: "ollama"
    model: "qwen3:7b"
    base_url: "http://localhost:11434"
  session_search:
    provider: "ollama"
    model: "qwen3:7b"
    base_url: "http://localhost:11434"

# 新增：主模型按任务类型路由
model_routing:
  # 默认/主力模型（文本对话、代码等）
  default:
    provider: "ollama"
    model: "qwen3:32b"
    base_url: "http://localhost:11434"

  # 视觉任务（用户上传图片、截图、需要理解图片内容时）
  vision:
    provider: "ollama"
    model: "qwen3-vl:8b"
    base_url: "http://localhost:11434"

  # 推理增强（复杂推理、数学、逻辑任务）
  reasoning:
    provider: "ollama"
    model: "qwen3:32b"
    base_url: "http://localhost:11434"

  # 编码任务（可选，使用专门的 coding 模型）
  # coding:
  #   provider: "deepseek"
  #   model: "deepseek-v4-flash"
```

#### 运行时行为

```
用户消息进入
    │
    ├── 检测是否包含图片附件？
    │   ├── YES → 使用 model_routing.vision 模型
    │   └── NO  → 继续
    │
    ├── 检测是否是复杂推理任务？（关键词/提示词启发式）
    │   ├── YES → 使用 model_routing.reasoning 模型
    │   └── NO  → 继续
    │
    └── 使用 model_routing.default 模型
```

#### 任务类型检测策略

| 任务类型 | 检测信号 | 置信度 |
|----------|---------|--------|
| vision | 用户消息包含图片附件（最可靠） | 高 |
| vision | 消息包含 "看这张图"、"截图"、"图片里有什么" | 中 |
| reasoning | 消息以 "思考"、"分析"、"推理"、"证明" 开头 | 中 |
| reasoning | 消息包含数学公式、代码调试、逻辑推理请求 | 低 |
| default | 以上都不匹配 | — |

> **注意**：任务类型检测应采用"乐观切换"策略——宁可多用通用模型，也不要误判。因为误判的代价远高于"该用视觉模型但用了通用模型"的代价（通用模型仍可处理大部分请求）。

#### fallback 链保持不变

```
model_routing.default 失败
  → fallback_model[0]
  → fallback_model[1]
  → ...

model_routing.vision 失败
  → model_routing.default（兜底到通用模型）
  → fallback_model[0]
  → ...
```

---

### 方案 B：智能 Ollama 模型标签（轻量替代）

**核心思路**：不改运行时路由逻辑，只在配置和 quickstart 层面自动识别 Ollama 模型能力。

#### Ollama 模型检测增强

```python
def _detect_ollama_models() -> list[dict]:
    """检测 Ollama 模型，自动分类。"""
    models = _detect_ollama()
    if not models:
        return []

    classified = []
    for name in models["models"]:
        info = _classify_ollama_model(name)
        classified.append({"name": name, "type": info["type"], "priority": info["priority"]})

    return classified

def _classify_ollama_model(name: str) -> dict:
    """根据模型名称启发式分类。"""
    name_lower = name.lower()
    # 视觉模型识别
    vision_keywords = ["vl", "vision", "llava", "cogvlm", "qwen-vl", "minicpm-v"]
    if any(kw in name_lower for kw in vision_keywords):
        return {"type": "vision", "priority": 1}
    # 推理模型识别
    reasoning_keywords = ["r1", "reasoning", "think", "qwq", "deepseek-r1"]
    if any(kw in name_lower for kw in reasoning_keywords):
        return {"type": "reasoning", "priority": 1}
    return {"type": "text", "priority": 0}
```

#### 自动配置逻辑

当 Ollama 检测到多个模型时：

```python
def _auto_configure_ollama_routing(models: list[dict]):
    """根据检测到的模型自动配置路由。"""
    text_models = [m for m in models if m["type"] == "text"]
    vision_models = [m for m in models if m["type"] == "vision"]

    config = {}

    # 主力：最大的文本模型（启发式：参数量最大 / 列表最后）
    if text_models:
        config["model"] = {"default": text_models[-1]["name"], "provider": "ollama"}
    else:
        config["model"] = {"default": models[0]["name"], "provider": "ollama"}

    # 辅助视觉：如果有视觉模型，配置到 auxiliary.vision
    if vision_models:
        config["auxiliary"] = {
            "vision": {
                "provider": "ollama",
                "model": vision_models[0]["name"],
                "base_url": "http://localhost:11434"
            }
        }

    # Fallback：第二个模型作为 fallback
    remaining = [m["name"] for m in models if m["name"] != config["model"]["default"]]
    if remaining:
        config["fallback_model"] = [
            {"provider": "ollama", "model": remaining[0], "base_url": "http://localhost:11434"}
        ]

    return config
```

#### 配置示例（自动生成）

```yaml
# quickstart 自动检测 Ollama 有 qwen3:32b + qwen3-vl:8b 后生成：
model:
  provider: ollama
  default: qwen3:32b

auxiliary:
  vision:
    provider: ollama
    model: qwen3-vl:8b
    base_url: http://localhost:11434

fallback_model:
  - provider: deepseek
    model: deepseek-v4-flash
```

**优点**：改动最小，复用现有 auxiliary 机制
**缺点**：vision 路由只覆盖 `vision_analyze` 工具，不覆盖主对话中的图片理解

---

### 方案 C：运行时模型切换（最强能力，最大改动）

**核心思路**：在 agent loop 中根据消息内容动态切换模型，支持同 provider 内的多模型切换。

#### 核心改动点

1. **`run_agent.py` 的 `run_conversation()`**：在构建 API 请求前，检测消息类型并选择合适的模型
2. **模型切换缓存**：同一 Ollama 实例上的模型切换不需要重建客户端，只需要改 `model` 参数
3. **上下文兼容性**：切换模型时需要考虑上下文窗口大小差异

```python
# run_agent.py 中新增
def _resolve_model_for_message(self, messages: list) -> tuple[str, str]:
    """根据消息内容决定使用哪个模型。

    Returns:
        (model_name, reason) — 选中的模型名和选择原因
    """
    route_config = self.config.get("model_routing", {})
    if not route_config:
        return self.model, "default"

    # 检测最后一条用户消息
    last_user_msg = ""
    for msg in reversed(messages):
        if msg.get("role") == "user":
            last_user_msg = msg.get("content", "")
            break

    # 图片检测
    has_images = self._message_has_images(messages)
    if has_images and "vision" in route_config:
        vision_cfg = route_config["vision"]
        if vision_cfg.get("model"):
            return vision_cfg["model"], "vision-task"

    return self.model, "default"
```

**优点**：能力最强，真正的按任务路由
**缺点**：改动大，需要修改 agent 核心循环；模型切换的上下文窗口处理复杂

---

## 推荐路径

```
Phase 1（方案 B）: quickstart 多模型自动检测 + auxiliary 配置
  ↓ 改动最小，即插即用，解决 80% 场景
Phase 2（方案 A）: model_routing 配置 + 消息级模型选择
  ↓ 覆盖主对话中的图片理解等场景
Phase 3（方案 C）: 运行时动态切换（如需）
  ↓ 完整的条件路由能力
```

---

## 待讨论问题

1. **模型名称约定**：Ollama 的模型名（如 `qwen3-vl:8b`）包含标签（`:8b`），LM Studio 使用本地文件路径。如何统一？
2. **任务类型粒度**：除了 vision / reasoning / coding，还需要哪些任务类型？
3. **用户干预**：用户是否可以在对话中手动指定"用 xxx 模型"？（如 `/model qwen3-vl:8b`）
4. **与 credential_pool 的关系**：同一 provider 内多模型切换和 credential_pool（多 key 轮换）如何协调？
5. **辅助模型与主模型的边界**：`auxiliary.vision` 是辅助工具（vision_analyze），`model_routing.vision` 是主对话模型——两者是否需要区分？用户能否同时配两个不同的视觉模型？

---

## 实现优先级

| Phase | 内容 | 预估改动文件 | 复杂度 |
|-------|------|-------------|--------|
| 1 | quickstart 多模型检测 + auxiliary 自动配置 | `quickstart.py`, `main.py` | 低 |
| 2 | model_routing 配置 + 运行时选择 | `cli.py`, `run_agent.py`, `quickstart.py` | 中 |
| 3 | 动态模型切换 + 上下文管理 | `run_agent.py`, `model_tools.py` | 高 |

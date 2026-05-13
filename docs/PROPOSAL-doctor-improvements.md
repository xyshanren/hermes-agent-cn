# Doctor 输出优化 — 待评估改进方案

> 状态：已评估（2026-05-13）| 来源：v0.12.0-cn.3 手工测试阶段发现（问题 D）
> 日期：2026-05-13

## 背景

`hermes doctor` 当前覆盖 10 大类检查（Python 环境、必需包、配置文件、目录结构、命令安装、外部工具、API 连通性、子模块、工具可用性、本地模型），但输出信息和诊断覆盖面仍有优化空间。

---

## D1: .env 文件内容智能检测

### 现状

- 检查 `.env` 是否存在、是否包含 API key（通过 `_PROVIDER_ENV_HINTS` 列表粗略匹配）
- 不检测 `.env` 内容有效性（空值、格式错误、注释行中的 key）

### 改进建议

| 检查项 | 描述 | 优先级 |
|--------|------|--------|
| 空值检测 | `KEY=` 形式的空值，提示用户填入有效值 | P1 |
| 格式校验 | 检测 `KEY = VALUE`（有空格）、`export KEY=VALUE`（有 export 前缀）等常见格式问题 | P2 |
| 注释干扰 | `# DEEPSEEK_API_KEY=xxx` 被注释掉的 key，提示可能遗漏 | P2 |
| 重复 key | `.env` 中多次定义同一 key（dotenv 行为是后写覆盖），提示可能配置混乱 | P2 |
| 过期 key 提示 | 检测到已弃用的环境变量名（如 `OPENAI_ORG_ID`），提示迁移 | P3 |

### 伪代码

```python
def _check_env_content(env_path: Path) -> list[str]:
    issues = []
    content = env_path.read_text()
    lines = [l.strip() for l in content.splitlines() if l.strip() and not l.strip().startswith("#")]

    # 空值检测
    for line in lines:
        if "=" in line and line.split("=", 1)[1].strip() == "":
            key = line.split("=", 1)[0].strip()
            if key in _PROVIDER_ENV_HINTS:
                issues.append(f"Empty value: {key}=")

    # 格式校验
    for i, line in enumerate(content.splitlines(), 1):
        stripped = line.strip()
        if stripped.startswith("export "):
            issues.append(f"Line {i}: 'export' prefix unnecessary in .env")

    return issues
```

---

## D2: Conda/系统 Python 环境检测

### 现状

- 检测是否在虚拟环境中（`sys.prefix != sys.base_prefix`）
- 不区分 venv、conda、pyenv 等不同虚拟环境类型

### 改进建议

| 检查项 | 描述 | 优先级 |
|--------|------|--------|
| Conda 检测 | 检测 `CONDA_DEFAULT_ENV` / `CONDA_PREFIX`，标注 "Conda 环境: xxx" | P1 |
| Pyenv 检测 | 检测 `PYENV_SHELL` / `PYENV_VERSION`，标注 "Pyenv 管理" | P2 |
| 系统 Python 警告 | 未在虚拟环境 + 在系统 Python 路径下运行，建议创建 venv | P1 |
| 路径显示 | 显示当前 Python 解释器完整路径，帮助排查路径混乱问题 | P2 |

### 伪代码

```python
def _check_python_env() -> dict:
    info = {"in_venv": sys.prefix != sys.base_prefix}

    # Conda
    conda_env = os.getenv("CONDA_DEFAULT_ENV", "")
    conda_prefix = os.getenv("CONDA_PREFIX", "")
    if conda_env:
        info["type"] = "conda"
        info["env_name"] = conda_env
    elif os.getenv("PYENV_SHELL"):
        info["type"] = "pyenv"
        info["version"] = os.getenv("PYENV_VERSION", "global")
    elif info["in_venv"]:
        info["type"] = "venv"
    else:
        info["type"] = "system"

    info["executable"] = sys.executable
    return info
```

---

## D3: 本地模型与 Fallback 链一致性检查

### 现状

- "本地模型"检查段只检测嵌入式模型安装状态（MODEL_REGISTRY）
- **不检查** Ollama/LM Studio 运行状态
- **不检查** fallback_model / fallback_providers 配置的有效性
- **不检查** 主力模型与 fallback 链的重复/冲突

### 改进建议

| 检查项 | 描述 | 优先级 |
|--------|------|--------|
| Fallback 链连通性 | 逐一检测 fallback_model 链中各条目的 provider + model 可达性 | P1 |
| Ollama 状态 | 检测 Ollama 服务是否运行，列出已部署的模型 | P1 |
| LM Studio 状态 | 检测 LM Studio 服务是否运行（http://127.0.0.1:1234） | P2 |
| 主力-Fallback 重复 | 检测 `model.default` 是否出现在 fallback_model 链中 | P1 |
| Fallback 格式统一 | 检测同时存在 `fallback_model` 和 `fallback_providers` 两个键的不一致状态 | P2 |
| 链长度提示 | 如果只有主力没有 fallback，提示 "未配置回退模型，主力失败时将无法继续" | P2 |

### 伪代码

```python
def _check_fallback_chain(cfg: dict) -> list[str]:
    issues = []
    primary_model = (cfg.get("model") or {}).get("default", "")

    # 键一致性
    has_fb_model = "fallback_model" in cfg
    has_fb_providers = "fallback_providers" in cfg
    if has_fb_model and has_fb_providers:
        issues.append("同时存在 fallback_model 和 fallback_providers，建议统一为 fallback_providers")

    # 解析链
    chain = cfg.get("fallback_providers") or cfg.get("fallback_model") or []
    if isinstance(chain, dict):
        chain = [chain]

    if not chain:
        issues.append("未配置 fallback 链，主力模型失败时将无法继续")
        return issues

    # 主力重复检测
    for entry in chain:
        if entry.get("model") == primary_model:
            issues.append(f"Fallback 链包含主力模型 {primary_model}，故障切换时将跳过")

    # 连通性检测
    for entry in chain:
        provider = entry.get("provider", "")
        model = entry.get("model", "")
        if provider == "embedded":
            continue  # 嵌入式不需要连通性检测
        # TODO: 逐一 ping 检测

    return issues
```

---

## D4: 输出格式优化

### 现状

- 10 大类检查以纯文本顺序输出，信息量大时难以快速定位问题
- Summary 段落只有简单计数

### 改进建议

| 改进项 | 描述 | 优先级 |
|--------|------|--------|
| 分组摘要 | 每个 Check 类别末尾显示本类别通过/警告/失败计数 | P2 |
| 颜色分级 | 已有，但可增加 🔴严重 / 🟡警告 / 🔵提示 三级 | P3 |
| JSON 输出 | 支持 `hermes doctor --json` 输出机器可读格式 | P3 |
| 只显示问题 | 支持 `hermes doctor --quiet` 只显示有问题的项目 | P2 |

---

## D5: 路由状态可视化（与多模型路由联动）

### 现状

- 不显示当前路由配置（主力模型 + fallback 链）

### 改进建议（依赖多模型路由方案）

| 检查项 | 描述 | 优先级 |
|--------|------|--------|
| 路由拓扑显示 | 可视化展示：主力 → fallback[0] → fallback[1] → ... | P1 |
| 任务类型路由 | 如果配置了 auxiliary 或条件路由，显示各任务类型的模型分配 | P2 |
| 实时状态 | 标注每个节点的可达性（✓ / ✗ / ⚠） | P1 |

---

## 评估标准

| 维度 | 权重 |
|------|------|
| 用户价值（减少排障时间） | 40% |
| 实现复杂度（低优先） | 20% |
| 与现有架构兼容性 | 20% |
| 误报/噪音控制 | 20% |

---

## 评估结论（2026-05-13）

基于 `hermes_cli/doctor.py`（1101 行，12 大类检查）的代码审查结果：

### 实际检查 vs 提案对照

| 方向 | 当前实现 | 差距 | 评估 |
|------|---------|------|------|
| **D1 .env 内容检测** | `_has_provider_env_config()` 仅做子串匹配 | 中等 | 影响已降低（v0.12.0-cn.3 已修 API Key 读取问题） |
| **D2 Conda/系统 Python** | `sys.prefix != sys.base_prefix` 基本检测 | 较大 | 用户已反馈此问题 |
| **D3 Fallback 链一致性** | **未实现** | 全部缺失 | 直接影响路由可用性 |
| **D4 输出格式优化** | 纯文本输出 | 中 | 锦上添花 |
| **D5 路由状态可视化** | 依赖多模型路由 Phase 2+ | 全部缺失 | 暂不实施 |

### 实施建议（重新排序）

考虑到 D5 依赖尚未实施的 Phase 2，**建议优先实施 D3 + D2，D1 降级**。

| 优先级 | 方向 | 预估工时 | 原因 |
|--------|------|---------|------|
| **P0** | **D3** — Fallback 链 + Ollama 状态 | 2h | 直接影响路由可用性；本次手工测试已发现问题 |
| **P1** | **D2** — Conda/Pyenv 环境检测 | 1h | 用户已反馈；文档 FAQ 已记录 |
| **P2** | **D1** — .env 内容智能检测 | 1.5h | 收益降低（Core Bug 已修） |
| **P3** | **D4** — 输出格式优化 | 2h | 纯体验提升 |
| ⏸️ | **D5** — 路由状态可视化 | 待定 | 依赖多模型路由 Phase 2 |

### D3 子项目拆分

| 子项 | 工时 | 说明 |
|------|------|------|
| D3.1 Ollama 运行状态检测 | 0.5h | `curl http://localhost:11434/api/tags` |
| D3.2 Fallback 链读取 & 一致性检查 | 1h | 从 config 读 fallback 链，检测空值/重复/连通性 |
| D3.3 主力-Fallback 重复检测 | 0.5h | 主力模型同时出现在 fallback 链中 |

### 快速启动

从 D3.1 开始：
```python
# 在 doctor.py 的 "本地模型" 检查段之后，新增 "外部模型服务" 段
def _check_ollama_status():
    """检测 Ollama 是否运行并列出已部署模型。"""
    import httpx
    try:
        r = httpx.get("http://localhost:11434/api/tags", timeout=3)
        if r.status_code == 200:
            models = r.json().get("models", [])
            check_ok(f"Ollama 服务运行中（{len(models)} 个模型）")
            for m in models:
                check_info(f"  {m['name']}")
        else:
            check_warn("Ollama 服务响应异常", f"HTTP {r.status_code}")
    except httpx.ConnectError:
        check_warn("Ollama 未运行", "(如需本地推理: ollama serve &)")
    except Exception as e:
        check_warn("Ollama 检测失败", str(e))
```

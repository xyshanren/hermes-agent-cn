"""
Hermes-Agent-CN 快捷启动 — 智能路由配置。

快速检测所有可用资源（API Key + Ollama + 本地离线模型），
自动配置三层智能路由：
  1. Ollama（本地主力推理）
  2. 云端 API（降级 / 复杂任务）
  3. 嵌入式本地模型（断网兜底）

如果三样都没有，引导安装本地离线模型。
"""

from __future__ import annotations

import json
import logging
import os
import sys
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# ── 国产 Provider 检测表 ──
# 按优先级排列：优先检测国产云 API
_PROVIDER_CHECKS = [
    {
        "id": "deepseek",
        "name": "DeepSeek",
        "env_var": "DEEPSEEK_API_KEY",
        "default_model": "deepseek-v4-flash",
        "base_url": "https://api.deepseek.com",
    },
    {
        "id": "siliconflow",
        "name": "硅基流动 SiliconFlow",
        "env_var": "SILICONFLOW_API_KEY",
        "default_model": "Qwen/Qwen2.5-7B-Instruct",
        "base_url": "https://api.siliconflow.cn/v1",
    },
    {
        "id": "zai",
        "name": "智谱 GLM",
        "env_var": "ZHIPUAI_API_KEY",
        "default_model": "glm-4-plus",
        "base_url": "https://open.bigmodel.cn/api/paas/v4",
    },
    {
        "id": "kimi-coding",
        "name": "月之暗面 Kimi",
        "env_var": "MOONSHOT_API_KEY",
        "default_model": "moonshot-v1-8k",
        "base_url": "https://api.moonshot.cn/v1",
    },
    {
        "id": "minimax",
        "name": "MiniMax",
        "env_var": "MINIMAX_API_KEY",
        "default_model": "minimax-text-01",
        "base_url": "https://api.minimax.chat/v1",
    },
    {
        "id": "alibaba",
        "name": "阿里云通义千问",
        "env_var": "DASHSCOPE_API_KEY",
        "default_model": "qwen-turbo-latest",
        "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
    },
    {
        "id": "xiaomi",
        "name": "小米",
        "env_var": "XIAOMI_API_KEY",
        "default_model": "mi-medium",
        "base_url": "https://api.minimax.chat/v1",
    },
]

_CN_PROVIDER_IDS = {p["id"] for p in _PROVIDER_CHECKS}

# ── Ollama 模型分类关键词 ──
_VISION_KEYWORDS = ("vl", "vision", "llava", "cogvlm", "minicpm-v", "ocr")
_REASONING_KEYWORDS = ("r1", "reasoning", "think", "qwq")

# L2 层：无需 API 调用的已知视觉家族检测
# 部分模型（如 qwen3.5）是原生多模态，名称不含 "vl" 但支持视觉
_VISION_FAMILIES = (
    "qwen3",
    "qwen3.5",
    "yi-vl", "internvl2", "internvl",
    "pixtral", "bakllava",
    "moondream", "llama-v", "llava-llama",
    "glm",
)
# 匹配家族但实际是编码专用模型的排除关键词
# 注: 模型名会被 replace('-', ' ') 归一化，所以排除词也需考虑空格形式
_VISION_FAMILY_EXCLUSIONS = (
    "coder", "code ", "instruct-code", "deepseek", "yi-lightning", "ocr",
)

_OLLAMA_MODEL_INFO_CACHE = {}


def _get_ollama_model_info(name: str) -> Optional[dict]:
    """Query Ollama /api/show for model details, with in-memory cache.

    Returns the full /api/show response dict, or None on failure.
    Results are cached so repeated calls for the same model are free.
    """
    if name in _OLLAMA_MODEL_INFO_CACHE:
        return _OLLAMA_MODEL_INFO_CACHE[name]
    try:
        import urllib.request

        req = urllib.request.Request(
            "http://localhost:11434/api/show",
            data=json.dumps({"name": name}).encode(),
            method="POST",
            headers={"Content-Type": "application/json"},
        )
        resp = urllib.request.urlopen(req, timeout=5)
        if resp.status == 200:
            info = json.loads(resp.read().decode())
            _OLLAMA_MODEL_INFO_CACHE[name] = info
            return info
    except Exception:
        pass
    _OLLAMA_MODEL_INFO_CACHE[name] = None
    return None


def _get_param_size(name: str) -> float:
    """Get parameter size as float (e.g. "7B" -> 7.0, "32B" -> 32.0).

    Falls back to parsing the model tag suffix (e.g. "qwen3:8b" -> 8.0)
    if /api/show is unavailable.
    """
    import re

    info = _get_ollama_model_info(name)
    if info:
        details = info.get("details", {})
        size_str = details.get("parameter_size", "")
        if size_str:
            match = re.match(r"([\d.]+)\s*[Bb]", str(size_str).strip())
            if match:
                return float(match.group(1))

    # Fallback: parse from tag suffix (e.g. "qwen3:8b" → 8)
    match = re.search(r":(\d+\.?\d*)\s*[bB]?$", name)
    if match:
        return float(match.group(1))
    return 0.0


def _check_vision_template(name: str) -> bool:
    """Check if model template contains vision-related markers via /api/show.

    Vision model chat templates contain image handling logic.  This is the
    ground-truth check (L3 layer) when name heuristics fail.
    """
    info = _get_ollama_model_info(name)
    if not info:
        return False
    template = info.get("template", "")
    if not template:
        return False
    # Vision models' chat templates handle image_data, image_url, or .Images
    template_lower = template.lower()
    vision_markers = ("image_url", "image_data", "images", "vision")
    return any(m in template_lower for m in vision_markers)


def _classify_ollama_model(name: str) -> str:
    """Three-layer classification of Ollama models.

    L1: Name keyword matching (fast, no API)
        - Vision: vl, vision, llava, cogvlm, minicpm-v
        - Reasoning: r1, reasoning, think, qwq
    L2: Known family matching (fast, no API)
        - Vision families: qwen3, qwen3.5, yi-vl, internvl2, etc.
        - Excludes coding-specialized models (e.g. qwen3-coder)
    L3: /api/show template inspection (API call, cached)
        - Checks if chat template handles image content

    Returns:
        "vision" | "reasoning" | "coding" | "embedding" | "text"
    """
    name_lower = name.lower().split(":")[0]  # 去掉标签（如 :8b）

    # L0: embedding 模型（不能用于 chat）
    if "embed" in name_lower:
        return "embedding"

    # L1: 关键词匹配
    if any(kw in name_lower for kw in _VISION_KEYWORDS):
        return "vision"
    if any(kw in name_lower for kw in _REASONING_KEYWORDS):
        return "reasoning"
    # L1.5: 编码模型检测（名称含 coder/code-/instruct-code）
    if any(kw in name_lower for kw in ("coder", "code-", "instruct-code")):
        return "coding"

    # L2: 已知视觉家族检测（排除编码专用模型）
    for family in _VISION_FAMILIES:
        if family in name_lower:
            if not any(excl in name_lower for excl in _VISION_FAMILY_EXCLUSIONS):
                return "vision"
            # 被排除（编码专用模型），继续检查其他家族

    # L3: 模板探查（仅对 L1+L2 未分类的模型）
    if _check_vision_template(name):
        return "vision"

    return "text"


def _pick_ollama_primary(models: list[str]) -> str:
    """从 Ollama 多模型中选择主力模型。

    优先级：text/reasoning > vision（视觉模型不适合做通用主力）。
    同类型中按参数规模选最大（回退到原有最后匹配）。
    """
    if not models:
        return "llama3.2"

    classified = [(name, _classify_ollama_model(name)) for name in models]
    # 优先 text/reasoning，排除 vision、coding 和 embedding（不能作为通用主力）
    non_vision_non_coding = [
        (name, t) for name, t in classified if t not in ("vision", "coding", "embedding")
    ]

    if non_vision_non_coding:
        # 同类型中选参数规模最大的
        return max(non_vision_non_coding, key=lambda x: _get_param_size(x[0]))[0]

    # 退而求其次：有 coding 但无 text/reasoning 时，选 coding 中最大的
    coding_models = [(name, t) for name, t in classified if t == "coding"]
    if coding_models:
        return max(coding_models, key=lambda x: _get_param_size(x[0]))[0]

    # 全是视觉模型时选参数规模最大的
    return max(models, key=_get_param_size)


def _find_ollama_vision_model(models: list[str]) -> Optional[str]:
    """找到 Ollama 中的视觉模型。有多个时选参数规模最大的。"""
    visions = [
        (name, _get_param_size(name)) for name in models
        if _classify_ollama_model(name) == "vision"
    ]

    if not visions:
        return None

    # 按参数规模降序取最大
    visions.sort(key=lambda x: x[1], reverse=True)
    return visions[0][0]


# ── 资源检测函数 ──

def _detect_api_key_providers() -> list[dict]:
    """扫描环境变量，返回已配置的国产 Provider 列表。"""
    found = []
    for p in _PROVIDER_CHECKS:
        key = os.environ.get(p["env_var"], "")
        if key and len(key) > 4:
            found.append(p)
    return found


def _detect_ollama() -> Optional[dict]:
    """检测本地 Ollama 服务是否运行，返回可用模型列表（含分类）。"""
    try:
        import urllib.request

        req = urllib.request.Request(
            "http://localhost:11434/api/tags",
            method="GET",
            headers={"Accept": "application/json"},
        )
        resp = urllib.request.urlopen(req, timeout=3)
        if resp.status == 200:
            data = json.loads(resp.read().decode())
            models = data.get("models", [])
            if models:
                model_names = [m.get("name", "") for m in models if m.get("name")]
                classified = [
                    {"name": n, "type": _classify_ollama_model(n)}
                    for n in model_names
                ]
                return {
                    "available": True,
                    "models": model_names,
                    "classified_models": classified,
                    "default_model": _pick_ollama_primary(model_names),
                    "vision_model": _find_ollama_vision_model(model_names),
                }
            return {"available": True, "models": [], "default_model": "llama3.2"}
    except Exception:
        pass
    return None


def _has_embedded_models() -> bool:
    """检查是否已安装本地离线模型。"""
    try:
        from hermes_cli.model_manager import is_installed

        return is_installed("qwen-0.5b") or is_installed("qwen-coder-1.5b")
    except Exception:
        return False


# ── 本地 OpenAI 兼容服务器检测（LM Studio / llama.cpp / FastLLM / vLLM / LocalAI 等）──
#
# 新后端接入模板:
#   1. 在 _LOCAL_SERVER_CONFIGS 中添加一个条目（字段见下方注释）
#   2. quickstart 会自动探测其 /v1/models 端点
#   3. 探测到后, _write_local_backends() 写入 config.yaml 的 local_backends 段
#   4. SmartRouter v2 自动识别并在路由时使用
#
# 自定义后端（不修改代码）:
#   在 config.yaml 中直接添加:
#     local_backends:
#       - name: my-server
#         base_url: http://localhost:9999/v1
#         priority: 5
#         kind: openai-compatible
#   无需重启, SmartRouter 下次探测自动识别。
#
# local_backends 条目完整字段:
#   name:     后端标识 (string, 必填) — 如 "vllm"、"my-server"
#   base_url: API 端点 (string, 必填) — 以 /v1 结尾的 OpenAI 兼容 URL
#   priority: 路由优先级 (int, 可选, 默认 99) — 数字越小越优先
#   kind:     后端类型 (string, 可选) — "ollama"|"openai-compatible"|"lm-studio"|"llama-cpp"|"fastllm"

_LOCAL_SERVER_CONFIGS = [
    {
        "id": "lm_studio",
        "name": "LM Studio",
        "base_url": "http://localhost:1234/v1",
        "display_name": "LM Studio（本地）",
        "default_model": "qwen2.5-7b-instruct",
    },
    {
        "id": "llama_cpp",
        "name": "llama.cpp",
        "base_url": "http://localhost:8080/v1",
        "display_name": "llama.cpp（本地）",
        "default_model": "llama-3.2-3b-instruct",
    },
    {
        "id": "fastllm",
        "name": "FastLLM",
        "base_url": "http://localhost:8088/v1",
        "display_name": "FastLLM（本地）",
        "default_model": "qwen2.5-7b-instruct",
    },
    {
        "id": "vllm",
        "name": "vLLM",
        "base_url": "http://localhost:8000/v1",
        "display_name": "vLLM（本地）",
        "default_model": "qwen2.5-7b-instruct",
    },
    {
        "id": "localai",
        "name": "LocalAI",
        "base_url": "http://localhost:8082/v1",
        "display_name": "LocalAI（本地）",
        "default_model": "qwen2.5-7b-instruct",
    },
]


def _classify_local_model(name: str) -> str:
    """Two-layer classification for non-Ollama local models.

    L1: Name keyword matching (fast, no API)
        - Vision: vl, vision, llava, cogvlm, minicpm-v
        - Reasoning: r1, reasoning, think, qwq
    L2: Known family matching (fast, no API)
        - Vision families: qwen3, qwen3.5, yi-vl, internvl2, etc.
        - Excludes coding-specialized models (e.g. qwen3-coder)

    Unlike _classify_ollama_model, does NOT call /api/show (not available
    on LM Studio/llama.cpp).  Falls back to "text" after L2.

    Returns:
        "vision" | "reasoning" | "coding" | "text"
    """
    name_lower = name.lower()
    # llama.cpp uses "model:" prefix (e.g. "model:qwen2.5-vl:7b") — strip it first
    if name_lower.startswith("model:"):
        name_lower = name_lower[6:]
    name_lower = name_lower.split(":")[0]  # Ollama-style tag
    name_lower = name_lower.replace("-", " ")  # Normalize hyphens

    # Remove size suffixes like "8b", "70b" etc.
    import re

    name_lower = re.sub(r"\s+\d+\s*b", "", name_lower).strip()

    # L1: 关键词匹配
    if any(kw in name_lower for kw in _VISION_KEYWORDS):
        return "vision"
    if any(kw in name_lower for kw in _REASONING_KEYWORDS):
        return "reasoning"
    # L1.5: 编码模型检测
    # 注意: name_lower 已做过 replace('-', ' ')，所以 'coder' 匹配 qwen3 coder，
    # 但 'code-' 不再匹配。用单词边界检查替代。
    if "coder" in name_lower or "code " in name_lower:
        return "coding"
    if re.search(r"\bcode\b", name_lower):
        return "coding"

    # L2: 已知视觉家族检测（排除编码专用模型）
    for family in _VISION_FAMILIES:
        # Also check with hyphens replaced by spaces
        family_normalized = family.replace("-", " ")
        if family_normalized in name_lower or family in name_lower:
            if not any(excl in name_lower for excl in _VISION_FAMILY_EXCLUSIONS):
                return "vision"

    return "text"


def _get_local_model_param_size(name: str) -> float:
    """Extract parameter size from local model name.

    Handles formats like:
      - "qwen2.5-7b-instruct" → 7.0
      - "llama-3.2-3b" → 3.0
      - "mistral-7b-instruct-v0.3" → 7.0
      - "qwen3:8b" → 8.0 (Ollama-like)
    """
    import re

    match = re.search(r"(\d+\.?\d*)\s*[bB](?:\s*-|\s+|$)", name)
    if match:
        return float(match.group(1))
    return 0.0


def _detect_local_server(server_config: dict) -> Optional[dict]:
    """检测本地 OpenAI 兼容服务是否运行。

    Calls GET {base_url}/models to list available models.
    Works with LM Studio (port 1234), llama.cpp server (port 8080),
    or any other OpenAI-compatible local server.
    """
    try:
        import urllib.request

        models_url = server_config["base_url"].rstrip("/") + "/models"
        req = urllib.request.Request(
            models_url,
            method="GET",
            headers={"Accept": "application/json"},
        )
        resp = urllib.request.urlopen(req, timeout=3)
        if resp.status == 200:
            data = json.loads(resp.read().decode())
            models = data.get("data", data.get("models", []))
            if models:
                # Filter out non-model entries like "global" (preset without model file)
                model_names = [
                    m.get("id", m.get("name", ""))
                    for m in models
                    if (m.get("id") or m.get("name"))
                    and m.get("id") != "global"
                ]
                if model_names:
                    classified = [
                        {"name": n, "type": _classify_local_model(n)}
                        for n in model_names
                    ]
                    return {
                        "available": True,
                        "provider_id": server_config["id"],
                        "name": server_config["name"],
                        "display_name": server_config["display_name"],
                        "base_url": server_config["base_url"],
                        "models": model_names,
                        "classified_models": classified,
                        "default_model": _pick_local_primary(model_names, _classify_local_model),
                        "vision_model": _find_local_vision_model(model_names, _classify_local_model),
                    }
            # Running but no models loaded
            return {
                "available": True,
                "provider_id": server_config["id"],
                "name": server_config["name"],
                "display_name": server_config["display_name"],
                "base_url": server_config["base_url"],
                "models": [],
                "default_model": server_config["default_model"],
            }
    except Exception:
        pass
    return None


def _pick_local_primary(
    models: list[str],
    classify_fn,
) -> str:
    """从本地模型列表中选择主力模型（通用版）。

    优先级：text/reasoning > coding > vision（视觉模型不适合做通用主力）。
    同类型中按参数规模选最大。
    """
    if not models:
        return ""

    classified = [(name, classify_fn(name)) for name in models]

    # 优先 text/reasoning，排除 vision 和 coding
    non_vision_non_coding = [
        (name, t) for name, t in classified if t not in ("vision", "coding")
    ]

    if non_vision_non_coding:
        return max(non_vision_non_coding, key=lambda x: _get_local_model_param_size(x[0]))[0]

    # coding 中选最大的
    coding_models = [(name, t) for name, t in classified if t == "coding"]
    if coding_models:
        return max(coding_models, key=lambda x: _get_local_model_param_size(x[0]))[0]

    # 全是视觉模型
    return max(models, key=_get_local_model_param_size)


def _find_local_vision_model(
    models: list[str],
    classify_fn,
) -> Optional[str]:
    """找到本地模型列表中的视觉模型，多选时取参数规模最大的。"""
    visions = [
        (name, _get_local_model_param_size(name))
        for name in models
        if classify_fn(name) == "vision"
    ]
    if not visions:
        return None
    visions.sort(key=lambda x: x[1], reverse=True)
    return visions[0][0]


# ── 配置写入函数 ──

def _configure_provider(provider: dict) -> bool:
    """将检测到的 Provider 写入 config.yaml 和 ~/.hermes/.env。"""
    try:
        from hermes_cli.auth import _update_config_for_provider

        _update_config_for_provider(
            provider["id"],
            provider["base_url"],
            default_model=provider["default_model"],
        )

        # Also set model.default explicitly
        from hermes_cli.config import load_config, save_config, save_env_value

        cfg = load_config()
        model = cfg.get("model", {})
        if isinstance(model, dict):
            model["default"] = provider["default_model"]
            cfg["model"] = model
            save_config(cfg)

        # Save API key to ~/.hermes/.env so Hermes runtime can find it
        key_val = os.environ.get(provider["env_var"], "")
        if key_val:
            save_env_value(provider["env_var"], key_val)

        return True
    except Exception as e:
        logger.warning("配置 Provider %s 失败: %s", provider["id"], e)
        return False


def _configure_ollama(ollama_info: dict) -> bool:
    """将 Ollama 配置写入 config.yaml。"""
    default_model = ollama_info.get("default_model", "llama3.2")
    try:
        from hermes_cli.auth import _update_config_for_provider

        _update_config_for_provider(
            "ollama",
            "http://localhost:11434/v1",
            default_model=default_model,
        )
        from hermes_cli.config import load_config, save_config

        cfg = load_config()
        model = cfg.get("model", {})
        if isinstance(model, dict):
            model["default"] = default_model
            cfg["model"] = model
            save_config(cfg)
        return True
    except Exception as e:
        logger.warning("配置 Ollama 失败: %s", e)
        return False


def _configure_embedded() -> bool:
    """将嵌入式推理配置写入 config.yaml。"""
    try:
        from hermes_cli.auth import _update_config_for_provider

        _update_config_for_provider(
            "embedded",
            "",
            default_model="qwen-0.5b",
        )
        from hermes_cli.config import load_config, save_config

        cfg = load_config()
        model = cfg.get("model", {})
        if isinstance(model, dict):
            model["default"] = "qwen-0.5b"
            model["provider"] = "embedded"
            cfg["model"] = model
            save_config(cfg)
        return True
    except Exception as e:
        logger.warning("配置嵌入式推理失败: %s", e)
        return False


def _configure_local_server(local_info: dict) -> bool:
    """将 LM Studio / llama.cpp 配置写入 config.yaml。

    使用 provider="custom" + base_url，兼容任何 OpenAI 兼容的本地服务。
    """
    default_model = local_info.get("default_model", "")
    base_url = local_info.get("base_url", "")
    provider_id = local_info.get("provider_id", "custom")
    try:
        from hermes_cli.auth import _update_config_for_provider

        _update_config_for_provider(
            "custom",
            base_url,
            default_model=default_model,
        )
        from hermes_cli.config import load_config, save_config

        cfg = load_config()
        model = cfg.get("model", {})
        if isinstance(model, dict):
            model["default"] = default_model
            model["provider"] = "custom"
            model["base_url"] = base_url
            cfg["model"] = model
            save_config(cfg)
        return True
    except Exception as e:
        logger.warning("配置 %s 失败: %s", provider_id, e)
        return False


# ── 智能路由配置 ──

def _build_fallback_chain(
    api_providers: list[dict],
    ollama_info: Optional[dict],
    has_embedded: bool,
    primary_provider_id: str,
    local_server_infos: Optional[list[dict]] = None,
) -> list[dict]:
    """构建 fallback_model 链。

    规则：
    - 已作为主力的 provider + 模型不放 fallback
    - 云端 API 作为第一 fallback
    - Ollama 非 vision 模型作为 fallback（如果 Ollama 有多个模型且是主力）
    - LM Studio / llama.cpp 作为本地 fallback
    - 嵌入式模型始终放最后（断网兜底）
    """
    chain: list[dict] = []
    local_server_infos = local_server_infos or []

    # 云端 API providers（排除主力）
    for p in api_providers:
        if p["id"] != primary_provider_id:
            chain.append({
                "provider": p["id"],
                "model": p["default_model"],
            })

    # Ollama（如果不是主力）
    if ollama_info and primary_provider_id != "ollama":
        chain.append({
            "provider": "ollama",
            "model": ollama_info["default_model"],
            "base_url": "http://localhost:11434/v1",
        })
    elif ollama_info and primary_provider_id == "ollama":
        # Ollama 是主力但有多个模型 — 将非 vision 非主力模型加入 fallback
        primary_model = ollama_info["default_model"]
        for m in ollama_info.get("models", []):
            m_type = _classify_ollama_model(m)
            if "embed" in m.lower():
                continue  # embedding 模型不能用于 chat
            if m != primary_model and m_type not in ("vision", "coding"):
                chain.append({
                    "provider": "ollama",
                    "model": m,
                    "base_url": "http://localhost:11434/v1",
                })
                break  # 只加一个 Ollama fallback

    # LM Studio / llama.cpp 本地服务 fallback
    for local_info in local_server_infos:
        local_id = local_info.get("provider_id", "")
        if local_id != primary_provider_id and local_info.get("models"):
            chain.append({
                "provider": "custom",
                "model": local_info["default_model"],
                "base_url": local_info.get("base_url", ""),
            })

    # 嵌入式模型 — 断网兜底（始终放最后）
    if has_embedded and primary_provider_id != "embedded":
        chain.append({
            "provider": "embedded",
            "model": "qwen-0.5b",
        })

    return chain


def _write_smart_routing(
    primary_provider_id: str,
    primary_model: str,
    fallback_chain: list[dict],
    api_providers: list[dict],
    ollama_info: Optional[dict] = None,
    local_server_infos: Optional[list[dict]] = None,
) -> bool:
    """将智能路由配置写入 config.yaml。

    包括：主力模型 + fallback_model 链 + auxiliary.vision + API Key 保存。
    """
    try:
        from hermes_cli.config import load_config, save_config, save_env_value

        cfg = load_config()
        local_server_infos = local_server_infos or []

        # 查找主力对应的本地服务信息（如果主力是 LM Studio / llama.cpp）
        primary_local_info = None
        for li in local_server_infos:
            if li.get("provider_id") == primary_provider_id:
                primary_local_info = li
                break

        # 写入主力模型
        model_cfg = cfg.get("model", {})
        if not isinstance(model_cfg, dict):
            model_cfg = {}
        model_cfg["default"] = primary_model
        model_cfg["provider"] = primary_provider_id
        # 恢复 Ollama 的 base_url — 云 Provider 配置（如 deepseek）
        # 会覆写 model.base_url，导致后续 provider=custom 时读取到错误 URL
        if primary_provider_id == "ollama":
            model_cfg["base_url"] = "http://localhost:11434/v1"
        elif primary_local_info:
            # LM Studio / llama.cpp 使用 custom provider + base_url
            model_cfg["provider"] = "custom"
            model_cfg["base_url"] = primary_local_info.get("base_url", "")
        cfg["model"] = model_cfg

        # 写入 fallback 链
        if fallback_chain:
            cfg["fallback_model"] = fallback_chain
            cfg.pop("fallback_providers", None)  # 统一格式，避免 doctor 警告
        else:
            cfg.pop("fallback_model", None)

        # 自动配置 auxiliary.vision
        # 先检查 Ollama，再检查本地服务（LM Studio / llama.cpp）
        vision_model = None
        vision_provider = None
        vision_base_url = None

        if ollama_info:
            vision_model = ollama_info.get("vision_model")
            if vision_model:
                vision_provider = "ollama"
                vision_base_url = "http://localhost:11434/v1"

        if not vision_model and local_server_infos:
            for li in local_server_infos:
                vm = li.get("vision_model")
                if vm:
                    vision_model = vm
                    vision_provider = "custom"
                    vision_base_url = li.get("base_url", "")
                    break

        if vision_model and vision_provider:
            aux = cfg.setdefault("auxiliary", {})
            if not isinstance(aux, dict):
                aux = {}
                cfg["auxiliary"] = aux
            vision_cfg = aux.get("vision", {})
            # 仅在当前未配置或为 auto 时自动设置
            current_provider = str(vision_cfg.get("provider", "auto")).strip()
            if current_provider in ("auto", "", "ollama", "custom"):
                aux["vision"] = {
                    "provider": vision_provider,
                    "model": vision_model,
                    "base_url": vision_base_url,
                    "api_key": "",
                }

        # Phase 2-3: 自动生成 model_routing 规则
        # 优先使用 Ollama 模型，其次使用其他本地服务模型
        routing_source = ollama_info
        if not routing_source and local_server_infos:
            routing_source = local_server_infos[0]

        if routing_source and len(routing_source.get("models", [])) >= 2:
            classified = routing_source.get("classified_models", [])
            vision_models = [m for m in classified if m.get("type") == "vision"]
            text_models = [m for m in classified if m.get("type") != "vision"]
            reasoning_models = [m for m in classified if m.get("type") == "reasoning"]
            coding_models = [
                m for m in classified
                if any(kw in m.get("name", "").lower() for kw in ("coder", "code-"))
            ]

            routing = cfg.get("model_routing", {})
            if not isinstance(routing, dict):
                routing = {}

            rules = []

            # vision 规则
            if vision_models:
                rules.append({
                    "name": "vision",
                    "match": {"has_image": True},
                    "model": vision_models[0]["name"],
                })

            # reasoning 规则
            rules.append({
                "name": "reasoning",
                "match": {
                    "keywords": ["分析", "推理", "思考", "证明"],
                },
                "model": reasoning_models[0]["name"] if reasoning_models else primary_model,
            })

            # coding 规则（阶段 2：有编码专用模型时自动生成）
            if coding_models:
                rules.append({
                    "name": "coding",
                    "match": {
                        "keywords": [
                            "写代码", "函数", "class", "debug",
                            "实现一个", "编程", "refactor", "coding",
                        ],
                        "threshold": 1,
                    },
                    "model": coding_models[0]["name"],
                })

            # short_chat 规则（阶段 3：有小参数量模型时自动生成）
            small_models = [
                m for m in text_models
                if _get_local_model_param_size(m["name"]) <= 8.0
                and m["name"] != primary_model
            ]
            if small_models:
                rules.append({
                    "name": "short_chat",
                    "match": {
                        "max_length": 80,
                        "exclude_keywords": ["bug", "报错", "crash", "fix", "error", "分析"],
                    },
                    "model": small_models[0]["name"],
                })

            # default 规则
            rules.append({
                "name": "default",
                "model": primary_model,
            })

            routing["rules"] = rules
            # 同步旧格式键（doctor / run_agent 仍检查 model_routing.default/vision/reasoning）
            for name in ("default", "vision", "reasoning"):
                rule = next((r for r in rules if r["name"] == name), None)
                if rule:
                    routing[name] = {"model": rule["model"]}
                else:
                    routing.pop(name, None)
            cfg["model_routing"] = routing
            logger.info(
                "自动生成 model_routing 规则: %d 条 (vision/reasoning%s%s/default)",
                len(rules),
                "/coding" if coding_models else "",
                "/short_chat" if small_models else "",
            )
        else:
            # 单模型或无模型场景: 清除旧 model_routing 防止残留
            # 例如用户从 Ollama 多模型切换到 llama.cpp 单模型时,
            # 旧规则仍引用 Ollama 模型名, 会被 _apply_model_routing 激活
            cfg.pop("model_routing", None)
            logger.info("无 model_routing 规则 (单模型场景), 已清除旧规则")

        save_config(cfg)

        # 保存所有 API Key 到 .env
        for p in api_providers:
            key_val = os.environ.get(p["env_var"], "")
            if key_val:
                save_env_value(p["env_var"], key_val)

        return True
    except Exception as e:
        logger.warning("写入智能路由配置失败: %s", e)
        return False


def _write_local_backends(
    ollama_info: Optional[dict] = None,
    local_server_infos: Optional[list[dict]] = None,
) -> bool:
    """将多本地后端配置写入 config.yaml 的 local_backends 段。

    SmartRouter v2 使用 local_backends 统一管理所有本地推理服务:
      Ollama (port 11434), LM Studio (port 1234), llama.cpp (port 8080), FastLLM (port 8088)

    每个后端条目包含:
      - name: 后端名称 (ollama / lm-studio / llama-cpp / fastllm)
      - base_url: API 地址
      - priority: 路由优先级 (数字越小越优先)
    """
    try:
        from hermes_cli.config import load_config, save_config

        cfg = load_config()
        backends = []
        priority = 1

        # Ollama
        if ollama_info and ollama_info.get("available"):
            backends.append({
                "name": "ollama",
                "base_url": "http://localhost:11434/v1",
                "priority": priority,
            })
            priority += 1

        # LM Studio / llama.cpp / FastLLM
        local_server_infos = local_server_infos or []
        for li in local_server_infos:
            if li.get("available") and li.get("base_url"):
                backends.append({
                    "name": li.get("name", "").lower().replace(" ", "-"),
                    "base_url": li.get("base_url", ""),
                    "priority": priority,
                })
                priority += 1

        if backends:
            # v2.1 合并模式: 保留用户手动添加的自定义后端
            existing = cfg.get("local_backends", [])
            if isinstance(existing, list):
                # 已知后端名称白名单 (quickstart 管理的)
                known_names = {"ollama", "lm-studio", "llama-cpp", "fastllm", "vllm", "localai"}
                detected_urls = {b["name"]: b["base_url"] for b in backends}
                for old_entry in existing:
                    old_name = old_entry.get("name", "")
                    # 保留非已知名称的自定义后端
                    if old_name not in known_names:
                        if old_entry.get("base_url", "") not in detected_urls.values():
                            backends.append(old_entry)
                    # 已知后端如果已离线, 保留旧配置 (不覆盖)
                    elif old_name in known_names and not any(
                        b["name"] == old_name and b["base_url"] for b in backends
                    ):
                        backends.append(old_entry)
            cfg["local_backends"] = backends
        else:
            # 保留旧 local_backends (如果用户手动配置了)
            cfg.pop("local_backends", None)

        save_config(cfg)
        logger.info("local_backends 配置已写入: %d 个后端", len(backends))
        return True
    except Exception as e:
        logger.warning("写入 local_backends 配置失败: %s", e)
        return False


def _get_current_provider_label() -> str:
    """获取当前配置的主力提供商描述。"""
    try:
        from hermes_cli.config import load_config

        cfg = load_config()
        model_cfg = cfg.get("model", {})
        if isinstance(model_cfg, dict):
            provider = model_cfg.get("provider", "")
            model = model_cfg.get("default", "")
            if provider and model:
                return f"{provider} ({model})"
            elif provider:
                return provider
        return ""
    except Exception:
        return ""


def _prompt_yes_no(prompt: str, default: bool = True) -> bool:
    """通用 Y/n 询问。"""
    hint = "[Y/n]" if default else "[y/N]"
    try:
        reply = input(f"  {prompt} {hint}: ").strip().lower()
    except (EOFError, KeyboardInterrupt):
        return default
    if not reply:
        return default
    return reply in ("y", "yes")



def _prompt_add_custom_backend() -> Optional[dict]:
    """交互式添加自定义本地推理后端 (Phase E: 新后端接入模板)。

    引导用户输入后端名称、端口和默认模型名。
    返回 server_config dict (兼容 _LOCAL_SERVER_CONFIGS 格式) 或 None。
    """
    from hermes_cli.colors import Colors, color

    print()
    print(f"  {color('🔧', Colors.BLUE)} 添加自定义本地后端")
    print(f"     支持任意 OpenAI 兼容的本地推理服务 (vLLM, LocalAI, Ollama, 自建服务等)")
    print()

    # 后端名称
    name = input("    后端名称 (如 vLLM、MyServer): ").strip()
    if not name:
        print(f"  {color('ℹ', Colors.BLUE)} 已跳过")
        return None

    name_id = name.lower().replace(" ", "-")

    # 端口
    port_str = input("    端口号 (默认 8000): ").strip()
    try:
        port = int(port_str) if port_str else 8000
    except ValueError:
        print(f"  {color('✗', Colors.RED)} 无效端口号")
        return None

    base_url = f"http://localhost:{port}/v1"

    # 默认模型
    default_model = input("    默认模型名 (如 qwen2.5-7b-instruct): ").strip()
    if not default_model:
        default_model = "qwen2.5-7b-instruct"

    # 验证连通性
    print(f"    正在探测 {base_url}/models ...", end=" ")
    try:
        info = _detect_local_server({
            "id": name_id,
            "name": name,
            "base_url": base_url,
            "display_name": f"{name}（自定义）",
            "default_model": default_model,
        })
        if info and info.get("available"):
            model_count = len(info.get("models", []))
            print(f"{color('✓', Colors.GREEN)} ({model_count} 个模型)")
            return info
        else:
            print(f"{color('⚠', Colors.YELLOW)} 无法连接（已记录配置，启动后端后自动生效）")
            return {
                "available": False,
                "provider_id": name_id,
                "name": name,
                "display_name": f"{name}（自定义, 离线）",
                "base_url": base_url,
                "models": [],
                "default_model": default_model,
            }
    except Exception as e:
        print(f"{color('⚠', Colors.YELLOW)} 探测失败: {e}")
        return {
            "available": False,
            "provider_id": name_id,
            "name": name,
            "display_name": f"{name}（自定义）",
            "base_url": base_url,
            "models": [],
            "default_model": default_model,
        }

# ── 安装本地模型 ──

def _prompt_install_local_model() -> int:
    """引导用户安装本地离线模型。返回 0 成功，1 失败/跳过。"""
    from hermes_cli.colors import Colors, color

    print(f"  🔧 自动安装本地离线模型...")
    print(f"     未检测到任何可用的 AI 资源。")
    print(f"     将自动安装本地离线模型（约 1.58GB），无需网络即可使用。")
    print()

    if not _prompt_yes_no("确认安装？", default=True):
        print(f"  {color('ℹ', Colors.BLUE)} 跳过安装")
        print()
        print(f"  您随时可以运行以下命令手动配置:")
        print(f"    hermes local-models setup     — 安装本地模型")
        print(f"    hermes setup                  — 配置 API Key")
        print(f"    hermes quickstart             — 重新自动检测")
        return 1

    print()
    print(f"  {color('⏳', Colors.YELLOW)} 正在安装，请稍候...")
    print()

    try:
        from hermes_cli.model_manager import cmd_local_models_setup

        setup_args = type("Args", (), {"yes": True, "model": None})()
        result = cmd_local_models_setup(setup_args)

        if result == 0:
            print(f"  {color('✅', Colors.GREEN)} 模型安装完成，正在写入配置...")
            _configure_embedded()
            return 0
        else:
            print(f"  {color('❌', Colors.RED)} 模型安装失败，请检查网络后重试")
            print(f"     运行: hermes local-models setup")
            return 1
    except Exception as e:
        print(f"  {color('❌', Colors.RED)} 安装出错: {e}")
        print(f"     运行: hermes local-models setup")
        return 1


# ── 主入口 ──

# ── MemPalace 知识库检测 ──

def _detect_mempalace() -> Optional[dict]:
    """检测 MemPalace 是否可用，返回配置信息。"""
    result: dict = {"installed": False, "initialized": False, "palace_path": ""}

    # 1. 检查 pip 包是否安装
    try:
        import importlib
        importlib.import_module("mempalace")
        result["installed"] = True
    except ImportError:
        return None

    # 2. 检查宫殿是否已初始化
    try:
        from hermes_cli.config import get_hermes_home
        hermes_home = get_hermes_home()
        # 可能的宫殿位置：项目根目录 > ~/.mempalace/palace
        palace_dirs = [
            os.path.join(hermes_home, "..", "mempalace", "palace"),
            os.path.expanduser("~/.mempalace/palace"),
        ]
        for d in palace_dirs:
            if os.path.isdir(d):
                result["initialized"] = True
                result["palace_path"] = d
                break
    except Exception:
        pass

    # 3. 检查 MCP 是否已配置
    result["mcp_configured"] = False
    try:
        from hermes_cli.config import load_config
        cfg = load_config()
        mcp = cfg.get("mcp_servers", {})
        if isinstance(mcp, dict) and "mempalace" in mcp:
            result["mcp_configured"] = True
    except Exception:
        pass

    return result


def _configure_mempalace_mcp() -> bool:
    """将 MemPalace MCP 服务器配置写入 config.yaml。

    自动检测 Python 路径，优先使用当前运行的解释器。
    如果 MCP 已配置，跳过不覆盖。
    """
    try:
        from hermes_cli.config import load_config, save_config

        cfg = load_config()
        mcp = cfg.get("mcp_servers", {})
        if not isinstance(mcp, dict):
            mcp = {}

        # 已配置则跳过
        if "mempalace" in mcp:
            return True

        python_path = sys.executable

        mcp["mempalace"] = {
            "command": python_path,
            "args": ["-m", "mempalace.mcp_server"],
            "env": {},
        }
        cfg["mcp_servers"] = mcp
        save_config(cfg)

        logger.info("MemPalace MCP 已配置: command=%s", python_path)
        return True
    except Exception as e:
        logger.warning("配置 MemPalace MCP 失败: %s", e)
        return False


def cmd_quickstart(args) -> int:
    """一键快速配置 Hermes-Agent-CN 智能路由。

    检测所有可用资源后自动配置多层路由：
      Ollama / LM Studio / llama.cpp（主力） → 云端 API（降级） → 嵌入式（断网兜底）
    """
    from hermes_cli.colors import Colors, color

    print()
    print(f"{'=' * 60}")
    print(f"  ⚡ Hermes-Agent-CN 快捷启动")
    print(f"{'=' * 60}")
    print()

    # ── Step 1: 并行收集全部资源 ──
    print(f"  🔍 Step 1/3: 扫描可用资源...")

    api_providers = _detect_api_key_providers()
    ollama_info = _detect_ollama()
    has_embedded = _has_embedded_models()
    mempalace_info = _detect_mempalace()

    # 检测 LM Studio 和 llama.cpp
    local_server_infos = []
    for srv in _LOCAL_SERVER_CONFIGS:
        info = _detect_local_server(srv)
        if info:
            local_server_infos.append(info)

    resource_count = (
        len(api_providers)
        + (1 if ollama_info else 0)
        + len(local_server_infos)
        + (1 if has_embedded else 0)
    )

    # ── 显示检测结果 ──
    if api_providers:
        print(f"  {color('✓', Colors.GREEN)} 云端 API Key ({len(api_providers)} 个):")
        for p in api_providers:
            key_preview = os.environ.get(p["env_var"], "")[:8]
            print(f"      {p['name']:12s}  ({p['env_var']}={key_preview}...)")
    else:
        print(f"  {color('⚠', Colors.YELLOW)} 云端 API Key: 未检测到")

    if ollama_info:
        models = ollama_info.get("models", [])
        classified = ollama_info.get("classified_models", [])
        if models and len(models) == 1:
            print(f"  {color('✓', Colors.GREEN)} Ollama 本地推理: 运行中 ({models[0]})")
        elif models and len(models) > 1:
            print(f"  {color('✓', Colors.GREEN)} Ollama 本地推理: 运行中 ({len(models)} 个模型)")
            primary = ollama_info.get("default_model", "")
            vision = ollama_info.get("vision_model")
            for m_info in classified:
                name = m_info["name"]
                mtype = m_info["type"]
                tag = ""
                if name == primary:
                    tag = " (主力)"
                elif name == vision:
                    tag = " → auxiliary.vision"
                type_label = {"vision": "视觉", "reasoning": "推理", "text": "文本"}.get(mtype, mtype)
                print(f"      {type_label:4s}: {name}{tag}")
        elif not models:
            print(f"  {color('✓', Colors.GREEN)} Ollama 本地推理: 运行中（暂无模型）")
    else:
        print(f"  {color('⚠', Colors.YELLOW)} Ollama 本地推理: 未运行")

    # 显示 LM Studio / llama.cpp 检测结果
    for li in local_server_infos:
        models = li.get("models", [])
        if models:
            display = li.get("display_name", li.get("name", ""))
            default = li.get("default_model", "")
            vision = li.get("vision_model")
            if len(models) == 1:
                print(f"  {color('✓', Colors.GREEN)} {display}: 运行中 ({default})")
            else:
                details = []
                if default:
                    details.append(f"主力: {default}")
                if vision:
                    details.append(f"视觉: {vision}")
                extra = f" ({', '.join(details)})" if details else ""
                print(f"  {color('✓', Colors.GREEN)} {display}: 运行中 ({len(models)} 个模型){extra}")
        else:
            display = li.get("display_name", li.get("name", ""))
            print(f"  {color('✓', Colors.GREEN)} {display}: 运行中（暂无模型）")

    if has_embedded:
        print(f"  {color('✓', Colors.GREEN)} 离线兜底模型: 已安装")
    else:
        print(f"  {color('⚠', Colors.YELLOW)} 离线兜底模型: 未安装")

    if mempalace_info and mempalace_info.get("installed"):
        mcp_status = "已配置" if mempalace_info.get("mcp_configured") else "待配置"
        init_status = "已初始化" if mempalace_info.get("initialized") else "未初始化"
        print(f"  {color('✓', Colors.GREEN)} MemPalace 记忆库: {init_status}（MCP {mcp_status}）")

    print()
    # Phase E: 自定义后端接入
    custom_backend_count = 0
    while True:
        if not _prompt_yes_no("添加自定义本地后端？", default=False):
            break
        custom_info = _prompt_add_custom_backend()
        if custom_info:
            local_server_infos.append(custom_info)
            custom_backend_count += 1
            resource_count += 1
            if custom_info.get("available") and custom_info.get("models"):
                display = custom_info.get("display_name", custom_info.get("name", ""))
                print()
                print(f"  {color('✓', Colors.GREEN)} {display}: 已添加")
            else:
                display = custom_info.get("display_name", custom_info.get("name", ""))
                print(f"  {color('ℹ', Colors.BLUE)} {display}: 已记录（启动后端后自动生效）")
        else:
            break


    # ── 无资源 → 引导安装 ──
    if resource_count == 0:
        print(f"  ❌ 未检测到任何可用的 AI 资源")
        print()
        result = _prompt_install_local_model()
        if result == 0:
            print(f"\n{'=' * 60}")
            print(f"  🎉 全部就绪！直接运行 hermes 即可开始对话")
            print(f"{'=' * 60}")
            print()
        return result

    # ── Step 2: 确定主力提供商 ──
    print(f"  ⚙ Step 2/3: 配置智能路由...")

    # 检查是否已有配置
    current_label = _get_current_provider_label()
    downgrade_old = False

    if current_label:
        print(f"  {color('ℹ', Colors.BLUE)} 当前主力: {current_label}")
        downgrade_old = _prompt_yes_no(
            f"将现有配置降为回退模型？",
            default=True,
        )
        print()

    # 确定主力提供商：Ollama > LM Studio > llama.cpp > 云端 API > 嵌入式
    primary_id = ""
    primary_model = ""
    primary_local_info = None

    if ollama_info:
        primary_id = "ollama"
        primary_model = ollama_info["default_model"]
    elif local_server_infos:
        primary_local_info = local_server_infos[0]
        primary_id = primary_local_info["provider_id"]
        primary_model = primary_local_info["default_model"]
    elif api_providers:
        primary_id = api_providers[0]["id"]
        primary_model = api_providers[0]["default_model"]
    elif has_embedded:
        primary_id = "embedded"
        primary_model = "qwen-0.5b"

    if not primary_id:
        print(f"  {color('❌', Colors.RED)} 无法确定主力提供商")
        return 1

    # ── Step 3: 构建路由链并写入 ──
    fallback_chain = _build_fallback_chain(
        api_providers, ollama_info, has_embedded, primary_id,
        local_server_infos=local_server_infos,
    )

    # 如果用户选择降级旧配置，将旧配置插入 fallback 链
    if downgrade_old and current_label:
        try:
            from hermes_cli.config import load_config
            cfg = load_config()
            old_model_cfg = cfg.get("model", {})
            if isinstance(old_model_cfg, dict):
                old_provider = old_model_cfg.get("provider", "")
                old_default = old_model_cfg.get("default", "")
                old_base_url = old_model_cfg.get("base_url", "").rstrip("/")
                
                # 获取新主力的 base_url
                new_base_url = ""
                if primary_local_info:
                    new_base_url = primary_local_info.get("base_url", "").rstrip("/")
                
                # 同 base_url = 同一服务，不重复加
                same_service = bool(
                    old_base_url and new_base_url
                    and old_base_url == new_base_url
                )
                
                if (
                    old_provider and old_default
                    and old_provider != primary_id
                    and not same_service
                ):
                    old_entry = {"provider": old_provider, "model": old_default}
                    if old_base_url:
                        old_entry["base_url"] = old_base_url
                    # 去重（provider+model）
                    existing_entries = {
                        (f.get("provider"), f.get("model"))
                        for f in fallback_chain
                    }
                    if (old_provider, old_default) not in existing_entries:
                        fallback_chain.insert(0, old_entry)
        except Exception:
            pass

    # 写入配置
    if primary_id == "ollama":
        _configure_ollama(ollama_info)
    elif primary_id == "embedded":
        _configure_embedded()
    elif primary_local_info:
        _configure_local_server(primary_local_info)
    else:
        # 找到对应的 cloud provider dict
        for p in api_providers:
            if p["id"] == primary_id:
                _configure_provider(p)
                break

    # 然后写入完整的智能路由（覆盖上面写入的 model 配置）
    _write_smart_routing(
        primary_id, primary_model, fallback_chain,
        api_providers, ollama_info,
        local_server_infos=local_server_infos,
    )

    # v2: 写入多后端配置（local_backends）
    _write_local_backends(
        ollama_info=ollama_info,
        local_server_infos=local_server_infos,
    )

    # MemPalace MCP 自动配置（如果已安装且未配置）
    if mempalace_info and mempalace_info.get("installed"):
        if not mempalace_info.get("mcp_configured"):
            if _configure_mempalace_mcp():
                print(f"  {color('✓', Colors.GREEN)} MemPalace MCP 已自动配置")
            else:
                print(f"  {color('⚠', Colors.YELLOW)} MemPalace MCP 配置失败，请手动设置")

    # ── 显示结果 ──
    print()
    print(f"{'=' * 60}")
    print(f"  ✅ 智能路由配置完成！")
    print(f"{'=' * 60}")
    print()

    # 主力
    _provider_names = {p["id"]: p["name"] for p in _PROVIDER_CHECKS}
    _provider_names["ollama"] = "Ollama（本地）"
    _provider_names["lm_studio"] = "LM Studio（本地）"
    _provider_names["llama_cpp"] = "llama.cpp（本地）"
    _provider_names["embedded"] = "Qwen2.5-0.5B（离线）"

    primary_name = _provider_names.get(primary_id, primary_id)
    print(f"  🔵 主力推理: {primary_name} — {primary_model}")

    # MemPalace 知识库状态
    if mempalace_info and mempalace_info.get("installed"):
        mcp_ok = mempalace_info.get("mcp_configured")
        status_text = "已就绪" if mcp_ok else "已启用（下次重启生效）"
        print(f"  🧠 知识库: MemPalace — {status_text}")

    # auxiliary.vision 显示
    vision_model = (ollama_info or {}).get("vision_model")
    if not vision_model and local_server_infos:
        vision_model = local_server_infos[0].get("vision_model")
    if vision_model:
        vision_label = "Ollama（本地）" if ollama_info and ollama_info.get("vision_model") else "本地服务"
        print(f"  👁 视觉分析: {vision_label} — {vision_model} (auxiliary)")

    # coding 模型显示
    coding_models = [m for m in (ollama_info or {}).get("classified_models", []) if m.get("type") == "coding"]
    if coding_models:
        cname = coding_models[0]["name"]
        print(f"  💻 代码编程: Ollama（本地） — {cname} (coding)")
    # fallback 链
    if fallback_chain:
        print(f"  📋 回退路由:")
        for i, fb in enumerate(fallback_chain, 1):
            fb_provider = fb.get("provider", "")
            fb_model = fb.get("model", "")
            fb_name = _provider_names.get(fb_provider, fb_provider)
            print(f"      {i}. {fb_name} — {fb_model}")
    else:
        print(f"  ⚠ 无回退路由（仅主力模型）")

    print()
    print(f"  运行 hermes 即可开始对话。如需调整，运行: hermes model")
    print()
    print(f"{'=' * 60}")
    print()

    return 0

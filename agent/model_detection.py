"""
Model detection utilities — shared between quickstart.py and SmartRouter.

Provides 3-layer Ollama model classification:
    L1: Name keyword matching (fast, no API)
    L2: Known family matching (fast, no API)
    L3: /api/show template inspection (API call, cached)

Also provides embedding/coding model detection for routing exclusion.

Usage:
    from agent.model_detection import classify_ollama_model, infer_vision_support
"""

from typing import Optional
import json

# ── Ollama 模型分类关键词 ──

_VISION_KEYWORDS = ("vl", "vision", "llava", "cogvlm", "minicpm-v")
_REASONING_KEYWORDS = ("r1", "reasoning", "think", "qwq")

# L2 层：无需 API 调用的已知视觉家族检测
# 部分模型（如 qwen3-vl）已被 L1 关键词匹配，此处只放纯多模态家族
# 选入规则：该家族所有已知模型都支持视觉，且名称无法被 L1 关键词覆盖
_VISION_FAMILIES = (
    "internvl2", "internvl",
    "pixtral", "bakllava",
    "moondream", "llama-v", "llava-llama",
)
# 匹配家族但实际是编码专用或非视觉模型的排除关键词
# 注: 模型名会被 replace('-', ' ') 归一化，所以排除词也需考虑空格形式
_VISION_FAMILY_EXCLUSIONS = (
    "coder", "code ", "instruct-code", "deepseek", "yi-lightning",
)

_OLLAMA_MODEL_INFO_CACHE: dict = {}


# ── API 调用 ──


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


# ── 分类函数 ──


def classify_ollama_model(name: str) -> str:
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


def infer_vision_support(model_name: str) -> bool:
    """快速判断模型是否支持视觉（仅 L1+L2，无 API 调用）。

    SmartRouter 在探测阶段使用此函数，避免额外 API 开销。
    如需完整 3 层检测（含模板探查），请使用 classify_ollama_model()。
    """
    name_lower = model_name.lower().split(":")[0]

    # L1: 关键词
    if any(kw in name_lower for kw in _VISION_KEYWORDS):
        return True

    # L2: 已知视觉家族
    for family in _VISION_FAMILIES:
        if family in name_lower:
            if not any(excl in name_lower for excl in _VISION_FAMILY_EXCLUSIONS):
                # 排除编码模型
                if not any(cw in name_lower for cw in ("coder", "code-", "instruct-code")):
                    return True

    return False


def is_embedding_model(name: str) -> bool:
    """判断是否是 embedding 模型（不适合用于 chat/routing）。"""
    name_lower = name.lower().split(":")[0]
    return "embed" in name_lower


def is_coding_model(name: str) -> bool:
    """判断是否是编码专用模型。"""
    name_lower = name.lower().split(":")[0]
    return any(kw in name_lower for kw in ("coder", "code-", "instruct-code"))

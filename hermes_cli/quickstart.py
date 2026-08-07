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
        "name": "阿里云通义千问（百炼）",
        "env_var": "DASHSCOPE_API_KEY",
        "default_model": "qwen-turbo-latest",
        "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
    },
    {
        "id": "baidu",
        "name": "百度千帆",
        "env_var": "QIANFAN_API_KEY",
        "default_model": "ernie-4.0-8k-latest",
        "base_url": "https://qianfan.baidubce.com/v2",
    },
    {
        "id": "volcengine",
        "name": "火山引擎（豆包）",
        "env_var": "ARK_API_KEY",
        "default_model": "doubao-pro-32k",
        "base_url": "https://ark.cn-beijing.volces.com/api/v3",
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

# ── Ollama 模型分类（共享自 agent.model_detection） ──
from agent.model_detection import (
    _VISION_KEYWORDS,
    _REASONING_KEYWORDS,
    _VISION_FAMILIES,
    _VISION_FAMILY_EXCLUSIONS,
    _get_ollama_model_info,
    _check_vision_template,
    classify_ollama_model,
    is_embedding_model,
    is_coding_model,
)


def _get_ollama_model_info(name: str) -> Optional[dict]:
    """Proxy to shared implementation in agent.model_detection."""
    from agent.model_detection import _get_ollama_model_info as _shared_get_info
    return _shared_get_info(name)


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
    """Proxy to shared implementation in agent.model_detection."""
    from agent.model_detection import _check_vision_template as _shared
    return _shared(name)


def _classify_ollama_model(name: str) -> str:
    """Three-layer classification of Ollama models.

    L1: Name keyword matching (fast, no API)
    L2: Known family matching (fast, no API)
    L3: /api/show template inspection (API call, cached)

    Returns:
        "vision" | "reasoning" | "coding" | "embedding" | "text"
    """
    return classify_ollama_model(name)


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


def _check_endpoint(endpoint: str, timeout: float = 5.0) -> bool:
    """检测 API 端点是否可连接。"""
    import socket

    try:
        from urllib.parse import urlparse

        parsed = urlparse(endpoint)
        host = parsed.hostname or ""
        port = parsed.port or (443 if parsed.scheme == "https" else 80)
        sock = socket.create_connection((host, port), timeout=timeout)
        sock.close()
        return True
    except Exception:
        return False


def _network_diagnostics() -> list[dict]:
    """检测常见国产 API 端点可达性，返回诊断结果列表。

    每条结果: {"provider": str, "endpoint": str, "reachable": bool}
    """
    endpoints = [
        ("DeepSeek", "https://api.deepseek.com"),
        ("硅基流动", "https://api.siliconflow.cn"),
        ("智谱 GLM", "https://open.bigmodel.cn"),
        ("月之暗面 Kimi", "https://api.moonshot.cn"),
        ("MiniMax", "https://api.minimax.chat"),
        ("阿里云百炼", "https://dashscope.aliyuncs.com"),
        ("百度千帆", "https://qianfan.baidubce.com"),
        ("火山引擎", "https://ark.cn-beijing.volces.com"),
    ]
    results = []
    from hermes_cli.colors import Colors, color

    for name, url in endpoints:
        ok = _check_endpoint(url)
        icon = color("✓", Colors.GREEN) if ok else color("✗", Colors.RED)
        results.append({"provider": name, "endpoint": url, "reachable": ok})
        print(f"    {icon} {name:20s} {url}")
    return results


# ── Ollama host resolution (NAT-aware) ──────────────────────────────────────
# Before this section, every Ollama URL was hardcoded `http://localhost:11434`,
# which silently breaks for WSL2 users running Ollama on the Windows host with
# NAT networking (the most common 2026+ setup). In WSL2 NAT mode, `localhost`
# inside the distro points at the distro's own loopback, NOT the Windows host,
# so detection silently returns "Ollama not found" even though `ollama serve`
# is happily listening on Windows.
#
# Resolution order (first hit wins for detection; cached for base_url writes):
#   1. HERMES_OLLAMA_HOST env var (full URL, e.g. http://192.168.1.5:11434)
#   2. http://localhost:11434       — Linux native / WSL mirrored / Mac
#   3. http://host.docker.internal:11434 — WSL2 NAT (Windows host reachable
#      via WSL2's special DNS injection; only works if Ollama binds to
#      0.0.0.0 or 127.0.0.1 with WSL2 NAT routing intact)
#   4. /etc/resolv.conf `nameserver` IP:11434 — generic Linux fallback when
#      WSL2 host.docker.internal isn't injected (older distros, custom images)
#
# IMPORTANT: even with this code fix, Windows-side Ollama must bind to a
# routable interface (set OLLAMA_HOST=0.0.0.0 in Windows env and restart the
# Ollama service) for options 3 and 4 to actually work. Without that, only
# options 1 and 2 will succeed — i.e. mirrored mode or a custom env override.

_OLLAMA_HOST_CACHE: Optional[str] = None
"""First URL where `_detect_ollama()` actually got a 200 from `/api/tags`.
Populated by `_detect_ollama()` on success; consulted by
`_get_ollama_base_url()` so base_url writes (model_cfg, fallback_model,
auxiliary.vision, etc.) match the URL detection proved reachable."""


def _probe_ollama_urls() -> list[str]:
    """Return ordered candidate URLs to probe for an Ollama server.

    Pure function — no network I/O. Used both by detection (probe each
    until one answers) and by base_url writers (fall back to localhost
    when detection never ran).
    """
    candidates: list[str] = []
    env = os.getenv("HERMES_OLLAMA_HOST", "").strip()
    if env:
        candidates.append(env.rstrip("/"))
    candidates.append("http://localhost:11434")
    # WSL2 NAT fallback: host.docker.internal is a Docker convention
    # that WSL2's daemon injects via /etc/hosts (or similar) so it
    # resolves to the Windows host's loopback. Detect WSL2 cheaply
    # via the WSL_DISTRO_NAME env var (set by the WSL launcher).
    if os.getenv("WSL_DISTRO_NAME") or os.path.exists("/proc/sys/fs/binfmt_misc"):
        candidates.append("http://host.docker.internal:11434")
    # Generic Linux /etc/resolv.conf nameserver fallback (NAT cases
    # where WSL2 magic doesn't apply — older distros, custom images,
    # containers, plain Linux VM behind a NAT).
    try:
        resolv = Path("/etc/resolv.conf")
        if resolv.exists():
            for line in resolv.read_text(encoding="utf-8", errors="ignore").splitlines():
                stripped = line.strip()
                if stripped.startswith("nameserver"):
                    parts = stripped.split()
                    if len(parts) >= 2:
                        ip = parts[1].strip()
                        if ip and ip not in ("127.0.0.1", "::1", "127.0.0.53"):
                            candidates.append(f"http://{ip}:11434")
                    break
    except Exception:
        pass
    return candidates


def _get_ollama_base_url() -> str:
    """Return the Ollama OpenAI-compatible base URL (with /v1 suffix).

    Prefers the host detection already proved reachable
    (`_OLLAMA_HOST_CACHE`); falls back to probing each candidate; falls
    back to localhost as a last resort. Always returns a `/v1` URL.
    """
    global _OLLAMA_HOST_CACHE
    if _OLLAMA_HOST_CACHE:
        return f"{_OLLAMA_HOST_CACHE}/v1"
    # Probe lazily so writers (model_cfg, fallback, vision) get a
    # reasonable URL even if `_detect_ollama()` was never called.
    import urllib.request
    for base in _probe_ollama_urls():
        try:
            req = urllib.request.Request(
                f"{base}/api/tags", method="GET",
                headers={"Accept": "application/json"},
            )
            urllib.request.urlopen(req, timeout=2).read()
            _OLLAMA_HOST_CACHE = base
            return f"{base}/v1"
        except Exception:
            continue
    return "http://localhost:11434/v1"


def _detect_ollama() -> Optional[dict]:
    """检测本地 Ollama 服务是否运行，返回可用模型列表（含分类）。

    Tries each URL in `_probe_ollama_urls()` (env override → localhost →
    host.docker.internal → /etc/resolv.conf nameserver) so WSL2 NAT users
    running Ollama on the Windows host are detected instead of silently
    returning None. Logs which URL worked so users debugging
    'quickstart doesn't see my ollama' know what to investigate.
    """
    global _OLLAMA_HOST_CACHE
    import urllib.request
    last_err: Optional[str] = None
    for base in _probe_ollama_urls():
        try:
            req = urllib.request.Request(
                f"{base}/api/tags",
                method="GET",
                headers={"Accept": "application/json"},
            )
            resp = urllib.request.urlopen(req, timeout=3)
            if resp.status == 200:
                data = json.loads(resp.read().decode())
                models = data.get("models", [])
                _OLLAMA_HOST_CACHE = base
                logger.info("Ollama detected at %s (%d models)", base, len(models))
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
        except Exception as exc:
            last_err = f"{base}: {type(exc).__name__}"
            continue
    if last_err:
        logger.debug("Ollama not reachable on any candidate: %s", last_err)
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


# ── 配置清理函数 ──


def _cleanup_config() -> list[str]:
    """整理简化 config.yaml，返回变更列表。

    处理项：
    - 删除空 dict / list 段落（providers, fallback_providers, credential_pool_strategies 等）
    - 删除默认 Docker/容器 terminal 配置（日常用不到）
    - 统一 fallback 格式（fallback_providers → fallback_model）
    - 删除空字符串值
    """
    from hermes_cli.config import load_config, save_config

    changes: list[str] = []
    try:
        cfg = load_config()
        original = str(cfg)

        # 1. 删除空值段落
        for key in list(cfg.keys()):
            val = cfg[key]
            if isinstance(val, dict) and not val:
                cfg.pop(key, None)
                changes.append(f"删除空段落: {key}")
            elif isinstance(val, list) and not val:
                cfg.pop(key, None)
                changes.append(f"删除空列表: {key}")
            elif val == "":
                cfg.pop(key, None)
                changes.append(f"删除空值: {key}")

        # 2. 清理 agent 中的空默认值
        agent = cfg.get("agent", {})
        if isinstance(agent, dict):
            for k in ("service_tier",):
                if agent.get(k) in ("", None):
                    agent.pop(k, None)
                    changes.append(f"清理 agent.{k} 空值")
            # 清理空 dict 的子段落
            for sk in list(agent.keys()):
                sv = agent[sk]
                if isinstance(sv, dict) and not sv:
                    agent.pop(sk, None)
                    changes.append(f"清理 agent.{sk} 空段")

        # 3. 清理 terminal 中的 Docker/容器默认配置
        terminal = cfg.get("terminal", {})
        if isinstance(terminal, dict):
            container_defaults = (
                "docker_image", "docker_forward_env", "docker_env",
                "singularity_image", "modal_image", "daytona_image",
                "vercel_runtime", "container_cpu", "container_memory",
                "container_disk",
            )
            for ck in container_defaults:
                if ck in terminal and terminal[ck] is not None:
                    terminal.pop(ck, None)
                    changes.append(f"清理 terminal.{ck} (容器默认)")

        # 4. 统一 fallback 格式：fallback_providers → fallback_model
        if "fallback_model" in cfg and "fallback_providers" in cfg:
            cfg.pop("fallback_providers", None)
            changes.append("统一 fallback: fallback_providers → fallback_model")

        if str(cfg) != original:
            save_config(cfg)
        return changes
    except Exception as e:
        logger.warning("config 清理失败: %s", e)
        return changes


def _cleanup_env() -> list[str]:
    """整理简化 ~/.hermes/.env 文件。

    处理项：
    - 删除重复 KEY（保留最后出现的值）
    - 删除明显无用的空 KEY
    """
    import re
    from pathlib import Path

    changes: list[str] = []
    env_path = Path.home() / ".hermes" / ".env"
    try:
        if not env_path.exists():
            return changes

        lines = env_path.read_text(encoding="utf-8").splitlines()
        new_lines: list[str] = []
        seen_keys: set[str] = set()
        duplicate_keys: set[str] = set()
        key_line_indices: dict[str, int] = {}

        for i, line in enumerate(lines):
            stripped = line.strip()
            # 保留注释和空行
            if not stripped or stripped.startswith("#"):
                new_lines.append(line)
                continue

            # 解析 KEY=VALUE
            if "=" in stripped:
                key = stripped.split("=", 1)[0].strip()
                if key in seen_keys:
                    duplicate_keys.add(key)
                seen_keys.add(key)
                key_line_indices[key] = len(new_lines)
                new_lines.append(line)
            else:
                new_lines.append(line)

        # 删除重复 KEY（保留最后出现的行）
        if duplicate_keys:
            for key in duplicate_keys:
                last_idx = key_line_indices[key]
                # 找到之前出现的该 KEY 的行并删除
                new_lines2: list[str] = []
                remove_next = False
                for idx, line in enumerate(new_lines):
                    if idx == last_idx:
                        remove_next = False
                        new_lines2.append(line)
                        continue
                    stripped = line.strip()
                    if "=" in stripped and stripped.split("=", 1)[0].strip() == key and idx < last_idx:
                        remove_next = True
                        changes.append(f"删除重复 KEY: {key} (保留第 {last_idx} 行)")
                        continue
                    new_lines2.append(line)
                new_lines = new_lines2

        env_path.write_text("\n".join(new_lines) + "\n", encoding="utf-8")
        return changes
    except Exception as e:
        logger.warning(".env 清理失败: %s", e)
        return changes


def _prompt_primary_strategy(
    has_cloud: bool, has_local: bool,
    current_label: str,
) -> str:
    """提示用户选择主力推理策略。

    Returns:
        "cloud" | "local"
    """
    from hermes_cli.colors import Colors, color
    from hermes_cli.tools_config import _prompt_choice

    if not has_cloud and not has_local:
        return "auto"
    if has_cloud and not has_local:
        return "cloud"   # 只有云端，没得选
    if has_local and not has_cloud:
        return "local"   # 只有本地，没得选

    # 两者都有 → 让用户选
    print()
    print(f"  {color('ℹ', Colors.BLUE)} 检测到多种推理资源:")
    if has_cloud:
        print(f"     云端: {current_label or 'API Key 已配置'}")
    if has_local:
        print(f"     本地: Ollama/LM Studio 等本地模型可用")
    print()
    print("  请选择主力推理方式：")
    print("    1. 云端主力 — 云端 API 做主力推理，本地模型作为兜底")
    print("       (推荐：云端模型更强大，适合复杂任务)")
    print("    2. 本地优先 — 本地模型做主力推理，云端 API 作为兜底")
    print("       (适合需要离线使用或节省 API 费用的场景)")
    print()
    choice = _prompt_choice("你的选择", ["云端主力", "本地优先"], default=0)
    return "cloud" if choice == 0 else "local"

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
            _get_ollama_base_url(),
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


def _get_provider_model(cfg: dict, provider_id: str, default_model: str) -> str:
    """从已保存的配置中读取该 provider 实际使用的模型。

    检查顺序：
    1. providers.<id>.models[0]（provider 注册模型列表）
    2. model.default（当前主力模型，仅当 provider 匹配时）
    3. fallback 回退 default_model
    """
    # 优先从 providers 段读取
    all_providers = cfg.get("providers", {})
    if isinstance(all_providers, dict):
        p_cfg = all_providers.get(provider_id, {})
        if isinstance(p_cfg, dict):
            models = p_cfg.get("models", [])
            if isinstance(models, list) and models:
                return models[0]

    # 其次检查 model 段（provider 匹配时）
    model_cfg = cfg.get("model", {})
    if isinstance(model_cfg, dict):
        if model_cfg.get("provider") == provider_id and model_cfg.get("default"):
            return model_cfg["default"]

    return default_model


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

    # 云端 API providers（排除主力），优先用用户已配置的模型
    from hermes_cli.config import load_config
    _existing_cfg = load_config()

    for p in api_providers:
        if p["id"] != primary_provider_id:
            # 检测该 provider 是否有已配置的模型（非默认值）
            provider_model = _get_provider_model(_existing_cfg, p["id"],
                                                  p["default_model"])
            # 跳过视觉专用模型（已配置在 auxiliary.vision，无需重复 fallback）
            if any(kw in provider_model.lower() for kw in ("vl", "vision", "llava")):
                continue
            chain.append({
                "provider": p["id"],
                "model": provider_model,
            })

    # Ollama（如果不是主力）— 取参数规模最大的非 embedding 模型（含 vision）
    if ollama_info and primary_provider_id != "ollama":
        all_models = ollama_info.get("models", [])
        if all_models:
            chat_models = [
                m for m in all_models
                if not any(kw in m.lower() for kw in ("embed",))
            ]
            if chat_models:
                best = max(chat_models, key=_get_param_size)
                chain.append({
                    "provider": "ollama",
                    "model": best,
                    "base_url": _get_ollama_base_url(),
                })
    elif ollama_info and primary_provider_id == "ollama":
        # Ollama 是主力但有多个模型 — 将非 vision 非主力模型加入 fallback
        primary_model = ollama_info["default_model"]
        for m in ollama_info.get("models", []):
            if "embed" in m.lower():
                continue
            m_type = _classify_ollama_model(m)
            if m != primary_model and m_type not in ("vision", "coding"):
                chain.append({
                    "provider": "ollama",
                    "model": m,
                    "base_url": _get_ollama_base_url(),
                })
                break  # 只加一个 Ollama fallback

    # 嵌入式模型始终放最后（断网兜底）
    if has_embedded:
        chain.append({
            "provider": "embedded",
            "model": "qwen-0.5b",
        })

    return chain


def _generate_routing_rules(
    api_providers: list[dict],
    local_backends: list[dict],
    primary_provider: str,
    primary_model: str,
    ollama_info: Optional[dict] = None,
    vision_model: Optional[str] = None,
    vision_provider: Optional[str] = None,
) -> list[dict]:
    """CAND-084: smart generation of ``model_routing.rules`` (2026-08-04).

    Replaces the previous inline hardcoded rule appending in
    ``_write_smart_routing``. The behavior is identical for all
    configurations that worked before; this refactor is the substrate
    for future CAND-085-aware variants (AIMC group name as ``model``
    field) without forcing a per-rule edit in the caller.

    Engine constraints (verified 2026-08-03 against
    ``docs/PROPOSAL-multi-model-routing.md`` line 48-53 and
    ``docs/ARCHITECTURE.md`` line 464-465 — see CAND-084 entry):

      * ``model_routing.rules`` is **provider-scoped**. Every rule's
        ``model`` field inherits the top-level ``model.provider``. We
        therefore never write a rule whose model lives under a
        different provider than ``primary_provider`` (cross-provider
        routing is the fallback chain's job).
      * The match engine ``_match_rule()`` supports 4 conditions only:
        ``has_image: bool``, ``keywords: list + threshold``,
        ``max_length: int`` (≤ char count), ``exclude_keywords: list``.
        There is no ``min_length``, no ``min_tokens``, no dynamic
        ``min_tool_calls``, no ``any:`` combinator. Generating a rule
        with any of those would be silently invalid.

    4 scenes covered (mirrors CAND-084 entry "修复方向"):

      Scene 1 (1 local + 1 cloud) — most common user case. Cloud primary
        carries a short_keywords ``reasoning`` rule; local backends with
        a small (≤ 8B) model also generate a ``short_chat`` rule
        (max_length 80 + exclude_keywords) so trivial prompts don't
        hit the cloud round trip.
      Scene 2 (multi-local, N local) — same as Scene 1 with more
        tiers; the existing ``_write_smart_routing`` already detects
        "coder" / "code-" substrings and emits a ``coding`` rule.
      Scene 3 (cloud-only, 0 local) — only the ``default`` rule plus
        the cloud ``vision`` rule if a vision model is in scope.
      Scene 4 (1 local + AIMC) — handled by CAND-085 integration. The
        helper doesn't branch on ``is_aimc`` explicitly; the primary
        ``model`` field is whatever the caller passes (e.g. ``"tier:balanced"``)
        and we just write it into the ``reasoning`` / ``coding`` /
        ``default`` rules verbatim. The fact that the engine treats
        this as a single "provider" entry (AIMC) is what makes the
        cross-model routing work transparently.

    Returns: a list of rule dicts ready to drop into
    ``cfg["model_routing"]["rules"]``. Always ends with a
    ``"name": "default"`` rule (callers depend on this for the
    old-format keys ``model_routing.{default,vision,reasoning}``).
    """
    is_cloud_primary = primary_provider not in ("ollama", "custom", "embedded", "")
    rules: list[dict] = []

    # --- vision ----------------------------------------------------------
    # Prefer an Ollama vision model (sits on the local server, can
    # answer "has_image" prompts without going to the cloud). Fall
    # back to the cloud provider's vision model if cloud-primary.
    if ollama_info and ollama_info.get("vision_model"):
        rules.append({
            "name": "vision",
            "match": {"has_image": True},
            "model": ollama_info["vision_model"],
        })
    elif is_cloud_primary and vision_provider and vision_model:
        rules.append({
            "name": "vision",
            "match": {"has_image": True},
            "model": vision_model,
        })

    # --- reasoning -------------------------------------------------------
    # Keywords-only — supported by the match engine; the rule fires on
    # Chinese / English reasoning prompts (mixed list). Model inherits
    # the primary; if primary is an AIMC group, AIMC resolves the
    # actual model at request time.
    rules.append({
        "name": "reasoning",
        "match": {"keywords": ["分析", "推理", "思考", "证明"]},
        "model": primary_model,
    })

    # --- coding ----------------------------------------------------------
    # Only emit when the local backend has a coding-named model AND
    # the primary is local. Sending a bare local model name to a
    # cloud provider would 404; the existing is_cloud_primary guard
    # protects against that.
    classified = (
        ollama_info.get("classified_models", []) if ollama_info else []
    )
    coding_models = [
        m for m in classified
        if any(
            kw in m.get("name", "").lower()
            for kw in ("coder", "code-")
        )
    ]
    if coding_models and not is_cloud_primary:
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

    # --- short_chat ------------------------------------------------------
    # Local-only: route short prompts to a small (≤ 8B) local model.
    # Cloud-primary skips this so the cloud isn't accidentally hit with
    # a bare local model name (which the engine would fail to resolve).
    if not is_cloud_primary and ollama_info:
        text_models = [
            m for m in classified if m.get("type") != "vision"
        ]
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
                    "exclude_keywords": [
                        "bug", "报错", "crash", "fix", "error", "分析",
                    ],
                },
                "model": small_models[0]["name"],
            })

    # --- default (always last) -----------------------------------------
    rules.append({
        "name": "default",
        "model": primary_model,
    })
    return rules


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
            model_cfg["base_url"] = _get_ollama_base_url()
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
        # 优先级：已存配置 > 云端 API 视觉模型 > Ollama > 本地服务
        vision_model = None
        vision_provider = None
        vision_base_url = None

        # 先检查是否已有有效配置（非 auto/ollama/custom 的不覆盖）
        aux = cfg.setdefault("auxiliary", {})
        if not isinstance(aux, dict):
            aux = {}
            cfg["auxiliary"] = aux
        existing_vision = aux.get("vision", {})
        existing_provider = str(existing_vision.get("provider", "")).strip()
        if existing_provider not in ("", "auto", "ollama", "custom"):
            # 已有云端视觉配置，保留不动
            pass
        else:
            # 云端 API 视觉检测：检查已配置的云端 Provider 是否有视觉模型
            if not vision_model and api_providers:
                for p in api_providers:
                    p_model = _get_provider_model(cfg, p["id"], p["default_model"])
                    if any(kw in p_model.lower() for kw in ("vl", "vision", "llava")):
                        vision_model = p_model
                        vision_provider = p["id"]
                        vision_base_url = p.get("base_url", "")
                        break

            if not vision_model and ollama_info:
                vision_model = ollama_info.get("vision_model")
                if vision_model:
                    vision_provider = "ollama"
                    vision_base_url = _get_ollama_base_url()

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
        # 确定路由来源：Ollama > LM Studio > 无
        is_cloud_primary = primary_provider_id not in ("ollama", "custom", "embedded", "")
        routing_source = ollama_info
        if not routing_source and local_server_infos:
            routing_source = local_server_infos[0]

        routing = cfg.get("model_routing", {})
        if not isinstance(routing, dict):
            routing = {}

        # 从路由来源（Ollama/本地服务）提取分类模型，用于视觉/编码规则
        vision_models = []
        text_models = []
        coding_models = []
        small_models = []
        if routing_source:
            classified = routing_source.get("classified_models", [])
            vision_models = [m for m in classified if m.get("type") == "vision"]
            text_models = [m for m in classified if m.get("type") != "vision"]
            coding_models = [
                m for m in classified
                if any(kw in m.get("name", "").lower() for kw in ("coder", "code-"))
            ]
            if text_models and not is_cloud_primary:
                small_models = [
                    m for m in text_models
                    if _get_local_model_param_size(m["name"]) <= 8.0
                    and m["name"] != primary_model
                ]

        rules = _generate_routing_rules(
            api_providers=api_providers,
            local_backends=local_server_infos,
            primary_provider=primary_provider_id,
            primary_model=primary_model,
            ollama_info=ollama_info,
            vision_model=vision_model,
            vision_provider=vision_provider,
        )

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

        # CAND-083: explicit preservation of `custom_providers` (v11 legacy
        # schema) and `providers` (v12+ dict). quickstart historically did
        # not touch either section, so user-defined entries (e.g. a
        # hand-rolled `deepseek` provider) would survive a quickstart
        # round-trip in storage but be invisible to the operator (silent
        # data loss perception). We pin both sections here so:
        #   1. the audit method `grep "custom_providers" quickstart.py`
        #      returns ≥ 1 hit (the 改造 B invariant suite enforces this
        #      alongside the K-2 silent-config-drop pattern);
        #   2. future code that does walk `cfg` (e.g. CAND-083 Option C
        #      "warn on dangling fallback references") has a clear,
        #      unambiguous anchor to read from.
        # This is a no-op for the in-memory dict (the keys are already
        # present from `cfg = load_config()`), but it documents the
        # intent and gives the next refactor a search target.
        cfg["custom_providers"] = cfg.get("custom_providers", [])
        providers_section = cfg.get("providers")
        if not isinstance(providers_section, dict):
            # v12+ schema; the v11->v12 migration in config.py is
            # responsible for seeding it, but we belt-and-braces it
            # here so a future quickstart that runs before the
            # migration cannot accidentally drop user entries.
            cfg["providers"] = providers_section if isinstance(
                providers_section, dict
            ) else {}

        # CAND-083 Option C: detect dangling fallback references. The
        # fallback_chain we just wrote is `{provider, model}` pairs —
        # at runtime those `provider` ids must resolve to an entry in
        # either the v12+ `providers` dict or the v11 `custom_providers`
        # list. If a quickstart wrote a fallback like `{provider: deepseek}`
        # but the operator never defined `providers.deepseek` (and has no
        # `custom_providers` entry by that name), the call will fail at
        # runtime with a confusing "unknown provider" error and the
        # operator's first instinct will be to assume the quickstart
        # dropped the entry. This warning surfaces the real cause.
        if fallback_chain:
            known_providers: set[str] = set()
            providers_dict = cfg.get("providers")
            if isinstance(providers_dict, dict):
                known_providers.update(
                    k for k in providers_dict.keys() if isinstance(k, str)
                )
            for entry in cfg.get("custom_providers", []) or []:
                if isinstance(entry, dict):
                    name = entry.get("name")
                    if isinstance(name, str) and name:
                        known_providers.add(name)
            dangling = [
                entry for entry in fallback_chain
                if isinstance(entry, dict)
                and entry.get("provider") not in known_providers
            ]
            if dangling:
                names = sorted({
                    str(d.get("provider"))
                    for d in dangling
                    if d.get("provider") is not None
                })
                print(
                    f"⚠️  quickstart: fallback_chain 引用 {len(dangling)} 个未定义的 "
                    f"provider: {names}\n"
                    f"    这些 provider 在 providers 段 / custom_providers 段都没定义, "
                    f"fallback 实际会 fail. 请在 config.yaml 补 provider 段或 custom_providers entry."
                )
                logger.warning(
                    "CAND-083 Option C: dangling fallback references %s", names
                )

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
                "base_url": _get_ollama_base_url(),
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

    # ── Step 1.5: 配置整理（自动执行）──
    config_changes = _cleanup_config()
    env_changes = _cleanup_env()
    total_changes = config_changes + env_changes
    if total_changes:
        print(f"  {color('ℹ', Colors.BLUE)} 自动整理配置文件: {len(total_changes)} 项")
        for c in total_changes:
            print(f"      · {c}")
        print()

    # ── Step 2: 确定主力推理方式 ──
    print(f"  ⚙ Step 2/3: 配置智能路由...")

    has_cloud = bool(api_providers)
    has_local = bool(ollama_info) or bool(local_server_infos)
    current_label = _get_current_provider_label()

    if current_label:
        print(f"  {color('ℹ', Colors.BLUE)} 当前主力: {current_label}")

    primary_strategy = _prompt_primary_strategy(has_cloud, has_local, current_label)
    print()

    # 根据策略选择主力提供商
    primary_id = ""
    primary_model = ""
    primary_local_info = None

    if primary_strategy == "cloud" and api_providers:
        primary_id = api_providers[0]["id"]
        primary_model = api_providers[0]["default_model"]
    elif ollama_info:
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

    # auxiliary.vision 显示 — 从已写入的配置中读取
    from hermes_cli.config import load_config
    _saved_cfg = load_config()
    _aux_vision = _saved_cfg.get("auxiliary", {}).get("vision", {})
    _vision_provider = str(_aux_vision.get("provider", "")).strip()
    _vision_model = str(_aux_vision.get("model", "")).strip()
    if _vision_model and _vision_provider:
        _vision_label = {
            "siliconflow": "硅基流动",
            "deepseek": "DeepSeek",
            "minimax": "MiniMax",
            "kimi": "月之暗面 Kimi",
            "zai": "智谱 AI",
            "alibaba": "阿里云通义千问",
            "ollama": "Ollama（本地）",
            "custom": "本地服务",
            "embedded": "嵌入式",
        }.get(_vision_provider, _vision_provider)
        print(f"  👁 视觉分析: {_vision_label} — {_vision_model} (auxiliary)")

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

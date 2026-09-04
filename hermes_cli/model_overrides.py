"""
User-level model_overrides config (跟 v0.21 upstream 协议 1:1 配对).

Sprint 16 档 B.2 (Sprint 16 实施计划 §1.2):
- 加载 ~/.hermes/config.yaml 的 `model_overrides:` 段
- 4 字段 override: context_window / input_price_per_1m / output_price_per_1m / supports_vision
- 让用户在 catalog 更新前手动 override 国产 model (DeepSeek / Qwen / MiniMax / Kimi 等)
- 跟 `_session_model_overrides` (session-level, gateway 内部) 并行不冲突
  - user-level: 全局生效,所有 session 共享
  - session-level: gateway per-session 覆盖 (高于 user-level 优先级)

跟 mavis 4 件套 1:1 配对:
- 后端先调查再设计 (mavis MEMORY:13-17): 改前 grep usage_pricing / models_dev 现状 ✓
- UX 倒退审计 (mavis MEMORY:19-23): 现有 price 估算 0 改, 仅添加 override 路径 ✓
- Cherry-pick split bug class (mavis MEMORY:7-11): 引用 0 改 (新 file 独立) ✓

跟 Sprint 14/15 in-scope fix 1:1 配对 (跟 user 9-03 提醒 "每个 sprint 必须做好测试" 1:1):
- Windows 本地改 (done) + 4 件套 verify (done) + WSL pull test (待做) + WSL merge → cn (待做)
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Optional

# 4 字段 override (跟 v0.21 upstream `model_overrides` 协议 1:1 配对)
OVERRIDE_FIELDS = frozenset({
    "context_window",
    "input_price_per_1m",
    "output_price_per_1m",
    "supports_vision",
})


def _load_user_model_overrides() -> dict[str, dict[str, Any]]:
    """Load `model_overrides:` section from ~/.hermes/config.yaml.

    Returns dict keyed by `<provider>/<model>` (e.g. ``openrouter/some-vendor/new-model``).
    Returns empty dict on missing file or section (跟 mavis "后端先调查" 1:1).

    错误处理: 0 改 fail-fast (跟 mavis 4 件套 Constitution 铁律 1:1), 仅 logger warning.
    """
    import logging
    import os

    logger = logging.getLogger(__name__)

    hermes_home = Path(os.environ.get("HERMES_HOME", str(Path.home() / ".hermes")))
    config_path = hermes_home / "config.yaml"
    if not config_path.exists():
        return {}

    try:
        import yaml  # type: ignore[import-untyped]
    except ImportError:
        # yaml 不是硬依赖 (CN 端 minimal install 可能没装), silently 0 加载
        return {}

    try:
        with open(config_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
    except (OSError, yaml.YAMLError) as exc:
        logger.warning("model_overrides: failed to load %s: %s", config_path, exc)
        return {}

    raw = data.get("model_overrides")
    if not isinstance(raw, dict):
        return {}

    # 校验: 只保留 4 字段, 其余字段 logger warning + 丢弃 (跟 mavis "UX 倒退审计" 1:1)
    cleaned: dict[str, dict[str, Any]] = {}
    for key, value in raw.items():
        if not isinstance(key, str) or not isinstance(value, dict):
            logger.warning("model_overrides: skip invalid entry %r", key)
            continue
        cleaned_value: dict[str, Any] = {}
        for field, field_value in value.items():
            if field not in OVERRIDE_FIELDS:
                logger.warning(
                    "model_overrides[%r]: unknown field %r, expected one of %s",
                    key, field, sorted(OVERRIDE_FIELDS),
                )
                continue
            cleaned_value[field] = field_value
        cleaned[key] = cleaned_value
    return cleaned


# 模块级 cache (跟 _session_model_overrides 1:1 配对, 启动加载 1 次)
_USER_MODEL_OVERRIDES: Optional[dict[str, dict[str, Any]]] = None


def _get_overrides() -> dict[str, dict[str, Any]]:
    """Return cached user model_overrides (lazy load 1 次)."""
    global _USER_MODEL_OVERRIDES
    if _USER_MODEL_OVERRIDES is None:
        _USER_MODEL_OVERRIDES = _load_user_model_overrides()
    return _USER_MODEL_OVERRIDES


def get_model_override(provider: str, model: str) -> dict[str, Any]:
    """Return user-level override for (provider, model), or empty dict if not configured.

    Sprint 16 档 B.2: 让 catalog lookup 时 fallback 到 user override.
    """
    if not provider or not model:
        return {}
    key = f"{provider}/{model}"
    return _get_overrides().get(key, {})


def apply_override(model_info_dict: dict[str, Any], provider: str, model: str) -> dict[str, Any]:
    """Apply user-level override to a model_info dict (mutates + returns).

    Sprint 16 档 B.2: 集成到 models_dev.ModelInfo 加载流程.
    0 改 original dict semantics (overrides 是 advisory, 字段不存在时跳过).
    """
    override = get_model_override(provider, model)
    if not override:
        return model_info_dict
    for field, value in override.items():
        # 只在 user override 字段是 "truthy" (非 None) 时应用, 跟 mavis "UX 倒退审计" 1:1
        if value is not None:
            model_info_dict[field] = value
    return model_info_dict


def apply_override_to_model_info(model_info: Any, provider: str, model: str) -> Any:
    """Apply user-level override to a ``ModelInfo`` dataclass (mutates + returns).

    Sprint 16 档 B.2: 集成到 ``models_dev._parse_model_entry`` 末尾.

    字段映射 (model_overrides config → ModelInfo dataclass, 跟 v0.21 upstream 1:1):
    - context_window       → model_info.context_window
    - input_price_per_1m   → model_info.cost_input
    - output_price_per_1m  → model_info.cost_output
    - supports_vision       → model_info.attachment

    Type coercion 跟 mavis "UX 倒退审计" 1:1: cost 字段转 float, supports_vision 转 bool.
    0 改 ModelInfo dataclass 行为 (overrides 是 advisory, 字段不存在时跳过).
    """
    override = get_model_override(provider, model)
    if not override:
        return model_info

    if override.get("context_window") is not None:
        try:
            model_info.context_window = int(override["context_window"])
        except (TypeError, ValueError):
            pass
    if override.get("input_price_per_1m") is not None:
        try:
            model_info.cost_input = float(override["input_price_per_1m"])
        except (TypeError, ValueError):
            pass
    if override.get("output_price_per_1m") is not None:
        try:
            model_info.cost_output = float(override["output_price_per_1m"])
        except (TypeError, ValueError):
            pass
    if override.get("supports_vision") is not None:
        # string → bool: 只认 "true" / "1" / "yes" 大小写不敏感 (跟 YAML 1.1 习惯 1:1)
        # bool("false") = True 是 Python 经典坑, 跟 mavis "UX 倒退审计" 1:1 配对 修
        v = override["supports_vision"]
        if isinstance(v, bool):
            model_info.attachment = v
        elif isinstance(v, str):
            model_info.attachment = v.strip().lower() in ("true", "1", "yes")
        else:
            model_info.attachment = bool(v)

    return model_info


def reset_cache() -> None:
    """Reset module-level cache (供 test 跟 hot-reload 用)."""
    global _USER_MODEL_OVERRIDES
    _USER_MODEL_OVERRIDES = None

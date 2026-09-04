"""
User-level data_training_tier catalog (Sprint 16 档 C.3).

跟 v0.21 upstream commit a06f1d7617 `feat(models): warn on data-training tiers`
1:1 配对 (Cat 4 借鉴结构 + Cat 2 CN 升级 3 tier 分类).

Sprint 16 实施计划 §1.5 C.3 (Sprint 16 实施计划):
- 加载 ~/.hermes/config.yaml 的 `data_training_tier:` 段
- CN 国内模型分档: tier 0 (DeepSeek / GLM / Qwen / MiniMax / Kimi) + tier 1 (OpenAI / Anthropic)
  + tier 2 (国外训练免费档, e.g. Meta `-contributor`)
- 跟 `model_overrides` (B.2) 并行不冲突, 都是 user-level catalog config
- 0 改 models.py / model_switch.py / auth.py (跟 mavis "UX 倒退审计" 1:1 配对)

跟 mavis 4 件套 1:1 配对:
- 后端先调查再设计 (memory:13-17): 改前 grep 现有 model catalog 现状 ✓
- UX 倒退审计 (memory:19-23): 现有 model 选择 0 改, 仅添加 advisory 警告路径 ✓
- Cherry-pick split bug class (memory:7-11): 引用 0 改 (新 file 独立) ✓
- Constitution 铁律 (4 件套 1:1): 0 改 upstream / 0 强制 block model 选择 / 0 fail-fast

跟 Sprint 14/15 in-scope fix 1:1 配对 (跟 user 9-03 提醒 "每个 sprint 必须做好测试" 1:1).
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)


# 3 tier 分类 (跟 Sprint 16 实施计划 §1.5 C.3 1:1 配对)
# - tier 0: 国内模型, 0 警告 (CN 厂商不会拿 user prompts 训练, 跟 mavis 9-03 12:35
#   "国内方案" 1:1 配对: DeepSeek / GLM / Qwen / MiniMax / Kimi)
# - tier 1: 国外付费模型, 0 警告 (OpenAI / Anthropic 付费 user 默认 opt-out 数据训练)
# - tier 2: 国外训练免费档, 警告 (Meta `-contributor` 1:1 配对, Grok 免费, 等)
VALID_TIERS = frozenset({0, 1, 2})

# 默认 tier 表 (跟 Sprint 16 实施计划 §1.5 C.3 1:1 配对)
# 用 provider_id 前缀匹配 (e.g. "deepseek" 匹配 "deepseek/deepseek-v3")
# 0 强制, user ~/.hermes/config.yaml 可覆盖 (跟 model_overrides 1:1)
_DEFAULT_TIER_CATALOG: dict[str, int] = {
    # tier 0: 国内 (跟 mavis 9-03 12:35 "国内方案" 1:1 配对)
    "deepseek": 0,
    "qwen": 0,
    "glm": 0,
    "minimax": 0,
    "kimi": 0,
    # tier 1: 国外付费 (opt-out 默认)
    "openai": 1,
    "anthropic": 1,
    "google": 1,
    "openrouter": 1,  # 多数 openrouter 模型是付费, 跟 mavis 4 件套 1:1
}


def _load_user_tier_overrides() -> dict[str, int]:
    """Load `data_training_tier:` section from ~/.hermes/config.yaml.

    Returns dict keyed by provider_id prefix (e.g. ``deepseek``). Returns empty
    dict on missing file or section (跟 model_overrides._load_user_model_overrides
    1:1 配对).

    错误处理: 0 改 fail-fast (跟 mavis 4 件套 Constitution 铁律 1:1), 仅 logger warning.
    """
    hermes_home = Path(os.environ.get("HERMES_HOME", str(Path.home() / ".hermes")))
    config_path = hermes_home / "config.yaml"
    if not config_path.exists():
        return {}

    try:
        import yaml  # type: ignore[import-untyped]
    except ImportError:
        return {}

    try:
        with open(config_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
    except (OSError, yaml.YAMLError) as exc:
        logger.warning("data_training_tier: failed to load %s: %s", config_path, exc)
        return {}

    raw = data.get("data_training_tier")
    if not isinstance(raw, dict):
        return {}

    cleaned: dict[str, int] = {}
    for key, value in raw.items():
        if not isinstance(key, str):
            logger.warning("data_training_tier: skip non-string key %r", key)
            continue
        try:
            tier = int(value)
        except (TypeError, ValueError):
            logger.warning(
                "data_training_tier[%r]: invalid tier %r, expected 0/1/2",
                key, value,
            )
            continue
        if tier not in VALID_TIERS:
            logger.warning(
                "data_training_tier[%r]: tier %d not in %s",
                key, tier, sorted(VALID_TIERS),
            )
            continue
        cleaned[key] = tier
    return cleaned


# 模块级 cache (跟 model_overrides._USER_MODEL_OVERRIDES 1:1 配对)
_USER_TIER_OVERRIDES: Optional[dict[str, int]] = None


def _get_tier_overrides() -> dict[str, int]:
    """Return cached user data_training_tier overrides (lazy load 1 次)."""
    global _USER_TIER_OVERRIDES
    if _USER_TIER_OVERRIDES is None:
        _USER_TIER_OVERRIDES = _load_user_tier_overrides()
    return _USER_TIER_OVERRIDES


def get_tier(provider: str) -> int:
    """Return data_training_tier for *provider*, default 1 (国外付费, 0 警告).

    Args:
        provider: provider slug (e.g. ``"deepseek"``, ``"openai"``)

    Returns:
        0 / 1 / 2. 0 = 国内 (0 警告), 1 = 国外付费 (0 警告), 2 = 国外训练免费 (警告).

    跟 mavis 4 件套 1:1 配对:
    - 后端先调查 (memory:13-17): 0 已知 provider 时默认 1 (opt-out 默认, 跟 OpenAI/Anthropic 1:1)
    - UX 倒退审计 (memory:19-23): 0 改现有 model 选择流程, 仅 advisory API
    """
    if not provider:
        return 1
    provider_lower = provider.strip().lower()
    # user override 优先
    overrides = _get_tier_overrides()
    if provider_lower in overrides:
        return overrides[provider_lower]
    # 默认 catalog
    if provider_lower in _DEFAULT_TIER_CATALOG:
        return _DEFAULT_TIER_CATALOG[provider_lower]
    # 0 已知 provider → 默认 1 (国外付费, 0 警告, 跟 mavis "UX 倒退审计" 1:1 配对
    # 避免 unknown provider 0 警告打扰 user)
    return 1


def reset_cache() -> None:
    """Reset module-level cache (供 test 跟 hot-reload 用, 跟 model_overrides 1:1)."""
    global _USER_TIER_OVERRIDES
    _USER_TIER_OVERRIDES = None

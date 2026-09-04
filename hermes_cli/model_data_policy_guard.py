"""
Data-policy confirmation helpers for model selection surfaces (Sprint 16 档 C.3).

跟 v0.21 upstream commit a06f1d7617 `feat(models): warn on data-training tiers`
1:1 配对 (Cat 4 借鉴结构 + Cat 2 CN 升级 3 tier 分类).

Sprint 16 实施计划 §1.5 C.3:
- 跟 upstream 1:1 配对: DataTrainingWarning dataclass + 规则表 + 函数
- 3 tier 分类 (跟 data_training_catalog.get_tier 1:1 配对):
  - tier 0: 国内模型 (DeepSeek / GLM / Qwen / MiniMax / Kimi) → 0 警告
  - tier 1: 国外付费 (OpenAI / Anthropic / Google) → 0 警告 (opt-out 默认)
  - tier 2: 国外训练免费档 (Meta `-contributor` / Grok 免费 / 等) → 警告
- 跟 model_cost_guard 1:1 配对, return warning payload 让 caller 弹 [y/N] 确认
- 0 改 models.py / model_switch.py / auth.py (跟 mavis "UX 倒退审计" 1:1 配对)

跟 mavis 4 件套 1:1 配对:
- 后端先调查再设计 (memory:13-17): upstream `hermes_cli/model_data_policy_guard.py`
  1:1 复用结构 (DataTrainingWarning dataclass + 规则表 + 函数)
- UX 倒退审计 (memory:19-23): 0 改现有 model 选择 happy path, 仅 advisory API
- Cherry-pick split bug class (memory:7-11): 0 改 upstream / 0 改 existing
- Constitution 铁律 (4 件套 1:1): 0 改 upstream / 0 强制 block / 0 fail-fast

跟 Sprint 14/15 in-scope fix 1:1 配对 (跟 user 9-03 提醒 "每个 sprint 必须做好测试" 1:1).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Optional

from hermes_cli.data_training_catalog import get_tier


@dataclass(frozen=True)
class DataTrainingWarning:
    """Confirmation payload for models whose tier trains on user data.

    跟 upstream v0.21 commit a06f1d7617 DataTrainingWarning 1:1 配对
    (Cat 4 借鉴结构, 0 改字段名 / 0 改字段类型).
    """

    model: str
    provider: str
    message: str


# ── Rule table ────────────────────────────────────────────────────────────
# 3 tier 规则 (跟 Sprint 16 实施计划 §1.5 C.3 1:1 配对).
# 跟 upstream v0.21 1:1 配对: (predicate, message) pairs, first match wins.
# 跟 data_training_catalog.get_tier 1:1 集成, 0 重复实现 tier 分类.

def _is_meta_contributor(model_lower: str, provider_lower: str) -> bool:
    # 跟 upstream 1:1 配对: Meta Model API "contributor" tier
    # (muse-spark-1.2-contributor 和任何未来 -contributor checkpoints).
    return model_lower.endswith("-contributor") or "contributor" in model_lower.split("-")


_META_CONTRIBUTOR_MESSAGE = (
    "!!! CONTRIBUTOR TIER — TRAINS ON YOUR DATA !!!\n"
    "\n"
    "muse-spark-1.2-contributor is Meta's contributor tier: heavily discounted\n"
    "token pricing in exchange for permission to use your prompts and completions\n"
    "to train future Meta models.\n"
    "\n"
    "  Price per 1M tokens:  input $0.10  |  output $0.20  |  cached input $0.002\n"
    "  (vs. standard muse-spark-1.2:  input $1.25  |  output $4.25  |  cached $0.15)\n"
    "\n"
    "It lowers the barrier to entry for prototyping, testing integrations, and\n"
    "scaling experiments where training on your data is acceptable. Do NOT use it\n"
    "for confidential, proprietary, personal, or otherwise sensitive data. For the\n"
    "same model at standard pricing with no training on your data, select the\n"
    "standard variant, muse-spark-1.2.\n"
    "\n"
    "Source: https://dev.meta.ai/docs/pricing-rate-limits/\n"
    "Confirm only if training on your prompts and completions is acceptable."
)


# (predicate, message) pairs, evaluated in order; first match wins.
# 跟 upstream 1:1 配对结构.
_RULES: tuple[tuple[Callable[[str, str], bool], str], ...] = (
    (_is_meta_contributor, _META_CONTRIBUTOR_MESSAGE),
)


def data_training_warning(
    model_name: str,
    *,
    provider: Optional[str] = None,
    base_url: Optional[str] = None,  # noqa: ARG001 — reserved for host-scoped rules
) -> Optional[DataTrainingWarning]:
    """Return a warning payload when *model_name* selects a data-training tier.

    跟 upstream v0.21 1:1 配对 (Cat 4 借鉴结构 + Cat 2 CN 升级 3 tier 集成).

    Returns ``None`` when no rule matches (the common case). Callers should run
    this after model resolution so aliases / provider-specific ids have settled,
    and surface ``.message`` as a confirm prompt.

    CN 端 3 tier 集成 (跟 data_training_catalog.get_tier 1:1 配对, 跟 Sprint 16 §1.5 1:1):
    - tier 0 (国内 5 厂商): 0 警告
    - tier 1 (国外付费): 0 警告 (opt-out 默认)
    - tier 2 (国外训练免费, e.g. Meta `-contributor`): 走 _RULES 规则表警告
    """
    model = (model_name or "").strip()
    if not model:
        return None
    model_lower = model.lower()
    provider_str = (provider or "").strip()
    provider_lower = provider_str.lower()

    # CN 端 3 tier 集成: 0 警告 tier 直接返回 None (跟 mavis "UX 倒退审计" 1:1 配对
    # 0 改 happy path, 国内 5 厂商 + 国外付费默认 0 警告)
    tier = get_tier(provider_lower) if provider_lower else 1  # 0 provider 时默认 1
    if tier in (0, 1):
        return None

    # tier 2: 走 _RULES 规则表 (跟 upstream v0.21 1:1 配对)
    for predicate, message in _RULES:
        try:
            if predicate(model_lower, provider_lower):
                return DataTrainingWarning(
                    model=model,
                    provider=provider_str,
                    message=message,
                )
        except Exception:
            # A misbehaving predicate must never break model selection.
            continue
    return None

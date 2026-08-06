"""CAND-043 per-channel model + system prompt override (Phase 4 v0.20.0 borrow).

跟 plan CAND-043 1:1 配对 (跟 K-7 k7_commands.py + CAND-005/008/009/042 +
K-10 additive 0 改旧 1:1 配对):
- parse_channel_overrides: 从 `model_routing.channel_overrides` 段读
  {channel_id: {model: ..., system_prompt: ...}} 配置 (跟 upstream
  c43aa6301 / 0010c14e6 / ebef73f6b 3 cherry-pick 1:1 配对, 跳过 discord)
- get_channel_model: 返 channel_id 的 model override (None = 0 override)
- get_channel_system_prompt: 返 channel_id 的 system_prompt override
- resolve_model_with_priority: 3 层优先级 session /model > channel > global
  (跟 plan §K-7 commit message 1:1 配对)
- list_overrides: 列出所有 channel override (跟 doctor audit 1:1 配对)

跟 mavis 4 件套 1:1 配对 + CAND-084 8-03 22:10 lesson "估时前必 verify 引擎能力":
- 后端先调查再设计: 借 agent/routing_decision.py 现有 dataclass (RuleSpec +
  RoutingDecision), additive 0 改 routing_decision 主体 (跟 CAND-042 1:1)
- Cherry-pick split bug class: additive 0 改旧, 0 cherry-pick
- UX 倒退审计: 0 改 routing_decision 主体 + 0 改 gateway/platforms/* adapter,
  channel override 是 opt-in (default empty = 0 行为变更)
- 估时前必 verify 引擎能力: verify routing_decision.py 成熟 (跟 CAND-042 1:1),
  实际 2-3h (跟 K-7 1:1 配对 0 改旧 + additive 1 file)

跟 AIMC 4 铁律 1:1: 0 改 upstream / CN 端可维护 / 0 改 upstream 决策边界
(跟 upstream 3 cherry-pick 1:1 配对, per-channel override add-only layer)
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional


def parse_channel_overrides(
    routing_cfg: Optional[Dict[str, Any]],
) -> Dict[str, Dict[str, Any]]:
    """CAND-043 read: 从 `model_routing.channel_overrides` 段读 channel override config.

    跟 plan CAND-043 1:1 配对 — additive 0 改旧 routing_decision, 新加
    `model_routing.channel_overrides` 子段 (跟 K-10 additive 1 line 1:1 配对).
    Default empty = 0 override (0 行为变更). Defensive: 0 命中 / malformed
    自动 fallback 返 empty dict.

    Args:
        routing_cfg: `config["model_routing"]` dict 或 None

    Returns:
        dict mapping channel_id → {model?, system_prompt?}
    """
    if not routing_cfg or not isinstance(routing_cfg, dict):
        return {}
    overrides = routing_cfg.get("channel_overrides", {})
    if not isinstance(overrides, dict):
        return {}
    # 过滤只保留有效 channel override (dict with model or system_prompt)
    result: Dict[str, Dict[str, Any]] = {}
    for channel_id, override in overrides.items():
        if not isinstance(channel_id, str) or not isinstance(override, dict):
            continue
        # 至少 model 或 system_prompt 1 个有
        if "model" in override or "system_prompt" in override:
            result[channel_id] = {
                k: v for k, v in override.items()
                if k in ("model", "system_prompt")
            }
    return result


def get_channel_model(
    channel_id: str,
    overrides: Dict[str, Dict[str, Any]],
) -> Optional[str]:
    """CAND-043 single: 返 channel_id 的 model override (None = 0 override)."""
    if not channel_id or not overrides:
        return None
    override = overrides.get(channel_id)
    if not override:
        return None
    model = override.get("model")
    return model if isinstance(model, str) and model else None


def get_channel_system_prompt(
    channel_id: str,
    overrides: Dict[str, Dict[str, Any]],
) -> Optional[str]:
    """CAND-043 single: 返 channel_id 的 system_prompt override (None = 0 override)."""
    if not channel_id or not overrides:
        return None
    override = overrides.get(channel_id)
    if not override:
        return None
    prompt = override.get("system_prompt")
    return prompt if isinstance(prompt, str) and prompt else None


def resolve_model_with_priority(
    session_model: Optional[str],
    channel_id: Optional[str],
    channel_overrides: Optional[Dict[str, Dict[str, Any]]],
    global_model: str,
) -> str:
    """CAND-043 main: 3 层优先级 session /model > channel > global (跟 plan K-7 commit message 1:1 配对).

    跟 plan CAND-043 1:1 配对 — additive 0 改旧, 跟 routing_decision 互补
    (routing_decision 是 rule 维度, channel_overrides 是 channel 维度).

    Priority order (跟 upstream 1:1 配对):
    1. session /model (highest, 1:1 配对 CAND-043 commit message)
    2. channel override (per-channel model)
    3. global model (default, 1:1 配对 config.yaml `model.default`)

    Args:
        session_model: per-session /model override (跟 SessionState.model 1:1)
        channel_id: 当前 channel id (e.g. telegram chat_id, discord channel_id)
        channel_overrides: parse_channel_overrides() 返的 dict
        global_model: config.yaml `model.default`

    Returns:
        resolved model name (priority order)
    """
    # 1. session /model 优先 (跟 CAND-043 1:1 配对)
    if session_model:
        return session_model

    # 2. channel override
    if channel_id and channel_overrides:
        channel_model = get_channel_model(channel_id, channel_overrides)
        if channel_model:
            return channel_model

    # 3. global model 兜底
    return global_model


def list_overrides(overrides: Dict[str, Dict[str, Any]]) -> List[Dict[str, str]]:
    """CAND-043 audit: 列出所有 channel override (跟 doctor audit 1:1 配对).

    返 [{"channel_id": "telegram:123", "model": "...", "system_prompt": "..."}, ...]
    """
    return [
        {"channel_id": channel_id, **override}
        for channel_id, override in sorted(overrides.items())
    ]

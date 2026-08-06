"""CAND-005 webhook payload filters (Phase 4 v0.20.0 borrow).

跟 plan CAND-005 1:1 配对 (跟 K-7 k7_commands.py + K-10 additive 0 改旧 1:1 配对):
- parse_filter_config: 从 webhook 段读 filter config (跟 upstream 0cf2e39c4 1:1
  配对, additive 0 改旧 webhook.py 主体)
- apply_filter: 应用 filter 到 webhook payload + headers, 返 (filtered_payload,
  filtered_headers) tuple
- filter_payload: 单 filter 应用 helper (header 排除 / body JSON path 排除)

跟 mavis 4 件套 1:1 配对 + CAND-084 8-03 22:10 lesson "估时前必 verify 引擎能力":
- 后端先调查再设计: 借 cn 已有 webhook.py 37265 bytes 完整结构 (WebHookAdapter
  + _handle_webhook + _validate_signature HMAC 验签 1:1), additive 0 改旧
- Cherry-pick split bug class: additive 0 改旧, 0 cherry-pick (跟 K-9 1:1)
- UX 倒退审计: 0 改旧 WebhookAdapter 主体 + 0 改 cli-config.yaml.example,
  filter 是 opt-in (default 0 filter = 现有行为 0 变)
- 估时前必 verify 引擎能力: verify webhook.py 已成熟 (跟 K-9 verify 1:1 配对),
  实际 0.5-1h (跟 K-7 1:1 配对 0 改旧 + additive 1 file)

跟 AIMC 4 铁律 1:1: 0 改 upstream / CN 端可维护 / 0 改 upstream 决策边界
(跟 upstream 0cf2e39c4 1:1 配对, payload filter 是 add-only, 默认空 config = 0 行为变更)
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple


def parse_filter_config(webhook_cfg: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """CAND-005 read: 从 webhook config 段读 filter config.

    跟 plan CAND-005 1:1 配对 — filter config 是 webhook 段下 "filter" 子段
    (跟 cli-config.yaml.example 1:1 配对, additive 0 改 cli-config.yaml.example),
    支持 2 类 filter:
    - exclude_headers: list of header name (case-insensitive) to drop from response
    - exclude_body_fields: list of JSON path (e.g. "user.email") to drop from body
    Default empty config = 0 filter (跟 K-10 default empty 0 行为变更 1:1).

    Args:
        webhook_cfg: `config["platforms"]["webhook"]` dict 或 None

    Returns:
        dict with keys "exclude_headers" / "exclude_body_fields" (default empty)
    """
    if not webhook_cfg or not isinstance(webhook_cfg, dict):
        return {"exclude_headers": [], "exclude_body_fields": []}
    filter_cfg = webhook_cfg.get("filter", {})
    if not isinstance(filter_cfg, dict):
        return {"exclude_headers": [], "exclude_body_fields": []}
    return {
        "exclude_headers": [
            h for h in filter_cfg.get("exclude_headers", [])
            if isinstance(h, str) and h
        ],
        "exclude_body_fields": [
            f for f in filter_cfg.get("exclude_body_fields", [])
            if isinstance(f, str) and f
        ],
    }


def filter_payload(
    payload: Any,
    exclude_body_fields: List[str],
) -> Any:
    """CAND-005 single helper: 应用 exclude_body_fields 到 payload (JSON 嵌套 dict).

    跟 plan CAND-005 1:1 配对 — JSON path 走 "." 分隔 (e.g. "user.email" 删
    payload["user"]["email"]). 0 改旧 payload type (str/list 等 non-dict 原样
    返回). 0 副作用: 没匹配 path 不改 payload.
    """
    if not isinstance(payload, dict) or not exclude_body_fields:
        return payload

    for field_path in exclude_body_fields:
        parts = field_path.split(".")
        if not parts or not parts[0]:
            continue
        # 简单 nested dict 路径, 不支持 list index (跟 plan 1:1 配对, defensive)
        current = payload
        for i, part in enumerate(parts):
            if not isinstance(current, dict):
                break
            if i == len(parts) - 1:
                # leaf 删除
                current.pop(part, None)
                break
            if part not in current:
                break
            current = current[part]
    return payload


def apply_filter(
    payload: Any,
    headers: Optional[Dict[str, str]],
    filter_cfg: Dict[str, Any],
) -> Tuple[Any, Dict[str, str]]:
    """CAND-005 main: 应用 filter 到 payload + headers, 返 (filtered, filtered_headers).

    跟 plan CAND-005 1:1 配对 — additive 0 改旧, 用于 webhook adapter 投递前
    二次 filter (跟 CAND-008 1:1 配对 opt-in, default 0 filter = 现有行为 0 变).
    返 (filtered_payload, filtered_headers) tuple, 跟 K-10 1:1 配对.

    Args:
        payload: webhook 响应 body (dict 或其他 type, non-dict 原样返回)
        headers: webhook 响应 header dict (case-insensitive key 比较)
        filter_cfg: parse_filter_config() 返的 filter config dict

    Returns:
        (filtered_payload, filtered_headers) tuple
    """
    if not filter_cfg:
        return payload, dict(headers or {})

    # 1. body field filter
    filtered_payload = filter_payload(payload, filter_cfg.get("exclude_body_fields", []))

    # 2. header filter (case-insensitive, 跟 HTTP 1:1 配对)
    filtered_headers = dict(headers or {})
    exclude_headers_lower = {h.lower() for h in filter_cfg.get("exclude_headers", [])}
    if exclude_headers_lower:
        for key in list(filtered_headers.keys()):
            if key.lower() in exclude_headers_lower:
                filtered_headers.pop(key, None)

    return filtered_payload, filtered_headers

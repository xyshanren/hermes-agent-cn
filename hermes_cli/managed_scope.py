"""CAND-042 managed-scope MDM-style config override (Phase 4 v0.20.0 borrow).

跟 plan CAND-042 1:1 配对 (跟 K-7 k7_commands.py + K-10 additive 0 改旧 1:1 配对):
- parse_managed_config: 从 managed config 段 (e.g. /etc/hermes/managed.yaml 或
  ~/.hermes/managed.yaml) 读 MDM-style override config
- apply_overrides: 应用 managed override 到 user config (跟 upstream
  9cbcc0c9 → ddd519ea 1:1 配对, 5 commits 跨 2 天 additive 0 改旧)
- get_managed_layer: 返当前 managed layer 描述 (跟 config show 1:1 配对)
- is_managed_key: 验 key 是否被 managed override (跟 doctor audit 1:1 配对)

跟 mavis 4 件套 1:1 配对 + CAND-084 8-03 22:10 lesson "估时前必 verify 引擎能力":
- 后端先调查再设计: 借 hermes_cli/config.py load_config() 已有 (line 3631+)
  deepcopy 缓存 pattern, additive 0 改 load_config 主体 (新加 layer, 不替换)
- Cherry-pick split bug class: additive 0 改旧, 0 cherry-pick
- UX 倒退审计: 0 改 load_config 主体 (新加 layer 走 managed override path),
  user config 优先, managed 0 命中时 0 行为变更
- 估时前必 verify 引擎能力: verify config.py 已有 deepcopy cache + layer load
  pattern, 实际 1-2h (跟 K-7 1:1 配对 0 改旧 + additive 1 file)

跟 AIMC 4 铁律 1:1: 0 改 upstream / CN 端可维护 / 0 改 upstream 决策边界
(跟 upstream 9cbcc0c9 → ddd519ea 1:1 配对, managed-scope 是 add-only layer)
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict, List, Optional


# Managed config 候选路径 (跟 upstream 1:1 配对, 优先级: system → user)
MANAGED_CONFIG_PATHS = [
    "/etc/hermes/managed.yaml",
    "/usr/local/etc/hermes/managed.yaml",
    str(Path.home() / ".hermes" / "managed.yaml"),
]


def parse_managed_config(managed_cfg: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """CAND-042 read: 解析 managed config dict (跟 upstream resolver 1:1 配对).

    Args:
        managed_cfg: 从 managed.yaml 读出的 dict 或 None

    Returns:
        normalized managed config dict (跟 layer pattern 1:1 配对)
    """
    if not managed_cfg or not isinstance(managed_cfg, dict):
        return {}
    return managed_cfg


def get_managed_layer() -> Optional[Dict[str, Any]]:
    """CAND-042 layer: 读 managed config 候选路径第一个存在的 (跟 plan 1:1 配对).

    跟 upstream 1:1 配对 — system managed (/etc/hermes/managed.yaml) 优先,
    user managed (~/.hermes/managed.yaml) 兜底. None = 0 managed layer (跟
    K-10 default empty 0 行为变更 1:1).
    """
    try:
        import yaml
    except ImportError:
        return None

    for path_str in MANAGED_CONFIG_PATHS:
        path = Path(path_str)
        if not path.exists():
            continue
        try:
            with path.open("r", encoding="utf-8") as f:
                data = yaml.safe_load(f)
            if isinstance(data, dict):
                return data
        except Exception:
            continue
    return None


def is_managed_key(key_path: str, managed_cfg: Optional[Dict[str, Any]]) -> bool:
    """CAND-042 audit: 验 key 是否被 managed override (跟 doctor audit 1:1 配对).

    Args:
        key_path: dot-separated key path (e.g. "approvals.mode")
        managed_cfg: managed config dict 或 None
    """
    if not managed_cfg or not key_path:
        return False
    parts = key_path.split(".")
    if not parts or not parts[0]:
        return False
    current: Any = managed_cfg
    for part in parts:
        if not isinstance(current, dict):
            return False
        if part not in current:
            return False
        current = current[part]
    return True


def apply_overrides(
    user_cfg: Dict[str, Any],
    managed_cfg: Optional[Dict[str, Any]],
) -> Dict[str, Any]:
    """CAND-042 main: 应用 managed override 到 user config (additive 0 改旧).

    跟 plan CAND-042 1:1 配对 — managed 优先, user 兜底. 0 managed_cfg = 原样
    返回 user_cfg (跟 K-10 default empty 0 行为变更 1:1). 用 deep copy 避免
    in-place mutation, 跟 config.py deepcopy cache 1:1 配对.

    Args:
        user_cfg: user config dict (从 config.yaml 加载)
        managed_cfg: managed override dict (从 managed.yaml 加载) 或 None

    Returns:
        merged config dict (user 优先字段 + managed override 字段)
    """
    if not managed_cfg:
        return user_cfg

    from copy import deepcopy
    merged = deepcopy(user_cfg)
    _deep_merge(merged, managed_cfg)
    return merged


def _deep_merge(base: Dict[str, Any], override: Dict[str, Any]) -> None:
    """CAND-042 helper: 递归 deep merge override 到 base (in-place).

    跟 plan CAND-042 1:1 配对 — dict 类型递归 merge, 其他类型 (str/int/list) 直接
    override. List 走 "managed 完全替换 user" 模式 (跟 upstream 1:1 配对,
    不做 list 元素 merge, 避免 MDM 行为 ambiguity).
    """
    for key, value in override.items():
        if (
            key in base
            and isinstance(base[key], dict)
            and isinstance(value, dict)
        ):
            _deep_merge(base[key], value)
        else:
            base[key] = value

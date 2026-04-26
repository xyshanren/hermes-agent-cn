"""
hermes fallback — manage the fallback provider chain.

当主模型因 rate-limit、过载或连接错误失败时，按顺序尝试备用模型。
rate-limit, overload, or connection errors. See:
https://hermes-agent.nousresearch.com/docs/user-guide/features/fallback-providers（中文文档建设中）

子命令：
  hermes fallback [list]   显示当前备用链（无子命令时的默认行为）
  hermes fallback add     通过与 `hermes model` 相同的选择器选取 provider + 模型，
                           然后追加到备用链
  hermes fallback remove  从备用链中删除选中的条目
  hermes fallback clear   清除所有备用条目

存储位置：``~/.hermes/config.yaml`` 顶层字段 ``fallback_providers``（列表，
每项为 ``{provider, model, base_url?, api_mode?}`` 字典）。旧的单字典格式
``fallback_model`` 会在首次添加时自动迁移为新列表格式。
"""
from __future__ import annotations

import copy
from typing import Any, Dict, List, Optional


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _read_chain(config: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Return the normalized fallback chain as a list of dicts.

    Accepts both the new list format (``fallback_providers``) and the legacy
    single-dict format (``fallback_model``).  The returned list is always a
    fresh copy — callers can mutate without touching the config dict.
    """
    chain = config.get("fallback_providers") or []
    if isinstance(chain, list):
        result = [dict(e) for e in chain if isinstance(e, dict) and e.get("provider") and e.get("model")]
        if result:
            return result
    legacy = config.get("fallback_model")
    if isinstance(legacy, dict) and legacy.get("provider") and legacy.get("model"):
        return [dict(legacy)]
    if isinstance(legacy, list):
        return [dict(e) for e in legacy if isinstance(e, dict) and e.get("provider") and e.get("model")]
    return []


def _write_chain(config: Dict[str, Any], chain: List[Dict[str, Any]]) -> None:
    """Persist the chain to ``fallback_providers`` and clear legacy key."""
    config["fallback_providers"] = chain
    # Drop the legacy single-dict key on write so there's only one source of truth.
    if "fallback_model" in config:
        config.pop("fallback_model", None)


def _format_entry(entry: Dict[str, Any]) -> str:
    """将备用条目格式化为单行可读文本。"""
    provider = entry.get("provider", "?")
    model = entry.get("model", "?")
    base = entry.get("base_url")
    suffix = f"  [{base}]" if base else ""
    _provider_names = {
        "openrouter": "OpenRouter", "nous": "Nous Portal",
        "openai": "OpenAI", "anthropic": "Anthropic",
        "gemini": "Google Gemini", "deepseek": "DeepSeek",
        "kimi-coding": "Kimi Coding", "kai": "阿里云通义",
        "zhipu": "智谱 GLM", "minimax": "MiniMax",
        "ollama": "Ollama", "lmstudio": "LM Studio",
        "custom": "自定义端点",
    }
    display_provider = _provider_names.get(provider, provider)
    return f"{model}  (via {display_provider}){suffix}"


def _extract_fallback_from_model_cfg(model_cfg: Any) -> Optional[Dict[str, Any]]:
    """Pull the ``{provider, model, base_url?, api_mode?}`` dict from a ``config["model"]`` snapshot."""
    if not isinstance(model_cfg, dict):
        return None
    provider = (model_cfg.get("provider") or "").strip()
    # The picker writes the selected model to ``model.default``.
    model = (model_cfg.get("default") or model_cfg.get("model") or "").strip()
    if not provider or not model:
        return None
    entry: Dict[str, Any] = {"provider": provider, "model": model}
    base_url = (model_cfg.get("base_url") or "").strip()
    if base_url:
        entry["base_url"] = base_url
    api_mode = (model_cfg.get("api_mode") or "").strip()
    if api_mode:
        entry["api_mode"] = api_mode
    return entry


def _snapshot_auth_active_provider() -> Any:
    """Return the current ``active_provider`` in auth.json, or a sentinel if unavailable."""
    try:
        from hermes_cli.auth import _load_auth_store
        store = _load_auth_store()
        return store.get("active_provider")
    except Exception:
        return None


def _restore_auth_active_provider(value: Any) -> None:
    """Write back a previously snapshotted ``active_provider`` value."""
    try:
        from hermes_cli.auth import _auth_store_lock, _load_auth_store, _save_auth_store
        with _auth_store_lock():
            store = _load_auth_store()
            store["active_provider"] = value
            _save_auth_store(store)
    except Exception:
        # Best-effort — if auth.json can't be restored, the user's primary
        # provider may have been deactivated by the picker.  They can re-run
        # `hermes model` to fix it.  Don't fail the fallback add.
        pass


# ---------------------------------------------------------------------------
# Subcommand handlers
# ---------------------------------------------------------------------------

def cmd_fallback_list(args) -> None:  # noqa: ARG001
    """Print the current fallback chain."""
    from hermes_cli.config import load_config

    config = load_config()
    chain = _read_chain(config)

    print()
    if not chain:
        print("  尚未配置任何备用模型。")
        print()
        print("  添加方式：hermes fallback add")
        print()
        return

    primary = _describe_primary(config)
    if primary:
        print(f"  主模型：   {primary}")
        print()
    entry_word = "条" if len(chain) == 1 else "条"
    print(f"  备用链（共 {len(chain)} {entry_word}）：")
    for i, entry in enumerate(chain, 1):
        print(f"    {i}. {_format_entry(entry)}")
    print()
    print("  Tried in order when the primary fails (rate-limit, 5xx, connection errors).")
    print("  Docs: https://hermes-agent.nousresearch.com/docs/user-guide/features/fallback-providers（中文文档建设中）")
    print()


def _describe_primary(config: Dict[str, Any]) -> Optional[str]:
    """One-line description of the primary model for display purposes."""
    model_cfg = config.get("model")
    if isinstance(model_cfg, dict):
        provider = (model_cfg.get("provider") or "?").strip() or "?"
        model = (model_cfg.get("default") or model_cfg.get("model") or "?").strip() or "?"
        return f"{model}  (via {provider})"
    if isinstance(model_cfg, str) and model_cfg.strip():
        return model_cfg.strip()
    return None


def cmd_fallback_add(args) -> None:
    """Launch the same picker as `hermes model`, then append the selection to the chain."""
    from hermes_cli.main import _require_tty, select_provider_and_model
    from hermes_cli.config import load_config, save_config

    _require_tty("fallback add")

    # Snapshot BEFORE the picker runs so we can distinguish "user actually
    # picked something" from "user cancelled" by comparing before/after.
    before_cfg = load_config()
    model_before = copy.deepcopy(before_cfg.get("model"))
    active_provider_before = _snapshot_auth_active_provider()

    print()
    print("  添加备用模型。下方选择器与 `hermes model` 相同，")
    print("  请选取你希望作为备用的 provider 和模型。")
    print()

    try:
        select_provider_and_model(args=args)
    except SystemExit:
        # Some provider flows exit on auth failure — restore state and re-raise.
        _restore_model_cfg(model_before)
        _restore_auth_active_provider(active_provider_before)
        raise

    # Read the post-picker state to see what the user selected.
    after_cfg = load_config()
    model_after = after_cfg.get("model")

    new_entry = _extract_fallback_from_model_cfg(model_after)
    if not new_entry:
        # Picker didn't complete (user cancelled or flow bailed).  Nothing to do.
        _restore_model_cfg(model_before)
        _restore_auth_active_provider(active_provider_before)
        print()
        print("  未添加任何备用模型（已取消）。")
        return

    # Picker picked the same thing that's already the primary → nothing changed,
    # and there's nothing useful to add as a fallback to itself.
    primary_entry = _extract_fallback_from_model_cfg(model_before)
    if primary_entry and primary_entry["provider"] == new_entry["provider"] \
            and primary_entry["model"] == new_entry["model"]:
        _restore_model_cfg(model_before)
        _restore_auth_active_provider(active_provider_before)
        print()
        print(f"  选中的模型与当前主模型相同（{_format_entry(new_entry)}）。")
        print("  模型不能作为自己的备用 — 未做任何更改。")
        return

    # Reload the config with the primary restored, then append the new entry
    # to ``fallback_providers``.  We deliberately re-load (rather than mutating
    # ``after_cfg``) because the picker may have touched other top-level keys
    # (custom_providers, providers credentials) that we want to keep.
    _restore_model_cfg(model_before)
    _restore_auth_active_provider(active_provider_before)

    final_cfg = load_config()
    chain = _read_chain(final_cfg)

    # Reject exact-duplicate fallback entries.
    for existing in chain:
        if existing.get("provider") == new_entry["provider"] \
                and existing.get("model") == new_entry["model"]:
            print()
            print(f"  {_format_entry(new_entry)} 已在备用链中 — 已跳过。")
            return

    chain.append(new_entry)
    _write_chain(final_cfg, chain)
    save_config(final_cfg)

    print()
    print(f"  已添加备用：{_format_entry(new_entry)}")
    print(f"  当前备用链共 {len(chain)} 条。")
    print()
    print("  运行 `hermes fallback list` 查看，或 `hermes fallback remove` 删除。")


def _restore_model_cfg(model_before: Any) -> None:
    """Restore ``config["model"]`` to a previously-captured snapshot."""
    from hermes_cli.config import load_config, save_config

    cfg = load_config()
    if model_before is None:
        cfg.pop("model", None)
    else:
        cfg["model"] = copy.deepcopy(model_before)
    save_config(cfg)


def cmd_fallback_remove(args) -> None:  # noqa: ARG001
    """Pick an entry from the chain and remove it."""
    from hermes_cli.config import load_config, save_config

    config = load_config()
    chain = _read_chain(config)

    if not chain:
        print()
        print("  尚未配置任何备用模型 — 无可删除项。")
        print()
        return

    choices = [_format_entry(e) for e in chain]
    choices.append("取消")

    try:
        from hermes_cli.setup import _curses_prompt_choice
        idx = _curses_prompt_choice("Select a fallback to remove:", choices, 0)
    except Exception:
        idx = _numbered_pick("Select a fallback to remove:", choices)

    if idx is None or idx < 0 or idx >= len(chain):
        print()
        print("  已取消 — 无更改。")
        return

    removed = chain.pop(idx)
    _write_chain(config, chain)
    save_config(config)

    print()
    print(f"  已删除备用：{_format_entry(removed)}")
    if chain:
        print(f"  当前备用链共 {len(chain)} 条。")
    else:
        print("  备用链已清空。")
    print()


def cmd_fallback_clear(args) -> None:  # noqa: ARG001
    """Remove all fallback entries (with confirmation)."""
    from hermes_cli.config import load_config, save_config

    config = load_config()
    chain = _read_chain(config)

    if not chain:
        print()
        print("  尚未配置任何备用模型 — 无可清空项。")
        print()
        return

    print()
    entry_word = "条" if len(chain) == 1 else "条"
    print(f"  当前备用链（共 {len(chain)} {entry_word}）：")
    for i, entry in enumerate(chain, 1):
        print(f"    {i}. {_format_entry(entry)}")
    print()
    try:
        resp = input("  确认清除全部条目？[y/N]：").strip().lower()
    except (KeyboardInterrupt, EOFError):
        print()
        print("  已取消。")
        return
    if resp not in ("y", "yes"):
        print("  已取消 — 无更改。")
        return

    _write_chain(config, [])
    save_config(config)
    print()
    print("  备用链已清空。")
    print()


def _numbered_pick(question: str, choices: List[str]) -> Optional[int]:
    """curses 不可用时的降级纯数字选择器。"""
    print(question)
    for i, c in enumerate(choices, 1):
        print(f"  {i}. {c}")
    print()
    while True:
        try:
            val = input(f"选择 [1-{len(choices)}]：").strip()
            if not val:
                return None
            idx = int(val) - 1
            if 0 <= idx < len(choices):
                return idx
            print(f"Please enter 1-{len(choices)}")
        except ValueError:
            print("Please enter a number")
        except (KeyboardInterrupt, EOFError):
            print()
            return None


# ---------------------------------------------------------------------------
# Dispatch
# ---------------------------------------------------------------------------

def cmd_fallback(args) -> None:
    """hermes fallback [子命令] 的顶层分发器。"""
    sub = getattr(args, "fallback_command", None)
    if sub in (None, "", "list", "ls"):
        cmd_fallback_list(args)
    elif sub == "add":
        cmd_fallback_add(args)
    elif sub in ("remove", "rm"):
        cmd_fallback_remove(args)
    elif sub == "clear":
        cmd_fallback_clear(args)
    else:
        print(f"未知的 fallback 子命令：{sub}")
        print("可用子命令：list, add, remove, clear")
        raise SystemExit(2)

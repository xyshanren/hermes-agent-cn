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
    """检测本地 Ollama 服务是否运行，返回可用模型列表。"""
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
                return {
                    "available": True,
                    "models": model_names,
                    "default_model": model_names[0] if model_names else "llama3.2",
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
            "http://localhost:11434",
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


# ── 智能路由配置 ──

def _build_fallback_chain(
    api_providers: list[dict],
    ollama_info: Optional[dict],
    has_embedded: bool,
    primary_provider_id: str,
) -> list[dict]:
    """构建 fallback_model 链。

    规则：
    - 已作为主力的 provider 不再放入 fallback
    - 云端 API 作为第一 fallback
    - 嵌入式模型始终放最后（断网兜底）
    - Ollama（如果不是主力）放在云端和嵌入式之间
    """
    chain: list[dict] = []

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
            "base_url": "http://localhost:11434",
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
) -> bool:
    """将智能路由配置写入 config.yaml。

    包括：主力模型 + fallback_model 链 + API Key 保存。
    """
    try:
        from hermes_cli.config import load_config, save_config, save_env_value

        cfg = load_config()

        # 写入主力模型
        model_cfg = cfg.get("model", {})
        if not isinstance(model_cfg, dict):
            model_cfg = {}
        model_cfg["default"] = primary_model
        model_cfg["provider"] = primary_provider_id
        cfg["model"] = model_cfg

        # 写入 fallback 链
        if fallback_chain:
            cfg["fallback_model"] = fallback_chain
        else:
            cfg.pop("fallback_model", None)

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

def cmd_quickstart(args) -> int:
    """一键快速配置 Hermes-Agent-CN 智能路由。

    检测所有可用资源后自动配置三层路由：
      Ollama（主力） → 云端 API（降级） → 嵌入式（断网兜底）
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

    resource_count = len(api_providers) + (1 if ollama_info else 0) + (1 if has_embedded else 0)

    # 显示检测结果
    if api_providers:
        print(f"  {color('✓', Colors.GREEN)} 云端 API Key ({len(api_providers)} 个):")
        for p in api_providers:
            key_preview = os.environ.get(p["env_var"], "")[:8]
            print(f"      {p['name']:12s}  ({p['env_var']}={key_preview}...)")
    else:
        print(f"  {color('⚠', Colors.YELLOW)} 云端 API Key: 未检测到")

    if ollama_info:
        models = ollama_info.get("models", [])
        if models:
            print(f"  {color('✓', Colors.GREEN)} Ollama 本地推理: 运行中 ({', '.join(models[:3])})")
        else:
            print(f"  {color('✓', Colors.GREEN)} Ollama 本地推理: 运行中（暂无模型）")
    else:
        print(f"  {color('⚠', Colors.YELLOW)} Ollama 本地推理: 未运行")

    if has_embedded:
        print(f"  {color('✓', Colors.GREEN)} 离线兜底模型: 已安装")
    else:
        print(f"  {color('⚠', Colors.YELLOW)} 离线兜底模型: 未安装")

    print()

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

    # 确定主力提供商：Ollama 优先 > 云端 API > 嵌入式
    primary_id = ""
    primary_model = ""

    if ollama_info:
        primary_id = "ollama"
        primary_model = ollama_info["default_model"]
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
                if old_provider and old_default and old_provider != primary_id:
                    # 插入到链头（作为第一 fallback）
                    old_entry = {"provider": old_provider, "model": old_default}
                    # 去重
                    existing_providers = {f.get("provider") for f in fallback_chain}
                    if old_provider not in existing_providers:
                        fallback_chain.insert(0, old_entry)
        except Exception:
            pass

    # 写入配置
    # 先调用 _update_config_for_provider 设置 auth.json
    if primary_id == "ollama":
        _configure_ollama(ollama_info)
    elif primary_id == "embedded":
        _configure_embedded()
    else:
        # 找到对应的 provider dict
        for p in api_providers:
            if p["id"] == primary_id:
                _configure_provider(p)
                break

    # 然后写入完整的智能路由（覆盖上面写入的 model 配置）
    _write_smart_routing(primary_id, primary_model, fallback_chain, api_providers)

    # ── 显示结果 ──
    print()
    print(f"{'=' * 60}")
    print(f"  ✅ 智能路由配置完成！")
    print(f"{'=' * 60}")
    print()

    # 主力
    _provider_names = {p["id"]: p["name"] for p in _PROVIDER_CHECKS}
    _provider_names["ollama"] = "Ollama（本地）"
    _provider_names["embedded"] = "Qwen2.5-0.5B（离线）"

    primary_name = _provider_names.get(primary_id, primary_id)
    print(f"  🔵 主力推理: {primary_name} — {primary_model}")

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

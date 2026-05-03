"""
Hermes-Agent-CN 快捷启动 — 零交互体验。

快速检测可用资源并自动配置，让用户从零开始一步到位。
适用于首次安装后、或重置配置后的场景。

检测顺序：
  1. 环境变量中的 API Key（优先国产 Provider）
  2. 本地 Ollama 服务
  3. 本地离线模型（嵌入式推理）

如果发现已配置的资源，自动写入 config.yaml 并设置默认模型。
如果三样都没有，引导安装本地离线模型。
"""

from __future__ import annotations

import json
import logging
import os
import subprocess
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
        "default_model": "deepseek-chat",
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
        import os
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


def cmd_quickstart(args) -> int:
    """一键快速配置 Hermes-Agent-CN。

    检测顺序：国产 API Key → Ollama → 本地离线模型。
    三种情况至少配置一种，保证用户可以直接开始使用。
    """
    from hermes_cli.colors import Colors, color

    print()
    print(f"{'=' * 60}")
    print(f"  ⚡ Hermes-Agent-CN 快捷启动")
    print(f"{'=' * 60}")
    print()

    # ── Step 1: 检测环境变量中的 API Key ──
    print(f"  🔍 Step 1/4: 检测国产 API Key...")
    api_providers = _detect_api_key_providers()
    if api_providers:
        print(f"  {color('✓', Colors.GREEN)} 发现 {len(api_providers)} 个已配置的 API Key:")
        for p in api_providers:
            key_preview = os.environ.get(p["env_var"], "")[:8]
            print(f"      {p['name']:12s}  ({p['env_var']}={key_preview}...)")
        print()
        print(f"  ⏳ 正在写入配置...")

        # 选优先级最高的配置
        best = api_providers[0]
        ok = _configure_provider(best)
        if ok:
            print(f"  {color('✅', Colors.GREEN)} 已配置: {best['name']}")
            print(f"     默认模型: {best['default_model']}")
            print(f"     如需更换模型，运行: hermes model")
            print()
            print(f"{'=' * 60}")
            print(f"  🎉 配置完成！直接运行 hermes 即可开始对话")
            print(f"{'=' * 60}")
            print()
            return 0
        else:
            print(f"  {color('❌', Colors.RED)} 配置写入失败")
    else:
        print(f"  {color('⚠', Colors.YELLOW)} 未发现 API Key")
    print()

    # ── Step 2: 检测本地 Ollama ──
    print(f"  🔍 Step 2/4: 检测本地 Ollama...")
    ollama_info = _detect_ollama()
    if ollama_info:
        models = ollama_info.get("models", [])
        if models:
            print(f"  {color('✓', Colors.GREEN)} Ollama 运行中，可用模型: {', '.join(models[:3])}")
        else:
            print(f"  {color('✓', Colors.GREEN)} Ollama 运行中（暂无模型）")
        print()

        if not api_providers:
            print(f"  ⏳ 正在配置 Ollama...")
            ok = _configure_ollama(ollama_info)
            if ok:
                print(f"  {color('✅', Colors.GREEN)} 已配置: Ollama（本地）")
                print(f"     默认模型: {ollama_info['default_model']}")
                print(f"     如需更换模型，运行: hermes model")
                print()
                print(f"{'=' * 60}")
                print(f"  🎉 配置完成！直接运行 hermes 即可开始对话")
                print(f"{'=' * 60}")
                print()
                return 0
        else:
            print(f"  {color('ℹ', Colors.BLUE)} 已有 API Key 配置，Ollama 作为备选")
            print(f"     如需切换，运行: hermes model")
    else:
        print(f"  {color('⚠', Colors.YELLOW)} 未检测到 Ollama")
    print()

    # ── Step 3: 安装本地离线模型 ──
    print(f"  🔍 Step 3/4: 检测本地离线模型...")
    if _has_embedded_models():
        print(f"  {color('✓', Colors.GREEN)} 本地模型已安装")
        if not api_providers and not ollama_info:
            print(f"  ⏳ 正在配置嵌入式推理...")
            ok = _configure_embedded()
            if ok:
                print(f"  {color('✅', Colors.GREEN)} 已配置: 本地离线推理（Qwen2.5-0.5B）")
                print()
                print(f"{'=' * 60}")
                print(f"  🎉 配置完成！直接运行 hermes 即可开始对话")
                print(f"{'=' * 60}")
                print()
                return 0
    else:
        print(f"  {color('⚠', Colors.YELLOW)} 未安装本地模型")
        print()

        # 没有 API Key、没有 Ollama、没有本地模型 → 引导安装
        if not api_providers and not ollama_info:
            print(f"  🔧 Step 4/4: 自动安装本地离线模型...")
            print(f"     未检测到任何可用的 AI 资源。")
            print(f"     将自动安装本地离线模型（约 1.58GB），无需网络即可使用。")
            print()

            try:
                reply = input("  确认安装？(Y/n): ").strip().lower()
            except (EOFError, KeyboardInterrupt):
                reply = "n"

            if reply in ("", "y", "yes"):
                print()
                print(f"  {color('⏳', Colors.YELLOW)} 正在安装，请稍候...")
                print()

                # 调用模型管理器的 setup 函数
                try:
                    from hermes_cli.model_manager import cmd_local_models_setup

                    # 构造带 --yes 的 args
                    setup_args = type("Args", (), {"yes": True, "model": None})()
                    result = cmd_local_models_setup(setup_args)

                    if result == 0:
                        print(f"  {color('✅', Colors.GREEN)} 模型安装完成，正在写入配置...")
                        _configure_embedded()
                        print(f"\n{'=' * 60}")
                        print(f"  🎉 全部就绪！直接运行 hermes 即可开始对话")
                        print(f"{'=' * 60}")
                        print()
                        return 0
                    else:
                        print(f"  {color('❌', Colors.RED)} 模型安装失败，请检查网络后重试")
                        print(f"     运行: hermes local-models setup")
                except Exception as e:
                    print(f"  {color('❌', Colors.RED)} 安装出错: {e}")
                    print(f"     运行: hermes local-models setup")
            else:
                print(f"  {color('ℹ', Colors.BLUE)} 跳过安装")
                print()
                print(f"  您随时可以运行以下命令手动配置:")
                print(f"    hermes local-models setup     — 安装本地模型")
                print(f"    hermes setup                  — 配置 API Key")
                print(f"    hermes quickstart             — 重新自动检测")
        else:
            print(f"  {color('ℹ', Colors.BLUE)} 已有其他可用配置，跳过本地模型安装")
            print(f"     如需安装，运行: hermes local-models setup")

    print()
    print(f"{'=' * 60}")
    print(f"  当前状态:")
    if api_providers:
        print(f"  ✓ API Key: {api_providers[0]['name']}")
    if ollama_info:
        print(f"  ✓ Ollama: 运行中")
    if _has_embedded_models():
        print(f"  ✓ 本地模型: 已安装")
    if not api_providers and not ollama_info and not _has_embedded_models():
        print(f"  ✗ 暂无可用的 AI 资源")
        print(f"  请运行: hermes local-models setup     — 安装本地模型")
        print(f"  或:     hermes setup                  — 配置 API Key")
    print(f"{'=' * 60}")
    print()
    return 0

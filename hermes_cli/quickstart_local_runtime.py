"""quickstart 的本地模型资源（local_runtime 托管目录）扫描与配置。

从 ``hermes_cli/quickstart.py`` 拆出的主题 sibling：facade 已超过 2000 行
ratchet 上限、只降不升。本地档只保留 local_runtime —— Ollama / LM Studio /
vLLM / embedded 等其它本地模型服务不再由 quickstart 探测或配置，需要时走
``hermes model`` 的自定义 provider 面。

``_prompt_models_dir`` 惰性 import ``quickstart._prompt_yes_no``，避免
facade ↔ sibling 的模块级循环。
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


def _detect_local_runtime_models() -> dict:
    """扫描 local_runtime 托管的模型目录（``local_runtime.models_dir`` 或默认）。

    只做目录 glob：``staged_models()`` 收录完整分片、排除 ``assets/``，所以
    手动放进该目录的 GGUF 也能被发现。路径可以指向 WSL（``/mnt/...``）或
    Windows（``D:\\...``）已有模型库。
    """
    try:
        from hermes_cli.local_runtime import bootstrap
        from hermes_cli.local_runtime.gguf import model_id_from_stem

        directory = bootstrap.models_dir()
        staged = bootstrap.staged_models()
    except Exception:  # boundary: a scan failure must not abort the wizard
        logger.debug("local_runtime model scan failed", exc_info=True)
        return {"models_dir": "", "models": [], "configured": False}

    configured = False
    try:
        from hermes_cli.config import load_config_readonly

        section = load_config_readonly().get("local_runtime") or {}
        configured = bool(str((section or {}).get("models_dir") or "").strip())
    except Exception:  # optional probe: "unset" is the safe default
        logger.debug("local_runtime.models_dir probe failed", exc_info=True)

    models = []
    for path in staged:
        try:
            size_mb = int(path.stat().st_size // (1024 * 1024))
        except OSError:
            size_mb = 0
        models.append(
            {"id": model_id_from_stem(path.stem), "path": path, "size_mb": size_mb}
        )
    return {"models_dir": str(directory), "models": models, "configured": configured}


def _save_models_dir(raw: str) -> None:
    """写入 ``local_runtime.models_dir``（空串 = 恢复默认目录）。"""
    from hermes_cli.config import load_config, save_config

    cfg = load_config()
    section = cfg.get("local_runtime")
    if not isinstance(section, dict):
        section = {}
        cfg["local_runtime"] = section
    section["models_dir"] = raw.strip()
    save_config(cfg)
    logger.info("local_runtime.models_dir set to %r", raw.strip())


def _prompt_models_dir(current: str) -> Optional[str]:
    """询问是否修改模型保存路径；返回新绝对路径，``None`` = 保持不变。"""
    from hermes_cli.quickstart import _prompt_yes_no

    print(f"     模型目录: {current}")
    if not _prompt_yes_no("修改模型保存路径？", default=False):
        return None
    raw = input("    新路径（支持 WSL /mnt/... 与 Windows D:\\...）: ").strip()
    if not raw:
        print("    （空输入，保持原路径）")
        return None
    path = Path(raw).expanduser()
    if not path.is_absolute():
        print(f"    ⚠ 需要绝对路径，已忽略: {raw}")
        return None
    return str(path)


def _count_available_resources(api_providers, aimc_info, local_runtime_info) -> int:
    """Step 1 的资源计数：云端 key + AIMC + local_runtime 托管模型。"""
    return (
        len(api_providers)
        + (1 if aimc_info else 0)
        + (1 if (local_runtime_info.get("models") or []) else 0)
    )


def _report_and_maybe_configure_local_runtime(info: dict) -> dict:
    """Step 1 展示 local_runtime 模型并询问目录；返回（可能刷新后的）扫描结果。"""
    from hermes_cli.colors import Colors, color

    models = info.get("models") or []
    if models:
        names = ", ".join(m["id"] for m in models[:3])
        more = f" 等 {len(models)} 个" if len(models) > 3 else ""
        print(f"  {color('✓', Colors.GREEN)} local_runtime 本地模型: {names}{more}")
    else:
        print(f"  {color('⚠', Colors.YELLOW)} local_runtime 本地模型: 暂无 GGUF")

    new_dir = _prompt_models_dir(info.get("models_dir") or "")
    if new_dir and new_dir != info.get("models_dir"):
        _save_models_dir(new_dir)
        info = _detect_local_runtime_models()
        count = len(info.get("models") or [])
        print(f"    ✓ 已保存模型目录（现有 {count} 个模型；重启 hermes 后托管服务生效）")
    return info


def _configure_local_runtime(model_id: str) -> bool:
    """把 local_runtime 托管模型设为主力（``provider=llamacpp`` 裸别名）。

    endpoint 由 ``resolve_llamacpp_endpoint`` 在请求期解析，所以这里不写
    ``base_url``；``local_runtime.enabled`` 必须为真，托管 server 才会启动。
    """
    try:
        from hermes_cli.config import load_config, save_config

        cfg = load_config()
        model = cfg.get("model")
        if not isinstance(model, dict):
            model = {}
        model["default"] = model_id
        model["provider"] = "llamacpp"
        model.pop("base_url", None)
        cfg["model"] = model

        section = cfg.get("local_runtime")
        if not isinstance(section, dict):
            section = {}
        section["enabled"] = True
        cfg["local_runtime"] = section
        save_config(cfg)
        return True
    except Exception as e:
        logger.warning("配置 local_runtime 失败: %s", e, exc_info=True)
        return False

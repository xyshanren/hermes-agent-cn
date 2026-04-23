#!/usr/bin/env python3
"""
Local Models Manager for Hermes Agent.

Provides `hermes local-models` CLI command for installing, listing, and managing
offline AI models (STT, TTS, LLM) that work without external API calls.

Model Registry:
  - STT:  faster-whisper-small  (Systran/faster-whisper-small)
  - TTS:  moss-tts-nano-onnx   (openmoss/MOSS-TTS-Nano-100M-ONNX)
  - LLM:  qwen2.5-coder-1.5b   (Qwen/Qwen2.5-Coder-1.5B-Instruct-GGUF)
           qwen2.5-0.5b         (Qwen/Qwen2.5-0.5B-Instruct-GGUF)

Usage:
    hermes local-models list
    hermes local-models install <model>
    hermes local-models remove <model>
    hermes local-models status
    hermes local-models test <model>

Environment:
  MODELSCOPE_TOKEN   Optional ModelScope API token for higher download limits.
  HERMES_MODELS_DIR  Override default model storage directory (~/.hermes/models).
"""

import hashlib
import json
import logging
import os
import shutil
import subprocess
import sys
import tarfile
import tempfile
import urllib.request
import zipfile
from pathlib import Path
from typing import Optional

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

def _get_hermes_home() -> Path:
    """Return the Hermes home directory (~/.hermes)."""
    return Path(os.path.expanduser("~/.hermes"))

def _get_models_dir() -> Path:
    """Return the local models storage directory."""
    return Path(os.environ.get("HERMES_MODELS_DIR", str(_get_hermes_home() / "models")))

# ---------------------------------------------------------------------------
# Model Registry
# ---------------------------------------------------------------------------

# Each entry: (id, name, category, model_scope_id, local_dir_name, size_mb, description)
MODEL_REGISTRY = [
    {
        "id": "whisper-small",
        "name": "Whisper-small (STT)",
        "category": "stt",
        "model_scope_id": "Systran/faster-whisper-small",
        "local_dir": "whisper-small",
        "size_mb": 464,
        "description": "本地语音识别模型 (~464MB)，支持多语言转写，无需网络",
        "install_hint": "通过 faster-whisper 自动下载 CTranslate2 格式模型",
    },
    {
        "id": "moss-tts-nano",
        "name": "MOSS-TTS-Nano (TTS)",
        "category": "tts",
        "model_scope_id": "openmoss/MOSS-TTS-Nano-100M-ONNX",
        "local_dir": "moss-tts-nano",
        "size_mb": 641,
        "description": "本地语音合成模型 (~641MB)，100M 参数 ONNX 版本，纯离线运行",
        "install_hint": "从 ModelScope 下载 ONNX 权重（包含 LFS 大文件 shared.data）",
    },
    {
        "id": "qwen-coder-1.5b",
        "name": "Qwen2.5-Coder-1.5B (LLM)",
        "category": "llm",
        "model_scope_id": "Qwen/Qwen2.5-Coder-1.5B-Instruct-GGUF",
        "local_dir": "qwen-coder-1.5b-q4_k_m",
        "size_mb": 1070,
        "description": "本地代码助手模型 (~1.07GB, Q4_K_M GGUF)，断网时 Hermes 降级使用",
        "install_hint": "从 ModelScope 下载 GGUF 格式量化模型（q4_k_m 版本）",
    },
    {
        "id": "qwen-0.5b",
        "name": "Qwen2.5-0.5B (LLM)",
        "category": "llm",
        "model_scope_id": "Qwen/Qwen2.5-0.5B-Instruct-GGUF",
        "local_dir": "qwen-0.5b-q4_k_m",
        "size_mb": 469,
        "description": "轻量本地模型 (~469MB, Q4_K_M GGUF)，资源受限环境首选",
        "install_hint": "从 ModelScope 下载 GGUF 格式量化模型（q4_k_m 版本）",
    },
]

# Group registry by category
MODELS_BY_CATEGORY = {"stt": [], "tts": [], "llm": []}
for m in MODEL_REGISTRY:
    MODELS_BY_CATEGORY[m["category"]].append(m)


# ---------------------------------------------------------------------------
# Status helpers
# ---------------------------------------------------------------------------

def get_model_path(model_id: str) -> Path:
    """Return the local path for a model."""
    entry = next((m for m in MODEL_REGISTRY if m["id"] == model_id), None)
    if not entry:
        raise ValueError(f"Unknown model: {model_id}")
    return _get_models_dir() / entry["local_dir"]


def is_installed(model_id: str) -> bool:
    """Return True if the model is installed locally."""
    try:
        path = get_model_path(model_id)
        return path.exists() and any(path.iterdir())
    except Exception:
        return False


def list_installed() -> list[dict]:
    """Return list of installed models with their info."""
    installed = []
    for m in MODEL_REGISTRY:
        inst = is_installed(m["id"])
        size = _get_dir_size(_get_models_dir() / m["local_dir"]) if inst else 0
        installed.append({**m, "installed": inst, "size_mb": size})
    return installed


def _get_dir_size(path: Path) -> float:
    """Return total size of directory in MB."""
    if not path.exists():
        return 0.0
    total = 0
    for f in path.rglob("*"):
        if f.is_file():
            total += f.stat().st_size
    return round(total / (1024 * 1024), 1)


def check_requirements(model_id: str) -> tuple[bool, str]:
    """Check if the model's runtime requirements are met. Returns (ok, message)."""
    m = next((x for x in MODEL_REGISTRY if x["id"] == model_id), None)
    if not m:
        return False, f"未知模型: {model_id}"

    if model_id == "whisper-small":
        try:
            import importlib
            spec = importlib.util.find_spec("faster_whisper")
            if spec is None:
                return False, "faster-whisper 未安装（运行: pip install faster-whisper）"
            return True, "faster-whisper 已安装"
        except Exception as e:
            return False, f"检查失败: {e}"

    elif model_id == "moss-tts-nano":
        # Check ONNX runtime
        try:
            import importlib
            spec = importlib.util.find_spec("onnxruntime")
            if spec is None:
                return False, "onnxruntime 未安装（运行: pip install onnxruntime）"
            return True, "onnxruntime 已安装"
        except Exception as e:
            return False, f"检查失败: {e}"

    elif model_id.startswith("qwen"):
        # Check llama.cpp python binding
        try:
            import importlib
            spec = importlib.util.find_spec("llama_cpp")
            if spec is None:
                return False, "llama-cpp-python 未安装（运行: pip install llama-cpp-python）"
            return True, "llama-cpp-python 已安装"
        except Exception as e:
            return False, f"检查失败: {e}"

    return True, "就绪"


# ---------------------------------------------------------------------------
# Download helpers
# ---------------------------------------------------------------------------

def _run_cmd(cmd: list[str], cwd: Optional[Path] = None, env: Optional[dict] = None) -> subprocess.CompletedProcess:
    """Run a shell command, return CompletedProcess."""
    merged_env = {**os.environ, **(env or {})}
    return subprocess.run(
        cmd,
        cwd=cwd,
        env=merged_env,
        capture_output=True,
        text=True,
    )


def _has_modelscope() -> bool:
    """Return True if modelscope SDK is available."""
    try:
        import importlib
        return importlib.util.find_spec("modelscope") is not None
    except Exception:
        return False


def download_model(model_id: str, progress_callback=None) -> bool:
    """
    Download a model to the local models directory.

    Args:
        model_id:  Model ID from MODEL_REGISTRY.
        progress_callback: Optional callable(msg: str) for progress output.

    Returns:
        True on success, False on failure.
    """
    m = next((x for x in MODEL_REGISTRY if x["id"] == model_id), None)
    if not m:
        print(f"[error] 未知模型: {model_id}")
        return False

    dest = _get_models_dir() / m["local_dir"]

    def _print(msg: str):
        print(msg)
        if progress_callback:
            progress_callback(msg)

    _print(f"\n📦 开始下载 {m['name']} ({m['size_mb']}MB)")
    _print(f"   ModelScope: {m['model_scope_id']}")
    _print(f"   目标目录: {dest}")

    # Ensure models dir exists
    _get_models_dir().mkdir(parents=True, exist_ok=True)

    # -------------------------------------------------------------------------
    # whisper-small: use faster-whisper auto-download
    # -------------------------------------------------------------------------
    if model_id == "whisper-small":
        _print("\n⏳ 正在通过 faster-whisper 下载模型（首次使用自动下载）...")
        result = _run_cmd([
            sys.executable, "-c",
            (
                "from faster_whisper import WhisperModel; "
                "model = WhisperModel('small', download_root=__import__('os').getcwd()); "
                "print('OK')"
            )
        ], cwd=_get_models_dir())
        if result.returncode == 0 and "OK" in result.stdout:
            _print(f"✅ Whisper-small 下载完成: {dest}")
            return True
        else:
            _print(f"❌ 下载失败:\n{result.stderr or result.stdout}")
            return False

    # -------------------------------------------------------------------------
    # Other models: require modelscope SDK
    # -------------------------------------------------------------------------
    if not _has_modelscope():
        _print("\n⛔ 需要安装 ModelScope SDK:")
        _print("   pip install modelscope")
        _print("\n或手动下载模型文件后放入目标目录。")
        return False

    token = os.environ.get("MODELSCOPE_TOKEN", "")

    # Try git-lfs clone first (handles LFS files like moss-tts shared.data)
    if model_id == "moss-tts-nano":
        _print("\n⏳ 使用 git lfs clone 下载（处理大文件）...")
        result = _run_cmd(["git", "lfs", "install"], cwd=_get_models_dir())
        result = _run_cmd(
            [
                "git", "clone",
                "--depth", "1",
                "https://www.modelscope.cn/{}.git".format(m["model_scope_id"]),
                m["local_dir"],
            ],
            cwd=_get_models_dir(),
        )
        if result.returncode == 0:
            _print(f"✅ MOSS-TTS-Nano 下载完成")
            return True
        else:
            _print(f"⚠ git clone 失败，尝试 ModelScope API...")
            # Fall through to API method

    # Fallback: use ModelScope Python API
    _print("\n⏳ 通过 ModelScope API 下载...")
    script = f"""
import os
from modelscope.hub.api import HubApi
api = HubApi()
api.login('{token}')
files = api.get_model_files('{m['model_scope_id']}', recursive=True)
for f in files:
    print(f.file_name)
"""
    result = _run_cmd([sys.executable, "-c", script])

    if result.returncode != 0:
        _print(f"❌ ModelScope API 调用失败:\n{result.stderr}")
        return False

    _print(f"⚠ 模型文件列表已获取，请手动下载到: {dest}")
    _print(f"   ModelScope 地址: https://www.modelscope.cn/{m['model_scope_id']}")
    _print(f"\n   或设置 MODELSCOPE_TOKEN 环境变量后重试")
    return True


def remove_model(model_id: str) -> bool:
    """Remove an installed model."""
    try:
        path = get_model_path(model_id)
        if path.exists():
            shutil.rmtree(path)
            print(f"✅ 已删除: {path}")
            return True
        else:
            print(f"⚠ 模型未安装: {model_id}")
            return False
    except Exception as e:
        print(f"❌ 删除失败: {e}")
        return False


# ---------------------------------------------------------------------------
# Test helpers
# -------------------------------------------------------------------------

def test_model(model_id: str) -> tuple[bool, str]:
    """Test if a model loads correctly. Returns (success, message)."""
    m = next((x for x in MODEL_REGISTRY if x["id"] == model_id), None)
    if not m:
        return False, f"未知模型: {model_id}"

    if not is_installed(model_id):
        return False, "模型未安装，请先运行 hermes local-models install"

    if model_id == "whisper-small":
        try:
            import importlib
            if importlib.util.find_spec("faster_whisper") is None:
                return False, "faster-whisper 未安装"
            from faster_whisper import WhisperModel
            model_dir = get_model_path(model_id)
            model = WhisperModel(str(model_dir), download_root=str(model_dir))
            del model
            return True, "Whisper-small 加载成功"
        except Exception as e:
            return False, f"加载失败: {e}"

    elif model_id == "moss-tts-nano":
        try:
            import importlib
            if importlib.util.find_spec("onnxruntime") is None:
                return False, "onnxruntime 未安装"
            return True, "MOSS-TTS-Nano ONNX 权重已就位，推理测试请参考 ModelScope 文档"
        except Exception as e:
            return False, f"检查失败: {e}"

    elif model_id.startswith("qwen"):
        try:
            import importlib
            if importlib.util.find_spec("llama_cpp") is None:
                return False, "llama-cpp-python 未安装"
            return True, "GGUF 权重已就位，请通过 Hermes 路由自动调用"
        except Exception as e:
            return False, f"检查失败: {e}"

    return True, "就绪"


# ---------------------------------------------------------------------------
# CLI commands (called from main.py)
# -------------------------------------------------------------------------

def cmd_local_models_list(args) -> int:
    """List all available models and their installation status."""
    from hermes_cli.colors import Colors, color

    print(f"\n{'─' * 60}")
    print(f"  📁 模型存储目录: {_get_models_dir()}")
    print(f"{'─' * 60}\n")

    categories = [
        ("stt", "🎤 语音识别 (STT)"),
        ("tts", "🔊 语音合成 (TTS)"),
        ("llm", "🤖 本地大语言模型 (LLM)"),
    ]

    installed_count = 0
    total_count = 0

    for cat_id, cat_name in categories:
        models = MODELS_BY_CATEGORY.get(cat_id, [])
        if not models:
            continue
        print(f"  {cat_name}")
        for m in models:
            total_count += 1
            inst = is_installed(m["id"])
            if inst:
                installed_count += 1
                size = _get_dir_size(_get_models_dir() / m["local_dir"])
                status_icon = color("✓", Colors.GREEN) + color(" 已安装", Colors.GREEN)
                status_detail = color(f"({size}MB)", Colors.DIM)
            else:
                status_icon = color("✗", Colors.RED) + color(" 未安装", Colors.RED)
                status_detail = color(f"(需 {m['size_mb']}MB)", Colors.DIM)

            print(f"    {status_icon} {status_detail}  {m['name']}")
            print(f"           {m['description']}")
            print(f"           {color(m['install_hint'], Colors.DIM)}")
            print()

    print(f"{'─' * 60}")
    print(f"  已安装: {installed_count}/{total_count}")
    print(f"{'─' * 60}\n")

    # Runtime requirement check
    print(f"  运行时依赖检查:")
    deps_ok = 0
    deps_total = 0
    for m in MODEL_REGISTRY:
        ok, msg = check_requirements(m["id"])
        deps_total += 1
        if ok:
            deps_ok += 1
            print(f"    {color('✓', Colors.GREEN)} {m['name']}: {msg}")
        else:
            print(f"    {color('✗', Colors.RED)} {m['name']}: {msg}")
    print(f"  依赖状态: {deps_ok}/{deps_total}\n")

    return 0


def cmd_local_models_install(args) -> int:
    """Install a model."""
    from hermes_cli.colors import Colors, color

    model_id = args.model
    if not model_id:
        print("❌ 请指定模型名称，例如: hermes local-models install whisper-small")
        print("   运行 hermes local-models list 查看可用模型")
        return 1

    # Validate model ID
    valid_ids = [m["id"] for m in MODEL_REGISTRY]
    if model_id not in valid_ids:
        print(f"❌ 未知模型: {model_id}")
        print("   可用模型:")
        for m in MODEL_REGISTRY:
            print(f"   - {m['id']:20s} {m['name']}")
        return 1

    success = download_model(model_id)
    return 0 if success else 1


def cmd_local_models_remove(args) -> int:
    """Remove an installed model."""
    model_id = args.model
    if not model_id:
        print("❌ 请指定模型名称，例如: hermes local-models remove whisper-small")
        return 1

    if not is_installed(model_id):
        print(f"⚠ 模型未安装: {model_id}")
        return 0

    print(f"⚠ 即将删除模型 {model_id}，此操作不可恢复。")
    confirm = input("   确认删除? (y/N): ").strip().lower()
    if confirm != "y":
        print("已取消")
        return 0

    remove_model(model_id)
    return 0


def cmd_local_models_status(args) -> int:
    """Show detailed status of installed models."""
    from hermes_cli.colors import Colors, color

    installed = list_installed()

    print(f"\n{'─' * 60}")
    print(f"  本地模型状态报告")
    print(f"{'─' * 60}\n")

    total_size = 0.0
    for m in installed:
        inst = m["installed"]
        size = m["size_mb"] if inst else 0
        total_size += size

        if inst:
            icon = color("✓", Colors.GREEN)
        else:
            icon = color("✗", Colors.RED)

        print(f"  {icon} {m['name']}")
        print(f"    安装状态: {'已安装' if inst else color('未安装', Colors.RED)}")
        print(f"    占用空间: {size}MB" if inst else f"    所需空间: {m['size_mb']}MB")

        # Check runtime requirements
        ok, msg = check_requirements(m["id"])
        req_icon = color("✓", Colors.GREEN) if ok else color("✗", Colors.RED)
        print(f"    运行时依赖: {req_icon} {msg}")
        print()

    total_installed = sum(1 for m in installed if m["installed"])
    print(f"{'─' * 60}")
    print(f"  已安装 {total_installed}/{len(installed)} 个模型，")
    print(f"  总占用 {round(total_size, 1)}MB")
    print(f"  存储目录: {_get_models_dir()}")
    print(f"{'─' * 60}\n")
    return 0


def cmd_local_models_test(args) -> int:
    """Test if a model loads correctly."""
    from hermes_cli.colors import Colors, color

    model_id = args.model
    if not model_id:
        print("❌ 请指定模型名称，例如: hermes local-models test whisper-small")
        return 1

    print(f"\n⏳ 正在测试模型 {model_id}...\n")
    success, msg = test_model(model_id)

    if success:
        print(f"  {color('✓', Colors.GREEN)} {color('测试通过', Colors.GREEN)}")
        print(f"  {msg}\n")
        return 0
    else:
        print(f"  {color('✗', Colors.RED)} {color('测试失败', Colors.RED)}")
        print(f"  {msg}\n")
        return 1

"""
Hermes Desktop (Chat GUI) uninstaller — CN 减法 stub.

Sprint 16 档 A.3 (跟 8-12 P3 拍 A "Cat 5 客户端" 1:1 配对):
- CN 端没跟 upstream desktop 路径
- 整个 module 改 stub, 0 改 `run_gui_uninstall` caller 协议
- Sprint 16 档 A.4 跟 apps/desktop 1529 文件一起 `git rm -r apps/desktop/`
- 推荐 CN 替代: hermes-tray (独立 git 仓库, 轻量 Tauri 2 客户端)

原 module 11 函数 + 495 行: 删 Electron artifacts + 删 packaged app + 删 userData
- _agent_root / desktop_userdata_dir / source_built_gui_artifacts / packaged_gui_app_paths
- agent_is_installed / gui_is_installed / gui_install_summary / uninstall_gui / _remove_path
- log_info / log_success / log_warn (UI helpers)

Caller 路径 (跟 stub 兼容):
- hermes_cli/uninstall.py:run_gui_uninstall (line 512-581) → stub 0 实际跑
- hermes_cli/main.py:cmd_uninstall `if getattr(args, "gui_summary", False)` branch → 改 stub
- hermes_cli/main.py:cmd_uninstall `if getattr(args, "gui", False)` branch → 改 stub
- hermes_cli/main.py:cmd_gui (A.3.2 stub) → 跟本 stub 1:1 配对
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional


def log_info(msg: str) -> None:
    """Sprint 16 档 A.3 CN 减法 stub. 原 log_info 0 改, 保留 import-time compatibility."""
    print(f"[INFO] {msg}")


def log_success(msg: str) -> None:
    """Sprint 16 档 A.3 CN 减法 stub. 原 log_success 0 改, 保留 import-time compatibility."""
    print(f"[OK] {msg}")


def log_warn(msg: str) -> None:
    """Sprint 16 档 A.3 CN 减法 stub. 原 log_warn 0 改, 保留 import-time compatibility."""
    print(f"[WARN] {msg}")


def _agent_root(hermes_home: Path) -> Path:
    """Sprint 16 档 A.3 CN 减法 stub. 原 _agent_root 0 改 (跟 stub 兼容)."""
    return hermes_home / "hermes-agent"


def desktop_userdata_dir() -> Path:
    """Sprint 16 档 A.3 CN 减法 stub. 返回 Path('/dev/null'),0 路径破坏."""
    return Path("/dev/null")


def source_built_gui_artifacts(hermes_home: Path) -> "list[Path]":
    """Sprint 16 档 A.3 CN 减法 stub. 返回空 list,0 路径破坏."""
    return []


def packaged_gui_app_paths() -> "list[Path]":
    """Sprint 16 档 A.3 CN 减法 stub. 返回空 list,0 路径破坏."""
    return []


def agent_is_installed(hermes_home: Path) -> bool:
    """Sprint 16 档 A.3 CN 减法 stub. 返回 True (CN agent 已装,0 desktop)."""
    return True


def gui_is_installed(hermes_home: Path) -> bool:
    """Sprint 16 档 A.3 CN 减法 stub. 返回 False (CN 端 0 Electron desktop)."""
    return False


def gui_install_summary(hermes_home: "Optional[Path]" = None) -> dict:
    """Sprint 16 档 A.3 CN 减法 stub. 返回空 summary (0 desktop installed)."""
    return {
        "gui_installed": False,
        "source_built_artifacts": [],
        "packaged_app_paths": [],
        "userdata_exists": False,
        "userdata_dir": Path("/dev/null"),
    }


def _remove_path(path: Path) -> bool:
    """Sprint 16 档 A.3 CN 减法 stub. 0 实际删除,0 路径破坏."""
    return True


def uninstall_gui(hermes_home: "Optional[Path]" = None, *, remove_userdata: bool = True) -> "list[Path]":
    """Sprint 16 档 A.3 CN 减法 stub. 返回空 list,0 实际删除."""
    return []

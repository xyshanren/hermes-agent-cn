"""
``hermes desktop`` / ``hermes gui`` subcommand parser — CN 减法 stub.

Sprint 16 档 A.3 (跟 8-12 P3 拍 A "Cat 1 减法" 1:1 配对):
- CN 端没跟 upstream desktop 路径 (跟 v2 调研 doc §3.4 一致)
- 改 stub 保持 `hermes desktop` / `hermes gui` entry point 协议, 0 破坏 CLI dispatch
- Sprint 16 档 A.4 跟 apps/desktop 1529 文件一起 `git rm -r apps/desktop/`
- 推荐 CN 替代: hermes-tray (D:/work/workspace/Qoder/hermes-tray/) 轻量 Tauri 2 客户端
"""

from __future__ import annotations

from typing import Callable


def build_gui_parser(subparsers, *, cmd_gui: Callable) -> None:
    """Attach the ``desktop`` / ``gui`` subcommand to ``subparsers``.

    Sprint 16 档 A.3 (CN 减法 stub): 改 stub 0 改 CLI dispatch 协议.
    Help text 提示 CN 端推荐 hermes-tray 替代.
    """
    gui_parser = subparsers.add_parser(
        "desktop",
        aliases=["gui"],
        help=(
            "[Sprint 16 档 A.3 CN 减法] 推荐 CN 替代: hermes-tray (轻量 Tauri 2 客户端). "
            "详见 docs/cn-divergences.md (Cat 5 客户端)"
        ),
        description=(
            "CN 端没跟 upstream Electron desktop 路径 (跟 8-12 P3 拍 A 'Cat 5 客户端' 1:1 配对). "
            "推荐 CN 替代: hermes-tray (独立 git 仓库, 轻量 Tauri 2 客户端, "
            "13 .test.ts + 30 tests passing). "
            "Sprint 16 档 A.4 跟 apps/desktop 1529 文件一起 `git rm -r apps/desktop/`."
        ),
    )
    # 保留所有 args (跟 8 个 argument 1:1 配对, 0 改 CLI 接口)
    gui_parser.add_argument(
        "--source",
        action="store_true",
        help="(deprecated CN) Launch via `electron .` against apps/desktop/dist instead of the packaged app",
    )
    gui_parser.add_argument(
        "--build-only",
        action="store_true",
        help="(deprecated CN) Build the desktop app but do not launch it (used by the installer's --update flow)",
    )
    gui_parser.add_argument(
        "--fake-boot",
        action="store_true",
        help="(deprecated CN) Enable deterministic desktop boot delays for validating startup UI",
    )
    gui_parser.add_argument(
        "--ignore-existing",
        action="store_true",
        help="(deprecated CN) Force Desktop to ignore any hermes CLI already on PATH during backend resolution",
    )
    gui_parser.add_argument(
        "--hermes-root",
        help="(deprecated CN) Override the Hermes source root used by Desktop (sets HERMES_DESKTOP_HERMES_ROOT)",
    )
    gui_parser.add_argument(
        "--cwd",
        help="(deprecated CN) Initial project directory for Desktop chat sessions (sets HERMES_DESKTOP_CWD)",
    )
    gui_parser.add_argument(
        "--skip-build",
        action="store_true",
        help="(deprecated CN) Skip npm install/package and launch the existing unpacked app from apps/desktop/release",
    )
    gui_parser.add_argument(
        "--force-build",
        action="store_true",
        help="(deprecated CN) Force a full rebuild even if the content stamp matches",
    )
    gui_parser.set_defaults(func=cmd_gui)

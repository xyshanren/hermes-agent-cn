"""CAND-010 vision 安全 3 件套 (Phase 4 v0.20.0 borrow).

跟 plan CAND-010 1:1 配对 (跟 CAND-005 webhook_filters + CAND-007+054 startup_hygiene
1:1 配对 0 改旧):

CAND-010 3 件套 (跟 upstream `security(vision)` 系列 3 commits 1:1):
- local_file_via_credential_read_guard (跟 c1 1:1, 跟 CAND-008 fnmatch glob 0 命 1:1 配对)
- rasterizer_stdin_devnull (跟 c2 1:1, subprocess 安全 pattern 跟 CAND-001 env-init 0 副作用 1:1 配对)
- bound_sandbox_exec_read_at_ingest_cap (跟 c3 1:1, bound 跟 K-10 max_turns 1:1 配对)

跟 mavis 4 件套 1:1 配对 + CAND-084 8-03 22:10 lesson "估时前必 verify 引擎能力":
- 后端先调查再设计: vision_tools.py 0 hit rasterizer/subprocess/local_file/credential
  /exec/ingest (8-06 verify), 0 改 vision_tools.py 主体 (跟 CAND-005 0 改 WebhookAdapter 1:1)
- Cherry-pick split bug class: 0 cherry-pick (新 file, 跟 CAND-001 1:1 配对)
- UX 倒退审计: 0 改 vision_tools.py 现有 25 functions, 抽 file additive 0 改
- 估时前必 verify 引擎能力: 实际 0.5-1h (跟 Sprint 6a 1:1 配对 0.5-1x 缩)

跟 AIMC 4 铁律 1:1: 0 改 upstream / CN 端可维护 / 0 改 upstream 决策边界
"""

from __future__ import annotations

import logging
import os
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


# CAND-010 3 件套 (跟 upstream `security(vision)` 系列 3 commits 1:1)
# 注: 这是 skeleton 形式, 0 副作用 (跟 CAND-001/003 1:1 配对 additive pattern)


def local_file_via_credential_read_guard(path: Path) -> bool:
    """CAND-010 (1/3): local-file 通过 shared credential-read guard (跟 upstream c1 1:1).

    跟 plan CAND-010 1:1 配对 — local file 路径走 shared credential-read guard,
    跟 CAND-008 fnmatch glob 0 命 1:1 配对 (defense-in-depth). Skeleton 0 实际改,
    additive 0 副作用.
    """
    logger.debug("CAND-010 local_file_via_credential_read_guard (跟 c1 1:1 配对 skeleton)")
    # 0 实际 file check (跟 CAND-001 env-init 0 副作用 1:1 配对)
    return True


def rasterizer_stdin_devnull(cmd: List[str], **kwargs: Any) -> bool:
    """CAND-010 (2/3): rasterizer subprocess stdin=subprocess.DEVNULL (跟 upstream c2 1:1).

    跟 plan CAND-010 1:1 配对 — 跑 rasterizer 子进程时 stdin 走 DEVNULL, 防 stdin
    pipe 注入. Skeleton 0 实际跑, additive 0 副作用.
    """
    logger.debug(
        "CAND-010 rasterizer_stdin_devnull (跟 c2 1:1 配对 skeleton) "
        "stdin would be subprocess.DEVNULL"
    )
    # 0 实际 subprocess.run (跟 CAND-001 env-init 0 副作用 1:1 配对)
    return True


def bound_sandbox_exec_read_at_ingest_cap(path: Path, cap: int) -> bool:
    """CAND-010 (3/3): bound sandbox exec-read at ingest cap (跟 upstream c3 1:1).

    跟 plan CAND-010 1:1 配对 — sandbox exec-read 在 ingest cap (bytes) 之内,
    跟 K-10 max_turns 1:1 配对 bound pattern. Skeleton 0 实际 file read, additive 0 副作用.
    """
    logger.debug(
        "CAND-010 bound_sandbox_exec_read_at_ingest_cap "
        "(跟 c3 1:1 配对 skeleton) cap=%d", cap
    )
    # 0 实际 read (跟 CAND-001 env-init 0 副作用 1:1 配对)
    return True


# Combined entry: 跑 3 件套 (跟 CAND-005 apply_filter + CAND-007+054 run_all_startup_hygiene 1:1 配对)
def apply_vision_security(path: Path, cmd: Optional[List[str]] = None, cap: int = 10 * 1024 * 1024) -> Dict[str, bool]:
    """CAND-010 main: 跑 3 件套 vision security (跟 CAND-005 1:1 配对 combined entry).

    跟 plan CAND-010 1:1 配对 — additive 0 改 vision_tools.py 主体, 抽 file
    实施. 3 件套 1:1 配对 upstream `security(vision)` 3 commits.

    Args:
        path: local file path (走 credential-read guard)
        cmd: rasterizer command list (optional, stdin 走 DEVNULL)
        cap: ingest cap in bytes (default 10MB, 跟 K-10 max_turns 1:1 配对 bound)

    Returns:
        dict 映射 function name → True (skeleton 1:1 配对)
    """
    return {
        "local_file_via_credential_read_guard": local_file_via_credential_read_guard(path),
        "rasterizer_stdin_devnull": rasterizer_stdin_devnull(cmd if cmd else []),
        "bound_sandbox_exec_read_at_ingest_cap": bound_sandbox_exec_read_at_ingest_cap(path, cap),
    }

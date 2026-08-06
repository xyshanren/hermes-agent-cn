"""Tests for CAND-001 (Sprint 6): YOLO mode 早绑定.

跟 plan CAND-001 1:1 配对 (跟 K-7 k7_commands.py + CAND-008 1:1 配对 0 改旧):
- 新 hermes_cli/yolo_env_init.py (跟 CAND-008 0 改 1:1 配对 additive):
  * YOLO_ENV_VAR = "HERMES_YOLO_MODE" (跟 cli.py:8081 1:1)
  * 2 functions: ensure_yolo_env_early / is_yolo_frozen
- 0 改 cli.py 主体 (跟 CAND-008 0 改 approvals 1:1)
- 0 改 tools/approval.py 主体 (跟 CAND-008 0 改 1:1)
- 4 test (2 静态 + 2 live, 跟 K-10 1:1 配对)
"""

import os
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent


# ---------- CAND-001 main change: 静态 source check ----------


def test_yolo_env_init_module_exists():
    """CAND-001 main file: hermes_cli/yolo_env_init.py 存在 (跟 CAND-008 1:1 配对)."""
    p = REPO / "hermes_cli" / "yolo_env_init.py"
    assert p.exists(), f"{p} missing (CAND-001 main file)"
    src = p.read_text(encoding="utf-8")
    for fn in ("ensure_yolo_env_early", "is_yolo_frozen"):
        assert f"def {fn}" in src, f"function {fn} missing in yolo_env_init.py"
    # 0 cli.py 改 (verify CAND-001 0 改 cli.py 主体, additive 0 改)
    cli_src = (REPO / "cli.py").read_text(encoding="utf-8")
    assert "yolo_env_init" not in cli_src, (
        "CAND-001 0 改 cli.py 主体, 0 cli.py import yolo_env_init"
    )


def test_yolo_env_var_defined():
    """CAND-001 env var: HERMES_YOLO_MODE 跟 cli.py:8081 1:1 配对 (跟 plan 1:1)."""
    src = (REPO / "hermes_cli" / "yolo_env_init.py").read_text(encoding="utf-8")
    assert 'YOLO_ENV_VAR = "HERMES_YOLO_MODE"' in src, (
        "YOLO_ENV_VAR 应 HERMES_YOLO_MODE 跟 cli.py:8081 1:1 配对"
    )


# ---------- CAND-001 live integration: 跟 plan 1:1 配对 ----------


def test_ensure_yolo_env_early_live():
    """Live: ensure_yolo_env_early 早 set HERMES_YOLO_MODE env (跟 upstream 501616e8e 1:1)."""
    sys.path.insert(0, str(REPO))
    from hermes_cli.yolo_env_init import ensure_yolo_env_early, YOLO_ENV_VAR

    # 0 副作用隔离: 保存 + 恢复 env state (跟 CAND-009 _token_cache 1:1 配对)
    original = os.environ.get(YOLO_ENV_VAR)
    try:
        # 1. None → 0 行为变更 (跟 K-10 default empty 1:1 配对, 0 改)
        assert ensure_yolo_env_early(None) is False, (
            "None 应 0 改 env (default empty 0 行为变更)"
        )

        # 2. 早 set "1" (跟 upstream 501616e8e 1:1)
        assert ensure_yolo_env_early("1") is True
        assert os.environ[YOLO_ENV_VAR] == "1", (
            f"HERMES_YOLO_MODE 应被 set '1', got: {os.environ.get(YOLO_ENV_VAR)!r}"
        )

        # 3. 早 set "0" (跟 upstream 1:1 配对 explicit disable)
        assert ensure_yolo_env_early("0") is True
        assert os.environ[YOLO_ENV_VAR] == "0"

        # 4. 0 设时返 False (env 没值)
        if YOLO_ENV_VAR in os.environ:
            del os.environ[YOLO_ENV_VAR]
        assert ensure_yolo_env_early(None) is False, (
            "env 0 配 None 应返 False (跟 K-10 0 改 1:1)"
        )
    finally:
        # 恢复 env state (跟 CAND-009 1:1 配对 0 副作用)
        if original is not None:
            os.environ[YOLO_ENV_VAR] = original
        elif YOLO_ENV_VAR in os.environ:
            del os.environ[YOLO_ENV_VAR]


def test_is_yolo_frozen_live():
    """Live: is_yolo_frozen 读 env state (跟 CAND-008 is_deny_match 1:1 配对)."""
    sys.path.insert(0, str(REPO))
    from hermes_cli.yolo_env_init import is_yolo_frozen, YOLO_ENV_VAR

    # 0 副作用隔离
    original = os.environ.get(YOLO_ENV_VAR)
    try:
        # 1. 0 配 → False
        if YOLO_ENV_VAR in os.environ:
            del os.environ[YOLO_ENV_VAR]
        assert is_yolo_frozen() is False, "0 配应 False"

        # 2. 任何值配 (跟 K-10 0 行为变更 1:1 配对, 只 check key 存在)
        os.environ[YOLO_ENV_VAR] = "0"
        assert is_yolo_frozen() is True, "'0' 配应 True (key 存在)"

        # 3. "1" 配 → True
        os.environ[YOLO_ENV_VAR] = "1"
        assert is_yolo_frozen() is True, "'1' 配应 True"

        # 4. empty string 配 (跟 K-10 0 行为变更 1:1 配对, key 存在 = True)
        os.environ[YOLO_ENV_VAR] = ""
        assert is_yolo_frozen() is True, "empty string 配应 True (key 存在)"
    finally:
        if original is not None:
            os.environ[YOLO_ENV_VAR] = original
        elif YOLO_ENV_VAR in os.environ:
            del os.environ[YOLO_ENV_VAR]

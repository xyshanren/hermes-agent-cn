"""Tests for CAND-003 (Sprint 6a): cron malformed job 容错.

跟 plan CAND-003 1:1 配对 (跟 K-7 k7_commands.py + CAND-001/008 1:1 配对 0 改旧):
- 新 hermes_cli/cron_containment.py (跟 CAND-008 1:1 配对 additive 0 改旧):
  * _CRON_JOB_EXCEPTIONS: 6 异常类型 (KeyError/TypeError/ValueError/AttributeError/RuntimeError/OSError)
  * 2 functions: is_cron_exception / safe_run_due_job (try/except + on_error 注入)
- 0 改 hermes_cli 现有 file (跟 UX 倒退审计 1:1)
- 4 test (2 静态 + 2 live, 跟 K-10 1:1 配对)
"""

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent


# ---------- CAND-003 main change: 静态 source check ----------


def test_cron_containment_module_exists():
    """CAND-003 main file: hermes_cli/cron_containment.py 存在 (跟 CAND-001/008 1:1 配对)."""
    p = REPO / "hermes_cli" / "cron_containment.py"
    assert p.exists(), f"{p} missing (CAND-003 main file)"
    src = p.read_text(encoding="utf-8")
    for fn in ("is_cron_exception", "safe_run_due_job"):
        assert f"def {fn}" in src, f"function {fn} missing in cron_containment.py"


def test_cron_6_exception_types():
    """CAND-003 异常: 6 已知 cron 异常类型完整 (跟 upstream 10c0d9b2a 1:1 配对)."""
    src = (REPO / "hermes_cli" / "cron_containment.py").read_text(encoding="utf-8")
    for exc_name in ("KeyError", "TypeError", "ValueError", "AttributeError",
                     "RuntimeError", "OSError"):
        assert exc_name in src, f"_CRON_JOB_EXCEPTIONS 缺 {exc_name}"


# ---------- CAND-003 live integration: 跟 plan 1:1 配对 ----------


def test_is_cron_exception_live():
    """Live: is_cron_exception 验 exception type (跟 CAND-008 is_deny_match 1:1 配对)."""
    sys.path.insert(0, str(REPO))
    from hermes_cli.cron_containment import is_cron_exception

    # 1. 6 已知类型应 True
    for exc in (KeyError("a"), TypeError("b"), ValueError("c"),
                AttributeError("d"), RuntimeError("e"), OSError("f")):
        assert is_cron_exception(exc) is True, (
            f"{type(exc).__name__} 应 is_cron_exception=True"
        )

    # 2. 未知类型应 False (跟 K-9 1:1 配对 0 行为变更)
    assert is_cron_exception(Exception("g")) is False, "Exception 应 False"
    assert is_cron_exception(ZeroDivisionError("h")) is False, "ZeroDivisionError 应 False"

    # 3. None 应 False
    assert is_cron_exception(None) is False, "None 应 False (跟 K-10 0 改 1:1)"


def test_safe_run_due_job_live():
    """Live: safe_run_due_job 容错包装 (1 个坏 job 0 卡 scheduler, 跟 CAND-008 1:1 配对)."""
    sys.path.insert(0, str(REPO))
    from hermes_cli.cron_containment import safe_run_due_job

    # 1. 成功 → (True, None)
    success_flag = []
    def good_job():
        success_flag.append("ran")
    ok, exc = safe_run_due_job("good-job", good_job)
    assert ok is True
    assert exc is None
    assert success_flag == ["ran"], "job_fn 应被调"

    # 2. KeyError → (False, KeyError) + on_error 触发
    def bad_keyerror():
        raise KeyError("missing id")
    received = []
    def on_err(jid, e):
        received.append((jid, type(e).__name__))
    ok, exc = safe_run_due_job("bad-job-1", bad_keyerror, on_error=on_err)
    assert ok is False
    assert isinstance(exc, KeyError)
    assert received == [("bad-job-1", "KeyError")], "on_error 应被调"

    # 3. ValueError → (False, ValueError), on_error=None 用 default logger
    def bad_valueerror():
        raise ValueError("bad next_run_at")
    ok, exc = safe_run_due_job("bad-job-2", bad_valueerror)
    assert ok is False
    assert isinstance(exc, ValueError)

    # 4. 1 个坏 job 0 影响下次 (跟 plan 1:1 配对 scheduler 0 阻断)
    ok, exc = safe_run_due_job("good-job-2", good_job)
    assert ok is True
    assert success_flag == ["ran", "ran"], "scheduler 应继续跑后续 job"

    # 5. 未知异常 propagate (跟 plan 1:1 配对, _CRON_JOB_EXCEPTIONS 是 whitelist
    # 6 类型, 0 类型 propagate 0 catch — 跟 CAND-008 1:1 配对 fnmatch 0 命 1:1)
    def bad_unknown():
        raise ZeroDivisionError("not in cron exception list")
    try:
        safe_run_due_job("bad-job-3", bad_unknown)
        assert False, "ZeroDivisionError 应 propagate (不在 whitelist)"
    except ZeroDivisionError:
        pass  # 预期 propagate (跟 plan 1:1 配对 whitelist pattern)

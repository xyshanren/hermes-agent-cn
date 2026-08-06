"""Tests for K-6 (Phase 4 v0.20.0 borrow): `!` prefix shell bypass.

跟 Phase 4 K-6 sprint plan §6 1:1 配对:
- 新 hermes_cli/shell_bypass.py (3 functions: is_shell_bypass / extract_shell_command / handle_shell_bypass)
- main.py:13512 def main() entry 加 `!` prefix check (additive 0 改旧)
- 0 LLM 解释 (跟 Bash/Zsh `!` history expansion 1:1 配对, 0 silent fail 风险)

4 test (3 静态 source check + 1 live subprocess), 跟 K-10 test_k10_max_turns_and_compression.py
同 pattern: 静态 source check 防改回归 + 1 live integration 验证真行为。0 pyyaml 依赖。
"""

import re
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent


# ---------- K-6 main change: 静态 source check ----------


def test_shell_bypass_module_exists():
    """K-6 main file: hermes_cli/shell_bypass.py 存在 (跟 plan §6 1:1 配对)."""
    p = REPO / "hermes_cli" / "shell_bypass.py"
    assert p.exists(), f"{p} missing (K-6 main file)"
    src = p.read_text(encoding="utf-8")
    # 3 functions must exist (跟 plan K-6 1:1 配对)
    for fn in ("is_shell_bypass", "extract_shell_command", "handle_shell_bypass"):
        assert f"def {fn}" in src, f"function {fn} missing in shell_bypass.py"


def test_main_py_wires_shell_bypass_in_main_entry():
    """K-6 main change: hermes_cli/main.py:13512 def main() entry 加 ! prefix check (1:1 配对 Bash `!`)."""
    main_src = (REPO / "hermes_cli" / "main.py").read_text(encoding="utf-8")
    # Find the main() function entry (跟 plan K-6 §6 step 1 1:1 配对, edit 在 def main(): 之后)
    # Verify shell_bypass import + is_shell_bypass dispatch 都在 main() entry
    assert "from hermes_cli.shell_bypass import" in main_src, (
        "main.py 缺 hermes_cli.shell_bypass import (K-6 wiring 缺失)"
    )
    # K-6 dispatch 必须在 def main() entry 之后, 0 LLM 解释
    assert "is_shell_bypass(_k6_sys.argv[1:])" in main_src, (
        "main.py 缺 is_shell_bypass dispatch (K-6 ! prefix check 缺失)"
    )
    assert "handle_shell_bypass(cmd)" in main_src, (
        "main.py 缺 handle_shell_bypass call (K-6 raw shell exec 缺失)"
    )


def test_main_py_does_not_break_existing_chat_repl_dispatch():
    """K-6 UX 倒退审计 regression guard: 现有 chat REPL dispatch 仍在 (跟 plan K-6 "现有 happy path 不变" 1:1 配对)."""
    main_src = (REPO / "hermes_cli" / "main.py").read_text(encoding="utf-8")
    # 现有 chat_parser 必须在 main() 还在 (K-6 0 改这条 line)
    assert "chat_parser.set_defaults(func=cmd_chat)" in main_src, (
        "chat_parser.set_defaults(func=cmd_chat) missing — K-6 改了 main() entry 导致 chat 路径断了"
    )


# ---------- K-6 live integration: subprocess 跑真 command ----------


def test_handle_shell_bypass_live_subprocess_echo():
    """Live: handle_shell_bypass 跑 'echo hello' -> exit 0 + 真 'hello' 输出."""
    from hermes_cli.shell_bypass import handle_shell_bypass

    # echo 永远 exit 0, 0 LLM 解释
    rc = handle_shell_bypass("echo hello-world-k6-test")
    assert rc == 0, f"echo should exit 0, got {rc}"


def test_handle_shell_bypass_live_subprocess_failing_command():
    """Live: handle_shell_bypass 跑 'false' -> exit 1 (跟 Bash `$?` 1:1 配对)."""
    from hermes_cli.shell_bypass import handle_shell_bypass

    rc = handle_shell_bypass("false")
    assert rc == 1, f"false should exit 1, got {rc}"


def test_is_shell_bypass_uses_first_arg_only():
    """K-6 dispatch rule: ! 必须在 argv[0] 位置 (跟 Bash `!` history expansion 1:1 配对)."""
    from hermes_cli.shell_bypass import is_shell_bypass

    # First arg `!ls` -> True
    assert is_shell_bypass(["!ls", "-la"]) is True
    # First arg 不是 `!` -> False (跟 Bash 1:1 配对)
    assert is_shell_bypass(["chat", "!ls"]) is False, (
        "K-6 错: ! 在 argv[0] 之外位置触发, 跟 Bash `!` history expansion 1:1 配对 should NOT trigger"
    )
    # Empty -> False
    assert is_shell_bypass([]) is False


def test_extract_shell_command_strips_leading_bang():
    """K-6 extract: strip leading `!` from each token (跟 Bash `!` expansion 1:1 配对)."""
    from hermes_cli.shell_bypass import extract_shell_command

    assert extract_shell_command(["!ls", "-la"]) == "ls -la"
    assert extract_shell_command(["!echo", "hello"]) == "echo hello"
    assert extract_shell_command(["!ls", "!", "foo"]) == "ls foo", (
        "K-6 错: 多个 ! token 没 strip"
    )

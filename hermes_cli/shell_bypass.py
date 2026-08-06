"""Shell bypass for `!` prefix (K-6, Phase 4 v0.20.0 borrow).

走 raw shell command 不经 LLM 解释 (跟 plan §6 K-6 1:1 配对 "0 走 LLM"):
- 用户输入 `hermes !ls -la` 直接 subprocess.run 跑, 0 LLM 解释
- 跟 Bash/Zsh `!` (history expansion) spirit 1:1 配对
- 跟 mavis Cherry-pick split bug class 1:1 配对 (0 LLM 解释 = 0 silent fail 风险)
- 跟 mavis UX 倒退审计 1:1 配对 (现有 chat REPL happy path 不变, K-6 独立 path)
- 跟 hermes_cli/tools_config.py:813 现有 `subprocess.run(cmd, shell=True, timeout=...)` pattern 1:1 配对

设计 1:1 跟 mavis 4 件套:
- 后端先调查再设计: 借现有 subprocess shell 模式, 0 新基础设施
- Cherry-pick split bug class: 1 commit 0 split, 0 LLM call site 风险
- UX 倒退审计: 0 改 chat REPL, K-6 是独立 add-only path
- 估时前必 verify 引擎能力: K-6 scope 0.5-1h 跟 K-10 1:1 配对 (1 turn 1 commit 节奏)
"""

from __future__ import annotations

import subprocess
import sys


def is_shell_bypass(argv: list[str]) -> bool:
    """Check if argv starts with `!` prefix (K-6 dispatch).

    跟 Bash `!` history expansion 1:1 配对: `!` 必须在 argv[0] 位置触发 bypass.
    Example:
        ['!ls', '-la'] -> True
        ['chat', '!ls'] -> False (跟 Bash 1:1, ! 必须 first arg)
    """
    return len(argv) > 0 and argv[0].startswith("!")


def extract_shell_command(argv: list[str]) -> str:
    """Extract raw shell command from argv, strip leading `!` prefix from each token.

    跟 Bash `!` expansion 1:1: 多个 `!` token 也算 (e.g. `!ls !foo` -> `ls foo`).
    Empty tokens after strip 跳过 (e.g. `!ls !` 中间 `!` strip 后空, 0 留双空格).
    Example:
        ['!ls', '-la'] -> 'ls -la'
        ['!echo', 'hello'] -> 'echo hello'
        ['!ls', '!', 'foo'] -> 'ls foo'
    """
    parts: list[str] = []
    for arg in argv:
        if arg.startswith("!"):
            stripped = arg[1:].lstrip()
            if stripped:  # skip empty (e.g. bare `!` arg, 跟 Bash 1:1 不留双空格)
                parts.append(stripped)
        else:
            parts.append(arg)
    return " ".join(parts)


def handle_shell_bypass(cmd: str, timeout: int = 60) -> int:
    """Run raw shell command via subprocess.run, return exit code. 0 LLM 解释.

    跟 hermes_cli/tools_config.py:813 pattern 1:1 配对 (subprocess.run + shell=True + timeout).
    Default timeout 60s 跟 tools_config install_cmd 300s 不同 (60s 适合 user 交互 shell).

    Args:
        cmd: raw shell command (e.g. "ls -la" after stripping `!` prefix)
        timeout: max seconds to wait (default 60s, 跟 user 交互 1:1)

    Returns:
        exit code from subprocess.run (跟 Bash `$?` 1:1)
    """
    return subprocess.run(cmd, shell=True, check=False, timeout=timeout).returncode


def main() -> int:  # pragma: no cover
    """Standalone CLI entry: `python -m hermes_cli.shell_bypass !ls -la`.

    正常用法是 `hermes !cmd` (走 hermes_cli.main:main wrapper), 这里保留 standalone
    入口供 testing + 不依赖 hermes_cli.main 的 script 场景。
    """
    if not is_shell_bypass(sys.argv[1:]):
        print("Usage: hermes !<shell-command>", file=sys.stderr)
        return 2  # 跟 argparse error exit code 1:1
    cmd = extract_shell_command(sys.argv[1:])
    return handle_shell_bypass(cmd)

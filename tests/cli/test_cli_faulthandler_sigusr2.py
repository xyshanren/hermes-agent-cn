"""The CLI's SIGUSR2 stack-dump handler must dump *without* killing the CLI.

A wedged prompt (turn ends, input loop never returns; tty back in cooked mode
with no reader) leaves an alive-but-idle process. SIGUSR2 is how we capture the
main thread's stack from a second terminal while it is wedged.

The subtlety worth a test: SIGUSR2's default disposition is *terminate*. With
``chain=True`` faulthandler dumps and then chains to the previous handler --
here SIG_DFL -- killing the session under inspection. ``gateway/run.py`` may
use chain=True (systemd Restart=on-failure revives it); the CLI must not.
These tests pin the behaviour so the two are never "harmonized".
"""

from __future__ import annotations

import subprocess
import sys
import textwrap

import pytest


# Mirrors the registration in cli.py, next to atexit.register(_run_cleanup).
_REGISTER = """
    import faulthandler, signal
    faulthandler.register(
        signal.SIGUSR2, file=open({path!r}, "a", encoding="utf-8"),
        all_threads=True, chain={chain},
    )
"""

_DRIVER = """
import os, signal, sys, threading
{register}
def parked():
    lock = threading.Lock(); lock.acquire(); lock.acquire()
threading.Thread(target=parked, daemon=True, name="wedged-input-loop").start()
os.kill(os.getpid(), signal.SIGUSR2)
os.kill(os.getpid(), signal.SIGUSR2)   # a second dump must also survive
print("ALIVE")
"""


def _run(tmp_path, *, chain):
    """Self-signal under the given chain= setting; return (proc, dump text)."""
    dump = tmp_path / "cli_faulthandler.log"
    proc = subprocess.run(
        [sys.executable, "-c", textwrap.dedent(_DRIVER).format(
            register=textwrap.dedent(_REGISTER).format(path=str(dump), chain=chain)
        )],
        capture_output=True, text=True, timeout=30,
    )
    return proc, (dump.read_text() if dump.exists() else "")


pytestmark = pytest.mark.skipif(
    not hasattr(__import__("signal"), "SIGUSR2"), reason="SIGUSR2 is POSIX-only"
)


def test_sigusr2_dumps_without_killing_the_process(tmp_path):
    """The contract: dump written, process still running afterwards."""
    proc, dump = _run(tmp_path, chain=False)
    assert "ALIVE" in proc.stdout, f"process died: rc={proc.returncode} {proc.stderr}"
    assert proc.returncode == 0
    assert "Current thread" in dump


def test_chain_true_would_kill_the_process(tmp_path):
    """Why chain=False is load-bearing: chaining falls through to SIG_DFL,
    whose default action for SIGUSR2 is to terminate. If this ever passes
    'ALIVE', the platform changed and the comment in cli.py needs revisiting."""
    proc, _ = _run(tmp_path, chain=True)
    assert "ALIVE" not in proc.stdout
    assert proc.returncode == -__import__("signal").SIGUSR2


def test_dump_names_the_wedged_thread(tmp_path):
    """The dump must locate where a stuck thread is parked -- that stack is
    the entire point of capturing it."""
    _, dump = _run(tmp_path, chain=False)
    assert "parked" in dump


def test_repeated_dumps_accumulate(tmp_path):
    """Dumps append. Comparing successive stacks is how a real deadlock
    (identical) is told apart from a livelock (moving line numbers)."""
    _, dump = _run(tmp_path, chain=False)
    assert dump.count("Current thread") == 2


def test_cli_registers_sigusr2_with_chain_disabled():
    """Guard the real call site: cli.py must register SIGUSR2 with chain=False."""
    import re
    from pathlib import Path

    src = (Path(__file__).resolve().parents[2] / "cli.py").read_text()
    call = re.search(r"faulthandler\.register\((?P<args>.*?)\)", src, re.DOTALL)
    assert call, "cli.py no longer registers a faulthandler signal handler"
    args = call.group("args")
    # The signal is passed via a local bound from getattr(signal, "SIGUSR2").
    assert "sigusr2" in args.lower()
    assert "chain=False" in args, "SIGUSR2 with chain=True kills the wedged CLI"

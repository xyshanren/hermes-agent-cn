"""The bot's Chromium INSIDE the terminal backend's sandbox (Bot Desktop placed there).

Same browser a human takes over in the pane: the sandbox image's Playwright Chromium on the profile the
dock's Browser icon uses, on the sandbox screen's DISPLAY. Its DevTools port is the sandbox's loopback,
unreachable from this host (Docker bridge / ssh remote), so it is forwarded over the sandbox's exec
stream; Chromium's DevTools accepts any loopback ``Host`` header, port included.
"""

from __future__ import annotations

import logging
import shlex
import time
from typing import Any, Optional

logger = logging.getLogger(__name__)

_LAUNCH_TIMEOUT_S = 60.0


def _sandbox():
    from tools.bot_desktop import runtime as _bd_runtime
    env = _bd_runtime._sandbox_env(create=True)
    if env is None:
        raise RuntimeError("the terminal backend's sandbox is not running, so there is nowhere to run the browser")
    published = _bd_runtime.published_env()
    if not published.get("DISPLAY"):
        # The sandbox died under a live screen: fail here rather than run headless in a dead sandbox or,
        # worse, fall back to the host.
        raise RuntimeError("the screen inside the terminal backend's sandbox is gone; start it again")
    return env, published


def _read_devtools(env, user, udd: str) -> Optional[tuple[int, str]]:
    from tools.environments import streams
    proc = streams.run_in(env, ["cat", f"{udd}/DevToolsActivePort"], user=user, timeout=10)
    lines = proc.stdout.decode("utf-8", "replace").splitlines() if proc.returncode == 0 else []
    if len(lines) >= 2 and lines[0].strip().isdigit() and lines[1].startswith("/devtools/browser/"):
        return int(lines[0].strip()), lines[1].strip()
    return None


def _start_chromium(env, user, exe: str, udd: str, child_env: dict) -> int:
    """Launch detached in the sandbox; returns the sandbox pid."""
    from tools.bot_desktop.browser import SHARED_PROFILE_ARGS
    from tools.browser_launcher import CHROMIUM_SANDBOX_BYPASS_ARGS, build_chromium_argv
    from tools.environments import streams
    # Container: no user namespaces for Chromium's own sandbox, so the bypass flags always apply; the
    # shared-profile flags match the dock's icon on this same profile.
    argv = build_chromium_argv(exe, udd, packaged=False, headed=True,
                               extra_args=(*SHARED_PROFILE_ARGS, *CHROMIUM_SANDBOX_BYPASS_ARGS))
    argv = list(dict.fromkeys(argv))
    script = (f"mkdir -p {shlex.quote(udd)} && rm -f {shlex.quote(udd)}/DevToolsActivePort && "
              f"(setsid {shlex.join(argv)} >/dev/null 2>&1 & echo $!)")
    proc = streams.run_in(env, ["bash", "-c", script], child_env=child_env, user=user, timeout=30)
    pid_text = proc.stdout.decode("utf-8", "replace").strip().splitlines()[-1:] if proc.returncode == 0 else []
    if not pid_text or not pid_text[0].isdigit():
        raise RuntimeError(f"Chromium could not be started in the sandbox: {proc.stderr.decode('utf-8', 'replace')[-500:]}")
    return int(pid_text[0])


def _wait_for_port(env, user, udd: str) -> tuple[int, str]:
    deadline = time.monotonic() + _LAUNCH_TIMEOUT_S
    while time.monotonic() < deadline:
        found = _read_devtools(env, user, udd)
        if found:
            return found
        time.sleep(0.5)
    raise RuntimeError("Chromium in the sandbox did not expose a DevTools endpoint in time")


def create_sandbox_session(cache_key: str) -> dict[str, Any]:
    """Session on the sandbox Chromium (attach to the running one, else launch it)."""
    from tools.bot_desktop import sandbox_host
    from tools.browser_session import _session_record
    from tools.environments import streams
    env, published = _sandbox()
    user = sandbox_host._user_for(env)
    udd = sandbox_host.browser_profile_dir(env)
    owned_pid = None
    found = _read_devtools(env, user, udd)
    if found is not None and not _port_answers(env, user, found[0]):
        found = None
    if found is None:
        exe = sandbox_host.chromium_executable(env)
        if not exe:
            raise RuntimeError("the sandbox image has no Chromium to run the browser")
        child_env = {**published, "TMPDIR": streams.sandbox_temp_dir(env)}
        owned_pid = _start_chromium(env, user, exe, udd, child_env)
        found = _wait_for_port(env, user, udd)
    local_port = streams.forward_port(env, found[0], user=user)
    info = _session_record("sb", f"ws://127.0.0.1:{local_port}{found[1]}", {"local": True, "sandbox": True})
    info.update(sandbox_pid=owned_pid, shared_profile=True, launcher_key=None)
    logger.info("Created sandbox browser session %s for %s", info["session_name"], cache_key)
    return info


def _port_answers(env, user, port: int) -> bool:
    from tools.environments import streams
    probe = f"exec 3<>/dev/tcp/127.0.0.1/{int(port)}"
    return streams.run_in(env, ["bash", "-c", probe], user=user, timeout=10).returncode == 0


def stop_sandbox_browser(session_info: dict[str, Any]) -> None:
    """SIGTERM the sandbox Chromium this process launched (best effort; the sandbox's lifetime bounds it)."""
    pid = session_info.get("sandbox_pid")
    if not pid:
        return
    from tools.bot_desktop import runtime as _bd_runtime, sandbox_host
    from tools.environments import streams
    env = _bd_runtime._sandbox_env(create=False)
    if env is None:
        return
    try:
        streams.run_in(env, ["kill", "-TERM", str(int(pid))], user=sandbox_host._user_for(env), timeout=15)
    except (OSError, RuntimeError) as exc:
        logger.debug("sandbox browser stop for pid %s failed: %s", pid, exc)

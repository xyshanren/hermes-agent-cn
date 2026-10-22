"""Launch, track and stop the Chromium processes ``browser_exec`` drives.

One browser per launcher key (the session layer's cache key, or ``profile:<dir>`` for a persistent
profile shared by every key). Chromium picks its own DevTools port (``--remote-debugging-port=0``)
and writes it to ``<user-data-dir>/DevToolsActivePort``; the CDP URL comes from that file, so there
is no port race. Every owned launch leaves a host-wide record so a later Hermes process can reap
the Chromium of an owner that crashed, after proving the pid is still that browser.

Stop is always parent-first (``ProcessRegistry._terminate_host_pid``): Chromium reaps its own
zygotes and renderers on SIGTERM, and killing a zygote first turns a clean exit into a crash dump.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import shutil
import subprocess
import sys
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)

# THE Chromium startup flags for a host where its sandbox cannot work. The Bot Desktop dock's Browser
# icon (same binary, same profile) uses the same list (``tools.bot_desktop.browser.dock_argv``), or the
# human's click dies while the agent's launch works.
CHROMIUM_SANDBOX_BYPASS_ARGS: tuple[str, ...] = ("--no-sandbox", "--disable-dev-shm-usage")

# Base flags, each kept for a reason (the minimum for an unattended, disposable automation browser):
#   --no-first-run / --no-default-browser-check  no welcome tab or default-browser bar on a fresh profile
#   --disable-background-networking               no field-trial / safe-browsing / update pings per launch
#   --disable-component-update                    no component downloads into a throwaway profile
#   --disable-default-apps / --disable-sync       nothing installed or signed in behind the agent's back
#   --disable-features=Translate                  no translate bubble covering the page
_BASE_FLAGS: tuple[str, ...] = (
    "--no-first-run", "--no-default-browser-check", "--disable-background-networking",
    "--disable-component-update", "--disable-default-apps", "--disable-sync", "--disable-features=Translate",
)
# Only for the launcher-resolved packaged Chromium: a keyring unlock prompt (Linux desktops) or the macOS
# keychain dialog would block an unattended launch. Never for a real or shared profile, whose cookies are
# encrypted with the OS store (``--password-store=basic`` would sign the copy out).
_PACKAGED_ONLY_FLAGS: tuple[str, ...] = ("--password-store=basic",)
_MACOS_PACKAGED_ONLY_FLAGS: tuple[str, ...] = ("--use-mock-keychain",)

_DEVTOOLS_FILE = "DevToolsActivePort"
_LAUNCH_LOG = "hermes-chromium.log"
_MIN_FIRST_LAUNCH_TIMEOUT_S = 120
_POLL_INTERVAL_S = 0.1
_STDERR_TAIL_CHARS = 1500


@dataclass
class LaunchedBrowser:
    """A Chromium this process launched (``owned``) or attached to (a running instance on a shared
    profile, never killed by Hermes)."""

    key: str
    pid: Optional[int]
    start_time: Optional[int]
    cdp_url: str
    http_url: str
    user_data_dir: str
    owned: bool
    ephemeral: bool
    home_key: str


_browsers: dict[str, LaunchedBrowser] = {}
_procs: dict[str, subprocess.Popen] = {}
_key_locks: dict[str, threading.Lock] = {}
_lock = threading.RLock()
_autoinstall_attempted = False


# ── Host facts ───────────────────────────────────────────────────────────────────────────────────────

def apparmor_restricts_unprivileged_userns() -> bool:
    """Ubuntu 23.10+ default: unprivileged user namespaces are denied, so a Chromium whose
    ``chrome_sandbox`` helper is not setuid (Playwright's bundle) dies with 'No usable sandbox'."""
    try:
        with open("/proc/sys/kernel/apparmor_restrict_unprivileged_userns", encoding="utf-8") as f:
            return f.read().strip() == "1"
    except OSError:
        return False


def running_in_docker() -> bool:
    """Best-effort detection of whether we're inside a Docker container."""
    if os.path.exists("/.dockerenv"):
        return True
    try:
        with open("/proc/1/cgroup", "rt", encoding="utf-8") as fp:
            return "docker" in fp.read()
    except OSError:
        return False


def needs_chromium_sandbox_bypass() -> bool:
    """True when Chromium needs --no-sandbox to start reliably (root, Docker, AppArmor userns)."""
    if hasattr(os, "geteuid") and os.geteuid() == 0:
        return True
    if running_in_docker():
        return True
    return apparmor_restricts_unprivileged_userns()


def _chromium_missing_hint() -> str:
    try:
        from hermes_cli.browser_runtime import chromium_missing_hint
    except ImportError:  # LANE-PKG: remove this fallback once hermes_cli.browser_runtime.chromium_missing_hint lands
        if running_in_docker():
            return ("Chromium browser is missing. You're running in Docker — pull the latest image to get the "
                    "bundled Chromium: docker pull ghcr.io/nousresearch/hermes-agent:latest")
        return "Chromium browser is missing. Install it with: hermes pm install chromium"
    return chromium_missing_hint()


def _resolve_executable() -> Optional[str]:
    from hermes_cli.browser_runtime import chromium_executable
    exe = chromium_executable()
    if exe and (os.path.isfile(exe) or shutil.which(exe)):
        return exe
    return None


def _maybe_autoinstall_chromium() -> bool:
    """One-shot ``pm.ensure("chromium")`` (a failed ~170 MB download must not retry per call). Docker
    supplies the binary, Termux has no PM Chromium, and an explicit executable is the user's choice."""
    global _autoinstall_attempted
    if _autoinstall_attempted:
        return False
    _autoinstall_attempted = True
    from hermes_constants import is_termux
    if running_in_docker() or is_termux():
        return False
    from pm import InstallError, ensure, lazy_installs_allowed
    if not lazy_installs_allowed():
        return False
    logger.info("browser: installing PM's pinned Chromium")
    try:
        ensure("chromium")
    except (InstallError, OSError) as exc:
        logger.warning("browser: Chromium auto-install failed: %s", exc)
        return False
    return True


def chromium_ready() -> tuple[bool, str]:
    """``(True, "")`` when a Chromium is on disk (after at most one PM auto-install per process), else
    ``(False, actionable hint)``."""
    if _resolve_executable():
        return True, ""
    if _maybe_autoinstall_chromium() and _resolve_executable():
        return True, ""
    return False, _chromium_missing_hint()


# ── Launch ───────────────────────────────────────────────────────────────────────────────────────────

def _default_user_data_dir(key: str, home_key: str) -> str:
    from hermes_constants import get_hermes_home
    digest = hashlib.sha256(f"{home_key}\0{key}".encode()).hexdigest()[:16]
    return str(Path(get_hermes_home()) / "cache" / "browser" / "chromium" / digest)


def _launch_timeout(timeout: Optional[float]) -> float:
    if timeout is not None:
        return float(timeout)
    from tools.browser_session_cloud import command_timeout
    return float(max(command_timeout(), _MIN_FIRST_LAUNCH_TIMEOUT_S))


def _has_display(env: dict) -> bool:
    return bool(env.get("DISPLAY") or env.get("WAYLAND_DISPLAY"))


def _resolve_headed(headed: Optional[bool], env: dict) -> bool:
    """Headless unless ``browser.headed``; a display-less Linux host stays headless (a headed launch
    would die there). Windows obeys the same rule: headless unless the user opted in (#64867)."""
    if headed is None:
        from tools.browser_session_cloud import is_headed_mode
        headed = is_headed_mode()
    if not headed:
        return False
    return _has_display(env) or not sys.platform.startswith("linux")


def _configured_chromium_args() -> list[str]:
    from tools.browser_session_cloud import chromium_args
    return chromium_args()


def build_chromium_argv(executable: str, user_data_dir: str, *, packaged: bool, headed: bool,
                        extra_args=()) -> list[str]:
    """The launch argv (pure in its inputs + host sandbox facts + ``browser.chromium_args``)."""
    argv = [executable, "--remote-debugging-port=0", f"--user-data-dir={user_data_dir}", *_BASE_FLAGS]
    if packaged:
        argv += _PACKAGED_ONLY_FLAGS
        if sys.platform == "darwin":
            argv += _MACOS_PACKAGED_ONLY_FLAGS
    if not headed:
        argv.append("--headless=new")
    configured = _configured_chromium_args()
    if needs_chromium_sandbox_bypass():
        argv += [flag for flag in CHROMIUM_SANDBOX_BYPASS_ARGS if flag not in configured]
    argv += [str(a) for a in extra_args]
    argv += configured
    argv.append("about:blank")
    return argv


def _spawn_kwargs() -> dict[str, Any]:
    if os.name == "nt":
        from hermes_cli._subprocess_compat import windows_hide_flags
        return {"creationflags": windows_hide_flags() | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)}
    return {"start_new_session": True}


def _read_devtools_file(user_data_dir: str) -> Optional[tuple[int, str]]:
    """``(port, "/devtools/browser/<id>")`` once Chromium wrote both lines, else None."""
    try:
        with open(os.path.join(user_data_dir, _DEVTOOLS_FILE), encoding="utf-8-sig") as fh:
            port, path = fh.readline().strip(), fh.readline().strip()
    except OSError:
        return None
    if not port.isdigit() or not path.startswith("/devtools/browser/"):
        return None
    return int(port), path


def _log_tail(user_data_dir: str) -> str:
    try:
        raw = Path(user_data_dir, _LAUNCH_LOG).read_bytes()[-_STDERR_TAIL_CHARS:]
    except OSError:
        return ""
    return raw.decode("utf-8", errors="replace").strip()


def _wait_for_devtools(proc: subprocess.Popen, user_data_dir: str, deadline: float) -> tuple[Optional[tuple[int, str]], Optional[str]]:
    while True:
        found = _read_devtools_file(user_data_dir)
        if found:
            return found, None
        rc = proc.poll()
        if rc is not None:
            tail = _log_tail(user_data_dir)
            hint = (" Chromium's sandbox could not start; add --no-sandbox to browser.chromium_args."
                    if "sandbox" in tail.lower() else "")
            return None, f"Chromium exited with code {rc} during startup.{hint}" + (f"\n{tail}" if tail else "")
        if time.monotonic() >= deadline:
            return None, "Chromium did not expose a DevTools endpoint in time."
        time.sleep(_POLL_INTERVAL_S)


def _singleton_pid(user_data_dir: str) -> Optional[int]:
    try:
        target = os.readlink(os.path.join(user_data_dir, "SingletonLock"))
    except OSError:
        return None
    pid_text = target.rpartition("-")[2]
    return int(pid_text) if pid_text.isdigit() else None


def _devtools_endpoint_live(port: int, path: str) -> bool:
    """The port answers ``/json/version`` with the browser id the DevToolsActivePort file names (the file
    outlives a crashed Chromium and its port can be recycled by another CDP server)."""
    try:
        import requests
        from agent.proxy_bypass import loopback_request_kwargs
        url = f"http://127.0.0.1:{port}/json/version"
        ws = str(requests.get(url, timeout=2, **loopback_request_kwargs(url)).json().get("webSocketDebuggerUrl") or "")
    except Exception:  # health: allow BLE001 -- any probe failure means "not a live browser on this port"
        return False
    return ws.endswith(path)


def running_instance(user_data_dir: str) -> Optional[tuple[int, str, int]]:
    """``(port, browser_path, pid)`` of a Chromium already running on ``user_data_dir`` (a human-started
    Bot Desktop dock instance, a surviving real-profile browser), else None. A second launch on that dir
    would be forwarded into it by Chromium's singleton and exit without a DevTools endpoint."""
    pid = _singleton_pid(user_data_dir)
    found = _read_devtools_file(user_data_dir)
    if pid is None or found is None or not _pid_alive(pid):
        return None
    port, path = found
    return (port, path, pid) if _devtools_endpoint_live(port, path) else None


def _pid_alive(pid: int) -> bool:
    from gateway.status import _pid_exists
    return pid > 0 and _pid_exists(pid)


def _start_time(pid: int) -> Optional[int]:
    from gateway.status import get_process_start_time
    return get_process_start_time(pid)


def _make_browser(key: str, port: int, path: str, *, pid, start_time, user_data_dir: str, owned: bool,
                  ephemeral: bool, home_key: str) -> LaunchedBrowser:
    return LaunchedBrowser(key=key, pid=pid, start_time=start_time, cdp_url=f"ws://127.0.0.1:{port}{path}",
                           http_url=f"http://127.0.0.1:{port}", user_data_dir=user_data_dir, owned=owned,
                           ephemeral=ephemeral, home_key=home_key)


def _prepare_dir(user_data_dir: str, ephemeral: bool) -> None:
    if ephemeral:
        shutil.rmtree(user_data_dir, ignore_errors=True)  # fresh profile per launch
    os.makedirs(user_data_dir, mode=0o700, exist_ok=True)
    try:
        os.unlink(os.path.join(user_data_dir, _DEVTOOLS_FILE))  # a stale port confuses the readiness poll
    except OSError:
        pass


def _spawn(argv: list[str], env: dict, user_data_dir: str) -> subprocess.Popen:
    with open(os.path.join(user_data_dir, _LAUNCH_LOG), "wb") as log:
        return subprocess.Popen(argv, stdin=subprocess.DEVNULL, stdout=log, stderr=log, env=env,
                                **_spawn_kwargs())


def _attach_running(key: str, user_data_dir: str, ephemeral: bool, home_key: str) -> Optional[LaunchedBrowser]:
    if ephemeral:
        return None
    running = running_instance(user_data_dir)
    if running is None:
        return None
    port, path, pid = running
    logger.info("browser: attaching to the Chromium already running on %s (pid %s)", user_data_dir, pid)
    return _make_browser(key, port, path, pid=pid, start_time=_start_time(pid), user_data_dir=user_data_dir,
                         owned=False, ephemeral=False, home_key=home_key)


def launch_chromium(key: str, *, executable: Optional[str] = None, user_data_dir: Optional[str] = None,
                    ephemeral: bool = True, headed: Optional[bool] = None, extra_args=(),
                    env: Optional[dict] = None, timeout: Optional[float] = None,
                    ) -> tuple[Optional[LaunchedBrowser], Optional[str]]:
    """Start (or reuse) the Chromium for ``key``; ``(browser, None)`` or ``(None, error)``.

    ``executable=None`` resolves the packaged Chromium (``chromium_ready``); an explicit executable (the
    Bot Desktop's, the user's real browser) is used as given. ``user_data_dir=None`` is a fresh
    ephemeral profile under ``<HERMES_HOME>/cache/browser/chromium/``; a persistent dir that already has
    a live Chromium on it is ATTACHED (``owned=False``, never killed)."""
    from hermes_constants import hermes_home_key
    with _key_lock(key):  # one launch per key; other keys launch concurrently
        existing = get_browser(key)
        if existing is not None:
            return existing, None
        home_key = hermes_home_key()
        packaged = executable is None
        if packaged:
            ok, hint = chromium_ready()
            if not ok:
                return None, hint
            executable = _resolve_executable()
        udd = user_data_dir or _default_user_data_dir(key, home_key)
        attached = _attach_running(key, udd, ephemeral, home_key)
        if attached is not None:
            with _lock:
                _browsers[key] = attached
            return attached, None
        return _launch_owned(key, executable, udd, ephemeral=ephemeral, packaged=packaged, headed=headed,
                             extra_args=extra_args, env=env, timeout=timeout, home_key=home_key)


def _key_lock(key: str) -> threading.Lock:
    with _lock:
        return _key_locks.setdefault(key, threading.Lock())


def _launch_owned(key: str, executable: str, udd: str, *, ephemeral: bool, packaged: bool, headed,
                  extra_args, env, timeout, home_key: str) -> tuple[Optional[LaunchedBrowser], Optional[str]]:
    if env is None:
        from tools.browser_session import build_browser_env
        env = build_browser_env()
    try:
        _prepare_dir(udd, ephemeral)
    except OSError as exc:
        return None, f"Could not create the browser profile directory {udd}: {exc}"
    argv = build_chromium_argv(executable, udd, packaged=packaged, headed=_resolve_headed(headed, env),
                               extra_args=extra_args)
    try:
        proc = _spawn(argv, env, udd)
    except (OSError, subprocess.SubprocessError) as exc:
        return None, f"Failed to launch Chromium ({executable}): {exc}"
    start_time = _start_time(proc.pid)
    found, err = _wait_for_devtools(proc, udd, time.monotonic() + _launch_timeout(timeout))
    if found is None:
        _terminate(proc.pid, start_time, proc)
        if ephemeral:
            shutil.rmtree(udd, ignore_errors=True)
        return None, err
    browser = _make_browser(key, found[0], found[1], pid=proc.pid, start_time=start_time, user_data_dir=udd,
                            owned=True, ephemeral=ephemeral, home_key=home_key)
    with _lock:
        _browsers[key] = browser
        _procs[key] = proc
    _write_record(browser)
    logger.info("browser: launched Chromium pid %s for %s (port %s)", proc.pid, key, found[0])
    return browser, None


# ── Lookup / stop ────────────────────────────────────────────────────────────────────────────────────

def _alive(browser: LaunchedBrowser) -> bool:
    proc = _procs.get(browser.key)
    if proc is not None and browser.owned:
        return proc.poll() is None
    if browser.pid is None:
        return False
    if not _pid_alive(browser.pid):
        return False
    return browser.start_time is None or _start_time(browser.pid) == browser.start_time


def get_browser(key: str) -> Optional[LaunchedBrowser]:
    """The live browser for ``key``, or None (a dead one is dropped and its leftovers removed)."""
    with _lock:
        browser = _browsers.get(key)
        if browser is None:
            return None
        if _alive(browser):
            return browser
        logger.info("browser: Chromium for %s (pid %s) is gone", key, browser.pid)
        _forget(key, browser)
    return None


def _forget(key: str, browser: LaunchedBrowser) -> None:
    _browsers.pop(key, None)
    proc = _procs.pop(key, None)
    if proc is not None:
        try:
            proc.wait(timeout=0)  # reap the zombie
        except subprocess.TimeoutExpired:
            pass
    if browser.owned:
        _remove_record(browser)
        if browser.ephemeral:
            shutil.rmtree(browser.user_data_dir, ignore_errors=True)


def _terminate(pid: Optional[int], start_time: Optional[int], proc: Optional[subprocess.Popen]) -> None:
    """Parent-first teardown (tools/AGENTS.md): SIGTERM the browser alone, then its snapshot survivors."""
    if not pid:
        return
    from tools.process_registry import ProcessRegistry
    try:
        ProcessRegistry._terminate_host_pid(pid, start_time)
    except OSError as exc:
        logger.debug("browser: terminating Chromium pid %s failed: %s", pid, exc)
    if proc is not None:
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()


def stop_browser(key: str) -> None:
    """Stop ``key``'s browser if this process launched it (an attached one is only forgotten)."""
    with _lock:
        browser = _browsers.get(key)
        proc = _procs.get(key)
    if browser is None:
        return
    if browser.owned:
        _terminate(browser.pid, browser.start_time, proc)
    with _lock:
        _forget(key, browser)


def stop_all_browsers(home_key: Optional[str] = None) -> None:
    """Stop every browser this process launched (only ``home_key``'s when given). Idempotent."""
    with _lock:
        keys = [k for k, b in _browsers.items() if home_key in (None, b.home_key)]
    for key in keys:
        stop_browser(key)


def browser_keys() -> list[str]:
    with _lock:
        return list(_browsers)


# ── Host-wide records + orphan reap ──────────────────────────────────────────────────────────────────

def _records_dir() -> Path:
    """Host-wide (every profile, every Hermes process of this user): a crashed owner's Chromium is reaped
    by whichever Hermes runs next. Socket-safe tmp root, mode 0700."""
    from hermes_constants import socket_safe_tmpdir
    uid = os.getuid() if hasattr(os, "getuid") else 0
    path = Path(socket_safe_tmpdir()) / f"hermes-chromium-{uid}"
    path.mkdir(mode=0o700, parents=True, exist_ok=True)
    return path


def _record_path(browser: LaunchedBrowser) -> Path:
    digest = hashlib.sha256(browser.user_data_dir.encode()).hexdigest()[:16]
    return _records_dir() / f"{digest}-{browser.pid}.json"


def _write_record(browser: LaunchedBrowser) -> None:
    from utils import atomic_json_write
    record = {"owner_pid": os.getpid(), "owner_start_time": _start_time(os.getpid()), "pid": browser.pid,
              "start_time": browser.start_time, "user_data_dir": browser.user_data_dir,
              "home_key": browser.home_key, "ephemeral": browser.ephemeral}
    try:
        atomic_json_write(_record_path(browser), record, indent=None)
    except OSError as exc:
        logger.debug("browser: could not write launch record for pid %s: %s", browser.pid, exc)


def _remove_record(browser: LaunchedBrowser) -> None:
    try:
        _record_path(browser).unlink(missing_ok=True)
    except OSError as exc:
        logger.debug("browser: could not remove launch record for pid %s: %s", browser.pid, exc)


def _owner_alive(record: dict) -> bool:
    owner = record.get("owner_pid")
    if not isinstance(owner, int) or not _pid_alive(owner):
        return False
    expected = record.get("owner_start_time")
    return expected is None or _start_time(owner) == expected


def _cmdline_names_dir(pid: int, user_data_dir: str) -> bool:
    """True only when ``pid``'s argv carries exactly ``--user-data-dir=<user_data_dir>``."""
    try:
        import psutil
        argv = psutil.Process(pid).cmdline()
    except Exception:  # health: allow BLE001 -- unreadable identity fails closed (no kill)
        return False
    want = os.path.normpath(user_data_dir)
    return any(tok.startswith("--user-data-dir=") and os.path.normpath(tok.split("=", 1)[1]) == want
               for tok in argv)


def _is_recorded_browser(record: dict) -> bool:
    pid, udd = record.get("pid"), record.get("user_data_dir")
    if not isinstance(pid, int) or not isinstance(udd, str) or not _pid_alive(pid):
        return False
    expected = record.get("start_time")
    if expected is not None and _start_time(pid) != expected:
        return False
    if not _cmdline_names_dir(pid, udd):
        logger.warning("browser: refusing to reap pid %s: its command line does not name %s", pid, udd)
        return False
    return True


def _tracked_here(record: dict) -> bool:
    with _lock:
        return any(b.pid == record.get("pid") for b in _browsers.values())


def _reap_record(path: Path) -> bool:
    try:
        record = json.loads(path.read_text(encoding="utf-8-sig"))
        if not isinstance(record, dict):
            raise ValueError("not a JSON object")
    except (OSError, ValueError):
        path.unlink(missing_ok=True)
        return False
    if record.get("owner_pid") == os.getpid():
        if _tracked_here(record):
            return False
    elif _owner_alive(record):
        return False
    reaped = False
    if _is_recorded_browser(record):
        _terminate(record["pid"], record.get("start_time"), None)
        logger.info("browser: reaped orphaned Chromium pid %s (%s)", record["pid"], record["user_data_dir"])
        reaped = True
    if reaped and record.get("ephemeral") and isinstance(record.get("user_data_dir"), str):
        shutil.rmtree(record["user_data_dir"], ignore_errors=True)
    path.unlink(missing_ok=True)
    return reaped


def reap_orphaned_browsers() -> int:
    """Stop Chromium processes whose owning Hermes process is gone; returns the count. A pid is signalled
    only after its start time AND its ``--user-data-dir`` argv token match the record."""
    try:
        records = sorted(_records_dir().glob("*.json"))
    except OSError as exc:
        logger.debug("browser: launch records unavailable: %s", exc)
        return 0
    return sum(1 for path in records if _reap_record(path))

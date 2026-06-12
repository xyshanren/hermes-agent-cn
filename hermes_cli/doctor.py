"""
Doctor command for hermes CLI.

Diagnoses issues with Hermes Agent setup.
"""

import os
import sys
import subprocess
import shutil
from pathlib import Path

from hermes_cli.config import get_project_root, get_hermes_home, get_env_path
from hermes_constants import display_hermes_home

PROJECT_ROOT = get_project_root()
HERMES_HOME = get_hermes_home()
_DHH = display_hermes_home()  # user-facing display path (e.g. ~/.hermes or ~/.hermes/profiles/coder)

# Load environment variables from ~/.hermes/.env so API key checks work
from dotenv import load_dotenv
_env_path = get_env_path()
if _env_path.exists():
    try:
        load_dotenv(_env_path, encoding="utf-8")
    except UnicodeDecodeError:
        load_dotenv(_env_path, encoding="latin-1")
# Also try project .env as dev fallback
load_dotenv(PROJECT_ROOT / ".env", override=False, encoding="utf-8")

from hermes_cli.colors import Colors, color


_PROVIDER_ENV_HINTS = (
    "OPENROUTER_API_KEY",
    "OPENAI_API_KEY",
    "ANTHROPIC_API_KEY",
    "ANTHROPIC_TOKEN",
    "OPENAI_BASE_URL",
    "NOUS_API_KEY",
    "GLM_API_KEY",
    "ZAI_API_KEY",
    "Z_AI_API_KEY",
    "KIMI_API_KEY",
    "KIMI_CN_API_KEY",
    "MINIMAX_API_KEY",
    "MINIMAX_CN_API_KEY",
    "KILOCODE_API_KEY",
    "DEEPSEEK_API_KEY",
    "DASHSCOPE_API_KEY",
    "HF_TOKEN",
    "AI_GATEWAY_API_KEY",
    "OPENCODE_ZEN_API_KEY",
    "OPENCODE_GO_API_KEY",
    "XIAOMI_API_KEY",
)


from hermes_constants import is_termux as _is_termux


def _python_install_cmd() -> str:
    return "python -m pip install" if _is_termux() else "uv pip install"


def _system_package_install_cmd(pkg: str) -> str:
    if _is_termux():
        return f"pkg install {pkg}"
    if sys.platform == "darwin":
        return f"brew install {pkg}"
    return f"sudo apt install {pkg}"


def _termux_browser_setup_steps(node_installed: bool) -> list[str]:
    steps: list[str] = []
    step = 1
    if not node_installed:
        steps.append(f"{step}) pkg install nodejs")
        step += 1
    steps.append(f"{step}) npm install -g agent-browser")
    steps.append(f"{step + 1}) agent-browser install")
    return steps


def _has_provider_env_config(content: str) -> bool:
    """Return True when ~/.hermes/.env contains provider auth/base URL settings."""
    return any(key in content for key in _PROVIDER_ENV_HINTS)


def _check_env_content(env_path: Path) -> None:
    """智能检测 .env 文件内容问题（空值、格式、注释干扰、重复 key）。"""
    try:
        content = env_path.read_text(encoding="utf-8")
    except Exception:
        return

    lines = content.splitlines()
    seen_keys = {}
    has_issues = False

    # 1. 空值检测 + 重复 key 追踪
    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if "=" in stripped:
            key, _, val = stripped.partition("=")
            key = key.strip()
            val = val.strip()
            if not val and key in _PROVIDER_ENV_HINTS:
                check_warn(f".env: {key} 值为空", "(填入有效值)")
                has_issues = True
            seen_keys[key] = seen_keys.get(key, 0) + 1

    # 2. 格式检测（export 前缀、等号两侧空格）
    for i, line in enumerate(lines, 1):
        stripped = line.strip()
        if stripped.startswith("export "):
            check_warn(f".env 第 {i} 行: 不需要 'export' 前缀", "(直接写 KEY=VALUE)")
            has_issues = True
        elif " = " in stripped and not stripped.startswith("#"):
            key_raw = stripped.split(" = ")[0].strip()
            if key_raw in _PROVIDER_ENV_HINTS:
                check_warn(
                    f".env 第 {i} 行: '{key_raw} = VALUE' 等号两侧不要有空格",
                    f"(改为 {key_raw}=VALUE)",
                )
                has_issues = True

    # 3. 注释干扰检测
    commented_keys = []
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("#"):
            inner = stripped[1:].strip()
            if "=" in inner:
                key_raw = inner.split("=", 1)[0].strip()
                if key_raw in _PROVIDER_ENV_HINTS and key_raw not in commented_keys:
                    commented_keys.append(key_raw)
    if commented_keys:
        check_warn(f".env: 被注释的 Key: {', '.join(commented_keys)}", "(取消注释以启用)")
        has_issues = True

    # 4. 重复 key 检测
    for key, count in seen_keys.items():
        if count > 1:
            check_warn(f".env: {key} 定义了 {count} 次", "(dotenv 行为是后者覆盖前者)")
            has_issues = True

    if not has_issues:
        check_ok(".env 内容检测通过", "(无空值/格式/重复问题)")


def _honcho_is_configured_for_doctor() -> bool:
    """Return True when Honcho is configured, even if this process has no active session."""
    try:
        from plugins.memory.honcho.client import HonchoClientConfig

        cfg = HonchoClientConfig.from_global_config()
        return bool(cfg.enabled and (cfg.api_key or cfg.base_url))
    except Exception:
        return False


def _apply_doctor_tool_availability_overrides(available: list[str], unavailable: list[dict]) -> tuple[list[str], list[dict]]:
    """Adjust runtime-gated tool availability for doctor diagnostics."""
    if not _honcho_is_configured_for_doctor():
        return available, unavailable

    updated_available = list(available)
    updated_unavailable = []
    for item in unavailable:
        if item.get("name") == "honcho":
            if "honcho" not in updated_available:
                updated_available.append("honcho")
            continue
        updated_unavailable.append(item)
    return updated_available, updated_unavailable


# ── D4: 分组摘要 & quiet 模式  ──
_quiet_mode: bool = False
_total_ok: int = 0
_total_warn: int = 0
_total_fail: int = 0
_section_ok: int = 0
_section_warn: int = 0
_section_fail: int = 0


def _reset_totals() -> None:
    """重置全局计数器（每次 run_doctor 调用前）。"""
    global _total_ok, _total_warn, _total_fail, _section_ok, _section_warn, _section_fail
    _total_ok = _total_warn = _total_fail = 0
    _section_ok = _section_warn = _section_fail = 0


def _section_reset() -> None:
    """重置每段计数器（在每个 ◆ 标题后调用）。"""
    global _section_ok, _section_warn, _section_fail
    _section_ok = _section_warn = _section_fail = 0


def _section_summary() -> None:
    """打印当前段的检测汇总。"""
    global _section_ok, _section_warn, _section_fail
    parts = []
    if _section_ok:
        parts.append(color(f"{_section_ok} ✓", Colors.GREEN))
    if _section_warn:
        parts.append(color(f"{_section_warn} ⚠", Colors.YELLOW))
    if _section_fail:
        parts.append(color(f"{_section_fail} ✗", Colors.RED))
    if parts:
        print(f"  {color('─' * 4, Colors.DIM)} {'  '.join(parts)}")


def check_ok(text: str, detail: str = ""):
    global _quiet_mode, _total_ok, _section_ok
    _total_ok += 1
    _section_ok += 1
    if _quiet_mode:
        return
    print(f"  {color('✓', Colors.GREEN)} {text}" + (f" {color(detail, Colors.DIM)}" if detail else ""))

def check_warn(text: str, detail: str = ""):
    global _total_warn, _section_warn
    _total_warn += 1
    _section_warn += 1
    print(f"  {color('⚠', Colors.YELLOW)} {text}" + (f" {color(detail, Colors.DIM)}" if detail else ""))

def check_fail(text: str, detail: str = ""):
    global _total_fail, _section_fail
    _total_fail += 1
    _section_fail += 1
    print(f"  {color('✗', Colors.RED)} {text}" + (f" {color(detail, Colors.DIM)}" if detail else ""))

def check_info(text: str):
    if _quiet_mode:
        return
    print(f"    {color('→', Colors.CYAN)} {text}")


def _check_gateway_service_linger(issues: list[str]) -> None:
    """Warn when a systemd user gateway service will stop after logout."""
    try:
        from hermes_cli.gateway import (
            get_systemd_linger_status,
            get_systemd_unit_path,
            is_linux,
        )
    except Exception as e:
        check_warn("Gateway service linger", f"(could not import gateway helpers: {e})")
        return

    if not is_linux():
        return

    unit_path = get_systemd_unit_path()
    if not unit_path.exists():
        return

    print()
    print(color("◆ 网关服务", Colors.CYAN, Colors.BOLD))

    linger_enabled, linger_detail = get_systemd_linger_status()
    if linger_enabled is True:
        check_ok("Systemd linger 已启用", "(网关服务可持续运行)")
    elif linger_enabled is False:
        check_warn("Systemd linger 未启用", "(网关可能在登出后停止)")
        check_info("Run: sudo loginctl enable-linger $USER")
        issues.append("Enable linger for the gateway user service: sudo loginctl enable-linger $USER")
    else:
        check_warn("无法验证 systemd linger", f"({linger_detail})")


def run_doctor(args):
    """Run diagnostic checks."""
    should_fix = getattr(args, 'fix', False)
    should_quiet = getattr(args, 'quiet', False)

    # D4: 设置 quiet 模式（静默输出只显示 ⚠ 和 ✗）
    global _quiet_mode
    _quiet_mode = should_quiet
    _reset_totals()

    # Doctor runs from the interactive CLI, so CLI-gated tool availability
    # checks (like cronjob management) should see the same context as `hermes`.
    os.environ.setdefault("HERMES_INTERACTIVE", "1")
    
    issues = []
    manual_issues = []  # issues that can't be auto-fixed
    fixed_count = 0
    
    print()
    print(color("┌─────────────────────────────────────────────────────────┐", Colors.CYAN))
    print(color("│                 🩺 Hermes 诊断工具                      │", Colors.CYAN))
    print(color("└─────────────────────────────────────────────────────────┘", Colors.CYAN))
    
    # =========================================================================
    # Check: Python version
    # =========================================================================
    print()
    print(color("◆ Python 环境", Colors.CYAN, Colors.BOLD))
    _section_reset()
    
    py_version = sys.version_info
    if py_version >= (3, 11):
        check_ok(f"Python {py_version.major}.{py_version.minor}.{py_version.micro}")
    elif py_version >= (3, 10):
        check_ok(f"Python {py_version.major}.{py_version.minor}.{py_version.micro}")
        check_warn("Python 3.11+ recommended for RL Training tools (tinker requires >= 3.11)")
    elif py_version >= (3, 8):
        check_warn(f"Python {py_version.major}.{py_version.minor}.{py_version.micro}", "(3.10+ recommended)")
    else:
        check_fail(f"Python {py_version.major}.{py_version.minor}.{py_version.micro}", "(3.10+ required)")
        issues.append("Upgrade Python to 3.10+")
    
    # Check virtual environment type (Conda / Pyenv / venv / system)
    conda_env = os.getenv("CONDA_DEFAULT_ENV", "")
    conda_prefix = os.getenv("CONDA_PREFIX", "")
    pyenv_shell = os.getenv("PYENV_SHELL", "")
    pyenv_version = os.getenv("PYENV_VERSION", "")
    in_venv = sys.prefix != sys.base_prefix

    if conda_env:
        check_ok(f"Conda 环境: {conda_env}")
        check_info(f"解释器路径: {sys.executable}")
    elif pyenv_shell:
        check_ok(f"Pyenv 管理", f"(Python {pyenv_version or 'global'})")
        check_info(f"解释器路径: {sys.executable}")
    elif in_venv:
        check_ok("Virtual environment active", "(venv)")
    else:
        check_warn("系统 Python", f"(建议创建虚拟环境: python -m venv venv)")
        check_info(f"解释器路径: {sys.executable}")
    
    # =========================================================================
    # Check: Required packages
    # =========================================================================
    _section_summary()
    print()
    print(color("◆ 必需的包", Colors.CYAN, Colors.BOLD))
    _section_reset()
    
    required_packages = [
        ("openai", "OpenAI SDK"),
        ("rich", "Rich (terminal UI)"),
        ("dotenv", "python-dotenv"),
        ("yaml", "PyYAML"),
        ("httpx", "HTTPX"),
    ]
    
    optional_packages = [
        ("croniter", "Croniter (cron expressions)"),
        ("telegram", "python-telegram-bot"),
        ("discord", "discord.py"),
    ]
    
    for module, name in required_packages:
        try:
            __import__(module)
            check_ok(name)
        except ImportError:
            check_fail(name, "(missing)")
            issues.append(f"Install {name}: {_python_install_cmd()} {module}")
    
    for module, name in optional_packages:
        try:
            __import__(module)
            check_ok(name, "(optional)")
        except ImportError:
            check_warn(name, "(optional, not installed)")
    
    # =========================================================================
    # Check: Configuration files
    # =========================================================================
    _section_summary()
    print()
    print(color("◆ 配置文件", Colors.CYAN, Colors.BOLD))
    _section_reset()
    
    # Check ~/.hermes/.env (primary location for user config)
    env_path = HERMES_HOME / '.env'
    if env_path.exists():
        check_ok(f"{_DHH}/.env file exists")
        
        # Check for common issues
        content = env_path.read_text()
        if _has_provider_env_config(content):
            check_ok("API key or custom endpoint configured")
        else:
            check_warn(f"No API key found in {_DHH}/.env")
            issues.append("Run 'hermes setup' to configure API keys")

        # D1: .env 内容智能检测
        _check_env_content(env_path)
    else:
        # Also check project root as fallback
        fallback_env = PROJECT_ROOT / '.env'
        if fallback_env.exists():
            check_ok(".env file exists (in project directory)")
        else:
            check_fail(f"{_DHH}/.env file missing")
            if should_fix:
                env_path.parent.mkdir(parents=True, exist_ok=True)
                env_path.touch()
                check_ok(f"Created empty {_DHH}/.env")
                check_info("Run 'hermes setup' to configure API keys")
                fixed_count += 1
            else:
                check_info("Run 'hermes setup' to create one")
                issues.append("Run 'hermes setup' to create .env")
    
    # Check ~/.hermes/config.yaml (primary) or project cli-config.yaml (fallback)
    config_path = HERMES_HOME / 'config.yaml'
    if config_path.exists():
        check_ok(f"{_DHH}/config.yaml exists")
    else:
        fallback_config = PROJECT_ROOT / 'cli-config.yaml'
        if fallback_config.exists():
            check_ok("cli-config.yaml exists (in project directory)")
        else:
            example_config = PROJECT_ROOT / 'cli-config.yaml.example'
            if should_fix and example_config.exists():
                config_path.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(str(example_config), str(config_path))
                check_ok(f"Created {_DHH}/config.yaml from cli-config.yaml.example")
                fixed_count += 1
            elif should_fix:
                check_warn("config.yaml not found and no example to copy from")
                manual_issues.append(f"Create {_DHH}/config.yaml manually")
            else:
                check_warn("config.yaml not found", "(using defaults)")

    # Check config version and stale keys
    config_path = HERMES_HOME / 'config.yaml'
    if config_path.exists():
        try:
            from hermes_cli.config import check_config_version, migrate_config
            current_ver, latest_ver = check_config_version()
            if current_ver < latest_ver:
                check_warn(
                    f"Config version outdated (v{current_ver} → v{latest_ver})",
                    "(new settings available)"
                )
                if should_fix:
                    try:
                        migrate_config(interactive=False, quiet=False)
                        check_ok("Config migrated to latest version")
                        fixed_count += 1
                    except Exception as mig_err:
                        check_warn(f"Auto-migration failed: {mig_err}")
                        issues.append("Run 'hermes setup' to migrate config")
                else:
                    issues.append("Run 'hermes doctor --fix' or 'hermes setup' to migrate config")
            else:
                check_ok(f"Config version up to date (v{current_ver})")
        except Exception:
            pass

        # Detect stale root-level model keys (known bug source — PR #4329)
        try:
            import yaml
            with open(config_path) as f:
                raw_config = yaml.safe_load(f) or {}
            stale_root_keys = [k for k in ("provider", "base_url") if k in raw_config and isinstance(raw_config[k], str)]
            if stale_root_keys:
                check_warn(
                    f"Stale root-level config keys: {', '.join(stale_root_keys)}",
                    "(should be under 'model:' section)"
                )
                if should_fix:
                    # Coerce scalar/None ``model:`` into a dict before mutation —
                    # ``setdefault("model", {})`` would return an existing scalar
                    # and then ``model_section[k] = ...`` would raise TypeError.
                    raw_model = raw_config.get("model")
                    if isinstance(raw_model, dict):
                        model_section = raw_model
                    elif isinstance(raw_model, str) and raw_model.strip():
                        model_section = {"default": raw_model.strip()}
                        raw_config["model"] = model_section
                    else:
                        model_section = {}
                        raw_config["model"] = model_section
                    for k in stale_root_keys:
                        if not model_section.get(k):
                            model_section[k] = raw_config.pop(k)
                        else:
                            raw_config.pop(k)
                    from utils import atomic_yaml_write
                    atomic_yaml_write(config_path, raw_config)
                    check_ok("Migrated stale root-level keys into model section")
                    fixed_count += 1
                else:
                    issues.append("Stale root-level provider/base_url in config.yaml — run 'hermes doctor --fix'")
        except Exception:
            pass

        # Validate config structure (catches malformed custom_providers, etc.)
        try:
            from hermes_cli.config import validate_config_structure
            config_issues = validate_config_structure()
            if config_issues:
                _section_summary()
                print()
                print(color("◆ 配置结构", Colors.CYAN, Colors.BOLD))
                _section_reset()
                for ci in config_issues:
                    if ci.severity == "error":
                        check_fail(ci.message)
                    else:
                        check_warn(ci.message)
                    # Show the hint indented
                    for hint_line in ci.hint.splitlines():
                        check_info(hint_line)
                    issues.append(ci.message)
        except Exception:
            pass

    # =========================================================================
    # Check: Directory structure
    # =========================================================================
    _section_summary()
    print()
    print(color("◆ 目录结构", Colors.CYAN, Colors.BOLD))
    _section_reset()
    
    hermes_home = HERMES_HOME
    if hermes_home.exists():
        check_ok(f"{_DHH} directory exists")
    else:
        if should_fix:
            hermes_home.mkdir(parents=True, exist_ok=True)
            check_ok(f"Created {_DHH} directory")
            fixed_count += 1
        else:
            check_warn(f"{_DHH} not found", "(will be created on first use)")
    
    # Check expected subdirectories
    expected_subdirs = ["cron", "sessions", "logs", "skills", "memories"]
    for subdir_name in expected_subdirs:
        subdir_path = hermes_home / subdir_name
        if subdir_path.exists():
            check_ok(f"{_DHH}/{subdir_name}/ exists")
        else:
            if should_fix:
                subdir_path.mkdir(parents=True, exist_ok=True)
                check_ok(f"Created {_DHH}/{subdir_name}/")
                fixed_count += 1
            else:
                check_warn(f"{_DHH}/{subdir_name}/ not found", "(will be created on first use)")
    
    # Check for SOUL.md persona file
    soul_path = hermes_home / "SOUL.md"
    if soul_path.exists():
        content = soul_path.read_text(encoding="utf-8").strip()
        # Check if it's just the template comments (no real content)
        lines = [l for l in content.splitlines() if l.strip() and not l.strip().startswith(("<!--", "-->", "#"))]
        if lines:
            check_ok(f"{_DHH}/SOUL.md exists (persona configured)")
        else:
            check_info(f"{_DHH}/SOUL.md exists but is empty — edit it to customize personality")
    else:
        check_warn(f"{_DHH}/SOUL.md not found", "(create it to give Hermes a custom personality)")
        if should_fix:
            soul_path.parent.mkdir(parents=True, exist_ok=True)
            soul_path.write_text(
                "# Hermes Agent Persona\n\n"
                "<!-- Edit this file to customize how Hermes communicates. -->\n\n"
                "You are Hermes, a helpful AI assistant.\n",
                encoding="utf-8",
            )
            check_ok(f"Created {_DHH}/SOUL.md with basic template")
            fixed_count += 1
    
    # Check memory directory
    memories_dir = hermes_home / "memories"
    if memories_dir.exists():
        check_ok(f"{_DHH}/memories/ directory exists")
        memory_file = memories_dir / "MEMORY.md"
        user_file = memories_dir / "USER.md"
        if memory_file.exists():
            size = len(memory_file.read_text(encoding="utf-8").strip())
            check_ok(f"MEMORY.md exists ({size} chars)")
        else:
            check_info("MEMORY.md not created yet (will be created when the agent first writes a memory)")
        if user_file.exists():
            size = len(user_file.read_text(encoding="utf-8").strip())
            check_ok(f"USER.md exists ({size} chars)")
        else:
            check_info("USER.md not created yet (will be created when the agent first writes a memory)")
    else:
        check_warn(f"{_DHH}/memories/ not found", "(will be created on first use)")
        if should_fix:
            memories_dir.mkdir(parents=True, exist_ok=True)
            check_ok(f"Created {_DHH}/memories/")
            fixed_count += 1
    
    # Check SQLite session store
    state_db_path = hermes_home / "state.db"
    if state_db_path.exists():
        try:
            import sqlite3
            conn = sqlite3.connect(str(state_db_path))
            cursor = conn.execute("SELECT COUNT(*) FROM sessions")
            count = cursor.fetchone()[0]
            conn.close()
            check_ok(f"{_DHH}/state.db exists ({count} sessions)")
        except Exception as e:
            check_warn(f"{_DHH}/state.db exists but has issues: {e}")
    else:
        check_info(f"{_DHH}/state.db not created yet (will be created on first session)")

    # Check WAL file size (unbounded growth indicates missed checkpoints)
    wal_path = hermes_home / "state.db-wal"
    if wal_path.exists():
        try:
            wal_size = wal_path.stat().st_size
            if wal_size > 50 * 1024 * 1024:  # 50 MB
                check_warn(
                    f"WAL file is large ({wal_size // (1024*1024)} MB)",
                    "(may indicate missed checkpoints)"
                )
                if should_fix:
                    import sqlite3
                    conn = sqlite3.connect(str(state_db_path))
                    conn.execute("PRAGMA wal_checkpoint(PASSIVE)")
                    conn.close()
                    new_size = wal_path.stat().st_size if wal_path.exists() else 0
                    check_ok(f"WAL checkpoint performed ({wal_size // 1024}K → {new_size // 1024}K)")
                    fixed_count += 1
                else:
                    issues.append("Large WAL file — run 'hermes doctor --fix' to checkpoint")
            elif wal_size > 10 * 1024 * 1024:  # 10 MB
                check_info(f"WAL file is {wal_size // (1024*1024)} MB (normal for active sessions)")
        except Exception:
            pass

    _check_gateway_service_linger(issues)

    # =========================================================================
    # Check: Command installation (hermes bin symlink)
    # =========================================================================
    if sys.platform != "win32":
        _section_summary()
        print()
        print(color("◆ 命令安装", Colors.CYAN, Colors.BOLD))
        _section_reset()

        # Determine the venv entry point location
        _venv_bin = None
        for _venv_name in ("venv", ".venv"):
            _candidate = PROJECT_ROOT / _venv_name / "bin" / "hermes"
            if _candidate.exists():
                _venv_bin = _candidate
                break

        # Determine the expected command link directory (mirrors install.sh logic)
        _prefix = os.environ.get("PREFIX", "")
        _is_termux_env = bool(os.environ.get("TERMUX_VERSION")) or "com.termux/files/usr" in _prefix
        if _is_termux_env and _prefix:
            _cmd_link_dir = Path(_prefix) / "bin"
            _cmd_link_display = "$PREFIX/bin"
        else:
            _cmd_link_dir = Path.home() / ".local" / "bin"
            _cmd_link_display = "~/.local/bin"
        _cmd_link = _cmd_link_dir / "hermes"

        if _venv_bin is None:
            check_warn(
                "Venv entry point not found",
                "(hermes not in venv/bin/ or .venv/bin/ — reinstall with pip install -e '.[all]')"
            )
            manual_issues.append(
                f"Reinstall entry point: cd {PROJECT_ROOT} && source venv/bin/activate && pip install -e '.[all]'"
            )
        else:
            check_ok(f"Venv entry point exists ({_venv_bin.relative_to(PROJECT_ROOT)})")

            # Check the symlink at the command link location
            if _cmd_link.is_symlink():
                _target = _cmd_link.resolve()
                _expected = _venv_bin.resolve()
                if _target == _expected:
                    check_ok(f"{_cmd_link_display}/hermes → correct target")
                else:
                    check_warn(
                        f"{_cmd_link_display}/hermes points to wrong target",
                        f"(→ {_target}, expected → {_expected})"
                    )
                    if should_fix:
                        _cmd_link.unlink()
                        _cmd_link.symlink_to(_venv_bin)
                        check_ok(f"Fixed symlink: {_cmd_link_display}/hermes → {_venv_bin}")
                        fixed_count += 1
                    else:
                        issues.append(f"Broken symlink at {_cmd_link_display}/hermes — run 'hermes doctor --fix'")
            elif _cmd_link.exists():
                # It's a regular file, not a symlink — possibly a wrapper script
                check_ok(f"{_cmd_link_display}/hermes exists (non-symlink)")
            else:
                check_fail(
                    f"{_cmd_link_display}/hermes not found",
                    "(hermes command may not work outside the venv)"
                )
                if should_fix:
                    _cmd_link_dir.mkdir(parents=True, exist_ok=True)
                    _cmd_link.symlink_to(_venv_bin)
                    check_ok(f"Created symlink: {_cmd_link_display}/hermes → {_venv_bin}")
                    fixed_count += 1

                    # Check if the link dir is on PATH
                    _path_dirs = os.environ.get("PATH", "").split(os.pathsep)
                    if str(_cmd_link_dir) not in _path_dirs:
                        check_warn(
                            f"{_cmd_link_display} is not on your PATH",
                            "(add it to your shell config: export PATH=\"$HOME/.local/bin:$PATH\")"
                        )
                        manual_issues.append(f"Add {_cmd_link_display} to your PATH")
                else:
                    issues.append(f"Missing {_cmd_link_display}/hermes symlink — run 'hermes doctor --fix'")

    # =========================================================================
    # Check: External tools
    # =========================================================================
    _section_summary()
    print()
    print(color("◆ 外部工具", Colors.CYAN, Colors.BOLD))
    _section_reset()
    
    # Git
    if shutil.which("git"):
        check_ok("git")
    else:
        check_warn("git not found", "(optional)")
    
    # ripgrep (optional, for faster file search)
    if shutil.which("rg"):
        check_ok("ripgrep (rg)", "(faster file search)")
    else:
        check_warn("ripgrep (rg) not found", "(file search uses grep fallback)")
        check_info(f"Install for faster search: {_system_package_install_cmd('ripgrep')}")
    
    # Docker (optional)
    terminal_env = os.getenv("TERMINAL_ENV", "local")
    if terminal_env == "docker":
        if shutil.which("docker"):
            # Check if docker daemon is running
            try:
                result = subprocess.run(["docker", "info"], capture_output=True, timeout=10)
            except subprocess.TimeoutExpired:
                result = None
            if result is not None and result.returncode == 0:
                check_ok("docker", "(daemon running)")
            else:
                check_fail("docker daemon not running")
                issues.append("Start Docker daemon")
        else:
            check_fail("docker not found", "(required for TERMINAL_ENV=docker)")
            issues.append("Install Docker or change TERMINAL_ENV")
    else:
        if shutil.which("docker"):
            check_ok("docker", "(optional)")
        else:
            if _is_termux():
                check_info("Docker backend is not available inside Termux (expected on Android)")
            else:
                check_warn("docker not found", "(optional)")
    
    # SSH (if using ssh backend)
    if terminal_env == "ssh":
        ssh_host = os.getenv("TERMINAL_SSH_HOST")
        if ssh_host:
            # Try to connect
            try:
                result = subprocess.run(
                    ["ssh", "-o", "ConnectTimeout=5", "-o", "BatchMode=yes", ssh_host, "echo ok"],
                    capture_output=True,
                    text=True,
                    timeout=15
                )
            except subprocess.TimeoutExpired:
                result = None
            if result is not None and result.returncode == 0:
                check_ok(f"SSH connection to {ssh_host}")
            else:
                check_fail(f"SSH connection to {ssh_host}")
                issues.append(f"Check SSH configuration for {ssh_host}")
        else:
            check_fail("TERMINAL_SSH_HOST not set", "(required for TERMINAL_ENV=ssh)")
            issues.append("Set TERMINAL_SSH_HOST in .env")
    
    # Daytona (if using daytona backend)
    if terminal_env == "daytona":
        daytona_key = os.getenv("DAYTONA_API_KEY")
        if daytona_key:
            check_ok("Daytona API key", "(configured)")
        else:
            check_fail("DAYTONA_API_KEY not set", "(required for TERMINAL_ENV=daytona)")
            issues.append("Set DAYTONA_API_KEY environment variable")
        try:
            from daytona import Daytona  # noqa: F401 — SDK presence check
            check_ok("daytona SDK", "(installed)")
        except ImportError:
            check_fail("daytona SDK not installed", "(pip install daytona)")
            issues.append("Install daytona SDK: pip install daytona")

    # Node.js + agent-browser (for browser automation tools)
    if shutil.which("node"):
        check_ok("Node.js")
        # Check if agent-browser is installed
        agent_browser_path = PROJECT_ROOT / "node_modules" / "agent-browser"
        if agent_browser_path.exists():
            check_ok("agent-browser (Node.js)", "(browser automation)")
        else:
            if _is_termux():
                check_info("agent-browser is not installed (expected in the tested Termux path)")
                check_info("Install it manually later with: npm install -g agent-browser && agent-browser install")
                check_info("Termux browser setup:")
                for step in _termux_browser_setup_steps(node_installed=True):
                    check_info(step)
            else:
                check_warn("agent-browser not installed", "(run: npm install)")
    else:
        if _is_termux():
            check_info("Node.js not found (browser tools are optional in the tested Termux path)")
            check_info("Install Node.js on Termux with: pkg install nodejs")
            check_info("Termux browser setup:")
            for step in _termux_browser_setup_steps(node_installed=False):
                check_info(step)
        else:
            check_warn("Node.js not found", "(optional, needed for browser tools)")
    
    # npm audit for all Node.js packages
    if shutil.which("npm"):
        npm_dirs = [
            (PROJECT_ROOT, "Browser tools (agent-browser)"),
            (PROJECT_ROOT / "scripts" / "whatsapp-bridge", "WhatsApp bridge"),
        ]
        for npm_dir, label in npm_dirs:
            if not (npm_dir / "node_modules").exists():
                continue
            try:
                audit_result = subprocess.run(
                    ["npm", "audit", "--json"],
                    cwd=str(npm_dir),
                    capture_output=True, text=True, timeout=30,
                )
                import json as _json
                audit_data = _json.loads(audit_result.stdout) if audit_result.stdout.strip() else {}
                vuln_count = audit_data.get("metadata", {}).get("vulnerabilities", {})
                critical = vuln_count.get("critical", 0)
                high = vuln_count.get("high", 0)
                moderate = vuln_count.get("moderate", 0)
                total = critical + high + moderate
                if total == 0:
                    check_ok(f"{label} deps", "(no known vulnerabilities)")
                elif critical > 0 or high > 0:
                    check_warn(
                        f"{label} deps",
                        f"({critical} critical, {high} high, {moderate} moderate — run: cd {npm_dir} && npm audit fix)"
                    )
                    issues.append(f"{label} has {total} npm vulnerability(ies)")
                else:
                    check_ok(f"{label} deps", f"({moderate} moderate vulnerability(ies))")
            except Exception:
                pass

    # =========================================================================
    # Check: API connectivity
    # =========================================================================
    _section_summary()
    print()
    print(color("◆ API 连通性", Colors.CYAN, Colors.BOLD))
    _section_reset()
    
    # -- API-key providers --
    # Tuple: (name, env_vars, default_url, base_env, supports_models_endpoint)
    # If supports_models_endpoint is False, we skip the health check and just show "configured"
    _apikey_providers = [
        ("Z.AI / GLM",      ("GLM_API_KEY", "ZAI_API_KEY", "Z_AI_API_KEY"), "https://api.z.ai/api/paas/v4/models", "GLM_BASE_URL", True),
        ("Kimi / Moonshot",  ("KIMI_API_KEY",),                              "https://api.moonshot.ai/v1/models",   "KIMI_BASE_URL", True),
        ("Kimi / Moonshot (China)", ("KIMI_CN_API_KEY",),                    "https://api.moonshot.cn/v1/models",   None, True),
        ("Arcee AI",         ("ARCEEAI_API_KEY",),                            "https://api.arcee.ai/api/v1/models",  "ARCEE_BASE_URL", True),
        ("DeepSeek",         ("DEEPSEEK_API_KEY",),                           "https://api.deepseek.com/models",  "DEEPSEEK_BASE_URL", True),
        ("Hugging Face",     ("HF_TOKEN",),                                   "https://router.huggingface.co/v1/models", "HF_BASE_URL", True),
        ("Alibaba/DashScope", ("DASHSCOPE_API_KEY",),                         "https://dashscope-intl.aliyuncs.com/compatible-mode/v1/models", "DASHSCOPE_BASE_URL", True),
        # MiniMax: the /anthropic endpoint doesn't support /models, but the /v1 endpoint does.
        ("MiniMax",          ("MINIMAX_API_KEY",),                            "https://api.minimax.io/v1/models",    "MINIMAX_BASE_URL", True),
        ("MiniMax (China)",  ("MINIMAX_CN_API_KEY",),                         "https://api.minimaxi.com/v1/models",  "MINIMAX_CN_BASE_URL", True),
        ("Vercel AI Gateway",       ("AI_GATEWAY_API_KEY",),                          "https://ai-gateway.vercel.sh/v1/models", "AI_GATEWAY_BASE_URL", True),
        ("Kilo Code",        ("KILOCODE_API_KEY",),                            "https://api.kilo.ai/api/gateway/models",  "KILOCODE_BASE_URL", True),
        ("OpenCode Zen",     ("OPENCODE_ZEN_API_KEY",),                        "https://opencode.ai/zen/v1/models",  "OPENCODE_ZEN_BASE_URL", True),
        # OpenCode Go has no shared /models endpoint; skip the health check.
        ("OpenCode Go",      ("OPENCODE_GO_API_KEY",),                         None,                                  "OPENCODE_GO_BASE_URL", False),
    ]
    for _pname, _env_vars, _default_url, _base_env, _supports_health_check in _apikey_providers:
        _key = ""
        for _ev in _env_vars:
            _key = os.getenv(_ev, "")
            if _key:
                break
        if _key:
            _label = _pname.ljust(20)
            # Some providers (like MiniMax) don't support /models endpoint
            if not _supports_health_check:
                print(f"  {color('✓', Colors.GREEN)} {_label} {color('(key configured)', Colors.DIM)}")
                continue
            print(f"  Checking {_pname} API...", end="", flush=True)
            try:
                import httpx
                _base = os.getenv(_base_env, "") if _base_env else ""
                # Auto-detect Kimi Code keys (sk-kimi-) → api.kimi.com
                if not _base and _key.startswith("sk-kimi-"):
                    _base = "https://api.kimi.com/coding/v1"
                # Anthropic-compat endpoints (/anthropic) don't support /models.
                # Rewrite to the OpenAI-compat /v1 surface for health checks.
                if _base and _base.rstrip("/").endswith("/anthropic"):
                    from agent.auxiliary_client import _to_openai_base_url
                    _base = _to_openai_base_url(_base)
                _url = (_base.rstrip("/") + "/models") if _base else _default_url
                _headers = {"Authorization": f"Bearer {_key}"}
                if "api.kimi.com" in _url.lower():
                    _headers["User-Agent"] = "KimiCLI/1.30.0"
                _resp = httpx.get(
                    _url,
                    headers=_headers,
                    timeout=10,
                )
                if _resp.status_code == 200:
                    print(f"\r  {color('✓', Colors.GREEN)} {_label}                          ")
                elif _resp.status_code == 401:
                    print(f"\r  {color('✗', Colors.RED)} {_label} {color('(invalid API key)', Colors.DIM)}           ")
                    issues.append(f"Check {_env_vars[0]} in .env")
                else:
                    print(f"\r  {color('⚠', Colors.YELLOW)} {_label} {color(f'(HTTP {_resp.status_code})', Colors.DIM)}           ")
            except Exception as _e:
                print(f"\r  {color('⚠', Colors.YELLOW)} {_label} {color(f'({_e})', Colors.DIM)}           ")

    # -- AWS Bedrock --
    # Bedrock uses the AWS SDK credential chain, not API keys.
    try:
        from agent.bedrock_adapter import has_aws_credentials, resolve_aws_auth_env_var, resolve_bedrock_region
        if has_aws_credentials():
            _auth_var = resolve_aws_auth_env_var()
            _region = resolve_bedrock_region()
            _label = "AWS Bedrock".ljust(20)
            print(f"  Checking AWS Bedrock...", end="", flush=True)
            try:
                import boto3
                _br_client = boto3.client("bedrock", region_name=_region)
                _br_resp = _br_client.list_foundation_models()
                _model_count = len(_br_resp.get("modelSummaries", []))
                print(f"\r  {color('✓', Colors.GREEN)} {_label} {color(f'({_auth_var}, {_region}, {_model_count} models)', Colors.DIM)}           ")
            except ImportError:
                print(f"\r  {color('⚠', Colors.YELLOW)} {_label} {color('(boto3 not installed — pip install hermes-agent[bedrock])', Colors.DIM)}           ")
                issues.append("Install boto3 for Bedrock: pip install hermes-agent[bedrock]")
            except Exception as _e:
                _err_name = type(_e).__name__
                print(f"\r  {color('⚠', Colors.YELLOW)} {_label} {color(f'({_err_name}: {_e})', Colors.DIM)}           ")
                issues.append(f"AWS Bedrock: {_err_name} — check IAM permissions for bedrock:ListFoundationModels")
    except ImportError:
        pass  # bedrock_adapter not available — skip silently

    # =========================================================================
    # D6: Network connectivity (国产 API 端点可达性检测)
    _section_summary()
    print()
    print(color("◆ 网络连通性", Colors.CYAN, Colors.BOLD))
    _section_reset()

    try:
        from hermes_cli.quickstart import _network_diagnostics

        results = _network_diagnostics()
        for r in results:
            if r["reachable"]:
                check_ok(f"{r['provider']} 可达", f"({r['endpoint']})")
            else:
                check_warn(f"{r['provider']} 不可达", f"({r['endpoint']} - 可能被墙或服务宕机)")
    except ImportError:
        check_warn("网络诊断模块不可用", "(quickstart 模块未加载)")

        check_warn("网络诊断模块不可用", "(quickstart 模块未加载)")

    # =========================================================================
    # D7: Config compatibility (yaml 与 .env 冲突检测)
    # =========================================================================
    _section_summary()
    print()
    print(color("◆ 配置兼容性", Colors.CYAN, Colors.BOLD))
    _section_reset()

    try:
        from hermes_cli.config import load_config, get_env_value

        _cfg = load_config()
        _issues = []

        # 检查每个 Provider 的 API Key 是否配置
        from hermes_cli.quickstart import _PROVIDER_CHECKS

        for _p in _PROVIDER_CHECKS:
            _env_val = os.environ.get(_p["env_var"], "")
            if not _env_val:
                _env_val = get_env_value(_p["env_var"])
            _has_key = bool(_env_val and len(_env_val) > 4)

            # 检查 providers 段中是否配置了该 provider
            _providers_cfg = _cfg.get("providers", {})
            _configured = isinstance(_providers_cfg, dict) and _p["id"] in _providers_cfg

            if _has_key and not _configured:
                _issues.append(f"{_p['name']}: .env 中有 {_p['env_var']}，但 config.yaml 未配置该 Provider")
            elif _configured and not _has_key:
                _issues.append(f"{_p['name']}: config.yaml 已配置，但 .env 中缺少 {_p['env_var']}")

        if not _issues:
            check_ok("配置一致性检查通过", "(8 个国产 Provider 均已校验)")
        else:
            for _issue in _issues:
                check_warn(f"配置冲突", _issue)
    except ImportError:
        check_warn("配置兼容性检测模块不可用", "(quickstart 模块未加载)")

    # =========================================================================
    # D8: GPU / CUDA environment (本地模型运行环境检测)
    # =========================================================================
    _section_summary()
    print()
    print(color("◆ GPU / CUDA 环境", Colors.CYAN, Colors.BOLD))
    _section_reset()

    _gpu_found = False

    # 1. 操作系统检测
    import platform as _pf
    _os = _pf.system()
    if _os == "Windows":
        # 原生 Windows 不支持 GPU 推理 (llama-cpp-python CUDA 仅限 WSL2)
        check_warn("原生 Windows GPU 检测", "(Hermes GPU 推理需在 WSL2 中运行)")
    elif "microsoft" in _pf.release().lower() or "WSL" in _pf.release():
        _wsl_version = ""
        try:
            _proc_version = Path("/proc/version").read_text().lower()
            if "wsl2" in _proc_version or "microsoft" in _proc_version:
                _wsl_version = "WSL2"
            elif "wsl1" in _proc_version or "wsl" in _proc_version:
                _wsl_version = "WSL"
            check_ok(f"运行环境: {_os} ({_wsl_version})", "GPU 推理可用")
        except Exception:
            check_ok(f"运行环境: {_os}", "(可能为 WSL2)")
    else:
        check_ok(f"运行环境: {_os}", "(Linux - GPU 推理可用)")

    # 2. nvidia-smi 检测
    try:
        import subprocess as _sp
        _nvsmi = _sp.run(["nvidia-smi", "--query-gpu=name,temperature.gpu,memory.total",
                          "--format=csv,noheader"], capture_output=True, text=True, timeout=10)
        if _nvsmi.returncode == 0 and _nvsmi.stdout.strip():
            _gpu_found = True
            for _line in _nvsmi.stdout.strip().splitlines():
                _parts = [p.strip() for p in _line.split(",")]
                _gpu_name = _parts[0] if len(_parts) > 0 else "?"
                _gpu_temp = _parts[1] if len(_parts) > 1 else "?"
                _gpu_mem = _parts[2] if len(_parts) > 2 else "?"
                check_ok(f"NVIDIA GPU: {_gpu_name}", f"温度: {_gpu_temp} / 显存: {_gpu_mem}")
        else:
            check_warn("NVIDIA GPU 不可用", "(nvidia-smi 未找到 — 本地模型将使用 CPU 运行)")
    except FileNotFoundError:
        check_warn("NVIDIA GPU 不可用", "(nvidia-smi 未安装 — 本地模型将使用 CPU 运行)")
    except Exception as _e:
        check_warn("GPU 检测失败", str(_e))

    # 3. CUDA 版本检测
    if _gpu_found:
        try:
            import subprocess as _sp
            _nvcc = _sp.run(["nvcc", "--version"], capture_output=True, text=True, timeout=5)
            if _nvcc.returncode == 0:
                _ver_line = _nvcc.stdout.splitlines()[-1] if _nvcc.stdout.splitlines() else "(unknown)"
                check_ok("CUDA Toolkit 已安装", _ver_line.strip())
            else:
                check_warn("CUDA Toolkit 未安装",
                           "(可通过 conda install cudatoolkit 或 apt install nvidia-cuda-toolkit 安装)")
        except FileNotFoundError:
            check_warn("CUDA Toolkit 未安装", "(nvcc 未找到 — 可通过 conda install cudatoolkit 安装)")

    # 4. PyTorch GPU 检测
    try:
        import torch as _torch
        if _torch.cuda.is_available():
            _cuda_ver = _torch.version.cuda or "?"
            _device_count = _torch.cuda.device_count()
            _devices = []
            for _i in range(_device_count):
                _devices.append(_torch.cuda.get_device_name(_i))
            check_ok("PyTorch GPU: 可用", f"(CUDA {_cuda_ver}, {_device_count} 个设备: {', '.join(_devices)})")
        else:
            check_warn("PyTorch GPU: 不可用",
                       "(torch.cuda.is_available()=False — 本地模型推理将使用 CPU)")
    except ImportError:
        pass  # PyTorch not installed — not a requirement
    except Exception as _e:
        check_warn("PyTorch GPU 检测异常", str(_e))

    # =========================================================================
    # Check: Submodules (tinker-atropos RL training backend)
    # =========================================================================
    _section_summary()
    print()
    print(color("◆ 子模块", Colors.CYAN, Colors.BOLD))
    _section_reset()

    tinker_dir = PROJECT_ROOT / "tinker-atropos"
    if tinker_dir.exists() and (tinker_dir / "pyproject.toml").exists():
        py_version = sys.version_info
        if py_version.major >= 3 and py_version.minor >= 11:
            try:
                import tinker_atropos  # noqa: F401
                check_ok("tinker-atropos 已安装", f"({tinker_dir})")
            except ImportError:
                install_cmd = f"{_python_install_cmd()} -e ./tinker-atropos"
                check_warn("tinker-atropos found but not installed", f"(run: {install_cmd})")
                issues.append(f"Install tinker-atropos: {install_cmd}")
        else:
            check_warn("tinker-atropos requires Python 3.11+", f"(current: {py_version.major}.{py_version.minor})")
    else:
        check_warn("tinker-atropos not found", "(run: git submodule update --init --recursive)")

    # =========================================================================
    # Check: Tool Availability
    # =========================================================================
    _section_summary()
    print()
    print(color("◆ 工具可用性", Colors.CYAN, Colors.BOLD))
    _section_reset()
    
    try:
        # Add project root to path for imports
        sys.path.insert(0, str(PROJECT_ROOT))
        from model_tools import check_tool_availability, TOOLSET_REQUIREMENTS
        
        available, unavailable = check_tool_availability()
        available, unavailable = _apply_doctor_tool_availability_overrides(available, unavailable)
        
        for tid in available:
            info = TOOLSET_REQUIREMENTS.get(tid, {})
            check_ok(info.get("name", tid))
        
        for item in unavailable:
            env_vars = item.get("missing_vars") or item.get("env_vars") or []
            if env_vars:
                vars_str = ", ".join(env_vars)
                check_warn(item["name"], f"(missing {vars_str})")
            else:
                check_warn(item["name"], "(system dependency not met)")

        # Count disabled tools with API key requirements
        api_disabled = [u for u in unavailable if (u.get("missing_vars") or u.get("env_vars"))]
        if api_disabled:
            issues.append("Run 'hermes setup' to configure missing API keys for full tool access")
    except Exception as e:
        check_warn("Could not check tool availability", f"({e})")
    
    # =========================================================================
    # Check: Skills Hub
    # =========================================================================
    _section_summary()
    print()
    print(color("◆ 技能中心", Colors.CYAN, Colors.BOLD))
    _section_reset()

    hub_dir = HERMES_HOME / "skills" / ".hub"
    if hub_dir.exists():
        check_ok("Skills Hub directory exists")
        lock_file = hub_dir / "lock.json"
        if lock_file.exists():
            try:
                import json
                lock_data = json.loads(lock_file.read_text())
                count = len(lock_data.get("installed", {}))
                check_ok(f"Lock file OK ({count} hub-installed skill(s))")
            except Exception:
                check_warn("Lock file", "(corrupted or unreadable)")
        quarantine = hub_dir / "quarantine"
        q_count = sum(1 for d in quarantine.iterdir() if d.is_dir()) if quarantine.exists() else 0
        if q_count > 0:
            check_warn(f"{q_count} skill(s) in quarantine", "(pending review)")
    else:
        check_warn("Skills Hub directory not initialized", "(run: hermes skills list)")

    from hermes_cli.config import get_env_value
    github_token = get_env_value("GITHUB_TOKEN") or get_env_value("GH_TOKEN")
    if github_token:
        check_ok("GitHub token configured (authenticated API access)")
    else:
        check_warn("No GITHUB_TOKEN", f"(60 req/hr rate limit — set in {_DHH}/.env for better rates)")

    # =========================================================================
    # Memory Provider (only check the active provider, if any)
    # =========================================================================
    _section_summary()
    print()
    print(color("◆ 记忆提供商", Colors.CYAN, Colors.BOLD))
    _section_reset()

    _active_memory_provider = ""
    try:
        import yaml as _yaml
        _mem_cfg_path = HERMES_HOME / "config.yaml"
        if _mem_cfg_path.exists():
            with open(_mem_cfg_path) as _f:
                _raw_cfg = _yaml.safe_load(_f) or {}
            _active_memory_provider = (_raw_cfg.get("memory") or {}).get("provider", "")
    except Exception:
        pass

    if not _active_memory_provider:
        check_ok("Built-in memory active", "(no external provider configured — this is fine)")
    elif _active_memory_provider == "honcho":
        try:
            from plugins.memory.honcho.client import HonchoClientConfig, resolve_config_path
            hcfg = HonchoClientConfig.from_global_config()
            _honcho_cfg_path = resolve_config_path()

            if not _honcho_cfg_path.exists():
                check_warn("Honcho config not found", "run: hermes memory setup")
            elif not hcfg.enabled:
                check_info(f"Honcho disabled (set enabled: true in {_honcho_cfg_path} to activate)")
            elif not (hcfg.api_key or hcfg.base_url):
                check_fail("Honcho API key or base URL not set", "run: hermes memory setup")
                issues.append("No Honcho API key — run 'hermes memory setup'")
            else:
                from plugins.memory.honcho.client import get_honcho_client, reset_honcho_client
                reset_honcho_client()
                try:
                    get_honcho_client(hcfg)
                    check_ok(
                        "Honcho connected",
                        f"workspace={hcfg.workspace_id} mode={hcfg.recall_mode} freq={hcfg.write_frequency}",
                    )
                except Exception as _e:
                    check_fail("Honcho connection failed", str(_e))
                    issues.append(f"Honcho unreachable: {_e}")
        except ImportError:
            check_fail("honcho-ai not installed", "pip install honcho-ai")
            issues.append("Honcho is set as memory provider but honcho-ai is not installed")
        except Exception as _e:
            check_warn("Honcho check failed", str(_e))
    elif _active_memory_provider == "mem0":
        try:
            from plugins.memory.mem0 import _load_config as _load_mem0_config
            mem0_cfg = _load_mem0_config()
            mem0_key = mem0_cfg.get("api_key", "")
            if mem0_key:
                check_ok("Mem0 API key configured")
                check_info(f"user_id={mem0_cfg.get('user_id', '?')}  agent_id={mem0_cfg.get('agent_id', '?')}")
            else:
                check_fail("Mem0 API key not set", "(set MEM0_API_KEY in .env or run hermes memory setup)")
                issues.append("Mem0 is set as memory provider but API key is missing")
        except ImportError:
            check_fail("Mem0 plugin not loadable", "pip install mem0ai")
            issues.append("Mem0 is set as memory provider but mem0ai is not installed")
        except Exception as _e:
            check_warn("Mem0 check failed", str(_e))
    else:
        # Generic check for other memory providers (openviking, hindsight, etc.)
        try:
            from plugins.memory import load_memory_provider
            _provider = load_memory_provider(_active_memory_provider)
            if _provider and _provider.is_available():
                check_ok(f"{_active_memory_provider} provider active")
            elif _provider:
                check_warn(f"{_active_memory_provider} configured but not available", "run: hermes memory status")
            else:
                check_warn(f"{_active_memory_provider} plugin not found", "run: hermes memory setup")
        except Exception as _e:
            check_warn(f"{_active_memory_provider} check failed", str(_e))

    # =========================================================================
    # Local Models
    # =========================================================================
    _section_summary()
    print()
    print(color("◆ 本地模型", Colors.CYAN, Colors.BOLD))
    _section_reset()

    try:
        from hermes_cli.model_manager import (
            MODEL_REGISTRY,
            is_installed,
            check_requirements,
            _get_models_dir,
            _get_dir_size,
        )

        models_dir = _get_models_dir()
        if models_dir.exists():
            check_ok(f"模型目录存在: {models_dir}")
        else:
            check_warn(f"模型目录不存在", f"(将在首次安装时创建)")

        installed_count = 0
        total_size = 0.0

        for m in MODEL_REGISTRY:
            model_id = m["id"]
            inst = is_installed(model_id)
            size = _get_dir_size(models_dir / m["local_dir"]) if inst else 0

            if inst:
                installed_count += 1
                total_size += size
                check_ok(f"{m['name']} ({size}MB)")
            else:
                check_warn(f"{m['name']}", f"(需 {m['size_mb']}MB)")

            # Check runtime requirements
            ok, msg = check_requirements(model_id)
            if ok:
                check_info(f"运行时就绪: {msg}")
            else:
                check_info(f"⚠ {msg}")

        if installed_count > 0:
            check_ok(f"已安装 {installed_count}/{len(MODEL_REGISTRY)} 个本地模型，占用 {round(total_size, 1)}MB")
        else:
            check_info("运行 'hermes local-models list' 查看可用模型")

    except ImportError:
        check_warn("model_manager 模块未加载", "(hermes local-models 命令不可用)")
    except Exception as e:
        check_warn("本地模型检查失败", str(e))

    # =========================================================================
    # External Model Services (Ollama, Fallback Chain)
    # =========================================================================
    _section_summary()
    print()
    print(color("◆ 外部模型服务", Colors.CYAN, Colors.BOLD))
    _section_reset()

    _config = None  # lazy-loaded

    try:
        from hermes_cli.config import load_config as _load_config_for_doctor
        _config = _load_config_for_doctor()
    except Exception:
        pass

    # ── D3.1: Ollama 运行状态检测 ──
    try:
        import httpx as _httpx
        _ollama_url = "http://localhost:11434/api/tags"
        _ollama_resp = _httpx.get(_ollama_url, timeout=3)
        if _ollama_resp.status_code == 200:
            _models = _ollama_resp.json().get("models", [])
            _model_names = [m.get("name", "?") for m in _models]
            _size_str = f"（{len(_models)} 个模型: {', '.join(_model_names[:5])}{'...' if len(_model_names) > 5 else ''}）"
            check_ok("Ollama 服务运行中", _size_str)
        else:
            check_warn("Ollama 服务响应异常", f"HTTP {_ollama_resp.status_code}")
    except ImportError:
        check_warn("Ollama 状态检测", "httpx 未安装，跳过")
    except _httpx.ConnectError:
        check_warn("Ollama 未运行", "（如需本地推理: ollama serve &）")
    except Exception as _e:
        check_warn("Ollama 检测失败", str(_e))

    # ── D3.2 + D3.3: Fallback 链一致性检测 ──
    if _config is None:
        check_warn("Fallback 链检测", "（无法读取配置文件，跳过）")
    else:
        _model_cfg = _config.get("model", {}) or {}
        _primary_model = _model_cfg.get("default", "") if isinstance(_model_cfg, dict) else ""
        _primary_provider = _model_cfg.get("provider", "") if isinstance(_model_cfg, dict) else ""

        if _primary_model:
            check_ok(f"主力模型: {_primary_model}", f"（Provider: {_primary_provider or '未指定'}）")
        else:
            check_warn("未配置主力模型", "（运行 hermes setup 或 quickstart）")

        # 收集 fallback 链
        _fb_chain = []
        _fb_config = _config.get("fallback_providers") or _config.get("fallback_model") or []
        if isinstance(_fb_config, dict):
            _fb_config = [_fb_config]
        if isinstance(_fb_config, list):
            _fb_chain = _fb_config

        if not _fb_chain:
            check_warn("未配置 Fallback 链", "（主力模型失败时将无法自动切换）")
        else:
            check_ok(f"Fallback 链已配置", f"（{len(_fb_chain)} 个条目）")

            for _i, _entry in enumerate(_fb_chain):
                _fb_provider = _entry.get("provider", "") if isinstance(_entry, dict) else ""
                _fb_model = _entry.get("model", "") if isinstance(_entry, dict) else ""
                _prefix = f"  [{_i + 1}]"

                if not _fb_provider:
                    check_warn(f"{_prefix} Fallback 条目缺少 provider")
                if not _fb_model:
                    check_warn(f"{_prefix} Fallback 条目缺少 model")

                # D3.3: 主力-Fallback 重复检测
                if _primary_model and _fb_model == _primary_model:
                    check_warn(f"{_prefix} Fallback 包含主力模型", f"（{_fb_model} — 故障切换时将跳过）")

                if _fb_provider and _fb_model:
                    check_ok(f"{_prefix} {_fb_provider}/{_fb_model}")

        # 检查 auxiliary.vision 配置
        _aux_cfg = _config.get("auxiliary", {}) or {}
        _vision_cfg = _aux_cfg.get("vision", {}) or {}
        if _vision_cfg.get("model"):
            check_ok("Auxiliary 视觉模型已配置", f"（{_vision_cfg.get('provider', '?')}/{_vision_cfg.get('model', '?')}）")

        # 配置不一致检测
        _has_fb_model = "fallback_model" in _config
        _has_fb_providers = "fallback_providers" in _config
        if _has_fb_model and _has_fb_providers:
            check_warn("配置不一致", "同时存在 fallback_model 和 fallback_providers 两个键，建议统一为 fallback_providers")

    # =========================================================================
    # 路由配置 (Phase 2)
    # =========================================================================
    _section_summary()
    _section_reset()
    print()
    print(color("◆ 路由配置", Colors.CYAN, Colors.BOLD))

    _routing_cfg = _config.get("model_routing", {}) or {}
    if not _routing_cfg:
        check_warn(
            "未配置 model_routing",
            "（图片/推理消息将使用统一模型，运行 quickstart 自动生成）",
        )
    else:
        _routing_default = _routing_cfg.get("default", {}) or {}
        _routing_vision = _routing_cfg.get("vision", {}) or {}
        _routing_reasoning = _routing_cfg.get("reasoning", {}) or {}

        if _routing_default.get("model"):
            check_ok(f"默认路由模型", f"（{_routing_default.get('model')}）")
        else:
            check_warn("缺少默认路由模型")

        if _routing_vision.get("model"):
            check_ok(f"视觉路由模型", f"（{_routing_vision.get('model')}）")
        else:
            check_warn("缺少视觉路由模型", "（图片/截图将无法自动切换模型）")

        if _routing_reasoning.get("model"):
            check_ok(f"推理路由模型", f"（{_routing_reasoning.get('model')}）")

    # =========================================================================
    # Profiles
    # =========================================================================
    try:
        from hermes_cli.profiles import list_profiles, _get_wrapper_dir, profile_exists
        import re as _re

        named_profiles = [p for p in list_profiles() if not p.is_default]
        if named_profiles:
            print()
            print(color("◆ 配置文件", Colors.CYAN, Colors.BOLD))
            check_ok(f"{len(named_profiles)} profile(s) found")
            wrapper_dir = _get_wrapper_dir()
            for p in named_profiles:
                parts = []
                if p.gateway_running:
                    parts.append("gateway running")
                if p.model:
                    parts.append(p.model[:30])
                if not (p.path / "config.yaml").exists():
                    parts.append("⚠ missing config")
                if not (p.path / ".env").exists():
                    parts.append("no .env")
                wrapper = wrapper_dir / p.name
                if not wrapper.exists():
                    parts.append("no alias")
                status = ", ".join(parts) if parts else "configured"
                check_ok(f"  {p.name}: {status}")

            # Check for orphan wrappers
            if wrapper_dir.is_dir():
                for wrapper in wrapper_dir.iterdir():
                    if not wrapper.is_file():
                        continue
                    try:
                        content = wrapper.read_text()
                        if "hermes -p" in content:
                            _m = _re.search(r"hermes -p (\S+)", content)
                            if _m and not profile_exists(_m.group(1)):
                                check_warn(f"Orphan alias: {wrapper.name} → profile '{_m.group(1)}' no longer exists")
                    except Exception:
                        pass
    except ImportError:
        pass
    except Exception:
        pass

    # =========================================================================
    # Summary
    # =========================================================================
    _section_summary()
    print()

    # D4: 显示检测项统计
    total_checks = _total_ok + _total_warn + _total_fail
    if total_checks > 0:
        stat_parts = []
        if _total_ok:
            stat_parts.append(color(f"{_total_ok} ✓", Colors.GREEN))
        if _total_warn:
            stat_parts.append(color(f"{_total_warn} ⚠", Colors.YELLOW))
        if _total_fail:
            stat_parts.append(color(f"{_total_fail} ✗", Colors.RED))
        print(f"  检测项: {'  '.join(stat_parts)}")
        print()

    remaining_issues = issues + manual_issues
    if should_fix and fixed_count > 0:
        print(color("─" * 60, Colors.GREEN))
        print(color(f"  Fixed {fixed_count} issue(s).", Colors.GREEN, Colors.BOLD), end="")
        if remaining_issues:
            print(color(f" {len(remaining_issues)} issue(s) require manual intervention.", Colors.YELLOW, Colors.BOLD))
        else:
            print()
        print()
        if remaining_issues:
            for i, issue in enumerate(remaining_issues, 1):
                print(f"  {i}. {issue}")
            print()
    elif remaining_issues:
        print(color("─" * 60, Colors.YELLOW))
        print(color(f"  Found {len(remaining_issues)} issue(s) to address:", Colors.YELLOW, Colors.BOLD))
        print()
        for i, issue in enumerate(remaining_issues, 1):
            print(f"  {i}. {issue}")
        print()
        if not should_fix:
            print(color("  Tip: run 'hermes doctor --fix' to auto-fix what's possible.", Colors.DIM))
    else:
        print(color("─" * 60, Colors.GREEN))
        print(color("  All checks passed! 🎉", Colors.GREEN, Colors.BOLD))
    
    print()

"""OpenViking memory plugin — full bidirectional MemoryProvider interface.

Context database by Volcengine (ByteDance) that organizes agent knowledge
into a filesystem hierarchy (viking:// URIs) with tiered context loading,
automatic memory extraction, and session management.

Original PR #3369 by Mibayy, rewritten to use the full OpenViking session
lifecycle instead of read-only search endpoints.

Config via environment variables (profile-scoped via each profile's .env):
  OPENVIKING_ENDPOINT  — Server URL (default: http://127.0.0.1:1933)
  OPENVIKING_API_KEY   — API key (required for authenticated servers)
  OPENVIKING_ACCOUNT   — Tenant account (default: default)
  OPENVIKING_USER      — Tenant user (default: default)
  OPENVIKING_AGENT   — Tenant agent (default: hermes)

Capabilities:
  - Automatic memory extraction on session commit (6 categories)
  - Tiered context: L0 (~100 tokens), L1 (~2k), L2 (full)
  - Semantic search with hierarchical directory retrieval
  - Filesystem-style browsing via viking:// URIs
  - Resource ingestion (URLs, docs, code)
"""

from __future__ import annotations

import atexit
import json
import logging
import mimetypes
import os
import stat
import tempfile
import threading
import uuid
import zipfile
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse
from urllib.request import url2pathname

from agent.memory_provider import MemoryProvider
from tools.registry import tool_error
from utils import atomic_json_write, env_var_enabled

logger = logging.getLogger(__name__)

_DEFAULT_ENDPOINT = "http://127.0.0.1:1933"
_TIMEOUT = 30.0
_SESSION_DRAIN_TIMEOUT = 10.0
_DEFERRED_COMMIT_TIMEOUT = (_TIMEOUT * 2) + 5.0
_REMOTE_RESOURCE_PREFIXES = ("http://", "https://", "git@", "ssh://", "git://")
_SYNC_TRACE_ENV = "HERMES_OPENVIKING_SYNC_TRACE"
_OPENVIKING_RECALL_TOOL_NAMES = {"viking_search", "viking_read", "viking_browse"}

# Maps the viking_remember `category` enum to a viking:// subdirectory.
# Keep in sync with REMEMBER_SCHEMA.parameters.properties.category.enum.
_CATEGORY_SUBDIR_MAP = {
    "preference": "preferences",
    "entity": "entities",
    "event": "events",
    "case": "cases",
    "pattern": "patterns",
}
_DEFAULT_MEMORY_SUBDIR = "preferences"

# Maps the built-in memory tool's `target` ("user" vs "memory") to a subdir
# for on_memory_write mirroring. User profile facts → preferences; agent
# notes / observations → patterns. Anything unknown falls back to the default.
_MEMORY_WRITE_TARGET_SUBDIR_MAP = {
    "user": "preferences",
    "memory": "patterns",
}
_LOCAL_OPENVIKING_HOSTS = {"localhost", "127.0.0.1", "::1"}
_LOCAL_OPENVIKING_AUTOSTART_TIMEOUT = 60.0
_OPENVIKING_SERVER_LOG_RELATIVE_PATH = Path("logs") / "openviking-server.log"
_OPENVIKING_RESPONDED_FAILURE_PREFIX = "OpenViking server responded"
_SETUP_CANCELLED = object()


@dataclass(frozen=True)
class _OvcliProfile:
    source: str
    name: str
    path: Path
    data: dict
    values: dict
    is_active: bool = False


class _OpenVikingHTTPError(RuntimeError):
    def __init__(self, message: str, status_code: Optional[int] = None):
        super().__init__(message)
        self.status_code = status_code


def _sanitize_openviking_error_message(message: str, status_code: Optional[int] = None) -> str:
    text = (message or "").strip()
    status = f"HTTP {status_code}" if status_code else "HTTP error"
    looks_like_html = bool(re.search(r"^\s*<(!doctype|html|head|body)\b", text, flags=re.IGNORECASE))
    if looks_like_html:
        title_match = re.search(r"<title[^>]*>(.*?)</title>", text, flags=re.IGNORECASE | re.DOTALL)
        if title_match:
            title = re.sub(r"\s+", " ", title_match.group(1)).strip()
            if "|" in title:
                title = title.split("|", 1)[1].strip()
            if status_code and title.startswith(f"{status_code}:"):
                title = title.split(":", 1)[1].strip()
            if title:
                return f"{status}: {title}"
        return f"{status}: OpenViking endpoint returned an HTML error page."

    if len(text) > 300:
        return text[:297].rstrip() + "..."
    return text or status


def _format_openviking_exception(error: Exception) -> str:
    status_code = None
    if isinstance(error, _OpenVikingHTTPError):
        status_code = error.status_code
    else:
        response = getattr(error, "response", None)
        status_code = getattr(response, "status_code", None)
    return _sanitize_openviking_error_message(str(error), status_code)


def _derive_openviking_user_text(content: Any) -> str:
    """Strip Hermes slash-skill scaffolding before sending content to OpenViking.

    Defense-in-depth: MemoryManager already strips skill scaffolding for the
    whole provider fan-out (see ``MemoryManager._strip_skill_scaffolding``), so
    in normal operation this receives already-clean text and passes it through
    unchanged. It stays here so OpenViking is correct if its hooks are ever
    invoked outside the manager. Delegates to the canonical extractor in
    ``agent.skill_commands`` — no duplicated marker literals, no drift risk.
    """
    return extract_user_instruction_from_skill_message(content) or ""


def _sync_trace_enabled() -> bool:
    return os.environ.get(_SYNC_TRACE_ENV, "").strip().lower() in {"1", "true", "yes", "on"}


def _preview(value: Any, limit: int = 160) -> str:
    text = "" if value is None else str(value)
    text = text.replace("\n", "\\n")
    if len(text) > limit:
        return text[:limit] + "..."
    return text


# ---------------------------------------------------------------------------
# Process-level atexit safety net — ensures pending sessions are committed
# even if shutdown_memory_provider is never called (e.g. gateway crash,
# SIGKILL, or exception in the session expiry watcher preventing shutdown).
# ---------------------------------------------------------------------------
_last_active_provider: Optional["OpenVikingMemoryProvider"] = None


def _atexit_commit_sessions():
    """Fire on_session_end for the last active provider on process exit."""
    global _last_active_provider
    provider = _last_active_provider
    if provider is None:
        return
    _last_active_provider = None
    try:
        provider.on_session_end([])
    except Exception:
        pass  # best-effort at shutdown time


atexit.register(_atexit_commit_sessions)


# ---------------------------------------------------------------------------
# HTTP helper — uses httpx to avoid requiring the openviking SDK
# ---------------------------------------------------------------------------

def _get_httpx():
    """Lazy import httpx."""
    try:
        import httpx
        return httpx
    except ImportError:
        return None


class _VikingClient:
    """Thin HTTP client for the OpenViking REST API."""

    def __init__(self, endpoint: str, api_key: str = "",
                 account: str = "", user: str = "", agent: str = ""):
        self._endpoint = endpoint.rstrip("/")
        self._api_key = api_key
        self._account = account or os.environ.get("OPENVIKING_ACCOUNT", "default")
        self._user = user or os.environ.get("OPENVIKING_USER", "default")
        self._agent = agent or os.environ.get("OPENVIKING_AGENT", "hermes")
        self._httpx = _get_httpx()
        if self._httpx is None:
            raise ImportError("httpx is required for OpenViking: pip install httpx")

    def _headers(self) -> dict:
        # Always send tenant headers when account/user are configured.
        # OpenViking 0.3.x requires X-OpenViking-Account and X-OpenViking-User
        # for ROOT API key requests to tenant-scoped APIs — omitting them
        # causes INVALID_ARGUMENT errors even when account="default".
        # User-level keys can omit them (server derives tenancy from the key),
        # but ROOT keys must always include them explicitly.
        h = {
            "Content-Type": "application/json",
            "X-OpenViking-Agent": self._agent,
        }
        if self._account:
            h["X-OpenViking-Account"] = self._account
        if self._user:
            h["X-OpenViking-User"] = self._user
        if self._api_key:
            h["X-API-Key"] = self._api_key
            h["Authorization"] = "Bearer " + self._api_key
        return h

    def _url(self, path: str) -> str:
        return f"{self._endpoint}{path}"

    def _multipart_headers(self) -> dict:
        headers = self._headers()
        headers.pop("Content-Type", None)
        return headers

    def _parse_response(self, resp) -> dict:
        try:
            data = resp.json()
        except Exception:
            data = None

        if resp.status_code >= 400:
            if isinstance(data, dict):
                error = data.get("error")
                if isinstance(error, dict):
                    code = error.get("code", "HTTP_ERROR")
                    message = error.get("message", resp.text)
                    raise RuntimeError(f"{code}: {message}")
                if data.get("status") == "error":
                    raise RuntimeError(str(data))
            resp.raise_for_status()

        if isinstance(data, dict) and data.get("status") == "error":
            error = data.get("error")
            if isinstance(error, dict):
                code = error.get("code", "OPENVIKING_ERROR")
                message = error.get("message", "")
                raise RuntimeError(f"{code}: {message}")
            raise RuntimeError(str(data))

        if data is None:
            return {}
        return data

    def get(self, path: str, **kwargs) -> dict:
        resp = self._httpx.get(
            self._url(path), headers=self._headers(), timeout=_TIMEOUT, **kwargs
        )
        return self._parse_response(resp)

    def post(self, path: str, payload: dict = None, **kwargs) -> dict:
        resp = self._httpx.post(
            self._url(path), json=payload or {}, headers=self._headers(),
            timeout=_TIMEOUT, **kwargs
        )
        return self._parse_response(resp)

    def upload_temp_file(self, file_path: Path) -> str:
        mime_type = mimetypes.guess_type(file_path.name)[0] or "application/octet-stream"
        with file_path.open("rb") as f:
            resp = self._httpx.post(
                self._url("/api/v1/resources/temp_upload"),
                files={"file": (file_path.name, f, mime_type)},
                headers=self._multipart_headers(),
                timeout=_TIMEOUT,
            )
        data = self._parse_response(resp)
        result = data.get("result", {})
        temp_file_id = result.get("temp_file_id", "")
        if not temp_file_id:
            raise RuntimeError("OpenViking temp upload did not return temp_file_id")
        return temp_file_id

    def health(self) -> bool:
        try:
            resp = self._httpx.get(
                self._url("/health"), headers=self._headers(), timeout=3.0
            )
            return resp.status_code == 200
        except Exception:
            return False


# ---------------------------------------------------------------------------
# Tool schemas
# ---------------------------------------------------------------------------

SEARCH_SCHEMA = {
    "name": "viking_search",
    "description": (
        "Semantic search over the OpenViking knowledge base. "
        "Returns ranked results with viking:// URIs for deeper reading. "
        "Use mode='deep' for complex queries that need reasoning across "
        "multiple sources, 'fast' for simple lookups."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "Search query."},
            "mode": {
                "type": "string", "enum": ["auto", "fast", "deep"],
                "description": "Search depth (default: auto).",
            },
            "scope": {
                "type": "string",
                "description": "Viking URI prefix to scope search (e.g. 'viking://resources/docs/').",
            },
            "limit": {"type": "integer", "description": "Max results (default: 10)."},
        },
        "required": ["query"],
    },
}

READ_SCHEMA = {
    "name": "viking_read",
    "description": (
        "Read content at a viking:// URI. Three detail levels:\n"
        "  abstract — ~100 token summary (L0)\n"
        "  overview — ~2k token key points (L1)\n"
        "  full — complete content (L2)\n"
        "Start with abstract/overview, only use full when you need details."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "uri": {"type": "string", "description": "viking:// URI to read."},
            "level": {
                "type": "string", "enum": ["abstract", "overview", "full"],
                "description": "Detail level (default: overview).",
            },
        },
        "required": ["uri"],
    },
}

BROWSE_SCHEMA = {
    "name": "viking_browse",
    "description": (
        "Browse the OpenViking knowledge store like a filesystem.\n"
        "  list — show directory contents\n"
        "  tree — show hierarchy\n"
        "  stat — show metadata for a URI"
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "action": {
                "type": "string", "enum": ["tree", "list", "stat"],
                "description": "Browse action.",
            },
            "path": {
                "type": "string",
                "description": "Viking URI path (default: viking://). Examples: 'viking://resources/', 'viking://user/memories/'.",
            },
        },
        "required": ["action"],
    },
}

REMEMBER_SCHEMA = {
    "name": "viking_remember",
    "description": (
        "Explicitly store a fact or memory in the OpenViking knowledge base. "
        "Use for important information the agent should remember long-term. "
        "The system automatically categorizes and indexes the memory."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "content": {"type": "string", "description": "The information to remember."},
            "category": {
                "type": "string",
                "enum": ["preference", "entity", "event", "case", "pattern"],
                "description": "Memory category (default: auto-detected).",
            },
        },
        "required": ["content"],
    },
}

ADD_RESOURCE_SCHEMA = {
    "name": "viking_add_resource",
    "description": (
        "Add a remote URL or local file/directory to the OpenViking knowledge base. "
        "Remote resources must be public http(s), git, or ssh URLs. "
        "Local files are uploaded first using OpenViking temp_upload. "
        "The system automatically parses, indexes, and generates summaries."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "url": {"type": "string", "description": "Remote URL or local file/directory path to add."},
            "reason": {
                "type": "string",
                "description": "Why this resource is relevant (improves search).",
            },
            "to": {
                "type": "string",
                "description": "Optional target viking:// URI for the resource.",
            },
            "parent": {
                "type": "string",
                "description": "Optional parent viking:// URI. Cannot be used with to.",
            },
            "instruction": {
                "type": "string",
                "description": "Optional processing instruction for semantic extraction.",
            },
            "wait": {
                "type": "boolean",
                "description": "Whether to wait for processing to complete.",
            },
            "timeout": {
                "type": "number",
                "description": "Timeout in seconds when wait is true.",
            },
        },
        "required": ["url"],
    },
}


# Recall tools (read-only) whose results we never re-ingest into OpenViking —
# echoing recalled memory back into the session transcript would re-store it.
# Write tools (viking_remember / viking_add_resource) are intentionally NOT
# here. Derived from the canonical schema names so renames can't desync.
_OPENVIKING_RECALL_TOOL_NAMES = {
    SEARCH_SCHEMA["name"],
    READ_SCHEMA["name"],
    BROWSE_SCHEMA["name"],
}


def _zip_directory(dir_path: Path) -> Path:
    """Create a temporary zip file containing a directory tree."""
    root = dir_path.resolve()
    zip_path = Path(tempfile.gettempdir()) / f"openviking_upload_{uuid.uuid4().hex}.zip"
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zipf:
        for file_path in dir_path.rglob("*"):
            if file_path.is_symlink():
                continue
            if file_path.is_file():
                try:
                    file_path.resolve().relative_to(root)
                except ValueError:
                    continue
                arcname = str(file_path.relative_to(dir_path)).replace("\\", "/")
                zipf.write(file_path, arcname=arcname)
    return zip_path


def _is_windows_absolute_path(value: str) -> bool:
    return (
        len(value) >= 3
        and value[0].isalpha()
        and value[1] == ":"
        and value[2] in {"/", "\\"}
    )


def _is_remote_resource_source(value: str) -> bool:
    return value.startswith(_REMOTE_RESOURCE_PREFIXES)


def _is_local_path_reference(value: str) -> bool:
    if not value or "\n" in value or "\r" in value:
        return False
    if _is_remote_resource_source(value):
        return False
    if _is_windows_absolute_path(value):
        return True
    return (
        value.startswith(("/", "./", "../", "~/", ".\\", "..\\", "~\\"))
        or "/" in value
        or "\\" in value
    )


def _path_from_file_uri(uri: str) -> Path | str:
    parsed = urlparse(uri)
    if parsed.netloc not in {"", "localhost"}:
        return f"Unsupported non-local file URI: {uri}"
    return Path(url2pathname(parsed.path)).expanduser()


def _clean_config_value(value: Any) -> str:
    return value.strip() if isinstance(value, str) else ""


def _default_ovcli_config_path() -> Path:
    return Path.home() / _OVCLI_DEFAULT_RELATIVE_PATH


def _resolve_ovcli_config_path(config_path: str = "") -> Path:
    env_path = os.environ.get(_OVCLI_CONFIG_ENV, "").strip()
    if env_path:
        return Path(env_path).expanduser()
    if config_path:
        return Path(config_path).expanduser()
    return _default_ovcli_config_path()


def _ovcli_config_dir() -> Path:
    return _default_ovcli_config_path().parent


def _load_ovcli_config(path: Optional[Path] = None) -> dict:
    config_path = path or _resolve_ovcli_config_path()
    if not config_path.exists():
        return {}
    with config_path.open(encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, dict):
        raise ValueError(f"OpenViking CLI config must be a JSON object: {config_path}")
    return data


def _connection_values_from_ovcli(data: dict) -> dict:
    api_key = _clean_config_value(data.get("api_key")) or _clean_config_value(data.get("root_api_key"))
    root_api_key = _clean_config_value(data.get("root_api_key"))
    send_identity = not api_key or api_key == root_api_key
    account = _clean_config_value(data.get("account") or data.get("account_id"))
    user = _clean_config_value(data.get("user") or data.get("user_id"))
    return {
        "endpoint": _normalize_openviking_url(data.get("url")),
        "api_key": api_key,
        "root_api_key": root_api_key,
        "account": account if send_identity else "",
        "user": user if send_identity else "",
        "agent": _clean_config_value(data.get("actor_peer_id") or data.get("agent_id")),
    }


def _is_valid_ovcli_profile_name(name: str) -> bool:
    if not name or name.strip() != name or name.startswith("."):
        return False
    if "/" in name or "\\" in name:
        return False
    return all(ch.isascii() and (ch.isalnum() or ch in {"-", "_"}) for ch in name)


def _validate_openviking_identity_value(value: str, *, field: str) -> tuple[bool, str, str]:
    label = "Account ID" if field == "account" else "User ID"
    identifier = "account_id" if field == "account" else "user_id"
    trimmed = value.strip()
    if not trimmed:
        return False, f"{label} cannot be empty.", ""
    if trimmed != value:
        return False, f"{label} cannot start or end with whitespace.", ""
    if field == "account" and trimmed.startswith("_"):
        return False, "Account ID cannot start with '_'.", ""
    if not all(ch.isascii() and (ch.isalnum() or ch in {"_", "-", ".", "@"}) for ch in trimmed):
        return False, f"{label} can only contain letters, numbers, '_', '-', '.', and '@'.", ""
    if trimmed.count("@") > 1:
        return False, f"{identifier} must have at most one '@'.", ""
    return True, "", trimmed


def _normalize_openviking_url(url: str) -> str:
    trimmed = _clean_config_value(url).rstrip("/")
    if not trimmed:
        return _DEFAULT_ENDPOINT
    lower = trimmed.lower()
    if lower in {"::1", "[::1]"}:
        return "http://[::1]:1933"
    if lower.startswith("[::1]:"):
        return f"http://[::1]:{trimmed.rsplit(':', 1)[1]}"
    if lower.startswith("::1:"):
        return f"http://[::1]:{trimmed.rsplit(':', 1)[1]}"
    if "://" in trimmed:
        return trimmed
    host, _sep, port = trimmed.partition(":")
    if host.lower() in {"localhost", "127.0.0.1"}:
        return f"http://{host}:{port or '1933'}"
    return trimmed


def _load_profile(path: Path, *, source: str, name: str) -> Optional[_OvcliProfile]:
    try:
        data = _load_ovcli_config(path)
    except Exception as e:
        logger.debug("Skipping invalid OpenViking CLI config %s: %s", path, e)
        return None
    return _OvcliProfile(
        source=source,
        name=name,
        path=path,
        data=data,
        values=_connection_values_from_ovcli(data),
    )


def _profile_identity(path: Path) -> str:
    try:
        return str(path.expanduser().resolve())
    except OSError:
        return str(path.expanduser())


def _profiles_equivalent(left: _OvcliProfile, right: _OvcliProfile) -> bool:
    return left.values == right.values


def _discover_ovcli_profiles() -> list[_OvcliProfile]:
    profiles: list[_OvcliProfile] = []
    seen_paths: set[str] = set()

    def add(path: Path, *, source: str, name: str) -> None:
        if not path.exists() or not path.is_file():
            return
        identity = _profile_identity(path)
        if identity in seen_paths:
            return
        profile = _load_profile(path, source=source, name=name)
        if profile is None:
            return
        seen_paths.add(identity)
        profiles.append(profile)

    env_path = os.environ.get(_OVCLI_CONFIG_ENV, "").strip()
    if env_path:
        add(Path(env_path).expanduser(), source="env", name=_OVCLI_CONFIG_ENV)

    active_path = _default_ovcli_config_path()
    active_profile = _load_profile(active_path, source="active", name="active") if active_path.exists() else None

    config_dir = _ovcli_config_dir()
    saved_start = len(profiles)
    if config_dir.exists():
        for path in sorted(config_dir.iterdir(), key=lambda item: item.name):
            if not path.is_file():
                continue
            name = path.name.removeprefix(_OVCLI_SAVED_PREFIX)
            if name == path.name or name == "bak" or not _is_valid_ovcli_profile_name(name):
                continue
            add(path, source="saved", name=name)

    if active_profile is not None:
        marked_active = False
        for idx in range(saved_start, len(profiles)):
            if profiles[idx].source == "saved" and _profiles_equivalent(profiles[idx], active_profile):
                profiles[idx] = replace(profiles[idx], is_active=True)
                marked_active = True
                break
        has_env_profile = any(profile.source == "env" for profile in profiles)
        has_saved_profile = any(profile.source == "saved" for profile in profiles)
        active_identity = _profile_identity(active_profile.path)
        if not marked_active and not has_env_profile and not has_saved_profile and active_identity not in seen_paths:
            profiles.append(active_profile)

    return profiles


def _is_local_openviking_url(value: str) -> bool:
    candidate = _normalize_openviking_url(value)
    if not candidate:
        return False
    if "://" not in candidate:
        candidate = f"//{candidate}"
    parsed = urlparse(candidate)
    scheme = (parsed.scheme or "http").lower()
    return scheme == "http" and (parsed.hostname or "").lower() in _LOCAL_OPENVIKING_HOSTS


def _load_hermes_openviking_config() -> dict:
    try:
        from hermes_cli.config import load_config

        config = load_config()
        memory_config = config.get("memory", {}) if isinstance(config, dict) else {}
        provider_config = memory_config.get("openviking", {}) if isinstance(memory_config, dict) else {}
        return dict(provider_config) if isinstance(provider_config, dict) else {}
    except Exception:
        return {}


def _env_value(name: str) -> Optional[str]:
    return os.environ[name].strip() if name in os.environ else None


def _first_nonempty(*values: Optional[str], default: str = "") -> str:
    for value in values:
        if value:
            return value
    return default


def _resolve_connection_settings(provider_config: Optional[dict] = None) -> dict:
    provider_config = dict(provider_config or {})
    ovcli_values: dict = {}
    if provider_config.get("use_ovcli_config"):
        ovcli_path = _resolve_ovcli_config_path(str(provider_config.get("ovcli_config_path") or ""))
        ovcli_values = _connection_values_from_ovcli(_load_ovcli_config(ovcli_path))

    endpoint_env = _env_value("OPENVIKING_ENDPOINT")
    api_key_env = _env_value("OPENVIKING_API_KEY")
    account_env = _env_value("OPENVIKING_ACCOUNT")
    user_env = _env_value("OPENVIKING_USER")
    agent_env = _env_value("OPENVIKING_AGENT")

    return {
        "endpoint": _first_nonempty(endpoint_env, ovcli_values.get("endpoint"), default=_DEFAULT_ENDPOINT),
        "api_key": api_key_env if api_key_env is not None else ovcli_values.get("api_key", ""),
        "account": account_env if account_env is not None else ovcli_values.get("account", ""),
        "user": user_env if user_env is not None else ovcli_values.get("user", ""),
        "agent": _first_nonempty(agent_env, ovcli_values.get("agent"), default=_DEFAULT_AGENT),
    }


def _env_writes_from_connection_values(values: dict) -> dict:
    writes = {}
    mapping = {
        "OPENVIKING_ENDPOINT": "endpoint",
        "OPENVIKING_API_KEY": "api_key",
        "OPENVIKING_ACCOUNT": "account",
        "OPENVIKING_USER": "user",
        "OPENVIKING_AGENT": "agent",
    }
    for env_key, value_key in mapping.items():
        value = _clean_config_value(values.get(value_key))
        if value:
            writes[env_key] = value
    return writes


def _restrict_secret_file_permissions(path: Path) -> None:
    try:
        path.chmod(stat.S_IRUSR | stat.S_IWUSR)
    except OSError:
        pass


def _write_env_vars(env_path: Path, env_writes: dict, remove_keys: tuple[str, ...] = ()) -> None:
    env_path.parent.mkdir(parents=True, exist_ok=True)
    remove_set = set(remove_keys) - set(env_writes)
    existing_lines = env_path.read_text(encoding="utf-8").splitlines() if env_path.exists() else []
    updated_keys = set()
    new_lines = []
    for line in existing_lines:
        key_match = line.split("=", 1)[0].strip() if "=" in line else ""
        if key_match in remove_set:
            continue
        if key_match in env_writes:
            new_lines.append(f"{key_match}={env_writes[key_match]}")
            updated_keys.add(key_match)
        else:
            new_lines.append(line)
    for key, val in env_writes.items():
        if key not in updated_keys:
            new_lines.append(f"{key}={val}")
    env_path.write_text("\n".join(new_lines) + ("\n" if new_lines else ""), encoding="utf-8")
    _restrict_secret_file_permissions(env_path)


def _remember_ovcli_path(provider_config: dict, ovcli_path: Path) -> None:
    default_path = _default_ovcli_config_path().expanduser()
    if os.environ.get(_OVCLI_CONFIG_ENV, "").strip() or ovcli_path.expanduser() != default_path:
        provider_config["ovcli_config_path"] = str(ovcli_path)
    else:
        provider_config.pop("ovcli_config_path", None)


def _ovcli_data_from_connection_values(values: dict) -> dict:
    data = {"url": _normalize_openviking_url(_clean_config_value(values.get("endpoint")) or _DEFAULT_ENDPOINT)}
    api_key = _clean_config_value(values.get("api_key"))
    root_api_key = _clean_config_value(values.get("root_api_key"))
    account = _clean_config_value(values.get("account"))
    user = _clean_config_value(values.get("user"))
    agent = _clean_config_value(values.get("agent")) or _DEFAULT_AGENT
    if api_key:
        data["api_key"] = api_key
    if root_api_key:
        data["root_api_key"] = root_api_key
    if account:
        data["account"] = account
    if user:
        data["user"] = user
    if agent:
        data["actor_peer_id"] = agent
    return data


def _write_ovcli_config(path: Path, values: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(_ovcli_data_from_connection_values(values), indent=2) + "\n", encoding="utf-8")
    _restrict_secret_file_permissions(path)


# ---------------------------------------------------------------------------
# MemoryProvider implementation
# ---------------------------------------------------------------------------

class OpenVikingMemoryProvider(MemoryProvider):
    """Full bidirectional memory via OpenViking context database."""

    def __init__(self):
        self._client: Optional[_VikingClient] = None
        self._endpoint = ""
        self._api_key = ""
        self._session_id = ""
        self._turn_count = 0
        # Commit only after session writes drain. The set is keyed by the sid
        # the writer is POSTing under (snapshotted at spawn), so on_session_end
        # / on_session_switch see every still-alive writer for that sid even
        # if later writes have replaced the latest-tracked thread.
        self._inflight_writers: Dict[str, Set[threading.Thread]] = {}
        self._inflight_lock = threading.Lock()
        self._deferred_commit_sids: Set[str] = set()
        self._deferred_commit_threads: Set[threading.Thread] = set()
        self._deferred_commit_lock = threading.Lock()
        self._prefetch_result = ""
        self._prefetch_lock = threading.Lock()
        self._prefetch_thread: Optional[threading.Thread] = None

    @property
    def name(self) -> str:
        return "openviking"

    def is_available(self) -> bool:
        """Check if OpenViking endpoint is configured. No network calls."""
        return bool(os.environ.get("OPENVIKING_ENDPOINT"))

    def get_config_schema(self):
        return [
            {
                "key": "endpoint",
                "description": "OpenViking server URL",
                "required": True,
                "default": _DEFAULT_ENDPOINT,
                "env_var": "OPENVIKING_ENDPOINT",
            },
            {
                "key": "api_key",
                "description": "OpenViking API key (leave blank for local dev mode)",
                "secret": True,
                "env_var": "OPENVIKING_API_KEY",
            },
            {
                "key": "account",
                "description": "OpenViking tenant account ID ([default], used when local mode, OPENVIKING_API_KEY is empty)",
                "default": "default",
                "env_var": "OPENVIKING_ACCOUNT",
            },
            {
                "key": "user",
                "description": "OpenViking user ID within the account ([default], used when local mode, OPENVIKING_API_KEY is empty)",
                "default": "default",
                "env_var": "OPENVIKING_USER",
            },
            {
                "key": "agent",
                "description": "OpenViking agent ID within the account ([hermes], useful in multi-agent mode)",
                "default": "hermes",
                "env_var": "OPENVIKING_AGENT",
            },
        ]

    def initialize(self, session_id: str, **kwargs) -> None:
        self._endpoint = os.environ.get("OPENVIKING_ENDPOINT", _DEFAULT_ENDPOINT)
        self._api_key = os.environ.get("OPENVIKING_API_KEY", "")
        self._account = os.environ.get("OPENVIKING_ACCOUNT", "default")
        self._user = os.environ.get("OPENVIKING_USER", "default")
        self._agent = os.environ.get("OPENVIKING_AGENT", "hermes")
        self._session_id = session_id
        self._turn_count = 0

        try:
            self._client = _VikingClient(
                self._endpoint, self._api_key,
                account=self._account, user=self._user, agent=self._agent,
            )
            if not self._client.health():
                logger.warning("OpenViking server at %s is not reachable", self._endpoint)
                self._client = None
        except ImportError:
            logger.warning("httpx not installed — OpenViking plugin disabled")
            self._client = None

        # Register as the last active provider for atexit safety net
        global _last_active_provider
        _last_active_provider = self

    def system_prompt_block(self) -> str:
        if not self._client:
            return ""
        # Provide brief info about the knowledge base
        try:
            # Check what's in the knowledge base via a root listing
            resp = self._client.get("/api/v1/fs/ls", params={"uri": "viking://"})
            result = resp.get("result", [])
            children = len(result) if isinstance(result, list) else 0
            if children == 0:
                return ""
            return (
                "# OpenViking Knowledge Base\n"
                f"Active. Endpoint: {self._endpoint}\n"
                "Use viking_search to find information, viking_read for details "
                "(abstract/overview/full), viking_browse to explore.\n"
                "Use viking_remember to store facts, viking_add_resource to index URLs/docs."
            )
        except Exception as e:
            logger.warning("OpenViking system_prompt_block failed: %s", e)
            return (
                "# OpenViking Knowledge Base\n"
                f"Active. Endpoint: {self._endpoint}\n"
                "Use viking_search, viking_read, viking_browse, "
                "viking_remember, viking_add_resource."
            )

    def prefetch(self, query: str, *, session_id: str = "") -> str:
        """Return prefetched results from the background thread."""
        if self._prefetch_thread and self._prefetch_thread.is_alive():
            self._prefetch_thread.join(timeout=3.0)
        with self._prefetch_lock:
            result = self._prefetch_result
            self._prefetch_result = ""
        if not result:
            return ""
        return f"## OpenViking Context\n{result}"

    def queue_prefetch(self, query: str, *, session_id: str = "") -> None:
        """Fire a background search to pre-load relevant context."""
        if not self._client or not query:
            return

        def _run():
            try:
                client = _VikingClient(
                    self._endpoint, self._api_key,
                    account=self._account, user=self._user, agent=self._agent,
                )
                resp = client.post("/api/v1/search/find", {
                    "query": query,
                    "top_k": 5,
                })
                result = resp.get("result", {})
                parts = []
                for ctx_type in ("memories", "resources"):
                    items = result.get(ctx_type, [])
                    for item in items[:3]:
                        uri = item.get("uri", "")
                        abstract = item.get("abstract", "")
                        score = item.get("score", 0)
                        if abstract:
                            parts.append(f"- [{score:.2f}] {abstract} ({uri})")
                if parts:
                    with self._prefetch_lock:
                        self._prefetch_result = "\n".join(parts)
            except Exception as e:
                logger.debug("OpenViking prefetch failed: %s", e)

        self._prefetch_thread = threading.Thread(
            target=_run, daemon=True, name="openviking-prefetch"
        )
        self._prefetch_thread.start()

    def _spawn_writer(self, sid: str, target: Callable[[], None], name: str) -> None:
        """Spawn a daemon writer tracked in _inflight_writers[sid].

        Tracking is keyed by sid (not by a single latest-thread slot) so that
        on_session_end / on_session_switch can drain every still-alive writer
        for the session being committed.
        """
        holder: List[threading.Thread] = []

        def _wrapped():
            try:
                target()
            finally:
                with self._inflight_lock:
                    workers = self._inflight_writers.get(sid)
                    if workers is not None:
                        workers.discard(holder[0])
                        if not workers:
                            self._inflight_writers.pop(sid, None)

        thread = threading.Thread(target=_wrapped, daemon=True, name=name)
        holder.append(thread)
        with self._inflight_lock:
            self._inflight_writers.setdefault(sid, set()).add(thread)
        thread.start()

    def _drain_finalizers(self, timeout: float) -> bool:
        """Join every in-flight async session finalizer within a timeout.

        The switch-path commit runs on a daemon finalizer thread so it never
        blocks the caller's command thread; this lets shutdown and tests wait
        for those commits deterministically. Returns True if all drained.
        """
        deadline = time.monotonic() + timeout
        while True:
            with self._deferred_commit_lock:
                workers = [t for t in self._deferred_commit_threads if t.is_alive()]
            if not workers:
                return True
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                return False
            for t in workers:
                slice_left = deadline - time.monotonic()
                if slice_left <= 0:
                    break
                # Floor the per-join wait so a thread whose join() returns
                # instantly while still reporting alive can't hot-spin this loop.
                t.join(timeout=min(slice_left, 0.05))

    def _drain_writers(self, sid: str, timeout: float) -> bool:
        """Join every in-flight writer for sid within a shared timeout budget.

        Returns True if all writers drained, False if any are still alive when
        the budget runs out. Callers use the False return to skip the commit.
        """
        if not sid:
            return True
        deadline = time.monotonic() + timeout
        while True:
            with self._inflight_lock:
                workers = [t for t in self._inflight_writers.get(sid, ()) if t.is_alive()]
            if not workers:
                return True
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                return False
            for t in workers:
                slice_left = deadline - time.monotonic()
                if slice_left <= 0:
                    break
                t.join(timeout=slice_left)

    def _new_client(self) -> _VikingClient:
        return _VikingClient(
            self._endpoint,
            self._api_key,
            account=self._account,
            user=self._user,
            agent=self._agent,
        )

    @staticmethod
    def _text_part(content: str) -> Dict[str, str]:
        return {"type": "text", "text": content}

    @classmethod
    def _turn_batch_payload(cls, user_content: str, assistant_content: str) -> Dict[str, Any]:
        return {
            "messages": [
                {"role": "user", "parts": [cls._text_part(user_content)]},
                {"role": "assistant", "parts": [cls._text_part(assistant_content)]},
            ]
        }

    @classmethod
    def _post_session_turn(
        cls,
        client: _VikingClient,
        sid: str,
        user_content: str,
        assistant_content: str,
    ) -> None:
        client.post(
            f"/api/v1/sessions/{sid}/messages/batch",
            cls._turn_batch_payload(user_content, assistant_content),
        )

    def _session_has_pending_tokens(self, sid: str) -> bool:
        try:
            response = self._client.get(f"/api/v1/sessions/{sid}")
        except Exception:
            return False
        session = self._unwrap_result(response)
        if not isinstance(session, dict):
            return False
        try:
            return int(session.get("pending_tokens") or 0) > 0
        except (TypeError, ValueError):
            return False

    def _commit_session(self, sid: str, turn_count: int, *, context: str) -> bool:
        try:
            self._client.post(f"/api/v1/sessions/{sid}/commit")
            logger.info("OpenViking session %s committed %s (%d turns)", sid, context, turn_count)
            return True
        except Exception as e:
            logger.warning("OpenViking session commit failed for %s: %s", sid, e)
            return False

    def _schedule_deferred_commit(self, sid: str, turn_count: int) -> None:
        if not sid or turn_count <= 0:
            return
        with self._deferred_commit_lock:
            if sid in self._deferred_commit_sids:
                return
            self._deferred_commit_sids.add(sid)

        holder: List[threading.Thread] = []

        def _finalize() -> None:
            try:
                if not self._drain_writers(sid, timeout=_DEFERRED_COMMIT_TIMEOUT):
                    logger.warning(
                        "OpenViking writer for %s still alive after deferred drain — "
                        "leaving session uncommitted",
                        sid,
                    )
                    return
                self._commit_session(sid, turn_count, context="after deferred drain")
            finally:
                with self._deferred_commit_lock:
                    self._deferred_commit_sids.discard(sid)
                    if holder:
                        self._deferred_commit_threads.discard(holder[0])

        thread = threading.Thread(
            target=_finalize,
            daemon=True,
            name=f"openviking-finalize-{sid}",
        )
        holder.append(thread)
        with self._deferred_commit_lock:
            self._deferred_commit_threads.add(thread)
        thread.start()

    def sync_turn(self, user_content: str, assistant_content: str, *, session_id: str = "") -> None:
        """Record the conversation turn in OpenViking's session (non-blocking)."""
        if not self._client:
            return

        user_content = _derive_openviking_user_text(user_content)
        if not user_content:
            return

        turn_messages = (
            self._extract_current_turn_messages(messages, user_content, assistant_content)
            if messages is not None
            else []
        )
        if turn_messages:
            turn_messages = [dict(message) for message in turn_messages]
            for message in turn_messages:
                if message.get("role") == "user":
                    message["content"] = user_content
                    break
        batch_messages = self._messages_to_openviking_batch(turn_messages)

        if _sync_trace_enabled():
            logger.info(
                "OpenViking sync_turn trace: session_arg=%r cached_session=%r "
                "messages_param_supported=true messages_present=%s message_count=%s "
                "turn_message_count=%d batch_message_count=%d user_len=%d assistant_len=%d "
                "user_preview=%r assistant_preview=%r",
                session_id,
                self._session_id,
                messages is not None,
                len(messages) if messages is not None else None,
                len(turn_messages),
                len(batch_messages),
                len(str(user_content or "")),
                len(str(assistant_content or "")),
                _preview(user_content),
                _preview(assistant_content),
            )

        # Snapshot the sid and bump the turn counter atomically so a
        # concurrent on_session_switch/on_session_end can't interleave its
        # snapshot+reset between the read and the increment (lost turn) and so
        # the turn is unambiguously attributed to the session it targets.
        with self._session_state_lock:
            sid = str(session_id or self._session_id).strip()
            if not sid:
                return
            self._turn_count += 1

        def _sync():
            try:
                client = self._new_client()
                self._post_session_turn(
                    client,
                    sid,
                    user_content[:4000],
                    assistant_content[:4000],
                )
            except Exception as e:
                logger.debug("OpenViking sync_turn failed, reconnecting: %s", e)
                try:
                    client = self._new_client()
                    self._post_session_turn(
                        client,
                        sid,
                        user_content[:4000],
                        assistant_content[:4000],
                    )
                except Exception as retry_error:
                    logger.warning("OpenViking sync_turn failed: %s", retry_error)

                self._post_session_turn(
                    client,
                    sid,
                    user_content[:4000],
                    self._message_text(assistant_content)[:4000],
                )

            try:
                client = self._new_client()
                _post_turn(client)
            except Exception as e:
                logger.debug("OpenViking sync_turn failed, reconnecting: %s", e)
                try:
                    client = self._new_client()
                    _post_turn(client)
                except Exception as retry_error:
                    logger.warning("OpenViking sync_turn failed: %s", retry_error)

                self._post_session_turn(
                    client,
                    sid,
                    user_content[:4000],
                    self._message_text(assistant_content)[:4000],
                )

            try:
                client = self._new_client()
                _post_turn(client)
            except Exception as e:
                logger.debug("OpenViking sync_turn failed, reconnecting: %s", e)
                try:
                    client = self._new_client()
                    _post_turn(client)
                except Exception as retry_error:
                    logger.warning("OpenViking sync_turn failed: %s", retry_error)

                self._post_session_turn(
                    client,
                    sid,
                    user_content[:4000],
                    self._message_text(assistant_content)[:4000],
                )

            try:
                client = self._new_client()
                _post_turn(client)
            except Exception as e:
                logger.debug("OpenViking sync_turn failed, reconnecting: %s", e)
                try:
                    client = self._new_client()
                    _post_turn(client)
                except Exception as retry_error:
                    logger.warning("OpenViking sync_turn failed: %s", retry_error)

                self._post_session_turn(
                    client,
                    sid,
                    user_content[:4000],
                    self._message_text(assistant_content)[:4000],
                )

            try:
                client = self._new_client()
                _post_turn(client)
            except Exception as e:
                logger.debug("OpenViking sync_turn failed, reconnecting: %s", e)
                try:
                    client = self._new_client()
                    _post_turn(client)
                except Exception as retry_error:
                    logger.warning("OpenViking sync_turn failed: %s", retry_error)

                self._post_session_turn(
                    client,
                    sid,
                    user_content[:4000],
                    self._message_text(assistant_content)[:4000],
                )

            try:
                client = self._new_client()
                _post_turn(client)
            except Exception as e:
                logger.debug("OpenViking sync_turn failed, reconnecting: %s", e)
                try:
                    client = self._new_client()
                    _post_turn(client)
                except Exception as retry_error:
                    logger.warning("OpenViking sync_turn failed: %s", retry_error)

                self._post_session_turn(
                    client,
                    sid,
                    user_content[:4000],
                    self._message_text(assistant_content)[:4000],
                )

            try:
                client = self._new_client()
                _post_turn(client)
            except Exception as e:
                logger.debug("OpenViking sync_turn failed, reconnecting: %s", e)
                try:
                    client = self._new_client()
                    _post_turn(client)
                except Exception as retry_error:
                    logger.warning("OpenViking sync_turn failed: %s", retry_error)

        # Wait for any previous sync to finish before starting a new one
        if self._sync_thread and self._sync_thread.is_alive():
            self._sync_thread.join(timeout=5.0)

        self._sync_thread = threading.Thread(
            target=_sync, daemon=True, name="openviking-sync"
        )
        self._sync_thread.start()

    def on_session_end(self, messages: List[Dict[str, Any]]) -> None:
        """Commit the session to trigger memory extraction.

        OpenViking automatically extracts 6 categories of memories:
        profile, preferences, entities, events, cases, and patterns.
        """
        if not self._client:
            return

        sid = self._session_id
        # Commit only after session writes drain.
        if not self._drain_writers(sid, timeout=_SESSION_DRAIN_TIMEOUT):
            logger.warning(
                "OpenViking writer for %s still alive after drain — skipping commit",
                sid,
            )
            return

        if self._turn_count == 0 and not self._session_has_pending_tokens(sid):
            return

        if self._commit_session(sid, self._turn_count, context="on session end"):
            # Mark clean so a follow-up on_session_switch skips its own commit.
            self._turn_count = 0

    def on_session_switch(
        self,
        new_session_id: str,
        *,
        parent_session_id: str = "",
        reset: bool = False,
        **kwargs,
    ) -> None:
        """Commit the old session and rotate cached state to the new session_id.

        Fires on /resume, /branch, /reset, /new, and context compression.
        Without this hook, ``_session_id`` stays stuck at the value
        ``initialize()`` cached, so subsequent ``sync_turn()`` writes land in
        the already-closed old session and ``on_session_end()`` tries to
        commit it a second time. The new session never accumulates messages,
        and memory extraction never fires for it. See hermes-agent#28296.

        Flushes any in-flight sync under the old session_id, commits the old
        session if it has pending turns (same extraction semantics as
        ``on_session_end``), drains and clears any stale prefetch result,
        then rotates ``_session_id`` and resets ``_turn_count``.
        """
        new_id = str(new_session_id or "").strip()
        if not new_id or not self._client:
            return

        old_session_id = self._session_id
        old_turn_count = self._turn_count

        # Commit only after session writes drain.
        writers_drained = True
        if old_session_id:
            writers_drained = self._drain_writers(old_session_id, timeout=_SESSION_DRAIN_TIMEOUT)
            if not writers_drained:
                logger.warning(
                    "OpenViking writer for %s still alive after drain — "
                    "skipping commit-on-switch",
                    old_session_id,
                )

        if writers_drained and old_session_id and old_turn_count > 0:
            self._commit_session(old_session_id, old_turn_count, context="on switch")
        elif not writers_drained:
            self._schedule_deferred_commit(old_session_id, old_turn_count)

        # Drop prefetch results from older switch generations.
        self._prefetch_generation += 1
        if self._prefetch_thread and self._prefetch_thread.is_alive():
            self._prefetch_thread.join(timeout=3.0)
        with self._prefetch_lock:
            self._prefetch_result = ""

        self._session_id = new_id
        self._turn_count = 0
        logger.debug(
            "OpenViking on_session_switch: old=%s new=%s parent=%s reset=%s",
            old_session_id, new_id, parent_session_id, reset,
        )

    def _build_memory_uri(self, subdir: str) -> str:
        """Build a viking:// memory URI under the configured user/agent/subdir."""
        slug = uuid.uuid4().hex[:12]
        return f"viking://user/{self._user}/agent/{self._agent}/memories/{subdir}/mem_{slug}.md"

    def on_memory_write(
        self,
        action: str,
        target: str,
        content: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Mirror built-in memory writes to OpenViking via content/write."""
        if not self._client or action != "add" or not content:
            return

        subdir = _MEMORY_WRITE_TARGET_SUBDIR_MAP.get(target, _DEFAULT_MEMORY_SUBDIR)
        uri = self._build_memory_uri(subdir)

        def _write():
            try:
                client = _VikingClient(
                    self._endpoint, self._api_key,
                    account=self._account, user=self._user, agent=self._agent,
                )
                client.post("/api/v1/content/write", {
                    "uri": uri,
                    "content": content,
                    "mode": "create",
                })
            except Exception as e:
                logger.debug("OpenViking memory mirror failed: %s", e)

        t = threading.Thread(target=_write, daemon=True, name="openviking-memwrite")
        t.start()

    def get_tool_schemas(self) -> List[Dict[str, Any]]:
        return [SEARCH_SCHEMA, READ_SCHEMA, BROWSE_SCHEMA, REMEMBER_SCHEMA, ADD_RESOURCE_SCHEMA]

    def handle_tool_call(self, tool_name: str, args: dict, **kwargs) -> str:
        if not self._client:
            return tool_error("OpenViking server not connected")

        try:
            if tool_name == "viking_search":
                return self._tool_search(args)
            elif tool_name == "viking_read":
                return self._tool_read(args)
            elif tool_name == "viking_browse":
                return self._tool_browse(args)
            elif tool_name == "viking_remember":
                return self._tool_remember(args)
            elif tool_name == "viking_add_resource":
                return self._tool_add_resource(args)
            return tool_error(f"Unknown tool: {tool_name}")
        except Exception as e:
            return tool_error(str(e))

    def shutdown(self) -> None:
        # Wait for every in-flight writer across all tracked sessions.
        with self._inflight_lock:
            all_workers = [
                t for workers in self._inflight_writers.values() for t in workers
            ]
        with self._deferred_commit_lock:
            deferred_workers = list(self._deferred_commit_threads)
        for t in all_workers:
            if t.is_alive():
                t.join(timeout=5.0)
        for t in deferred_workers:
            if t.is_alive():
                t.join(timeout=5.0)
        if self._prefetch_thread and self._prefetch_thread.is_alive():
            self._prefetch_thread.join(timeout=5.0)
        # Clear atexit reference so it doesn't double-commit.
        global _last_active_provider
        if _last_active_provider is self:
            _last_active_provider = None

    # -- Tool implementations ------------------------------------------------

    @staticmethod
    def _unwrap_result(resp: Any) -> Any:
        """Return OpenViking payload body regardless of wrapped/unwrapped shape."""
        if isinstance(resp, dict) and "result" in resp:
            return resp.get("result")
        return resp

    @staticmethod
    def _normalize_summary_uri(uri: str) -> str:
        """Map pseudo summary files to their parent directory URI for L0/L1 reads."""
        if not uri:
            return uri
        for suffix in ("/.abstract.md", "/.overview.md", "/.read.md", "/.full.md"):
            if uri.endswith(suffix):
                return uri[: -len(suffix)] or "viking://"
        return uri

    def _is_directory_uri(self, uri: str) -> bool | None:
        """Probe fs/stat to decide if a URI is a directory.

        Returns True/False when the server answers cleanly, and None when the
        probe itself fails (network error, unexpected shape). Callers should
        treat None as "unknown" and fall back to the exception-based path.
        """
        try:
            resp = self._client.get("/api/v1/fs/stat", params={"uri": uri})
        except Exception:
            return None
        result = self._unwrap_result(resp)
        if isinstance(result, dict):
            if "isDir" in result:
                return bool(result.get("isDir"))
            if "is_dir" in result:
                return bool(result.get("is_dir"))
            if result.get("type") == "dir":
                return True
            if result.get("type") == "file":
                return False
        return None

    def _tool_search(self, args: dict) -> str:
        query = args.get("query", "")
        if not query:
            return tool_error("query is required")

        payload: Dict[str, Any] = {"query": query}
        mode = args.get("mode", "auto")
        if mode != "auto":
            payload["mode"] = mode
        if args.get("scope"):
            payload["target_uri"] = args["scope"]
        if args.get("limit"):
            payload["limit"] = args["limit"]

        resp = self._client.post("/api/v1/search/find", payload)
        result = resp.get("result", {})

        # Format results for the model — keep it concise
        scored_entries = []
        for ctx_type in ("memories", "resources", "skills"):
            items = result.get(ctx_type, [])
            for item in items:
                raw_score = item.get("score")
                sort_score = raw_score if raw_score is not None else 0.0
                entry = {
                    "uri": item.get("uri", ""),
                    "type": ctx_type.rstrip("s"),
                    "score": round(raw_score, 3) if raw_score is not None else 0.0,
                    "abstract": item.get("abstract", ""),
                }
                if item.get("relations"):
                    entry["related"] = [r.get("uri") for r in item["relations"][:3]]
                scored_entries.append((sort_score, entry))

        scored_entries.sort(key=lambda x: x[0], reverse=True)
        formatted = [entry for _, entry in scored_entries]

        return json.dumps({
            "results": formatted,
            "total": result.get("total", len(formatted)),
        }, ensure_ascii=False)

    def _tool_read(self, args: dict) -> str:
        uri = args.get("uri", "")
        if not uri:
            return tool_error("uri is required")

        level = args.get("level", "overview")

        summary_level = level in {"abstract", "overview"}
        # OpenViking expects directory URIs for pseudo summary files
        # (e.g. viking://user/hermes/.overview.md).
        resolved_uri = self._normalize_summary_uri(uri) if summary_level else uri
        used_fallback = False

        # abstract/overview endpoints are directory-only on OpenViking
        # (v0.3.x returns 500/412 for file URIs). When the caller asks for a
        # summary level on a non-pseudo URI, probe fs/stat first and route
        # file URIs straight to /content/read instead of eating a failing
        # round-trip. The pseudo-URI path already points at a directory, so
        # skip the probe there.
        if summary_level and resolved_uri == uri:
            is_dir = self._is_directory_uri(uri)
            if is_dir is False:
                resolved_uri = uri
                used_fallback = True

        # Map our level names to OpenViking GET endpoints.
        endpoint = "/api/v1/content/read"
        if not used_fallback:
            if level == "abstract":
                endpoint = "/api/v1/content/abstract"
            elif level == "overview":
                endpoint = "/api/v1/content/overview"

        try:
            resp = self._client.get(endpoint, params={"uri": resolved_uri})
        except Exception:
            # OpenViking may return HTTP 500 for abstract/overview reads on normal
            # file URIs (mem_*.md). For those, gracefully fallback to full read.
            if not summary_level or resolved_uri != uri or used_fallback:
                raise
            resp = self._client.get("/api/v1/content/read", params={"uri": uri})
            used_fallback = True

        result = self._unwrap_result(resp)
        # Content endpoints may return either plain strings or objects.
        if isinstance(result, str):
            content = result
        elif isinstance(result, dict):
            content = result.get("content", "") or result.get("text", "")
        else:
            content = ""

        # Truncate long content to avoid flooding context.
        max_len = 8000
        if level == "overview":
            max_len = 4000
        elif level == "abstract":
            max_len = 1200

        if len(content) > max_len:
            content = content[:max_len] + "\n\n[... truncated, use a more specific URI or full level]"

        payload = {
            "uri": uri,
            "resolved_uri": resolved_uri,
            "level": level,
            "content": content,
        }
        if used_fallback:
            payload["fallback"] = "content/read"

        return json.dumps(payload, ensure_ascii=False)

    def _tool_browse(self, args: dict) -> str:
        action = args.get("action", "list")
        path = args.get("path", "viking://")

        # Map action to the correct fs endpoint (all GET with uri= param)
        endpoint_map = {"tree": "/api/v1/fs/tree", "list": "/api/v1/fs/ls", "stat": "/api/v1/fs/stat"}
        endpoint = endpoint_map.get(action, "/api/v1/fs/ls")
        resp = self._client.get(endpoint, params={"uri": path})
        result = self._unwrap_result(resp)

        # Format list/tree results for readability
        if action in {"list", "tree"}:
            raw_entries = result
            if isinstance(result, dict):
                raw_entries = result.get("entries") or result.get("items") or result.get("children") or []

            if isinstance(raw_entries, list):
                entries = []
                for e in raw_entries[:50]:  # cap at 50 entries
                    uri = e.get("uri", "")
                    name = e.get("rel_path") or e.get("name") or (uri.rsplit("/", 1)[-1] if uri else "")
                    is_dir = bool(e.get("isDir") or e.get("is_dir") or e.get("type") == "dir")
                    entries.append({
                        "name": name,
                        "uri": uri,
                        "type": "dir" if is_dir else "file",
                        "abstract": e.get("abstract", ""),
                    })
                return json.dumps({"path": path, "entries": entries}, ensure_ascii=False)

        return json.dumps(result, ensure_ascii=False)

    def _tool_remember(self, args: dict) -> str:
        content = args.get("content", "")
        if not content:
            return tool_error("content is required")

        category = args.get("category", "")
        subdir = _CATEGORY_SUBDIR_MAP.get(category, _DEFAULT_MEMORY_SUBDIR)
        uri = self._build_memory_uri(subdir)

        # Write directly via content/write API.
        # This creates the file, stores the content, and queues vector indexing
        # in a single call — no dependency on session commit / VLM extraction.
        try:
            result = self._client.post("/api/v1/content/write", {
                "uri": uri,
                "content": content,
                "mode": "create",
            })
            written = result.get("result", {}).get("written_bytes", 0)
            return json.dumps({
                "status": "stored",
                "message": f"Memory stored ({written}b) and queued for vector indexing.",
            })
        except Exception as e:
            logger.error("OpenViking content/write failed: %s", e)
            return tool_error(f"Failed to store memory: {e}")

    def _tool_add_resource(self, args: dict) -> str:
        url = args.get("url", "")
        if not url:
            return tool_error("url is required")

        if args.get("to") and args.get("parent"):
            return tool_error("Cannot specify both 'to' and 'parent'")

        payload: Dict[str, Any] = {}
        for key in ("reason", "to", "parent", "instruction", "wait", "timeout"):
            if key in args and args[key] not in {None, ""}:
                payload[key] = args[key]

        parsed_url = urlparse(url)
        if _is_remote_resource_source(url):
            source_path = None
        elif parsed_url.scheme == "file":
            source_path = _path_from_file_uri(url)
            if isinstance(source_path, str):
                return tool_error(source_path)
        elif parsed_url.scheme and not _is_windows_absolute_path(url):
            source_path = None
        else:
            source_path = Path(url).expanduser()

        cleanup_path: Optional[Path] = None
        try:
            if source_path is not None:
                if source_path.exists():
                    if source_path.is_dir():
                        payload["source_name"] = source_path.name
                        cleanup_path = _zip_directory(source_path)
                        upload_path = cleanup_path
                    elif source_path.is_file():
                        payload["source_name"] = source_path.name
                        upload_path = source_path
                    else:
                        return tool_error(f"Unsupported local resource path: {url}")
                    payload["temp_file_id"] = self._client.upload_temp_file(upload_path)
                elif _is_local_path_reference(url):
                    return tool_error(f"Local resource path does not exist: {url}")
                else:
                    payload["path"] = url
            else:
                payload["path"] = url

            resp = self._client.post("/api/v1/resources", payload)
            result = resp.get("result", {})
        finally:
            if cleanup_path:
                cleanup_path.unlink(missing_ok=True)

        return json.dumps({
            "status": "added",
            "root_uri": result.get("root_uri", ""),
            "message": "Resource queued for processing. Use viking_search after a moment to find it.",
        }, ensure_ascii=False)


# ---------------------------------------------------------------------------
# Plugin entry point
# ---------------------------------------------------------------------------

def register(ctx) -> None:
    """Register OpenViking as a memory provider plugin."""
    ctx.register_memory_provider(OpenVikingMemoryProvider())

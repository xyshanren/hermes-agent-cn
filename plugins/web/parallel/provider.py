"""Parallel.ai web search + content extraction — plugin form.

Subclasses :class:`agent.web_search_provider.WebSearchProvider`.

Search runs on one of two transports, picked by credential:

- **No key →** the free hosted Search MCP at ``https://search.parallel.ai/mcp``
  (anonymous Streamable-HTTP JSON-RPC). This makes ``web_search`` work out of
  the box with zero setup.
- **``PARALLEL_API_KEY`` →** the ``parallel`` SDK's v1 ``search`` / ``extract``
  REST endpoints (objective-tuned, mode-selectable, higher rate limits).

Extract mirrors search: keyed uses the async SDK (``AsyncParallel``) v1
``extract``; keyless uses the free MCP's ``web_fetch``. :meth:`extract` is
declared ``async def`` and the dispatcher in
:func:`tools.web_tools.web_extract_tool` detects coroutines via
:func:`inspect.iscoroutinefunction` and awaits.

Config keys this provider responds to::

    web:
      search_backend: "parallel"      # explicit per-capability
      extract_backend: "parallel"     # explicit per-capability
      backend: "parallel"             # shared fallback
      # Optional: search mode (default "advanced"; also "basic")
      # via the PARALLEL_SEARCH_MODE env var. REST path only.

Env vars::

    PARALLEL_API_KEY=...             # https://parallel.ai (optional — unlocks
                                     # the v1 REST Search API; without it,
                                     # search and extract use the free MCP)
    PARALLEL_SEARCH_MODE=advanced    # optional: basic|advanced (legacy
                                     # fast/one-shot map to basic, agentic to
                                     # advanced). REST path only.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import uuid
from typing import Any, Dict, List

import httpx

from agent.web_search_provider import WebSearchProvider

logger = logging.getLogger(__name__)

# Free hosted Search MCP — anonymous-friendly, used when no PARALLEL_API_KEY is
# configured. Docs: https://docs.parallel.ai/integrations/mcp/search-mcp
_MCP_SEARCH_URL = "https://search.parallel.ai/mcp"
_MCP_PROTOCOL_VERSION = "2025-06-18"
_MCP_CLIENT_NAME = "hermes-agent"
_MCP_CLIENT_VERSION = "1.0.0"
_MCP_USER_AGENT = f"{_MCP_CLIENT_NAME}/{_MCP_CLIENT_VERSION}"
_MCP_TIMEOUT_SECONDS = 30.0

# Free-tier attribution. The hosted Search MCP is free to use; surfacing this
# on keyless results credits Parallel and matches the free-tier terms.
_FREE_MCP_ATTRIBUTION = (
    "Search powered by the free Parallel Web Search MCP (https://parallel.ai)."
)


def _new_session_id() -> str:
    """Mint a fresh Parallel ``session_id`` for a single tool call."""
    return f"hermes-agent-{uuid.uuid4().hex}"


# Module-level note: the canonical cache slots ``_parallel_client`` and
# ``_async_parallel_client`` live on :mod:`tools.web_tools` so tests that do
# ``tools.web_tools._parallel_client = None`` between cases see fresh state.
# The plugin reads/writes through that public module (see
# :func:`_get_sync_client` / :func:`_get_async_client`).


def _ensure_parallel_sdk_installed() -> None:
    """Trigger lazy install of the parallel SDK if it isn't present.

    Mirrors the lazy-deps pattern used by the legacy implementation.
    Swallows benign ImportError from the lazy_deps helper itself; if the
    SDK is genuinely missing the subsequent ``from parallel import ...``
    raises ImportError that the caller can handle.
    """
    try:
        from tools.lazy_deps import ensure as _lazy_ensure

        _lazy_ensure("search.parallel", prompt=False)
    except ImportError:
        pass
    except Exception as exc:  # noqa: BLE001 — surface install hint as ImportError
        raise ImportError(str(exc))


def _get_sync_client() -> Any:
    """Lazy-load + cache the sync Parallel client.

    Cache lives on :mod:`tools.web_tools` (as ``_parallel_client``) so unit
    tests that reset that name between cases keep working.
    """
    import tools.web_tools as _wt

    cached = getattr(_wt, "_parallel_client", None)
    if cached is not None:
        return cached

    api_key = os.getenv("PARALLEL_API_KEY")
    if not api_key:
        raise ValueError(
            "PARALLEL_API_KEY environment variable not set. "
            "Get your API key at https://parallel.ai"
        )

    _ensure_parallel_sdk_installed()
    from parallel import Parallel  # noqa: WPS433 — deliberately lazy

    client = Parallel(api_key=api_key)
    _wt._parallel_client = client
    return client


def _get_async_client() -> Any:
    """Lazy-load + cache the async Parallel client.

    Cache lives on :mod:`tools.web_tools` (as ``_async_parallel_client``).
    """
    import tools.web_tools as _wt

    cached = getattr(_wt, "_async_parallel_client", None)
    if cached is not None:
        return cached

    api_key = os.getenv("PARALLEL_API_KEY")
    if not api_key:
        raise ValueError(
            "PARALLEL_API_KEY environment variable not set. "
            "Get your API key at https://parallel.ai"
        )

    _ensure_parallel_sdk_installed()
    from parallel import AsyncParallel  # noqa: WPS433 — deliberately lazy

    client = AsyncParallel(api_key=api_key)
    _wt._async_parallel_client = client
    return client


def _reset_clients_for_tests() -> None:
    """Drop both cached clients so tests can re-instantiate cleanly.

    Clears the canonical slots on :mod:`tools.web_tools` (where
    :func:`_get_sync_client` / :func:`_get_async_client` read/write them).
    """
    import tools.web_tools as _wt

    _wt._parallel_client = None
    _wt._async_parallel_client = None


# Backward-compatible aliases for the names that lived in tools.web_tools
# before the migration (matches existing tests + external callers).
_get_parallel_client = _get_sync_client
_get_async_parallel_client = _get_async_client


def _resolve_search_mode() -> str:
    """Return the validated PARALLEL_SEARCH_MODE value (default "advanced").

    REST-only. The free MCP path does not expose a mode parameter.
    """
    mode = os.getenv("PARALLEL_SEARCH_MODE", "advanced").lower().strip()
    if mode not in {"basic", "advanced"}:
        mode = "advanced"
    return mode


# ---------------------------------------------------------------------------
# Keyless free MCP helpers (Streamable-HTTP JSON-RPC)
# ---------------------------------------------------------------------------


def _mcp_headers(
    mcp_session_id: str | None, api_key: str | None,
    protocol_version: str = _MCP_PROTOCOL_VERSION,
) -> Dict[str, str]:
    """Build headers for an MCP request."""
    headers: Dict[str, str] = {
        "Content-Type": "application/json",
        "User-Agent": _MCP_USER_AGENT,
        "MCP-Protocol-Version": protocol_version,
    }
    if mcp_session_id:
        headers["Mcp-Session-Id"] = mcp_session_id
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    return headers


def _mcp_response_envelope(raw: str, request_id: str) -> dict:
    """Parse a single JSON-RPC response and validate its id."""
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"MCP response not valid JSON: {exc}") from exc
    if not isinstance(parsed, dict):
        raise RuntimeError(f"MCP response is not a JSON object: {type(parsed)}")
    if parsed.get("id") not in (request_id, None):
        raise RuntimeError(
            f"MCP response id mismatch: got {parsed.get('id')!r}, "
            f"expected {request_id!r}"
        )
    if parsed.get("error"):
        err = parsed["error"]
        raise RuntimeError(
            f"MCP error (code {err.get('code', '?')}): "
            f"{err.get('message', 'unknown')}"
        )
    return parsed


def _mcp_payload(envelope: dict) -> dict:
    """Extract the tool-call result content from an MCP response envelope.

    Returns the first ``text`` content item's ``text`` field parsed as JSON.
    """
    result = envelope.get("result") or {}
    content = result.get("content") or []
    for item in content:
        if isinstance(item, dict) and item.get("type") == "text":
            raw = item.get("text", "{}")
            if isinstance(raw, str):
                try:
                    return json.loads(raw)
                except json.JSONDecodeError:
                    continue
    raise RuntimeError(
        f"Parallel MCP returned no parseable content: {str(result)[:500]}"
    )


def _mcp_call(
    tool_name: str, arguments: Dict[str, Any], api_key: str | None
) -> Dict[str, Any]:
    """Run the MCP handshake then a single ``tools/call`` and return its payload.

    initialize -> (capture ``Mcp-Session-Id``) -> notifications/initialized ->
    tools/call ``tool_name``. Returns the parsed tool payload dict (see
    :func:`_mcp_payload`). A Bearer token is attached only when *api_key* is set.
    """
    with httpx.Client(timeout=_MCP_TIMEOUT_SECONDS) as client:
        # 1. initialize
        init_id = str(uuid.uuid4())
        init = client.post(
            _MCP_SEARCH_URL,
            headers=_mcp_headers(None, api_key),
            json={
                "jsonrpc": "2.0",
                "id": init_id,
                "method": "initialize",
                "params": {
                    "protocolVersion": _MCP_PROTOCOL_VERSION,
                    "capabilities": {},
                    "clientInfo": {
                        "name": _MCP_CLIENT_NAME,
                        "version": _MCP_CLIENT_VERSION,
                    },
                },
            },
        )
        init.raise_for_status()
        mcp_session_id = init.headers.get("mcp-session-id")
        init_env = _mcp_response_envelope(init.text, init_id)
        negotiated_version = (
            (init_env.get("result") or {}).get("protocolVersion")
            or _MCP_PROTOCOL_VERSION
        )

        # 2. notifications/initialized
        client.post(
            _MCP_SEARCH_URL,
            headers=_mcp_headers(mcp_session_id, api_key, negotiated_version),
            json={"jsonrpc": "2.0", "method": "notifications/initialized"},
        )

        # 3. tools/call
        call_id = str(uuid.uuid4())
        call = client.post(
            _MCP_SEARCH_URL,
            headers=_mcp_headers(mcp_session_id, api_key, negotiated_version),
            json={
                "jsonrpc": "2.0",
                "id": call_id,
                "method": "tools/call",
                "params": {"name": tool_name, "arguments": arguments},
            },
        )
        call.raise_for_status()
        return _mcp_payload(_mcp_response_envelope(call.text, call_id))


def _mcp_web_search(query: str, limit: int, api_key: str | None) -> Dict[str, Any]:
    """Run a ``web_search`` tool call against the hosted Search MCP.

    Returns the standard provider search shape
    (``{"success": True, "data": {"web": [...]}}``).
    """
    payload = _mcp_call(
        "web_search",
        {
            "objective": query,
            "search_queries": [query],
            "session_id": _new_session_id(),
        },
        api_key,
    )

    web_results: List[Dict[str, Any]] = []
    for i, result in enumerate((payload.get("results") or [])[: max(limit, 1)]):
        if not isinstance(result, dict):
            continue
        excerpts = result.get("excerpts") or []
        web_results.append(
            {
                "url": result.get("url") or "",
                "title": result.get("title") or "",
                "description": " ".join(excerpts) if excerpts else "",
                "position": i + 1,
            }
        )

    return {
        "success": True,
        "data": {"web": web_results},
        "provider": "parallel",
        "attribution": _FREE_MCP_ATTRIBUTION,
    }


def _mcp_web_fetch(urls: List[str], api_key: str | None) -> List[Dict[str, Any]]:
    """Run a ``web_fetch`` tool call against the hosted Search MCP.

    Returns the per-URL extract shape that
    :func:`tools.web_tools.web_extract_tool` expects.
    """
    payload = _mcp_call(
        "web_fetch",
        {"urls": list(urls), "full_content": True, "session_id": _new_session_id()},
        api_key,
    )

    by_url: Dict[str, Dict[str, Any]] = {}
    for item in payload.get("results") or []:
        if isinstance(item, dict) and item.get("url"):
            by_url.setdefault(item["url"], item)

    results: List[Dict[str, Any]] = []
    for url in urls:
        item = by_url.get(url)
        if item is None:
            results.append(
                {
                    "url": url,
                    "title": "",
                    "content": "",
                    "error": "extraction failed (no content returned)",
                    "metadata": {"sourceURL": url},
                }
            )
            continue
        title = item.get("title") or ""
        content = item.get("full_content") or "\n\n".join(item.get("excerpts") or [])
        results.append(
            {
                "url": url,
                "title": title,
                "content": content,
                "raw_content": content,
                "metadata": {"sourceURL": url, "title": title},
            }
        )

    return results


class ParallelWebSearchProvider(WebSearchProvider):
    """Parallel.ai search + async extract provider."""

    @property
    def name(self) -> str:
        return "parallel"

    @property
    def display_name(self) -> str:
        return "Parallel"

    def is_available(self) -> bool:
        """Return True when ``PARALLEL_API_KEY`` is set.

        Deliberately key-based: this gates the registry's active-provider walk
        and the ``hermes tools`` picker. The keyless free-MCP path is reached
        independently via :func:`tools.web_tools._get_backend`'s ``parallel``
        terminal default.
        """
        return bool(os.getenv("PARALLEL_API_KEY", "").strip())

    def supports_search(self) -> bool:
        return True

    def supports_extract(self) -> bool:
        return True

    def search(self, query: str, limit: int = 5) -> Dict[str, Any]:
        """Execute a Parallel search (sync).

        With ``PARALLEL_API_KEY`` set, uses the v1 ``search`` REST endpoint with
        the configured mode (``PARALLEL_SEARCH_MODE`` env var, default
        "advanced"). Without a key, falls back to the free hosted Search MCP so
        search still works with zero setup.
        """
        try:
            from tools.interrupt import is_interrupted

            if is_interrupted():
                return {"success": False, "error": "Interrupted"}

            api_key = os.getenv("PARALLEL_API_KEY", "").strip()
            if not api_key:
                logger.info(
                    "Parallel search (free MCP): '%s' (limit=%d)", query, limit
                )
                return _mcp_web_search(query, limit, api_key=None)

            mode = _resolve_search_mode()
            logger.info(
                "Parallel search (v1 REST): '%s' (mode=%s, limit=%d)",
                query, mode, limit,
            )
            response = _get_sync_client().search(
                search_queries=[query],
                objective=query,
                mode=mode,
                session_id=_new_session_id(),
                advanced_settings={"max_results": min(max(limit, 1), 20)},
            )

            web_results = []
            for i, result in enumerate((response.results or [])[: max(limit, 1)]):
                excerpts = result.excerpts or []
                web_results.append(
                    {
                        "url": result.url or "",
                        "title": result.title or "",
                        "description": " ".join(excerpts) if excerpts else "",
                        "position": i + 1,
                    }
                )

            return {"success": True, "data": {"web": web_results}}
        except ValueError as exc:
            return {"success": False, "error": str(exc)}
        except ImportError as exc:
            return {
                "success": False,
                "error": f"Parallel SDK not installed: {exc}",
            }
        except Exception as exc:  # noqa: BLE001
            logger.warning("Parallel search error: %s", exc)
            return {"success": False, "error": f"Parallel search failed: {exc}"}

    async def extract(
        self, urls: List[str], **kwargs: Any
    ) -> List[Dict[str, Any]]:
        """Extract content from one or more URLs.

        With ``PARALLEL_API_KEY`` set, uses the async SDK's v1 ``extract`` for
        full page content. Without a key, falls back to the free hosted Search
        MCP's ``web_fetch`` tool so extraction works with zero setup.

        Returns the legacy list-of-results shape that
        :func:`tools.web_tools.web_extract_tool` expects: one entry per
        successful URL plus one entry per failed URL with an ``error``
        field. Errors are not raised — they're returned as per-URL items.
        """
        try:
            from tools.interrupt import is_interrupted

            if is_interrupted():
                return [
                    {"url": u, "error": "Interrupted", "title": ""} for u in urls
                ]

            api_key = os.getenv("PARALLEL_API_KEY", "").strip()
            if not api_key:
                logger.info(
                    "Parallel extract (free MCP web_fetch): %d URL(s)", len(urls)
                )
                return await asyncio.to_thread(_mcp_web_fetch, list(urls), None)

            logger.info("Parallel extract (v1 REST): %d URL(s)", len(urls))
            response = await _get_async_client().extract(
                urls=urls,
                advanced_settings={"full_content": True},
                session_id=_new_session_id(),
            )

            results: List[Dict[str, Any]] = []
            for result in response.results or []:
                content = result.full_content or ""
                if not content:
                    content = "\n\n".join(result.excerpts or [])
                url = result.url or ""
                title = result.title or ""
                results.append(
                    {
                        "url": url,
                        "title": title,
                        "content": content,
                        "raw_content": content,
                        "metadata": {"sourceURL": url, "title": title},
                    }
                )

            for error in response.errors or []:
                err_url = getattr(error, "url", "") or ""
                err_msg = (
                    getattr(error, "message", None)
                    or getattr(error, "content", None)
                    or getattr(error, "error_type", None)
                    or "extraction failed"
                )
                results.append(
                    {
                        "url": err_url,
                        "title": "",
                        "content": "",
                        "error": err_msg,
                        "metadata": {"sourceURL": err_url},
                    }
                )

            return results
        except ValueError as exc:
            return [{"url": u, "title": "", "content": "", "error": str(exc)} for u in urls]
        except ImportError as exc:
            return [
                {"url": u, "title": "", "content": "", "error": f"Parallel SDK not installed: {exc}"}
                for u in urls
            ]
        except Exception as exc:  # noqa: BLE001
            logger.warning("Parallel extract error: %s", exc)
            return [
                {"url": u, "title": "", "content": "", "error": f"Parallel extract failed: {exc}"}
                for u in urls
            ]

    def get_setup_schema(self) -> Dict[str, Any]:
        return {
            "name": "Parallel",
            "badge": "free",
            "tag": (
                "Free web search + extraction via Parallel's hosted Search MCP "
                "— no key needed. Add PARALLEL_API_KEY for the v1 REST Search "
                "API (richer modes, higher limits)."
            ),
            "env_vars": [
                {
                    "key": "PARALLEL_API_KEY",
                    "prompt": "Parallel API key (optional — unlocks the v1 REST Search API)",
                    "url": "https://parallel.ai",
                },
            ],
        }

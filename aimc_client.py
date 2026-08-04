"""AIMC gateway client — profile-based model routing + dynamic adaptation.

CAND-085 (AIMC 网关集成). Embeds 4 iron laws (verbatim, non-negotiable):

  1. ❌ hermes-agent-cn does NOT modify AIMC config (0 PUT/POST/PATCH calls).
  2. ❌ hermes-agent-cn does NOT write back its own profile (0 config.yaml
     writers here).
  3. ✅ AIMC routing decisions listen to AIMC's DB + intelligence layer ONLY.
     hermes-agent-cn does not run side-channel heuristics or local fallback
     that bypasses AIMC's answer.
  4. ✅ Startup is fail-fast. ``AIMCClient.refresh()`` must raise on HTTP
     failure or invalid response. Callers propagate the exception — no
     silent cache, no swallowing.

Endpoints we consume (verified against ``gitee XiaoYRecluse/aimc`` Phase 2.8,
commit 929e5fb+):

  - ``GET /v1/models`` returns the OpenAI-standard ``data`` list plus an
    AIMC-specific ``data_groups`` field. Each group entry has at least
    ``id`` (the group name, e.g. ``tier:balanced``) and ``member_count``.
    This is the ONLY endpoint the client uses.

We do NOT need a separate ``get_actual_model()`` helper because
``POST /v1/chat/completions`` accepts the group name directly and AIMC
responds with the ``X-AIMC-Actual-Model`` header (Phase 2.5).

See ``notes/2026-08-04-phase1-cand085-kickoff.md`` §4.2 for the
8-03 22:10 verified scope (post CAND-084 routing-engine re-check).
"""

from __future__ import annotations

import logging
from typing import Any, Optional

import httpx


logger = logging.getLogger("aimc_client")


class AIMCClient:
    """Thin async client around the AIMC gateway ``/v1/models`` endpoint.

    Cache layout: ``self._groups: set[str]`` for fast membership tests
    (used by ``is_known_group`` and ``validate_known_groups``). The model
    list is intentionally not cached here — it is consumed by the
    OpenAI client wiring, not by hermes-agent-cn's own logic.
    """

    def __init__(
        self,
        base_url: str,
        api_key: str = "",
        timeout: float = 30.0,
        client: Optional[httpx.AsyncClient] = None,
    ) -> None:
        # Iron law 1+2: only the base URL and credentials are stored.
        # No method on this class can reach a write endpoint.
        self._base_url = base_url.rstrip("/")
        self._api_key = api_key
        self._timeout = timeout
        # Allow tests to inject a stub client. When None, build the real one
        # lazily so importing this module never spins up network resources.
        self._client = client
        self._owns_client = client is None
        self._groups: set[str] = set()

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            headers = {"Authorization": f"Bearer {self._api_key}"} if self._api_key else {}
            self._client = httpx.AsyncClient(
                base_url=self._base_url,
                timeout=self._timeout,
                headers=headers,
            )
        return self._client

    async def aclose(self) -> None:
        if self._owns_client and self._client is not None:
            await self._client.aclose()
            self._client = None

    async def refresh(self) -> None:
        """Re-fetch the model + group catalog from AIMC and update cache.

        Iron law 4: on any HTTP / JSON error this method raises. Callers
        (e.g. ``main.py`` startup, the daily cron) must propagate.

        All failure modes funnel into ``RuntimeError`` so callers don't
        need to import ``httpx`` to handle the fail-fast contract.
        """
        client = await self._get_client()
        # Iron law 1: GET only. The call signature has no method kwarg
        # that could be flipped to POST/PUT/PATCH.
        try:
            response = await client.get("/v1/models")
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            raise RuntimeError(
                f"AIMC refresh failed: HTTP {exc.response.status_code} from "
                f"{self._base_url}/v1/models ({exc}). Refusing to start with "
                f"an empty/stale AIMC group cache."
            ) from exc
        except httpx.HTTPError as exc:
            # ConnectError, ReadTimeout, etc. — same fail-fast contract.
            raise RuntimeError(
                f"AIMC refresh failed: transport error contacting "
                f"{self._base_url}/v1/models ({type(exc).__name__}: {exc}). "
                f"Refusing to start with an empty AIMC group cache."
            ) from exc
        payload: dict[str, Any] = response.json()

        # AIMC Phase 2.8 shape: ``data`` (model list) + ``data_groups``
        # (group list). Either may be absent on a pre-Phase-2.8 deployment
        # — treat that as a hard failure rather than silently assuming an
        # empty catalog.
        if "data_groups" not in payload:
            raise RuntimeError(
                f"AIMC /v1/models response missing 'data_groups' field — "
                f"deployment is pre-Phase 2.8; upgrade AIMC or pin the "
                f"gateway version. Got keys: {list(payload.keys())!r}"
            )

        new_groups: set[str] = set()
        for entry in payload.get("data_groups", []):
            if not isinstance(entry, dict):
                continue
            gid = entry.get("id")
            if isinstance(gid, str) and gid:
                new_groups.add(gid)

        # Iron law 4 again: a refresh that produced ZERO known groups is
        # treated as a hard failure. It is almost always better to fail
        # loudly than to silently fall back to "no AIMC groups available"
        # and let the main chat mysteriously fail later.
        if not new_groups:
            raise RuntimeError(
                "AIMC /v1/models returned an empty 'data_groups' list — "
                "AIMC has no groups configured (run seed_model_groups.py "
                "on the AIMC side, or this is a misconfigured deployment)"
            )

        self._groups = new_groups
        logger.info(
            "AIMC refresh: %d groups available: %s",
            len(self._groups),
            sorted(self._groups),
        )

    def is_known_group(self, name: str) -> bool:
        """Membership test against the most recently refreshed cache."""
        return name in self._groups

    def validate_known_groups(self, profile_names: list[str]) -> list[str]:
        """Return the subset of ``profile_names`` that are NOT known groups.

        Empty list means all profile names pass. Non-empty list means the
        caller (typically ``main.py`` startup) should raise with these
        names so the operator fixes their config.yaml.

        Iron law 3: we don't try to "fix" unknown names ourselves. The
        hermes side just reports them; the human operator decides what to
        do (update profile, disable the entry, or fix AIMC seeding).
        """
        return [name for name in profile_names if name not in self._groups]

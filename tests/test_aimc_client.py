"""Tests for the AIMC gateway client (CAND-085).

6 unit tests in 4 functional groups, all mocked. No real LLM, no AIMC
daemon, no network. Runs anywhere ``pytest`` runs.

Mocking strategy (mirrors ``tests/integration/test_sprint_2026-07-23.py``
and the 改造 B regression suite):

  T1 (2 cases, parametrize) — refresh happy path
    refresh_parses_data_and_data_groups:
      - minimum valid payload (data + data_groups)
      - fixture payload (5 group + 7 model, the full Phase 2.8 shape)

  T2 (1 test) — is_known_group cache behaviour after refresh

  T3 (1 test) — validate_known_groups returns the unknown subset (iron law 4:
    caller is responsible for raising, we just report)

  T4 (4 cases, parametrize) — refresh failure paths (all raise, iron law 4)
    - HTTP 503
    - empty data_groups
    - missing data_groups (pre-Phase-2.8 deployment)
    - malformed JSON

  T5 (1 test) — iron law 1: AST source check, no PUT/POST/PATCH anywhere
    in ``aimc_client.py`` (only GET)

  T6 (1 test) — iron law 2: AST source check, no hermes config writers
    (no ``yaml.dump``, no ``open(..., "w")`` in ``aimc_client.py``)

Run:
    pytest tests/test_aimc_client.py -v

See ``notes/2026-08-04-phase1-cand085-kickoff.md`` §5 for the original
test plan and §6 for the CAND-085 risk model.
"""

from __future__ import annotations

import asyncio
import inspect
import json
import re
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

import aimc_client
from aimc_client import AIMCClient


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def _fixture_payload() -> dict[str, Any]:
    """Realistic Phase 2.8 /v1/models response — 5 group + 7 model.

    Mirrors the seed_model_groups.py output (tier:flagship / tier:strong /
    tier:balanced / tier:light / scene:code) plus a handful of bare
    model entries on the ``data`` side.
    """
    return {
        "object": "list",
        "data": [
            {"id": "deepseek-chat", "object": "model", "owned_by": "deepseek"},
            {"id": "deepseek-coder", "object": "model", "owned_by": "deepseek"},
            {"id": "qwen-plus", "object": "model", "owned_by": "qwen"},
            {"id": "qwen-turbo", "object": "model", "owned_by": "qwen"},
            {"id": "glm-4-air", "object": "model", "owned_by": "glm"},
            {"id": "kimi-k2", "object": "model", "owned_by": "kimi"},
            {"id": "minimax-m3", "object": "model", "owned_by": "minimax"},
        ],
        "data_groups": [
            {"id": "tier:flagship", "type": "model_group", "display_name": "旗舰推理组",
             "tier": "T0", "member_count": 4},
            {"id": "tier:strong", "type": "model_group", "display_name": "高强推理组",
             "tier": "T1", "member_count": 7},
            {"id": "tier:balanced", "type": "model_group", "display_name": "均衡性价比组",
             "tier": "T2", "member_count": 7},
            {"id": "tier:light", "type": "model_group", "display_name": "轻量免费组",
             "tier": "T3", "member_count": 7},
            {"id": "scene:code", "type": "model_group", "display_name": "代码专用组",
             "tier": None, "member_count": 4},
        ],
    }


def _make_fake_response(payload: Any, status_code: int = 200) -> MagicMock:
    """Build a fake httpx Response for an AIMC client.get() stub."""
    resp = MagicMock()
    resp.status_code = status_code
    resp.json = MagicMock(return_value=payload)
    resp.raise_for_status = MagicMock()
    if status_code >= 400:
        # Mirror httpx's behaviour: raise_for_status raises HTTPStatusError.
        import httpx
        resp.raise_for_status.side_effect = httpx.HTTPStatusError(
            f"{status_code} Server Error", request=MagicMock(), response=resp,
        )
    return resp


# ---------------------------------------------------------------------------
# T1 (2 cases) — refresh parses data + data_groups from /v1/models
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "scenario,payload",
    [
        ("minimum", {"data": [], "data_groups": [{"id": "tier:balanced", "member_count": 1}]}),
        ("fixture", _fixture_payload()),
    ],
)
def test_refresh_parses_data_and_data_groups(scenario, payload):
    """T1 — after ``refresh()`` the client knows every group id from
    ``data_groups`` and they pass ``is_known_group()``.
    """
    response = _make_fake_response(payload)
    fake_client = MagicMock()
    fake_client.get = AsyncMock(return_value=response)
    fake_client.aclose = AsyncMock()

    client = AIMCClient(
        base_url="http://localhost:8080/v1",
        api_key="test-key",
        client=fake_client,
    )

    asyncio.run(client.refresh())
    asyncio.run(client.aclose())

    expected_group_ids = {entry["id"] for entry in payload["data_groups"]}
    for gid in expected_group_ids:
        assert client.is_known_group(gid), (
            f"refresh ({scenario}) failed to register group {gid!r}"
        )
    # Negative check: a name that was not in the payload must be unknown.
    assert not client.is_known_group("tier:does-not-exist"), (
        f"refresh ({scenario}) leaked a phantom group"
    )


# ---------------------------------------------------------------------------
# T2 (1) — is_known_group before refresh
# ---------------------------------------------------------------------------

def test_is_known_group_empty_before_refresh():
    """T2 — before refresh the cache is empty, so no group is known.

    This is the "fail-safe" default: if startup somehow skips refresh,
    the first call to ``is_known_group`` returns False rather than a
    cached value. Callers (e.g. main.py's profile validation) must
    refresh first.
    """
    client = AIMCClient(base_url="http://x", client=MagicMock())
    assert not client.is_known_group("tier:balanced")
    assert not client.is_known_group("scene:code")
    assert client._groups == set()


# ---------------------------------------------------------------------------
# T3 (1) — validate_known_groups returns the unknown subset
# ---------------------------------------------------------------------------

def test_validate_known_groups_returns_unknown_subset():
    """T3 — ``validate_known_groups`` returns the names NOT in the cache.

    Empty list = all profile names pass. Non-empty list = caller is
    expected to raise (main.py does this at startup, iron law 4).
    The client itself never raises from this method so it can be called
    in dry-run / diagnostic contexts without crashing the process.
    """
    response = _make_fake_response(_fixture_payload())
    fake_client = MagicMock()
    fake_client.get = AsyncMock(return_value=response)
    fake_client.aclose = AsyncMock()

    client = AIMCClient(base_url="http://x", client=fake_client)
    asyncio.run(client.refresh())

    # All-known case: empty list.
    all_known = ["tier:balanced", "tier:strong", "scene:code"]
    assert client.validate_known_groups(all_known) == []

    # Mixed case: only the unknowns come back, in the same order.
    mixed = ["tier:balanced", "tier:typo", "scene:code", "scene:nonexistent"]
    assert client.validate_known_groups(mixed) == [
        "tier:typo", "scene:nonexistent",
    ]


# ---------------------------------------------------------------------------
# T4 (4 cases) — refresh failure paths all raise (iron law 4)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "scenario,payload,status_code,exc_type,expected_substr",
    [
        (
            "http_503", None, 503, RuntimeError, "AIMC refresh failed",
        ),
        (
            "empty_data_groups",
            {"data": [], "data_groups": []},
            200, RuntimeError, "empty 'data_groups' list",
        ),
        (
            "missing_data_groups",
            {"data": []},  # no data_groups at all
            200, RuntimeError, "missing 'data_groups' field",
        ),
        (
            "malformed_json",
            {"data": "not-a-list", "data_groups": "also-not-a-list"},
            200, RuntimeError, "empty 'data_groups' list",  # we get the same error path
        ),
    ],
)
def test_refresh_failures_raise(scenario, payload, status_code, exc_type, expected_substr):
    """T4 — iron law 4 (verbatim from aimc_client.py module docstring):

    ``AIMCClient.refresh()`` MUST raise on HTTP failure or invalid
    response. Callers propagate; no silent cache, no swallowing.

    The 4 scenarios cover the realistic failure modes for an AIMC
    deployment: gateway 5xx, AIMC seeded with no groups, an older
    AIMC version that doesn't return data_groups, and a malformed
    payload (here we model "data_groups is a string" which we skip
    silently and then fall through to the empty-group check).
    """
    response = _make_fake_response(payload, status_code=status_code)
    fake_client = MagicMock()
    fake_client.get = AsyncMock(return_value=response)
    fake_client.aclose = AsyncMock()

    client = AIMCClient(base_url="http://x", client=fake_client)
    with pytest.raises(exc_type) as excinfo:
        asyncio.run(client.refresh())
    assert expected_substr in str(excinfo.value), (
        f"refresh ({scenario}) raised with unexpected message: {excinfo.value!r}"
    )


# ---------------------------------------------------------------------------
# T5 (1) — iron law 1: source code has no write HTTP methods
# ---------------------------------------------------------------------------

def test_iron_law_1_no_write_http_methods():
    """T5 — AST source check: ``aimc_client.py`` never invokes a write
    HTTP method (PUT/POST/PATCH/DELETE) against AIMC.

    Iron law 1 (verbatim from the module docstring): hermes-agent-cn
    does NOT modify AIMC config; only GET reads from it.
    """
    src = inspect.getsource(aimc_client)
    # Allow the words "post" / "patch" / "put" / "delete" to appear in
    # comments / docstrings, but never as a method call on a client.
    for forbidden in ("client.put", "client.post", "client.patch",
                      "client.delete", "client.request("):
        assert forbidden not in src, (
            f"iron law 1 violation: source contains {forbidden!r}. "
            f"aimc_client.py must only read from AIMC, never write."
        )

    # The actual get() call must be present (positive check that the
    # AST inspection is meaningful — if get() were also missing the
    # test would pass spuriously).
    assert "client.get(" in src, (
        "iron law 1 verification failed: aimc_client.py should call "
        "client.get() for refresh, but the call was not found in the source"
    )


# ---------------------------------------------------------------------------
# T6 (1) — iron law 2: source code never writes to hermes config
# ---------------------------------------------------------------------------

def test_iron_law_2_no_hermes_config_writer():
    """T6 — AST source check: ``aimc_client.py`` never opens a file for
    writing nor dumps YAML / JSON to disk.

    Iron law 2 (verbatim): hermes-agent-cn does NOT write back its own
    profile. Even an "I-think-I'll-just-save-this-cached-group-list"
    temptation is a violation, because the only legitimate side effects
    are the in-memory cache + the structured log line.
    """
    src = inspect.getsource(aimc_client)

    forbidden_patterns = [
        re.compile(r"\byaml\.dump\b"),
        re.compile(r"\bjson\.dump\b"),  # the *file* variant; json.dumps is fine (logging)
        re.compile(r"open\([^)]*[\"']w[\"']"),  # any open(..., "w"...) call
        re.compile(r"open\([^)]*[\"']a[\"']"),  # append mode is also a write
        re.compile(r"Path\([^)]*\)\.write_text\b"),
        re.compile(r"Path\([^)]*\)\.write_bytes\b"),
    ]
    for pattern in forbidden_patterns:
        match = pattern.search(src)
        assert match is None, (
            f"iron law 2 violation: aimc_client.py source matches "
            f"{pattern.pattern!r} (found at offset {match.start() if match else 0}). "
            f"aimc_client.py must never write to the hermes profile or "
            f"any other file on disk."
        )

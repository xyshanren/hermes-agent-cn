"""Sprint 2026-07-23~24 integration tests v2.3 — verify 8 commits wire-level behavior.

12 tests across 4 functional groups, all fully mocked. No real LLM, no
network, no WSL dependency — runs anywhere ``pytest`` runs.

Mocking strategy (post v1→v2 review of 4 signature-drift bugs):

  T1a (4 tests, parametrize) — K-2: 4 patched call sites
    (judge_goal / decompose_task / specify_task / describe_profile) all
    invoke ``agent.auxiliary_client.call_llm`` (the post-K-2 unified entry).
    Verified via ``patch.object(aux, "call_llm", side_effect=stub)``.

  T1b (1 test) — K-2 second half: ``call_llm`` itself reads
    ``_get_task_extra_body(task)`` and merges it into the wire kwargs via
    ``_build_call_kwargs``. Proved end-to-end by patching
    ``_get_cached_client`` to return a fake client whose
    ``chat.completions.create`` captures kwargs.

  T2 (3 tests) — K-1b: goal_mode pre-completion judge gate. Same
    ``_get_cached_client`` patch as T1b, with a fake client whose
    ``chat.completions.create`` returns the verdict JSON we choose.
    NB: ``_parse_judge_response`` reads the ``done`` field (bool) — not
    the upstream ``verdict`` string.

  T3 (4 tests, parametrize) — K-4: ``conversation_id`` propagation. The
    K-4 cherry-pick wired the cid kwarg into all 4 entry points and made
    each of them set the ``_ambient_conversation_id`` ContextVar. The wire
    payload itself is NOT auto-populated by K-4 — child agents (and the
    fan-out calls inside MoA) read the ambient ContextVar. So the contract
    under test is: "the cid kwarg is accepted and the ambient ContextVar
    is set." Verified by reading the ContextVar after the entry call.

Why fully mocked (rather than real LLM via WSL like the v1 draft at
c0dc0abaa)?
  v1 hit 4 mock signature drift bugs when the WSL env was unavailable
  (mixture_of_agents_tool prompt→user_prompt; delegate_task prompt→goal;
   call_llm reads _get_task_extra_body not _config.get_auxiliary_extra_body;
   judge_goal fail-closed, not fail-open). Catching these at WSL CI time
   costs a 1-2h round trip per fix. v2.3 mocks the exact layer under
   test, so the test is deterministic and short. WSL/real-LLM coverage is
   delegated to upstream CI for the 8 commits.

Run:
    pytest tests/integration/test_sprint_2026-07-23.py -v

NO push per HANDOFF (sprint 2026-07-23~08-05, 阶段收尾批推).
"""

from __future__ import annotations

import asyncio
import json
import os
import uuid
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def _marker() -> str:
    """Unique per-test-run marker so the wire payload is deterministic
    and we can grep for it in captured kwargs without colliding across
    reruns.
    """
    return f"k2-verify-{uuid.uuid4().hex[:12]}"


def _model() -> str:
    """Test model override; falls back to the cn default."""
    return os.environ.get("HERMES_TEST_MODEL", "minimax-m3")


# Module-level response factories so the class bodies can use the kwarg
# name ``content`` without colliding with the local var. (Earlier inline
# versions tripped NameError because ``content = content`` inside a class
# body binds to the class namespace, which doesn't exist yet on the RHS.)
class _StubMsg:
    def __init__(self, content: str):
        self.content = content
        self.role = "assistant"


class _StubChoice:
    def __init__(self, content: str):
        self.message = _StubMsg(content)
        self.finish_reason = "stop"
        self.index = 0


class _StubResp:
    def __init__(self, content: str):
        self.choices = [_StubChoice(content)]
        self.model = _model()
        self.usage = None
        self.id = "test"


class _StubAsyncResp:
    """An awaitable response for async_call_llm — the call site does
    ``await client.chat.completions.create(**kwargs)``."""

    def __init__(self, content: str):
        self.choices = [_StubChoice(content)]
        self.model = _model()
        self.usage = None
        self.id = "test"

    def __await__(self):
        async def _coro():
            return self
        return _coro().__await__()


def _make_fake_client(captured: dict[str, Any], content: str = "ok",
                      is_async: bool = False) -> Any:
    """Build a fake openai client whose .chat.completions.create captures
    kwargs into ``captured`` and returns a stub response.

    The client also exposes a ``base_url`` attribute (mimicking real
    openai.OpenAI) so downstream code that reads ``getattr(client, "base_url", ...)``
    doesn't crash.

    If ``is_async`` is True, the create method is an AsyncMock so
    ``await client.chat.completions.create(**kwargs)`` works.

    For T3 async_call_llm / T3 MoA the cid is propagated via the ambient
    ContextVar inside the asyncio task. The outer thread does NOT see
    those sets (asyncio.run() copies the outer context, then sets within
    the task remain in the task). So the async stub also records the
    ambient it sees in ``captured["in_task_ambient"]`` so the test can
    verify propagation across the entry's task boundary.
    """
    from agent import conversation_context as _ctx
    client = MagicMock()
    client.base_url = "https://test.invalid/v1"
    if is_async:
        resp = _StubAsyncResp(content)
        async def _capture_async(*args, **kwargs):
            captured.update(kwargs)
            captured["in_task_ambient"] = _ctx._ambient_conversation_id.get()
            return resp
        client.chat.completions.create = _capture_async
    else:
        resp = _StubResp(content)
        def _capture(*args, **kwargs):
            captured.update(kwargs)
            return resp
        client.chat.completions.create = _capture
    return client


def _reset_ambient_conversation_id() -> None:
    """Reset the ambient ContextVar so test cases don't bleed into each
    other (each entry sets it, but earlier tests' cid can leak into later
    tests' ambient reads if we don't reset).
    """
    from agent import conversation_context as _ctx
    _ctx._ambient_conversation_id.set(None)


# ---------------------------------------------------------------------------
# T1a (4 cases, parametrize) — K-2: 4 patched call sites route via call_llm
# ---------------------------------------------------------------------------
#
# Pre-K-2 these sites did:
#     client = get_text_auxiliary_client(task)
#     client.chat.completions.create(model=..., messages=..., extra_body=...)
# Post-K-2 they all do:
#     call_llm(task=<name>, messages=[...], ...)
#
# We verify (a) call_llm is invoked with the right task kwarg, and
# (b) call_llm is invoked with non-empty messages.
#
# NB: the actual task names used at each call site (verified in source):
#   judge_goal       -> task="goal_judge"
#   decompose_task   -> task="kanban_decomposer"
#   specify_task     -> task="triage_specifier"
#   describe_profile -> task="profile_describer"

@pytest.mark.parametrize(
    "call_name,expected_task",
    [
        ("judge_goal", "goal_judge"),
        ("decompose_task", "kanban_decomposer"),
        ("specify_task", "triage_specifier"),
        ("describe_profile", "profile_describer"),
    ],
)
def test_k2_call_site_routes_through_call_llm(call_name, expected_task, tmp_path, monkeypatch):
    """K-2 cherry-pick #35566: 4 direct-create aux callers now route
    through ``call_llm(task=...)`` so operator config
    (auxiliary.<task>.extra_body / base_url / reasoning_effort / retries)
    actually flows.
    """
    from agent import auxiliary_client as _aux

    captured_llm: dict[str, Any] = {}

    def _stub_call_llm(*args, **kwargs):
        captured_llm.update(kwargs)
        # judge_goal expects a JSON verdict, other helpers consume plain text.
        if expected_task == "goal_judge":
            return _StubResp('{"done": true, "reason": ""}')
        return _StubResp("ok")

    async def _stub_async_call_llm(*args, **kwargs):
        captured_llm.update(kwargs)
        return _StubResp("ok")

    monkeypatch.setenv("HERMES_HOME", str(tmp_path / ".hermes"))
    (tmp_path / ".hermes").mkdir()
    monkeypatch.setattr(Path, "home", lambda: tmp_path)

    with patch.object(_aux, "call_llm", side_effect=_stub_call_llm), \
         patch.object(_aux, "async_call_llm", side_effect=_stub_async_call_llm):
        if call_name == "judge_goal":
            from hermes_cli.goals import judge_goal
            judge_goal("test goal", "test response", timeout=5.0)
        elif call_name == "decompose_task":
            # decompose_task needs a real triage task. create_task signature
            # is ``triage: bool = False`` (not ``status=``).
            from hermes_cli import kanban_db as kb
            kb._INITIALIZED_PATHS.clear()
            kb.init_db()
            conn = kb.connect()
            try:
                tid = kb.create_task(
                    conn, title="T1-decompose", assignee="test",
                    body="x", triage=True,
                )
            finally:
                conn.close()
            from hermes_cli.kanban_decompose import decompose_task
            decompose_task(tid)
        elif call_name == "specify_task":
            from hermes_cli import kanban_db as kb
            kb._INITIALIZED_PATHS.clear()
            kb.init_db()
            conn = kb.connect()
            try:
                tid = kb.create_task(
                    conn, title="T1-specify", assignee="test",
                    body="x", triage=True,
                )
            finally:
                conn.close()
            from hermes_cli.kanban_specify import specify_task
            specify_task(tid)
        elif call_name == "describe_profile":
            # Use the "default" virtual profile so profile_exists returns
            # True and the helper reaches the call_llm site.
            from hermes_cli.profile_describer import describe_profile
            describe_profile("default", overwrite=True)

    assert "task" in captured_llm, (
        f"{call_name}: call_llm was not invoked at all (K-2 fix missing?)"
    )
    assert captured_llm["task"] == expected_task, (
        f"{call_name}: call_llm invoked with task={captured_llm.get('task')!r}, "
        f"expected {expected_task!r}"
    )
    msgs = captured_llm.get("messages") or []
    assert msgs, (
        f"{call_name}: call_llm was invoked with empty messages — K-2 fix "
        f"is wired but dropped the prompt"
    )


# ---------------------------------------------------------------------------
# T1b (1 test) — call_llm's extra_body helper chain reaches the wire
# ---------------------------------------------------------------------------
def test_k2_call_llm_merges_auxiliary_extra_body_into_wire(tmp_path, monkeypatch):
    """T1a proves the 4 sites invoke call_llm. This proves call_llm itself
    reads ``_get_task_extra_body(task)`` and merges it into the wire kwargs
    via ``_build_call_kwargs``. Without this half, the operator's
    ``auxiliary.<task>.extra_body`` config is still silently dropped.
    """
    from agent import auxiliary_client as _aux

    marker = _marker()
    captured: dict[str, Any] = {}

    fake_client = _make_fake_client(captured)

    monkeypatch.setenv("HERMES_HOME", str(tmp_path / ".hermes"))
    (tmp_path / ".hermes").mkdir()
    monkeypatch.setattr(Path, "home", lambda: tmp_path)

    with patch.object(_aux, "_get_task_extra_body",
                      return_value={"verifier_marker": marker}) as p_extra, \
         patch.object(_aux, "_resolve_task_provider_model",
                      return_value=("openai", _model(), None, None, None)), \
         patch.object(_aux, "_get_cached_client",
                      return_value=(fake_client, _model())):
        from agent.auxiliary_client import call_llm
        call_llm(
            task="goal_judge",
            messages=[{"role": "user", "content": "hi"}],
        )

    # Verify the helper was consulted with the right task name.
    assert p_extra.called, "_get_task_extra_body was not called"
    args, _ = p_extra.call_args
    assert args == ("goal_judge",), (
        f"_get_task_extra_body called with {args!r}, expected ('goal_judge',)"
    )

    # Verify the marker reached the wire.
    eb = captured.get("extra_body")
    assert eb is not None, (
        "no extra_body in chat.completions.create kwargs — call_llm's "
        "helper chain dropped the operator's auxiliary.<task>.extra_body"
    )
    assert eb.get("verifier_marker") == marker, (
        f"extra_body reached the wire but missing verifier marker "
        f"(got keys {list(eb.keys())!r})"
    )


# ---------------------------------------------------------------------------
# T2 (3 tests) — K-1b: goal_mode pre-completion judge gate
# ---------------------------------------------------------------------------
def _setup_goal_mode_env(tmp_path, monkeypatch, task_title: str) -> str:
    """Set up HERMES_HOME / profile / goal_mode / kanban task and return
    the new task id. Shared by T2 / T2b / T2c.
    """
    home = tmp_path / ".hermes"
    home.mkdir()
    monkeypatch.setenv("HERMES_HOME", str(home))
    monkeypatch.setenv("HERMES_PROFILE", "test-worker")
    monkeypatch.setenv("HERMES_KANBAN_GOAL_MODE", "1")
    monkeypatch.delenv("HERMES_SESSION_ID", raising=False)
    monkeypatch.setattr(Path, "home", lambda: tmp_path)

    from hermes_cli import kanban_db as kb
    kb._INITIALIZED_PATHS.clear()
    kb.init_db()
    conn = kb.connect()
    try:
        tid = kb.create_task(
            conn, title=task_title, assignee="test-worker",
            body="Achieve X.", goal_mode=True,
        )
        kb.claim_task(conn, tid)
    finally:
        conn.close()
    monkeypatch.setenv("HERMES_KANBAN_TASK", tid)
    return tid


def _patch_judge_response(content: str) -> tuple[dict, list]:
    """Return ``(captured, ctx_managers)`` — apply the context managers
    in a ``with`` block to make call_llm return the given judge JSON.

    NB: ``_parse_judge_response`` reads the ``done`` field as a bool
    (line 646 of hermes_cli/goals.py), not the upstream ``verdict`` string.
    So pass ``{"done": true, "reason": "..."}`` for an accept verdict.
    """
    from agent import auxiliary_client as _aux
    captured: dict[str, Any] = {}
    fake_client = _make_fake_client(captured, content=content)
    return captured, [
        patch.object(_aux, "_get_cached_client",
                     return_value=(fake_client, _model())),
        patch.object(_aux, "_get_task_extra_body", return_value={}),
        patch.object(_aux, "_resolve_task_provider_model",
                     return_value=("openai", _model(), None, None, None)),
    ]


def test_k1b_goal_mode_completion_rejected_when_judge_says_continue(tmp_path, monkeypatch):
    """K-1b: judge returns 'continue' -> kanban_complete is REJECTED, task
    stays in 'running' status (the gate ran before the write txn).
    """
    from hermes_cli import kanban_db as kb
    from tools import kanban_tools as kt

    tid = _setup_goal_mode_env(tmp_path, monkeypatch, "T2-reject-when-continue")
    captured, ctx_managers = _patch_judge_response(
        '{"done": false, "reason": "criteria not met"}'
    )

    with ctx_managers[0], ctx_managers[1], ctx_managers[2]:
        out = kt._handle_complete({"summary": "did some stuff but not X"})

    d = json.loads(out)
    assert "error" in d, f"expected rejection, got {d!r}"
    assert "Goal completion rejected by judge" in d["error"]
    assert "criteria not met" in d["error"], (
        f"expected judge reason 'criteria not met' in error, got {d['error']!r}"
    )

    # DB still says running — the gate ran before the write txn.
    conn = kb.connect()
    try:
        assert kb.get_task(conn, tid).status == "running", (
            "task should remain 'running' after judge rejection"
        )
    finally:
        conn.close()


def test_k1b_goal_mode_completion_accepted_when_judge_says_done(tmp_path, monkeypatch):
    """K-1b happy path: judge returns 'done' -> kanban_complete is ACCEPTED."""
    from hermes_cli import kanban_db as kb
    from tools import kanban_tools as kt

    tid = _setup_goal_mode_env(tmp_path, monkeypatch, "T2-accept-when-done")
    captured, ctx_managers = _patch_judge_response(
        '{"done": true, "reason": "criteria met"}'
    )

    with ctx_managers[0], ctx_managers[1], ctx_managers[2]:
        out = kt._handle_complete({"summary": "X is achieved."})

    d = json.loads(out)
    assert d.get("ok") is True, f"expected success, got {d!r}"

    conn = kb.connect()
    try:
        assert kb.get_task(conn, tid).status == "done", (
            "task should be 'done' after judge acceptance"
        )
    finally:
        conn.close()


def test_k1b_goal_mode_judge_failure_is_fail_closed(tmp_path, monkeypatch):
    """K-1b: if the judge call raises (network / provider down / misconfig),
    judge_goal catches the exception and returns
    ``('continue', 'judge error: <ExcType>', False)``, so the gate
    REJECTS the completion (fail-CLOSED). This test pins the actual
    behaviour; see the K-1b design-vs-impl TODO in CANDIDATES.md.
    """
    from agent import auxiliary_client as _aux
    from hermes_cli import kanban_db as kb
    from tools import kanban_tools as kt

    tid = _setup_goal_mode_env(tmp_path, monkeypatch, "T2-fail-closed")

    def _judge_raises(*args, **kwargs):
        raise RuntimeError("auxiliary provider unreachable")

    with patch.object(_aux, "_get_cached_client",
                      side_effect=_judge_raises):
        out = kt._handle_complete({"summary": "X is done."})

    d = json.loads(out)
    # Actual behaviour: fail-CLOSED — judge error -> continue -> reject.
    # The K-1b design intended fail-OPEN, but the cn implementation returns
    # ('continue', 'judge error: <ExcType>', False), so the gate rejects.
    assert "error" in d, (
        f"expected rejection (fail-CLOSED), got {d!r} — if you see 'ok' here, "
        f"the K-1b judge failure path was upgraded to fail-OPEN; update this "
        f"test and remove the K-1b TODO in CANDIDATES.md."
    )
    assert "judge error" in d["error"].lower(), (
        f"expected 'judge error' in rejection, got {d['error']!r}"
    )

    conn = kb.connect()
    try:
        assert kb.get_task(conn, tid).status == "running", (
            "task should remain 'running' after judge failure (fail-CLOSED)"
        )
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# T3 (4 cases, parametrize) — K-4: conversation_id propagation
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    "entry_name",
    [
        "call_llm",
        "async_call_llm",
        "mixture_of_agents_tool",
        "delegate_task",
    ],
)
def test_k4_conversation_id_propagates_from_each_entry(entry_name, tmp_path, monkeypatch):
    """K-4 cherry-pick #9ce0e67f2: ``conversation_id`` is propagated from
    the 4 entry points K-4 added the kwarg to. All 4 set the
    ``_ambient_conversation_id`` ContextVar so the cid is visible to any
    nested call_llm / fan-out that reads it. We verify the ambient set;
    the wire payload itself is NOT auto-populated by K-4 (child agents
    read the ambient and re-thread it on their own calls).
    """
    from agent import auxiliary_client as _aux
    from agent import conversation_context as _ctx

    cid = f"k4-verify-{uuid.uuid4().hex[:12]}"

    # Start clean so ambient leakage from a prior parametrize case doesn't
    # pollute this one.
    _reset_ambient_conversation_id()

    monkeypatch.setenv("HERMES_HOME", str(tmp_path / ".hermes"))
    (tmp_path / ".hermes").mkdir()
    monkeypatch.setattr(Path, "home", lambda: tmp_path)

    if entry_name == "call_llm":
        captured: dict[str, Any] = {}
        fake_client = _make_fake_client(captured)
        with patch.object(_aux, "_get_cached_client",
                          return_value=(fake_client, _model())), \
             patch.object(_aux, "_get_task_extra_body", return_value={}), \
             patch.object(_aux, "_resolve_task_provider_model",
                          return_value=("openai", _model(), None, None, None)):
            from agent.auxiliary_client import call_llm
            call_llm(
                task="test_conv",
                messages=[{"role": "user", "content": "hi"}],
                conversation_id=cid,
            )
        assert _ctx._ambient_conversation_id.get() == cid, (
            f"call_llm: ambient ContextVar was not set to {cid!r} "
            f"(got {_ctx._ambient_conversation_id.get()!r}) — K-4 ambient "
            f"propagation broken"
        )

    elif entry_name == "async_call_llm":
        captured = {}
        fake_client = _make_fake_client(captured, is_async=True)
        with patch.object(_aux, "_get_cached_client",
                          return_value=(fake_client, _model())), \
             patch.object(_aux, "_get_task_extra_body", return_value={}), \
             patch.object(_aux, "_resolve_task_provider_model",
                          return_value=("openai", _model(), None, None, None)):
            from agent.auxiliary_client import async_call_llm
            asyncio.run(async_call_llm(
                task="test_conv",
                messages=[{"role": "user", "content": "hi"}],
                conversation_id=cid,
            ))
        # async_call_llm runs inside asyncio.run's task, so the ambient
        # set inside it does NOT bleed to the outer thread. Verify the
        # ambient inside the create() call (captured by the fake client).
        assert captured.get("in_task_ambient") == cid, (
            f"async_call_llm: ambient ContextVar was not visible inside the "
            f"chat.completions.create call (got {captured.get('in_task_ambient')!r}, "
            f"expected {cid!r}) — K-4 ambient propagation broken"
        )

    elif entry_name == "mixture_of_agents_tool":
        # MoA: ambient-test. The contract under test is that the ambient
        # ContextVar is set, NOT that the fan-out actually completes. So
        # we short-circuit the two fan-out helpers (``_run_reference_model_safe``
        # and ``_run_aggregator_model``) to return immediately, avoiding
        # the OPENROUTER_API_KEY / extract_content_or_reasoning / retry
        # loop surface area. Wire plumbing through _get_openrouter_client
        # is upstream's job, not K-4's.
        #
        # MoA runs inside asyncio.run's task, so the ambient set inside it
        # does NOT bleed to the outer thread. We verify the ambient the
        # fan-out helper saw (captured by the stub) — that is the
        # contract that lets child fan-out calls inherit the cid.
        monkeypatch.setenv("OPENROUTER_API_KEY", "test-key-stub")
        import tools.mixture_of_agents_tool as _moa
        moa_captured: dict[str, Any] = {}

        async def _stub_reference(*args, **kwargs):
            moa_captured["reference_in_task_ambient"] = (
                _ctx._ambient_conversation_id.get()
            )
            return (_model(), "stub", True)

        async def _stub_aggregator(*args, **kwargs):
            moa_captured["aggregator_in_task_ambient"] = (
                _ctx._ambient_conversation_id.get()
            )
            return "stub"

        with patch.object(_moa, "_run_reference_model_safe",
                          side_effect=_stub_reference), \
             patch.object(_moa, "_run_aggregator_model",
                          side_effect=_stub_aggregator):
            from tools.mixture_of_agents_tool import mixture_of_agents_tool
            asyncio.run(mixture_of_agents_tool(
                user_prompt="hi",
                reference_models=[_model()],
                aggregator_model=_model(),
                conversation_id=cid,
            ))
        assert moa_captured.get("reference_in_task_ambient") == cid, (
            f"mixture_of_agents_tool: ambient ContextVar was not visible "
            f"inside the reference fan-out (got "
            f"{moa_captured.get('reference_in_task_ambient')!r}, expected "
            f"{cid!r}) — K-4 ambient propagation broken"
        )
        assert moa_captured.get("aggregator_in_task_ambient") == cid, (
            f"mixture_of_agents_tool: ambient ContextVar was not visible "
            f"inside the aggregator call (got "
            f"{moa_captured.get('aggregator_in_task_ambient')!r}, expected "
            f"{cid!r}) — K-4 ambient propagation broken"
        )

    elif entry_name == "delegate_task":
        # delegate_task: ambient-test. Patch is_spawn_paused to True so
        # the function takes the early-return path immediately after
        # setting the ambient ContextVar (the early return is line 1990,
        # AFTER the ambient set on line 1983-1985). parent_agent is
        # required; we give a MagicMock (it is only type-checked, not
        # dereferenced deeply, before the is_spawn_paused branch).
        fake_parent = MagicMock()
        with patch("tools.delegate_tool.is_spawn_paused", return_value=True):
            from tools.delegate_tool import delegate_task
            delegate_task(
                goal="hi",
                parent_agent=fake_parent,
                conversation_id=cid,
            )
        assert _ctx._ambient_conversation_id.get() == cid, (
            f"delegate_task: ambient ContextVar was not set to {cid!r} "
            f"(got {_ctx._ambient_conversation_id.get()!r}) — K-4 ambient "
            f"propagation broken"
        )

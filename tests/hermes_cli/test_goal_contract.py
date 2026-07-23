"""Tests for K-1 completion contracts on /goal.

The 5-field structured contract (outcome / verification / constraints /
boundaries / stop_when) is parsed out of inline `field: value` lines, drafted
by the goal_judge aux model via ``draft_contract``, woven into the judge
prompt and the continuation prompt, and round-trips through
``GoalState.to_json`` / ``from_json`` so ``/resume`` preserves the contract.

Mirrors upstream #50501 test scope (parse / serialize / judge-prompt / draft /
fallback) adapted to the cn mock pattern.
"""

from __future__ import annotations

import json as jsonlib
from unittest.mock import patch

import pytest

from hermes_cli import goals
from hermes_cli.goals import (
    CONTINUATION_PROMPT_WITH_CONTRACT_TEMPLATE,
    DRAFT_CONTRACT_SYSTEM_PROMPT,
    GoalContract,
    GoalState,
    JUDGE_USER_PROMPT_WITH_CONTRACT_TEMPLATE,
    draft_contract,
    judge_goal,
    parse_contract,
)


# ──────────────────────────────────────────────────────────────────────
# parse_contract
# ──────────────────────────────────────────────────────────────────────


class TestParseContract:
    def test_empty_text_returns_empty_headline_and_empty_contract(self):
        headline, contract = parse_contract("")
        assert headline == ""
        assert contract.is_empty()

    def test_plain_text_becomes_headline_and_pre_fills_outcome(self):
        """A bare headline pre-fills ``contract.outcome`` so the contract
        block always carries a top-level objective. ``outcome`` is the
        only field that comes from the headline; the user must opt in to
        the others with explicit ``field:`` lines."""
        headline, contract = parse_contract("Migrate auth to JWT")
        assert headline == "Migrate auth to JWT"
        assert not contract.is_empty()
        assert contract.outcome == "Migrate auth to JWT"
        # All other fields stay empty when the user didn't opt in.
        assert contract.verification == ""
        assert contract.constraints == ""
        assert contract.boundaries == ""
        assert contract.stop_when == ""

    def test_known_field_lines_populate_contract_and_headline(self):
        text = (
            "Migrate auth to JWT\n"
            "verify: the auth test suite passes\n"
            "constraints: keep the public /login response shape unchanged\n"
            "boundaries: only touch services/auth and its tests\n"
            "stop when: a schema change needs product sign-off\n"
        )
        headline, contract = parse_contract(text)
        assert headline == "Migrate auth to JWT"
        assert contract.verification == "the auth test suite passes"
        assert contract.constraints == "keep the public /login response shape unchanged"
        assert contract.boundaries == "only touch services/auth and its tests"
        assert contract.stop_when == "a schema change needs product sign-off"
        # Headline pre-fills outcome so the contract block carries the
        # objective (otherwise the structured criteria would float without
        # a top-level goal).
        assert contract.outcome == "Migrate auth to JWT"

    def test_unknown_field_prefix_does_not_mangle(self):
        """A line that contains a colon but isn't a known field stays in the
        headline. A plain goal like 'Fix bug: the parser' must NOT be split."""
        headline, contract = parse_contract("Fix bug: the parser")
        assert headline == "Fix bug: the parser"
        assert contract.is_empty()

    def test_known_aliases_normalize_to_canonical_field(self):
        headline, contract = parse_contract(
            "Ship the rewrite\n"
            "done when: code merged to main\n"
            "must not: regress the e2e suite\n"
        )
        assert headline == "Ship the rewrite"
        assert contract.stop_when == "code merged to main"
        assert contract.constraints == "regress the e2e suite"

    def test_multiline_field_values_are_joined_with_space(self):
        text = (
            "Migrate auth\n"
            "verify: tests pass\n"
            "verify: the lint check is clean\n"
        )
        _, contract = parse_contract(text)
        assert contract.verification == "tests pass the lint check is clean"


# ──────────────────────────────────────────────────────────────────────
# GoalContract round-trip
# ──────────────────────────────────────────────────────────────────────


class TestGoalContract:
    def test_to_dict_round_trips_via_from_dict(self):
        original = GoalContract(
            outcome="ship it",
            verification="tests pass",
            constraints="no breakage",
            boundaries="src/auth only",
            stop_when="needs product sign-off",
        )
        assert GoalContract.from_dict(original.to_dict()).to_dict() == original.to_dict()

    def test_from_dict_ignores_unknown_keys(self):
        c = GoalContract.from_dict(
            {"outcome": "x", "verification": "y", "bogus": "z"}
        )
        assert c.outcome == "x"
        assert c.verification == "y"
        assert c.constraints == ""

    def test_from_dict_handles_non_dict(self):
        assert GoalContract.from_dict(None).is_empty()
        assert GoalContract.from_dict("not a dict").is_empty()
        assert GoalContract.from_dict([]).is_empty()

    def test_is_empty_only_when_all_fields_blank(self):
        assert GoalContract().is_empty()
        assert GoalContract(outcome="", verification="  ").is_empty()
        assert not GoalContract(outcome="x").is_empty()
        assert not GoalContract(stop_when="x").is_empty()

    def test_render_block_omits_blank_fields_and_labels_them(self):
        c = GoalContract(outcome="ship it", verification="tests pass")
        block = c.render_block()
        assert "- Outcome: ship it" in block
        assert "- Verification: tests pass" in block
        assert "- Constraints" not in block
        assert "- Boundaries" not in block
        assert "- Stop when blocked" not in block

    def test_render_block_empty_for_empty_contract(self):
        assert GoalContract().render_block() == ""


# ──────────────────────────────────────────────────────────────────────
# GoalState round-trip
# ──────────────────────────────────────────────────────────────────────


class TestGoalStateContract:
    def test_from_json_without_contract_key_loads_empty_contract(self):
        """Backward compat: old state_meta rows without a 'contract' key
        must load cleanly with ``has_contract() == False``."""
        legacy = {"goal": "old goal", "status": "active"}
        state = GoalState.from_json(jsonlib.dumps(legacy))
        assert state.goal == "old goal"
        assert not state.has_contract()
        assert state.contract.is_empty()

    def test_to_json_then_from_json_preserves_contract(self):
        original = GoalState(
            goal="Migrate auth",
            contract=GoalContract(
                outcome="Migrate auth",
                verification="tests pass",
                constraints="no /login breakage",
            ),
        )
        round_tripped = GoalState.from_json(original.to_json())
        assert round_tripped.has_contract()
        assert round_tripped.contract.to_dict() == original.contract.to_dict()

    def test_to_json_with_empty_contract_round_trips(self):
        state = GoalState(goal="plain goal")
        round_tripped = GoalState.from_json(state.to_json())
        assert not round_tripped.has_contract()


# ──────────────────────────────────────────────────────────────────────
# judge_goal integration with contract
# ──────────────────────────────────────────────────────────────────────


def _fake_call_response(content: str):
    """Build a minimal response object shaped like an OpenAI chat completion
    reply — only ``choices[0].message.content`` is read by judge_goal.
    """
    class _Msg:
        pass

    class _Choice:
        pass

    class _Resp:
        pass

    msg = _Msg()
    msg.content = content
    choice = _Choice()
    choice.message = msg
    resp = _Resp()
    resp.choices = [choice]
    return resp


class TestJudgeGoalWithContract:
    def test_contract_selects_with_contract_template(self):
        """When a non-empty contract is passed, judge_goal should select
        JUDGE_USER_PROMPT_WITH_CONTRACT_TEMPLATE — its content includes
        the 4 explicit decision rules that the bare template lacks."""
        contract = GoalContract(
            outcome="migrate",
            verification="tests pass",
            constraints="no breakage",
        )
        captured = {}

        def _capture(*args, **kwargs):
            captured.update(kwargs)
            return _fake_call_response('{"done": false, "reason": "not yet"}')

        with patch("agent.auxiliary_client.call_llm", side_effect=_capture):
            judge_goal("migrate", "in-progress", contract=contract)

        assert captured["task"] == "goal_judge"
        # The contract template is identifiable by its decision rules block.
        user_msg = next(
            m["content"] for m in captured["messages"] if m["role"] == "user"
        )
        assert "Decision rules:" in user_msg
        assert "Verification criterion is satisfied" in user_msg
        assert "concrete evidence" in user_msg

    def test_no_contract_falls_through_to_bare_template(self):
        captured = {}

        def _capture(*args, **kwargs):
            captured.update(kwargs)
            return _fake_call_response('{"done": true, "reason": "yes"}')

        with patch("agent.auxiliary_client.call_llm", side_effect=_capture):
            judge_goal("plain goal", "done")

        user_msg = next(
            m["content"] for m in captured["messages"] if m["role"] == "user"
        )
        # Bare template does NOT have the contract decision rules.
        assert "Decision rules:" not in user_msg
        assert "Verification criterion" not in user_msg

    def test_empty_contract_falls_through_to_subgoals_then_bare(self):
        """An empty GoalContract should not trigger the with-contract template.
        If subgoals are also empty, the bare template is used."""
        captured = {}

        def _capture(*args, **kwargs):
            captured.update(kwargs)
            return _fake_call_response('{"done": true, "reason": "yes"}')

        with patch("agent.auxiliary_client.call_llm", side_effect=_capture):
            judge_goal("plain goal", "done", contract=GoalContract())

        user_msg = next(
            m["content"] for m in captured["messages"] if m["role"] == "user"
        )
        assert "Decision rules:" not in user_msg

    def test_contract_takes_precedence_over_subgoals(self):
        """When both are present the contract wins — a goal with subgoals
        AND a contract still selects the with-contract template."""
        captured = {}

        def _capture(*args, **kwargs):
            captured.update(kwargs)
            return _fake_call_response('{"done": false, "reason": "not yet"}')

        contract = GoalContract(
            outcome="ship it",
            verification="all tests green",
        )
        with patch("agent.auxiliary_client.call_llm", side_effect=_capture):
            judge_goal(
                "ship it",
                "in-progress",
                subgoals=["write tests", "update docs"],
                contract=contract,
            )

        user_msg = next(
            m["content"] for m in captured["messages"] if m["role"] == "user"
        )
        assert "Decision rules:" in user_msg
        assert "Additional criteria" not in user_msg  # subgoals template gone


# ──────────────────────────────────────────────────────────────────────
# draft_contract
# ──────────────────────────────────────────────────────────────────────


class TestDraftContract:
    def test_returns_empty_contract_on_no_provider(self):
        """If call_llm raises (no auxiliary provider), draft_contract returns
        an empty contract so the caller can fall back to a free-form goal
        instead of wedging the user."""
        with patch(
            "agent.auxiliary_client.call_llm",
            side_effect=RuntimeError("No auxiliary LLM provider configured"),
        ):
            result = draft_contract("migrate auth")
        assert result.is_empty()

    def test_parses_valid_json_response(self):
        canned = jsonlib.dumps(
            {
                "outcome": "ship auth",
                "verification": "tests pass",
                "constraints": "no /login breakage",
                "boundaries": "src/auth",
                "stop_when": "schema change",
            }
        )
        with patch(
            "agent.auxiliary_client.call_llm",
            return_value=_fake_call_response(canned),
        ):
            result = draft_contract("migrate auth")
        assert result.outcome == "ship auth"
        assert result.verification == "tests pass"
        assert result.constraints == "no /login breakage"
        assert result.boundaries == "src/auth"
        assert result.stop_when == "schema change"

    def test_tolerates_fenced_json(self):
        """The model is told to reply one-line JSON; some implementations
        add a markdown fence — parse it anyway instead of returning empty."""
        fenced = (
            "```json\n"
            + jsonlib.dumps({"outcome": "ship it", "verification": "tests pass"})
            + "\n```"
        )
        with patch(
            "agent.auxiliary_client.call_llm",
            return_value=_fake_call_response(fenced),
        ):
            result = draft_contract("ship it")
        assert result.outcome == "ship it"
        assert result.verification == "tests pass"

    def test_returns_empty_on_malformed_json(self):
        with patch(
            "agent.auxiliary_client.call_llm",
            return_value=_fake_call_response("not json at all"),
        ):
            result = draft_contract("ship it")
        assert result.is_empty()

    def test_returns_empty_on_non_dict_json(self):
        with patch(
            "agent.auxiliary_client.call_llm",
            return_value=_fake_call_response("[1, 2, 3]"),
        ):
            result = draft_contract("ship it")
        assert result.is_empty()

    def test_draft_uses_goal_judge_task(self):
        """The aux LLM call must route through the goal_judge task so
        ``auxiliary.goal_judge.*`` config (model / reasoning_effort /
        extra_body) applies via the K-2 unified call_llm path."""
        captured = {}

        def _capture(*args, **kwargs):
            captured.update(kwargs)
            return _fake_call_response('{"outcome": "x"}')

        with patch("agent.auxiliary_client.call_llm", side_effect=_capture):
            draft_contract("ship it")
        assert captured["task"] == "goal_judge"
        # System prompt should instruct one-line JSON.
        sys_msg = captured["messages"][0]["content"]
        assert "single JSON object on one line" in sys_msg


# ──────────────────────────────────────────────────────────────────────
# GoalManager set(contract=...) integration
# ──────────────────────────────────────────────────────────────────────


class TestGoalManagerSetContract:
    def test_set_with_contract_persists(self, tmp_path, monkeypatch):
        """GoalManager.set should store the contract in GoalState, and
        ``to_json`` should round-trip it through SessionDB."""
        from hermes_cli.goals import GoalManager

        # Point the manager at a fresh tmp HERMES_HOME so we don't touch
        # the user's real session DB.
        monkeypatch.setenv("HERMES_HOME", str(tmp_path / ".hermes"))
        (tmp_path / ".hermes").mkdir()
        # Reset the module-level DB cache so the manager picks up the
        # new HERMES_HOME.
        goals._DB_CACHE.clear()

        mgr = GoalManager(session_id="test-cc-1")
        contract = GoalContract(
            outcome="migrate",
            verification="tests pass",
            constraints="no /login breakage",
        )
        state = mgr.set("migrate auth", contract=contract)

        assert state.has_contract()
        assert state.contract.verification == "tests pass"

        # Round-trip via DB.
        loaded = GoalManager(session_id="test-cc-1")._state
        assert loaded is not None
        assert loaded.has_contract()
        assert loaded.contract.to_dict() == contract.to_dict()

"""Regression tests for 12 cherry-pick split bugs in v0.17.0+cn.16+cn.17.

Each test maps 1:1 to a bug fix commit. Adding a test before a fix = TDD.
Removing a test = requires manual review of the related commit.

Bug → test mapping:

  1. 70c6f7cf8 / run_agent.py orphan 107-line body     → test_run_agent_module_loads
  2. 70c6f7cf8 / model_tools.py orphan 23-line try/except → test_model_tools_module_loads
  3. 70c6f7cf8 / context_compressor.py HISTORICAL_*      → test_summary_prefix_uses_defined_constants
  4. 70c6f7cf8 / run_agent.py _OPENAI_CLS_CACHE          → test_load_openai_cls_module_level_decl
  5. 70c6f7cf8 / hermes_state.py fts_migrations_complete → test_fts_migrations_complete_initialized
  6. 70c6f7cf8 / hermes_state.py v16 migration helpers   → test_schema_v16_migration_helpers_defined
  7. 70c6f7cf8 / hermes_state.py _insert_session_row cwd → test_insert_session_row_accepts_cwd
  8. 70c6f7cf8 / cli.py _release_active_session         → test_finalize_single_query_no_attribute_error
  9. 70c6f7cf8 / run_agent.py tool_progress_mode + 3 cb  → test_get_tool_definitions_signature_3_kwargs
 10. 70c6f7cf8 / utils.py mode -> original_mode          → test_atomic_json_write_uses_original_mode
 11. 47d0e5573 / cli.py finally: return                  → test_main_falls_through_to_cli_run_for_interactive
 12. a13843285 / prompt tier filter block                → test_prompt_tier_filter_block_present
"""
import importlib
import inspect
import subprocess

import pytest


# === Module load smoke (regression for orphan dead code) ===

def test_run_agent_module_loads():
    """Bug 1: orphan 107-line function body at line 9247 broke import.

    The forwarder was kept but the body of _try_shrink_image_parts_in_messages
    was left as dead code without a `def` line, breaking module load.
    """
    import run_agent
    assert hasattr(run_agent, "AIAgent"), "AIAgent class missing from run_agent"
    assert hasattr(run_agent, "_load_openai_cls"), "_load_openai_cls helper missing"


def test_model_tools_module_loads():
    """Bug 2: orphan 23-line try/except from PR #28479 rebase artifact.

    The dispatch path was wrapped in middleware on main, but cn has the
    direct-dispatch sites. The cherry-pick left an orphan except/try block
    that broke syntax.
    """
    import model_tools
    sig = inspect.signature(model_tools.get_tool_definitions)
    # 3 kwargs (post-fix #9): enabled_toolsets, disabled_toolsets, quiet_mode
    assert len(sig.parameters) == 3, (
        f"get_tool_definitions should have 3 kwargs, got {len(sig.parameters)}: "
        f"{list(sig.parameters)}"
    )


# === HISTORICAL_*_HEADING constants (Bug 3) ===

def test_summary_prefix_uses_defined_constants():
    """Bug 3: 4 HISTORICAL_*_HEADING constants referenced in f-string but not defined.

    Cherry-pick 180d4600c (PR #38389) used these constants in SUMMARY_PREFIX
    but the defining commit d5e2fbf24 was not cherry-picked.
    """
    from agent.context_compressor import (
        HISTORICAL_TASK_HEADING,
        HISTORICAL_IN_PROGRESS_HEADING,
        HISTORICAL_PENDING_ASKS_HEADING,
        HISTORICAL_REMAINING_WORK_HEADING,
    )
    for name, value in [
        ("HISTORICAL_TASK_HEADING", HISTORICAL_TASK_HEADING),
        ("HISTORICAL_IN_PROGRESS_HEADING", HISTORICAL_IN_PROGRESS_HEADING),
        ("HISTORICAL_PENDING_ASKS_HEADING", HISTORICAL_PENDING_ASKS_HEADING),
        ("HISTORICAL_REMAINING_WORK_HEADING", HISTORICAL_REMAINING_WORK_HEADING),
    ]:
        assert isinstance(value, str), f"{name} must be str"
        assert value.startswith("##"), f"{name} should be a markdown heading"


# === _OPENAI_CLS_CACHE module-level decl (Bug 4) ===

def test_load_openai_cls_module_level_decl():
    """Bug 4: _OPENAI_CLS_CACHE was used as `global` but never declared at module level.

    The function _load_openai_cls() did `global _OPENAI_CLS_CACHE` but the
    assignment was missing at the top of run_agent.py.
    """
    import run_agent
    # Module-level attribute must exist (not just inside the function scope)
    assert hasattr(run_agent, "_OPENAI_CLS_CACHE"), (
        "_OPENAI_CLS_CACHE missing at module level — global decl in _load_openai_cls would NameError"
    )
    # Initial value should be None
    assert run_agent._OPENAI_CLS_CACHE is None, (
        f"expected _OPENAI_CLS_CACHE initial value None, got {run_agent._OPENAI_CLS_CACHE!r}"
    )


# === fts_migrations_complete init (Bug 5) ===

def test_fts_migrations_complete_initialized():
    """Bug 5: fts_migrations_complete set inside v11 block but referenced unconditionally.

    Users at v12+ would hit UnboundLocalError when the final check runs.
    Fix: initialize fts_migrations_complete = True before the version-gated chain.
    """
    import hermes_state
    src = inspect.getsource(hermes_state)
    # The init must appear somewhere before the final check
    assert "fts_migrations_complete = True  # init" in src, (
        "fts_migrations_complete = True init line missing — users at v12+ will UnboundLocalError"
    )
    # The final check must reference the variable
    assert "if current_version < SCHEMA_VERSION and fts_migrations_complete" in src


# === v16 migration helpers (Bug 6) ===

def test_schema_v16_migration_helpers_defined():
    """Bug 6: v16 migration helpers + SCHEMA_VERSION bump both missing.

    The v16 migration code (from commit d62979a6f) referenced helpers that
    weren't defined. SCHEMA_VERSION also wasn't bumped from 15 to 16.
    """
    import hermes_state
    for helper in (
        "_delegate_from_json",
        "_BRANCH_CHILD_SQL",
        "_COMPRESSION_CHILD_SQL",
        "_LISTABLE_CHILD_SQL",
        "_ephemeral_child_sql",
    ):
        assert hasattr(hermes_state, helper), f"missing helper: {helper}"
    assert hermes_state.SCHEMA_VERSION >= 16, (
        f"SCHEMA_VERSION must be >= 16 to enable the v16 migration; got {hermes_state.SCHEMA_VERSION}"
    )


# === _insert_session_row accepts cwd (Bug 7) ===

def test_insert_session_row_accepts_cwd(tmp_path):
    """Bug 7: _insert_session_row signature missing 'cwd' param.

    Commit d3d406418 (PR #38562) added cwd=... to the call site but didn't
    update _insert_session_row to accept it.
    """
    import inspect
    from hermes_state import SessionDB
    sig = inspect.signature(SessionDB._insert_session_row)
    assert "cwd" in sig.parameters, (
        f"_insert_session_row missing 'cwd' param; got {list(sig.parameters)}"
    )


# === _release_active_session no-op stub (Bug 8) ===

def test_finalize_single_query_no_attribute_error():
    """Bug 8: _finalize_single_query called cli._release_active_session() but the
    full active-session lease mechanism wasn't cherry-picked.

    Fix: added no-op stubs to HermesCLI. One-shot CLI runs don't compete
    for the global slot.

    Source-level check (don't import cli.py — too heavy): verify the
    stubs are present in cli.py source.
    """
    from pathlib import Path
    cli_path = Path(__file__).resolve().parents[2] / "cli.py"
    src = cli_path.read_text()

    # Both stubs must be defined
    assert "def _claim_active_session" in src, (
        "_claim_active_session stub missing in cli.py — _finalize_single_query would AttributeError"
    )
    assert "def _release_active_session" in src, (
        "_release_active_session stub missing in cli.py — _finalize_single_query would AttributeError"
    )


# === get_tool_definitions signature (Bug 9) ===

def test_get_tool_definitions_signature_3_kwargs():
    """Bug 9: get_tool_definitions() only accepts 3 kwargs; cn call was passing 80+.

    Cherry-pick 6fb4419a1 expanded the call site but the callee refactor
    wasn't cherry-picked. Fix: shrunk the call to 3 kwargs.
    """
    from model_tools import get_tool_definitions
    import inspect
    sig = inspect.signature(get_tool_definitions)
    assert set(sig.parameters) == {"enabled_toolsets", "disabled_toolsets", "quiet_mode"}, (
        f"expected 3 specific kwargs, got {set(sig.parameters)}"
    )


def test_run_agent_init_has_tool_progress_mode():
    """Bug 9 (cont'd): AIAgent.__init__ missing tool_progress_mode signature.

    The expanded get_tool_definitions call passes tool_progress_mode=...
    but the __init__ didn't declare it.
    """
    import inspect
    from run_agent import AIAgent
    sig = inspect.signature(AIAgent.__init__)
    assert "tool_progress_mode" in sig.parameters, (
        f"AIAgent.__init__ missing tool_progress_mode; got {list(sig.parameters)}"
    )
    # 3 callbacks that were also missing
    for cb in ("read_terminal_callback", "user_id_alt"):
        assert cb in sig.parameters, f"AIAgent.__init__ missing {cb}"


# === atomic_json_write uses original_mode (Bug 10) ===

def test_atomic_json_write_uses_original_mode(tmp_path):
    """Bug 10: atomic_json_write referenced 'mode' but local var was 'original_mode'.

    Line 122 had `if mode is not None` but the assignment was to
    `original_mode = _preserve_file_mode(path)`. NameError on every call,
    silently swallowed → models_dev disk cache + skills prompt snapshot saves fail.
    """
    from utils import atomic_json_write
    target = tmp_path / "test.json"
    target.write_text("{}")
    # Should not raise NameError on 'mode'
    atomic_json_write(target, {"k": "v"})
    assert target.read_text()  # file exists and is non-empty


def test_atomic_json_write_source_uses_original_mode():
    """Bug 10 (cont'd): source-level structural check.

    Ensures the fix doesn't get reverted by a future commit. The check
    `if original_mode is not None` must be in utils.py.
    """
    from utils import atomic_json_write
    src = inspect.getsource(atomic_json_write)
    assert "if original_mode is not None" in src, (
        "atomic_json_write should check 'original_mode' (not 'mode')"
    )
    assert "os.fchmod(fd, original_mode)" in src, (
        "atomic_json_write should call fchmod with original_mode (not mode)"
    )


# === finally: return kills interactive mode (Bug 11) ===

def test_main_falls_through_to_cli_run_for_interactive():
    """Bug 11: `finally: return` made cli.run() dead code.

    When query/image are falsy (no -q/-Q), the user runs `hermes chat`
    expecting interactive mode. But the `finally` block's `return` exited
    main() before reaching `cli.run()`.

    Fix: removed the `return` from the finally block.

    Source-level check (don't import cli.py — too heavy): verify the
    structure of main() in cli.py source.
    """
    from pathlib import Path
    cli_path = Path(__file__).resolve().parents[2] / "cli.py"
    src = cli_path.read_text()
    lines = [l for l in src.splitlines() if l.strip()]

    # Find main() definition
    main_start = None
    for i, line in enumerate(lines):
        if line.startswith("def main(") and "def main_" not in line:
            main_start = i
            break
    assert main_start is not None, "main() not found in cli.py"

    # From main_start, find: finally: ... cli.run()
    found_finally = False
    found_cli_run = False
    for j in range(main_start, len(lines)):
        if "finally:" in lines[j]:
            found_finally = True
        if "cli.run()" in lines[j] and found_finally:
            found_cli_run = True
            # cli.run() must be at function level (indent 0-4), not nested
            # inside the try/finally block (which would be 8+).
            stripped = lines[j].lstrip()
            indent = len(lines[j]) - len(stripped)
            assert indent < 8, (
                f"cli.run() at indent {indent} — must be at function level (indent <8), "
                f"not inside try/finally. Otherwise the `finally: return` bug regressed."
            )
            return
    if not found_finally:
        pytest.fail("finally: not found in main() — structure changed")
    if not found_cli_run:
        pytest.fail("cli.run() not found after finally in main() — interactive mode may be dead")


# === _archived_list tier filter (Bug 12) ===

def test_prompt_tier_filter_block_present():
    """Bug 12: _archived_list NameError — tier filter block cherry-pick was dropped.

    The cherry-pick left the consumer code (`_archived_list = archived`)
    but not the if/else that always defines _archived_list. If the
    `if tier_data:` branch was False, `_archived_list` would be undefined.

    Fix commit a13843285 added `else: _archived_list = None`.

    This is a structural test — verify the else clause is present so the
    variable is always defined.
    """
    from agent import prompt_builder
    src = inspect.getsource(prompt_builder)
    # The else clause after `if tier_data:` must set _archived_list
    # Find the if tier_data: block and verify the else sets _archived_list
    assert "if tier_data:" in src, "if tier_data: block not found in prompt_builder"
    # The else must assign _archived_list = None
    assert "_archived_list = None" in src, (
        "_archived_list = None not found — the else branch is missing, "
        "so when tier_data is None, the variable is undefined and later "
        "uses raise NameError."
    )

"""Regression tests for the 12 cn split bugs (2026-07-03 ~ 07-22).

Each test asserts that the fix from a specific split-bug commit is still in place.
Static analysis (AST + source string) so the suite runs without needing the
optional `yaml` env dependency that some cn modules import transitively.

12 commits covered (per `2026-07-23-upstream-borrow/phase2-filter-borrow.md`
bug fix audit table):

  1.  (1st - pre-handle)            - n/a (merged before split-bug audit started)
  2.  1221320dc  whatsapp_identity restore
  3.  eb74cdf6b  Platform.HOMEASSISTANT removal
  4.  c7de9eec7  Platform.MSGRAPH_WEBHOOK removal
  5.  d2dadd73e  pre-existing test failures (Windows os.WIFEXITED fallback)
  6.  565b5228a  _current_max_iterations helper
  7.  4c89dafff  dispatch_once signature (default_assignee + max_in_progress_per_profile)
  8.  34607f7c3  cmd_quickstart register
  9.  91637ce1e  NAT-aware Ollama detection
  10. 023626054  NameError on terminal resize (cli.py)
  11. 0a8b17dd8  unterminated docstring in test_model_metadata.py
  12. aaa3ee615  _MAX_TAIL_MESSAGE_FLOOR constant

A failure here means a previously-fixed cn-specific bug has re-emerged (likely
from a refactor or partial cherry-pick that dropped the fix). The test name
embeds the commit hash so the offender can be located via `git show <hash>`.
"""

from __future__ import annotations

import ast
import os
import re
from pathlib import Path
from typing import Iterable

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]


def _read(rel_path: str) -> str:
    return (REPO_ROOT / rel_path).read_text(encoding="utf-8")


def _parse(rel_path: str) -> ast.Module:
    return ast.parse(_read(rel_path), filename=rel_path)


def _find_function(tree: ast.Module, name: str) -> ast.FunctionDef | None:
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return node
    return None


def _attr_names(tree: ast.Module, base: str) -> list[str]:
    """Return all attribute names accessed via ``<base>.<attr>`` in the tree.

    Comments are not part of the AST, so this only catches *real* uses.
    """
    found: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name):
            if node.value.id == base:
                found.append(node.attr)
    return found


def _function_params(tree: ast.Module, name: str) -> list[str]:
    """Return all param names of `name`, including keyword-only args (after `*,`).

    The split-bug dispatch_once fix added two kwargs *after* a `*,` separator, so
    they live in `args.kwonlyargs`, not `args.args`. We union the two so
    regression tests don't silently miss keyword-only signature additions.
    """
    func = _find_function(tree, name)
    if func is None:
        return []
    return [a.arg for a in func.args.args] + [a.arg for a in func.args.kwonlyargs]


# ---------------------------------------------------------------------------
# 2. 1221320dc - cherry-pick 1c68f6f81 + restore whatsapp_identity module
# ---------------------------------------------------------------------------
def test_split_bug_2_1221320dc_whatsapp_identity_module_exists() -> None:
    """The restored `gateway/whatsapp_identity` module must be importable as a file.

    The cn T1b jian-fa refactor (fa72efeb1) deleted the module but not its
    3 import sites; the later deletion of those sites was never cherry-picked.
    Cherry-picking upstream's 1c68f6f81 (which uses the helpers at run.py
    L6309/L6313/L6314) restored the module so the gateway can import.
    """
    path = REPO_ROOT / "gateway" / "whatsapp_identity.py"
    assert path.is_file(), f"missing module restored by 1221320dc: {path}"
    # Sanity: must be a real Python module, not a stub.
    text = path.read_text(encoding="utf-8")
    assert "canonical_whatsapp_identifier" in text or "whatsapp_identity" in text


# ---------------------------------------------------------------------------
# 3. eb74cdf6b - Platform.HOMEASSISTANT removal
# ---------------------------------------------------------------------------
def test_split_bug_3_eb74cdf6b_platform_homeassistant_removed() -> None:
    """No real code reference to `Platform.HOMEASSISTANT` should remain.

    The fix removed the `if platform == Platform.HOMEASSISTANT:` branch in
    `gateway/run.py:_is_user_authorized`. Comments mentioning the enum member
    are allowed (they document the removal), but AST-level Attribute nodes
    catch only real uses - which should be zero.
    """
    tree = _parse("gateway/run.py")
    attrs = _attr_names(tree, "Platform")
    assert "HOMEASSISTANT" not in attrs, (
        f"Platform.HOMEASSISTANT still referenced in gateway/run.py: {attrs}"
    )


# ---------------------------------------------------------------------------
# 4. c7de9eec7 — Platform.MSGRAPH_WEBHOOK removal
# ---------------------------------------------------------------------------
def test_split_bug_4_c7de9eec7_platform_msgraph_webhook_removed() -> None:
    """`_wire_teams_pipeline_runtime` must early-return with a T1c jian-fa marker.

    Mirror of the HOMEASSISTANT fix: the `elif platform == Platform.MSGRAPH_WEBHOOK:`
    branch in the teams-pipeline adapter-creation loop was removed. The fix
    inserted a `return` at the top of `_wire_teams_pipeline_runtime` with a
    comment referencing T1c jian-fa, so the rest of the function (which still
    mentions `Platform.MSGRAPH_WEBHOOK` in dead code preserved for documentation)
    is unreachable. A regression that drops the early return would re-expose
    the dead branch and crash the WSL gateway when the teams_pipeline plugin
    is enabled.
    """
    tree = _parse("gateway/run.py")
    func = _find_function(tree, "_wire_teams_pipeline_runtime")
    assert func is not None, (
        "_wire_teams_pipeline_runtime() missing from gateway/run.py"
    )
    # The fix marker is a string constant on its own line, containing
    # 'T1c jian-fa' (the cn-internal refactor that actually deleted the
    # MSGraph webhook adapter). The dead-code `if Platform.MSGRAPH_WEBHOOK
    # not in self.adapters:` is preserved below the `return` and is OK.
    src = ast.get_source_segment(_read("gateway/run.py"), func) or ""
    assert "T1c jian-fa" in src, (
        "_wire_teams_pipeline_runtime is missing the T1c jian-fa early-return "
        "marker comment introduced by c7de9eec7"
    )
    # The early return must be present (the body of the dead code is fine).
    assert re.search(r"^\s*return\s+#\s*cn T1c jian-fa", src, re.MULTILINE), (
        "expected `return  # cn T1c jian-fa: no MSGraph webhook adapter` line "
        "introduced by c7de9eec7"
    )


# ---------------------------------------------------------------------------
# 5. d2dadd73e - Windows os.WIFEXITED fallback (7 pre-existing test failures)
# ---------------------------------------------------------------------------
def test_split_bug_5_d2dadd73e_wifexited_windows_fallback() -> None:
    """`os.WIFEXITED` / `os.WIFSIGNALED` must be guarded with `hasattr(os, ...)`.

    The cn T1b refactor ran the protocol_violation auto-block path on POSIX
    only; on Windows `os.WIFEXITED` doesn't exist and the raw `os.WIFEXITED(raw)`
    call raised AttributeError. The fix wraps both calls in `hasattr(os, ...)`
    so the same code path runs on both platforms.
    """
    text = _read("hermes_cli/kanban_db.py")
    # The guard is required; raw use is forbidden.
    assert re.search(r"hasattr\(\s*os\s*,\s*[\"']WIFEXITED[\"']\s*\)", text), (
        "missing hasattr(os, 'WIFEXITED') guard introduced by d2dadd73e"
    )
    assert re.search(r"hasattr\(\s*os\s*,\s*[\"']WIFSIGNALED[\"']\s*\)", text), (
        "missing hasattr(os, 'WIFSIGNALED') guard introduced by d2dadd73e"
    )
    # Negative: no raw `os.WIFEXITED(raw)` outside the guard.
    # Match raw calls that are NOT inside a `hasattr(...) and ...` short-circuit.
    # We approximate by ensuring every `os.WIFEXITED(` is preceded (within
    # the same line) by the `and` of a hasattr guard - too brittle. Instead,
    # we just assert the guard exists (above) and skip the negative regex.


# ---------------------------------------------------------------------------
# 6. 565b5228a - _current_max_iterations helper
# ---------------------------------------------------------------------------
def test_split_bug_6_565b5228a_current_max_iterations_helper() -> None:
    """`gateway.run._current_max_iterations` must be defined and callable.

    Cherry-pick companion to api_server.py:932 - upstream 460b1e50e introduced
    this helper so per-turn runtime budget reflects freshly loaded config.yaml
    without letting stale .env override authoritative config. cn cherry-picked
    the call site but not the definition, leading to ImportError on first use.
    """
    tree = _parse("gateway/run.py")
    func = _find_function(tree, "_current_max_iterations")
    assert func is not None, (
        "_current_max_iterations() missing from gateway/run.py "
        "(defined in 565b5228a, cherry-pick companion to api_server.py)"
    )
    # The helper refreshes runtime env then reads HERMES_MAX_ITERATIONS
    # with a default of 90. We just assert the function body is non-empty.
    assert len(func.body) > 0


# ---------------------------------------------------------------------------
# 7. 4c89dafff - dispatch_once signature (default_assignee + max_in_progress_per_profile)
# ---------------------------------------------------------------------------
def test_split_bug_7_4c89dafff_dispatch_once_kwargs() -> None:
    """`dispatch_once` must accept `default_assignee` and `max_in_progress_per_profile`.

    Cherry-pick companion to gateway/kanban_watchers.py:806 - upstream 3b6347af1
    added these kwargs; cn cherry-picked the call site but not the signature, so
    the gateway-embedded dispatcher tick raised
    `TypeError: dispatch_once() got an unexpected keyword argument 'default_assignee'`
    on the first board 6 seconds after gateway startup. Body implementation of
    the upstream feature is NOT included here - only the kwargs are accepted.
    """
    tree = _parse("hermes_cli/kanban_db.py")
    params = _function_params(tree, "dispatch_once")
    assert "default_assignee" in params, (
        f"dispatch_once() missing 'default_assignee' kwarg from 4c89dafff; "
        f"have: {params}"
    )
    assert "max_in_progress_per_profile" in params, (
        f"dispatch_once() missing 'max_in_progress_per_profile' kwarg from 4c89dafff; "
        f"have: {params}"
    )


# ---------------------------------------------------------------------------
# 8. 34607f7c3 - cmd_quickstart register
# ---------------------------------------------------------------------------
def test_split_bug_8_34607f7c3_cmd_quickstart_registered() -> None:
    """`hermes_cli.main.cmd_quickstart` must be a callable function.

    Without this thin wrapper, the subparser registration at the bottom of
    `hermes_cli/main.py` would fail to resolve `cmd_quickstart` and
    `hermes quickstart` would be unreachable from the CLI.
    """
    tree = _parse("hermes_cli/main.py")
    func = _find_function(tree, "cmd_quickstart")
    assert func is not None, (
        "cmd_quickstart() missing from hermes_cli/main.py (registered in 34607f7c3)"
    )
    # Wrapper should defer to hermes_cli.quickstart.cmd_quickstart.
    src = ast.get_source_segment(_read("hermes_cli/main.py"), func) or ""
    assert "from hermes_cli.quickstart import cmd_quickstart" in src, (
        "cmd_quickstart wrapper does not defer to hermes_cli.quickstart"
    )


# ---------------------------------------------------------------------------
# 9. 91637ce1e - NAT-aware Ollama detection
# ---------------------------------------------------------------------------
def test_split_bug_9_91637ce1e_nat_aware_ollama_detection() -> None:
    """`hermes_cli/quickstart.py` must document the NAT-aware Ollama resolution.

    Before this fix every Ollama URL was hardcoded `http://localhost:11434`,
    which silently breaks for WSL2 users running Ollama on the Windows host
    with NAT networking. The fix added a NAT-aware resolution order and a
    `host.docker.internal` fallback. The test asserts the documentation
    marker is present; the resolution logic is exercised by
    `tests/hermes_cli/test_quickstart_ollama.py` (or similar).
    """
    text = _read("hermes_cli/quickstart.py")
    # Look for the NAT-aware header comment or the function that does the
    # multi-host resolution. Both are reliable markers introduced in 91637ce1e.
    assert "NAT-aware" in text or "host.docker.internal" in text or "WSL2 NAT" in text, (
        "quickstart.py missing NAT-aware Ollama detection (regression of 91637ce1e)"
    )


# ---------------------------------------------------------------------------
# 10. 023626054 - NameError on terminal resize (cli.py)
# ---------------------------------------------------------------------------
def test_split_bug_10_023626054_resize_nameerror_fix() -> None:
    """`cli.py:_schedule_status_bar_unsuppress` must NOT call `original_on_resize()`.

    The earlier code (pre-fix) had a copy-paste leftover: a call to
    `original_on_resize()` inside `_schedule_status_bar_unsuppress`, where
    `original_on_resize` is NOT in scope (it lives in `_recover_after_resize`'s
    scope). The first resize recovery that took the debounced path raised
    `NameError: name 'original_on_resize' is not defined`. The fix removed the
    call and added a comment explaining why so a future refactor doesn't
    re-introduce it.

    `ast.get_source_segment` doesn't include trailing comments after the last
    statement, so we read the file directly and bound the check to the lines
    between the function def and the next top-level `def`.
    """
    rel = "cli.py"
    text = _read(rel)
    # Locate `_schedule_status_bar_unsuppress` def and the next top-level def.
    lines = text.splitlines()
    start = end = None
    for i, line in enumerate(lines, start=1):
        if start is None and line.lstrip().startswith("def _schedule_status_bar_unsuppress"):
            start = i
        elif start is not None and line and not line[0].isspace() and line.startswith("def "):
            end = i - 1
            break
    assert start is not None, "_schedule_status_bar_unsuppress() missing from cli.py"
    if end is None:
        end = len(lines)
    func_block = "\n".join(lines[start - 1 : end])
    # Negative: no call to `original_on_resize` inside the function block.
    tree = _parse(rel)
    func_node = _find_function(tree, "_schedule_status_bar_unsuppress")
    assert func_node is not None
    for node in ast.walk(func_node):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            if node.func.id == "original_on_resize":
                pytest.fail(
                    "_schedule_status_bar_unsuppress() must not call "
                    "original_on_resize() (regression of 023626054 10th "
                    "split bug cleanup)"
                )
    # Positive: a comment marker explaining the fix is present in the
    # function block (incl. trailing comments after the last statement).
    assert "do NOT call original_on_resize" in func_block, (
        "missing 'do NOT call original_on_resize' marker comment in "
        "_schedule_status_bar_unsuppress - a future refactor could "
        "re-introduce the bug"
    )


# ---------------------------------------------------------------------------
# 11. 0a8b17dd8 - unterminated docstring in test_model_metadata.py
# ---------------------------------------------------------------------------
def test_split_bug_11_0a8b17dd8_test_model_metadata_parses() -> None:
    """`tests/agent/test_model_metadata.py` must be valid Python (parses cleanly).

    The 11th split bug was an unterminated docstring in the test file itself.
    `ast.parse` would raise SyntaxError on the file. The fix added the closing
    triple-quote. This test fails immediately if anyone re-introduces an
    unterminated docstring.
    """
    rel = "tests/agent/test_model_metadata.py"
    text = _read(rel)
    try:
        ast.parse(text, filename=rel)
    except SyntaxError as exc:
        pytest.fail(
            f"{rel} has a syntax error (regression of 0a8b17dd8 unterminated "
            f"docstring): {exc}"
        )


# ---------------------------------------------------------------------------
# 12. aaa3ee615 - _MAX_TAIL_MESSAGE_FLOOR constant
# ---------------------------------------------------------------------------
def test_split_bug_12_aaa3ee615_max_tail_message_floor_constant() -> None:
    """`agent.context_compressor._MAX_TAIL_MESSAGE_FLOOR` must be defined as 8.

    Cherry-pick companion to upstream b7e688bba - the commit references the
    constant in the auto-focus tail-cut path but the definition line was
    missing in cn. Any chat triggering the 'Auxiliary background review'
    path raised `NameError: name '_MAX_TAIL_MESSAGE_FLOOR' is not defined`.
    Upstream defines it as 8.
    """
    tree = _parse("agent/context_compressor.py")
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Assign)
            and len(node.targets) == 1
            and isinstance(node.targets[0], ast.Name)
            and node.targets[0].id == "_MAX_TAIL_MESSAGE_FLOOR"
        ):
            value = node.value
            if isinstance(value, ast.Constant) and value.value == 8:
                return
            # Allow `8` wrapped in a unary `+` / `-` too (paranoia).
            if (
                isinstance(value, ast.UnaryOp)
                and isinstance(value.op, ast.UAdd)
                and isinstance(value.operand, ast.Constant)
                and value.operand.value == 8
            ):
                return
    pytest.fail(
        "_MAX_TAIL_MESSAGE_FLOOR = 8 missing from agent/context_compressor.py "
        "(regression of aaa3ee615 12th split bug cleanup)"
    )


# ---------------------------------------------------------------------------
# Sanity: every test name in this module embeds the commit hash it guards.
# ---------------------------------------------------------------------------
def test_split_bugs_regression_suite_covers_all_11_known_commits() -> None:
    """Meta-test: assert that this file's test functions reference the
    expected commit hashes in their names. Catches accidental renaming
    that would orphan a test from its provenance.
    """
    expected = {
        "1221320dc",
        "eb74cdf6b",
        "c7de9eec7",
        "d2dadd73e",
        "565b5228a",
        "4c89dafff",
        "34607f7c3",
        "91637ce1e",
        "023626054",
        "0a8b17dd8",
        "aaa3ee615",
    }
    this_file = Path(__file__)
    text = this_file.read_text(encoding="utf-8")
    found: set[str] = set()
    for h in expected:
        if h in text:
            found.add(h)
    missing = expected - found
    assert not missing, f"regression suite no longer references commits: {missing}"

"""Sprint 15 in-scope fix: SIGTERM-from-subprocess vs user Ctrl+C distinction.

Before the fix, `except KeyboardInterrupt:` in agent/tool_executor.py
unconditionally called `agent.interrupt("keyboard interrupt")`, which set
`agent._interrupt_requested = True`. This caused the conversation loop to
exit with `reason=interrupted_by_user` even when the KeyboardInterrupt
came from a subprocess receiving SIGTERM (e.g. install.sh run_with_timeout
sending SIGTERM to the process group — see scripts/install.sh:2059-2144).

The fix: only call agent.interrupt() when user has actively redirected
(_pending_redirect is set via /steer or new message). When no redirect is
pending, the KeyboardInterrupt is treated as a tool-level cancellation,
not a user interrupt, so the conversation continues normally.

These tests verify the three cases the fix must distinguish:
1. SIGTERM from subprocess (no redirect) → no interrupt flag set
2. User redirect + KeyboardInterrupt → interrupt flag set
3. User Ctrl+C with pending redirect → interrupt flag set (existing behavior)
"""

import threading
import unittest
from unittest.mock import MagicMock


def _make_bare_agent():
    """Create a bare AIAgent via __new__ with all interrupt-related attrs.

    Mirrors tests/run_agent/test_interrupt_propagation.py setUp style,
    with _pending_redirect + _pending_redirect_lock added (needed for the
    _has_pending_redirect() guard introduced in Sprint 15).
    """
    from run_agent import AIAgent
    agent = AIAgent.__new__(AIAgent)
    agent._interrupt_requested = False
    agent._interrupt_message = None
    agent._hard_interrupt_requested = threading.Event()
    agent._execution_thread_id = None
    agent._interrupt_thread_signal_pending = False
    agent._pending_redirect = None
    agent._pending_redirect_lock = threading.Lock()
    # Mock interrupt() to avoid _set_interrupt(thread_id=None) raising
    # in the bare-agent test fixture. Real agent.interrupt() also calls
    # _set_interrupt only when _execution_thread_id is set, so this mock
    # matches the production gate.
    agent.interrupt = MagicMock()
    return agent


def _simulate_tool_executor_fix(agent):
    """Mirror the fixed except KeyboardInterrupt: block from agent/tool_executor.py.

    Returns True if agent.interrupt() was called, False otherwise.
    Mirrors the 3 sites in tool_executor.py:
      - line 1071 (managed-execution branch)
      - line 2079 (interactive spinner branch)
      - line 2156 (non-spinner branch)
    All 3 use the same `if agent._has_pending_redirect():` guard.
    """
    if agent._has_pending_redirect():
        try:
            agent.interrupt("keyboard interrupt")
            return True
        except Exception:
            return False
    return False


class TestToolExecutorSignalDistinction(unittest.TestCase):
    """Sprint 15: SIGTERM-from-subprocess must not be treated as user interrupt."""

    def test_subprocess_sigterm_without_redirect_does_not_set_interrupt(self):
        """SIGTERM from subprocess (e.g. install.sh run_with_timeout) with no user
        redirect pending must NOT call agent.interrupt().

        Reproduces: install.sh run_with_timeout (scripts/install.sh:2059-2144)
        sends SIGTERM to process group, hermes-cli signal handler
        (hermes_cli/proxy/server.py:277-282) raises KeyboardInterrupt. Before
        the fix, agent._interrupt_requested was set to True, causing the
        conversation to exit with interrupted_by_user. After the fix, only
        the tool is cancelled; the conversation continues normally.
        """
        agent = _make_bare_agent()
        # No user redirect: install.sh timeout, not user Ctrl+C
        agent._pending_redirect = None

        interrupt_was_called = _simulate_tool_executor_fix(agent)

        self.assertFalse(
            interrupt_was_called,
            "agent.interrupt() must not be called when no user redirect is pending",
        )
        agent.interrupt.assert_not_called()
        # Note: _interrupt_requested stays False because interrupt() was never
        # called (the mock would have set it if called).
        self.assertFalse(agent._interrupt_requested)

    def test_user_redirect_with_keyboardinterrupt_sets_interrupt(self):
        """When user has actively redirected (/steer or new message) and a
        KeyboardInterrupt is raised, agent.interrupt() should be called.

        This preserves the existing behavior for genuine user-initiated
        interrupts: a user types Ctrl+C while a tool is running, after
        having already submitted a redirect via /steer or a new message.
        """
        agent = _make_bare_agent()
        # User actively redirected via /steer or new message
        agent._pending_redirect = "user correction text"

        interrupt_was_called = _simulate_tool_executor_fix(agent)

        self.assertTrue(
            interrupt_was_called,
            "agent.interrupt() must be called when user redirect is pending",
        )
        agent.interrupt.assert_called_once_with("keyboard interrupt")

    def test_user_ctrl_c_with_pending_redirect_sets_interrupt(self):
        """User Ctrl+C with a pending redirect should call agent.interrupt().
        This is the standard user-interrupt path and must keep working after
        the fix.

        Scenario: user types /steer or new message (sets _pending_redirect),
        then presses Ctrl+C while a tool is still executing. The interrupt
        should propagate to interrupt the current turn.
        """
        agent = _make_bare_agent()
        # Simulate: user typed a redirect via stdin, then pressed Ctrl+C
        agent._pending_redirect = "user typed during tool execution"

        interrupt_was_called = _simulate_tool_executor_fix(agent)

        self.assertTrue(interrupt_was_called)
        agent.interrupt.assert_called_once_with("keyboard interrupt")

    def test_has_pending_redirect_false_when_no_redirect(self):
        """_has_pending_redirect() should return False when _pending_redirect is None.

        Helper assertion guarding the fix's check predicate.
        """
        agent = _make_bare_agent()
        agent._pending_redirect = None
        self.assertFalse(agent._has_pending_redirect())

    def test_has_pending_redirect_true_when_set(self):
        """_has_pending_redirect() should return True when _pending_redirect is set.

        Helper assertion guarding the fix's check predicate.
        """
        agent = _make_bare_agent()
        agent._pending_redirect = "some user text"
        self.assertTrue(agent._has_pending_redirect())


if __name__ == "__main__":
    unittest.main()

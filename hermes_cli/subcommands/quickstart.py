"""``hermes quickstart`` subcommand parser (CN).

CN one-shot wizard: auto-detect local + cloud resources and configure a
layered routing chain (Ollama / LM Studio / llama.cpp primary → cloud API
fallback → embedded offline fallback). Implementation lives in
``hermes_cli/quickstart.py:cmd_quickstart``. Handler injected to avoid
importing ``main``; the heavyweight detection module only loads at
invocation time via the ``cmd_quickstart`` wrapper in ``main.py``.
"""

from __future__ import annotations

from typing import Callable


def build_quickstart_parser(subparsers, *, cmd_quickstart: Callable) -> None:
    """Attach the ``quickstart`` subcommand to ``subparsers``."""
    # =========================================================================
    # quickstart command (CN-specific)
    # =========================================================================
    quickstart_parser = subparsers.add_parser(
        "quickstart",
        help="CN one-shot quickstart: auto-detect local + cloud resources and configure layered routing",
        description=(
            "Hermes-Agent-CN quickstart wizard. Detects Ollama / LM Studio / "
            "llama.cpp / cloud API keys / embedded fallback and configures a "
            "layered routing chain."
        ),
    )
    quickstart_parser.set_defaults(func=cmd_quickstart)

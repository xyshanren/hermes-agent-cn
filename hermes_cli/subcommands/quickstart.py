"""``hermes quickstart`` subcommand parser (CN).

CN one-shot wizard: detect cloud API keys, the AIMC gateway and
local_runtime-hosted GGUF models, then configure the primary model plus
routing rules. Other local model servers (Ollama / LM Studio / vLLM) are
configured through ``hermes model``'s custom-provider flow instead.
Implementation lives in ``hermes_cli/quickstart.py:cmd_quickstart``. Handler
injected to avoid importing ``main``; the heavyweight detection module only
loads at invocation time via the ``cmd_quickstart`` wrapper in ``main.py``.
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
        help="CN one-shot quickstart: cloud API keys / AIMC / local_runtime models → routing",
        description=(
            "Hermes-Agent-CN quickstart wizard. Detects cloud API keys, the "
            "AIMC gateway and local_runtime-hosted GGUF models, then configures "
            "the primary model and routing rules. Other local model servers "
            "belong in `hermes model`'s custom provider flow."
        ),
    )
    quickstart_parser.set_defaults(func=cmd_quickstart)

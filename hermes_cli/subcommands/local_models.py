"""``hermes local-models`` subcommand parser (CN).

CN offline model management: embedded CPU inference models (Qwen, whisper,
edge-tts, ...) installed from the ModelScope mirror — zero API dependency,
usable offline. Implementation lives in ``hermes_cli/model_manager.py``
(stdlib-only module; handlers imported directly, no dependency on ``main``).

Restored 2026-09-19 alongside the module after the v0.19.1/v0.20.0
base-bump rewrite dropped both; the docs (README / docs/API.md) and
``hermes quickstart`` output referenced ``hermes local-models`` while no
subcommand registered it.
"""

from __future__ import annotations

from hermes_cli.model_manager import (
    cmd_local_models_install,
    cmd_local_models_list,
    cmd_local_models_remove,
    cmd_local_models_setup,
    cmd_local_models_status,
    cmd_local_models_test,
)


def build_local_models_parser(subparsers) -> None:
    """Attach the ``local-models`` subcommand group to ``subparsers``."""
    local_models_parser = subparsers.add_parser(
        "local-models",
        help="CN: manage local offline models (embedded CPU inference)",
        description=(
            "Manage locally-installed offline models (embedded CPU "
            "inference via llama-cpp-python, faster-whisper, edge-tts). "
            "Models download from the ModelScope mirror — no API key, "
            "works offline."
        ),
    )
    lm_subparsers = local_models_parser.add_subparsers(dest="local_models_action")

    def _local_models_summary(args):
        local_models_parser.print_help()
        return 0

    local_models_parser.set_defaults(func=_local_models_summary)

    lm_subparsers.add_parser(
        "list",
        help="List available and installed local models",
    ).set_defaults(func=cmd_local_models_list)

    install_parser = lm_subparsers.add_parser(
        "install",
        help="Install a local model by id (or 'all' for bundled+recommended)",
    )
    install_parser.add_argument("model", nargs="?", default=None, help="Model id")
    install_parser.set_defaults(func=cmd_local_models_install)

    setup_parser = lm_subparsers.add_parser(
        "setup",
        help="One-shot install: runtime deps + all built-in/recommended models",
    )
    setup_parser.add_argument(
        "--yes", action="store_true", help="Skip the confirmation prompt",
    )
    setup_parser.set_defaults(func=cmd_local_models_setup)

    remove_parser = lm_subparsers.add_parser(
        "remove",
        help="Remove an installed local model",
    )
    remove_parser.add_argument("model", nargs="?", default=None, help="Model id")
    remove_parser.set_defaults(func=cmd_local_models_remove)

    lm_subparsers.add_parser(
        "status",
        help="Show detailed status of installed models",
    ).set_defaults(func=cmd_local_models_status)

    test_parser = lm_subparsers.add_parser(
        "test",
        help="Run a smoke inference test on an installed model",
    )
    test_parser.add_argument("model", nargs="?", default=None, help="Model id")
    test_parser.set_defaults(func=cmd_local_models_test)

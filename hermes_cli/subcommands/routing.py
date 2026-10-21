"""``hermes routing`` subcommand parser (CN).

Routing-rule patch management (CAND-080 layer 1.1 CLI). Surfaces
``hermes routing patches <list|show|apply|history>`` as the shell-side
companion to ``tools.routing_rule_manager_tool``; every config-writing step
delegates back to the tool so the ``confirmed=True`` fail-fast gate lives in
exactly one place. The handler is injected so this module never imports
``main``; the implementation lives in ``hermes_cli/main_routing_patches.py``.
"""

from __future__ import annotations

from typing import Callable


def build_routing_parser(subparsers, *, cmd_routing_patches: Callable) -> None:
    """Attach the ``routing`` subcommand to ``subparsers``."""
    routing_parser = subparsers.add_parser(
        "routing",
        help="Manage routing-rule patches (CAND-080 layer 1.1)",
        description=(
            "Inspect and apply routing-rule patches queued by the agent. "
            "The tool layer (tools.routing_rule_manager_tool) is the "
            "canonical source of the apply gate; this CLI is a thin shell "
            "wrapper. Patches land in config.yaml::model_routing.rules "
            "only via ``hermes routing patches apply <patch_id> --confirmed``."
        ),
    )
    routing_subparsers = routing_parser.add_subparsers(dest="routing_action")

    # The actual patch sub-action group lives under ``hermes routing
    # patches`` (跟 task 1 kickoff doc 1:1 命名). A bare ``hermes routing``
    # prints the namespace summary and exits.
    routing_patches_parser = routing_subparsers.add_parser(
        "patches",
        help="Manage the routing-rule patch queue (pending + applied)",
        description=(
            "Inspect and apply routing-rule patches. The patch queue "
            "lives under ``$HERMES_HOME/routing_patches/{pending,applied}/``; "
            "the apply step writes ``config.yaml::model_routing.rules`` "
            "atomically via ``hermes_cli.config.save_config`` (跟 task 1 "
            "借现成 0 新模式)."
        ),
    )
    patches_subparsers = routing_patches_parser.add_subparsers(
        dest="patches_action"
    )

    # list
    patches_subparsers.add_parser(
        "list",
        help="List pending + applied routing-rule patches",
    )

    # show <patch_id>
    patches_show = patches_subparsers.add_parser(
        "show",
        help="Show one routing-rule patch by id (pending first, then applied)",
    )
    patches_show.add_argument(
        "patch_id",
        help="12-char patch id returned by the layer-1 patch tool",
    )

    # apply <patch_id> [--confirmed]
    patches_apply = patches_subparsers.add_parser(
        "apply",
        help=(
            "Apply a pending routing-rule patch to config.yaml. "
            "REQUIRES --confirmed (跟 tool confirmed=True 1:1, 0 隐式)."
        ),
    )
    patches_apply.add_argument(
        "patch_id",
        help="12-char patch id of a queued (pending) patch",
    )
    patches_apply.add_argument(
        "--confirmed",
        action="store_true",
        default=False,
        help=(
            "Explicit user confirmation. Required to land the patch in "
            "config.yaml. CAND-085 4 铁律 1:1 (不写回 hermes profile): "
            "without this flag the CLI refuses the apply."
        ),
    )

    # history
    patches_subparsers.add_parser(
        "history",
        help="List only applied patches (read-only, 跟 CAND-085 1:1)",
    )

    routing_patches_parser.set_defaults(func=cmd_routing_patches)
    routing_parser.set_defaults(func=cmd_routing_patches)

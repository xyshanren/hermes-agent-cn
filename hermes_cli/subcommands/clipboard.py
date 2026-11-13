"""``hermes clipboard`` subcommand parser."""

from __future__ import annotations

from hermes_cli.subcommands._shared import add_json_flag


def _cmd_clipboard(args):
    from hermes_cli.clipboard_cmd import cmd_clipboard

    return cmd_clipboard(args)


def build_clipboard_parser(subparsers) -> None:
    """Attach the ``clipboard`` subcommand to ``subparsers``."""
    from agent.i18n import t

    clipboard_parser = subparsers.add_parser(
        "clipboard", help=t("cli.clipboard.help"),
        description=t("cli.clipboard.description"))
    actions = clipboard_parser.add_subparsers(dest="clipboard_action", required=True)
    image_parser = actions.add_parser(
        "image", help=t("cli.clipboard.image_help"),
        description=t("cli.clipboard.image_description"))
    image_parser.add_argument("--out", required=True, metavar="PATH", help=t("cli.clipboard.out_help"))
    add_json_flag(image_parser, t("cli.clipboard.json_help"))
    image_parser.set_defaults(func=_cmd_clipboard)

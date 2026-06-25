"""Bitwarden secret source - CN reduction stub.

The Bitwarden integration was removed in v0.15.0+cn.6 (T1a jian-fa reduction).
This stub exists because `secrets_cli.py` still imports from this module path
(not yet pruned in CN). The CLI is only reachable via the explicit subcommand
`hermes secrets bitwarden ...`; calling any function here will raise a clear
"removed in CN" error.
"""

from __future__ import annotations
from typing import Any


# Constants expected by the (still-imported) secrets_cli module
_BWS_VERSION: str = "0.0.0-removed-cn"


class BitwardenRemovedError(NotImplementedError):
    """Raised when a Bitwarden function is called after CN reduction."""

    def __init__(self) -> None:
        super().__init__(
            "Bitwarden integration removed in CN v0.15.0+cn.6 "
            "(T1a jian-fa reduction). This CLI is a no-op stub."
        )


def find_bws(*_args: Any, **_kwargs: Any) -> None:
    """Stub: always returns None (no bws binary)."""
    return None


def install_bws(*_args: Any, **_kwargs: Any) -> None:
    """Stub: raises NotImplementedError."""
    raise BitwardenRemovedError()


def fetch_bitwarden_secrets(*_args: Any, **_kwargs: Any) -> tuple[dict[str, str], list[str]]:
    """Stub: returns empty secrets and a single warning."""
    return {}, ["Bitwarden integration removed in CN v0.15.0+cn.6 (T1a jian-fa reduction)."]

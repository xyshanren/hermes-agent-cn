"""External secret source integrations.

A secret source is anything that can supply environment-variable-shaped
credentials at process startup, _after_ ~/.hermes/.env has loaded.  By
default sources are non-destructive: they only set values for env vars
that aren't already present, so .env and shell exports continue to win.

(v0.15.0+cn.6: Bitwarden integration removed — see CHANGELOG_CN.md
T1a jian-fa.  No remaining secret source modules.)
"""

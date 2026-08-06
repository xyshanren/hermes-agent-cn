#!/usr/bin/env python3
"""
Check for unresolved Git merge conflict markers.

Proper state machine: a real conflict marker is a 3-part pair
  <<<<<<<  (7 '<' chars, line start)
  ...
  =======  (7 '=' chars, line start)
  ...
  >>>>>>>  (7 '>' chars, line start)

False positives we must avoid:
  - Python module-level docstring separator (single-line '=======')
  - Python comment separator (e.g. '# ===============')
  - Markdown / docs that mention markers as examples

Strategy: only flag a '=======' or '>>>>>>>' if preceded by an unmatched '<<<<<<<'.
A stray standalone '=======' (like the docstring separator) is ignored.
"""

import os
import sys
from pathlib import Path

EXCLUDE_DIRS = {".git", ".venv", "archive", "__pycache__", "node_modules"}
EXCLUDE_FILES = {  # known false-positive cases (if any in future)
    # "tests/tools/test_mcp_oauth_metadata.py:10",  # docstring separator; legitimate non-conflict
}
INCLUDE_EXT = (".py", ".md", ".yaml", ".json", ".yml")

CONFLICT_START = "<" * 7
CONFLICT_MID = "=" * 7
CONFLICT_END = ">" * 7


def find_unresolved_conflicts(root_dir):
    """Walk root_dir and return list of (path, lineno, line) for unresolved conflict markers."""
    conflicts = []
    for root, dirs, files in os.walk(root_dir):
        # Filter excluded dirs in-place so os.walk skips them
        dirs[:] = [d for d in dirs if d not in EXCLUDE_DIRS]
        for fname in files:
            if not fname.endswith(INCLUDE_EXT):
                continue
            path = os.path.join(root, fname)
            if path in EXCLUDE_FILES:
                continue
            try:
                with open(path, "r", encoding="utf-8") as f:
                    in_conflict = False
                    for lineno, raw in enumerate(f, 1):
                        line = raw.rstrip("\n")
                        if line.startswith(CONFLICT_START):
                            in_conflict = True
                        elif in_conflict and line.startswith(CONFLICT_MID):
                            pass  # mid marker, expected
                        elif in_conflict and line.startswith(CONFLICT_END):
                            # Properly closed conflict block
                            conflicts.append((path, lineno, line))
                            in_conflict = False
                        elif in_conflict:
                            # Started a conflict but next line is neither mid nor end
                            # -- false positive, reset
                            in_conflict = False
            except (UnicodeDecodeError, OSError):
                # Binary or unreadable file -- skip
                continue
    return conflicts


def main():
    repo_root = Path(__file__).parent.parent
    conflicts = find_unresolved_conflicts(str(repo_root))

    if conflicts:
        print("ERROR: Unresolved merge conflicts found:")
        for path, lineno, line in conflicts:
            print(f"  {path}:{lineno}: {line}")
        return 1

    print("No unresolved merge conflicts")
    return 0


if __name__ == "__main__":
    sys.exit(main())

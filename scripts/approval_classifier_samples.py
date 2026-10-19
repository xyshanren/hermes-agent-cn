#!/usr/bin/env python3
"""Approval classifier sample table: find-family deletion forms.

Data-driven sample table (command form -> expected classification) for the
destructive-command approval layer. Born from the 2026-09-26 incident where
a `find ... | xargs rm -rf` deleting 326 directories ran with no approval
while bare `rm -rf` and `find -delete` both prompted (see
docs/approval-classifier-gaps.md).

Classification follows DELETION SEMANTICS, not the command head word: any
pipeline that ends in bulk deletion must land in the dangerous class,
whatever the entry point (find -exec/-execdir/-delete, xargs rm, plain rm).

Usage:
    python scripts/approval_classifier_samples.py            # full report
    python scripts/approval_classifier_samples.py --quiet    # misses only

Exit codes: 0 = no misses (every "dangerous" sample is detected);
1 = at least one miss. False positives on "clean" samples are reported but
do not fail the run (overtriggering is the safe direction — approval
friction, not a bypass).

stdlib-only; imports the real detector (no mocks) so the measurement always
reflects the shipped pattern tables.
"""

from __future__ import annotations

import sys

sys.path.insert(0, ".")

from tools.approval import detect_dangerous_command, detect_hardline_command  # noqa: E402

# (command, expected, note)
# expected: "dangerous" — must be flagged (approval prompt in manual mode)
#           "clean"     — must NOT be flagged
SAMPLES: list[tuple[str, str, str]] = [
    # --- find -delete family ---
    ("find /proj -name '*.tsbuildinfo' -delete", "dangerous", "bare -delete"),
    ("find /proj -name '*.tmp' -delete -print", "dangerous", "-delete with trailing action"),
    # --- find -exec rm family ---
    ("find /proj -name '*.log' -exec rm {} \\;", "dangerous", "-exec rm brace-semicolon"),
    ("find /proj -type d -name node_modules -exec rm -rf {} +", "dangerous", "-exec rm -rf plus-form"),
    ("find /proj \\( -name '*.o' -o -name '*.a' \\) -exec rm {} \\;", "dangerous", "-exec rm after grouped expr"),
    ("find /proj -exec rm {} +", "dangerous", "bare -exec rm plus"),
    ("find /proj -exec rm -f {} \\;", "dangerous", "-exec rm -f"),
    ("sudo find /proj -name '*.log' -exec rm {} \\;", "dangerous", "sudo-prefixed find -exec rm"),
    # --- find -execdir family ---
    ("find /proj -execdir rm {} \\;", "dangerous", "-execdir rm"),
    ("find /proj -execdir rm -rf {} +", "dangerous", "-execdir rm -rf plus"),
    # --- find -> xargs rm pipelines (the 326-directory incident form) ---
    ("find /proj -type d | xargs rm -rf", "dangerous", "find | xargs rm -rf (incident form)"),
    (r"cd ~/deepseek-harness && find . \( -name node_modules -prune \) -o -type d -name lib -print | wc -l"
     r" && find . \( -name node_modules -prune \) -o -type d -name lib -print0 | xargs -0 rm -rf"
     r" && echo \"=== 清理完成，复查残留 ===\" && find . \( -name node_modules -prune \) -o -type d -name lib -print | wc -l",
     "dangerous", "verbatim 2026-09-26 incident command (86d315)"),
    ("find /proj -print0 | xargs -0 rm -rf", "dangerous", "find -print0 | xargs -0"),
    ("find /proj -type f | xargs rm", "dangerous", "find | xargs rm"),
    ("find /proj | xargs --no-run-if-empty rm -rf", "dangerous", "xargs long flag"),
    ("find /proj | xargs -P 4 rm -rf", "dangerous", "parallel xargs"),
    ("find /proj | xargs rm -r", "dangerous", "xargs rm -r (no -f)"),
    # --- other bulk-delete entry points ---
    ("ls | xargs rm -rf", "dangerous", "ls | xargs rm"),
    ("cat manifest.txt | xargs rm", "dangerous", "cat | xargs rm"),
    ("xargs rm -rf < manifest.txt", "dangerous", "xargs rm with stdin redirect"),
    ("find /proj -exec unlink {} \\;", "dangerous", "-exec unlink (rm synonym)"),
    ("find /proj -execdir unlink {} \\;", "dangerous", "-execdir unlink"),
    ("find /proj -exec sh -c 'rm -rf \"$@\"' _ {} +", "dangerous", "-exec sh -c wrapping rm"),
    ("find /proj -exec /bin/rm {} \\;", "dangerous", "-exec absolute-path rm"),
    # --- baseline sanity (non-find) ---
    ("rm -rf /tmp/build", "dangerous", "plain recursive rm"),
    ("rm -rf /", "dangerous", "hardline floor: root wipe"),
    ("rm -rf /etc", "dangerous", "hardline floor: system dir"),
    # --- benign find usage that must stay clean ---
    ("find /proj -name '*.ts' -type f", "clean", "plain search"),
    ("find /proj -mtime -1 -print", "clean", "recency filter"),
    ("find /proj -name node_modules -prune -o -type f -print", "clean", "prune walk"),
    ("find /proj -name '*.py' | xargs grep -l TODO", "clean", "xargs grep"),
    ("find /proj -name '*.log' | xargs wc -l", "clean", "xargs wc"),
    ("find /proj -exec ls -la {} \\;", "clean", "-exec ls"),
    ("find /proj -exec grep -l foo {} \\;", "clean", "-exec grep"),
    ("find /proj -exec chmod 644 {} \\;", "clean", "-exec chmod non-world-writable"),
    ("find /etc -newer /tmp/marker -print", "clean", "-newer comparison"),
    ("rm file.txt", "clean", "single-file rm"),
    ("echo hello", "clean", "trivial"),
]


def main() -> int:
    quiet = "--quiet" in sys.argv[1:]
    misses = []
    false_positives = []
    for command, expected, note in SAMPLES:
        is_hardline, _hl_desc = detect_hardline_command(command)
        hit, _key, description = detect_dangerous_command(command)
        flagged = is_hardline or hit
        ok = (expected == "dangerous") == flagged
        if ok:
            if not quiet:
                print(f"  ok   [{expected:9s}] {command}")
        elif expected == "dangerous":
            misses.append((command, note))
            print(f"  MISS [dangerous] {command}   ({note})")
        else:
            false_positives.append((command, note))
            print(f"  FP   [clean   ] {command}   ({note})")

    dangerous_n = sum(1 for _, e, _ in SAMPLES if e == "dangerous")
    clean_n = len(SAMPLES) - dangerous_n
    print(f"\nsamples: {len(SAMPLES)} ({dangerous_n} dangerous / {clean_n} clean)")
    print(f"misses (destructive form NOT flagged): {len(misses)}/{dangerous_n}"
          + (f"  -> {' / '.join(n for _, n in misses)}" if misses else ""))
    print(f"false positives (clean flagged): {len(false_positives)}/{clean_n}"
          + (f"  -> {' / '.join(n for _, n in false_positives)}" if false_positives else ""))
    return 1 if misses else 0


if __name__ == "__main__":
    sys.exit(main())

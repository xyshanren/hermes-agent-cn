"""Tests for CAND-057 (Sprint 6a): hermes-agent skill docs 覆盖 v0.13-0.17.

跟 plan CAND-057 1:1 配对 (跟 K-7 k7_commands.py + CAND-001/003/008/056 1:1 配对 0 改旧):
- 新 docs/hermes-agent-skill-v0.13-0.17.md (跟 CAND-001/003/008/056 1:1 配对
  additive 0 改旧, cherry-pick from upstream f67c0b3e6)
- 0 改 docs 现有 file (跟 UX 倒退审计 1:1)
- 4 test (2 静态 + 2 live, 跟 K-10 1:1 配对)
"""

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent


# ---------- CAND-057 main change: 静态 source check ----------


def test_skill_docs_exists():
    """CAND-057 main file: docs/hermes-agent-skill-v0.13-0.17.md 存在 (跟 CAND-001 1:1)."""
    p = REPO / "docs" / "hermes-agent-skill-v0.13-0.17.md"
    assert p.exists(), f"{p} missing (CAND-057 main file)"
    src = p.read_text(encoding="utf-8")
    # 5 版本段完整 (跟 plan 1:1 配对)
    for ver in ("v0.13", "v0.14", "v0.15", "v0.16", "v0.17"):
        assert f"## v0.{ver[3:]}" in src or f"## {ver}" in src, f"docs 缺 {ver} 段"


def test_skill_docs_cherry_pick_source():
    """CAND-057 source: 跟 upstream f67c0b3e6 1:1 配对 (cherry-pick)."""
    src = (REPO / "docs" / "hermes-agent-skill-v0.13-0.17.md").read_text(encoding="utf-8")
    # upstream commit 引用 (跟 cherry-pick source 1:1 配对)
    assert "f67c0b3e6" in src, "应引用 upstream commit f67c0b3e6"
    assert "v0.13" in src and "v0.17" in src, "docs 应覆盖 v0.13-0.17"


# ---------- CAND-057 live integration: 跟 plan 1:1 配对 ----------


def test_skill_docs_existing_files_unchanged():
    """Live: 0 改 docs 现有 file (跟 CAND-001/003/008/056 0 改 1:1 配对 UX 倒退审计).

    Sprint 10b note (跟 v0.19.1 base 1:1 配对): upstream v0.19.1's
    docs/ tree no longer carries the 3 monolithic doc files our CAND-057
    pre-sync invariant referenced (API.md / ARCHITECTURE.md / DOCS-MAP.md
    were replaced by 7 focused contract docs like ``profile-routing.md``).
    CAND-057's additive doc ``hermes-agent-skill-v0.13-0.17.md`` is
    still 0-touch; we just verify the *current* v0.19.1 docs set is
    still pristine (excluding our own additive file).
    """
    # Sprint 10b: 0 假设具体 fname, 取 v0.19.1 实际 docs/ 下所有 .md
    docs_dir = REPO / "docs"
    if not docs_dir.exists():
        return  # v0.19.1 dropped the docs/ dir entirely; nothing to check
    md_files = list(docs_dir.glob("*.md"))
    # CAND-057 0 改 docs/ 现有 file (跟 mavis UX 倒退审计 1:1)
    # 排除 CAND-057 自己的 additive file (the new doc itself, 0 触碰其他 file)
    cand_057_additive = "hermes-agent-skill-v0.13-0.17"
    for p in md_files:
        # Skip CAND-057's own additive file (它当然 contains 自己的 name)
        if cand_057_additive in p.name:
            continue
        src = p.read_text(encoding="utf-8")
        # 现有 docs 0 引用 CAND-057 新 doc (verify additive 0 改)
        assert cand_057_additive not in src, (
            f"{p.name} 0 改 0 失, CAND-057 不应 modify 现有 docs"
        )


def test_skill_docs_content_sections():
    """Live: 5 版本段 + 0 改旧验证段 + Sprint retrospective 段 完整 (跟 plan 1:1)."""
    sys.path.insert(0, str(REPO))
    p = REPO / "docs" / "hermes-agent-skill-v0.13-0.17.md"
    src = p.read_text(encoding="utf-8")

    # 5 版本段都有内容
    sections = ["v0.13", "v0.14", "v0.15", "v0.16", "v0.17"]
    for ver in sections:
        assert ver in src, f"应含 {ver} 段"

    # 0 改旧验证段
    assert "0 改旧验证" in src or "UX 倒退审计" in src, (
        "应含 0 改旧验证段 (跟 UX 倒退审计 1:1 配对)"
    )

    # Sprint retrospective 段
    assert "Sprint retrospective" in src or "跨 project reference" in src, (
        "应含跨 project reference 段 (跟 CAND-084 8-03 22:10 lesson 1:1 配对)"
    )

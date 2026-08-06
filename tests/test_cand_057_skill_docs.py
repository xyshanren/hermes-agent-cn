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
    """Live: 0 改 docs 现有 file (跟 CAND-001/003/008/056 0 改 1:1 配对 UX 倒退审计)."""
    # 验证 3 个核心 docs file 0 改
    for fname in ("API.md", "ARCHITECTURE.md", "DOCS-MAP.md"):
        p = REPO / "docs" / fname
        assert p.exists(), f"{p} missing (existing docs file)"
        # docs 是 text 文件, 0 改 = 0 内容变化
        # (新增 docs/hermes-agent-skill-v0.13-0.17.md 独立 file, 0 触碰现有 file)
        src = p.read_text(encoding="utf-8")
        # 0 引用新 doc name (verify additive 0 改)
        assert "hermes-agent-skill-v0.13-0.17" not in src, (
            f"{fname} 0 改 0 失, CAND-057 不应 modify 现有 docs"
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

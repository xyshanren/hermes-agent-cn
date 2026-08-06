"""Tests for CAND-044 (Sprint 7 Wave 2): Journey 学习时间线."""

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent


def test_journey_timeline_module_exists():
    p = REPO / "hermes_cli" / "journey_timeline.py"
    assert p.exists()
    src = p.read_text(encoding="utf-8")
    for fn in ("journey_timeline_build", "journey_timeline_render",
               "journey_timeline_aggregate", "apply_journey_timeline"):
        assert f"def {fn}" in src


def test_journey_timeline_does_not_modify_memory():
    cli_src = (REPO / "cli.py").read_text(encoding="utf-8")
    assert "journey_timeline" not in cli_src


def test_cand_044_1_journey_timeline_build_live():
    sys.path.insert(0, str(REPO))
    from hermes_cli.journey_timeline import journey_timeline_build
    nodes = [
        {"id": "1", "timestamp": "2026-08-05T10:00:00", "topic": "a"},
        {"id": "2", "timestamp": "2026-08-03T08:00:00", "topic": "b"},
        {"id": "3", "timestamp": "2026-08-07T12:00:00", "topic": "c"},
    ]
    result = journey_timeline_build(nodes)
    assert result["node_count"] == 3
    # 排序 by timestamp 升序
    assert result["nodes"][0]["id"] == "2"
    assert result["nodes"][1]["id"] == "1"
    assert result["nodes"][2]["id"] == "3"


def test_cand_044_2_journey_timeline_render_live():
    sys.path.insert(0, str(REPO))
    from hermes_cli.journey_timeline import journey_timeline_render
    timeline = {"node_count": 5}
    # tui viewport
    result = journey_timeline_render(timeline, viewport="tui")
    assert result["viewport"] == "tui"
    assert result["node_count"] == 5
    assert result["rendered"] is True


def test_cand_044_3_journey_timeline_aggregate_live():
    sys.path.insert(0, str(REPO))
    from hermes_cli.journey_timeline import journey_timeline_aggregate
    timeline = {
        "nodes": [
            {"timestamp": "2026-08-05T10:00:00"},
            {"timestamp": "2026-08-05T14:00:00"},
            {"timestamp": "2026-08-06T09:00:00"},
            {"timestamp": "2026-08-07T11:00:00"},
        ]
    }
    # day 聚合 → 3 groups
    result = journey_timeline_aggregate(timeline, group_by="day")
    assert result["group_by"] == "day"
    assert result["total_groups"] == 3
    assert result["groups"]["2026-08-05"] == 2
    assert result["groups"]["2026-08-06"] == 1
    # month 聚合 → 1 group
    result_month = journey_timeline_aggregate(timeline, group_by="month")
    assert result_month["total_groups"] == 1


def test_apply_journey_timeline_combined_entry_live():
    sys.path.insert(0, str(REPO))
    from hermes_cli.journey_timeline import apply_journey_timeline
    nodes = [
        {"id": "1", "timestamp": "2026-08-05T10:00:00"},
        {"id": "2", "timestamp": "2026-08-06T11:00:00"},
    ]
    result = apply_journey_timeline(nodes, viewport="tui", group_by="day")
    assert isinstance(result, dict)
    assert set(result.keys()) == {"build", "render", "aggregate"}
    assert result["build"]["node_count"] == 2
    assert result["render"]["viewport"] == "tui"
    assert result["aggregate"]["total_groups"] == 2

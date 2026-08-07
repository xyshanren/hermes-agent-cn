"""Tests for CAND-058 (Sprint 8): TTFT round 2 UX bridge to hermes-tray."""

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent


def test_ttft_tray_bridge_module_exists():
    p = REPO / "hermes_cli" / "ttft_tray_bridge.py"
    assert p.exists()
    src = p.read_text(encoding="utf-8")
    for fn in ("ttft_tray_bridge_endpoint", "ttft_tray_bridge_serialize",
               "ttft_tray_bridge_dispatch", "apply_ttft_tray_bridge"):
        assert f"def {fn}" in src


def test_ttft_tray_bridge_does_not_modify_ttft_cache():
    cli_src = (REPO / "cli.py").read_text(encoding="utf-8")
    assert "ttft_tray_bridge" not in cli_src


def test_cand_058_1_ttft_tray_bridge_endpoint_live():
    sys.path.insert(0, str(REPO))
    from hermes_cli.ttft_tray_bridge import ttft_tray_bridge_endpoint
    result = ttft_tray_bridge_endpoint()
    assert result["endpoint"] == "/v1/tray/ttft_stream"
    assert result["method"] == "GET"
    assert result["content_type"] == "text/event-stream"


def test_cand_058_2_ttft_tray_bridge_serialize_live():
    sys.path.insert(0, str(REPO))
    from hermes_cli.ttft_tray_bridge import ttft_tray_bridge_serialize
    # partial line
    result = ttft_tray_bridge_serialize("hello", partial=True)
    assert result["data"] == "hello"
    assert result["partial"] is True
    assert result["reasoning"] is False
    # full line
    result_full = ttft_tray_bridge_serialize("world", partial=False)
    assert result_full["partial"] is False


def test_cand_058_3_ttft_tray_bridge_dispatch_live():
    sys.path.insert(0, str(REPO))
    from hermes_cli.ttft_tray_bridge import ttft_tray_bridge_dispatch
    events = [
        {"data": "a", "partial": True},
        {"data": "b", "partial": True},
        {"data": "c", "partial": False},
    ]
    result = ttft_tray_bridge_dispatch(events)
    assert result["dispatched_count"] == 3
    assert result["status"] == "dispatched"


def test_apply_ttft_tray_bridge_combined_entry_live():
    sys.path.insert(0, str(REPO))
    from hermes_cli.ttft_tray_bridge import apply_ttft_tray_bridge
    result = apply_ttft_tray_bridge(line="hello world", partial=True)
    assert isinstance(result, dict)
    assert set(result.keys()) == {"endpoint", "serialize", "dispatch"}
    assert result["endpoint"]["endpoint"] == "/v1/tray/ttft_stream"
    assert result["serialize"]["data"] == "hello world"
    assert result["dispatch"]["dispatched_count"] == 1

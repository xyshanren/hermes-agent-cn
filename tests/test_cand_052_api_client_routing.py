"""Tests for CAND-052 (Sprint 7 Wave 2): API server per-client model routing."""

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent


def test_api_client_routing_module_exists():
    p = REPO / "hermes_cli" / "api_client_routing.py"
    assert p.exists()
    src = p.read_text(encoding="utf-8")
    for fn in ("api_client_model_routes_register", "api_client_extra_http_headers",
               "api_client_route_resolve", "apply_api_client_routing"):
        assert f"def {fn}" in src


def test_api_client_routing_does_not_modify_api_server():
    cli_src = (REPO / "cli.py").read_text(encoding="utf-8")
    assert "api_client_routing" not in cli_src


def test_cand_052_1_api_client_model_routes_register_live():
    sys.path.insert(0, str(REPO))
    from hermes_cli.api_client_routing import api_client_model_routes_register
    result = api_client_model_routes_register("client-1", "deepseek-v3")
    assert result["client_id"] == "client-1"
    assert result["model"] == "deepseek-v3"
    assert result["registered"] is True


def test_cand_052_2_api_client_extra_http_headers_live():
    sys.path.insert(0, str(REPO))
    from hermes_cli.api_client_routing import api_client_extra_http_headers
    # custom headers
    result = api_client_extra_http_headers({"X-Custom": "value"})
    assert result == {"X-Custom": "value"}
    # 0 headers → empty dict
    result_empty = api_client_extra_http_headers()
    assert result_empty == {}


def test_cand_052_3_api_client_route_resolve_live():
    sys.path.insert(0, str(REPO))
    from hermes_cli.api_client_routing import api_client_route_resolve
    routes = {"client-1": "deepseek-v3", "client-2": "qwen-max"}
    # client-1 配 → 用 deepseek-v3
    result = api_client_route_resolve("client-1", routes, default_model="default")
    assert result["model"] == "deepseek-v3"
    assert result["is_override"] is True
    # client-3 0 配 → 用 default
    result_default = api_client_route_resolve("client-3", routes, default_model="default")
    assert result_default["model"] == "default"
    assert result_default["is_override"] is False


def test_apply_api_client_routing_combined_entry_live():
    sys.path.insert(0, str(REPO))
    from hermes_cli.api_client_routing import apply_api_client_routing
    routes = {"client-1": "deepseek-v3"}
    headers = {"X-Trace-Id": "abc-123"}
    result = apply_api_client_routing(
        client_id="client-1",
        model_routes=routes,
        extra_headers=headers,
        default_model="default",
    )
    assert isinstance(result, dict)
    assert set(result.keys()) == {"register", "extra_headers", "resolve"}
    assert result["register"]["model"] == "deepseek-v3"
    assert result["extra_headers"] == {"X-Trace-Id": "abc-123"}
    assert result["resolve"]["is_override"] is True

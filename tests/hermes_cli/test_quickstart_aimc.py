"""quickstart AIMC 一等公民化（CAND-085 复活 + Ollama 网关探测 + 兜底链）测试。

Covers (all mocked, no real network, no real quickstart run):

  A1  _parse_default_gateway — /proc/net/route 纯解析
  A2  _probe_gateway_url — 协议/元数据守卫（不发请求）
  A3  _detect_aimc — 候选顺序 + 组列表抓取
  A4  _configure_aimc — providers.aimc + aimc.enabled + model dict
  A5  _generate_routing_rules — AIMC 主力：reasoning_model 生效、视觉规则不跨 provider
  A6  _write_smart_routing — AIMC 主力写 tier:strong 规则 + 悬挂检查跳过
      内联 base_url / embedded 内置
  A7  _build_fallback_chain — OCR 排除、非视觉优先、有 Ollama 兜底时不叠 embedded
  A8  main._initialize_aimc_client_or_fail — dict 形态 model.default 现在能
      触发 fail-fast refresh（旧代码 str 类型判断永远 False，死代码）

Run:
    scripts/run_tests.sh tests/hermes_cli/test_quickstart_aimc.py -q
"""

import asyncio
from unittest.mock import patch

import pytest


# ---------------------------------------------------------------------------
# A1 — _parse_default_gateway
# ---------------------------------------------------------------------------

_ROUTE_TABLE = """Iface   Destination Gateway     Flags RefCnt Use Metric Mask
eth0    00000000    01401CAC    0000  0      0   0      0000
eth0    AC1C4000    00000000    0003  0      0   0      FFFC
"""


def test_parse_default_gateway_extracts_little_endian_hex():
    from hermes_cli.quickstart import _parse_default_gateway

    # /proc/net/route 以小端内存字节序显示 u32：172.28.64.1 → 0xAC1C4001
    # → 内存字节 01 40 1C AC → 显示"01401CAC"。WSL vNIC 网关典型值。
    assert _parse_default_gateway(_ROUTE_TABLE) == "172.28.64.1"


def test_parse_default_gateway_returns_none_without_default_route():
    from hermes_cli.quickstart import _parse_default_gateway

    assert _parse_default_gateway("") is None
    assert _parse_default_gateway(
        "Iface Destination Gateway Flags\neth0 AC1C4000 00000000 0003\n"
    ) is None


def test_parse_default_gateway_skips_loopback_gateway():
    from hermes_cli.quickstart import _parse_default_gateway

    text = (
        "Iface Destination Gateway Flags RefCnt Use Metric Mask\n"
        "lo    00000000    0100007F 0000  0 0 0 0000\n"
    )
    assert _parse_default_gateway(text) is None


# ---------------------------------------------------------------------------
# A2 — _probe_gateway_url guards (no request issued for bad input)
# ---------------------------------------------------------------------------

def test_probe_gateway_url_rejects_non_http_schemes():
    from hermes_cli.quickstart import _probe_gateway_url

    assert _probe_gateway_url("ftp://127.0.0.1:8080/health") is False
    assert _probe_gateway_url("file:///etc/passwd") is False


def test_probe_gateway_url_rejects_cloud_metadata_endpoints():
    from hermes_cli.quickstart import _probe_gateway_url

    assert _probe_gateway_url("http://169.254.169.254/latest/meta-data") is False
    assert _probe_gateway_url("http://metadata.google.internal/computeMetadata") is False


def test_probe_gateway_url_accepts_loopback_target_and_fails_closed():
    from hermes_cli.quickstart import _probe_gateway_url

    # 无服务监听的端口 → 连接失败 → False（允许 loopback 是设计目标）
    assert _probe_gateway_url("http://127.0.0.1:1/health", timeout=0.5) is False


# ---------------------------------------------------------------------------
# A3 — _detect_aimc
# ---------------------------------------------------------------------------

def test_detect_aimc_prefers_env_then_default_and_fetches_groups(monkeypatch, tmp_path):
    from hermes_cli import quickstart

    monkeypatch.delenv("AIMC_BASE_URL", raising=False)
    monkeypatch.setenv("AIMC_API_KEY", "test-key-not-real")

    health_hits: list[str] = []

    def fake_probe(url, timeout=2.0):
        health_hits.append(url)
        return "8080" in url

    def fake_fetch(url, headers=None, timeout=3.0):
        assert headers and "Bearer" in headers.get("Authorization", "")
        return {
            "data": [],
            "data_groups": [
                {"id": "tier:strong", "member_count": 2},
                {"id": "tier:balanced", "member_count": 3},
            ],
        }

    monkeypatch.setattr(quickstart, "_probe_gateway_url", fake_probe)
    monkeypatch.setattr(quickstart, "_fetch_gateway_json", fake_fetch)

    info = quickstart._detect_aimc()

    assert info is not None
    # 先试 env（未设）→ config（空）→ 默认 127.0.0.1:8080；/health 挂在
    # origin 根上（不带 /v1）
    assert health_hits[0] == "http://127.0.0.1:8080/health"
    assert info["base_url"] == "http://127.0.0.1:8080/v1"  # 规范化为 OpenAI 端点
    assert info["groups"] == {"tier:strong", "tier:balanced"}


def test_detect_aimc_returns_none_when_no_candidate_answers(monkeypatch):
    from hermes_cli import quickstart

    monkeypatch.delenv("AIMC_BASE_URL", raising=False)
    monkeypatch.delenv("AIMC_API_KEY", raising=False)
    monkeypatch.setattr(quickstart, "_probe_gateway_url", lambda url, timeout=2.0: False)

    assert quickstart._detect_aimc() is None


def test_detect_aimc_env_candidate_tried_before_default(monkeypatch):
    from hermes_cli import quickstart

    monkeypatch.setenv("AIMC_BASE_URL", "http://192.168.8.9:9000")
    monkeypatch.delenv("AIMC_API_KEY", raising=False)
    hits: list[str] = []

    def fake_probe(url, timeout=2.0):
        hits.append(url)
        return "9000" in url

    monkeypatch.setattr(quickstart, "_probe_gateway_url", fake_probe)

    info = quickstart._detect_aimc()

    assert hits[0] == "http://192.168.8.9:9000/health"
    assert info["base_url"] == "http://192.168.8.9:9000/v1"


def test_detect_aimc_env_with_v1_suffix_probed_at_origin(monkeypatch):
    """带 /v1 后缀的候选（.env 实况形态）必须在 origin 根上探 /health，
    否则 /v1/health 404 会把活跃网关误跳过。"""
    from hermes_cli import quickstart

    monkeypatch.setenv("AIMC_BASE_URL", "http://127.0.0.1:8080/v1")
    monkeypatch.delenv("AIMC_API_KEY", raising=False)
    hits: list[str] = []

    def fake_probe(url, timeout=2.0):
        hits.append(url)
        return url.endswith("/health") and "8080" in url

    monkeypatch.setattr(quickstart, "_probe_gateway_url", fake_probe)

    info = quickstart._detect_aimc()

    assert hits[0] == "http://127.0.0.1:8080/health"
    assert info["base_url"] == "http://127.0.0.1:8080/v1"


# ---------------------------------------------------------------------------
# A3b — 网关请求守卫（协议/元数据）
# ---------------------------------------------------------------------------

def test_gateway_url_ok_rejects_non_http_and_metadata():
    from hermes_cli.quickstart import _gateway_url_ok

    assert _gateway_url_ok("http://127.0.0.1:8080/health") is True
    assert _gateway_url_ok("https://aimc.example.internal/v1/models") is True
    assert _gateway_url_ok("ftp://127.0.0.1/health") is False
    assert _gateway_url_ok("file:///etc/passwd") is False
    assert _gateway_url_ok("http://169.254.169.254/latest/meta-data") is False
    assert _gateway_url_ok("http://metadata.google.internal/computeMetadata") is False


def test_fetch_gateway_json_rejects_bad_scheme_and_metadata():
    from hermes_cli.quickstart import _fetch_gateway_json

    assert _fetch_gateway_json("ftp://127.0.0.1/x", {}) is None
    assert _fetch_gateway_json("http://169.254.169.254/x", {}) is None


# ---------------------------------------------------------------------------
# A4 — _configure_aimc
# ---------------------------------------------------------------------------

@pytest.fixture
def hermes_home(tmp_path, monkeypatch):
    home = tmp_path / ".hermes"
    home.mkdir()
    monkeypatch.setenv("HERMES_HOME", str(home))
    return home


def _write_config(home, cfg):
    import yaml

    (home / "config.yaml").write_text(yaml.safe_dump(cfg), encoding="utf-8")


def _read_config(home):
    import yaml

    return yaml.safe_load((home / "config.yaml").read_text(encoding="utf-8"))


def test_configure_aimc_writes_provider_section_enabled_flag_and_model(hermes_home):
    from hermes_cli import quickstart

    assert quickstart._configure_aimc(
        {"available": True, "base_url": "http://127.0.0.1:8080", "groups": set()}
    )

    cfg = _read_config(hermes_home)
    assert cfg["providers"]["aimc"]["base_url"] == "http://127.0.0.1:8080/v1"
    # 密钥不落明文 — 引用 .env
    assert cfg["providers"]["aimc"]["api_key"] == "${AIMC_API_KEY}"
    assert cfg["aimc"]["enabled"] is True
    assert cfg["model"]["default"] == "tier:balanced"
    assert cfg["model"]["provider"] == "aimc"


def test_configure_aimc_preserves_existing_keys_and_inline_url_suffix(hermes_home):
    from hermes_cli import quickstart

    _write_config(hermes_home, {
        "providers": {
            "aimc": {"base_url": "http://127.0.0.1:8080/v1", "api_key": "sk-existing"}
        },
        "aimc": {"enabled": False, "note": "keep"},
    })

    assert quickstart._configure_aimc(
        {"available": True, "base_url": "http://127.0.0.1:8080", "groups": set()}
    )

    cfg = _read_config(hermes_home)
    entry = cfg["providers"]["aimc"]
    assert entry["base_url"].endswith("/v1")          # 不重复追加 /v1
    assert entry["api_key"] == "sk-existing"          # 已有 key 不覆盖
    assert cfg["aimc"] == {"enabled": True, "note": "keep"}


def test_configure_aimc_preserves_operator_chosen_aimc_default(hermes_home):
    """操作员已选 AIMC 组主力（tier:strong）时，重跑 quickstart 不得
    硬编码回 tier:balanced。"""
    from hermes_cli import quickstart

    _write_config(hermes_home, {
        "model": {"default": "tier:strong", "provider": "aimc"},
    })

    assert quickstart._configure_aimc(
        {"available": True, "base_url": "http://127.0.0.1:8080", "groups": set()}
    )

    cfg = _read_config(hermes_home)
    assert cfg["model"]["default"] == "tier:strong"
    assert cfg["model"]["provider"] == "aimc"


def test_resolve_aimc_default_preserves_group_else_tier_balanced():
    from hermes_cli import quickstart

    assert quickstart._resolve_aimc_default(
        {"model": {"default": "tier:strong"}}
    ) == "tier:strong"
    assert quickstart._resolve_aimc_default(
        {"model": {"default": "scene:code"}}
    ) == "scene:code"
    assert quickstart._resolve_aimc_default(
        {"model": {"default": "qwen-0.5b"}}
    ) == "tier:balanced"
    assert quickstart._resolve_aimc_default({}) == "tier:balanced"


# ---------------------------------------------------------------------------
# A5 — _generate_routing_rules（AIMC 主力）
# ---------------------------------------------------------------------------

def test_aimc_primary_reasoning_rule_uses_reasoning_model():
    from hermes_cli import quickstart

    rules = quickstart._generate_routing_rules(
        api_providers=[],
        local_backends=[],
        primary_provider="aimc",
        primary_model="tier:balanced",
        ollama_info={
            "classified_models": [{"name": "qwen3-vl:2b", "type": "vision"}],
            "vision_model": "qwen3-vl:2b",
        },
        reasoning_model="tier:strong",
    )

    names = [r["name"] for r in rules]
    assert names[-1] == "default"
    reasoning = next(r for r in rules if r["name"] == "reasoning")
    assert reasoning["model"] == "tier:strong"
    assert reasoning["match"]["keywords"] == ["分析", "推理", "思考", "证明"]
    default_rule = next(r for r in rules if r["name"] == "default")
    assert default_rule["model"] == "tier:balanced"

    # 跨 provider 视觉规则不得出现：Ollama 视觉模型挂在 aimc 主力下无效
    assert "vision" not in names, (
        f"AIMC primary must not emit cross-provider vision rules, got {names!r}"
    )


def test_aimc_primary_without_reasoning_model_falls_back_to_primary():
    from hermes_cli import quickstart

    rules = quickstart._generate_routing_rules(
        api_providers=[],
        local_backends=[],
        primary_provider="aimc",
        primary_model="tier:balanced",
    )
    reasoning = next(r for r in rules if r["name"] == "reasoning")
    assert reasoning["model"] == "tier:balanced"


def test_non_aimc_primary_still_emits_ollama_vision_rule():
    from hermes_cli import quickstart

    rules = quickstart._generate_routing_rules(
        api_providers=[],
        local_backends=[],
        primary_provider="ollama",
        primary_model="minicpm5:2b",
        ollama_info={
            "classified_models": [{"name": "qwen3-vl:2b", "type": "vision"}],
            "vision_model": "qwen3-vl:2b",
        },
    )
    vision = next((r for r in rules if r["name"] == "vision"), None)
    assert vision is not None and vision["model"] == "qwen3-vl:2b"


# ---------------------------------------------------------------------------
# A6 — _write_smart_routing（AIMC 主力 + 悬挂检查）
# ---------------------------------------------------------------------------

def test_write_smart_routing_aimc_writes_strong_rule_and_no_dangling_warning(
    hermes_home, capsys
):
    from hermes_cli import quickstart

    ok = quickstart._write_smart_routing(
        "aimc",
        "tier:balanced",
        fallback_chain=[
            {
                "provider": "ollama",
                "model": "minicpm5:2b",
                "base_url": "http://172.28.64.1:11434/v1",
            }
        ],
        api_providers=[],
        ollama_info={"models": ["minicpm5:2b"], "classified_models": []},
        aimc_info={"available": True, "base_url": "http://127.0.0.1:8080", "groups": set()},
    )
    assert ok

    out = capsys.readouterr().out
    # 自描述（inline base_url）条目不得触发 CAND-083 悬挂警告
    assert "未定义的" not in out

    cfg = _read_config(hermes_home)
    rules = {r["name"]: r for r in cfg["model_routing"]["rules"]}
    assert rules["reasoning"]["model"] == "tier:strong"
    assert rules["default"]["model"] == "tier:balanced"
    assert cfg["model_routing"]["reasoning"]["model"] == "tier:strong"  # legacy 键同步
    assert cfg["fallback_model"][0]["provider"] == "ollama"
    assert cfg["fallback_model"][0]["base_url"] == "http://172.28.64.1:11434/v1"


def test_write_smart_routing_embedded_fallback_not_flagged_dangling(
    hermes_home, capsys
):
    from hermes_cli import quickstart

    ok = quickstart._write_smart_routing(
        "aimc",
        "tier:balanced",
        fallback_chain=[{"provider": "embedded", "model": "minicpm5-1b"}],
        api_providers=[],
        aimc_info={"available": True, "base_url": "http://127.0.0.1:8080", "groups": set()},
    )
    assert ok

    out = capsys.readouterr().out
    # embedded 是内置离线层，无需 providers 段 — 不算悬挂
    assert "未定义的" not in out


def test_write_smart_routing_still_warns_on_genuinely_dangling_entry(
    hermes_home, capsys
):
    from hermes_cli import quickstart

    quickstart._write_smart_routing(
        "aimc",
        "tier:balanced",
        fallback_chain=[{"provider": "no-such-provider", "model": "m"}],
        api_providers=[],
        aimc_info={"available": True, "base_url": "http://127.0.0.1:8080", "groups": set()},
    )

    out = capsys.readouterr().out
    assert "未定义的" in out
    assert "no-such-provider" in out


# ---------------------------------------------------------------------------
# A7 — _build_fallback_chain
# ---------------------------------------------------------------------------

def test_fallback_chain_prefers_chat_model_and_skips_embedded_when_ollama(
    monkeypatch,
):
    from hermes_cli import quickstart

    monkeypatch.setattr(
        quickstart, "_get_ollama_base_url",
        lambda: "http://172.28.64.1:11434/v1",
    )

    chain = quickstart._build_fallback_chain(
        api_providers=[],
        ollama_info={
            "models": ["bge-m3", "paddleocr-vl:1.6", "glm-ocr", "qwen3-vl:2b", "minicpm5:2b"],
        },
        has_embedded=True,
        primary_provider_id="aimc",
    )

    providers = [e["provider"] for e in chain]
    assert providers == ["ollama"], f"embedded 必须让位给 Ollama 兜底, got {providers!r}"
    entry = chain[0]
    # OCR / embedding / vision 都不选，minicpm5:2b 是唯一通用对话模型
    assert entry["model"] == "minicpm5:2b"
    assert entry["base_url"] == "http://172.28.64.1:11434/v1"


def test_fallback_chain_keeps_embedded_when_no_ollama(monkeypatch):
    from hermes_cli import quickstart

    monkeypatch.setattr(
        "hermes_cli.model_manager.get_available_embedded_model",
        lambda: "minicpm5-1b",
    )

    chain = quickstart._build_fallback_chain(
        api_providers=[],
        ollama_info=None,
        has_embedded=True,
        primary_provider_id="aimc",
    )

    assert chain == [{"provider": "embedded", "model": "minicpm5-1b"}]


def test_fallback_chain_aimc_as_cloud_fallback_when_not_primary():
    from hermes_cli import quickstart

    chain = quickstart._build_fallback_chain(
        api_providers=[{"id": "aimc", "default_model": "tier:balanced"}],
        ollama_info=None,
        has_embedded=False,
        primary_provider_id="ollama",
    )

    assert chain == [{"provider": "aimc", "model": "tier:balanced"}]


# ---------------------------------------------------------------------------
# A8 — main.py 门检：dict 形态 model.default 现在触发 fail-fast
# ---------------------------------------------------------------------------

def _install_stub_aimc_client(monkeypatch, calls):
    import sys
    import types

    stub_module = types.ModuleType("aimc_client")

    class _StubClient:
        def __init__(self, base_url="", api_key="", timeout=0.0, client=None):
            calls.append({"base_url": base_url, "api_key": api_key})

        async def refresh(self):
            calls.append("refreshed")
            # 记录运行中的事件循环 —— 门检必须在同一个循环里完成
            # refresh + aclose（两个 asyncio.run 会把绑定在第一个循环上
            # 的 httpx 客户端关在第二个循环里 → "Event loop is closed"）。
            calls.append(("loop", id(asyncio.get_running_loop())))

        async def aclose(self):
            calls.append(("loop", id(asyncio.get_running_loop())))

    stub_module.AIMCClient = _StubClient
    monkeypatch.setitem(sys.modules, "aimc_client", stub_module)
    return _StubClient


def test_gate_activates_fail_fast_for_dict_model_default(hermes_home, monkeypatch):
    """旧代码 isinstance(model, str) 恒 False → CAND-085 fail-fast 死代码；
    修复后 dict 形态 model.default=tier:* 必须触发 refresh。"""
    _write_config(hermes_home, {
        "model": {"default": "tier:balanced", "provider": "aimc"},
        "providers": {"aimc": {"base_url": "http://127.0.0.1:8080/v1"}},
        "aimc": {"enabled": True},
    })

    calls: list = []
    _install_stub_aimc_client(monkeypatch, calls)

    from hermes_cli.main import _initialize_aimc_client_or_fail

    _initialize_aimc_client_or_fail()  # 不抛 = refresh 走通
    assert calls[0]["base_url"] == "http://127.0.0.1:8080/v1"
    assert "refreshed" in calls
    # refresh 与 aclose 必须跑在同一个事件循环上
    loops = [c for c in calls if isinstance(c, tuple) and c[0] == "loop"]
    assert len(loops) == 2 and loops[0][1] == loops[1][1], (
        f"refresh/aclose ran on different event loops: {loops!r} "
        f"(double asyncio.run breaks httpx teardown)"
    )


def test_gate_skips_when_main_model_is_not_aimc_group(hermes_home, monkeypatch):
    _write_config(hermes_home, {
        "model": {"default": "qwen-0.5b", "provider": "embedded"},
        "providers": {"aimc": {"base_url": "http://127.0.0.1:8080/v1"}},
        "aimc": {"enabled": True},
    })

    calls: list = []
    _install_stub_aimc_client(monkeypatch, calls)

    from hermes_cli.main import _initialize_aimc_client_or_fail

    _initialize_aimc_client_or_fail()
    assert calls == [], "非 AIMC 组主力不应触发 refresh"


def test_gate_raises_when_refresh_fails(hermes_home, monkeypatch):
    import sys
    import types

    _write_config(hermes_home, {
        "model": {"default": "tier:balanced", "provider": "aimc"},
        "providers": {"aimc": {"base_url": "http://127.0.0.1:8080/v1"}},
        "aimc": {"enabled": True},
    })

    stub_module = types.ModuleType("aimc_client")

    class _FailingClient:
        def __init__(self, *a, **k):
            pass

        async def refresh(self):
            raise RuntimeError("AIMC refresh failed: simulated")

        async def aclose(self):
            pass

    stub_module.AIMCClient = _FailingClient
    monkeypatch.setitem(sys.modules, "aimc_client", stub_module)

    from hermes_cli.main import _initialize_aimc_client_or_fail

    with pytest.raises(RuntimeError, match="AIMC refresh failed"):
        _initialize_aimc_client_or_fail()


# asyncio.run 在 Windows 上需要的事件循环策略由 conftest 处理；这里显式
# 防御 collection 期无策略的环境。
def test_asyncio_gate_helper_runs_coroutine():
    async def _coro():
        return 42

    assert asyncio.run(_coro()) == 42

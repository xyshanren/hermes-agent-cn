"""P2 (K-71): ModelScope 下载源 —— download_source 配置 + resolve URL fallback 链。

Covers:
  M1  _ms_url —— ModelScope resolve URL 格式（与 HF 同构，host 硬编码公网域）
  M2  _download_source —— 默认 modelscope；配置 huggingface/auto；非法值回落
  M3  _asset_urls —— 三种 source 的 (primary, fallbacks)：
      huggingface → (hf, ()), modelscope → (ms_master, (ms_main,)),
      auto → (ms_master, (ms_main, hf))；modelscope_repo / modelscope_revision
      覆盖；companion repo 走 fallback_repo
  M4  _download_plan —— plan 行首元素为 (primary, fallbacks) 对

Run:
    scripts/run_tests.sh tests/hermes_cli/test_local_download_source.py -q
"""

from types import SimpleNamespace

import pytest


def _patch_source(monkeypatch, source):
    from hermes_cli import config

    monkeypatch.setattr(
        config, "load_config_readonly",
        lambda: {"local_runtime": {"download_source": source}},
    )


def _entry(**over):
    base = dict(repo="org/model", modelscope_repo="", modelscope_revision="",
                mmproj=None, draft=None, mtp_head=None, variants=())
    base.update(over)
    return SimpleNamespace(**base)


def _asset(**over):
    base = dict(repo=None, path="model-Q4_K_M.gguf", revision="f737bcabc",
                local_name="model-Q4_K_M.gguf", size_bytes=0)
    base.update(over)
    return SimpleNamespace(**base)


# ---------------------------------------------------------------------------
# M1 — _ms_url
# ---------------------------------------------------------------------------

def test_ms_url_has_hf_shape_with_modelscope_host():
    from hermes_cli.web_routers.local_models import _ms_url

    url = _ms_url("org/model", "model-Q4_K_M.gguf", "master")
    assert url == "https://www.modelscope.cn/models/org/model/resolve/master/model-Q4_K_M.gguf"


# ---------------------------------------------------------------------------
# M2 — _download_source
# ---------------------------------------------------------------------------

def test_download_source_defaults_to_modelscope(monkeypatch):
    from hermes_cli.web_routers.local_models import _download_source

    _patch_source(monkeypatch, "")
    assert _download_source() == "modelscope"


@pytest.mark.parametrize("source", ["huggingface", "auto", "modelscope"])
def test_download_source_reads_config(monkeypatch, source):
    from hermes_cli.web_routers.local_models import _download_source

    _patch_source(monkeypatch, source)
    assert _download_source() == source


@pytest.mark.parametrize("source", ["huggingface", "auto", "modelscope"])
def test_download_source_case_insensitive(monkeypatch, source):
    from hermes_cli.web_routers.local_models import _download_source

    _patch_source(monkeypatch, source.upper())
    assert _download_source() == source


def test_download_source_unknown_value_falls_back_to_modelscope(monkeypatch):
    from hermes_cli.web_routers.local_models import _download_source

    _patch_source(monkeypatch, "banana")
    assert _download_source() == "modelscope"


# ---------------------------------------------------------------------------
# M3 — _asset_urls
# ---------------------------------------------------------------------------

def test_asset_urls_huggingface_mode_returns_hf_only(monkeypatch):
    from hermes_cli.web_routers.local_models import _asset_urls

    _patch_source(monkeypatch, "huggingface")
    primary, fallbacks = _asset_urls(_entry(), _asset())
    assert primary == "https://huggingface.co/org/model/resolve/f737bcabc/model-Q4_K_M.gguf"
    assert fallbacks == ()


def test_asset_urls_modelscope_mode_uses_revision_and_main_fallback(monkeypatch):
    from hermes_cli.web_routers.local_models import _asset_urls

    _patch_source(monkeypatch, "modelscope")
    primary, fallbacks = _asset_urls(_entry(), _asset())
    assert primary == "https://www.modelscope.cn/models/org/model/resolve/master/model-Q4_K_M.gguf"
    assert fallbacks == (
        "https://www.modelscope.cn/models/org/model/resolve/main/model-Q4_K_M.gguf",
    )


def test_asset_urls_modelscope_revision_main_skips_duplicate_fallback(monkeypatch):
    from hermes_cli.web_routers.local_models import _asset_urls

    _patch_source(monkeypatch, "modelscope")
    primary, fallbacks = _asset_urls(
        _entry(modelscope_revision="main"), _asset())
    assert "main" in primary
    assert fallbacks == ()


def test_asset_urls_auto_appends_hf_after_modelscope(monkeypatch):
    from hermes_cli.web_routers.local_models import _asset_urls

    _patch_source(monkeypatch, "auto")
    primary, fallbacks = _asset_urls(_entry(), _asset())
    assert "modelscope.cn" in primary
    assert len(fallbacks) == 2
    assert fallbacks[0].endswith("/resolve/main/model-Q4_K_M.gguf")
    assert fallbacks[1].startswith("https://huggingface.co/")


def test_asset_urls_modelscope_repo_overrides_family_repo(monkeypatch):
    from hermes_cli.web_routers.local_models import _asset_urls

    _patch_source(monkeypatch, "modelscope")
    primary, _ = _asset_urls(_entry(modelscope_repo="cn/other-repo"), _asset())
    assert "cn/other-repo" in primary
    assert "org/model" not in primary


def test_asset_urls_companion_asset_keeps_its_own_repo(monkeypatch):
    from hermes_cli.web_routers.local_models import _asset_urls

    _patch_source(monkeypatch, "modelscope")
    primary, _ = _asset_urls(
        _entry(), _asset(repo="companion/org", path="draft.gguf"))
    assert "companion/org" in primary


# ---------------------------------------------------------------------------
# M4 — _download_plan rows carry (primary, fallbacks)
# ---------------------------------------------------------------------------

def test_download_plan_rows_are_pairs_of_urls(monkeypatch):
    from hermes_cli.web_routers.local_models import _download_plan

    _patch_source(monkeypatch, "auto")
    entry = _entry()
    variant = SimpleNamespace(files=(_asset(),))
    plan = _download_plan(entry, variant)

    assert len(plan) == 1
    urls, dest, size = plan[0]
    assert isinstance(urls, tuple) and len(urls) == 2
    assert urls[0].startswith("https://www.modelscope.cn/")
    assert urls[1][0].startswith("https://www.modelscope.cn/")
    assert dest.name == "model-Q4_K_M.gguf"
    assert size == 0
"""P1: local_runtime 模型目录配置化 + quickstart 单路径扫描（K-71）。

Covers:
  M1  models_dir() 默认 = get_default_hermes_root()/models
  M2  local_runtime.models_dir 配置键生效
  M3  HERMES_MODELS_DIR 兜底生效，且配置键优先
  M4  相对路径被忽略（回落默认，不炸模型列表）
  M5  quickstart._detect_local_runtime_models 扫描：手动 GGUF + 完整分片
      各算一个，残缺分片不算，assets/ 不算
  M6  quickstart._save_models_dir 写回 config
  M7  _prompt_models_dir 拒绝相对路径

Run:
    scripts/run_tests.sh tests/hermes_cli/test_quickstart_models_dir.py -q
"""

import yaml


def _patch_config(monkeypatch, cfg):
    """让 bootstrap/_detect 读到构好的 config，不碰真实 ~/.hermes。"""
    from hermes_cli import config

    monkeypatch.setattr(config, "load_config_readonly", lambda: cfg)


def test_models_dir_defaults_to_hermes_root(tmp_path, monkeypatch):
    from hermes_cli.local_runtime import bootstrap
    from hermes_constants import get_default_hermes_root

    monkeypatch.setenv("HERMES_HOME", str(tmp_path / ".hermes"))
    monkeypatch.delenv("HERMES_MODELS_DIR", raising=False)
    _patch_config(monkeypatch, {})

    assert bootstrap.models_dir() == get_default_hermes_root() / "models"


def test_models_dir_uses_config_key(tmp_path, monkeypatch):
    from hermes_cli.local_runtime import bootstrap

    library = tmp_path / "gguf-library"
    _patch_config(monkeypatch, {"local_runtime": {"models_dir": str(library)}})

    assert bootstrap.models_dir() == library


def test_models_dir_env_fallback_and_config_precedence(tmp_path, monkeypatch):
    from hermes_cli.local_runtime import bootstrap

    env_dir = tmp_path / "from-env"
    cfg_dir = tmp_path / "from-config"

    monkeypatch.setenv("HERMES_MODELS_DIR", str(env_dir))
    _patch_config(monkeypatch, {})
    assert bootstrap.models_dir() == env_dir

    _patch_config(monkeypatch, {"local_runtime": {"models_dir": str(cfg_dir)}})
    assert bootstrap.models_dir() == cfg_dir


def test_models_dir_ignores_relative_path(tmp_path, monkeypatch):
    from hermes_cli.local_runtime import bootstrap
    from hermes_constants import get_default_hermes_root

    monkeypatch.setenv("HERMES_HOME", str(tmp_path / ".hermes"))
    monkeypatch.delenv("HERMES_MODELS_DIR", raising=False)
    _patch_config(monkeypatch, {"local_runtime": {"models_dir": "relative/ggufs"}})

    assert bootstrap.models_dir() == get_default_hermes_root() / "models"


def test_detect_scans_manual_gguf_and_complete_splits(tmp_path, monkeypatch):
    from hermes_cli import quickstart_local_runtime

    library = tmp_path / "lib"
    library.mkdir()
    (library / "manual-Q4_K_M.gguf").write_bytes(b"x" * 100)
    for part in (1, 2):
        (library / f"split-{part:05d}-of-00002.gguf").write_bytes(b"x" * 100)
    # 残缺分片：只有 part 1，不可服务
    (library / "broken-00001-of-00002.gguf").write_bytes(b"x")
    # assets/ 不是模型
    assets = library / "assets"
    assets.mkdir()
    (assets / "mmproj.gguf").write_bytes(b"x")

    _patch_config(monkeypatch, {"local_runtime": {"models_dir": str(library)}})

    info = quickstart_local_runtime._detect_local_runtime_models()
    ids = {m["id"] for m in info["models"]}
    assert ids == {"manual-Q4_K_M", "split"}
    assert info["configured"] is True
    assert info["models_dir"] == str(library)


def test_save_models_dir_writes_config(tmp_path, monkeypatch):
    from hermes_cli import quickstart_local_runtime

    home = tmp_path / ".hermes"
    home.mkdir()
    monkeypatch.setenv("HERMES_HOME", str(home))

    target = tmp_path / "models"
    quickstart_local_runtime._save_models_dir(str(target))

    cfg = yaml.safe_load((home / "config.yaml").read_text(encoding="utf-8"))
    assert cfg["local_runtime"]["models_dir"] == str(target)


def test_prompt_models_dir_rejects_relative_path(monkeypatch):
    from hermes_cli import quickstart, quickstart_local_runtime

    # _prompt_models_dir lazy-imports quickstart._prompt_yes_no at call time,
    # so the patch belongs on the facade.
    monkeypatch.setattr(quickstart, "_prompt_yes_no", lambda *a, **k: True)
    monkeypatch.setattr("builtins.input", lambda *a: "relative/path")

    assert quickstart_local_runtime._prompt_models_dir("/abs/dir") is None

"""CN local-models (hermes_cli/model_manager) wiring tests.

The module was restored from the v0.12-v0.17 implementation after the
v0.19.1/v0.20.0 base-bump rewrite dropped it (while ``hermes quickstart``
still imported ``model_manager.is_installed`` and the docs advertised
``hermes local-models setup``).  Tests pin:

- The ``hermes local-models`` subcommand tree registers with all six
  verbs and every verb resolves to a callable handler.
- Model storage is profile-aware (routes through get_hermes_home(),
  honoring the AGENTS.md no-hardcoded-~/.hermes rule).
- Registry invariants: every entry carries the fields the CLI prints
  and the setup flow needs; is_installed() is safe for unknown ids.

Pure unit tests — no network, no downloads.
"""

import argparse

import pytest

from hermes_cli.model_manager import (
    MODEL_REGISTRY,
    _get_models_dir,
    is_installed,
)
from hermes_cli.subcommands.local_models import build_local_models_parser


EXPECTED_VERBS = ("list", "install", "setup", "remove", "status", "test")


def _parse(argv):
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command")
    build_local_models_parser(subparsers)
    return parser.parse_args(argv)


class TestLocalModelsSubcommand:

    def test_all_verbs_register(self):
        argv = ["local-models"] + [v for v in EXPECTED_VERBS]
        parser = argparse.ArgumentParser()
        subparsers = parser.add_subparsers(dest="command")
        build_local_models_parser(subparsers)
        # Bare group invocation resolves to the help summary handler.
        args = parser.parse_args(["local-models"])
        assert callable(args.func)

    def test_each_verb_has_callable_handler(self):
        for verb in EXPECTED_VERBS:
            args = _parse(["local-models", verb])
            assert callable(getattr(args, "func", None)), verb

    def test_setup_accepts_yes_flag(self):
        args = _parse(["local-models", "setup", "--yes"])
        assert getattr(args, "yes") is True

    def test_install_accepts_model_positional(self):
        args = _parse(["local-models", "install", "whisper-small"])
        assert args.model == "whisper-small"


class TestModelStorageProfileAware:

    def test_models_dir_honors_hermes_home(self, tmp_path, monkeypatch):
        monkeypatch.setenv("HERMES_HOME", str(tmp_path / "profile-home"))
        monkeypatch.delenv("HERMES_MODELS_DIR", raising=False)
        models_dir = _get_models_dir()
        assert str(models_dir).startswith(str(tmp_path / "profile-home"))

    def test_hermes_models_dir_override_wins(self, tmp_path, monkeypatch):
        monkeypatch.setenv("HERMES_MODELS_DIR", str(tmp_path / "custom"))
        assert _get_models_dir() == tmp_path / "custom"


class TestModelRegistry:

    def test_registry_entries_carry_required_fields(self):
        """Every entry must have what the CLI printer and setup flow read:
        id / name / size_mb. (Behavior contract — no count or id snapshots;
        the registry is expected to grow.)"""
        assert len(MODEL_REGISTRY) >= 1
        for entry in MODEL_REGISTRY:
            assert entry["id"], entry
            assert entry["name"], entry
            assert isinstance(entry["size_mb"], (int, float)), entry

    def test_setup_models_exist_in_registry(self):
        """The one-shot setup flow installs these ids — they must resolve."""
        registry_ids = {entry["id"] for entry in MODEL_REGISTRY}
        for required in ("whisper-small", "edge-tts", "qwen-0.5b"):
            assert required in registry_ids

    def test_is_installed_unknown_id_is_false(self, tmp_path, monkeypatch):
        monkeypatch.setenv("HERMES_HOME", str(tmp_path / "home"))
        monkeypatch.delenv("HERMES_MODELS_DIR", raising=False)
        assert is_installed("no-such-model-id") is False

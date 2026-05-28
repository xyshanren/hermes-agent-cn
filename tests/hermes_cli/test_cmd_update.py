"""Tests for cmd_update — branch fallback when remote branch doesn't exist."""

import subprocess
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from hermes_cli.main import cmd_update, PROJECT_ROOT


def _make_run_side_effect(branch="main", verify_ok=True, commit_count="0"):
    """Build a side_effect function for subprocess.run that simulates git commands."""

    def side_effect(cmd, **kwargs):
        joined = " ".join(str(c) for c in cmd)

        # git rev-parse --abbrev-ref HEAD  (get current branch)
        if "rev-parse" in joined and "--abbrev-ref" in joined:
            return subprocess.CompletedProcess(cmd, 0, stdout=f"{branch}\n", stderr="")

        # git rev-parse --verify origin/{branch}  (check remote branch exists)
        if "rev-parse" in joined and "--verify" in joined:
            rc = 0 if verify_ok else 128
            return subprocess.CompletedProcess(cmd, rc, stdout="", stderr="")

        # git rev-list HEAD..origin/{branch} --count
        if "rev-list" in joined:
            return subprocess.CompletedProcess(cmd, 0, stdout=f"{commit_count}\n", stderr="")

        # Fallback: return a successful CompletedProcess with empty stdout
        return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")

    return side_effect


@pytest.fixture
def mock_args():
    return SimpleNamespace()


class TestCmdUpdatePip:
    """Regression tests for pip-install update flows."""

    @patch("shutil.which", return_value="/usr/bin/uv")
    @patch("subprocess.run")
    def test_update_pip_exports_virtualenv_from_sys_prefix(
        self, mock_run, _mock_which, mock_args, monkeypatch
    ):
        from hermes_cli import main as hm

        mock_run.return_value = subprocess.CompletedProcess([], 0, stdout="", stderr="")
        monkeypatch.delenv("VIRTUAL_ENV", raising=False)
        monkeypatch.setattr(hm.sys, "prefix", "/tmp/hermes-launcher-venv")
        monkeypatch.setattr(hm.sys, "base_prefix", "/usr")

        hm._cmd_update_pip(mock_args)

        assert mock_run.call_count == 1
        assert mock_run.call_args.args[0] == ["/usr/bin/uv", "pip", "install", "--upgrade", "hermes-agent"]
        assert mock_run.call_args.kwargs["env"]["VIRTUAL_ENV"] == "/tmp/hermes-launcher-venv"

    @patch("shutil.which", return_value="/usr/bin/uv")
    @patch("subprocess.run")
    def test_update_pip_does_not_export_virtualenv_for_system_python(
        self, mock_run, _mock_which, mock_args, monkeypatch
    ):
        from hermes_cli import main as hm

        mock_run.return_value = subprocess.CompletedProcess([], 0, stdout="", stderr="")
        monkeypatch.delenv("VIRTUAL_ENV", raising=False)
        monkeypatch.setattr(hm.sys, "prefix", "/usr")
        monkeypatch.setattr(hm.sys, "base_prefix", "/usr")

        hm._cmd_update_pip(mock_args)

        assert mock_run.call_count == 1
        assert "env" not in mock_run.call_args.kwargs


class TestCmdUpdateBranchFallback:
    """cmd_update falls back to main when current branch has no remote counterpart."""

    @patch("shutil.which", return_value=None)
    @patch("subprocess.run")
    def test_update_falls_back_to_main_when_branch_not_on_remote(
        self, mock_run, _mock_which, mock_args, capsys
    ):
        mock_run.side_effect = _make_run_side_effect(
            branch="fix/stoicneko", verify_ok=False, commit_count="3"
        )

        cmd_update(mock_args)

        commands = [" ".join(str(a) for a in c.args[0]) for c in mock_run.call_args_list]

        # rev-list should use origin/main, not origin/fix/stoicneko
        rev_list_cmds = [c for c in commands if "rev-list" in c]
        assert len(rev_list_cmds) == 1
        assert "origin/main" in rev_list_cmds[0]
        assert "origin/fix/stoicneko" not in rev_list_cmds[0]

        # pull should use main, not fix/stoicneko
        pull_cmds = [c for c in commands if "pull" in c]
        assert len(pull_cmds) == 1
        assert "main" in pull_cmds[0]

    @patch("shutil.which", return_value=None)
    @patch("subprocess.run")
    def test_update_uses_current_branch_when_on_remote(
        self, mock_run, _mock_which, mock_args, capsys
    ):
        mock_run.side_effect = _make_run_side_effect(
            branch="main", verify_ok=True, commit_count="2"
        )

        cmd_update(mock_args)

        commands = [" ".join(str(a) for a in c.args[0]) for c in mock_run.call_args_list]

        rev_list_cmds = [c for c in commands if "rev-list" in c]
        assert len(rev_list_cmds) == 1
        assert "origin/main" in rev_list_cmds[0]

        pull_cmds = [c for c in commands if "pull" in c]
        assert len(pull_cmds) == 1
        assert "main" in pull_cmds[0]

    @patch("shutil.which", return_value=None)
    @patch("subprocess.run")
    def test_update_already_up_to_date(
        self, mock_run, _mock_which, mock_args, capsys
    ):
        mock_run.side_effect = _make_run_side_effect(
            branch="main", verify_ok=True, commit_count="0"
        )

        cmd_update(mock_args)

        captured = capsys.readouterr()
        assert "Already up to date!" in captured.out

        # Should NOT have called pull
        commands = [" ".join(str(a) for a in c.args[0]) for c in mock_run.call_args_list]
        pull_cmds = [c for c in commands if "pull" in c]
        assert len(pull_cmds) == 0

    @patch("shutil.which", return_value=None)
    @patch("subprocess.run")
    def test_update_on_fork_checks_upstream_when_origin_up_to_date(
        self, mock_run, _mock_which, mock_args, capsys
    ):
        """Regression for issue #26172: forks whose local HEAD already matches
        origin/main must still consult upstream/main before printing
        "Already up to date!" — otherwise a fork that's caught up to its own
        origin but behind NousResearch/hermes-agent silently misses updates.
        """
        from hermes_cli import main as hm

        mock_run.side_effect = _make_run_side_effect(
            branch="main", verify_ok=True, commit_count="0"
        )

        with patch.object(
            hm,
            "_get_origin_url",
            return_value="https://github.com/example/hermes-agent.git",
        ), patch.object(hm, "_sync_with_upstream_if_needed") as sync_mock:
            cmd_update(mock_args)

        sync_mock.assert_called_once_with(["git"], PROJECT_ROOT)
        captured = capsys.readouterr()
        assert "Already up to date!" in captured.out

    @patch("shutil.which")
    @patch("subprocess.run")
    def test_update_refreshes_repo_and_tui_node_dependencies(
        self, mock_run, mock_which, mock_args
    ):
        from hermes_cli import main as hm

        mock_which.side_effect = {"uv": "/usr/bin/uv", "npm": "/usr/bin/npm"}.get
        mock_run.side_effect = _make_run_side_effect(
            branch="main", verify_ok=True, commit_count="1"
        )
        # The web UI build runs through _run_with_idle_timeout now (issue
        # #33788) so it no longer appears in subprocess.run's call list.
        # Mock it so the test doesn't actually shell out to ``tsc``.
        import subprocess as _subprocess
        build_ok = _subprocess.CompletedProcess([], 0, stdout="", stderr="")
        with patch.object(hm, "_is_termux_env", return_value=False), \
             patch.object(hm, "_run_with_idle_timeout", return_value=build_ok) as mock_idle:
            cmd_update(mock_args)

        npm_calls = [
            (call.args[0], call.kwargs.get("cwd"))
            for call in mock_run.call_args_list
            if call.args and call.args[0][0] == "/usr/bin/npm"
        ]

        # cmd_update runs npm commands in four locations:
        #   1. repo root  — slash-command / TUI bridge deps  (subprocess.run)
        #   2. ui-tui/    — Ink TUI deps                     (subprocess.run)
        #   3. web/       — npm install                      (subprocess.run)
        #   4. web/       — npm run build                    (_run_with_idle_timeout)
        #
        # Repo-root and ui-tui installs intentionally omit `--silent` and run
        # without `capture_output` so optional postinstall scripts (e.g.
        # `@askjo/camofox-browser`'s browser-binary fetch) print progress —
        # otherwise long downloads look like a hang (#18840).  The web/ install
        # keeps `--silent` because its build step is short and noisy.
        update_flags = [
            "/usr/bin/npm",
            "ci",
            "--no-fund",
            "--no-audit",
            "--progress=false",
        ]
        assert npm_calls[:2] == [
            (update_flags, PROJECT_ROOT),
            (update_flags, PROJECT_ROOT / "ui-tui"),
        ]
        if len(npm_calls) > 2:
            # Only the web/ install is left in subprocess.run; the build moved
            # to _run_with_idle_timeout to make Vite progress visible (#33788).
            assert npm_calls[2:] == [
                (["/usr/bin/npm", "ci", "--silent"], PROJECT_ROOT / "web"),
            ]

        # The web UI build itself went through the streaming helper.
        mock_idle.assert_called_once()
        idle_args, idle_kwargs = mock_idle.call_args
        assert idle_args[0] == ["/usr/bin/npm", "run", "build"]
        assert idle_kwargs["cwd"] == PROJECT_ROOT / "web"

        # Regression for #18840: repo root + ui-tui installs must stream
        # output (capture_output=False) so postinstall progress is visible
        # to the user.
        repo_and_tui_calls = [
            call
            for call in mock_run.call_args_list
            if call.args
            and call.args[0][0] == "/usr/bin/npm"
            and call.args[0][1] == "ci"
            and call.kwargs.get("cwd") in {PROJECT_ROOT, PROJECT_ROOT / "ui-tui"}
        ]
        assert len(repo_and_tui_calls) == 2
        for call in repo_and_tui_calls:
            assert call.kwargs.get("capture_output") is False, (
                "repo-root / ui-tui npm install must stream output "
                "(no capture_output) so postinstall progress is visible"
            )

    def test_update_non_interactive_runs_safe_config_migrations(self, mock_args, capsys):
        """Dashboard/web updates apply non-interactive migrations before restart."""
        with patch("shutil.which", return_value=None), patch(
            "subprocess.run"
        ) as mock_run, patch("builtins.input") as mock_input, patch(
            "hermes_cli.config.get_missing_env_vars", return_value=["MISSING_KEY"]
        ), patch(
            "hermes_cli.config.get_missing_config_fields",
            return_value=[{"key": "new.option", "default": True}],
        ), patch("hermes_cli.config.check_config_version", return_value=(1, 2)), patch(
            "hermes_cli.config.migrate_config",
            return_value={"env_added": [], "config_added": ["new.option"]},
        ), patch("hermes_cli.main.sys") as mock_sys:
            mock_sys.stdin.isatty.return_value = False
            mock_sys.stdout.isatty.return_value = False
            mock_run.side_effect = _make_run_side_effect(
                branch="main", verify_ok=True, commit_count="1"
            )

            cmd_update(mock_args)

            mock_input.assert_not_called()
            from hermes_cli.config import migrate_config

            migrate_config.assert_called_once_with(interactive=False, quiet=False)
            captured = capsys.readouterr()
            assert "applying safe config migrations" in captured.out
            assert "API keys require manual entry" in captured.out


class TestCmdUpdateProfileSkillSync:
    """cmd_update syncs bundled skills to all profiles, including the active one.

    Regression guard for #16176: previously the active profile was excluded
    from the seed_profile_skills loop, leaving it on stale skill content.
    """

    @patch("shutil.which", return_value=None)
    @patch("subprocess.run")
    def test_active_profile_included_in_skill_sync(
        self, mock_run, _mock_which, mock_args, capsys
    ):
        from pathlib import Path

        mock_run.side_effect = _make_run_side_effect(
            branch="main", verify_ok=True, commit_count="1"
        )

        default_p = SimpleNamespace(name="default", path=Path("/fake/.hermes"))
        active_p = SimpleNamespace(name="bit", path=Path("/fake/.hermes/profiles/bit"))
        other_p = SimpleNamespace(name="work", path=Path("/fake/.hermes/profiles/work"))
        all_profiles = [default_p, active_p, other_p]

        synced_paths = []

        def fake_seed(path, quiet=False):
            synced_paths.append(path)
            return {"copied": [], "updated": [], "user_modified": []}

        empty_sync = {"copied": [], "updated": [], "user_modified": [], "cleaned": []}

        with (
            patch("hermes_cli.profiles.list_profiles", return_value=all_profiles),
            patch("hermes_cli.profiles.seed_profile_skills", side_effect=fake_seed),
            patch("tools.skills_sync.sync_skills", return_value=empty_sync),
        ):
            cmd_update(mock_args)

        assert active_p.path in synced_paths, (
            f"Active profile 'bit' must be included in skill sync; got: {synced_paths}"
        )
        assert set(synced_paths) == {p.path for p in all_profiles}, (
            f"All profiles must be synced; got: {synced_paths}"
        )

    @patch("shutil.which", return_value=None)
    @patch("subprocess.run")
    def test_single_profile_default_is_synced(
        self, mock_run, _mock_which, mock_args, capsys
    ):
        from pathlib import Path

        mock_run.side_effect = _make_run_side_effect(
            branch="main", verify_ok=True, commit_count="1"
        )

        default_p = SimpleNamespace(name="default", path=Path("/fake/.hermes"))
        synced_paths = []

        def fake_seed(path, quiet=False):
            synced_paths.append(path)
            return {"copied": [], "updated": [], "user_modified": []}

        empty_sync = {"copied": [], "updated": [], "user_modified": [], "cleaned": []}

        with (
            patch("hermes_cli.profiles.list_profiles", return_value=[default_p]),
            patch("hermes_cli.profiles.seed_profile_skills", side_effect=fake_seed),
            patch("tools.skills_sync.sync_skills", return_value=empty_sync),
        ):
            cmd_update(mock_args)

        assert default_p.path in synced_paths


def test_is_termux_env_true_for_termux_prefix():
    from hermes_cli import main as hm

    assert hm._is_termux_env({"PREFIX": "/data/data/com.termux/files/usr"}) is True


def test_is_termux_env_false_for_non_termux_prefix():
    from hermes_cli import main as hm

    assert hm._is_termux_env({"PREFIX": "/usr/local"}) is False


def test_load_installable_optional_extras_supports_termux_group(tmp_path, monkeypatch):
    from hermes_cli import main as hm

    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text(
        """
[project]
name = "x"
version = "0.0.0"

[project.optional-dependencies]
all = ["x[mcp]"]
termux-all = ["x[termux]", "x[mcp]"]
mcp = ["mcp>=1"]
termux = ["rich>=14"]
""".strip()
    )
    monkeypatch.setattr(hm, "PROJECT_ROOT", tmp_path)

    assert hm._load_installable_optional_extras(group="all") == ["mcp"]
    assert hm._load_installable_optional_extras(group="termux-all") == ["termux", "mcp"]

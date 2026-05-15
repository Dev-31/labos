from __future__ import annotations

import json

from typer.testing import CliRunner

from labos.cli.main import app
from labos.runtimes.docker_probe import DockerEnvironmentProbe

runner = CliRunner()


def test_release_readiness_reports_clean_ready_repo(monkeypatch) -> None:
    monkeypatch.setattr("labos.cli.main._git_status_is_clean", lambda: True)
    monkeypatch.setattr(
        "labos.cli.main.probe_docker_environment",
        lambda: DockerEnvironmentProbe(
            cli_present=True,
            daemon_reachable=True,
            detail="docker CLI and daemon are available",
        ),
    )

    result = runner.invoke(app, ["release", "readiness"])

    assert result.exit_code == 0
    assert json.loads(result.stdout) == {
        "blockers": [],
        "docker": {
            "cli_present": True,
            "daemon_reachable": True,
            "detail": "docker CLI and daemon are available",
            "ready": True,
        },
        "git_clean": True,
        "ready": True,
    }


def test_release_readiness_reports_blockers_and_fails(monkeypatch) -> None:
    monkeypatch.setattr("labos.cli.main._git_status_is_clean", lambda: False)
    monkeypatch.setattr(
        "labos.cli.main.probe_docker_environment",
        lambda: DockerEnvironmentProbe(
            cli_present=False,
            daemon_reachable=False,
            detail="docker CLI is not installed or not on PATH",
        ),
    )

    result = runner.invoke(app, ["release", "readiness"])

    assert result.exit_code == 1
    assert json.loads(result.stdout) == {
        "blockers": [
            "git working tree is not clean",
            "docker CLI is not installed or not on PATH",
        ],
        "docker": {
            "cli_present": False,
            "daemon_reachable": False,
            "detail": "docker CLI is not installed or not on PATH",
            "ready": False,
        },
        "git_clean": False,
        "ready": False,
    }

from __future__ import annotations

import json

from typer.testing import CliRunner

from labos.cli.main import app
from labos.runtimes.docker_probe import DockerEnvironmentProbe

runner = CliRunner()


def test_runtime_probe_docker_reports_ready_environment(monkeypatch) -> None:
    monkeypatch.setattr(
        "labos.cli.main.probe_docker_environment",
        lambda: DockerEnvironmentProbe(
            cli_present=True,
            cli_path="/usr/bin/docker",
            daemon_reachable=True,
            daemon_error=None,
            detail="docker CLI and daemon are available",
            issue_code="ready",
            remediation="none",
        ),
    )

    result = runner.invoke(app, ["runtime", "probe-docker"])

    assert result.exit_code == 0
    assert json.loads(result.stdout) == {
        "cli_present": True,
        "cli_path": "/usr/bin/docker",
        "daemon_reachable": True,
        "daemon_error": None,
        "detail": "docker CLI and daemon are available",
        "issue_code": "ready",
        "remediation": "none",
        "ready": True,
    }


def test_runtime_probe_docker_fails_when_environment_is_not_ready(monkeypatch) -> None:
    monkeypatch.setattr(
        "labos.cli.main.probe_docker_environment",
        lambda: DockerEnvironmentProbe(
            cli_present=False,
            cli_path=None,
            daemon_reachable=False,
            daemon_error=None,
            detail="docker CLI is not installed or not on PATH",
            issue_code="cli_missing",
            remediation="install Docker CLI and ensure it is available on PATH",
        ),
    )

    result = runner.invoke(app, ["runtime", "probe-docker"])

    assert result.exit_code == 1
    assert json.loads(result.stdout) == {
        "cli_present": False,
        "cli_path": None,
        "daemon_reachable": False,
        "daemon_error": None,
        "detail": "docker CLI is not installed or not on PATH",
        "issue_code": "cli_missing",
        "remediation": "install Docker CLI and ensure it is available on PATH",
        "ready": False,
    }

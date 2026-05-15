from __future__ import annotations

import json
from typing import Any

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


def test_release_smoke_docs_runs_health_profile_create_list_and_destroy(monkeypatch) -> None:
    calls: list[tuple[str, str, str, dict[str, Any] | None]] = []

    def fake_request_json(
        *,
        api_url: str,
        method: str,
        path: str,
        payload: dict[str, Any] | None = None,
    ) -> Any:
        calls.append((api_url, method, path, payload))
        if (method, path) == ("GET", "/health"):
            return {"status": "ok"}
        if (method, path) == ("GET", "/profiles"):
            return [{"name": "safe-dev"}, {"name": "red-zone"}]
        if (method, path) == ("POST", "/labs"):
            assert payload == {
                "profile_name": "safe-dev",
                "requester_type": "human",
                "base_snapshot_id": None,
                "metadata": {"source": "release-smoke-docs"},
            }
            return {"id": "lab-1", "state": "approved", "profile_name": "safe-dev"}
        if (method, path) == ("GET", "/labs"):
            return [{"id": "lab-1", "state": "approved"}]
        if (method, path) == ("DELETE", "/labs/lab-1"):
            return {"id": "lab-1", "state": "destroyed"}
        raise AssertionError(f"unexpected request: {(method, path, payload)}")

    monkeypatch.setattr("labos.cli.main._request_json", fake_request_json)

    result = runner.invoke(
        app,
        [
            "release",
            "smoke-docs",
            "--api-url",
            "http://127.0.0.1:8005",
            "--profile",
            "safe-dev",
            "--requester-type",
            "human",
        ],
    )

    assert result.exit_code == 0
    assert json.loads(result.stdout) == {
        "api_url": "http://127.0.0.1:8005",
        "created_lab": {"id": "lab-1", "profile_name": "safe-dev", "state": "approved"},
        "destroyed_lab": {"id": "lab-1", "state": "destroyed"},
        "health": {"status": "ok"},
        "labs_list_count": 1,
        "profile_names": ["safe-dev", "red-zone"],
        "profile_requested": "safe-dev",
        "requester_type": "human",
    }
    assert calls == [
        ("http://127.0.0.1:8005", "GET", "/health", None),
        ("http://127.0.0.1:8005", "GET", "/profiles", None),
        (
            "http://127.0.0.1:8005",
            "POST",
            "/labs",
            {
                "profile_name": "safe-dev",
                "requester_type": "human",
                "base_snapshot_id": None,
                "metadata": {"source": "release-smoke-docs"},
            },
        ),
        ("http://127.0.0.1:8005", "GET", "/labs", None),
        ("http://127.0.0.1:8005", "DELETE", "/labs/lab-1", None),
    ]

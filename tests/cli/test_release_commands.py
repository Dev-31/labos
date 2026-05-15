from __future__ import annotations

import json
from typing import Any

import typer
from typer.testing import CliRunner

from labos.cli.main import DEFAULT_API_URL, app
from labos.runtimes.docker_probe import DockerEnvironmentProbe

runner = CliRunner()


def test_run_external_command_strips_virtual_env_before_invoking_uv(monkeypatch) -> None:
    monkeypatch.setenv("VIRTUAL_ENV", "/tmp/foreign-venv")
    captured: dict[str, Any] = {}

    def fake_run(
        args: list[str],
        *,
        check: bool,
        capture_output: bool,
        text: bool,
        env: dict[str, str],
    ) -> Any:
        captured["args"] = args
        captured["env"] = env
        return type(
            "CompletedProcess",
            (),
            {"returncode": 0, "stdout": "ok\n", "stderr": ""},
        )()

    monkeypatch.setattr("labos.cli.main.subprocess.run", fake_run)

    from labos.cli.main import _run_external_command

    output = _run_external_command(["uv", "run", "pytest", "-q"])

    assert output == "ok\n"
    assert captured["args"] == ["uv", "run", "pytest", "-q"]
    assert "VIRTUAL_ENV" not in captured["env"]


def test_release_readiness_reports_clean_ready_repo(monkeypatch) -> None:
    monkeypatch.setattr(
        "labos.cli.main._git_status_payload",
        lambda: {
            "clean": True,
            "detail": "git working tree is clean",
            "entries": [],
            "issue_code": "clean",
            "remediation": "none",
        },
    )
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

    result = runner.invoke(app, ["release", "readiness"])

    assert result.exit_code == 0
    assert json.loads(result.stdout) == {
        "blockers": [],
        "docker": {
            "cli_present": True,
            "cli_path": "/usr/bin/docker",
            "current_user": None,
            "daemon_reachable": True,
            "daemon_error": None,
            "daemon_target": None,
            "detail": "docker CLI and daemon are available",
            "issue_code": "ready",
            "ready": True,
            "remediation": "none",
            "socket_exists": None,
            "socket_group": None,
            "socket_mode": None,
            "socket_owner": None,
            "socket_path": None,
            "user_groups": [],
            "user_in_socket_group": None,
        },
        "git": {
            "clean": True,
            "detail": "git working tree is clean",
            "entries": [],
            "issue_code": "clean",
            "remediation": "none",
        },
        "git_clean": True,
        "next_action": "tag the verified v0.1.0 release once changelog/release notes are finalized",
        "pending_steps": [
            "tag first release",
        ],
        "ready": True,
        "tag_ready": True,
    }


def test_release_readiness_reports_blockers_and_fails(monkeypatch) -> None:
    monkeypatch.setattr(
        "labos.cli.main._git_status_payload",
        lambda: {
            "clean": False,
            "detail": "git working tree is not clean: ?? get-docker.sh",
            "entries": [{"path": "get-docker.sh", "status": "??"}],
            "issue_code": "dirty",
            "remediation": "commit, stash, or delete the reported paths before tagging",
        },
    )
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

    result = runner.invoke(app, ["release", "readiness"])

    assert result.exit_code == 1
    assert json.loads(result.stdout) == {
        "blockers": [
            "git working tree is not clean: ?? get-docker.sh",
            "docker CLI is not installed or not on PATH",
        ],
        "docker": {
            "cli_present": False,
            "cli_path": None,
            "current_user": None,
            "daemon_reachable": False,
            "daemon_error": None,
            "daemon_target": None,
            "detail": "docker CLI is not installed or not on PATH",
            "issue_code": "cli_missing",
            "ready": False,
            "remediation": "install Docker CLI and ensure it is available on PATH",
            "socket_exists": None,
            "socket_group": None,
            "socket_mode": None,
            "socket_owner": None,
            "socket_path": None,
            "user_groups": [],
            "user_in_socket_group": None,
        },
        "git": {
            "clean": False,
            "detail": "git working tree is not clean: ?? get-docker.sh",
            "entries": [{"path": "get-docker.sh", "status": "??"}],
            "issue_code": "dirty",
            "remediation": "commit, stash, or delete the reported paths before tagging",
        },
        "git_clean": False,
        "next_action": "clean the git working tree, then re-run labos release readiness",
        "pending_steps": [
            "clean git working tree",
            "validate local Docker integration from scratch",
            "tag first release",
        ],
        "ready": False,
        "tag_ready": False,
    }


def test_release_evidence_reports_machine_readable_release_template(monkeypatch) -> None:
    monkeypatch.setattr(
        "labos.cli.main._git_status_payload",
        lambda: {
            "clean": False,
            "detail": "git working tree is not clean: ?? get-docker.sh",
            "entries": [{"path": "get-docker.sh", "status": "??"}],
            "issue_code": "dirty",
            "remediation": "commit, stash, or delete the reported paths before tagging",
        },
    )
    monkeypatch.setattr("labos.cli.main._git_head_sha", lambda: "abc123def456")
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

    result = runner.invoke(app, ["release", "evidence"])

    assert result.exit_code == 0
    assert json.loads(result.stdout) == {
        "blockers": [
            "git working tree is not clean: ?? get-docker.sh",
            "docker CLI is not installed or not on PATH",
        ],
        "commit": "abc123def456",
        "docker": {
            "cli_present": False,
            "cli_path": None,
            "current_user": None,
            "daemon_reachable": False,
            "daemon_error": None,
            "daemon_target": None,
            "detail": "docker CLI is not installed or not on PATH",
            "issue_code": "cli_missing",
            "ready": False,
            "remediation": "install Docker CLI and ensure it is available on PATH",
            "socket_exists": None,
            "socket_group": None,
            "socket_mode": None,
            "socket_owner": None,
            "socket_path": None,
            "user_groups": [],
            "user_in_socket_group": None,
        },
        "docs_validated": [
            "README.md",
            "docs/api.md",
            "docs/cli.md",
            "docs/release-checklist.md",
        ],
        "git": {
            "clean": False,
            "detail": "git working tree is not clean: ?? get-docker.sh",
            "entries": [{"path": "get-docker.sh", "status": "??"}],
            "issue_code": "dirty",
            "remediation": "commit, stash, or delete the reported paths before tagging",
        },
        "git_clean": False,
        "honesty_boundary_confirmed": False,
        "next_action": "clean the git working tree, then re-run labos release readiness",
        "pending_steps": [
            "clean git working tree",
            "validate local Docker integration from scratch",
            "tag first release",
        ],
        "ready": False,
        "tag_ready": False,
        "template": {
            "API smoke": "labos release smoke-docs",
            "CLI smoke": "labos release smoke-cli",
            "Docker smoke": "labos release smoke-docker",
            "Commit": "abc123def456",
            "Git detail": "git working tree is not clean: ?? get-docker.sh",
            "Git entries": "?? get-docker.sh",
            "Git issue code": "dirty",
            "Git remediation": "commit, stash, or delete the reported paths before tagging",
            "Docker CLI path": "unknown",
            "Docker current user": "unknown",
            "Docker daemon error": "n/a",
            "Docker daemon target": "unknown",
            "Docker issue code": "cli_missing",
            "Docker integration notes": "docker CLI is not installed or not on PATH",
            "Docker remediation": "install Docker CLI and ensure it is available on PATH",
            "Docker socket exists": "no",
            "Docker socket group": "n/a",
            "Docker socket mode": "n/a",
            "Docker socket owner": "n/a",
            "Docker socket path": "n/a",
            "Docker user groups": "none",
            "Docker user in socket group": "unknown",
            "Docs validated": "README.md, docs/api.md, docs/cli.md, docs/release-checklist.md",
            "Honesty boundary confirmed": "no",
            "Install smoke": "uv sync --extra dev",
            "Lint": "uv run ruff check .",
            "Next action": "clean the git working tree, then re-run labos release readiness",
            "Pending steps": (
                "clean git working tree; validate local Docker integration from "
                "scratch; tag first release"
            ),
            "Tag ready": "no",
            "Tests": "uv run pytest -q",
            "Types": "uv run mypy",
        },
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


def test_release_smoke_docs_destroys_created_lab_when_later_step_fails(monkeypatch) -> None:
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
            return [{"name": "safe-dev"}]
        if (method, path) == ("POST", "/labs"):
            return {"id": "lab-1", "state": "approved", "profile_name": "safe-dev"}
        if (method, path) == ("GET", "/labs"):
            raise typer.Exit(code=1)
        if (method, path) == ("DELETE", "/labs/lab-1"):
            return {"id": "lab-1", "state": "destroyed"}
        raise AssertionError(f"unexpected request: {(method, path, payload)}")

    monkeypatch.setattr("labos.cli.main._request_json", fake_request_json)

    result = runner.invoke(app, ["release", "smoke-docs"])

    assert result.exit_code == 1
    assert calls == [
        (DEFAULT_API_URL, "GET", "/health", None),
        (DEFAULT_API_URL, "GET", "/profiles", None),
        (
            DEFAULT_API_URL,
            "POST",
            "/labs",
            {
                "profile_name": "safe-dev",
                "requester_type": "human",
                "base_snapshot_id": None,
                "metadata": {"source": "release-smoke-docs"},
            },
        ),
        (DEFAULT_API_URL, "GET", "/labs", None),
        (DEFAULT_API_URL, "DELETE", "/labs/lab-1", None),
    ]


def test_release_smoke_cli_validates_help_and_representative_commands(monkeypatch) -> None:
    calls: list[tuple[list[str], dict[str, str] | None]] = []

    def fake_run_cli_command(
        args: list[str],
        *,
        env_overrides: dict[str, str] | None = None,
    ) -> str:
        calls.append((args, env_overrides))
        if args == ["--help"]:
            return "Usage: labos [OPTIONS] COMMAND [ARGS]...\n\n  LabOS operator CLI\n"
        if args == ["profiles", "list"]:
            return json.dumps([{"name": "safe-dev"}, {"name": "red-zone"}])
        if args == [
            "labs",
            "create",
            "safe-dev",
            "--requester-type",
            "human",
            "--metadata",
            '{"source": "release-smoke-cli"}',
        ]:
            return json.dumps({"id": "lab-2", "state": "approved", "profile_name": "safe-dev"})
        if args == ["labs", "list"]:
            return json.dumps([{"id": "lab-2", "state": "approved"}])
        if args == ["labs", "get", "lab-2"]:
            return json.dumps({"id": "lab-2", "state": "approved", "profile_name": "safe-dev"})
        if args == ["labs", "destroy", "lab-2"]:
            return json.dumps({"id": "lab-2", "state": "destroyed"})
        raise AssertionError(f"unexpected CLI command: {args}")

    monkeypatch.setattr("labos.cli.main._run_cli_command", fake_run_cli_command)

    result = runner.invoke(
        app,
        [
            "release",
            "smoke-cli",
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
        "commands_validated": [
            "labos --help",
            "labos profiles list",
            "labos labs create safe-dev --requester-type human",
            "labos labs list",
            "labos labs get lab-2",
            "labos labs destroy lab-2",
        ],
        "created_lab": {"id": "lab-2", "profile_name": "safe-dev", "state": "approved"},
        "destroyed_lab": {"id": "lab-2", "state": "destroyed"},
        "help_verified": True,
        "listed_lab_count": 1,
        "profile_names": ["safe-dev", "red-zone"],
        "profile_requested": "safe-dev",
        "requester_type": "human",
        "retrieved_lab": {"id": "lab-2", "profile_name": "safe-dev", "state": "approved"},
    }
    assert calls == [
        (["--help"], {"LABOS_API_URL": "http://127.0.0.1:8005"}),
        (["profiles", "list"], {"LABOS_API_URL": "http://127.0.0.1:8005"}),
        (
            [
                "labs",
                "create",
                "safe-dev",
                "--requester-type",
                "human",
                "--metadata",
                '{"source": "release-smoke-cli"}',
            ],
            {"LABOS_API_URL": "http://127.0.0.1:8005"},
        ),
        (["labs", "list"], {"LABOS_API_URL": "http://127.0.0.1:8005"}),
        (["labs", "get", "lab-2"], {"LABOS_API_URL": "http://127.0.0.1:8005"}),
        (["labs", "destroy", "lab-2"], {"LABOS_API_URL": "http://127.0.0.1:8005"}),
    ]


def test_release_smoke_cli_destroys_created_lab_when_later_step_fails(monkeypatch) -> None:
    calls: list[tuple[list[str], dict[str, str] | None]] = []

    def fake_run_cli_command(
        args: list[str],
        *,
        env_overrides: dict[str, str] | None = None,
    ) -> str:
        calls.append((args, env_overrides))
        if args == ["--help"]:
            return "Usage: labos [OPTIONS] COMMAND [ARGS]...\n\n  LabOS operator CLI\n"
        if args == ["profiles", "list"]:
            return json.dumps([{"name": "safe-dev"}])
        if args == [
            "labs",
            "create",
            "safe-dev",
            "--requester-type",
            "human",
            "--metadata",
            '{"source": "release-smoke-cli"}',
        ]:
            return json.dumps({"id": "lab-2", "state": "approved", "profile_name": "safe-dev"})
        if args == ["labs", "list"]:
            raise typer.Exit(code=1)
        if args == ["labs", "destroy", "lab-2"]:
            return json.dumps({"id": "lab-2", "state": "destroyed"})
        raise AssertionError(f"unexpected CLI command: {args}")

    monkeypatch.setattr("labos.cli.main._run_cli_command", fake_run_cli_command)

    result = runner.invoke(app, ["release", "smoke-cli"])

    assert result.exit_code == 1
    assert calls == [
        (["--help"], {"LABOS_API_URL": DEFAULT_API_URL}),
        (["profiles", "list"], {"LABOS_API_URL": DEFAULT_API_URL}),
        (
            [
                "labs",
                "create",
                "safe-dev",
                "--requester-type",
                "human",
                "--metadata",
                '{"source": "release-smoke-cli"}',
            ],
            {"LABOS_API_URL": DEFAULT_API_URL},
        ),
        (["labs", "list"], {"LABOS_API_URL": DEFAULT_API_URL}),
        (["labs", "destroy", "lab-2"], {"LABOS_API_URL": DEFAULT_API_URL}),
    ]


def test_release_smoke_docker_reports_probe_and_pytest_output(monkeypatch) -> None:
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

    def fake_run_external_command(args: list[str]) -> str:
        assert args == [
            "uv",
            "run",
            "pytest",
            "-q",
            "tests/integration/test_docker_runtime_smoke.py",
        ]
        return "1 passed in 0.42s\n"

    monkeypatch.setattr("labos.cli.main._run_external_command", fake_run_external_command)

    result = runner.invoke(app, ["release", "smoke-docker"])

    assert result.exit_code == 0
    assert json.loads(result.stdout) == {
        "command": "uv run pytest -q tests/integration/test_docker_runtime_smoke.py",
        "docker": {
            "cli_present": True,
            "cli_path": "/usr/bin/docker",
            "current_user": None,
            "daemon_reachable": True,
            "daemon_error": None,
            "daemon_target": None,
            "detail": "docker CLI and daemon are available",
            "issue_code": "ready",
            "ready": True,
            "remediation": "none",
            "socket_exists": None,
            "socket_group": None,
            "socket_mode": None,
            "socket_owner": None,
            "socket_path": None,
            "user_groups": [],
            "user_in_socket_group": None,
        },
        "output": "1 passed in 0.42s",
        "ready": True,
    }


def test_release_smoke_docker_fails_honestly_when_probe_is_not_ready(monkeypatch) -> None:
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

    def fake_run_external_command(args: list[str]) -> str:
        raise AssertionError(f"pytest should not run when docker probe fails: {args}")

    monkeypatch.setattr("labos.cli.main._run_external_command", fake_run_external_command)

    result = runner.invoke(app, ["release", "smoke-docker"])

    assert result.exit_code == 1
    assert json.loads(result.stdout) == {
        "command": "uv run pytest -q tests/integration/test_docker_runtime_smoke.py",
        "docker": {
            "cli_present": False,
            "cli_path": None,
            "current_user": None,
            "daemon_reachable": False,
            "daemon_error": None,
            "daemon_target": None,
            "detail": "docker CLI is not installed or not on PATH",
            "issue_code": "cli_missing",
            "ready": False,
            "remediation": "install Docker CLI and ensure it is available on PATH",
            "socket_exists": None,
            "socket_group": None,
            "socket_mode": None,
            "socket_owner": None,
            "socket_path": None,
            "user_groups": [],
            "user_in_socket_group": None,
        },
        "output": None,
        "ready": False,
    }


def test_release_smoke_local_bootstraps_temp_api_and_runs_release_smokes(
    monkeypatch,
    tmp_path,
) -> None:
    started: list[tuple[str, str]] = []
    waited_on: list[str] = []
    stopped: list[str] = []
    cli_calls: list[tuple[list[str], dict[str, str] | None]] = []

    class DummyProcess:
        def __init__(self) -> None:
            self.returncode = None

    def fake_prepare_environment() -> tuple[str, dict[str, str]]:
        return (
            "http://127.0.0.1:8017",
            {
                "LABOS_DATABASE_URL": f"sqlite+pysqlite:///{tmp_path / 'labos-release.db'}",
                "LABOS_MANAGED_STORAGE_ROOT": str(tmp_path / 'storage'),
            },
        )

    def fake_initialize_database(database_url: str) -> None:
        started.append(("db", database_url))

    def fake_start_local_api_server(*, api_url: str, env_overrides: dict[str, str]) -> DummyProcess:
        started.append((api_url, env_overrides["LABOS_DATABASE_URL"]))
        return DummyProcess()

    def fake_wait_for_api_ready(api_url: str) -> None:
        waited_on.append(api_url)

    def fake_run_cli_json_command(
        args: list[str],
        *,
        env_overrides: dict[str, str] | None = None,
    ) -> Any:
        cli_calls.append((args, env_overrides))
        if args == ["release", "smoke-docs", "--api-url", "http://127.0.0.1:8017"]:
            return {"health": {"status": "ok"}, "requester_type": "human"}
        if args == ["release", "smoke-cli", "--api-url", "http://127.0.0.1:8017"]:
            return {"help_verified": True, "listed_lab_count": 1}
        raise AssertionError(f"unexpected CLI command: {args}")

    def fake_release_smoke_docker_payload() -> dict[str, Any]:
        return {
            "command": "uv run pytest -q tests/integration/test_docker_runtime_smoke.py",
            "docker": {
                "cli_present": True,
                "cli_path": "/usr/bin/docker",
                "daemon_reachable": True,
                "daemon_error": None,
                "detail": "docker CLI and daemon are available",
                "issue_code": "ready",
                "remediation": "none",
                "ready": True,
            },
            "output": "1 passed in 0.42s",
            "ready": True,
        }

    def fake_stop_process(process: DummyProcess) -> None:
        del process
        stopped.append("stopped")

    monkeypatch.setattr(
        "labos.cli.main._prepare_release_smoke_local_environment",
        fake_prepare_environment,
    )
    monkeypatch.setattr("labos.cli.main._initialize_database", fake_initialize_database)
    monkeypatch.setattr("labos.cli.main._start_local_api_server", fake_start_local_api_server)
    monkeypatch.setattr("labos.cli.main._wait_for_api_ready", fake_wait_for_api_ready)
    monkeypatch.setattr("labos.cli.main._run_cli_json_command", fake_run_cli_json_command)
    monkeypatch.setattr(
        "labos.cli.main._release_smoke_docker_payload",
        fake_release_smoke_docker_payload,
    )
    monkeypatch.setattr("labos.cli.main._stop_process", fake_stop_process)

    result = runner.invoke(app, ["release", "smoke-local"])

    assert result.exit_code == 0
    assert json.loads(result.stdout) == {
        "api_url": "http://127.0.0.1:8017",
        "cli_smoke": {"help_verified": True, "listed_lab_count": 1},
        "docker_smoke": {
            "command": "uv run pytest -q tests/integration/test_docker_runtime_smoke.py",
            "docker": {
                "cli_present": True,
                "cli_path": "/usr/bin/docker",
                "daemon_reachable": True,
                "daemon_error": None,
                "detail": "docker CLI and daemon are available",
                "issue_code": "ready",
                "remediation": "none",
                "ready": True,
            },
            "output": "1 passed in 0.42s",
            "ready": True,
        },
        "docs_smoke": {"health": {"status": "ok"}, "requester_type": "human"},
        "environment": {
            "database_url": f"sqlite+pysqlite:///{tmp_path / 'labos-release.db'}",
            "managed_storage_root": str(tmp_path / 'storage'),
        },
        "ready": True,
    }
    assert started == [
        ("db", f"sqlite+pysqlite:///{tmp_path / 'labos-release.db'}"),
        ("http://127.0.0.1:8017", f"sqlite+pysqlite:///{tmp_path / 'labos-release.db'}"),
    ]
    assert waited_on == ["http://127.0.0.1:8017"]
    assert cli_calls == [
        (["release", "smoke-docs", "--api-url", "http://127.0.0.1:8017"], None),
        (["release", "smoke-cli", "--api-url", "http://127.0.0.1:8017"], None),
    ]
    assert stopped == ["stopped"]


def test_release_smoke_local_stops_temp_api_and_fails_when_docker_smoke_is_blocked(
    monkeypatch, tmp_path
) -> None:
    stopped: list[str] = []

    class DummyProcess:
        def __init__(self) -> None:
            self.returncode = None

    monkeypatch.setattr(
        "labos.cli.main._prepare_release_smoke_local_environment",
        lambda: (
            "http://127.0.0.1:8018",
            {
                "LABOS_DATABASE_URL": f"sqlite+pysqlite:///{tmp_path / 'labos-release.db'}",
                "LABOS_MANAGED_STORAGE_ROOT": str(tmp_path / 'storage'),
            },
        ),
    )
    monkeypatch.setattr("labos.cli.main._initialize_database", lambda database_url: None)
    monkeypatch.setattr(
        "labos.cli.main._start_local_api_server",
        lambda *, api_url, env_overrides: DummyProcess(),
    )
    monkeypatch.setattr("labos.cli.main._wait_for_api_ready", lambda api_url: None)
    monkeypatch.setattr(
        "labos.cli.main._run_cli_json_command",
        lambda args, env_overrides=None: {"ok": True},
    )
    monkeypatch.setattr(
        "labos.cli.main._release_smoke_docker_payload",
        lambda: {
            "command": "uv run pytest -q tests/integration/test_docker_runtime_smoke.py",
            "docker": {
                "cli_present": False,
                "cli_path": None,
                "daemon_reachable": False,
                "daemon_error": None,
                "detail": "docker CLI is not installed or not on PATH",
                "issue_code": "cli_missing",
                "remediation": "install Docker CLI and ensure it is available on PATH",
                "ready": False,
            },
            "output": None,
            "ready": False,
        },
    )
    monkeypatch.setattr("labos.cli.main._stop_process", lambda process: stopped.append("stopped"))

    result = runner.invoke(app, ["release", "smoke-local"])

    assert result.exit_code == 1
    assert json.loads(result.stdout)["ready"] is False
    assert stopped == ["stopped"]

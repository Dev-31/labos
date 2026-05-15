from __future__ import annotations

import json
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import time
from contextlib import suppress
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import httpx
import typer

from labos import __version__
from labos.db.schema import Base
from labos.db.session import build_engine
from labos.runtimes.docker_probe import probe_docker_environment

DEFAULT_API_URL = "http://127.0.0.1:8000"

app = typer.Typer(help="LabOS operator CLI")
profiles_app = typer.Typer(help="Inspect built-in policy profiles")
labs_app = typer.Typer(help="Create and inspect governed lab records")
runs_app = typer.Typer(help="Create and inspect governed run records")
snapshots_app = typer.Typer(help="Create and inspect governed snapshot records")
exports_app = typer.Typer(help="Request and inspect governed export records")
approvals_app = typer.Typer(help="Inspect and decide approval requests")
events_app = typer.Typer(help="Inspect audit and event records")
scheduler_app = typer.Typer(help="Queue and dispatch scheduler-controlled jobs")
runtime_app = typer.Typer(help="Inspect runtime adapter readiness and honesty boundaries")
release_app = typer.Typer(help="Inspect release readiness and current blockers")
app.add_typer(profiles_app, name="profiles")
app.add_typer(labs_app, name="labs")
app.add_typer(runs_app, name="runs")
app.add_typer(snapshots_app, name="snapshots")
app.add_typer(exports_app, name="exports")
app.add_typer(approvals_app, name="approvals")
app.add_typer(events_app, name="events")
app.add_typer(scheduler_app, name="scheduler")
app.add_typer(runtime_app, name="runtime")
app.add_typer(release_app, name="release")


def _normalize_api_url(api_url: str) -> str:
    return api_url.rstrip("/")


def _emit_json(payload: Any) -> None:
    typer.echo(json.dumps(payload, indent=2, sort_keys=True))


def _docker_probe_payload(probe: Any) -> dict[str, Any]:
    return {
        "cli_present": probe.cli_present,
        "cli_path": probe.cli_path,
        "daemon_reachable": probe.daemon_reachable,
        "daemon_error": probe.daemon_error,
        "detail": probe.detail,
        "ready": probe.ready,
    }


def _git_status_is_clean() -> bool:
    result = subprocess.run(
        ["git", "status", "--short"],
        check=False,
        capture_output=True,
        text=True,
    )
    return result.returncode == 0 and result.stdout.strip() == ""


def _git_head_sha() -> str:
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return "unknown"
    return result.stdout.strip() or "unknown"


def _release_pending_steps(*, git_clean: bool, docker_ready: bool) -> list[str]:
    pending_steps: list[str] = []
    if not git_clean:
        pending_steps.append("clean git working tree")
    if not docker_ready:
        pending_steps.append("validate local Docker integration from scratch")
    pending_steps.append("tag first release")
    return pending_steps


def _release_next_action(*, git_clean: bool, docker_ready: bool) -> str:
    if not git_clean:
        return "clean the git working tree, then re-run labos release readiness"
    if not docker_ready:
        return (
            "install Docker CLI or run on a host with a reachable Docker daemon, "
            "then re-run labos release smoke-docker and labos runtime probe-docker"
        )
    return "tag the verified v0.1.0 release once changelog/release notes are finalized"


def _release_status_payload(*, include_commit: bool = False) -> dict[str, Any]:
    git_clean = _git_status_is_clean()
    docker_probe = probe_docker_environment()
    blockers: list[str] = []
    if not git_clean:
        blockers.append("git working tree is not clean")
    if not docker_probe.ready:
        blockers.append(docker_probe.detail)

    payload: dict[str, Any] = {
        "blockers": blockers,
        "docker": _docker_probe_payload(docker_probe),
        "git_clean": git_clean,
        "next_action": _release_next_action(
            git_clean=git_clean,
            docker_ready=docker_probe.ready,
        ),
        "pending_steps": _release_pending_steps(
            git_clean=git_clean,
            docker_ready=docker_probe.ready,
        ),
        "ready": not blockers,
        "tag_ready": git_clean and docker_probe.ready,
    }
    if include_commit:
        payload["commit"] = _git_head_sha()
    return payload


def _request_json(
    *,
    api_url: str,
    method: str,
    path: str,
    payload: dict[str, Any] | None = None,
) -> Any:
    try:
        with httpx.Client(base_url=_normalize_api_url(api_url), timeout=10.0) as client:
            response = client.request(method, path, json=payload)
            response.raise_for_status()
            return response.json()
    except httpx.HTTPStatusError as exc:
        detail = exc.response.text.strip() or str(exc)
        typer.echo(detail, err=True)
        raise typer.Exit(code=1) from exc
    except httpx.HTTPError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc


def _parse_json_object(option_name: str, raw_value: str | None) -> dict[str, Any] | None:
    if raw_value is None:
        return None
    try:
        parsed = json.loads(raw_value)
    except json.JSONDecodeError as exc:
        typer.echo(f"{option_name} must be a valid JSON object.", err=True)
        raise typer.Exit(code=1) from exc
    if not isinstance(parsed, dict):
        typer.echo(f"{option_name} must be a valid JSON object.", err=True)
        raise typer.Exit(code=1)
    return parsed


def _run_cli_command(
    args: list[str],
    *,
    env_overrides: dict[str, str] | None = None,
) -> str:
    env = os.environ.copy()
    if env_overrides:
        env.update(env_overrides)
    result = subprocess.run(
        [sys.executable, "-m", "labos.cli.main", *args],
        check=False,
        capture_output=True,
        text=True,
        env=env,
    )
    if result.returncode != 0:
        detail = result.stderr.strip() or result.stdout.strip()
        if not detail:
            detail = f"CLI command failed: {' '.join(args)}"
        typer.echo(detail, err=True)
        raise typer.Exit(code=1)
    return result.stdout


def _run_cli_json_command(
    args: list[str],
    *,
    env_overrides: dict[str, str] | None = None,
) -> Any:
    raw_output = _run_cli_command(args, env_overrides=env_overrides)
    try:
        return json.loads(raw_output)
    except json.JSONDecodeError as exc:
        typer.echo(f"CLI command did not return valid JSON: {' '.join(args)}", err=True)
        raise typer.Exit(code=1) from exc


def _run_external_command(args: list[str]) -> str:
    result = subprocess.run(
        args,
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        detail = result.stderr.strip() or result.stdout.strip()
        if not detail:
            detail = f"External command failed: {' '.join(args)}"
        typer.echo(detail, err=True)
        raise typer.Exit(code=1)
    return result.stdout


def _find_free_tcp_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])



def _prepare_release_smoke_local_environment() -> tuple[str, dict[str, str]]:
    root = Path(tempfile.mkdtemp(prefix="labos-release-smoke-"))
    port = _find_free_tcp_port()
    api_url = f"http://127.0.0.1:{port}"
    return (
        api_url,
        {
            "LABOS_DATABASE_URL": f"sqlite+pysqlite:///{root / 'labos-release.db'}",
            "LABOS_MANAGED_STORAGE_ROOT": str(root / "storage"),
            "LABOS_RELEASE_SMOKE_ROOT": str(root),
        },
    )



def _initialize_database(database_url: str) -> None:
    engine = build_engine(database_url)
    Base.metadata.create_all(engine)



def _start_local_api_server(
    *,
    api_url: str,
    env_overrides: dict[str, str],
) -> subprocess.Popen[str]:
    parsed = urlparse(api_url)
    host = parsed.hostname or "127.0.0.1"
    port = parsed.port
    if port is None:
        typer.echo(f"release smoke local API URL must include a port: {api_url}", err=True)
        raise typer.Exit(code=1)

    env = os.environ.copy()
    env.update(env_overrides)
    return subprocess.Popen(
        [
            sys.executable,
            "-m",
            "uvicorn",
            "labos.api.app:app",
            "--host",
            host,
            "--port",
            str(port),
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env=env,
    )



def _wait_for_api_ready(api_url: str, *, timeout_seconds: float = 15.0) -> None:
    deadline = time.monotonic() + timeout_seconds
    last_error: str | None = None
    while time.monotonic() < deadline:
        try:
            with httpx.Client(base_url=_normalize_api_url(api_url), timeout=2.0) as client:
                response = client.get("/health")
                response.raise_for_status()
                return
        except httpx.HTTPError as exc:
            last_error = str(exc)
            time.sleep(0.2)

    detail = last_error or "timed out waiting for local LabOS API"
    typer.echo(detail, err=True)
    raise typer.Exit(code=1)



def _stop_process(process: subprocess.Popen[str]) -> None:
    if process.poll() is not None:
        return

    process.terminate()
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=5)



def _release_smoke_docker_payload() -> dict[str, Any]:
    command = ["uv", "run", "pytest", "-q", "tests/integration/test_docker_runtime_smoke.py"]
    docker_probe = probe_docker_environment()
    output: str | None = None
    if docker_probe.ready:
        output = _run_external_command(command).strip()

    return {
        "command": " ".join(command),
        "docker": _docker_probe_payload(docker_probe),
        "output": output,
        "ready": docker_probe.ready,
    }


def _best_effort_destroy_lab_via_api(*, api_url: str, lab_id: str) -> dict[str, Any] | None:
    with suppress(Exception):
        result = _request_json(api_url=api_url, method="DELETE", path=f"/labs/{lab_id}")
        if isinstance(result, dict):
            return result
    return None


def _best_effort_destroy_lab_via_cli(
    *,
    env_overrides: dict[str, str],
    lab_id: str,
) -> dict[str, Any] | None:
    with suppress(Exception):
        result = _run_cli_json_command(["labs", "destroy", lab_id], env_overrides=env_overrides)
        if isinstance(result, dict):
            return result
    return None


@app.command()
def version() -> None:
    """Print the LabOS CLI version."""
    typer.echo(__version__)


@runtime_app.command("probe-docker")
def runtime_probe_docker() -> None:
    """Probe whether the optional local Docker runtime smoke can run on this host."""
    probe = probe_docker_environment()
    _emit_json(_docker_probe_payload(probe))
    if not probe.ready:
        raise typer.Exit(code=1)


@release_app.command("readiness")
def release_readiness() -> None:
    """Report whether the current checkout is ready for the remaining v0.1 release gate."""
    payload = _release_status_payload()

    _emit_json(payload)
    if payload["blockers"]:
        raise typer.Exit(code=1)


@release_app.command("evidence")
def release_evidence() -> None:
    """Emit a machine-readable release evidence template with current blockers."""
    status = _release_status_payload(include_commit=True)

    docs_validated = [
        "README.md",
        "docs/api.md",
        "docs/cli.md",
        "docs/release-checklist.md",
    ]
    honesty_boundary_confirmed = bool(status["tag_ready"])

    _emit_json(
        {
            **status,
            "docs_validated": docs_validated,
            "honesty_boundary_confirmed": honesty_boundary_confirmed,
            "template": {
                "API smoke": "labos release smoke-docs",
                "CLI smoke": "labos release smoke-cli",
                "Docker smoke": "labos release smoke-docker",
                "Commit": status["commit"],
                "Docker CLI path": status["docker"]["cli_path"] or "unknown",
                "Docker daemon error": status["docker"]["daemon_error"] or "n/a",
                "Docker integration notes": status["docker"]["detail"],
                "Docs validated": ", ".join(docs_validated),
                "Honesty boundary confirmed": "yes" if honesty_boundary_confirmed else "no",
                "Install smoke": "uv sync --extra dev",
                "Lint": "uv run ruff check .",
                "Next action": status["next_action"],
                "Pending steps": "; ".join(status["pending_steps"]),
                "Tag ready": "yes" if status["tag_ready"] else "no",
                "Tests": "uv run pytest -q",
                "Types": "uv run mypy",
            },
        }
    )


@release_app.command("smoke-docs")
def release_smoke_docs(
    api_url: str = typer.Option(
        DEFAULT_API_URL,
        envvar="LABOS_API_URL",
        help="LabOS API base URL.",
    ),
    profile: str = typer.Option("safe-dev", help="Profile to use for the release docs smoke lab."),
    requester_type: str = typer.Option(
        "human",
        help="Requester type recorded for the temporary release smoke lab.",
    ),
) -> None:
    """Exercise the documented health/profile/create/list/destroy flow against a live API."""
    created_lab: dict[str, Any] | None = None
    try:
        health = _request_json(api_url=api_url, method="GET", path="/health")
        profiles = _request_json(api_url=api_url, method="GET", path="/profiles")
        created_lab = _request_json(
            api_url=api_url,
            method="POST",
            path="/labs",
            payload={
                "profile_name": profile,
                "requester_type": requester_type,
                "base_snapshot_id": None,
                "metadata": {"source": "release-smoke-docs"},
            },
        )
        labs = _request_json(api_url=api_url, method="GET", path="/labs")
        destroyed_lab = _request_json(
            api_url=api_url,
            method="DELETE",
            path=f"/labs/{created_lab['id']}",
        )
    except BaseException:
        if isinstance(created_lab, dict) and "id" in created_lab:
            _best_effort_destroy_lab_via_api(api_url=api_url, lab_id=str(created_lab["id"]))
        raise

    _emit_json(
        {
            "api_url": _normalize_api_url(api_url),
            "created_lab": created_lab,
            "destroyed_lab": destroyed_lab,
            "health": health,
            "labs_list_count": len(labs),
            "profile_names": [item["name"] for item in profiles],
            "profile_requested": profile,
            "requester_type": requester_type,
        }
    )


@release_app.command("smoke-cli")
def release_smoke_cli(
    api_url: str = typer.Option(
        DEFAULT_API_URL,
        envvar="LABOS_API_URL",
        help="LabOS API base URL.",
    ),
    profile: str = typer.Option("safe-dev", help="Profile to use for the release CLI smoke lab."),
    requester_type: str = typer.Option(
        "human",
        help="Requester type recorded for the temporary release CLI smoke lab.",
    ),
) -> None:
    """Exercise representative CLI commands against a live API and capture one JSON proof."""
    env_overrides = {"LABOS_API_URL": _normalize_api_url(api_url)}
    created_lab: dict[str, Any] | None = None
    try:
        help_output = _run_cli_command(["--help"], env_overrides=env_overrides)
        help_verified = "LabOS operator CLI" in help_output
        profiles = _run_cli_json_command(["profiles", "list"], env_overrides=env_overrides)
        created_lab = _run_cli_json_command(
            [
                "labs",
                "create",
                profile,
                "--requester-type",
                requester_type,
                "--metadata",
                json.dumps({"source": "release-smoke-cli"}),
            ],
            env_overrides=env_overrides,
        )
        labs = _run_cli_json_command(["labs", "list"], env_overrides=env_overrides)
        retrieved_lab = _run_cli_json_command(
            ["labs", "get", created_lab["id"]],
            env_overrides=env_overrides,
        )
        destroyed_lab = _run_cli_json_command(
            ["labs", "destroy", created_lab["id"]],
            env_overrides=env_overrides,
        )
    except BaseException:
        if isinstance(created_lab, dict) and "id" in created_lab:
            _best_effort_destroy_lab_via_cli(
                env_overrides=env_overrides,
                lab_id=str(created_lab["id"]),
            )
        raise

    _emit_json(
        {
            "api_url": _normalize_api_url(api_url),
            "commands_validated": [
                "labos --help",
                "labos profiles list",
                f"labos labs create {profile} --requester-type {requester_type}",
                "labos labs list",
                f"labos labs get {created_lab['id']}",
                f"labos labs destroy {created_lab['id']}",
            ],
            "created_lab": created_lab,
            "destroyed_lab": destroyed_lab,
            "help_verified": help_verified,
            "listed_lab_count": len(labs),
            "profile_names": [item["name"] for item in profiles],
            "profile_requested": profile,
            "requester_type": requester_type,
            "retrieved_lab": retrieved_lab,
        }
    )


@release_app.command("smoke-docker")
def release_smoke_docker() -> None:
    """Run the optional real-Docker release smoke and emit one JSON proof payload."""
    payload = _release_smoke_docker_payload()
    _emit_json(payload)
    if not payload["ready"]:
        raise typer.Exit(code=1)


@release_app.command("smoke-local")
def release_smoke_local() -> None:
    """Boot a temporary local API, run release smokes, and report Docker honestly."""
    api_url, env_overrides = _prepare_release_smoke_local_environment()
    database_url = env_overrides["LABOS_DATABASE_URL"]
    managed_storage_root = env_overrides["LABOS_MANAGED_STORAGE_ROOT"]
    process: subprocess.Popen[str] | None = None
    cleanup_root = env_overrides.get("LABOS_RELEASE_SMOKE_ROOT")

    try:
        _initialize_database(database_url)
        process = _start_local_api_server(api_url=api_url, env_overrides=env_overrides)
        _wait_for_api_ready(api_url)
        docs_smoke = _run_cli_json_command(["release", "smoke-docs", "--api-url", api_url])
        cli_smoke = _run_cli_json_command(["release", "smoke-cli", "--api-url", api_url])
        docker_smoke = _release_smoke_docker_payload()
    finally:
        if process is not None:
            _stop_process(process)
        if cleanup_root:
            shutil.rmtree(cleanup_root, ignore_errors=True)

    payload = {
        "api_url": api_url,
        "cli_smoke": cli_smoke,
        "docker_smoke": docker_smoke,
        "docs_smoke": docs_smoke,
        "environment": {
            "database_url": database_url,
            "managed_storage_root": managed_storage_root,
        },
        "ready": bool(docker_smoke["ready"]),
    }
    _emit_json(payload)
    if not payload["ready"]:
        raise typer.Exit(code=1)


@profiles_app.command("list")
def profiles_list(
    api_url: str = typer.Option(
        DEFAULT_API_URL,
        envvar="LABOS_API_URL",
        help="LabOS API base URL.",
    ),
) -> None:
    """List built-in policy profiles."""
    _emit_json(_request_json(api_url=api_url, method="GET", path="/profiles"))


@labs_app.command("create")
def labs_create(
    profile_name: str,
    requester_type: str = typer.Option(..., help="Requester type recorded for the lab request."),
    base_snapshot_id: str | None = typer.Option(
        None,
        help="Optional base snapshot ID used to seed the requested lab.",
    ),
    metadata: str | None = typer.Option(
        None,
        help="Optional request metadata as a JSON object.",
    ),
    api_url: str = typer.Option(
        DEFAULT_API_URL,
        envvar="LABOS_API_URL",
        help="LabOS API base URL.",
    ),
) -> None:
    """Create a governed lab request record."""
    payload: dict[str, Any] = {
        "profile_name": profile_name,
        "requester_type": requester_type,
        "base_snapshot_id": base_snapshot_id,
        "metadata": _parse_json_object("metadata", metadata),
    }
    _emit_json(_request_json(api_url=api_url, method="POST", path="/labs", payload=payload))


@labs_app.command("list")
def labs_list(
    api_url: str = typer.Option(
        DEFAULT_API_URL,
        envvar="LABOS_API_URL",
        help="LabOS API base URL.",
    ),
) -> None:
    """List governed lab request records."""
    _emit_json(_request_json(api_url=api_url, method="GET", path="/labs"))


@labs_app.command("get")
def labs_get(
    lab_id: str,
    api_url: str = typer.Option(
        DEFAULT_API_URL,
        envvar="LABOS_API_URL",
        help="LabOS API base URL.",
    ),
) -> None:
    """Get one governed lab request record."""
    _emit_json(_request_json(api_url=api_url, method="GET", path=f"/labs/{lab_id}"))


@labs_app.command("destroy")
def labs_destroy(
    lab_id: str,
    api_url: str = typer.Option(
        DEFAULT_API_URL,
        envvar="LABOS_API_URL",
        help="LabOS API base URL.",
    ),
) -> None:
    """Destroy a governed lab record and remove its managed storage."""
    _emit_json(_request_json(api_url=api_url, method="DELETE", path=f"/labs/{lab_id}"))


@runs_app.command("start")
def runs_start(
    lab_id: str,
    command: str,
    metadata: str | None = typer.Option(
        None,
        help="Optional run metadata as a JSON object.",
    ),
    api_url: str = typer.Option(
        DEFAULT_API_URL,
        envvar="LABOS_API_URL",
        help="LabOS API base URL.",
    ),
) -> None:
    """Create a governed run request record."""
    payload = {
        "lab_id": lab_id,
        "command": command,
        "metadata": _parse_json_object("metadata", metadata),
    }
    _emit_json(_request_json(api_url=api_url, method="POST", path="/runs", payload=payload))


@runs_app.command("list")
def runs_list(
    api_url: str = typer.Option(
        DEFAULT_API_URL,
        envvar="LABOS_API_URL",
        help="LabOS API base URL.",
    ),
) -> None:
    """List governed run request records."""
    _emit_json(_request_json(api_url=api_url, method="GET", path="/runs"))


@snapshots_app.command("list")
def snapshots_list(
    api_url: str = typer.Option(
        DEFAULT_API_URL,
        envvar="LABOS_API_URL",
        help="LabOS API base URL.",
    ),
) -> None:
    """List governed snapshot records."""
    _emit_json(_request_json(api_url=api_url, method="GET", path="/snapshots"))


@snapshots_app.command("create")
def snapshots_create(
    lab_id: str,
    run_id: str | None = typer.Option(None, help="Optional run linked to this snapshot."),
    requester_type: str = typer.Option(
        "human",
        help="Requester type recorded for the snapshot request.",
    ),
    api_url: str = typer.Option(
        DEFAULT_API_URL,
        envvar="LABOS_API_URL",
        help="LabOS API base URL.",
    ),
) -> None:
    """Create a governed snapshot record."""
    _emit_json(
        _request_json(
            api_url=api_url,
            method="POST",
            path="/snapshots",
            payload={"lab_id": lab_id, "run_id": run_id, "requester_type": requester_type},
        )
    )


@exports_app.command("request")
def exports_request(
    lab_id: str,
    source_path: str,
    run_id: str | None = typer.Option(None, help="Optional run linked to this export request."),
    requester_type: str = typer.Option(
        "human",
        help="Requester type recorded for the export request.",
    ),
    api_url: str = typer.Option(
        DEFAULT_API_URL,
        envvar="LABOS_API_URL",
        help="LabOS API base URL.",
    ),
) -> None:
    """Stage an export request through quarantine."""
    _emit_json(
        _request_json(
            api_url=api_url,
            method="POST",
            path="/exports",
            payload={
                "lab_id": lab_id,
                "source_path": source_path,
                "run_id": run_id,
                "requester_type": requester_type,
            },
        )
    )


@exports_app.command("list")
def exports_list(
    api_url: str = typer.Option(
        DEFAULT_API_URL,
        envvar="LABOS_API_URL",
        help="LabOS API base URL.",
    ),
) -> None:
    """List governed export request records."""
    _emit_json(_request_json(api_url=api_url, method="GET", path="/exports"))


@approvals_app.command("list")
def approvals_list(
    api_url: str = typer.Option(
        DEFAULT_API_URL,
        envvar="LABOS_API_URL",
        help="LabOS API base URL.",
    ),
) -> None:
    """List approval records."""
    _emit_json(_request_json(api_url=api_url, method="GET", path="/approvals"))


@approvals_app.command("approve")
def approvals_approve(
    approval_id: str,
    actor: str = typer.Option(..., help="Decision actor recorded in audit metadata."),
    comment: str | None = typer.Option(None, help="Optional decision comment."),
    api_url: str = typer.Option(
        DEFAULT_API_URL,
        envvar="LABOS_API_URL",
        help="LabOS API base URL.",
    ),
) -> None:
    """Approve a pending approval request."""
    _emit_json(
        _request_json(
            api_url=api_url,
            method="POST",
            path=f"/approvals/{approval_id}/approve",
            payload={"actor": actor, "comment": comment},
        )
    )


@approvals_app.command("deny")
def approvals_deny(
    approval_id: str,
    actor: str = typer.Option(..., help="Decision actor recorded in audit metadata."),
    comment: str | None = typer.Option(None, help="Optional decision comment."),
    api_url: str = typer.Option(
        DEFAULT_API_URL,
        envvar="LABOS_API_URL",
        help="LabOS API base URL.",
    ),
) -> None:
    """Deny a pending approval request."""
    _emit_json(
        _request_json(
            api_url=api_url,
            method="POST",
            path=f"/approvals/{approval_id}/deny",
            payload={"actor": actor, "comment": comment},
        )
    )


@events_app.command("list")
def events_list(
    api_url: str = typer.Option(
        DEFAULT_API_URL,
        envvar="LABOS_API_URL",
        help="LabOS API base URL.",
    ),
) -> None:
    """List audit and event records."""
    _emit_json(_request_json(api_url=api_url, method="GET", path="/events"))


@scheduler_app.command("enqueue")
def scheduler_enqueue(
    action: str,
    requester_id: str = typer.Option(..., help="Scheduler identity recorded in audit metadata."),
    profile_name: str | None = typer.Option(None, help="Profile to request for create-lab jobs."),
    lab_id: str | None = typer.Option(None, help="Lab ID to target for start-run jobs."),
    command: str | None = typer.Option(None, help="Command to queue for start-run jobs."),
    scheduled_for: str | None = typer.Option(
        None,
        help="Optional RFC3339 timestamp for when the job becomes dispatchable.",
    ),
    max_attempts: int = typer.Option(3, min=1, help="Maximum scheduler dispatch attempts."),
    api_url: str = typer.Option(
        DEFAULT_API_URL,
        envvar="LABOS_API_URL",
        help="LabOS API base URL.",
    ),
) -> None:
    """Enqueue a scheduler job for governed lab or run requests."""
    normalized_action = action.replace("-", "_")
    if normalized_action not in {"create_lab", "start_run"}:
        typer.echo("action must be one of: create-lab, start-run", err=True)
        raise typer.Exit(code=1)

    _emit_json(
        _request_json(
            api_url=api_url,
            method="POST",
            path="/scheduler/jobs",
            payload={
                "action": normalized_action,
                "requester_id": requester_id,
                "profile_name": profile_name,
                "lab_id": lab_id,
                "command": command,
                "scheduled_for": scheduled_for,
                "max_attempts": max_attempts,
            },
        )
    )


@scheduler_app.command("list")
def scheduler_list(
    api_url: str = typer.Option(
        DEFAULT_API_URL,
        envvar="LABOS_API_URL",
        help="LabOS API base URL.",
    ),
) -> None:
    """List recorded scheduler jobs."""
    _emit_json(_request_json(api_url=api_url, method="GET", path="/scheduler/jobs"))


@scheduler_app.command("dispatch-next")
def scheduler_dispatch_next(
    api_url: str = typer.Option(
        DEFAULT_API_URL,
        envvar="LABOS_API_URL",
        help="LabOS API base URL.",
    ),
) -> None:
    """Dispatch the next eligible scheduler job through the control plane."""
    _emit_json(_request_json(api_url=api_url, method="POST", path="/scheduler/jobs/dispatch-next"))


if __name__ == "__main__":
    app()

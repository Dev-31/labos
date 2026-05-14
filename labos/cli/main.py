from __future__ import annotations

import json
from typing import Any

import httpx
import typer

from labos import __version__

DEFAULT_API_URL = "http://127.0.0.1:8000"

app = typer.Typer(help="LabOS operator CLI")
profiles_app = typer.Typer(help="Inspect built-in policy profiles")
labs_app = typer.Typer(help="Create and inspect governed lab records")
runs_app = typer.Typer(help="Create and inspect governed run records")
snapshots_app = typer.Typer(help="Create and inspect governed snapshot records")
exports_app = typer.Typer(help="Request and inspect governed export records")
approvals_app = typer.Typer(help="Inspect and decide approval requests")
events_app = typer.Typer(help="Inspect audit and event records")
app.add_typer(profiles_app, name="profiles")
app.add_typer(labs_app, name="labs")
app.add_typer(runs_app, name="runs")
app.add_typer(snapshots_app, name="snapshots")
app.add_typer(exports_app, name="exports")
app.add_typer(approvals_app, name="approvals")
app.add_typer(events_app, name="events")


def _normalize_api_url(api_url: str) -> str:
    return api_url.rstrip("/")


def _emit_json(payload: Any) -> None:
    typer.echo(json.dumps(payload, indent=2, sort_keys=True))


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


@app.command()
def version() -> None:
    """Print the LabOS CLI version."""
    typer.echo(__version__)


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

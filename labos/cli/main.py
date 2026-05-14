from __future__ import annotations

import json
from typing import Any

import httpx
import typer

from labos import __version__

DEFAULT_API_URL = "http://127.0.0.1:8000"

app = typer.Typer(help="LabOS operator CLI")
approvals_app = typer.Typer(help="Inspect and decide approval requests")
app.add_typer(approvals_app, name="approvals")


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


@app.command()
def version() -> None:
    """Print the LabOS CLI version."""
    typer.echo(__version__)


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

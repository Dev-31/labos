from __future__ import annotations

import json
from typing import Any

from typer.testing import CliRunner

from labos.cli.main import app

runner = CliRunner()


def test_approvals_list_prints_json(monkeypatch) -> None:
    def fake_request_json(
        *,
        api_url: str,
        method: str,
        path: str,
        payload: dict[str, Any] | None = None,
    ) -> Any:
        assert api_url == "http://127.0.0.1:8000"
        assert method == "GET"
        assert path == "/approvals"
        assert payload is None
        return [{"id": "approval-1", "state": "requested"}]

    monkeypatch.setattr("labos.cli.main._request_json", fake_request_json)

    result = runner.invoke(app, ["approvals", "list"])

    assert result.exit_code == 0
    assert json.loads(result.stdout) == [{"id": "approval-1", "state": "requested"}]


def test_approvals_approve_posts_decision_payload(monkeypatch) -> None:
    def fake_request_json(
        *,
        api_url: str,
        method: str,
        path: str,
        payload: dict[str, Any] | None = None,
    ) -> Any:
        assert api_url == "http://127.0.0.1:8000"
        assert method == "POST"
        assert path == "/approvals/approval-1/approve"
        assert payload == {"actor": "operator", "comment": "manual review accepted"}
        return {"id": "approval-1", "state": "approved"}

    monkeypatch.setattr("labos.cli.main._request_json", fake_request_json)

    result = runner.invoke(
        app,
        [
            "approvals",
            "approve",
            "approval-1",
            "--actor",
            "operator",
            "--comment",
            "manual review accepted",
        ],
    )

    assert result.exit_code == 0
    assert json.loads(result.stdout) == {"id": "approval-1", "state": "approved"}


def test_approvals_deny_posts_decision_payload(monkeypatch) -> None:
    def fake_request_json(
        *,
        api_url: str,
        method: str,
        path: str,
        payload: dict[str, Any] | None = None,
    ) -> Any:
        assert api_url == "http://127.0.0.1:8000"
        assert method == "POST"
        assert path == "/approvals/approval-1/deny"
        assert payload == {"actor": "operator", "comment": "rejected after review"}
        return {"id": "approval-1", "state": "rejected"}

    monkeypatch.setattr("labos.cli.main._request_json", fake_request_json)

    result = runner.invoke(
        app,
        [
            "approvals",
            "deny",
            "approval-1",
            "--actor",
            "operator",
            "--comment",
            "rejected after review",
        ],
    )

    assert result.exit_code == 0
    assert json.loads(result.stdout) == {"id": "approval-1", "state": "rejected"}

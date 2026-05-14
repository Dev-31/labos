from __future__ import annotations

import json
from typing import Any

from typer.testing import CliRunner

from labos.cli.main import app

runner = CliRunner()


def test_scheduler_enqueue_create_lab_posts_request_payload(monkeypatch) -> None:
    def fake_request_json(
        *,
        api_url: str,
        method: str,
        path: str,
        payload: dict[str, Any] | None = None,
    ) -> Any:
        assert api_url == "http://127.0.0.1:8000"
        assert method == "POST"
        assert path == "/scheduler/jobs"
        assert payload == {
            "action": "create_lab",
            "requester_id": "nightly-labs",
            "profile_name": "safe-dev",
            "lab_id": None,
            "command": None,
            "scheduled_for": "2026-05-14T12:00:00Z",
            "max_attempts": 4,
        }
        return {"id": "job-1", "state": "queued"}

    monkeypatch.setattr("labos.cli.main._request_json", fake_request_json)

    result = runner.invoke(
        app,
        [
            "scheduler",
            "enqueue",
            "create-lab",
            "--requester-id",
            "nightly-labs",
            "--profile-name",
            "safe-dev",
            "--scheduled-for",
            "2026-05-14T12:00:00Z",
            "--max-attempts",
            "4",
        ],
    )

    assert result.exit_code == 0
    assert json.loads(result.stdout) == {"id": "job-1", "state": "queued"}


def test_scheduler_list_prints_json(monkeypatch) -> None:
    def fake_request_json(
        *,
        api_url: str,
        method: str,
        path: str,
        payload: dict[str, Any] | None = None,
    ) -> Any:
        assert api_url == "http://127.0.0.1:8000"
        assert method == "GET"
        assert path == "/scheduler/jobs"
        assert payload is None
        return [{"id": "job-1"}]

    monkeypatch.setattr("labos.cli.main._request_json", fake_request_json)

    result = runner.invoke(app, ["scheduler", "list"])

    assert result.exit_code == 0
    assert json.loads(result.stdout) == [{"id": "job-1"}]


def test_scheduler_dispatch_next_posts_request(monkeypatch) -> None:
    def fake_request_json(
        *,
        api_url: str,
        method: str,
        path: str,
        payload: dict[str, Any] | None = None,
    ) -> Any:
        assert api_url == "http://127.0.0.1:8000"
        assert method == "POST"
        assert path == "/scheduler/jobs/dispatch-next"
        assert payload is None
        return {"id": "job-1", "state": "succeeded"}

    monkeypatch.setattr("labos.cli.main._request_json", fake_request_json)

    result = runner.invoke(app, ["scheduler", "dispatch-next"])

    assert result.exit_code == 0
    assert json.loads(result.stdout) == {"id": "job-1", "state": "succeeded"}

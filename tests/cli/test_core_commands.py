from __future__ import annotations

import json
from typing import Any

from typer.testing import CliRunner

from labos.cli.main import app

runner = CliRunner()


def test_profiles_list_prints_json(monkeypatch) -> None:
    def fake_request_json(
        *,
        api_url: str,
        method: str,
        path: str,
        payload: dict[str, Any] | None = None,
    ) -> Any:
        assert api_url == "http://127.0.0.1:8000"
        assert method == "GET"
        assert path == "/profiles"
        assert payload is None
        return [{"name": "safe-dev"}, {"name": "red-zone"}]

    monkeypatch.setattr("labos.cli.main._request_json", fake_request_json)

    result = runner.invoke(app, ["profiles", "list"])

    assert result.exit_code == 0
    assert json.loads(result.stdout) == [{"name": "safe-dev"}, {"name": "red-zone"}]


def test_labs_create_posts_request_payload(monkeypatch) -> None:
    def fake_request_json(
        *,
        api_url: str,
        method: str,
        path: str,
        payload: dict[str, Any] | None = None,
    ) -> Any:
        assert api_url == "http://127.0.0.1:8000"
        assert method == "POST"
        assert path == "/labs"
        assert payload == {
            "profile_name": "safe-dev",
            "requester_type": "human",
            "base_snapshot_id": "snapshot-1",
            "metadata": {"ticket": "ops-42"},
        }
        return {"id": "lab-1", "state": "approved", "profile_name": "safe-dev"}

    monkeypatch.setattr("labos.cli.main._request_json", fake_request_json)

    result = runner.invoke(
        app,
        [
            "labs",
            "create",
            "safe-dev",
            "--requester-type",
            "human",
            "--base-snapshot-id",
            "snapshot-1",
            "--metadata",
            '{"ticket": "ops-42"}',
        ],
    )

    assert result.exit_code == 0
    assert json.loads(result.stdout) == {
        "id": "lab-1",
        "state": "approved",
        "profile_name": "safe-dev",
    }


def test_labs_list_prints_json(monkeypatch) -> None:
    def fake_request_json(
        *,
        api_url: str,
        method: str,
        path: str,
        payload: dict[str, Any] | None = None,
    ) -> Any:
        assert api_url == "http://127.0.0.1:8000"
        assert method == "GET"
        assert path == "/labs"
        assert payload is None
        return [{"id": "lab-1"}]

    monkeypatch.setattr("labos.cli.main._request_json", fake_request_json)

    result = runner.invoke(app, ["labs", "list"])

    assert result.exit_code == 0
    assert json.loads(result.stdout) == [{"id": "lab-1"}]


def test_labs_get_prints_json(monkeypatch) -> None:
    def fake_request_json(
        *,
        api_url: str,
        method: str,
        path: str,
        payload: dict[str, Any] | None = None,
    ) -> Any:
        assert api_url == "http://127.0.0.1:8000"
        assert method == "GET"
        assert path == "/labs/lab-1"
        assert payload is None
        return {"id": "lab-1", "state": "approved"}

    monkeypatch.setattr("labos.cli.main._request_json", fake_request_json)

    result = runner.invoke(app, ["labs", "get", "lab-1"])

    assert result.exit_code == 0
    assert json.loads(result.stdout) == {"id": "lab-1", "state": "approved"}


def test_runs_start_posts_request_payload(monkeypatch) -> None:
    def fake_request_json(
        *,
        api_url: str,
        method: str,
        path: str,
        payload: dict[str, Any] | None = None,
    ) -> Any:
        assert api_url == "http://127.0.0.1:8000"
        assert method == "POST"
        assert path == "/runs"
        assert payload == {
            "lab_id": "lab-1",
            "command": "python -m pytest",
            "metadata": {"source": "cli"},
        }
        return {"id": "run-1", "state": "queued", "lab_id": "lab-1"}

    monkeypatch.setattr("labos.cli.main._request_json", fake_request_json)

    result = runner.invoke(
        app,
        [
            "runs",
            "start",
            "lab-1",
            "python -m pytest",
            "--metadata",
            '{"source": "cli"}',
        ],
    )

    assert result.exit_code == 0
    assert json.loads(result.stdout) == {"id": "run-1", "state": "queued", "lab_id": "lab-1"}


def test_runs_list_prints_json(monkeypatch) -> None:
    def fake_request_json(
        *,
        api_url: str,
        method: str,
        path: str,
        payload: dict[str, Any] | None = None,
    ) -> Any:
        assert api_url == "http://127.0.0.1:8000"
        assert method == "GET"
        assert path == "/runs"
        assert payload is None
        return [{"id": "run-1"}]

    monkeypatch.setattr("labos.cli.main._request_json", fake_request_json)

    result = runner.invoke(app, ["runs", "list"])

    assert result.exit_code == 0
    assert json.loads(result.stdout) == [{"id": "run-1"}]


def test_events_list_prints_json(monkeypatch) -> None:
    def fake_request_json(
        *,
        api_url: str,
        method: str,
        path: str,
        payload: dict[str, Any] | None = None,
    ) -> Any:
        assert api_url == "http://127.0.0.1:8000"
        assert method == "GET"
        assert path == "/events"
        assert payload is None
        return [{"event_type": "lab.requested"}]

    monkeypatch.setattr("labos.cli.main._request_json", fake_request_json)

    result = runner.invoke(app, ["events", "list"])

    assert result.exit_code == 0
    assert json.loads(result.stdout) == [{"event_type": "lab.requested"}]


def test_invalid_metadata_json_exits_with_error() -> None:
    result = runner.invoke(
        app,
        [
            "labs",
            "create",
            "safe-dev",
            "--requester-type",
            "human",
            "--metadata",
            "not-json",
        ],
    )

    assert result.exit_code == 1
    assert "metadata must be a valid JSON object" in result.stderr

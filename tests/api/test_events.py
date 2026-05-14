from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from labos.api.app import create_app
from labos.db.schema import Base
from labos.db.session import build_engine, build_session_factory


def build_test_client(tmp_path: Path) -> TestClient:
    database_url = f"sqlite+pysqlite:///{tmp_path / 'labos-test.db'}"
    engine = build_engine(database_url)
    Base.metadata.create_all(engine)
    session_factory = build_session_factory(database_url)
    return TestClient(
        create_app(
            session_factory=session_factory,
            managed_storage_root=tmp_path / "managed-storage",
        )
    )


def create_lab(client: TestClient, profile_name: str = "safe-dev") -> dict[str, object]:
    response = client.post(
        "/labs",
        json={"profile_name": profile_name, "requester_type": "human"},
    )
    assert response.status_code == 201
    return response.json()


def create_run(client: TestClient, lab_id: str) -> dict[str, object]:
    response = client.post(
        "/runs",
        json={"lab_id": lab_id, "command": "python -m pytest", "requester_type": "human"},
    )
    assert response.status_code == 201
    return response.json()


def test_events_capture_actor_and_resource_metadata_for_major_workflows(tmp_path: Path) -> None:
    client = build_test_client(tmp_path)
    source_lab = create_lab(client)
    run = create_run(client, source_lab["id"])

    snapshot_response = client.post(
        "/snapshots",
        json={"lab_id": source_lab["id"], "run_id": run["id"], "requester_type": "human"},
    )
    assert snapshot_response.status_code == 201
    snapshot = snapshot_response.json()

    target_lab = create_lab(client, profile_name="model-local")
    restore_response = client.post(
        f"/snapshots/{snapshot['id']}/restore",
        json={"lab_id": target_lab["id"], "requester_type": "human"},
    )
    assert restore_response.status_code == 200

    events_response = client.get("/events")
    assert events_response.status_code == 200
    events = events_response.json()

    event_types = [event["event_type"] for event in events]
    assert event_types == [
        "lab.requested",
        "run.queued",
        "snapshot.created",
        "lab.requested",
        "snapshot.restored",
    ]

    assert events[0]["actor_type"] == "human"
    assert events[0]["resource_type"] == "lab"
    assert events[0]["resource_id"] == source_lab["id"]

    assert events[1]["actor_type"] == "human"
    assert events[1]["resource_type"] == "run"
    assert events[1]["resource_id"] == run["id"]
    assert events[1]["run_id"] == run["id"]

    assert events[2]["actor_type"] == "human"
    assert events[2]["resource_type"] == "snapshot"
    assert events[2]["resource_id"] == snapshot["id"]

    assert events[4]["actor_type"] == "human"
    assert events[4]["resource_type"] == "snapshot"
    assert events[4]["resource_id"] == snapshot["id"]
    assert events[4]["lab_id"] == target_lab["id"]


def test_list_events_supports_filters_for_actor_resource_and_run_scope(tmp_path: Path) -> None:
    client = build_test_client(tmp_path)
    lab = create_lab(client)
    run = create_run(client, lab["id"])

    snapshot_response = client.post(
        "/snapshots",
        json={"lab_id": lab["id"], "run_id": run["id"], "requester_type": "human"},
    )
    assert snapshot_response.status_code == 201
    snapshot = snapshot_response.json()

    by_type = client.get("/events", params={"event_type": "run.queued"})
    assert by_type.status_code == 200
    assert [event["event_type"] for event in by_type.json()] == ["run.queued"]

    by_actor = client.get("/events", params={"actor_type": "human"})
    assert by_actor.status_code == 200
    assert len(by_actor.json()) == 3

    by_resource = client.get(
        "/events",
        params={"resource_type": "snapshot", "resource_id": snapshot["id"]},
    )
    assert by_resource.status_code == 200
    assert [event["event_type"] for event in by_resource.json()] == ["snapshot.created"]

    by_run = client.get("/events", params={"run_id": run["id"]})
    assert by_run.status_code == 200
    assert [event["event_type"] for event in by_run.json()] == [
        "run.queued",
        "snapshot.created",
    ]

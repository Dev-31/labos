from __future__ import annotations

import json
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


def test_create_snapshot_captures_workspace_and_manifest(tmp_path: Path) -> None:
    client = build_test_client(tmp_path)
    lab = create_lab(client)
    workspace_path = Path(lab["storage"]["workspace_path"])
    (workspace_path / "notes.txt").write_text("important experiment state")

    run_response = client.post(
        "/runs",
        json={"lab_id": lab["id"], "command": "python -m pytest"},
    )
    assert run_response.status_code == 201
    run_id = run_response.json()["id"]

    create_response = client.post(
        "/snapshots",
        json={"lab_id": lab["id"], "run_id": run_id},
    )

    assert create_response.status_code == 201
    created = create_response.json()
    assert created["lab_id"] == lab["id"]
    assert created["run_id"] == run_id
    assert created["profile_name"] == "safe-dev"
    assert created["runtime_class"] == "container"
    assert created["state"] == "created"
    assert len(created["sha256"]) == 64
    assert created["size_bytes"] > 0

    archive_path = Path(created["backend_ref"])
    manifest_path = Path(created["manifest_path"])
    assert archive_path.exists() is True
    assert manifest_path.exists() is True
    assert archive_path.parent == workspace_path.parent / "snapshots"

    manifest = json.loads(manifest_path.read_text())
    assert manifest["lab_id"] == lab["id"]
    assert manifest["run_id"] == run_id
    assert manifest["profile_name"] == "safe-dev"
    assert manifest["runtime_class"] == "container"
    assert manifest["state"] == "created"
    assert manifest["sha256"] == created["sha256"]
    assert manifest["workspace_path"] == str(workspace_path)

    list_response = client.get("/snapshots")

    assert list_response.status_code == 200
    assert list_response.json()[0]["id"] == created["id"]
    assert list_response.json()[0]["manifest_path"] == created["manifest_path"]


def test_restore_snapshot_rehydrates_workspace_contents(tmp_path: Path) -> None:
    client = build_test_client(tmp_path)
    source_lab = create_lab(client)
    source_workspace_path = Path(source_lab["storage"]["workspace_path"])
    original_file = source_workspace_path / "notes.txt"
    original_file.write_text("baseline state")

    snapshot_response = client.post("/snapshots", json={"lab_id": source_lab["id"]})
    assert snapshot_response.status_code == 201
    snapshot = snapshot_response.json()

    target_lab = create_lab(client, profile_name="model-local")
    target_workspace_path = Path(target_lab["storage"]["workspace_path"])
    (target_workspace_path / "notes.txt").write_text("mutated state")
    (target_workspace_path / "extra.txt").write_text("remove me")

    restore_response = client.post(
        f"/snapshots/{snapshot['id']}/restore",
        json={"lab_id": target_lab["id"]},
    )

    assert restore_response.status_code == 200
    restored = restore_response.json()
    assert restored["id"] == snapshot["id"]
    assert restored["state"] == "restored"
    assert restored["restored_lab_id"] == target_lab["id"]
    assert restored["restored_at"] is not None
    assert (target_workspace_path / "notes.txt").read_text() == "baseline state"
    assert (target_workspace_path / "extra.txt").exists() is False


def test_snapshot_creation_rejects_unsupported_microvm_runtime(tmp_path: Path) -> None:
    client = build_test_client(tmp_path)
    lab = create_lab(client, profile_name="red-zone")

    response = client.post("/snapshots", json={"lab_id": lab["id"]})

    assert response.status_code == 409
    assert response.json() == {
        "detail": "unsupported_snapshot_runtime",
        "resource": "snapshot",
    }


def test_snapshot_creation_requires_existing_run_when_run_id_is_supplied(tmp_path: Path) -> None:
    client = build_test_client(tmp_path)
    lab = create_lab(client)

    response = client.post(
        "/snapshots",
        json={"lab_id": lab["id"], "run_id": "run-missing"},
    )

    assert response.status_code == 404
    assert response.json() == {"detail": "resource_not_found", "resource": "run"}

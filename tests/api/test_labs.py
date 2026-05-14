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


def test_create_list_and_get_lab(tmp_path: Path) -> None:
    client = build_test_client(tmp_path)

    create_response = client.post(
        "/labs",
        json={"profile_name": "safe-dev", "requester_type": "human"},
    )

    assert create_response.status_code == 201
    created = create_response.json()
    assert created["profile_name"] == "safe-dev"
    assert created["runtime_class"] == "container"
    assert created["state"] == "approved"
    assert created["storage"]["workspace_path"].endswith("/labs/" + created["id"] + "/workspace")
    assert created["storage"]["persistence_mode"] == "ephemeral"

    list_response = client.get("/labs")

    assert list_response.status_code == 200
    assert [item["id"] for item in list_response.json()] == [created["id"]]

    get_response = client.get(f"/labs/{created['id']}")

    assert get_response.status_code == 200
    assert get_response.json() == created

    approvals_response = client.get("/approvals")
    assert approvals_response.status_code == 200
    assert approvals_response.json() == []


def test_high_risk_lab_creation_records_pending_approval(tmp_path: Path) -> None:
    client = build_test_client(tmp_path)

    create_response = client.post(
        "/labs",
        json={"profile_name": "red-zone", "requester_type": "human"},
    )

    assert create_response.status_code == 201
    created = create_response.json()
    assert created["state"] == "pending_approval"

    approvals_response = client.get("/approvals")
    assert approvals_response.status_code == 200
    approvals = approvals_response.json()
    assert len(approvals) == 1
    assert approvals[0]["resource_type"] == "lab"
    assert approvals[0]["resource_id"] == created["id"]
    assert approvals[0]["action"] == "lab.create"
    assert approvals[0]["state"] == "requested"
    assert approvals[0]["approved"] is False


def test_approving_lab_request_advances_lab_to_approved(tmp_path: Path) -> None:
    client = build_test_client(tmp_path)

    create_response = client.post(
        "/labs",
        json={"profile_name": "red-zone", "requester_type": "human"},
    )
    approval = client.get("/approvals").json()[0]

    decision_response = client.post(
        f"/approvals/{approval['id']}/approve",
        json={"actor": "operator", "comment": "manual review accepted"},
    )

    assert decision_response.status_code == 200
    decided = decision_response.json()
    assert decided["state"] == "approved"
    assert decided["approved"] is True
    assert decided["decision_comment"] == "manual review accepted"
    assert decided["decided_by"] == "operator"

    get_lab_response = client.get(f"/labs/{create_response.json()['id']}")
    assert get_lab_response.status_code == 200
    assert get_lab_response.json()["state"] == "approved"


def test_denying_lab_request_marks_lab_failed(tmp_path: Path) -> None:
    client = build_test_client(tmp_path)

    create_response = client.post(
        "/labs",
        json={"profile_name": "red-zone", "requester_type": "human"},
    )
    approval = client.get("/approvals").json()[0]

    decision_response = client.post(
        f"/approvals/{approval['id']}/deny",
        json={"actor": "operator", "comment": "profile denied for this request"},
    )

    assert decision_response.status_code == 200
    decided = decision_response.json()
    assert decided["state"] == "rejected"
    assert decided["approved"] is False
    assert decided["decision_comment"] == "profile denied for this request"

    get_lab_response = client.get(f"/labs/{create_response.json()['id']}")
    assert get_lab_response.status_code == 200
    assert get_lab_response.json()["state"] == "failed"


def test_create_lab_returns_custom_validation_errors(tmp_path: Path) -> None:
    client = build_test_client(tmp_path)

    response = client.post("/labs", json={"profile_name": "safe-dev"})

    assert response.status_code == 422
    payload = response.json()
    assert payload["detail"] == "validation_error"
    assert payload["errors"][0]["field"] == "body.requester_type"


def test_get_missing_lab_returns_custom_404_shape(tmp_path: Path) -> None:
    client = build_test_client(tmp_path)

    response = client.get("/labs/lab-missing")

    assert response.status_code == 404
    assert response.json() == {"detail": "resource_not_found", "resource": "lab"}


def test_destroy_lab_marks_record_destroyed_and_cleans_managed_storage(tmp_path: Path) -> None:
    client = build_test_client(tmp_path)

    create_response = client.post(
        "/labs",
        json={"profile_name": "safe-dev", "requester_type": "human"},
    )
    created = create_response.json()
    workspace_path = Path(created["storage"]["workspace_path"])
    exported_file = Path(created["storage"]["exports_path"]) / "artifact.txt"
    workspace_path.mkdir(parents=True, exist_ok=True)
    (workspace_path / "session.txt").write_text("lab state")
    exported_file.write_text("artifact")

    destroy_response = client.delete(f"/labs/{created['id']}")

    assert destroy_response.status_code == 200
    destroyed = destroy_response.json()
    assert destroyed["id"] == created["id"]
    assert destroyed["state"] == "destroyed"
    assert Path(destroyed["storage"]["root_path"]).exists() is False

    get_response = client.get(f"/labs/{created['id']}")
    assert get_response.status_code == 200
    assert get_response.json()["state"] == "destroyed"

    events_response = client.get(
        "/events",
        params={"resource_type": "lab", "resource_id": created["id"]},
    )
    assert events_response.status_code == 200
    event_types = [item["event_type"] for item in events_response.json()]
    assert event_types == ["lab.requested", "lab.destroyed"]

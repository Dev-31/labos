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

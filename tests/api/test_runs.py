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
    return TestClient(create_app(session_factory=session_factory))


def create_lab(client: TestClient) -> str:
    response = client.post(
        "/labs",
        json={"profile_name": "safe-dev", "requester_type": "human"},
    )
    assert response.status_code == 201
    return response.json()["id"]


def test_create_list_and_get_runs(tmp_path: Path) -> None:
    client = build_test_client(tmp_path)
    lab_id = create_lab(client)

    create_response = client.post(
        "/runs",
        json={"lab_id": lab_id, "command": "python -m pytest"},
    )

    assert create_response.status_code == 201
    created = create_response.json()
    assert created["lab_id"] == lab_id
    assert created["state"] == "queued"
    assert created["command"] == "python -m pytest"

    list_response = client.get("/runs")

    assert list_response.status_code == 200
    assert [item["id"] for item in list_response.json()] == [created["id"]]

    get_response = client.get(f"/runs/{created['id']}")

    assert get_response.status_code == 200
    assert get_response.json() == created


def test_create_run_requires_existing_lab(tmp_path: Path) -> None:
    client = build_test_client(tmp_path)

    response = client.post(
        "/runs",
        json={"lab_id": "lab-missing", "command": "python -m pytest"},
    )

    assert response.status_code == 404
    assert response.json() == {"detail": "resource_not_found", "resource": "lab"}


def test_get_missing_run_returns_custom_404_shape(tmp_path: Path) -> None:
    client = build_test_client(tmp_path)

    response = client.get("/runs/run-missing")

    assert response.status_code == 404
    assert response.json() == {"detail": "resource_not_found", "resource": "run"}

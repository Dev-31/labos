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


def test_profiles_list_returns_builtin_profiles(tmp_path: Path) -> None:
    client = build_test_client(tmp_path)

    response = client.get("/profiles")

    assert response.status_code == 200
    payload = response.json()
    assert [item["name"] for item in payload] == [
        "model-local",
        "red-zone",
        "research-persistent",
        "safe-dev",
    ]
    assert payload[0]["runtime_class"] == "container"


def test_profile_detail_returns_builtin_profile(tmp_path: Path) -> None:
    client = build_test_client(tmp_path)

    response = client.get("/profiles/red-zone")

    assert response.status_code == 200
    assert response.json()["risk_class"] == "critical"
    assert response.json()["approval_on_start"] is True


def test_profile_detail_returns_custom_404_shape(tmp_path: Path) -> None:
    client = build_test_client(tmp_path)

    response = client.get("/profiles/does-not-exist")

    assert response.status_code == 404
    assert response.json() == {"detail": "resource_not_found", "resource": "profile"}

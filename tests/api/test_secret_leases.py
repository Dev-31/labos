from pathlib import Path

from fastapi.testclient import TestClient

from labos.api.app import create_app
from labos.core.policy_engine import PolicyEngine
from labos.db.schema import Base
from labos.db.session import build_engine, build_session_factory


def build_test_client(tmp_path: Path, monkeypatch) -> TestClient:
    database_url = f"sqlite+pysqlite:///{tmp_path / 'labos-secret-leases.db'}"
    engine = build_engine(database_url)
    Base.metadata.create_all(engine)
    session_factory = build_session_factory(database_url)
    policy = PolicyEngine()
    policy.profiles["safe-dev"] = policy.profiles["safe-dev"].model_copy(
        update={"allowed_secret_names": ["API_TOKEN"]}
    )
    monkeypatch.setenv("LABOS_SECRET_API_TOKEN", "super-secret")
    return TestClient(
        create_app(
            session_factory=session_factory,
            managed_storage_root=tmp_path / "managed-storage",
            policy_engine=policy,
        )
    )


def test_create_list_and_revoke_secret_leases(tmp_path: Path, monkeypatch) -> None:
    client = build_test_client(tmp_path, monkeypatch)

    lab_response = client.post(
        "/labs",
        json={"profile_name": "safe-dev", "requester_type": "human"},
    )
    lab_id = lab_response.json()["id"]

    create_lease = client.post(
        f"/labs/{lab_id}/secret-leases",
        json={"secret_name": "API_TOKEN", "requester_type": "human", "ttl_minutes": 30},
    )

    assert create_lease.status_code == 201
    created = create_lease.json()
    assert created["lab_id"] == lab_id
    assert created["secret_name"] == "API_TOKEN"
    assert created["approved"] is True
    assert created["revoked_at"] is None

    listed = client.get(f"/labs/{lab_id}/secret-leases")
    assert listed.status_code == 200
    assert [item["id"] for item in listed.json()] == [created["id"]]

    issue_events = client.get("/events", params={"event_type": "secret_lease.issued"})
    assert issue_events.status_code == 200
    assert issue_events.json()[0]["resource_id"] == created["id"]

    revoke_response = client.post(
        f"/secret-leases/{created['id']}/revoke",
        json={"actor": "operator", "reason": "end of run"},
    )
    assert revoke_response.status_code == 200
    revoked = revoke_response.json()
    assert revoked["id"] == created["id"]
    assert revoked["revoked_at"] is not None

    revoke_events = client.get("/events", params={"event_type": "secret_lease.revoked"})
    assert revoke_events.status_code == 200
    assert revoke_events.json()[0]["resource_id"] == created["id"]


def test_create_secret_lease_rejects_unapproved_secret_name(tmp_path: Path, monkeypatch) -> None:
    client = build_test_client(tmp_path, monkeypatch)

    lab_response = client.post(
        "/labs",
        json={"profile_name": "safe-dev", "requester_type": "human"},
    )
    lab_id = lab_response.json()["id"]

    response = client.post(
        f"/labs/{lab_id}/secret-leases",
        json={"secret_name": "OPENAI_API_KEY", "requester_type": "human", "ttl_minutes": 30},
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "secret_name is not allowed by profile"



def test_create_secret_lease_returns_clear_error_when_secret_value_missing(
    tmp_path: Path, monkeypatch
) -> None:
    client = build_test_client(tmp_path, monkeypatch)
    monkeypatch.delenv("LABOS_SECRET_API_TOKEN", raising=False)

    lab_response = client.post(
        "/labs",
        json={"profile_name": "safe-dev", "requester_type": "human"},
    )
    lab_id = lab_response.json()["id"]

    response = client.post(
        f"/labs/{lab_id}/secret-leases",
        json={"secret_name": "API_TOKEN", "requester_type": "human", "ttl_minutes": 30},
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "secret value not found for API_TOKEN"

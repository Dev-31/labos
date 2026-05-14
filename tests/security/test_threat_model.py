from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient

from labos.api.app import create_app
from labos.core.policy_engine import PolicyEngine
from labos.core.policy_models import NetworkMode
from labos.db.schema import Base
from labos.db.session import build_engine, build_session_factory


def build_test_client(tmp_path: Path) -> TestClient:
    database_url = f"sqlite+pysqlite:///{tmp_path / 'labos-security-test.db'}"
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


def test_threat_model_defaults_to_empty_secret_injection() -> None:
    decision = PolicyEngine().validate_request(
        profile_name="safe-dev",
        requested_overrides={},
        requester_type="human",
    )

    assert decision.injected_secrets == []


def test_threat_model_red_zone_policy_denies_network_by_default() -> None:
    decision = PolicyEngine().validate_request(
        profile_name="red-zone",
        requested_overrides={},
        requester_type="human",
    )

    assert decision.network_mode is NetworkMode.DENY


def test_threat_model_blocks_home_directory_host_mounts() -> None:
    engine = PolicyEngine()
    engine.profiles["mount-enabled"] = engine.profiles["safe-dev"].model_copy(
        update={"name": "mount-enabled", "allow_host_mounts": True}
    )

    try:
        engine.validate_request(
            profile_name="mount-enabled",
            requested_overrides={"host_mounts": ["/home/ubuntu/.ssh:/lab/secrets"]},
            requester_type="human",
        )
    except ValueError as exc:
        assert str(exc) == "host mounts under home directories are forbidden"
    else:
        raise AssertionError("expected home directory host mount to be rejected")


def test_threat_model_blocks_docker_socket_host_mounts() -> None:
    engine = PolicyEngine()
    engine.profiles["mount-enabled"] = engine.profiles["safe-dev"].model_copy(
        update={"name": "mount-enabled", "allow_host_mounts": True}
    )

    try:
        engine.validate_request(
            profile_name="mount-enabled",
            requested_overrides={"host_mounts": ["/var/run/docker.sock:/var/run/docker.sock"]},
            requester_type="human",
        )
    except ValueError as exc:
        assert str(exc) == "Docker socket mounts are forbidden"
    else:
        raise AssertionError("expected Docker socket host mount to be rejected")


def test_threat_model_export_quarantine_cannot_be_bypassed_via_path_escape(tmp_path: Path) -> None:
    client = build_test_client(tmp_path)
    lab = create_lab(client)
    workspace_path = Path(lab["storage"]["workspace_path"])
    (workspace_path / "secret.txt").write_text("do not export directly")

    response = client.post(
        "/exports",
        json={
            "lab_id": lab["id"],
            "source_path": "/lab/exports/../workspace/secret.txt",
        },
    )

    assert response.status_code == 409
    assert response.json() == {
        "detail": "export path escapes managed exports root",
        "resource": "export",
    }

    events_response = client.get("/events", params={"resource_type": "export"})
    assert events_response.status_code == 200
    assert events_response.json() == []


def test_threat_model_records_actor_audit_trail_for_high_risk_approval(tmp_path: Path) -> None:
    client = build_test_client(tmp_path)
    lab = create_lab(client, profile_name="red-zone")
    approvals_response = client.get("/approvals")
    assert approvals_response.status_code == 200
    approval = approvals_response.json()[0]

    response = client.post(
        f"/approvals/{approval['id']}/approve",
        json={"actor": "security-operator", "comment": "risk accepted"},
    )

    assert response.status_code == 200
    events_response = client.get(
        "/events",
        params={
            "event_type": "approval.approved",
            "resource_type": "approval",
            "resource_id": approval["id"],
            "lab_id": lab["id"],
        },
    )
    assert events_response.status_code == 200
    events = events_response.json()
    assert len(events) == 1
    assert events[0]["actor_type"] == "human"
    assert events[0]["actor_id"] == "security-operator"
    payload = json.loads(events[0]["payload_json"])
    assert payload["action"] == "lab.create"
    assert payload["actor"] == "security-operator"

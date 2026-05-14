from __future__ import annotations

import hashlib
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


def create_run(client: TestClient, lab_id: str) -> str:
    response = client.post(
        "/runs",
        json={"lab_id": lab_id, "command": "python -m pytest"},
    )
    assert response.status_code == 201
    return response.json()["id"]


def test_create_export_stages_artifact_and_records_provenance(tmp_path: Path) -> None:
    client = build_test_client(tmp_path)
    lab = create_lab(client)
    run_id = create_run(client, lab["id"])
    exports_path = Path(lab["storage"]["exports_path"])
    artifact_path = exports_path / "report.txt"
    artifact_contents = b"artifact payload\n"
    artifact_path.write_bytes(artifact_contents)

    response = client.post(
        "/exports",
        json={
            "lab_id": lab["id"],
            "run_id": run_id,
            "source_path": "/lab/exports/report.txt",
        },
    )

    assert response.status_code == 201
    payload = response.json()
    assert payload["lab_id"] == lab["id"]
    assert payload["run_id"] == run_id
    assert payload["source_path"] == "/lab/exports/report.txt"
    assert payload["state"] == "quarantined"
    assert payload["approval_required"] is False
    assert payload["size_bytes"] == len(artifact_contents)
    assert payload["sha256"] == hashlib.sha256(artifact_contents).hexdigest()
    quarantine_path = Path(payload["quarantine_path"])
    assert quarantine_path.exists() is True
    assert quarantine_path.read_bytes() == artifact_contents
    assert payload["released_path"] is None
    assert payload["denial_reason"] is None

    events_response = client.get("/events", params={"resource_type": "export"})
    assert events_response.status_code == 200
    event_types = [event["event_type"] for event in events_response.json()]
    assert event_types == ["export.requested", "export.staged"]

    approvals_response = client.get("/approvals")
    assert approvals_response.status_code == 200
    assert approvals_response.json() == []


def test_release_export_copies_artifact_to_approved_area(tmp_path: Path) -> None:
    client = build_test_client(tmp_path)
    lab = create_lab(client)
    exports_path = Path(lab["storage"]["exports_path"])
    (exports_path / "report.txt").write_text("ready for release")

    create_response = client.post(
        "/exports",
        json={"lab_id": lab["id"], "source_path": "/lab/exports/report.txt"},
    )
    assert create_response.status_code == 201
    export_id = create_response.json()["id"]

    release_response = client.post(f"/exports/{export_id}/release")

    assert release_response.status_code == 200
    released = release_response.json()
    assert released["state"] == "released"
    assert released["released_path"] is not None
    released_path = Path(released["released_path"])
    assert released_path.exists() is True
    assert released_path.read_text() == "ready for release"

    events_response = client.get("/events", params={"resource_type": "export"})
    assert events_response.status_code == 200
    event_types = [event["event_type"] for event in events_response.json()]
    assert event_types == ["export.requested", "export.staged", "export.released"]


def test_high_risk_export_requires_approval_before_release(tmp_path: Path) -> None:
    client = build_test_client(tmp_path)
    lab = create_lab(client, profile_name="red-zone")
    exports_path = Path(lab["storage"]["exports_path"])
    (exports_path / "report.txt").write_text("sensitive artifact")

    create_response = client.post(
        "/exports",
        json={"lab_id": lab["id"], "source_path": "/lab/exports/report.txt"},
    )
    assert create_response.status_code == 201
    payload = create_response.json()
    assert payload["approval_required"] is True

    approvals_response = client.get("/approvals")
    assert approvals_response.status_code == 200
    approvals = approvals_response.json()
    export_approvals = [approval for approval in approvals if approval["resource_type"] == "export"]
    assert len(export_approvals) == 1
    assert export_approvals[0]["resource_id"] == payload["id"]
    assert export_approvals[0]["action"] == "export.release"
    assert export_approvals[0]["state"] == "requested"

    release_response = client.post(f"/exports/{payload['id']}/release")

    assert release_response.status_code == 409
    assert release_response.json() == {
        "detail": "export_approval_required",
        "resource": "export",
    }

    events_response = client.get("/events")
    assert events_response.status_code == 200
    event_types = [event["event_type"] for event in events_response.json()]
    assert event_types[-1] == "export.release_blocked"
    assert event_types.count("approval.requested") == 2
    assert "export.requested" in event_types
    assert "export.staged" in event_types


def test_approving_high_risk_export_unblocks_release(tmp_path: Path) -> None:
    client = build_test_client(tmp_path)
    lab = create_lab(client, profile_name="red-zone")
    exports_path = Path(lab["storage"]["exports_path"])
    (exports_path / "report.txt").write_text("sensitive artifact")

    create_response = client.post(
        "/exports",
        json={"lab_id": lab["id"], "source_path": "/lab/exports/report.txt"},
    )
    assert create_response.status_code == 201
    export_payload = create_response.json()
    approval = [
        item for item in client.get("/approvals").json() if item["resource_type"] == "export"
    ][0]

    decision_response = client.post(
        f"/approvals/{approval['id']}/approve",
        json={"actor": "operator", "comment": "artifact cleared for release"},
    )
    assert decision_response.status_code == 200
    assert decision_response.json()["state"] == "approved"

    release_response = client.post(f"/exports/{export_payload['id']}/release")

    assert release_response.status_code == 200
    released = release_response.json()
    assert released["state"] == "released"
    assert released["approval_required"] is False


def test_denying_high_risk_export_via_approval_marks_export_rejected(tmp_path: Path) -> None:
    client = build_test_client(tmp_path)
    lab = create_lab(client, profile_name="red-zone")
    exports_path = Path(lab["storage"]["exports_path"])
    (exports_path / "report.txt").write_text("sensitive artifact")

    create_response = client.post(
        "/exports",
        json={"lab_id": lab["id"], "source_path": "/lab/exports/report.txt"},
    )
    assert create_response.status_code == 201
    export_payload = create_response.json()
    approval = [
        item for item in client.get("/approvals").json() if item["resource_type"] == "export"
    ][0]

    decision_response = client.post(
        f"/approvals/{approval['id']}/deny",
        json={"actor": "operator", "comment": "artifact denied by manual review"},
    )
    assert decision_response.status_code == 200
    assert decision_response.json()["state"] == "rejected"

    get_exports_response = client.get("/exports")
    assert get_exports_response.status_code == 200
    export = get_exports_response.json()[0]
    assert export["id"] == export_payload["id"]
    assert export["state"] == "rejected"
    assert export["denial_reason"] == "artifact denied by manual review"


def test_deny_export_marks_request_rejected(tmp_path: Path) -> None:
    client = build_test_client(tmp_path)
    lab = create_lab(client)
    exports_path = Path(lab["storage"]["exports_path"])
    (exports_path / "report.txt").write_text("deny me")

    create_response = client.post(
        "/exports",
        json={"lab_id": lab["id"], "source_path": "/lab/exports/report.txt"},
    )
    assert create_response.status_code == 201
    export_id = create_response.json()["id"]

    deny_response = client.post(
        f"/exports/{export_id}/deny",
        json={"reason": "manual review rejected artifact"},
    )

    assert deny_response.status_code == 200
    denied = deny_response.json()
    assert denied["state"] == "rejected"
    assert denied["denial_reason"] == "manual review rejected artifact"
    assert denied["released_path"] is None

    events_response = client.get("/events", params={"resource_type": "export"})
    assert events_response.status_code == 200
    event_types = [event["event_type"] for event in events_response.json()]
    assert event_types == ["export.requested", "export.staged", "export.denied"]

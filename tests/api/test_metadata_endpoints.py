from pathlib import Path
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from labos.api.app import create_app
from labos.db.schema import ApprovalRow, Base, EventRow, ExportRow, LabRow, SnapshotRow
from labos.db.session import build_engine, build_session_factory


def build_test_client(tmp_path: Path) -> tuple[TestClient, Session]:
    database_url = f"sqlite+pysqlite:///{tmp_path / 'labos-test.db'}"
    engine = build_engine(database_url)
    Base.metadata.create_all(engine)
    session_factory = build_session_factory(database_url)
    client = TestClient(create_app(session_factory=session_factory))
    session = session_factory()
    return client, session


def seed_lab(session: Session) -> str:
    lab = LabRow(
        id=str(uuid4()),
        profile_name="safe-dev",
        state="approved",
        runtime_class="container",
    )
    session.add(lab)
    session.commit()
    return lab.id


def test_list_approvals_snapshots_exports_and_events(tmp_path: Path) -> None:
    client, session = build_test_client(tmp_path)
    lab_id = seed_lab(session)

    approval = ApprovalRow(id=str(uuid4()), lab_id=lab_id, action="start", approved=False)
    snapshot = SnapshotRow(id=str(uuid4()), lab_id=lab_id, backend_ref="snapshot://lab/1")
    export = ExportRow(
        id=str(uuid4()),
        lab_id=lab_id,
        source_path="/lab/exports/result.txt",
        sha256="a" * 64,
    )
    event = EventRow(
        id=str(uuid4()),
        lab_id=lab_id,
        run_id=None,
        event_type="lab.created",
        payload_json='{"status":"ok"}',
    )
    session.add_all([approval, snapshot, export, event])
    session.commit()
    approval_id = approval.id
    snapshot_id = snapshot.id
    export_id = export.id
    event_id = event.id
    session.close()

    approvals_response = client.get("/approvals")
    snapshots_response = client.get("/snapshots")
    exports_response = client.get("/exports")
    events_response = client.get("/events")

    assert approvals_response.status_code == 200
    assert approvals_response.json()[0]["id"] == approval_id
    assert approvals_response.json()[0]["action"] == "start"
    assert approvals_response.json()[0]["approved"] is False

    assert snapshots_response.status_code == 200
    assert snapshots_response.json()[0]["id"] == snapshot_id
    assert snapshots_response.json()[0]["backend_ref"] == "snapshot://lab/1"

    assert exports_response.status_code == 200
    assert exports_response.json()[0]["id"] == export_id
    assert exports_response.json()[0]["source_path"] == "/lab/exports/result.txt"
    assert exports_response.json()[0]["sha256"] == "a" * 64

    assert events_response.status_code == 200
    assert events_response.json()[0]["id"] == event_id
    assert events_response.json()[0]["event_type"] == "lab.created"
    assert events_response.json()[0]["payload_json"] == '{"status":"ok"}'

from datetime import UTC, datetime, timedelta
from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from labos.api.app import create_app
from labos.db.schema import ApprovalRow, Base, EventRow, LabRow, RunRow, SchedulerJobRow
from labos.db.session import build_engine, build_session_factory


def build_test_client(tmp_path: Path) -> tuple[TestClient, Session]:
    database_url = f"sqlite+pysqlite:///{tmp_path / 'labos-scheduler.db'}"
    engine = build_engine(database_url)
    Base.metadata.create_all(engine)
    session_factory = build_session_factory(database_url)
    client = TestClient(create_app(session_factory=session_factory))
    session = session_factory()
    return client, session


def test_enqueue_scheduler_job_records_queue_state(tmp_path: Path) -> None:
    client, session = build_test_client(tmp_path)
    scheduled_for = (datetime.now(UTC) + timedelta(minutes=5)).isoformat()

    response = client.post(
        "/scheduler/jobs",
        json={
            "action": "create_lab",
            "profile_name": "safe-dev",
            "requester_id": "nightly-research",
            "scheduled_for": scheduled_for,
        },
    )

    assert response.status_code == 201
    payload = response.json()
    assert payload["action"] == "create_lab"
    assert payload["state"] == "queued"
    assert payload["requester_id"] == "nightly-research"
    assert payload["profile_name"] == "safe-dev"
    assert payload["lab_id"] is None
    assert payload["command"] is None
    assert payload["attempt_count"] == 0
    assert payload["max_attempts"] == 3

    stored = session.get(SchedulerJobRow, payload["id"])
    assert stored is not None
    assert stored.action == "create_lab"
    assert stored.state == "queued"
    assert stored.requester_id == "nightly-research"
    assert stored.profile_name == "safe-dev"


def test_dispatch_scheduler_lab_job_uses_lab_creation_policy_path(tmp_path: Path) -> None:
    client, session = build_test_client(tmp_path)
    enqueue_response = client.post(
        "/scheduler/jobs",
        json={
            "action": "create_lab",
            "profile_name": "research-persistent",
            "requester_id": "cron-research",
        },
    )
    job_id = enqueue_response.json()["id"]

    dispatch_response = client.post("/scheduler/jobs/dispatch-next")

    assert dispatch_response.status_code == 200
    payload = dispatch_response.json()
    assert payload["id"] == job_id
    assert payload["state"] == "succeeded"
    assert payload["result_resource_type"] == "lab"
    created_lab_id = payload["result_resource_id"]
    assert created_lab_id is not None

    created_lab = session.get(LabRow, created_lab_id)
    assert created_lab is not None
    assert created_lab.profile_name == "research-persistent"
    assert created_lab.state == "pending_approval"

    approvals = session.scalars(
        select(ApprovalRow).where(ApprovalRow.resource_id == created_lab_id)
    ).all()
    assert len(approvals) == 1
    assert approvals[0].action == "lab.create"
    assert approvals[0].requested_by == "scheduler"

    job_event_types = {
        row.event_type
        for row in session.scalars(select(EventRow).where(EventRow.resource_id == job_id)).all()
    }
    assert {
        "scheduler_job.enqueued",
        "scheduler_job.dispatched",
        "scheduler_job.succeeded",
    }.issubset(job_event_types)


def test_dispatch_scheduler_run_job_creates_run_record(tmp_path: Path) -> None:
    client, session = build_test_client(tmp_path)
    create_lab_response = client.post(
        "/labs",
        json={"profile_name": "safe-dev", "requester_type": "human"},
    )
    lab_id = create_lab_response.json()["id"]

    enqueue_response = client.post(
        "/scheduler/jobs",
        json={
            "action": "start_run",
            "lab_id": lab_id,
            "command": "python -m pytest",
            "requester_id": "nightly-runs",
        },
    )
    job_id = enqueue_response.json()["id"]

    dispatch_response = client.post("/scheduler/jobs/dispatch-next")

    assert dispatch_response.status_code == 200
    payload = dispatch_response.json()
    assert payload["id"] == job_id
    assert payload["state"] == "succeeded"
    assert payload["result_resource_type"] == "run"
    run_id = payload["result_resource_id"]
    assert run_id is not None

    run_row = session.get(RunRow, run_id)
    assert run_row is not None
    assert run_row.lab_id == lab_id
    assert run_row.command == "python -m pytest"
    assert run_row.state == "queued"


def test_scheduler_retries_then_fails_after_max_attempts(tmp_path: Path) -> None:
    client, session = build_test_client(tmp_path)
    enqueue_response = client.post(
        "/scheduler/jobs",
        json={
            "action": "start_run",
            "lab_id": "missing-lab",
            "command": "python -m pytest",
            "requester_id": "retry-runs",
            "max_attempts": 2,
        },
    )
    job_id = enqueue_response.json()["id"]

    first_dispatch = client.post("/scheduler/jobs/dispatch-next")
    second_dispatch = client.post("/scheduler/jobs/dispatch-next")

    assert first_dispatch.status_code == 200
    assert first_dispatch.json()["state"] == "queued"
    assert first_dispatch.json()["attempt_count"] == 1
    assert first_dispatch.json()["last_error"] == "lab"

    assert second_dispatch.status_code == 200
    assert second_dispatch.json()["state"] == "failed"
    assert second_dispatch.json()["attempt_count"] == 2
    assert second_dispatch.json()["last_error"] == "lab"

    stored = session.get(SchedulerJobRow, job_id)
    assert stored is not None
    assert stored.state == "failed"


def test_scheduler_enforces_pending_job_quota(tmp_path: Path) -> None:
    client, _session = build_test_client(tmp_path)

    for index in range(5):
        response = client.post(
            "/scheduler/jobs",
            json={
                "action": "create_lab",
                "profile_name": "safe-dev",
                "requester_id": "quota-bound",
                "scheduled_for": (datetime.now(UTC) + timedelta(minutes=index + 1)).isoformat(),
            },
        )
        assert response.status_code == 201

    overflow = client.post(
        "/scheduler/jobs",
        json={
            "action": "create_lab",
            "profile_name": "safe-dev",
            "requester_id": "quota-bound",
        },
    )

    assert overflow.status_code == 409
    assert overflow.json() == {
        "detail": "scheduler_pending_job_quota_exceeded",
        "resource": "scheduler_job",
    }


def test_scheduler_rejects_action_payload_mismatch(tmp_path: Path) -> None:
    client, _session = build_test_client(tmp_path)

    response = client.post(
        "/scheduler/jobs",
        json={
            "action": "start_run",
            "profile_name": "safe-dev",
            "requester_id": "nightly-runs",
        },
    )

    assert response.status_code == 422
    assert response.json()["detail"] == "validation_error"

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from labos.core.enums import ApprovalState, LabState, RunState
from labos.db.schema import (
    ApprovalRow,
    Base,
    EventRow,
    LabRow,
    LabStorageRow,
    RunRow,
    SecretLeaseRow,
)
from labos.db.session import build_engine, build_session_factory
from labos.runtimes.base import LabInspection
from labos.storage.models import StorageAllocation
from labos.workers.reconciler import ReconciliationService


@dataclass
class FakeRuntimeInventory:
    inspections: list[LabInspection]

    def list_managed_labs(self) -> list[LabInspection]:
        return list(self.inspections)


@dataclass
class FakeStorageDestroyer:
    failures_remaining: int = 0
    destroyed_lab_ids: list[str] | None = None

    def __post_init__(self) -> None:
        if self.destroyed_lab_ids is None:
            self.destroyed_lab_ids = []

    def destroy(self, allocation: StorageAllocation) -> None:
        if self.failures_remaining > 0:
            self.failures_remaining -= 1
            raise RuntimeError("storage backend busy")
        assert self.destroyed_lab_ids is not None
        self.destroyed_lab_ids.append(allocation.lab_id)
        if allocation.root_path.exists():
            for child in sorted(allocation.root_path.rglob("*"), reverse=True):
                if child.is_file():
                    child.unlink()
                else:
                    child.rmdir()
            allocation.root_path.rmdir()


def build_session(tmp_path: Path) -> Session:
    database_url = f"sqlite+pysqlite:///{tmp_path / 'labos-reconcile.db'}"
    engine = build_engine(database_url)
    Base.metadata.create_all(engine)
    session_factory = build_session_factory(database_url)
    return session_factory()


def test_reconciler_marks_lab_failed_when_storage_record_is_missing(tmp_path: Path) -> None:
    session = build_session(tmp_path)
    session.add(
        LabRow(
            id="lab-half-created",
            profile_name="safe-dev",
            state=LabState.APPROVED.value,
            runtime_class="container",
        )
    )
    session.commit()

    report = ReconciliationService(
        runtime_inventory=FakeRuntimeInventory(inspections=[])
    ).reconcile(session)
    session.commit()

    refreshed = session.get(LabRow, "lab-half-created")
    assert refreshed is not None
    assert refreshed.state == LabState.FAILED.value
    assert report.failed_lab_ids == ["lab-half-created"]

    events = session.scalars(
        select(EventRow)
        .where(EventRow.resource_id == "lab-half-created")
        .order_by(EventRow.created_at, EventRow.id)
    ).all()
    assert [event.event_type for event in events] == ["lab.reconciliation_failed"]


def test_reconciler_detects_orphaned_runtime_labs(tmp_path: Path) -> None:
    session = build_session(tmp_path)
    session.add(
        LabRow(
            id="lab-known",
            profile_name="safe-dev",
            state=LabState.RUNNING.value,
            runtime_class="container",
        )
    )
    session.add(
        LabStorageRow(
            id="storage-known",
            lab_id="lab-known",
            persistence_mode="ephemeral",
            root_path=str(tmp_path / "managed" / "labs" / "lab-known"),
            workspace_path=str(tmp_path / "managed" / "labs" / "lab-known" / "workspace"),
            exports_path=str(tmp_path / "managed" / "labs" / "lab-known" / "exports"),
            quarantine_path=str(tmp_path / "managed" / "labs" / "lab-known" / "quarantine"),
            snapshots_path=str(tmp_path / "managed" / "labs" / "lab-known" / "snapshots"),
            workspace_mount_target="/lab/workspace",
        )
    )
    session.commit()

    inventory = FakeRuntimeInventory(
        inspections=[
            LabInspection(
                lab_id="lab-known",
                backend="docker",
                container_name="labos-lab-known",
                status="running",
                labels={"labos.managed": "true", "labos.lab_id": "lab-known"},
            ),
            LabInspection(
                lab_id="lab-orphan",
                backend="docker",
                container_name="labos-lab-orphan",
                status="running",
                labels={"labos.managed": "true", "labos.lab_id": "lab-orphan"},
            ),
        ]
    )

    report = ReconciliationService(runtime_inventory=inventory).reconcile(session)
    session.commit()

    assert report.orphaned_runtime_lab_ids == ["lab-orphan"]
    orphan_events = session.scalars(
        select(EventRow)
        .where(EventRow.resource_id == "lab-orphan")
        .order_by(EventRow.created_at, EventRow.id)
    ).all()
    assert [event.event_type for event in orphan_events] == ["runtime_lab.orphan_detected"]



def test_reconciler_detects_zombie_runtime_for_destroyed_lab(tmp_path: Path) -> None:
    session = build_session(tmp_path)
    lab_root = tmp_path / "managed" / "labs" / "lab-destroyed"
    lab_root.mkdir(parents=True)
    session.add(
        LabRow(
            id="lab-destroyed",
            profile_name="safe-dev",
            state=LabState.DESTROYED.value,
            runtime_class="container",
        )
    )
    session.add(
        LabStorageRow(
            id="storage-destroyed",
            lab_id="lab-destroyed",
            persistence_mode="ephemeral",
            root_path=str(lab_root),
            workspace_path=str(lab_root / "workspace"),
            exports_path=str(lab_root / "exports"),
            quarantine_path=str(lab_root / "quarantine"),
            snapshots_path=str(lab_root / "snapshots"),
            workspace_mount_target="/lab/workspace",
        )
    )
    session.commit()

    inventory = FakeRuntimeInventory(
        inspections=[
            LabInspection(
                lab_id="lab-destroyed",
                backend="docker",
                container_name="labos-lab-destroyed",
                status="running",
                labels={"labos.managed": "true", "labos.lab_id": "lab-destroyed"},
            )
        ]
    )

    report = ReconciliationService(runtime_inventory=inventory).reconcile(session)
    session.commit()

    assert report.zombie_lab_ids == ["lab-destroyed"]
    zombie_events = session.scalars(
        select(EventRow)
        .where(EventRow.resource_id == "lab-destroyed")
        .order_by(EventRow.created_at, EventRow.id)
    ).all()
    assert [event.event_type for event in zombie_events] == ["runtime_lab.zombie_detected"]


def test_reconciler_retries_destroying_lab_and_marks_it_destroyed(tmp_path: Path) -> None:
    session = build_session(tmp_path)
    lab_root = tmp_path / "managed" / "labs" / "lab-destroy-retry"
    workspace_path = lab_root / "workspace"
    workspace_path.mkdir(parents=True)
    (workspace_path / "notes.txt").write_text("cleanup me")
    session.add(
        LabRow(
            id="lab-destroy-retry",
            profile_name="safe-dev",
            state=LabState.DESTROYING.value,
            runtime_class="container",
            destroy_attempts=0,
        )
    )
    session.add(
        LabStorageRow(
            id="storage-destroy-retry",
            lab_id="lab-destroy-retry",
            persistence_mode="ephemeral",
            root_path=str(lab_root),
            workspace_path=str(workspace_path),
            exports_path=str(lab_root / "exports"),
            quarantine_path=str(lab_root / "quarantine"),
            snapshots_path=str(lab_root / "snapshots"),
            workspace_mount_target="/lab/workspace",
        )
    )
    session.commit()

    destroyer = FakeStorageDestroyer()
    report = ReconciliationService(
        runtime_inventory=FakeRuntimeInventory(inspections=[]),
        storage_destroyer=destroyer,
    ).reconcile(session)
    session.commit()

    lab = session.get(LabRow, "lab-destroy-retry")
    assert lab is not None
    assert lab.state == LabState.DESTROYED.value
    assert lab.destroy_attempts == 1
    assert lab.last_destroy_error is None
    assert report.destroyed_lab_ids == ["lab-destroy-retry"]
    assert destroyer.destroyed_lab_ids == ["lab-destroy-retry"]
    assert lab_root.exists() is False

    events = session.scalars(
        select(EventRow)
        .where(EventRow.resource_id == "lab-destroy-retry")
        .order_by(EventRow.created_at, EventRow.id)
    ).all()
    assert [event.event_type for event in events] == ["lab.destroyed"]


def test_reconciler_marks_destroying_lab_failed_after_retry_budget_exhausted(
    tmp_path: Path,
) -> None:
    session = build_session(tmp_path)
    lab_root = tmp_path / "managed" / "labs" / "lab-destroy-fails"
    lab_root.mkdir(parents=True)
    session.add(
        LabRow(
            id="lab-destroy-fails",
            profile_name="safe-dev",
            state=LabState.DESTROYING.value,
            runtime_class="container",
            destroy_attempts=0,
        )
    )
    session.add(
        LabStorageRow(
            id="storage-destroy-fails",
            lab_id="lab-destroy-fails",
            persistence_mode="ephemeral",
            root_path=str(lab_root),
            workspace_path=str(lab_root / "workspace"),
            exports_path=str(lab_root / "exports"),
            quarantine_path=str(lab_root / "quarantine"),
            snapshots_path=str(lab_root / "snapshots"),
            workspace_mount_target="/lab/workspace",
        )
    )
    session.commit()

    destroyer = FakeStorageDestroyer(failures_remaining=2)
    reconciler = ReconciliationService(
        runtime_inventory=FakeRuntimeInventory(inspections=[]),
        storage_destroyer=destroyer,
        max_destroy_attempts=2,
    )

    first_report = reconciler.reconcile(session)
    session.commit()

    first_lab = session.get(LabRow, "lab-destroy-fails")
    assert first_lab is not None
    assert first_lab.state == LabState.DESTROYING.value
    assert first_lab.destroy_attempts == 1
    assert first_lab.last_destroy_error == "storage backend busy"
    assert first_report.failed_destroy_lab_ids == []

    second_report = reconciler.reconcile(session)
    session.commit()

    second_lab = session.get(LabRow, "lab-destroy-fails")
    assert second_lab is not None
    assert second_lab.state == LabState.FAILED.value
    assert second_lab.destroy_attempts == 2
    assert second_lab.last_destroy_error == "storage backend busy"
    assert second_report.failed_destroy_lab_ids == ["lab-destroy-fails"]

    events = session.scalars(
        select(EventRow)
        .where(EventRow.resource_id == "lab-destroy-fails")
        .order_by(EventRow.created_at, EventRow.id)
    ).all()
    assert [event.event_type for event in events] == [
        "lab.destroy_retry_failed",
        "lab.destroy_retry_failed",
        "lab.destroy_failed",
    ]



def test_reconciler_ignores_stopped_runtime_for_stopped_lab(tmp_path: Path) -> None:
    session = build_session(tmp_path)
    lab_root = tmp_path / "managed" / "labs" / "lab-stopped"
    lab_root.mkdir(parents=True)
    session.add(
        LabRow(
            id="lab-stopped",
            profile_name="safe-dev",
            state=LabState.STOPPED.value,
            runtime_class="container",
        )
    )
    session.add(
        LabStorageRow(
            id="storage-stopped",
            lab_id="lab-stopped",
            persistence_mode="ephemeral",
            root_path=str(lab_root),
            workspace_path=str(lab_root / "workspace"),
            exports_path=str(lab_root / "exports"),
            quarantine_path=str(lab_root / "quarantine"),
            snapshots_path=str(lab_root / "snapshots"),
            workspace_mount_target="/lab/workspace",
        )
    )
    session.commit()

    inventory = FakeRuntimeInventory(
        inspections=[
            LabInspection(
                lab_id="lab-stopped",
                backend="docker",
                container_name="labos-lab-stopped",
                status="exited",
                labels={"labos.managed": "true", "labos.lab_id": "lab-stopped"},
            )
        ]
    )

    report = ReconciliationService(runtime_inventory=inventory).reconcile(session)
    session.commit()

    assert report.zombie_lab_ids == []
    zombie_events = session.scalars(
        select(EventRow)
        .where(EventRow.resource_id == "lab-stopped")
        .order_by(EventRow.created_at, EventRow.id)
    ).all()
    assert zombie_events == []



def test_reconciler_expires_stale_pending_approvals_and_fails_lab(tmp_path: Path) -> None:
    session = build_session(tmp_path)
    now = datetime(2026, 5, 14, 12, 0, tzinfo=UTC)
    lab_root = tmp_path / "managed" / "labs" / "lab-awaiting-approval"
    lab_root.mkdir(parents=True)
    session.add(
        LabRow(
            id="lab-awaiting-approval",
            profile_name="research-persistent",
            state=LabState.PENDING_APPROVAL.value,
            runtime_class="container",
        )
    )
    session.add(
        LabStorageRow(
            id="storage-awaiting-approval",
            lab_id="lab-awaiting-approval",
            persistence_mode="persistent",
            root_path=str(lab_root),
            workspace_path=str(lab_root / "workspace"),
            exports_path=str(lab_root / "exports"),
            quarantine_path=str(lab_root / "quarantine"),
            snapshots_path=str(lab_root / "snapshots"),
            workspace_mount_target="/lab/workspace",
        )
    )
    session.add(
        ApprovalRow(
            id="approval-expired",
            lab_id="lab-awaiting-approval",
            resource_type="lab",
            resource_id="lab-awaiting-approval",
            action="lab.create",
            reason="profile requires approval",
            requested_by="scheduler",
            state=ApprovalState.REQUESTED.value,
            approved=False,
            expires_at=now - timedelta(minutes=5),
        )
    )
    session.commit()

    reconciler = ReconciliationService(runtime_inventory=FakeRuntimeInventory(inspections=[]))
    report = reconciler.reconcile(session, now=now)
    session.commit()

    approval = session.get(ApprovalRow, "approval-expired")
    assert approval is not None
    assert approval.state == ApprovalState.EXPIRED.value
    assert approval.approved is False
    assert approval.decided_by == "reconciler"
    assert approval.decided_at is not None
    assert approval.decided_at.replace(tzinfo=UTC) == now

    lab = session.get(LabRow, "lab-awaiting-approval")
    assert lab is not None
    assert lab.state == LabState.FAILED.value

    assert report.expired_approval_ids == ["approval-expired"]
    events = session.scalars(
        select(EventRow)
        .where(EventRow.resource_id == "approval-expired")
        .order_by(EventRow.created_at, EventRow.id)
    ).all()
    assert [event.event_type for event in events] == ["approval.expired"]


def test_reconciler_revokes_expired_secret_leases(tmp_path: Path) -> None:
    session = build_session(tmp_path)
    now = datetime(2026, 5, 14, 12, 0, tzinfo=UTC)
    lab_root = tmp_path / "managed" / "labs" / "lab-secret-cleanup"
    lab_root.mkdir(parents=True)
    session.add(
        LabRow(
            id="lab-secret-cleanup",
            profile_name="safe-dev",
            state=LabState.RUNNING.value,
            runtime_class="container",
        )
    )
    session.add(
        LabStorageRow(
            id="storage-secret-cleanup",
            lab_id="lab-secret-cleanup",
            persistence_mode="ephemeral",
            root_path=str(lab_root),
            workspace_path=str(lab_root / "workspace"),
            exports_path=str(lab_root / "exports"),
            quarantine_path=str(lab_root / "quarantine"),
            snapshots_path=str(lab_root / "snapshots"),
            workspace_mount_target="/lab/workspace",
        )
    )
    session.add(
        SecretLeaseRow(
            id="lease-expired",
            lab_id="lab-secret-cleanup",
            secret_name="API_TOKEN",
            approved=True,
            expires_at=now - timedelta(minutes=1),
            revoked_at=None,
        )
    )
    session.commit()

    reconciler = ReconciliationService(runtime_inventory=FakeRuntimeInventory(inspections=[]))
    report = reconciler.reconcile(session, now=now)
    session.commit()

    lease = session.get(SecretLeaseRow, "lease-expired")
    assert lease is not None
    assert lease.revoked_at is not None
    assert lease.revoked_at.replace(tzinfo=UTC) == now

    assert report.revoked_secret_lease_ids == ["lease-expired"]
    events = session.scalars(
        select(EventRow)
        .where(EventRow.resource_id == "lease-expired")
        .order_by(EventRow.created_at, EventRow.id)
    ).all()
    assert [event.event_type for event in events] == ["secret_lease.expired"]


def test_reconciler_times_out_overdue_runs_and_records_event(tmp_path: Path) -> None:
    session = build_session(tmp_path)
    now = datetime(2026, 5, 14, 12, 0, tzinfo=UTC)
    lab_root = tmp_path / "managed" / "labs" / "lab-run-timeout"
    lab_root.mkdir(parents=True)
    session.add(
        LabRow(
            id="lab-run-timeout",
            profile_name="safe-dev",
            state=LabState.RUNNING.value,
            runtime_class="container",
        )
    )
    session.add(
        LabStorageRow(
            id="storage-run-timeout",
            lab_id="lab-run-timeout",
            persistence_mode="ephemeral",
            root_path=str(lab_root),
            workspace_path=str(lab_root / "workspace"),
            exports_path=str(lab_root / "exports"),
            quarantine_path=str(lab_root / "quarantine"),
            snapshots_path=str(lab_root / "snapshots"),
            workspace_mount_target="/lab/workspace",
        )
    )
    session.add(
        RunRow(
            id="run-expired",
            lab_id="lab-run-timeout",
            state=RunState.RUNNING.value,
            command="python -m pytest",
            timeout_at=now - timedelta(minutes=1),
        )
    )
    session.commit()

    reconciler = ReconciliationService(runtime_inventory=FakeRuntimeInventory(inspections=[]))
    report = reconciler.reconcile(session, now=now)
    session.commit()

    run = session.get(RunRow, "run-expired")
    assert run is not None
    assert run.state == RunState.TIMED_OUT.value
    assert run.finished_at is not None
    assert run.finished_at.replace(tzinfo=UTC) == now

    assert report.timed_out_run_ids == ["run-expired"]
    events = session.scalars(
        select(EventRow)
        .where(EventRow.resource_id == "run-expired")
        .order_by(EventRow.created_at, EventRow.id)
    ).all()
    assert [event.event_type for event in events] == ["run.timed_out"]

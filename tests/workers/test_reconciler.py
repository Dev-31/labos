from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from labos.core.enums import LabState
from labos.db.schema import Base, EventRow, LabRow, LabStorageRow
from labos.db.session import build_engine, build_session_factory
from labos.runtimes.base import LabInspection
from labos.workers.reconciler import ReconciliationService


@dataclass
class FakeRuntimeInventory:
    inspections: list[LabInspection]

    def list_managed_labs(self) -> list[LabInspection]:
        return list(self.inspections)


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

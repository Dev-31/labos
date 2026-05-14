from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol

from sqlalchemy import select
from sqlalchemy.orm import Session

from labos.core.enums import ActorType, LabState
from labos.core.events import EventRecord, EventWriter
from labos.db.schema import LabRow, LabStorageRow
from labos.runtimes.base import LabInspection


class RuntimeInventory(Protocol):
    def list_managed_labs(self) -> list[LabInspection]: ...


@dataclass(frozen=True)
class ReconciliationReport:
    failed_lab_ids: list[str] = field(default_factory=list)
    orphaned_runtime_lab_ids: list[str] = field(default_factory=list)


class ReconciliationService:
    """Detect inconsistent LabOS state before it turns into silent drift."""

    def __init__(self, *, runtime_inventory: RuntimeInventory | None = None) -> None:
        self._runtime_inventory = runtime_inventory

    def reconcile(self, session: Session) -> ReconciliationReport:
        report = ReconciliationReport()
        labs = session.scalars(select(LabRow).order_by(LabRow.created_at, LabRow.id)).all()
        lab_ids = {lab.id for lab in labs}
        storage_rows = session.scalars(
            select(LabStorageRow).where(LabStorageRow.lab_id.in_(lab_ids))
        ).all()
        storage_by_lab_id = {row.lab_id: row for row in storage_rows}
        event_writer = EventWriter(session)

        for lab in labs:
            if lab.state == LabState.DESTROYED.value:
                continue

            failure_reason: str | None = None
            storage_row = storage_by_lab_id.get(lab.id)
            if storage_row is None:
                failure_reason = "missing_storage_record"
            elif not Path(storage_row.root_path).exists():
                failure_reason = "missing_storage_root"

            if failure_reason is None:
                continue

            if lab.state != LabState.FAILED.value:
                lab.state = LabState.FAILED.value
            report.failed_lab_ids.append(lab.id)
            event_writer.write(
                EventRecord(
                    event_type="lab.reconciliation_failed",
                    lab_id=lab.id,
                    actor_type=ActorType.SYSTEM.value,
                    actor_id="reconciler",
                    resource_type="lab",
                    resource_id=lab.id,
                    payload={"reason": failure_reason, "state": lab.state},
                )
            )

        if self._runtime_inventory is None:
            return report

        for inspection in self._runtime_inventory.list_managed_labs():
            if inspection.lab_id in lab_ids:
                continue
            report.orphaned_runtime_lab_ids.append(inspection.lab_id)
            event_writer.write(
                EventRecord(
                    event_type="runtime_lab.orphan_detected",
                    actor_type=ActorType.SYSTEM.value,
                    actor_id="reconciler",
                    resource_type="runtime_lab",
                    resource_id=inspection.lab_id,
                    payload={
                        "backend": inspection.backend,
                        "container_name": inspection.container_name,
                        "status": inspection.status,
                    },
                )
            )

        report.failed_lab_ids.sort()
        report.orphaned_runtime_lab_ids.sort()
        return report

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Protocol

from sqlalchemy import select
from sqlalchemy.orm import Session

from labos.core.enums import ActorType, ApprovalState, ExportState, LabState
from labos.core.events import EventRecord, EventWriter
from labos.db.schema import ApprovalRow, ExportRow, LabRow, LabStorageRow, SecretLeaseRow
from labos.runtimes.base import LabInspection


class RuntimeInventory(Protocol):
    def list_managed_labs(self) -> list[LabInspection]: ...


@dataclass(frozen=True)
class ReconciliationReport:
    failed_lab_ids: list[str] = field(default_factory=list)
    orphaned_runtime_lab_ids: list[str] = field(default_factory=list)
    expired_approval_ids: list[str] = field(default_factory=list)
    revoked_secret_lease_ids: list[str] = field(default_factory=list)


class ReconciliationService:
    """Detect inconsistent LabOS state before it turns into silent drift."""

    def __init__(self, *, runtime_inventory: RuntimeInventory | None = None) -> None:
        self._runtime_inventory = runtime_inventory

    def reconcile(self, session: Session, *, now: datetime | None = None) -> ReconciliationReport:
        report = ReconciliationReport()
        current_time = self._normalize_datetime(now or datetime.now(UTC))
        labs = session.scalars(select(LabRow).order_by(LabRow.created_at, LabRow.id)).all()
        lab_ids = {lab.id for lab in labs}
        storage_rows = session.scalars(
            select(LabStorageRow).where(LabStorageRow.lab_id.in_(lab_ids))
        ).all()
        storage_by_lab_id = {row.lab_id: row for row in storage_rows}
        event_writer = EventWriter(session)

        self._expire_stale_approvals(
            session,
            event_writer=event_writer,
            report=report,
            now=current_time,
        )
        self._revoke_expired_secret_leases(
            session,
            event_writer=event_writer,
            report=report,
            now=current_time,
        )

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
        report.expired_approval_ids.sort()
        report.revoked_secret_lease_ids.sort()
        return report

    def _expire_stale_approvals(
        self,
        session: Session,
        *,
        event_writer: EventWriter,
        report: ReconciliationReport,
        now: datetime,
    ) -> None:
        approvals = session.scalars(
            select(ApprovalRow)
            .where(ApprovalRow.state == ApprovalState.REQUESTED.value)
            .where(ApprovalRow.expires_at.is_not(None))
            .order_by(ApprovalRow.created_at, ApprovalRow.id)
        ).all()
        for approval in approvals:
            expires_at = approval.expires_at
            if expires_at is None:
                continue
            expires_at = self._normalize_datetime(expires_at)
            if expires_at > now:
                continue

            approval.state = ApprovalState.EXPIRED.value
            approval.approved = False
            approval.decided_by = "reconciler"
            approval.decided_at = now
            report.expired_approval_ids.append(approval.id)

            if approval.resource_type == "lab":
                lab = session.get(LabRow, approval.resource_id)
                if lab is not None and lab.state == LabState.PENDING_APPROVAL.value:
                    lab.state = LabState.FAILED.value
            elif approval.resource_type == "export":
                export = session.get(ExportRow, approval.resource_id)
                if export is not None:
                    export.state = ExportState.REJECTED.value
                    export.denial_reason = "approval request expired"
                    export.approval_required = False

            event_writer.write(
                EventRecord(
                    event_type="approval.expired",
                    lab_id=approval.lab_id,
                    actor_type=ActorType.SYSTEM.value,
                    actor_id="reconciler",
                    resource_type="approval",
                    resource_id=approval.id,
                    payload={
                        "approval_id": approval.id,
                        "resource_type": approval.resource_type,
                        "resource_id": approval.resource_id,
                        "action": approval.action,
                    },
                )
            )

    def _revoke_expired_secret_leases(
        self,
        session: Session,
        *,
        event_writer: EventWriter,
        report: ReconciliationReport,
        now: datetime,
    ) -> None:
        leases = session.scalars(
            select(SecretLeaseRow)
            .where(SecretLeaseRow.revoked_at.is_(None))
            .order_by(SecretLeaseRow.created_at, SecretLeaseRow.id)
        ).all()
        for lease in leases:
            if self._normalize_datetime(lease.expires_at) > now:
                continue
            lease.revoked_at = now
            report.revoked_secret_lease_ids.append(lease.id)
            event_writer.write(
                EventRecord(
                    event_type="secret_lease.expired",
                    lab_id=lease.lab_id,
                    actor_type=ActorType.SYSTEM.value,
                    actor_id="reconciler",
                    resource_type="secret_lease",
                    resource_id=lease.id,
                    payload={"secret_name": lease.secret_name, "lease_id": lease.id},
                )
            )

    @staticmethod
    def _normalize_datetime(value: datetime) -> datetime:
        if value.tzinfo is None:
            return value.replace(tzinfo=UTC)
        return value

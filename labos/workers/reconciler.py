from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Protocol

from sqlalchemy import select
from sqlalchemy.orm import Session

from labos.core.enums import ActorType, ApprovalState, ExportState, LabState, RunState
from labos.core.events import EventRecord, EventWriter
from labos.core.policy_models import PersistenceMode
from labos.db.schema import ApprovalRow, ExportRow, LabRow, LabStorageRow, RunRow, SecretLeaseRow
from labos.runtimes.base import LabInspection
from labos.storage.models import StorageAllocation


class RuntimeInventory(Protocol):
    def list_managed_labs(self) -> list[LabInspection]: ...


class StorageDestroyer(Protocol):
    def destroy(self, allocation: StorageAllocation) -> None: ...


@dataclass(frozen=True)
class ReconciliationReport:
    failed_lab_ids: list[str] = field(default_factory=list)
    destroyed_lab_ids: list[str] = field(default_factory=list)
    failed_destroy_lab_ids: list[str] = field(default_factory=list)
    orphaned_runtime_lab_ids: list[str] = field(default_factory=list)
    zombie_lab_ids: list[str] = field(default_factory=list)
    expired_approval_ids: list[str] = field(default_factory=list)
    revoked_secret_lease_ids: list[str] = field(default_factory=list)
    timed_out_run_ids: list[str] = field(default_factory=list)


class ReconciliationService:
    """Detect inconsistent LabOS state before it turns into silent drift."""

    def __init__(
        self,
        *,
        runtime_inventory: RuntimeInventory | None = None,
        storage_destroyer: StorageDestroyer | None = None,
        max_destroy_attempts: int = 3,
    ) -> None:
        self._runtime_inventory = runtime_inventory
        self._storage_destroyer = storage_destroyer
        self._max_destroy_attempts = max_destroy_attempts

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
        self._timeout_overdue_runs(
            session,
            event_writer=event_writer,
            report=report,
            now=current_time,
        )
        self._retry_destroying_labs(
            session,
            storage_by_lab_id=storage_by_lab_id,
            event_writer=event_writer,
            report=report,
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
            self._sort_report(report)
            return report

        labs_by_id = {lab.id: lab for lab in labs}
        for inspection in self._runtime_inventory.list_managed_labs():
            matching_lab = labs_by_id.get(inspection.lab_id)
            if matching_lab is None:
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
                continue

            if self._is_zombie_lab(matching_lab.state, inspection.status):
                report.zombie_lab_ids.append(inspection.lab_id)
                event_writer.write(
                    EventRecord(
                        event_type="runtime_lab.zombie_detected",
                        lab_id=matching_lab.id,
                        actor_type=ActorType.SYSTEM.value,
                        actor_id="reconciler",
                        resource_type="runtime_lab",
                        resource_id=inspection.lab_id,
                        payload={
                            "backend": inspection.backend,
                            "container_name": inspection.container_name,
                            "status": inspection.status,
                            "lab_state": matching_lab.state,
                        },
                    )
                )

        self._sort_report(report)
        return report

    def _retry_destroying_labs(
        self,
        session: Session,
        *,
        storage_by_lab_id: dict[str, LabStorageRow],
        event_writer: EventWriter,
        report: ReconciliationReport,
    ) -> None:
        if self._storage_destroyer is None:
            return

        destroying_labs = session.scalars(
            select(LabRow)
            .where(LabRow.state == LabState.DESTROYING.value)
            .order_by(LabRow.created_at, LabRow.id)
        ).all()
        for lab in destroying_labs:
            storage_row = storage_by_lab_id.get(lab.id)
            if storage_row is None:
                lab.state = LabState.FAILED.value
                lab.last_destroy_error = "missing_storage_record"
                report.failed_destroy_lab_ids.append(lab.id)
                event_writer.write(
                    EventRecord(
                        event_type="lab.destroy_failed",
                        lab_id=lab.id,
                        actor_type=ActorType.SYSTEM.value,
                        actor_id="reconciler",
                        resource_type="lab",
                        resource_id=lab.id,
                        payload={
                            "attempt": lab.destroy_attempts,
                            "max_attempts": self._max_destroy_attempts,
                            "reason": lab.last_destroy_error,
                        },
                    )
                )
                continue

            lab.destroy_attempts += 1
            try:
                allocation = self._storage_allocation_from_row(storage_row, lab.id)
                self._storage_destroyer.destroy(allocation)
            except Exception as exc:
                lab.last_destroy_error = str(exc)
                event_writer.write(
                    EventRecord(
                        event_type="lab.destroy_retry_failed",
                        lab_id=lab.id,
                        actor_type=ActorType.SYSTEM.value,
                        actor_id="reconciler",
                        resource_type="lab",
                        resource_id=lab.id,
                        payload={
                            "attempt": lab.destroy_attempts,
                            "max_attempts": self._max_destroy_attempts,
                            "reason": lab.last_destroy_error,
                        },
                    )
                )
                if lab.destroy_attempts >= self._max_destroy_attempts:
                    lab.state = LabState.FAILED.value
                    report.failed_destroy_lab_ids.append(lab.id)
                    event_writer.write(
                        EventRecord(
                            event_type="lab.destroy_failed",
                            lab_id=lab.id,
                            actor_type=ActorType.SYSTEM.value,
                            actor_id="reconciler",
                            resource_type="lab",
                            resource_id=lab.id,
                            payload={
                                "attempt": lab.destroy_attempts,
                                "max_attempts": self._max_destroy_attempts,
                                "reason": lab.last_destroy_error,
                            },
                        )
                    )
                continue

            lab.state = LabState.DESTROYED.value
            lab.last_destroy_error = None
            report.destroyed_lab_ids.append(lab.id)
            event_writer.write(
                EventRecord(
                    event_type="lab.destroyed",
                    lab_id=lab.id,
                    actor_type=ActorType.SYSTEM.value,
                    actor_id="reconciler",
                    resource_type="lab",
                    resource_id=lab.id,
                    payload={"attempt": lab.destroy_attempts, "state": lab.state},
                )
            )

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

    def _timeout_overdue_runs(
        self,
        session: Session,
        *,
        event_writer: EventWriter,
        report: ReconciliationReport,
        now: datetime,
    ) -> None:
        active_states = [RunState.QUEUED.value, RunState.STARTING.value, RunState.RUNNING.value]
        runs = session.scalars(
            select(RunRow)
            .where(RunRow.state.in_(active_states))
            .where(RunRow.timeout_at.is_not(None))
            .order_by(RunRow.created_at, RunRow.id)
        ).all()
        for run in runs:
            timeout_at = run.timeout_at
            if timeout_at is None:
                continue
            timeout_at = self._normalize_datetime(timeout_at)
            if timeout_at > now:
                continue

            run.state = RunState.TIMED_OUT.value
            run.finished_at = now
            report.timed_out_run_ids.append(run.id)
            event_writer.write(
                EventRecord(
                    event_type="run.timed_out",
                    lab_id=run.lab_id,
                    run_id=run.id,
                    actor_type=ActorType.SYSTEM.value,
                    actor_id="reconciler",
                    resource_type="run",
                    resource_id=run.id,
                    payload={
                        "state": run.state,
                        "timeout_at": timeout_at.isoformat(),
                    },
                )
            )

    @staticmethod
    def _sort_report(report: ReconciliationReport) -> None:
        report.failed_lab_ids.sort()
        report.destroyed_lab_ids.sort()
        report.failed_destroy_lab_ids.sort()
        report.orphaned_runtime_lab_ids.sort()
        report.zombie_lab_ids.sort()
        report.expired_approval_ids.sort()
        report.revoked_secret_lease_ids.sort()
        report.timed_out_run_ids.sort()

    @staticmethod
    def _storage_allocation_from_row(row: LabStorageRow, lab_id: str) -> StorageAllocation:
        return StorageAllocation(
            lab_id=lab_id,
            root_path=Path(row.root_path),
            workspace_path=Path(row.workspace_path),
            exports_path=Path(row.exports_path),
            quarantine_path=Path(row.quarantine_path),
            snapshots_path=Path(row.snapshots_path),
            persistence_mode=PersistenceMode(row.persistence_mode),
            retention_days=0,
            workspace_mount_target=row.workspace_mount_target,
        )

    @staticmethod
    def _is_zombie_lab(lab_state: str, runtime_status: str) -> bool:
        active_runtime_statuses = {"created", "restarting", "running", "paused"}
        if runtime_status not in active_runtime_statuses:
            return False

        allowed_runtime_states = {
            LabState.PROVISIONING.value,
            LabState.RUNNING.value,
            LabState.STOPPED.value,
            LabState.DESTROYING.value,
        }
        return lab_state not in allowed_runtime_states

    @staticmethod
    def _normalize_datetime(value: datetime) -> datetime:
        if value.tzinfo is None:
            return value.replace(tzinfo=UTC)
        return value

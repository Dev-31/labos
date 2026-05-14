from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from labos import __version__
from labos.config.profiles.base import DEFAULT_PROFILES
from labos.config.settings import Settings, load_settings
from labos.core.enums import (
    ActorType,
    ApprovalState,
    ExportState,
    LabState,
    RunState,
    SchedulerAction,
    SchedulerJobState,
)
from labos.core.events import EventRecord, EventWriter
from labos.core.models import (
    ApprovalDecisionRequest,
    ApprovalResponse,
    ErrorResponse,
    EventResponse,
    ExportCreateRequest,
    ExportDenyRequest,
    ExportResponse,
    HealthResponse,
    LabCreateRequest,
    LabResponse,
    LabStorageResponse,
    RunCreateRequest,
    RunResponse,
    SchedulerJobCreateRequest,
    SchedulerJobResponse,
    SecretLeaseCreateRequest,
    SecretLeaseResponse,
    SecretLeaseRevokeRequest,
    SnapshotCreateRequest,
    SnapshotResponse,
    SnapshotRestoreRequest,
    ValidationErrorItem,
    ValidationErrorResponse,
)
from labos.core.policy_engine import PolicyEngine
from labos.core.policy_models import PersistenceMode, RequesterType
from labos.db.schema import (
    ApprovalRow,
    EventRow,
    ExportRow,
    LabRow,
    LabStorageRow,
    RunRow,
    SchedulerJobRow,
    SecretLeaseRow,
    SnapshotRow,
)
from labos.db.session import build_session_factory
from labos.security.export_gate import (
    ExportGate,
    ExportPolicyError,
    ExportSourceNotFoundError,
    ExportStateError,
)
from labos.security.secret_broker import (
    EnvSecretBroker,
    SecretLeaseService,
    SecretLeaseStateError,
    SecretNotFoundError,
)
from labos.storage import ManagedStorageAllocator, SnapshotManager, StoragePolicy
from labos.storage.models import StorageAllocation
from labos.storage.snapshots import (
    SnapshotMetadata,
    SnapshotMetadataError,
    UnsupportedSnapshotRuntimeError,
)
from labos.workers.scheduler import SchedulerQuotaExceededError, SchedulerService


class ResourceNotFoundError(Exception):
    def __init__(self, resource: str) -> None:
        self.resource = resource
        super().__init__(resource)


class ConflictError(Exception):
    def __init__(self, detail: str, resource: str | None = None) -> None:
        self.detail = detail
        self.resource = resource
        super().__init__(detail)


def _lab_response_from_row(row: LabRow, storage: LabStorageRow) -> LabResponse:
    return LabResponse(
        id=row.id,
        profile_name=row.profile_name,
        state=row.state,
        runtime_class=row.runtime_class,
        storage=LabStorageResponse(
            persistence_mode=storage.persistence_mode,
            root_path=storage.root_path,
            workspace_path=storage.workspace_path,
            exports_path=storage.exports_path,
            quarantine_path=storage.quarantine_path,
            snapshots_path=storage.snapshots_path,
            workspace_mount_target=storage.workspace_mount_target,
        ),
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def _storage_allocation_from_row(row: LabStorageRow) -> StorageAllocation:
    return StorageAllocation(
        lab_id=row.lab_id,
        root_path=Path(row.root_path),
        workspace_path=Path(row.workspace_path),
        exports_path=Path(row.exports_path),
        quarantine_path=Path(row.quarantine_path),
        snapshots_path=Path(row.snapshots_path),
        persistence_mode=PersistenceMode(row.persistence_mode),
        retention_days=0,
        workspace_mount_target=row.workspace_mount_target,
    )


def _run_response_from_row(row: RunRow) -> RunResponse:
    return RunResponse(
        id=row.id,
        lab_id=row.lab_id,
        state=row.state,
        command=row.command,
        timeout_at=row.timeout_at,
        finished_at=row.finished_at,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def _approval_response_from_row(row: ApprovalRow) -> ApprovalResponse:
    return ApprovalResponse(
        id=row.id,
        lab_id=row.lab_id,
        resource_type=row.resource_type,
        resource_id=row.resource_id,
        action=row.action,
        reason=row.reason,
        requested_by=row.requested_by,
        state=row.state,
        approved=row.approved,
        decision_comment=row.decision_comment,
        decided_by=row.decided_by,
        expires_at=row.expires_at,
        decided_at=row.decided_at,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def _record_approval_request(
    session: Session,
    *,
    lab_id: str | None,
    resource_type: str,
    resource_id: str,
    action: str,
    reason: str,
    requested_by: str,
) -> ApprovalRow:
    approval = ApprovalRow(
        id=str(uuid4()),
        lab_id=lab_id,
        resource_type=resource_type,
        resource_id=resource_id,
        action=action,
        reason=reason,
        requested_by=requested_by,
        state=ApprovalState.REQUESTED.value,
        approved=False,
        expires_at=ApprovalRow.default_expiry(),
    )
    session.add(approval)
    return approval


def _ensure_approval_pending(row: ApprovalRow) -> None:
    if row.state != ApprovalState.REQUESTED.value:
        raise ConflictError("approval_not_pending", resource="approval")
    if row.expires_at is not None:
        expires_at = row.expires_at
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=UTC)
        current_time = datetime.now(expires_at.tzinfo)
        if expires_at <= current_time:
            row.state = ApprovalState.EXPIRED.value
            row.approved = False
            row.decided_at = current_time
            raise ConflictError("approval_request_expired", resource="approval")


def _apply_approval_decision(
    session: Session,
    *,
    row: ApprovalRow,
    decision: ApprovalState,
    actor: str,
    comment: str | None,
) -> None:
    _ensure_approval_pending(row)

    if decision is ApprovalState.REJECTED and (comment is None or comment.strip() == ""):
        raise ConflictError("approval_comment_required", resource="approval")

    row.state = decision.value
    row.approved = decision is ApprovalState.APPROVED
    row.decision_comment = comment
    row.decided_by = actor
    row.decided_at = datetime.now(UTC)

    if row.resource_type == "lab":
        lab = session.get(LabRow, row.resource_id)
        if lab is None:
            raise ResourceNotFoundError("lab")
        lab.state = (
            LabState.APPROVED.value if decision is ApprovalState.APPROVED else LabState.FAILED.value
        )
    elif row.resource_type == "export":
        export = session.get(ExportRow, row.resource_id)
        if export is None:
            raise ResourceNotFoundError("export")
        if decision is ApprovalState.APPROVED:
            export.approval_required = False
            export.state = ExportState.APPROVED.value
            export.denial_reason = None
        else:
            export.state = ExportState.REJECTED.value
            export.denial_reason = comment


def _snapshot_response_from_row(
    row: SnapshotRow,
    metadata: SnapshotMetadata | None = None,
) -> SnapshotResponse:
    return SnapshotResponse(
        id=row.id,
        lab_id=row.lab_id,
        backend_ref=row.backend_ref,
        run_id=None if metadata is None else metadata.run_id,
        profile_name=None if metadata is None else metadata.profile_name,
        runtime_class=None if metadata is None else metadata.runtime_class,
        state=None if metadata is None else metadata.state,
        manifest_path=None if metadata is None else metadata.manifest_path,
        sha256=None if metadata is None else metadata.sha256,
        size_bytes=None if metadata is None else metadata.size_bytes,
        restored_at=None
        if metadata is None or metadata.restored_at is None
        else datetime.fromisoformat(metadata.restored_at),
        restored_lab_id=None if metadata is None else metadata.restored_lab_id,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def _export_response_from_row(row: ExportRow) -> ExportResponse:
    return ExportResponse(
        id=row.id,
        lab_id=row.lab_id,
        run_id=row.run_id,
        source_path=row.source_path,
        state=row.state,
        quarantine_path=row.quarantine_path,
        released_path=row.released_path,
        approval_required=row.approval_required,
        sha256=row.sha256,
        size_bytes=row.size_bytes,
        denial_reason=row.denial_reason,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def _secret_lease_response_from_row(row: SecretLeaseRow) -> SecretLeaseResponse:
    return SecretLeaseResponse(
        id=row.id,
        lab_id=row.lab_id,
        secret_name=row.secret_name,
        approved=row.approved,
        expires_at=row.expires_at,
        revoked_at=row.revoked_at,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def _record_event(
    session: Session,
    *,
    event_type: str,
    payload: dict[str, object],
    lab_id: str | None = None,
    run_id: str | None = None,
    actor_type: str = "system",
    actor_id: str | None = None,
    resource_type: str | None = None,
    resource_id: str | None = None,
) -> None:
    EventWriter(session).write(
        EventRecord(
            event_type=event_type,
            payload=payload,
            lab_id=lab_id,
            run_id=run_id,
            actor_type=actor_type,
            actor_id=actor_id,
            resource_type=resource_type,
            resource_id=resource_id,
        )
    )


def _event_response_from_row(row: EventRow) -> EventResponse:
    return EventResponse(
        id=row.id,
        lab_id=row.lab_id,
        run_id=row.run_id,
        event_type=row.event_type,
        actor_type=ActorType(row.actor_type),
        actor_id=row.actor_id,
        resource_type=row.resource_type,
        resource_id=row.resource_id,
        payload_json=row.payload_json,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def _scheduler_job_response_from_row(row: SchedulerJobRow) -> SchedulerJobResponse:
    return SchedulerJobResponse(
        id=row.id,
        action=SchedulerAction(row.action),
        state=SchedulerJobState(row.state),
        requester_id=row.requester_id,
        profile_name=row.profile_name,
        lab_id=row.lab_id,
        command=row.command,
        scheduled_for=row.scheduled_for,
        attempt_count=row.attempt_count,
        max_attempts=row.max_attempts,
        last_error=row.last_error,
        result_resource_type=row.result_resource_type,
        result_resource_id=row.result_resource_id,
        dispatched_at=row.dispatched_at,
        completed_at=row.completed_at,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def create_app(
    *,
    settings: Settings | None = None,
    session_factory: sessionmaker[Session] | None = None,
    policy_engine: PolicyEngine | None = None,
    managed_storage_root: Path | None = None,
) -> FastAPI:
    app_settings = settings or load_settings()
    db_session_factory = session_factory or build_session_factory(app_settings.database_url)
    policy = policy_engine or PolicyEngine()
    storage_allocator = ManagedStorageAllocator(
        root=managed_storage_root or app_settings.managed_storage_root
    )
    snapshot_manager = SnapshotManager()
    export_gate = ExportGate(policy_engine=policy)
    secret_lease_service = SecretLeaseService(policy_engine=policy, broker=EnvSecretBroker())
    scheduler_service = SchedulerService()

    app = FastAPI(title=app_settings.app_name, version=__version__)

    @app.exception_handler(ResourceNotFoundError)
    async def resource_not_found_handler(
        request: Request, exc: ResourceNotFoundError
    ) -> JSONResponse:
        del request
        payload = ErrorResponse(detail="resource_not_found", resource=exc.resource)
        return JSONResponse(status_code=status.HTTP_404_NOT_FOUND, content=payload.model_dump())

    @app.exception_handler(ConflictError)
    async def conflict_error_handler(request: Request, exc: ConflictError) -> JSONResponse:
        del request
        payload = ErrorResponse(detail=exc.detail, resource=exc.resource)
        return JSONResponse(status_code=status.HTTP_409_CONFLICT, content=payload.model_dump())

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        del request
        payload = ValidationErrorResponse(
            detail="validation_error",
            errors=[
                ValidationErrorItem(
                    field=".".join(str(part) for part in error["loc"]),
                    message=error["msg"],
                )
                for error in exc.errors()
            ],
        )
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            content=payload.model_dump(),
        )

    def _create_lab_record(session: Session, request: LabCreateRequest) -> LabResponse:
        try:
            decision = policy.validate_request(
                profile_name=request.profile_name,
                requested_overrides={},
                requester_type=request.requester_type,
            )
        except KeyError as exc:
            raise ResourceNotFoundError("profile") from exc
        except ValueError as exc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

        lab_state = (
            LabState.PENDING_APPROVAL.value
            if decision.approval_required
            else LabState.APPROVED.value
        )
        lab_id = str(uuid4())
        allocation = storage_allocator.allocate(
            lab_id,
            StoragePolicy(
                filesystem_mode=decision.filesystem_mode,
                persistence_mode=decision.persistence_mode,
                disk_mb=decision.disk_mb,
                retention_days=decision.retention_days,
            ),
        )
        row = LabRow(
            id=lab_id,
            profile_name=decision.profile_name,
            state=lab_state,
            runtime_class=decision.runtime_class.value,
        )
        storage_row = LabStorageRow(
            id=str(uuid4()),
            lab_id=lab_id,
            persistence_mode=allocation.persistence_mode.value,
            root_path=str(allocation.root_path),
            workspace_path=str(allocation.workspace_path),
            exports_path=str(allocation.exports_path),
            quarantine_path=str(allocation.quarantine_path),
            snapshots_path=str(allocation.snapshots_path),
            workspace_mount_target=allocation.workspace_mount_target,
        )
        session.add(row)
        session.add(storage_row)
        if decision.approval_required:
            approval = _record_approval_request(
                session,
                lab_id=lab_id,
                resource_type="lab",
                resource_id=lab_id,
                action="lab.create",
                reason=", ".join(decision.approval_reasons),
                requested_by=request.requester_type,
            )
            _record_event(
                session,
                event_type="approval.requested",
                lab_id=lab_id,
                actor_type="system",
                actor_id="policy-engine",
                resource_type="approval",
                resource_id=approval.id,
                payload={
                    "approval_id": approval.id,
                    "resource_type": approval.resource_type,
                    "resource_id": approval.resource_id,
                    "action": approval.action,
                },
            )
        _record_event(
            session,
            event_type="lab.requested",
            lab_id=lab_id,
            actor_type=request.requester_type.value,
            resource_type="lab",
            resource_id=lab_id,
            payload={
                "profile_name": decision.profile_name,
                "runtime_class": decision.runtime_class.value,
                "state": lab_state,
            },
        )
        session.flush()
        session.refresh(row)
        session.refresh(storage_row)
        return _lab_response_from_row(row, storage_row)

    def _create_run_record(session: Session, request: RunCreateRequest) -> RunResponse:
        lab = session.get(LabRow, request.lab_id)
        if lab is None:
            raise ResourceNotFoundError("lab")

        now = datetime.now(UTC)
        row = RunRow(
            id=str(uuid4()),
            lab_id=request.lab_id,
            state=RunState.QUEUED.value,
            command=request.command,
            timeout_at=now + timedelta(minutes=app_settings.default_run_timeout_minutes),
        )
        session.add(row)
        _record_event(
            session,
            event_type="run.queued",
            lab_id=request.lab_id,
            run_id=row.id,
            actor_type=request.requester_type.value,
            resource_type="run",
            resource_id=row.id,
            payload={"command": row.command, "state": row.state},
        )
        session.flush()
        session.refresh(row)
        return _run_response_from_row(row)

    @app.get("/health", response_model=HealthResponse)
    def health() -> HealthResponse:
        return HealthResponse()

    @app.get("/profiles")
    def list_profiles() -> list[dict[str, object]]:
        return [DEFAULT_PROFILES[name].model_dump(mode="json") for name in sorted(DEFAULT_PROFILES)]

    @app.get("/profiles/{profile_name}")
    def get_profile(profile_name: str) -> dict[str, object]:
        profile = DEFAULT_PROFILES.get(profile_name)
        if profile is None:
            raise ResourceNotFoundError("profile")
        return profile.model_dump(mode="json")

    @app.post("/labs", response_model=LabResponse, status_code=status.HTTP_201_CREATED)
    def create_lab(request: LabCreateRequest) -> LabResponse:
        with db_session_factory() as session:
            response = _create_lab_record(session, request)
            session.commit()
            return response

    @app.get("/labs", response_model=list[LabResponse])
    def list_labs() -> list[LabResponse]:
        with db_session_factory() as session:
            rows = session.scalars(select(LabRow).order_by(LabRow.created_at, LabRow.id)).all()
            lab_ids = [row.id for row in rows]
            storage_rows = session.scalars(
                select(LabStorageRow).where(LabStorageRow.lab_id.in_(lab_ids))
            ).all()
            storage_by_lab_id = {row.lab_id: row for row in storage_rows}
            return [_lab_response_from_row(row, storage_by_lab_id[row.id]) for row in rows]

    @app.get("/labs/{lab_id}", response_model=LabResponse)
    def get_lab(lab_id: str) -> LabResponse:
        with db_session_factory() as session:
            row = session.get(LabRow, lab_id)
            if row is None:
                raise ResourceNotFoundError("lab")
            storage_row = session.scalar(
                select(LabStorageRow).where(LabStorageRow.lab_id == row.id)
            )
            if storage_row is None:
                raise ResourceNotFoundError("lab_storage")
            return _lab_response_from_row(row, storage_row)

    @app.delete("/labs/{lab_id}", response_model=LabResponse)
    def destroy_lab(lab_id: str) -> LabResponse:
        with db_session_factory() as session:
            row = session.get(LabRow, lab_id)
            if row is None:
                raise ResourceNotFoundError("lab")
            storage_row = session.scalar(
                select(LabStorageRow).where(LabStorageRow.lab_id == row.id)
            )
            if storage_row is None:
                raise ResourceNotFoundError("lab_storage")

            if row.state == LabState.DESTROYED.value:
                raise ConflictError("lab_already_destroyed", resource="lab")

            storage_allocator.destroy(_storage_allocation_from_row(storage_row))
            row.state = LabState.DESTROYED.value
            _record_event(
                session,
                event_type="lab.destroyed",
                lab_id=row.id,
                actor_type="human",
                resource_type="lab",
                resource_id=row.id,
                payload={"state": row.state},
            )
            session.commit()
            session.refresh(row)
            session.refresh(storage_row)
            return _lab_response_from_row(row, storage_row)

    @app.post(
        "/labs/{lab_id}/secret-leases",
        response_model=SecretLeaseResponse,
        status_code=status.HTTP_201_CREATED,
    )
    def create_secret_lease(lab_id: str, request: SecretLeaseCreateRequest) -> SecretLeaseResponse:
        with db_session_factory() as session:
            try:
                lease = secret_lease_service.issue_lease(
                    session,
                    lab_id=lab_id,
                    secret_name=request.secret_name,
                    requester_type=request.requester_type,
                    ttl_minutes=request.ttl_minutes,
                )
            except SecretNotFoundError as exc:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"secret value not found for {exc.secret_name}",
                ) from exc
            except LookupError as exc:
                raise ResourceNotFoundError(str(exc)) from exc
            except ValueError as exc:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=str(exc),
                ) from exc

            _record_event(
                session,
                event_type="secret_lease.issued",
                lab_id=lab_id,
                actor_type=request.requester_type.value,
                resource_type="secret_lease",
                resource_id=lease.id,
                payload={
                    "secret_name": lease.secret_name,
                    "approved": lease.approved,
                    "expires_at": lease.expires_at.isoformat(),
                },
            )
            session.commit()
            session.refresh(lease)
            return _secret_lease_response_from_row(lease)

    @app.get("/labs/{lab_id}/secret-leases", response_model=list[SecretLeaseResponse])
    def list_secret_leases(lab_id: str) -> list[SecretLeaseResponse]:
        with db_session_factory() as session:
            if session.get(LabRow, lab_id) is None:
                raise ResourceNotFoundError("lab")
            leases = secret_lease_service.list_leases(session, lab_id=lab_id)
            return [_secret_lease_response_from_row(lease) for lease in leases]

    @app.post("/secret-leases/{lease_id}/revoke", response_model=SecretLeaseResponse)
    def revoke_secret_lease(
        lease_id: str, request: SecretLeaseRevokeRequest
    ) -> SecretLeaseResponse:
        with db_session_factory() as session:
            try:
                lease = secret_lease_service.revoke_lease(session, lease_id=lease_id)
            except LookupError as exc:
                raise ResourceNotFoundError(str(exc)) from exc
            except SecretLeaseStateError as exc:
                raise ConflictError(str(exc), resource="secret_lease") from exc

            _record_event(
                session,
                event_type="secret_lease.revoked",
                lab_id=lease.lab_id,
                actor_type="human",
                actor_id=request.actor,
                resource_type="secret_lease",
                resource_id=lease.id,
                payload={
                    "secret_name": lease.secret_name,
                    "reason": request.reason,
                    "revoked_at": lease.revoked_at.isoformat() if lease.revoked_at else None,
                },
            )
            session.commit()
            session.refresh(lease)
            return _secret_lease_response_from_row(lease)

    @app.post("/runs", response_model=RunResponse, status_code=status.HTTP_201_CREATED)
    def create_run(request: RunCreateRequest) -> RunResponse:
        with db_session_factory() as session:
            response = _create_run_record(session, request)
            session.commit()
            return response

    @app.get("/runs", response_model=list[RunResponse])
    def list_runs() -> list[RunResponse]:
        with db_session_factory() as session:
            rows = session.scalars(select(RunRow).order_by(RunRow.created_at, RunRow.id)).all()
            return [_run_response_from_row(row) for row in rows]

    @app.get("/runs/{run_id}", response_model=RunResponse)
    def get_run(run_id: str) -> RunResponse:
        with db_session_factory() as session:
            row = session.get(RunRow, run_id)
            if row is None:
                raise ResourceNotFoundError("run")
            return _run_response_from_row(row)

    @app.post(
        "/scheduler/jobs",
        response_model=SchedulerJobResponse,
        status_code=status.HTTP_201_CREATED,
    )
    def enqueue_scheduler_job(request: SchedulerJobCreateRequest) -> SchedulerJobResponse:
        with db_session_factory() as session:
            try:
                row = scheduler_service.enqueue(session, request)
            except SchedulerQuotaExceededError as exc:
                raise ConflictError(
                    "scheduler_pending_job_quota_exceeded",
                    resource="scheduler_job",
                ) from exc

            _record_event(
                session,
                event_type="scheduler_job.enqueued",
                actor_type=ActorType.SCHEDULER.value,
                actor_id=request.requester_id,
                resource_type="scheduler_job",
                resource_id=row.id,
                payload={
                    "action": row.action,
                    "scheduled_for": row.scheduled_for.isoformat(),
                    "max_attempts": row.max_attempts,
                },
            )
            session.commit()
            session.refresh(row)
            return _scheduler_job_response_from_row(row)

    @app.get("/scheduler/jobs", response_model=list[SchedulerJobResponse])
    def list_scheduler_jobs() -> list[SchedulerJobResponse]:
        with db_session_factory() as session:
            rows = scheduler_service.list_jobs(session)
            return [_scheduler_job_response_from_row(row) for row in rows]

    @app.post("/scheduler/jobs/dispatch-next", response_model=SchedulerJobResponse)
    def dispatch_next_scheduler_job() -> SchedulerJobResponse:
        with db_session_factory() as session:
            row = scheduler_service.run_next(
                session,
                create_lab=lambda profile_name: _create_lab_record(
                    session,
                    LabCreateRequest(
                        profile_name=profile_name,
                        requester_type=RequesterType.SCHEDULER,
                    ),
                ).id,
                create_run=lambda lab_id, command: _create_run_record(
                    session,
                    RunCreateRequest(
                        lab_id=lab_id,
                        command=command,
                        requester_type=RequesterType.SCHEDULER,
                    ),
                ).id,
            )
            if row is None:
                raise ResourceNotFoundError("scheduler_job")

            _record_event(
                session,
                event_type="scheduler_job.dispatched",
                actor_type=ActorType.SYSTEM.value,
                actor_id="scheduler-worker",
                resource_type="scheduler_job",
                resource_id=row.id,
                payload={
                    "action": row.action,
                    "attempt_count": row.attempt_count,
                },
            )
            terminal_state_event = (
                "scheduler_job.succeeded"
                if row.state == SchedulerJobState.SUCCEEDED.value
                else "scheduler_job.failed"
                if row.state == SchedulerJobState.FAILED.value
                else "scheduler_job.requeued"
            )
            _record_event(
                session,
                event_type=terminal_state_event,
                actor_type=ActorType.SYSTEM.value,
                actor_id="scheduler-worker",
                resource_type="scheduler_job",
                resource_id=row.id,
                payload={
                    "state": row.state,
                    "attempt_count": row.attempt_count,
                    "last_error": row.last_error,
                    "result_resource_type": row.result_resource_type,
                    "result_resource_id": row.result_resource_id,
                },
            )
            session.commit()
            session.refresh(row)
            return _scheduler_job_response_from_row(row)

    @app.get("/approvals", response_model=list[ApprovalResponse])
    def list_approvals() -> list[ApprovalResponse]:
        with db_session_factory() as session:
            rows = session.scalars(
                select(ApprovalRow).order_by(ApprovalRow.created_at, ApprovalRow.id)
            ).all()
            return [_approval_response_from_row(row) for row in rows]

    @app.post("/approvals/{approval_id}/approve", response_model=ApprovalResponse)
    def approve_request(approval_id: str, request: ApprovalDecisionRequest) -> ApprovalResponse:
        with db_session_factory() as session:
            row = session.get(ApprovalRow, approval_id)
            if row is None:
                raise ResourceNotFoundError("approval")

            _apply_approval_decision(
                session,
                row=row,
                decision=ApprovalState.APPROVED,
                actor=request.actor,
                comment=request.comment,
            )
            _record_event(
                session,
                event_type="approval.approved",
                lab_id=row.lab_id,
                actor_type="human",
                actor_id=request.actor,
                resource_type="approval",
                resource_id=row.id,
                payload={
                    "approval_id": row.id,
                    "resource_type": row.resource_type,
                    "resource_id": row.resource_id,
                    "action": row.action,
                    "actor": request.actor,
                    "comment": request.comment,
                },
            )
            session.commit()
            session.refresh(row)
            return _approval_response_from_row(row)

    @app.post("/approvals/{approval_id}/deny", response_model=ApprovalResponse)
    def deny_request(approval_id: str, request: ApprovalDecisionRequest) -> ApprovalResponse:
        with db_session_factory() as session:
            row = session.get(ApprovalRow, approval_id)
            if row is None:
                raise ResourceNotFoundError("approval")

            _apply_approval_decision(
                session,
                row=row,
                decision=ApprovalState.REJECTED,
                actor=request.actor,
                comment=request.comment,
            )
            _record_event(
                session,
                event_type="approval.denied",
                lab_id=row.lab_id,
                actor_type="human",
                actor_id=request.actor,
                resource_type="approval",
                resource_id=row.id,
                payload={
                    "approval_id": row.id,
                    "resource_type": row.resource_type,
                    "resource_id": row.resource_id,
                    "action": row.action,
                    "actor": request.actor,
                    "comment": request.comment,
                },
            )
            session.commit()
            session.refresh(row)
            return _approval_response_from_row(row)

    @app.get("/snapshots", response_model=list[SnapshotResponse])
    def list_snapshots() -> list[SnapshotResponse]:
        with db_session_factory() as session:
            rows = session.scalars(
                select(SnapshotRow).order_by(SnapshotRow.created_at, SnapshotRow.id)
            ).all()
            return [
                _snapshot_response_from_row(
                    row,
                    snapshot_manager.load_metadata(row),
                )
                for row in rows
            ]

    @app.post("/snapshots", response_model=SnapshotResponse, status_code=status.HTTP_201_CREATED)
    def create_snapshot(request: SnapshotCreateRequest) -> SnapshotResponse:
        with db_session_factory() as session:
            lab = session.get(LabRow, request.lab_id)
            if lab is None:
                raise ResourceNotFoundError("lab")
            storage_row = session.scalar(
                select(LabStorageRow).where(LabStorageRow.lab_id == request.lab_id)
            )
            if storage_row is None:
                raise ResourceNotFoundError("lab_storage")

            if request.run_id is not None:
                run = session.get(RunRow, request.run_id)
                if run is None:
                    raise ResourceNotFoundError("run")
                if run.lab_id != lab.id:
                    raise ConflictError("snapshot_run_mismatch", resource="snapshot")

            snapshot_id = str(uuid4())
            try:
                metadata = snapshot_manager.create_snapshot(
                    snapshot_id,
                    lab=lab,
                    storage=storage_row,
                    run_id=request.run_id,
                )
            except UnsupportedSnapshotRuntimeError as exc:
                raise ConflictError("unsupported_snapshot_runtime", resource="snapshot") from exc

            row = SnapshotRow(id=snapshot_id, lab_id=lab.id, backend_ref=metadata.backend_ref)
            session.add(row)
            _record_event(
                session,
                event_type="snapshot.created",
                lab_id=lab.id,
                run_id=request.run_id,
                actor_type=request.requester_type.value,
                resource_type="snapshot",
                resource_id=snapshot_id,
                payload={
                    "backend_ref": metadata.backend_ref,
                    "runtime_class": metadata.runtime_class,
                    "state": metadata.state,
                },
            )
            session.commit()
            session.refresh(row)
            return _snapshot_response_from_row(row, metadata)

    @app.post("/snapshots/{snapshot_id}/restore", response_model=SnapshotResponse)
    def restore_snapshot(snapshot_id: str, request: SnapshotRestoreRequest) -> SnapshotResponse:
        with db_session_factory() as session:
            snapshot = session.get(SnapshotRow, snapshot_id)
            if snapshot is None:
                raise ResourceNotFoundError("snapshot")

            target_lab = session.get(LabRow, request.lab_id)
            if target_lab is None:
                raise ResourceNotFoundError("lab")
            target_storage = session.scalar(
                select(LabStorageRow).where(LabStorageRow.lab_id == target_lab.id)
            )
            if target_storage is None:
                raise ResourceNotFoundError("lab_storage")

            try:
                metadata = snapshot_manager.restore_snapshot(
                    snapshot,
                    target_lab=target_lab,
                    target_storage=target_storage,
                )
            except UnsupportedSnapshotRuntimeError as exc:
                raise ConflictError("unsupported_snapshot_runtime", resource="snapshot") from exc
            except SnapshotMetadataError as exc:
                raise ConflictError(str(exc), resource="snapshot") from exc

            _record_event(
                session,
                event_type="snapshot.restored",
                lab_id=target_lab.id,
                run_id=metadata.run_id,
                actor_type=request.requester_type.value,
                resource_type="snapshot",
                resource_id=snapshot.id,
                payload={
                    "source_lab_id": snapshot.lab_id,
                    "restored_lab_id": target_lab.id,
                    "state": metadata.state,
                },
            )
            session.commit()
            return _snapshot_response_from_row(snapshot, metadata)

    @app.post("/exports", response_model=ExportResponse, status_code=status.HTTP_201_CREATED)
    def create_export(request: ExportCreateRequest) -> ExportResponse:
        with db_session_factory() as session:
            lab = session.get(LabRow, request.lab_id)
            if lab is None:
                raise ResourceNotFoundError("lab")
            storage_row = session.scalar(
                select(LabStorageRow).where(LabStorageRow.lab_id == request.lab_id)
            )
            if storage_row is None:
                raise ResourceNotFoundError("lab_storage")

            if request.run_id is not None:
                run = session.get(RunRow, request.run_id)
                if run is None:
                    raise ResourceNotFoundError("run")
                if run.lab_id != lab.id:
                    raise ConflictError("export_run_mismatch", resource="export")

            export_id = str(uuid4())
            _record_event(
                session,
                event_type="export.requested",
                lab_id=lab.id,
                run_id=request.run_id,
                actor_type=request.requester_type.value,
                resource_type="export",
                resource_id=export_id,
                payload={
                    "export_id": export_id,
                    "source_path": request.source_path,
                },
            )
            try:
                staged = export_gate.stage_export(
                    export_id,
                    lab=lab,
                    storage=storage_row,
                    source_path=request.source_path,
                    run_id=request.run_id,
                )
            except ExportSourceNotFoundError as exc:
                raise ResourceNotFoundError("export_source") from exc
            except ExportPolicyError as exc:
                raise ConflictError(str(exc), resource="export") from exc

            row = ExportRow(
                id=export_id,
                lab_id=lab.id,
                run_id=request.run_id,
                source_path=staged.provenance.source_path,
                state=staged.state.value,
                quarantine_path=staged.provenance.quarantine_path,
                released_path=staged.provenance.released_path,
                approval_required=staged.approval_required,
                sha256=staged.provenance.artifact_hash.digest,
                size_bytes=staged.provenance.size_bytes,
                denial_reason=None,
            )
            session.add(row)
            _record_event(
                session,
                event_type="export.staged",
                lab_id=lab.id,
                run_id=request.run_id,
                actor_type="system",
                actor_id="export-gate",
                resource_type="export",
                resource_id=export_id,
                payload={
                    "export_id": export_id,
                    "source_path": row.source_path,
                    "quarantine_path": row.quarantine_path,
                    "sha256": row.sha256,
                    "size_bytes": row.size_bytes,
                    "approval_required": row.approval_required,
                },
            )
            if staged.approval_required:
                approval = _record_approval_request(
                    session,
                    lab_id=lab.id,
                    resource_type="export",
                    resource_id=export_id,
                    action="export.release",
                    reason="profile requires export approval",
                    requested_by="system",
                )
                _record_event(
                    session,
                    event_type="approval.requested",
                    lab_id=lab.id,
                    run_id=request.run_id,
                    actor_type="system",
                    actor_id="policy-engine",
                    resource_type="approval",
                    resource_id=approval.id,
                    payload={
                        "approval_id": approval.id,
                        "resource_type": approval.resource_type,
                        "resource_id": approval.resource_id,
                        "action": approval.action,
                    },
                )
            session.commit()
            session.refresh(row)
            return _export_response_from_row(row)

    @app.post("/exports/{export_id}/release", response_model=ExportResponse)
    def release_export(export_id: str) -> ExportResponse:
        with db_session_factory() as session:
            row = session.get(ExportRow, export_id)
            if row is None:
                raise ResourceNotFoundError("export")
            storage_row = session.scalar(
                select(LabStorageRow).where(LabStorageRow.lab_id == row.lab_id)
            )
            if storage_row is None:
                raise ResourceNotFoundError("lab_storage")

            try:
                released = export_gate.release_export(row, storage=storage_row)
            except ExportSourceNotFoundError as exc:
                raise ResourceNotFoundError("export_source") from exc
            except ExportPolicyError as exc:
                _record_event(
                    session,
                    event_type="export.release_blocked",
                    lab_id=row.lab_id,
                    run_id=row.run_id,
                    actor_type="system",
                    actor_id="export-gate",
                    resource_type="export",
                    resource_id=row.id,
                    payload={
                        "export_id": row.id,
                        "reason": str(exc),
                    },
                )
                session.commit()
                raise ConflictError(str(exc), resource="export") from exc
            except ExportStateError as exc:
                raise ConflictError(str(exc), resource="export") from exc

            row.state = released.state.value
            row.released_path = released.provenance.released_path
            row.denial_reason = None
            _record_event(
                session,
                event_type="export.released",
                lab_id=row.lab_id,
                run_id=row.run_id,
                actor_type="system",
                actor_id="export-gate",
                resource_type="export",
                resource_id=row.id,
                payload={
                    "export_id": row.id,
                    "released_path": row.released_path,
                },
            )
            session.commit()
            session.refresh(row)
            return _export_response_from_row(row)

    @app.post("/exports/{export_id}/deny", response_model=ExportResponse)
    def deny_export(export_id: str, request: ExportDenyRequest) -> ExportResponse:
        with db_session_factory() as session:
            row = session.get(ExportRow, export_id)
            if row is None:
                raise ResourceNotFoundError("export")

            try:
                denied = export_gate.deny_export(row, reason=request.reason)
            except ExportStateError as exc:
                raise ConflictError(str(exc), resource="export") from exc

            row.state = denied.state.value
            row.denial_reason = denied.denial_reason
            row.released_path = None
            _record_event(
                session,
                event_type="export.denied",
                lab_id=row.lab_id,
                run_id=row.run_id,
                actor_type="human",
                resource_type="export",
                resource_id=row.id,
                payload={
                    "export_id": row.id,
                    "reason": row.denial_reason,
                },
            )
            session.commit()
            session.refresh(row)
            return _export_response_from_row(row)

    @app.get("/exports", response_model=list[ExportResponse])
    def list_exports() -> list[ExportResponse]:
        with db_session_factory() as session:
            rows = session.scalars(
                select(ExportRow).order_by(ExportRow.created_at, ExportRow.id)
            ).all()
            return [_export_response_from_row(row) for row in rows]

    @app.get("/events", response_model=list[EventResponse])
    def list_events(
        event_type: str | None = None,
        actor_type: str | None = None,
        resource_type: str | None = None,
        resource_id: str | None = None,
        lab_id: str | None = None,
        run_id: str | None = None,
    ) -> list[EventResponse]:
        with db_session_factory() as session:
            query = select(EventRow)
            if event_type is not None:
                query = query.where(EventRow.event_type == event_type)
            if actor_type is not None:
                query = query.where(EventRow.actor_type == actor_type)
            if resource_type is not None:
                query = query.where(EventRow.resource_type == resource_type)
            if resource_id is not None:
                query = query.where(EventRow.resource_id == resource_id)
            if lab_id is not None:
                query = query.where(EventRow.lab_id == lab_id)
            if run_id is not None:
                query = query.where(EventRow.run_id == run_id)
            rows = session.scalars(query.order_by(EventRow.created_at, EventRow.id)).all()
            return [_event_response_from_row(row) for row in rows]

    return app


app = create_app()

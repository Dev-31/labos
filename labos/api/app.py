from __future__ import annotations

from datetime import datetime
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
from labos.core.models import (
    ApprovalResponse,
    ErrorResponse,
    EventResponse,
    ExportResponse,
    HealthResponse,
    LabCreateRequest,
    LabResponse,
    LabStorageResponse,
    RunCreateRequest,
    RunResponse,
    SnapshotCreateRequest,
    SnapshotResponse,
    SnapshotRestoreRequest,
    ValidationErrorItem,
    ValidationErrorResponse,
)
from labos.core.policy_engine import PolicyEngine
from labos.db.schema import (
    ApprovalRow,
    EventRow,
    ExportRow,
    LabRow,
    LabStorageRow,
    RunRow,
    SnapshotRow,
)
from labos.db.session import build_session_factory
from labos.storage import ManagedStorageAllocator, SnapshotManager, StoragePolicy
from labos.storage.snapshots import (
    SnapshotMetadata,
    SnapshotMetadataError,
    UnsupportedSnapshotRuntimeError,
)


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


def _run_response_from_row(row: RunRow) -> RunResponse:
    return RunResponse(
        id=row.id,
        lab_id=row.lab_id,
        state=row.state,
        command=row.command,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def _approval_response_from_row(row: ApprovalRow) -> ApprovalResponse:
    return ApprovalResponse(
        id=row.id,
        lab_id=row.lab_id,
        action=row.action,
        approved=row.approved,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


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
        source_path=row.source_path,
        sha256=row.sha256,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def _event_response_from_row(row: EventRow) -> EventResponse:
    return EventResponse(
        id=row.id,
        lab_id=row.lab_id,
        run_id=row.run_id,
        event_type=row.event_type,
        payload_json=row.payload_json,
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

        lab_state = "pending_approval" if decision.approval_required else "approved"
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
        with db_session_factory() as session:
            session.add(row)
            session.add(storage_row)
            session.commit()
            session.refresh(row)
            session.refresh(storage_row)
            return _lab_response_from_row(row, storage_row)

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

    @app.post("/runs", response_model=RunResponse, status_code=status.HTTP_201_CREATED)
    def create_run(request: RunCreateRequest) -> RunResponse:
        with db_session_factory() as session:
            lab = session.get(LabRow, request.lab_id)
            if lab is None:
                raise ResourceNotFoundError("lab")

            row = RunRow(
                id=str(uuid4()),
                lab_id=request.lab_id,
                state="queued",
                command=request.command,
            )
            session.add(row)
            session.commit()
            session.refresh(row)
            return _run_response_from_row(row)

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

    @app.get("/approvals", response_model=list[ApprovalResponse])
    def list_approvals() -> list[ApprovalResponse]:
        with db_session_factory() as session:
            rows = session.scalars(
                select(ApprovalRow).order_by(ApprovalRow.created_at, ApprovalRow.id)
            ).all()
            return [_approval_response_from_row(row) for row in rows]

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

            return _snapshot_response_from_row(snapshot, metadata)

    @app.get("/exports", response_model=list[ExportResponse])
    def list_exports() -> list[ExportResponse]:
        with db_session_factory() as session:
            rows = session.scalars(
                select(ExportRow).order_by(ExportRow.created_at, ExportRow.id)
            ).all()
            return [_export_response_from_row(row) for row in rows]

    @app.get("/events", response_model=list[EventResponse])
    def list_events() -> list[EventResponse]:
        with db_session_factory() as session:
            rows = session.scalars(
                select(EventRow).order_by(EventRow.created_at, EventRow.id)
            ).all()
            return [_event_response_from_row(row) for row in rows]

    return app


app = create_app()

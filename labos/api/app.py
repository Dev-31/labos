from __future__ import annotations

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
    RunCreateRequest,
    RunResponse,
    SnapshotResponse,
    ValidationErrorItem,
    ValidationErrorResponse,
)
from labos.core.policy_engine import PolicyEngine
from labos.db.schema import ApprovalRow, EventRow, ExportRow, LabRow, RunRow, SnapshotRow
from labos.db.session import build_session_factory


class ResourceNotFoundError(Exception):
    def __init__(self, resource: str) -> None:
        self.resource = resource
        super().__init__(resource)


def _lab_response_from_row(row: LabRow) -> LabResponse:
    return LabResponse(
        id=row.id,
        profile_name=row.profile_name,
        state=row.state,
        runtime_class=row.runtime_class,
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


def _snapshot_response_from_row(row: SnapshotRow) -> SnapshotResponse:
    return SnapshotResponse(
        id=row.id,
        lab_id=row.lab_id,
        backend_ref=row.backend_ref,
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
) -> FastAPI:
    app_settings = settings or load_settings()
    db_session_factory = session_factory or build_session_factory(app_settings.database_url)
    policy = policy_engine or PolicyEngine()

    app = FastAPI(title=app_settings.app_name, version=__version__)

    @app.exception_handler(ResourceNotFoundError)
    async def resource_not_found_handler(
        request: Request, exc: ResourceNotFoundError
    ) -> JSONResponse:
        del request
        payload = ErrorResponse(detail="resource_not_found", resource=exc.resource)
        return JSONResponse(status_code=status.HTTP_404_NOT_FOUND, content=payload.model_dump())

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
        row = LabRow(
            id=str(uuid4()),
            profile_name=decision.profile_name,
            state=lab_state,
            runtime_class=decision.runtime_class.value,
        )
        with db_session_factory() as session:
            session.add(row)
            session.commit()
            session.refresh(row)
            return _lab_response_from_row(row)

    @app.get("/labs", response_model=list[LabResponse])
    def list_labs() -> list[LabResponse]:
        with db_session_factory() as session:
            rows = session.scalars(select(LabRow).order_by(LabRow.created_at, LabRow.id)).all()
            return [_lab_response_from_row(row) for row in rows]

    @app.get("/labs/{lab_id}", response_model=LabResponse)
    def get_lab(lab_id: str) -> LabResponse:
        with db_session_factory() as session:
            row = session.get(LabRow, lab_id)
            if row is None:
                raise ResourceNotFoundError("lab")
            return _lab_response_from_row(row)

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
            return [_snapshot_response_from_row(row) for row in rows]

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

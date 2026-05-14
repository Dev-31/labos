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
    ErrorResponse,
    HealthResponse,
    LabCreateRequest,
    LabResponse,
    ValidationErrorItem,
    ValidationErrorResponse,
)
from labos.core.policy_engine import PolicyEngine
from labos.db.schema import LabRow
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

    return app


app = create_app()

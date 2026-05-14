from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class HealthResponse(BaseModel):
    status: str = "ok"


class LabCreateRequest(BaseModel):
    profile_name: str
    requester_type: str


class LabStorageResponse(BaseModel):
    persistence_mode: str
    root_path: str
    workspace_path: str
    exports_path: str
    quarantine_path: str
    snapshots_path: str
    workspace_mount_target: str


class LabResponse(BaseModel):
    id: str
    profile_name: str
    state: str
    runtime_class: str
    storage: LabStorageResponse
    created_at: datetime
    updated_at: datetime


class RunCreateRequest(BaseModel):
    lab_id: str
    command: str


class RunResponse(BaseModel):
    id: str
    lab_id: str
    state: str
    command: str
    created_at: datetime
    updated_at: datetime


class ApprovalResponse(BaseModel):
    id: str
    lab_id: str | None
    action: str
    approved: bool
    created_at: datetime
    updated_at: datetime


class SnapshotResponse(BaseModel):
    id: str
    lab_id: str
    backend_ref: str
    created_at: datetime
    updated_at: datetime


class ExportResponse(BaseModel):
    id: str
    lab_id: str
    source_path: str
    sha256: str
    created_at: datetime
    updated_at: datetime


class EventResponse(BaseModel):
    id: str
    lab_id: str | None
    run_id: str | None
    event_type: str
    payload_json: str
    created_at: datetime
    updated_at: datetime


class ErrorResponse(BaseModel):
    detail: str
    resource: str | None = None


class ValidationErrorItem(BaseModel):
    field: str
    message: str


class ValidationErrorResponse(BaseModel):
    detail: str
    errors: list[ValidationErrorItem]

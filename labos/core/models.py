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


class ApprovalDecisionRequest(BaseModel):
    actor: str
    comment: str | None = None


class ApprovalResponse(BaseModel):
    id: str
    lab_id: str | None
    resource_type: str
    resource_id: str
    action: str
    reason: str
    requested_by: str
    state: str
    approved: bool
    decision_comment: str | None = None
    decided_by: str | None = None
    expires_at: datetime | None = None
    decided_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class SnapshotCreateRequest(BaseModel):
    lab_id: str
    run_id: str | None = None


class SnapshotRestoreRequest(BaseModel):
    lab_id: str


class SnapshotResponse(BaseModel):
    id: str
    lab_id: str
    backend_ref: str
    run_id: str | None = None
    profile_name: str | None = None
    runtime_class: str | None = None
    state: str | None = None
    manifest_path: str | None = None
    sha256: str | None = None
    size_bytes: int | None = None
    restored_at: datetime | None = None
    restored_lab_id: str | None = None
    created_at: datetime
    updated_at: datetime


class ExportCreateRequest(BaseModel):
    lab_id: str
    source_path: str
    run_id: str | None = None


class ExportDenyRequest(BaseModel):
    reason: str


class ExportResponse(BaseModel):
    id: str
    lab_id: str
    run_id: str | None = None
    source_path: str
    state: str
    quarantine_path: str
    released_path: str | None = None
    approval_required: bool
    sha256: str
    size_bytes: int
    denial_reason: str | None = None
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

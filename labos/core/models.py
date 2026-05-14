from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field, model_validator

from labos.core.enums import ActorType, SchedulerAction, SchedulerJobState
from labos.core.policy_models import RequesterType


class HealthResponse(BaseModel):
    status: str = "ok"


class LabCreateRequest(BaseModel):
    profile_name: str
    requester_type: RequesterType


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


class SecretLeaseCreateRequest(BaseModel):
    secret_name: str
    requester_type: RequesterType = RequesterType.HUMAN
    ttl_minutes: int = Field(default=15, ge=1, le=24 * 60)


class SecretLeaseRevokeRequest(BaseModel):
    actor: str
    reason: str | None = None


class SecretLeaseResponse(BaseModel):
    id: str
    lab_id: str
    secret_name: str
    approved: bool
    expires_at: datetime
    revoked_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class RunCreateRequest(BaseModel):
    lab_id: str
    command: str
    requester_type: RequesterType = RequesterType.HUMAN


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
    requester_type: RequesterType = RequesterType.HUMAN


class SnapshotRestoreRequest(BaseModel):
    lab_id: str
    requester_type: RequesterType = RequesterType.HUMAN


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
    requester_type: RequesterType = RequesterType.HUMAN


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
    actor_type: ActorType
    actor_id: str | None = None
    resource_type: str | None = None
    resource_id: str | None = None
    payload_json: str
    created_at: datetime
    updated_at: datetime


class SchedulerJobCreateRequest(BaseModel):
    action: SchedulerAction
    requester_id: str = Field(min_length=1)
    profile_name: str | None = None
    lab_id: str | None = None
    command: str | None = None
    scheduled_for: datetime | None = None
    max_attempts: int = Field(default=3, ge=1, le=10)

    @model_validator(mode="after")
    def validate_action_payload(self) -> SchedulerJobCreateRequest:
        if self.action is SchedulerAction.CREATE_LAB:
            if self.profile_name is None:
                raise ValueError("profile_name is required for create_lab jobs")
            if self.lab_id is not None or self.command is not None:
                raise ValueError("create_lab jobs do not accept lab_id or command")
        elif self.action is SchedulerAction.START_RUN:
            if self.lab_id is None:
                raise ValueError("lab_id is required for start_run jobs")
            if self.command is None:
                raise ValueError("command is required for start_run jobs")
            if self.profile_name is not None:
                raise ValueError("start_run jobs do not accept profile_name")
        return self


class SchedulerJobResponse(BaseModel):
    id: str
    action: SchedulerAction
    state: SchedulerJobState
    requester_id: str
    profile_name: str | None = None
    lab_id: str | None = None
    command: str | None = None
    scheduled_for: datetime
    attempt_count: int
    max_attempts: int
    last_error: str | None = None
    result_resource_type: str | None = None
    result_resource_id: str | None = None
    dispatched_at: datetime | None = None
    completed_at: datetime | None = None
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

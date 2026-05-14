from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class HealthResponse(BaseModel):
    status: str = "ok"


class LabCreateRequest(BaseModel):
    profile_name: str
    requester_type: str


class LabResponse(BaseModel):
    id: str
    profile_name: str
    state: str
    runtime_class: str
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

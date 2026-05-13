from __future__ import annotations

from datetime import UTC, datetime
from typing import ClassVar
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field

from labos.core.enums import (
    ApprovalState,
    AuditLevel,
    ExportState,
    LabState,
    RunState,
    SnapshotState,
)


def _utc_now() -> datetime:
    return datetime.now(UTC)


class EntityRecord(BaseModel):
    model_config = ConfigDict(frozen=False, use_enum_values=False)

    id: str = Field(default_factory=lambda: str(uuid4()))
    created_at: datetime = Field(default_factory=_utc_now)
    updated_at: datetime = Field(default_factory=_utc_now)

    immutable_fields: ClassVar[frozenset[str]] = frozenset({"id", "created_at"})

    def validate_update_from(self, previous: EntityRecord) -> None:
        changed_fields = [
            field_name
            for field_name in self.immutable_fields
            if getattr(self, field_name) != getattr(previous, field_name)
        ]
        if changed_fields:
            field_list = ", ".join(sorted(changed_fields))
            raise ValueError(f"immutable fields changed: {field_list}")


class ProfileRecord(EntityRecord):
    name: str
    runtime_class: str
    network_mode: str
    filesystem_mode: str
    persistence_mode: str
    export_mode: str
    approval_required: bool = False
    audit_level: AuditLevel = AuditLevel.BASIC

    immutable_fields: ClassVar[frozenset[str]] = EntityRecord.immutable_fields | frozenset({"name"})


class LabRecord(EntityRecord):
    profile_name: str
    state: LabState

    immutable_fields: ClassVar[frozenset[str]] = (
        EntityRecord.immutable_fields | frozenset({"profile_name"})
    )


class RunRecord(EntityRecord):
    lab_id: str
    state: RunState

    immutable_fields: ClassVar[frozenset[str]] = (
        EntityRecord.immutable_fields | frozenset({"lab_id"})
    )


class ApprovalRequestRecord(EntityRecord):
    lab_id: str
    requester: str
    state: ApprovalState = ApprovalState.REQUESTED
    reason: str

    immutable_fields: ClassVar[frozenset[str]] = EntityRecord.immutable_fields | frozenset(
        {"lab_id", "requester", "reason"}
    )


class SnapshotRecord(EntityRecord):
    lab_id: str
    state: SnapshotState = SnapshotState.PENDING
    storage_uri: str | None = None

    immutable_fields: ClassVar[frozenset[str]] = (
        EntityRecord.immutable_fields | frozenset({"lab_id"})
    )


class ExportRequestRecord(EntityRecord):
    lab_id: str
    artifact_path: str
    state: ExportState = ExportState.REQUESTED
    checksum_sha256: str | None = None

    immutable_fields: ClassVar[frozenset[str]] = EntityRecord.immutable_fields | frozenset(
        {"lab_id", "artifact_path"}
    )


class AuditEventRecord(EntityRecord):
    lab_id: str | None = None
    run_id: str | None = None
    actor: str
    action: str
    detail: str


class SecretLeaseRecord(EntityRecord):
    lab_id: str
    secret_name: str
    expires_at: datetime

    immutable_fields: ClassVar[frozenset[str]] = EntityRecord.immutable_fields | frozenset(
        {"lab_id", "secret_name", "expires_at"}
    )


class SchedulerJobRecord(EntityRecord):
    profile_name: str
    cron: str
    enabled: bool = True

    immutable_fields: ClassVar[frozenset[str]] = EntityRecord.immutable_fields | frozenset(
        {"profile_name", "cron"}
    )

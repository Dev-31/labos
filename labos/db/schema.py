from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """Shared declarative base for durable LabOS metadata."""


def utc_now() -> datetime:
    return datetime.now(UTC)


class TimestampedRow:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )


class LabRow(TimestampedRow, Base):
    __tablename__ = "labs"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    profile_name: Mapped[str] = mapped_column(String(128), nullable=False)
    state: Mapped[str] = mapped_column(String(32), nullable=False)
    runtime_class: Mapped[str] = mapped_column(String(32), nullable=False)


class LabStorageRow(TimestampedRow, Base):
    __tablename__ = "lab_storage"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    lab_id: Mapped[str] = mapped_column(
        ForeignKey("labs.id", ondelete="CASCADE"), nullable=False, unique=True
    )
    persistence_mode: Mapped[str] = mapped_column(String(32), nullable=False)
    root_path: Mapped[str] = mapped_column(String(512), nullable=False)
    workspace_path: Mapped[str] = mapped_column(String(512), nullable=False)
    exports_path: Mapped[str] = mapped_column(String(512), nullable=False)
    quarantine_path: Mapped[str] = mapped_column(String(512), nullable=False)
    snapshots_path: Mapped[str] = mapped_column(String(512), nullable=False)
    workspace_mount_target: Mapped[str] = mapped_column(String(128), nullable=False)


class RunRow(TimestampedRow, Base):
    __tablename__ = "runs"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    lab_id: Mapped[str] = mapped_column(ForeignKey("labs.id", ondelete="CASCADE"), nullable=False)
    state: Mapped[str] = mapped_column(String(32), nullable=False)
    command: Mapped[str] = mapped_column(Text, nullable=False)
    timeout_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class ApprovalRow(TimestampedRow, Base):
    __tablename__ = "approvals"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    lab_id: Mapped[str | None] = mapped_column(
        ForeignKey("labs.id", ondelete="SET NULL"), nullable=True
    )
    resource_type: Mapped[str] = mapped_column(String(32), nullable=False)
    resource_id: Mapped[str] = mapped_column(String(64), nullable=False)
    action: Mapped[str] = mapped_column(String(128), nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    requested_by: Mapped[str] = mapped_column(String(64), nullable=False)
    state: Mapped[str] = mapped_column(String(32), nullable=False, default="requested")
    approved: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    decision_comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    decided_by: Mapped[str | None] = mapped_column(String(64), nullable=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    @staticmethod
    def default_expiry() -> datetime:
        return utc_now() + timedelta(hours=24)


class ExportRow(TimestampedRow, Base):
    __tablename__ = "exports"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    lab_id: Mapped[str] = mapped_column(ForeignKey("labs.id", ondelete="CASCADE"), nullable=False)
    run_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    source_path: Mapped[str] = mapped_column(String(512), nullable=False)
    state: Mapped[str] = mapped_column(String(32), nullable=False)
    quarantine_path: Mapped[str] = mapped_column(String(512), nullable=False)
    released_path: Mapped[str | None] = mapped_column(String(512), nullable=True)
    approval_required: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    denial_reason: Mapped[str | None] = mapped_column(Text, nullable=True)


class SnapshotRow(TimestampedRow, Base):
    __tablename__ = "snapshots"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    lab_id: Mapped[str] = mapped_column(ForeignKey("labs.id", ondelete="CASCADE"), nullable=False)
    backend_ref: Mapped[str] = mapped_column(String(512), nullable=False)


class SecretLeaseRow(TimestampedRow, Base):
    __tablename__ = "secret_leases"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    lab_id: Mapped[str] = mapped_column(
        ForeignKey("labs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    secret_name: Mapped[str] = mapped_column(String(128), nullable=False)
    approved: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class EventRow(TimestampedRow, Base):
    __tablename__ = "events"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    lab_id: Mapped[str | None] = mapped_column(
        ForeignKey("labs.id", ondelete="SET NULL"), nullable=True, index=True
    )
    run_id: Mapped[str | None] = mapped_column(
        ForeignKey("runs.id", ondelete="SET NULL"), nullable=True, index=True
    )
    event_type: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    actor_type: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="system",
        index=True,
    )
    actor_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    resource_type: Mapped[str | None] = mapped_column(String(32), nullable=True, index=True)
    resource_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    payload_json: Mapped[str] = mapped_column(Text, nullable=False)


class SchedulerJobRow(TimestampedRow, Base):
    __tablename__ = "scheduler_jobs"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    action: Mapped[str] = mapped_column(String(32), nullable=False)
    state: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    requester_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    profile_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    lab_id: Mapped[str | None] = mapped_column(
        ForeignKey("labs.id", ondelete="SET NULL"), nullable=True, index=True
    )
    command: Mapped[str | None] = mapped_column(Text, nullable=True)
    scheduled_for: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )
    attempt_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    max_attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=3)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    result_resource_type: Mapped[str | None] = mapped_column(String(32), nullable=True)
    result_resource_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    dispatched_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

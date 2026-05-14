from enum import StrEnum


class LabState(StrEnum):
    REQUESTED = "requested"
    PENDING_APPROVAL = "pending_approval"
    APPROVED = "approved"
    PROVISIONING = "provisioning"
    RUNNING = "running"
    STOPPED = "stopped"
    FAILED = "failed"
    DESTROYING = "destroying"
    DESTROYED = "destroyed"
    ARCHIVED = "archived"


class RunState(StrEnum):
    QUEUED = "queued"
    STARTING = "starting"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    TIMED_OUT = "timed_out"


class ApprovalState(StrEnum):
    REQUESTED = "requested"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXPIRED = "expired"


class ExportState(StrEnum):
    REQUESTED = "requested"
    QUARANTINED = "quarantined"
    APPROVED = "approved"
    RELEASED = "released"
    REJECTED = "rejected"


class SnapshotState(StrEnum):
    PENDING = "pending"
    CREATED = "created"
    FAILED = "failed"
    RESTORED = "restored"


class ActorType(StrEnum):
    HUMAN = "human"
    AGENT = "agent"
    SCHEDULER = "scheduler"
    SYSTEM = "system"


class AuditLevel(StrEnum):
    BASIC = "basic"
    DETAILED = "detailed"
    FORENSIC = "forensic"

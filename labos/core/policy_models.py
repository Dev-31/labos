from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, model_validator

from labos.core.enums import AuditLevel


class RuntimeClass(StrEnum):
    CONTAINER = "container"
    MICROVM = "microvm"


class NetworkMode(StrEnum):
    DENY = "deny"
    RESTRICTED = "restricted"
    ALLOWLIST = "allowlist"


class FilesystemMode(StrEnum):
    MANAGED = "managed"
    READ_ONLY_ROOT = "read-only-root"


class PersistenceMode(StrEnum):
    EPHEMERAL = "ephemeral"
    PERSISTENT = "persistent"


class ExportMode(StrEnum):
    REQUEST = "request"
    APPROVAL = "approval"


class RiskClass(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class RequesterType(StrEnum):
    HUMAN = "human"
    AGENT = "agent"
    SCHEDULER = "scheduler"


class Profile(BaseModel):
    model_config = ConfigDict(use_enum_values=False)

    name: str
    runtime_class: RuntimeClass
    risk_class: RiskClass
    network_mode: NetworkMode
    filesystem_mode: FilesystemMode
    persistence_mode: PersistenceMode
    export_mode: ExportMode
    cpu_limit: int = Field(ge=1)
    memory_mb: int = Field(ge=256)
    disk_mb: int = Field(ge=1024)
    max_runtime_minutes: int = Field(ge=1)
    approval_on_start: bool = False
    approval_on_export: bool = False
    audit_level: AuditLevel = AuditLevel.BASIC
    retention_days: int = Field(ge=1)
    allow_host_mounts: bool = False
    allowed_secret_names: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_combinations(self) -> Profile:
        if self.runtime_class is RuntimeClass.MICROVM:
            if self.network_mode is not NetworkMode.DENY:
                raise ValueError("microVM profiles must deny network egress")
            if self.export_mode is not ExportMode.APPROVAL:
                raise ValueError("microVM profiles must require approval-based exports")
            if not self.approval_on_start:
                raise ValueError("microVM profiles must require approval on start")
            if self.allow_host_mounts:
                raise ValueError("microVM profiles cannot allow host mounts")

        if self.risk_class in {RiskClass.HIGH, RiskClass.CRITICAL} and not self.approval_on_export:
            raise ValueError("high-risk profiles must require export approval")

        if self.risk_class is RiskClass.LOW and self.runtime_class is RuntimeClass.MICROVM:
            raise ValueError("low-risk profiles cannot require a microVM runtime")

        return self

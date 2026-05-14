from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Protocol

from labos.core.policy_models import NetworkMode, PersistenceMode


@dataclass(frozen=True)
class ManagedMount:
    source: str
    target: str
    read_only: bool = False


@dataclass(frozen=True)
class SecretLease:
    name: str
    value: str
    approved: bool
    expires_at: datetime

    def is_active(self, now: datetime | None = None) -> bool:
        current_time = now or datetime.now(UTC)
        return self.expires_at > current_time


@dataclass(frozen=True)
class RuntimeSpec:
    image: str
    network_mode: NetworkMode
    persistence_mode: PersistenceMode
    cpu_limit: int
    memory_mb: int
    managed_mounts: list[ManagedMount] = field(default_factory=list)
    secret_leases: list[SecretLease] = field(default_factory=list)
    labels: dict[str, str] = field(default_factory=dict)
    command: list[str] | None = None


@dataclass(frozen=True)
class ProvisionedLab:
    lab_id: str
    backend: str
    container_name: str
    network_name: str | None
    volume_names: list[str]


@dataclass(frozen=True)
class RunExecutionResult:
    exit_code: int
    stdout: str
    stderr: str = ""


@dataclass(frozen=True)
class LabInspection:
    lab_id: str
    backend: str
    container_name: str
    status: str
    labels: dict[str, str]


class RuntimeAdapter(Protocol):
    def backend_name(self) -> str: ...

    def list_managed_labs(self) -> list[LabInspection]: ...

    def create_lab(self, lab_id: str, spec: RuntimeSpec) -> ProvisionedLab: ...

    def start_lab(self, lab_id: str) -> None: ...

    def stop_lab(self, lab_id: str, timeout: int = 10) -> None: ...

    def destroy_lab(self, lab_id: str, remove_persistent_volume: bool = False) -> None: ...

    def exec_run(self, lab_id: str, command: str) -> RunExecutionResult: ...

    def get_logs(self, lab_id: str, tail: int | str = "all") -> str: ...

    def inspect_lab(self, lab_id: str) -> LabInspection: ...

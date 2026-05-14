from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from labos.core.policy_models import FilesystemMode, PersistenceMode, Profile
from labos.runtimes.base import ManagedMount


@dataclass(frozen=True)
class StoragePolicy:
    filesystem_mode: FilesystemMode
    persistence_mode: PersistenceMode
    disk_mb: int
    retention_days: int
    snapshot_capable: bool = True
    workspace_mount_target: str = "/workspace"

    @classmethod
    def from_profile(cls, profile: Profile) -> StoragePolicy:
        return cls(
            filesystem_mode=profile.filesystem_mode,
            persistence_mode=profile.persistence_mode,
            disk_mb=profile.disk_mb,
            retention_days=profile.retention_days,
        )


@dataclass(frozen=True)
class StorageAllocation:
    lab_id: str
    root_path: Path
    workspace_path: Path
    exports_path: Path
    quarantine_path: Path
    snapshots_path: Path
    persistence_mode: PersistenceMode
    retention_days: int
    workspace_mount_target: str = "/workspace"

    def runtime_mount(self) -> ManagedMount:
        return ManagedMount(source=str(self.workspace_path), target=self.workspace_mount_target)

from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path
from shutil import rmtree

from labos.core.policy_models import PersistenceMode
from labos.storage.models import StorageAllocation, StoragePolicy


class ManagedStorageAllocator:
    def __init__(self, root: Path) -> None:
        self.root = root.resolve()

    def allocate(self, lab_id: str, policy: StoragePolicy) -> StorageAllocation:
        root_path = self.root / "labs" / lab_id
        workspace_path = root_path / "workspace"
        exports_path = root_path / "exports"
        quarantine_path = root_path / "quarantine"
        snapshots_path = root_path / "snapshots"

        for path in (workspace_path, exports_path, quarantine_path, snapshots_path):
            path.mkdir(parents=True, exist_ok=True)

        return StorageAllocation(
            lab_id=lab_id,
            root_path=root_path,
            workspace_path=workspace_path,
            exports_path=exports_path,
            quarantine_path=quarantine_path,
            snapshots_path=snapshots_path,
            persistence_mode=policy.persistence_mode,
            retention_days=policy.retention_days,
            workspace_mount_target=policy.workspace_mount_target,
        )

    def destroy(self, allocation: StorageAllocation) -> None:
        self.assert_managed_path(allocation.root_path)
        if allocation.root_path.exists():
            rmtree(allocation.root_path)

    def retention_deadline(
        self,
        allocation: StorageAllocation,
        *,
        released_at: datetime,
    ) -> datetime:
        if allocation.persistence_mode is PersistenceMode.EPHEMERAL:
            return released_at
        return released_at + timedelta(days=allocation.retention_days)

    def cleanup(
        self,
        allocation: StorageAllocation,
        *,
        released_at: datetime,
        as_of: datetime,
    ) -> bool:
        self.assert_managed_path(allocation.root_path)
        if as_of < self.retention_deadline(allocation, released_at=released_at):
            return False
        if allocation.root_path.exists():
            rmtree(allocation.root_path)
        return True

    def assert_managed_path(self, path: Path) -> None:
        resolved = path.resolve()
        try:
            resolved.relative_to(self.root)
        except ValueError as exc:
            raise ValueError("path must stay under the managed storage root") from exc

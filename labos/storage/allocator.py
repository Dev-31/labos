from __future__ import annotations

from pathlib import Path

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
            workspace_mount_target=policy.workspace_mount_target,
        )

    def assert_managed_path(self, path: Path) -> None:
        resolved = path.resolve()
        try:
            resolved.relative_to(self.root)
        except ValueError as exc:
            raise ValueError("path must stay under the managed storage root") from exc

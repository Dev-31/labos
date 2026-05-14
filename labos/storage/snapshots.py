from __future__ import annotations

import hashlib
import json
import tarfile
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from shutil import rmtree
from typing import Any

from labos.core.policy_models import RuntimeClass
from labos.db.schema import LabRow, LabStorageRow, SnapshotRow


class SnapshotError(Exception):
    """Base class for snapshot workflow failures."""


class UnsupportedSnapshotRuntimeError(SnapshotError):
    pass


class SnapshotMetadataError(SnapshotError):
    pass


@dataclass(frozen=True)
class SnapshotMetadata:
    snapshot_id: str
    lab_id: str
    run_id: str | None
    profile_name: str
    runtime_class: str
    state: str
    backend_ref: str
    manifest_path: str
    sha256: str
    size_bytes: int
    workspace_path: str
    created_at: str
    restored_at: str | None = None
    restored_lab_id: str | None = None

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> SnapshotMetadata:
        return cls(
            snapshot_id=str(payload["snapshot_id"]),
            lab_id=str(payload["lab_id"]),
            run_id=_optional_string(payload.get("run_id")),
            profile_name=str(payload["profile_name"]),
            runtime_class=str(payload["runtime_class"]),
            state=str(payload["state"]),
            backend_ref=str(payload["backend_ref"]),
            manifest_path=str(payload["manifest_path"]),
            sha256=str(payload["sha256"]),
            size_bytes=int(payload["size_bytes"]),
            workspace_path=str(payload["workspace_path"]),
            created_at=str(payload["created_at"]),
            restored_at=_optional_string(payload.get("restored_at")),
            restored_lab_id=_optional_string(payload.get("restored_lab_id")),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "snapshot_id": self.snapshot_id,
            "lab_id": self.lab_id,
            "run_id": self.run_id,
            "profile_name": self.profile_name,
            "runtime_class": self.runtime_class,
            "state": self.state,
            "backend_ref": self.backend_ref,
            "manifest_path": self.manifest_path,
            "sha256": self.sha256,
            "size_bytes": self.size_bytes,
            "workspace_path": self.workspace_path,
            "created_at": self.created_at,
            "restored_at": self.restored_at,
            "restored_lab_id": self.restored_lab_id,
        }


class SnapshotManager:
    def create_snapshot(
        self,
        snapshot_id: str,
        *,
        lab: LabRow,
        storage: LabStorageRow,
        run_id: str | None = None,
    ) -> SnapshotMetadata:
        self._ensure_runtime_supported(lab.runtime_class)

        snapshots_root = Path(storage.snapshots_path)
        snapshots_root.mkdir(parents=True, exist_ok=True)
        archive_path = snapshots_root / f"{snapshot_id}.tar.gz"
        manifest_path = snapshots_root / f"{snapshot_id}.json"
        workspace_path = Path(storage.workspace_path)

        with tarfile.open(archive_path, "w:gz") as archive:
            archive.add(workspace_path, arcname="workspace")

        metadata = SnapshotMetadata(
            snapshot_id=snapshot_id,
            lab_id=lab.id,
            run_id=run_id,
            profile_name=lab.profile_name,
            runtime_class=lab.runtime_class,
            state="created",
            backend_ref=str(archive_path),
            manifest_path=str(manifest_path),
            sha256=self._hash_file(archive_path),
            size_bytes=archive_path.stat().st_size,
            workspace_path=str(workspace_path),
            created_at=_utc_now().isoformat(),
        )
        manifest_path.write_text(json.dumps(metadata.to_dict(), indent=2, sort_keys=True))
        return metadata

    def load_metadata(self, row: SnapshotRow) -> SnapshotMetadata | None:
        manifest_path = self._manifest_path_for(row)
        if manifest_path.exists() is False:
            return None
        try:
            payload = json.loads(manifest_path.read_text())
        except json.JSONDecodeError as exc:
            raise SnapshotMetadataError("snapshot manifest is not valid JSON") from exc
        return SnapshotMetadata.from_dict(payload)

    def restore_snapshot(
        self,
        row: SnapshotRow,
        *,
        target_lab: LabRow,
        target_storage: LabStorageRow,
    ) -> SnapshotMetadata:
        metadata = self.load_metadata(row)
        if metadata is None:
            raise SnapshotMetadataError("snapshot manifest is missing")

        self._ensure_runtime_supported(metadata.runtime_class)
        self._ensure_runtime_supported(target_lab.runtime_class)

        archive_path = Path(metadata.backend_ref)
        if archive_path.exists() is False:
            raise SnapshotMetadataError("snapshot archive is missing")

        workspace_path = Path(target_storage.workspace_path)
        workspace_path.mkdir(parents=True, exist_ok=True)
        self._clear_directory(workspace_path)

        extract_root = workspace_path.parent.resolve()
        with tarfile.open(archive_path, "r:gz") as archive:
            members = archive.getmembers()
            for member in members:
                member_path = extract_root / Path(member.name)
                try:
                    member_path.resolve().relative_to(extract_root)
                except ValueError as exc:
                    raise SnapshotMetadataError("snapshot archive contains an unsafe path") from exc
            archive.extractall(path=extract_root, filter="data")

        extracted_workspace = workspace_path.parent / "workspace"
        if extracted_workspace != workspace_path and extracted_workspace.exists():
            self._clear_directory(workspace_path)
            for child in extracted_workspace.iterdir():
                destination = workspace_path / child.name
                child.replace(destination)
            extracted_workspace.rmdir()

        restored = SnapshotMetadata(
            snapshot_id=metadata.snapshot_id,
            lab_id=metadata.lab_id,
            run_id=metadata.run_id,
            profile_name=metadata.profile_name,
            runtime_class=metadata.runtime_class,
            state="restored",
            backend_ref=metadata.backend_ref,
            manifest_path=metadata.manifest_path,
            sha256=metadata.sha256,
            size_bytes=metadata.size_bytes,
            workspace_path=metadata.workspace_path,
            created_at=metadata.created_at,
            restored_at=_utc_now().isoformat(),
            restored_lab_id=target_lab.id,
        )
        Path(metadata.manifest_path).write_text(
            json.dumps(restored.to_dict(), indent=2, sort_keys=True)
        )
        return restored

    def _manifest_path_for(self, row: SnapshotRow) -> Path:
        backend_ref = Path(row.backend_ref)
        if backend_ref.suffixes[-2:] == [".tar", ".gz"]:
            return backend_ref.with_suffix("").with_suffix(".json")
        return backend_ref.with_suffix(".json")

    def _ensure_runtime_supported(self, runtime_class: str) -> None:
        if runtime_class != RuntimeClass.CONTAINER.value:
            raise UnsupportedSnapshotRuntimeError(
                "only container snapshots are supported in Phase 1"
            )

    def _clear_directory(self, path: Path) -> None:
        for child in path.iterdir():
            if child.is_dir():
                rmtree(child)
            else:
                child.unlink()

    def _hash_file(self, path: Path) -> str:
        hasher = hashlib.sha256()
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                hasher.update(chunk)
        return hasher.hexdigest()


def _optional_string(value: object) -> str | None:
    if value is None:
        return None
    return str(value)


def _utc_now() -> datetime:
    return datetime.now(UTC)

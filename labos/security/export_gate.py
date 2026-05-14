from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from shutil import copy2

from labos.core.enums import ExportState
from labos.core.policy_engine import PolicyEngine
from labos.db.schema import ExportRow, LabRow, LabStorageRow


class ExportGateError(Exception):
    """Base class for export workflow failures."""


class ExportSourceNotFoundError(ExportGateError):
    pass


class ExportPolicyError(ExportGateError):
    pass


class ExportStateError(ExportGateError):
    pass


@dataclass(frozen=True)
class ArtifactHash:
    algorithm: str
    digest: str


@dataclass(frozen=True)
class ExportProvenance:
    lab_id: str
    run_id: str | None
    source_path: str
    quarantine_path: str
    released_path: str | None
    size_bytes: int
    artifact_hash: ArtifactHash


@dataclass(frozen=True)
class ExportStageResult:
    provenance: ExportProvenance
    approval_required: bool
    state: ExportState
    denial_reason: str | None = None


class ExportGate:
    GUEST_EXPORT_ROOT = PurePosixPath("/lab/exports")
    RELEASED_DIRNAME = "released"

    def __init__(self, policy_engine: PolicyEngine | None = None) -> None:
        self.policy_engine = policy_engine or PolicyEngine()

    def stage_export(
        self,
        export_id: str,
        *,
        lab: LabRow,
        storage: LabStorageRow,
        source_path: str,
        run_id: str | None = None,
    ) -> ExportStageResult:
        decision = self.policy_engine.validate_export(lab.profile_name, source_path)
        if decision.allowed is False:
            raise ExportPolicyError(decision.reason)

        source = self._resolve_managed_source(storage, source_path)
        if source.exists() is False or source.is_file() is False:
            raise ExportSourceNotFoundError(source_path)

        quarantine_dir = Path(storage.quarantine_path) / export_id
        quarantine_dir.mkdir(parents=True, exist_ok=True)
        quarantine_path = quarantine_dir / source.name
        copy2(source, quarantine_path)

        artifact_hash = ArtifactHash(algorithm="sha256", digest=self._hash_file(quarantine_path))
        provenance = ExportProvenance(
            lab_id=lab.id,
            run_id=run_id,
            source_path=source_path,
            quarantine_path=str(quarantine_path),
            released_path=None,
            size_bytes=quarantine_path.stat().st_size,
            artifact_hash=artifact_hash,
        )
        return ExportStageResult(
            provenance=provenance,
            approval_required=decision.approval_required,
            state=ExportState.QUARANTINED,
        )

    def release_export(self, export_row: ExportRow, *, storage: LabStorageRow) -> ExportStageResult:
        state = ExportState(export_row.state)
        if state is ExportState.REJECTED:
            raise ExportStateError("export_already_rejected")
        if state is ExportState.RELEASED:
            raise ExportStateError("export_already_released")
        if export_row.approval_required:
            raise ExportPolicyError("export_approval_required")

        quarantine_path = Path(export_row.quarantine_path)
        if quarantine_path.exists() is False or quarantine_path.is_file() is False:
            raise ExportSourceNotFoundError(export_row.source_path)

        released_dir = Path(storage.root_path) / self.RELEASED_DIRNAME / export_row.id
        released_dir.mkdir(parents=True, exist_ok=True)
        released_path = released_dir / quarantine_path.name
        copy2(quarantine_path, released_path)

        provenance = ExportProvenance(
            lab_id=export_row.lab_id,
            run_id=export_row.run_id,
            source_path=export_row.source_path,
            quarantine_path=export_row.quarantine_path,
            released_path=str(released_path),
            size_bytes=export_row.size_bytes,
            artifact_hash=ArtifactHash(algorithm="sha256", digest=export_row.sha256),
        )
        return ExportStageResult(
            provenance=provenance,
            approval_required=export_row.approval_required,
            state=ExportState.RELEASED,
        )

    def deny_export(self, export_row: ExportRow, *, reason: str) -> ExportStageResult:
        state = ExportState(export_row.state)
        if state is ExportState.RELEASED:
            raise ExportStateError("export_already_released")
        if state is ExportState.REJECTED:
            raise ExportStateError("export_already_rejected")
        if reason.strip() == "":
            raise ExportStateError("export_denial_reason_required")

        provenance = ExportProvenance(
            lab_id=export_row.lab_id,
            run_id=export_row.run_id,
            source_path=export_row.source_path,
            quarantine_path=export_row.quarantine_path,
            released_path=None,
            size_bytes=export_row.size_bytes,
            artifact_hash=ArtifactHash(algorithm="sha256", digest=export_row.sha256),
        )
        return ExportStageResult(
            provenance=provenance,
            approval_required=export_row.approval_required,
            state=ExportState.REJECTED,
            denial_reason=reason,
        )

    def _resolve_managed_source(self, storage: LabStorageRow, source_path: str) -> Path:
        guest_path = PurePosixPath(source_path)
        try:
            relative_guest_path = guest_path.relative_to(self.GUEST_EXPORT_ROOT)
        except ValueError as exc:
            raise ExportPolicyError("exports must use a managed guest export path") from exc

        exports_root = Path(storage.exports_path).resolve()
        source = (exports_root / Path(*relative_guest_path.parts)).resolve()
        try:
            source.relative_to(exports_root)
        except ValueError as exc:
            raise ExportPolicyError("export path escapes managed exports root") from exc
        return source

    def _hash_file(self, path: Path) -> str:
        digest = hashlib.sha256()
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()

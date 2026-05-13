from datetime import UTC, datetime

import pytest

from labos.core.entities import LabRecord, RunRecord
from labos.core.enums import (
    ApprovalState,
    ExportState,
    LabState,
    RunState,
    SnapshotState,
)
from labos.core.state_machine import (
    can_transition_approval,
    can_transition_export,
    can_transition_lab,
    can_transition_run,
    can_transition_snapshot,
)

NOW = datetime(2026, 5, 13, tzinfo=UTC)


def test_lab_valid_transition_requested_to_approved() -> None:
    assert can_transition_lab(LabState.REQUESTED, LabState.APPROVED) is True


def test_lab_invalid_transition_destroyed_to_running() -> None:
    assert can_transition_lab(LabState.DESTROYED, LabState.RUNNING) is False


def test_run_valid_transition_starting_to_running() -> None:
    assert can_transition_run(RunState.STARTING, RunState.RUNNING) is True


def test_approval_transitions_are_explicit() -> None:
    assert can_transition_approval(ApprovalState.REQUESTED, ApprovalState.APPROVED) is True
    assert can_transition_approval(ApprovalState.APPROVED, ApprovalState.REJECTED) is False


def test_export_transitions_require_quarantine_before_release() -> None:
    assert can_transition_export(ExportState.REQUESTED, ExportState.RELEASED) is False
    assert can_transition_export(ExportState.QUARANTINED, ExportState.APPROVED) is True


def test_snapshot_transitions_are_one_way() -> None:
    assert can_transition_snapshot(SnapshotState.CREATED, SnapshotState.FAILED) is False
    assert can_transition_snapshot(SnapshotState.PENDING, SnapshotState.CREATED) is True


def test_lab_record_rejects_profile_name_mutation() -> None:
    original = LabRecord(
        id="lab-123",
        profile_name="safe-dev",
        state=LabState.REQUESTED,
        created_at=NOW,
        updated_at=NOW,
    )
    candidate = original.model_copy(update={"profile_name": "red-zone"})

    with pytest.raises(ValueError, match="immutable fields changed: profile_name"):
        candidate.validate_update_from(original)


def test_run_record_allows_state_transition_with_immutable_identity() -> None:
    original = RunRecord(
        id="run-123",
        lab_id="lab-123",
        state=RunState.STARTING,
        created_at=NOW,
        updated_at=NOW,
    )
    candidate = original.model_copy(
        update={"state": RunState.RUNNING, "updated_at": datetime(2026, 5, 14, tzinfo=UTC)}
    )

    candidate.validate_update_from(original)


def test_run_record_rejects_lab_id_mutation() -> None:
    original = RunRecord(
        id="run-123",
        lab_id="lab-123",
        state=RunState.RUNNING,
        created_at=NOW,
        updated_at=NOW,
    )
    candidate = original.model_copy(update={"lab_id": "lab-999"})

    with pytest.raises(ValueError, match="immutable fields changed: lab_id"):
        candidate.validate_update_from(original)

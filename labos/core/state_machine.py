from labos.core.enums import ApprovalState, ExportState, LabState, RunState, SnapshotState

LAB_TRANSITIONS: dict[LabState, set[LabState]] = {
    LabState.REQUESTED: {LabState.PENDING_APPROVAL, LabState.APPROVED, LabState.FAILED},
    LabState.PENDING_APPROVAL: {LabState.APPROVED, LabState.FAILED},
    LabState.APPROVED: {LabState.PROVISIONING, LabState.FAILED, LabState.DESTROYING},
    LabState.PROVISIONING: {LabState.RUNNING, LabState.FAILED, LabState.DESTROYING},
    LabState.RUNNING: {LabState.STOPPED, LabState.FAILED, LabState.DESTROYING},
    LabState.STOPPED: {LabState.RUNNING, LabState.DESTROYING, LabState.ARCHIVED},
    LabState.FAILED: {LabState.DESTROYING, LabState.ARCHIVED},
    LabState.DESTROYING: {LabState.DESTROYED},
    LabState.DESTROYED: set(),
    LabState.ARCHIVED: set(),
}

RUN_TRANSITIONS: dict[RunState, set[RunState]] = {
    RunState.QUEUED: {RunState.STARTING, RunState.CANCELLED},
    RunState.STARTING: {RunState.RUNNING, RunState.FAILED, RunState.CANCELLED},
    RunState.RUNNING: {
        RunState.COMPLETED,
        RunState.FAILED,
        RunState.CANCELLED,
        RunState.TIMED_OUT,
    },
    RunState.COMPLETED: set(),
    RunState.FAILED: set(),
    RunState.CANCELLED: set(),
    RunState.TIMED_OUT: set(),
}

APPROVAL_TRANSITIONS: dict[ApprovalState, set[ApprovalState]] = {
    ApprovalState.REQUESTED: {
        ApprovalState.APPROVED,
        ApprovalState.REJECTED,
        ApprovalState.EXPIRED,
    },
    ApprovalState.APPROVED: set(),
    ApprovalState.REJECTED: set(),
    ApprovalState.EXPIRED: set(),
}

EXPORT_TRANSITIONS: dict[ExportState, set[ExportState]] = {
    ExportState.REQUESTED: {ExportState.QUARANTINED, ExportState.REJECTED},
    ExportState.QUARANTINED: {ExportState.APPROVED, ExportState.REJECTED},
    ExportState.APPROVED: {ExportState.RELEASED},
    ExportState.RELEASED: set(),
    ExportState.REJECTED: set(),
}

SNAPSHOT_TRANSITIONS: dict[SnapshotState, set[SnapshotState]] = {
    SnapshotState.PENDING: {SnapshotState.CREATED, SnapshotState.FAILED},
    SnapshotState.CREATED: {SnapshotState.RESTORED},
    SnapshotState.FAILED: set(),
    SnapshotState.RESTORED: set(),
}
def can_transition_lab(current: LabState, target: LabState) -> bool:
    return target in LAB_TRANSITIONS[current]


def can_transition_run(current: RunState, target: RunState) -> bool:
    return target in RUN_TRANSITIONS[current]


def can_transition_approval(current: ApprovalState, target: ApprovalState) -> bool:
    return target in APPROVAL_TRANSITIONS[current]


def can_transition_export(current: ExportState, target: ExportState) -> bool:
    return target in EXPORT_TRANSITIONS[current]


def can_transition_snapshot(current: SnapshotState, target: SnapshotState) -> bool:
    return target in SNAPSHOT_TRANSITIONS[current]

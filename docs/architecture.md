# LabOS Architecture

LabOS is a policy-first control plane for isolated labs.

## Phase 1 scope
- API + CLI control plane
- Docker-backed standard labs
- microVM adapter boundary for later high-risk runtimes
- policy profiles
- approvals
- audit events
- snapshots
- export gate

## Core domain vocabulary
- `Profile` defines the allowed runtime, network, filesystem, persistence, approval, and export posture.
- `Lab` is the governed execution environment created from a profile.
- `Run` is a supervised execution inside a lab.
- `ApprovalRequest`, `Snapshot`, `ExportRequest`, `AuditEvent`, `SecretLease`, and `SchedulerJob` are first-class records, not ad hoc side channels.

## Policy evaluation
- Profiles are validated against explicit policy enums instead of free-form strings.
- Risk classes are explicit: `low`, `medium`, `high`, `critical`.
- Profile evaluation returns an execution plan with runtime class, network mode, filesystem mode, persistence mode, resource limits, audit level, approval requirements, and the injected secret set.
- Host mounts are forbidden unless a profile explicitly allows them.
- The default secret set is empty.
- Network mode is fixed by profile and cannot be widened through request overrides.
- High-risk and critical exports are deny-until-reviewed: managed export path required plus quarantine/approval before release.

## Lifecycle states
- lab states: `requested`, `pending_approval`, `approved`, `provisioning`, `running`, `stopped`, `failed`, `destroying`, `destroyed`, `archived`
- run states: `queued`, `starting`, `running`, `completed`, `failed`, `cancelled`, `timed_out`
- approval states: `requested`, `approved`, `rejected`, `expired`
- export states: `requested`, `quarantined`, `approved`, `released`, `rejected`
- snapshot states: `pending`, `created`, `failed`, `restored`

These states are explicit so policy, storage, runtime, and API layers can share the same lifecycle contract.

## Durable metadata
- SQLAlchemy is the Phase 1 metadata layer.
- Core durable tables are `labs`, `runs`, `approvals`, `exports`, `snapshots`, and `events`.
- Alembic manages schema evolution so the control plane can move without hand-edited database drift.

## Runtime adapter boundary
- `RuntimeAdapter` defines the public execution-plane contract: create, start, stop, destroy, exec, logs, and inspect.
- `DockerRuntime` is the Phase 1 backend and uses managed naming conventions for containers (`labos-<lab_id>`) and networks (`labos-net-<lab_id>`).
- Secret injection is explicit and gated through approved, non-expired `SecretLease` records only.
- CPU and memory limits are applied at container creation time.
- Docker network mode is conservative: `deny` maps to `network_disabled`, while non-deny modes use LabOS-managed networks. This is not yet a full egress allowlist engine.
- Persistent-volume lifecycle policy remains a separate storage-layer concern. The runtime attaches managed volumes but does not claim snapshot or retention semantics that do not exist yet.

## Product boundaries
- public core platform only
- no private datasets, profiles, or strategy packs in this repo
- no web dashboard in Phase 1
- no fake microVM guarantees before a real backend exists

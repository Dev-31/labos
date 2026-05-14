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
- Core durable tables are `labs`, `lab_storage`, `runs`, `approvals`, `exports`, `snapshots`, `secret_leases`, and `events`.
- Alembic migrations are committed under `alembic/versions/` and remain the supported schema upgrade path for local and CI environments.

## Managed lab filesystem
- LabOS reserves a managed filesystem root per lab under `LABOS_MANAGED_STORAGE_ROOT`.
- Current path convention is `labs/<lab-id>/` with dedicated `workspace`, `exports`, `quarantine`, and `snapshots` subdirectories.
- Export release copies are published under a managed `released/<export-id>/` subtree inside the same lab root; release is a control-plane action, not a direct host write from the lab.
- Storage allocation metadata is recorded separately from lab lifecycle metadata so later runtime, snapshot, and retention phases can evolve without overloading the `labs` table.
- The control plane rejects unmanaged host paths when validating managed storage sources.

## Phase 1 export gate model
- Export requests are staged from the managed guest path `/lab/exports/...` into a per-export quarantine directory.
- Quarantine records include lab identity, optional run identity, hash, size, staged path, and final state.
- Release copies from quarantine into a managed released directory only after policy review succeeds.
- High-risk exports are honestly blocked with `export_approval_required` until the later approval workflow lands; LabOS does not pretend that approval automation already exists.

## Phase 1 snapshot model
- Phase 1 snapshots are honest container-storage snapshots: a tarred copy of the managed workspace plus a JSON manifest.
- Snapshot manifests record provenance for `lab_id`, optional `run_id`, `profile_name`, `runtime_class`, managed workspace path, creation timestamp, archive hash, and archive size.
- Restore currently rehydrates managed workspace contents for container labs only.
- MicroVM/runtime-level memory snapshots are not implemented yet and LabOS returns an explicit unsupported-runtime error instead of pretending to offer VM-grade time travel.

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

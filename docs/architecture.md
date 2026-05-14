# LabOS Architecture

LabOS is a policy-first control plane for isolated labs. The public core is responsible for governance, durability, and operator interfaces first; full runtime orchestration follows only where the implementation is real.

## Phase 1 scope
- API + CLI control plane
- policy profiles as the primary operator abstraction
- durable metadata for labs, runs, approvals, exports, snapshots, events, secret leases, and scheduler jobs
- Docker-backed runtime adapter implementation
- microVM-ready runtime contract for later high-risk backend work
- managed storage, snapshot, export, approval, audit, scheduler, and reconciliation layers

## Control-plane map
```text
Operator plane
  ├── FastAPI app
  └── Typer CLI

Governance plane
  ├── profile registry
  ├── policy evaluation
  ├── lifecycle/state machine
  ├── approval workflow
  └── audit/event recording

Persistence plane
  ├── SQLAlchemy schema
  ├── Alembic migrations
  └── settings/session wiring

Execution boundary
  ├── runtime adapter interface
  ├── Docker runtime implementation
  └── future microVM backend slot

Recovery workers
  ├── scheduler dispatch service
  └── reconciliation service
```

## Core domain vocabulary
- `Profile` defines runtime class, network mode, filesystem mode, persistence mode, resource limits, secret allowlist, export posture, approval posture, and audit level.
- `Lab` is the governed execution environment requested from a profile.
- `Run` is a governed execution request associated with a lab.
- `ApprovalRequest`, `Snapshot`, `ExportRequest`, `AuditEvent`, `SecretLease`, and `SchedulerJob` are durable first-class records, not side channels.

## Policy evaluation
- Profiles are validated against explicit enums.
- Risk classes are explicit: `low`, `medium`, `high`, `critical`.
- Evaluation returns an execution plan with runtime, storage, network, export, approval, secret, and audit posture.
- Host mounts are forbidden unless explicitly allowed, with hard blocks on home-directory mounts and Docker socket passthrough.
- Default secret injection is empty.
- Network mode is profile-owned and cannot be widened via request metadata.
- High-risk exports are deny-until-reviewed.

## Lifecycle states
- lab states: `requested`, `pending_approval`, `approved`, `provisioning`, `running`, `stopped`, `failed`, `destroying`, `destroyed`, `archived`
- run states: `queued`, `starting`, `running`, `completed`, `failed`, `cancelled`, `timed_out`
- approval states: `requested`, `approved`, `rejected`, `expired`
- export states: `requested`, `quarantined`, `approved`, `released`, `rejected`
- snapshot states: `pending`, `created`, `failed`, `restored`

These explicit state machines let API, worker, storage, runtime, and audit layers share one lifecycle contract.

## Durable metadata
- SQLAlchemy schema lives in `labos/db/schema.py`.
- Alembic migrations under `alembic/versions/` are the supported schema upgrade path.
- Current durable tables cover labs, lab storage allocations, runs, approvals, exports, snapshots, secret leases, scheduler jobs, and events.
- Reconciliation reads durable state as the source of truth and records drift as audit events.

## Storage model
- Managed storage roots live under `LABOS_MANAGED_STORAGE_ROOT`.
- Each lab gets a dedicated root with `workspace/`, `exports/`, `quarantine/`, and `snapshots/` subdirectories.
- Storage allocation metadata is kept separately from lab lifecycle metadata so retention and runtime evolution can change without overloading the `labs` table.
- Export releases are copied into a managed `released/<export-id>/` subtree instead of granting raw host write access.
- Snapshot archives represent managed workspace contents only.
- The control plane rejects unmanaged host paths for export and snapshot operations.

## Runtime support matrix
| Surface | Status | Honest boundary |
| --- | --- | --- |
| Runtime adapter contract | implemented | Defines create/start/stop/destroy/exec/logs/inspect/inventory methods. |
| Docker runtime | implemented and tested | Supports container create/start/stop/destroy flows, conservative networking, and managed secret injection at the adapter level. |
| Public API lab provisioning | not wired yet | `POST /labs` records metadata and storage only; it does not launch a container. |
| Public API run execution | not wired yet | `POST /runs` records run intent and timeout metadata only. |
| MicroVM backend | contract only | No Firecracker-class backend shipped in the public core yet. |

## Export workflow
1. The control plane validates that a requested artifact path resolves inside the managed guest export tree.
2. The export gate copies the file into quarantine and records hash, size, provenance, and state.
3. Approval-required exports stay blocked until an explicit approval decision changes state.
4. Release copies the quarantined artifact into managed release storage.

## Approval workflow
1. Policy or action-specific rules create an approval row.
2. Operator surfaces list the approval with expiry metadata.
3. An explicit approve/deny action mutates the associated lab or export record.
4. Reconciliation expires stale approvals and emits `approval.expired` audit events.

## Reliability and reconciliation
- Broken lab metadata/storage pairings are marked `failed` with audit evidence.
- Destroying labs can be retried and eventually hard-failed with explicit retry/failure events.
- Expired secret leases are revoked automatically.
- Overdue queued/starting/running runs are marked `timed_out` by reconciliation.
- Runtime inventory is inspected for orphaned or zombie LabOS-managed artifacts.
- These are control-plane recovery features, not a claim of perfect runtime self-healing.

## Product boundaries
- public core platform only
- no private datasets, strategies, credentials brokers, or workload packs in this repo
- no web dashboard in Phase 1
- no fake microVM guarantees before a real backend exists
- no claim that snapshot restore provides VM-memory or time-travel semantics

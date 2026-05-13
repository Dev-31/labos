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

## Product boundaries
- public core platform only
- no private datasets, profiles, or strategy packs in this repo
- no web dashboard in Phase 1
- no fake microVM guarantees before a real backend exists

# Changelog

All notable changes to LabOS will be documented in this file.

## v0.1.0 (unreleased)

### Added
- Public core control plane built around FastAPI, Typer, SQLAlchemy, Alembic, and policy-first domain models.
- Named built-in policy profiles (`safe-dev`, `model-local`, `research-persistent`, `red-zone`) with explicit risk, network, persistence, approval, and export posture.
- Durable metadata for labs, runs, approvals, snapshots, exports, audit events, secret leases, and scheduler jobs.
- API and CLI surfaces for profile inspection, governed lab/run metadata creation, approval handling, snapshot/export flows, scheduler hooks, and audit/event inspection.
- Managed storage allocation plus container-lab workspace archive/restore support for snapshot metadata workflows.
- Export quarantine/release flow with provenance hashing, path confinement, and approval-aware release controls.
- Reconciliation coverage for stale approvals, expired secret leases, timed-out runs, zombie runtime detection, and destroy retry accounting.
- Contributor-facing docs covering architecture, threat model, policy model, profiles, API, CLI, release readiness, and the public-core/private-workload split.

### Changed
- Threat-model verification now has explicit regression coverage so unsafe defaults and unsupported guarantees are easier to catch before release.
- Contributor and operator docs now track the actual public-core behavior instead of implying hidden runtime guarantees.
- Release-prep tooling now includes `labos runtime probe-docker` and matching `make probe-docker` / `make smoke-docker` entrypoints so Docker readiness failures surface before the optional runtime smoke is attempted.
- Release-prep tooling now also includes `labos release readiness`, which reports the current Git/Docker blockers before attempting the remaining `v0.1.0` gate checks.
- Release-prep tooling now also includes `labos release evidence`, which emits a machine-readable evidence template with the current commit SHA, verification commands, docs surface, and current Docker blocker detail.
- Release-prep tooling now also includes `labos release smoke-cli` and `make smoke-cli`, which capture one JSON proof for the representative CLI help/profile/create/list/get/destroy flow against a live API by invoking the real CLI commands instead of shortcutting through internal helpers.
- Release smoke commands now perform best-effort cleanup of their temporary lab records if a later validation step fails after creation, reducing false leftover metadata during release rehearsals.

### Honesty boundary
- LabOS `v0.1.0` is the **public core** release, not a promise of full runtime orchestration.
- The repo includes a tested Docker runtime adapter contract and a microVM-ready interface boundary, but the public API/CLI do **not** yet provision real labs or execute runs inside Docker or Firecracker-class backends.
- Snapshot support in the public core describes managed workspace archive/restore metadata only; it does not claim VM-memory or hypervisor-grade snapshot semantics.

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

## Product boundaries
- public core platform only
- no private datasets, profiles, or strategy packs in this repo
- no web dashboard in Phase 1
- no fake microVM guarantees before a real backend exists

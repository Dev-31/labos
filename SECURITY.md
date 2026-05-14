# Security Policy

## Scope

LabOS is a policy-first containment control plane. The public core covers:
- FastAPI control-plane APIs
- Typer CLI
- policy evaluation and approval flow
- managed storage, snapshots, and export quarantine
- Docker-backed runtime adapter contract
- audit events and reconciliation workers

It does **not** currently promise:
- production Firecracker or other microVM isolation
- kernel- or hypervisor-level sandbox guarantees in the public core
- unrestricted network policy enforcement beyond the documented Phase 1 controls
- private workload packs, datasets, or trading logic

## Supported versions

Until `v0.1.0` is tagged, only the `main` branch is supported for security fixes.

## Reporting a vulnerability

Please report suspected vulnerabilities privately. Include:
- affected commit SHA or branch
- reproduction steps
- impact assessment
- any logs, traces, or proof-of-concept details needed to validate the issue

Current disclosure contact: **open a private GitHub security advisory** for `Dev-31/labos` if available. If private advisories are unavailable in your environment, use a private maintainer contact channel instead of a public issue.

Do **not** post weaponized exploit details in public issues before maintainers have a chance to assess and patch.

## Disclosure process

Maintainers should:
1. acknowledge receipt
2. reproduce and scope the issue
3. ship a fix and regression test when applicable
4. publish release notes or an advisory once users have a remediation path

## Phase 1 security stance

LabOS currently enforces these public-core rules:
- no host environment inheritance by default
- no home-directory host mounts
- no Docker socket passthrough
- network access remains profile-controlled, with deny-by-default behavior for `red-zone`
- secret injection is named, scoped, and empty by default
- exports must originate from managed guest export paths and enter quarantine before release
- dangerous actions emit audit events with actor metadata when the API captures an actor

## Verification coverage

The repo includes automated coverage for the active threat-model controls, including:
- blocked host-mount paths and Docker socket passthrough
- empty default secret injection
- deny-by-default `red-zone` networking policy
- export path escape rejection through the public API
- actor/audit trail capture for approval decisions

## Security testing notes

The Docker runtime adapter is real for Phase 1 container labs, but the public core remains honest about current limits:
- microVM support is an adapter boundary, not a shipped backend guarantee
- snapshot/export semantics are metadata- and file-workflow based, not VM-grade rollback claims
- reconciliation improves cleanup and failure recovery, but it is not a substitute for host hardening

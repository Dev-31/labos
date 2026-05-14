# Threat Model

## Primary risks
- host contamination from untrusted code
- accidental secret leakage
- unrestricted egress
- unsafe artifact export
- long-lived zombie labs

## Phase 1 stance
- no host environment inheritance by default
- no direct host writes
- network access must be explicit in policy
- exports enter quarantine before release
- scheduler and agents must use control-plane APIs

## Current enforcement points
- host mounts are rejected unless a profile explicitly opts in, and home-directory mounts plus Docker socket passthrough remain forbidden even for opt-in profiles
- secret injection defaults to an empty list and rejects unknown secret names
- request-time network widening is rejected; the profile remains authoritative
- critical microVM-ready profiles require deny-by-default networking and approval-gated exports
- export requests must resolve inside managed guest export paths before quarantine/release proceeds
- the reconciliation worker flags active runtime artifacts that linger after a lab reaches destroyed/failed/pre-runtime states

## Verification coverage
- `tests/security/test_threat_model.py` covers blocked host mounts, Docker socket rejection, empty default secret injection, export-path escape rejection, and actor/audit capture for high-risk approvals
- `tests/runtimes/test_docker_runtime.py` verifies deny-mode labs are created with Docker networking disabled

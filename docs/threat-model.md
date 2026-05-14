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
- host mounts are rejected unless a profile explicitly opts in
- secret injection defaults to an empty list and rejects unknown secret names
- request-time network widening is rejected; the profile remains authoritative
- critical microVM-ready profiles require deny-by-default networking and approval-gated exports
- the reconciliation worker flags active runtime artifacts that linger after a lab reaches destroyed/failed/pre-runtime states

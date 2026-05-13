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

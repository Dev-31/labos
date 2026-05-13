# LabOS Policy Model

LabOS is policy-first by design. Operators request a named profile; the control plane turns that profile into an enforceable execution plan.

## Phase 1 guarantees

- Profiles, not ad hoc runtime flags, determine runtime, network, filesystem, persistence, export mode, and resource limits.
- Host environment inheritance is forbidden by default.
- Host mounts are forbidden unless a profile explicitly allows them.
- Secret injection defaults to an empty set and only permits names allowlisted by the profile.
- Exports must come from managed LabOS paths.
- High-risk and critical profiles require export quarantine and approval before release.
- Non-human requesters for high-risk profiles require approval even when the profile does not auto-approve normal starts.

## Built-in profiles

### `safe-dev`
- Runtime: container
- Risk: low
- Network: restricted
- Persistence: ephemeral
- Exports: request-based from managed paths

### `model-local`
- Runtime: container
- Risk: medium
- Network: restricted
- Persistence: persistent
- Exports: approval on export

### `research-persistent`
- Runtime: container
- Risk: high
- Network: restricted
- Persistence: persistent
- Exports: approval + quarantine
- Starts: scheduler/agent requests require approval

### `red-zone`
- Runtime: microVM contract
- Risk: critical
- Network: deny
- Filesystem: read-only root + managed writable areas
- Persistence: ephemeral
- Exports: approval + quarantine
- Starts: always require approval

## Current limits

Phase 1 exposes a microVM-ready contract in policy, but does not claim full production Firecracker orchestration yet. Snapshot semantics remain honest: managed storage and metadata first, not fake VM time travel.
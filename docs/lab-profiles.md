# LabOS Lab Profiles

Profiles are the primary operator abstraction in LabOS. Operators request a named profile and the control plane derives runtime, network, storage, approval, export, and audit posture from that profile.

This document covers the built-in public-core profiles. YAML examples live under `examples/profiles/`.

## Profile matrix
| Profile | Runtime class | Risk | Filesystem | Persistence | Network | Export mode | Start approval | Export approval |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `safe-dev` | container | low | managed | ephemeral | restricted | request | no | no |
| `model-local` | container | medium | managed | persistent | restricted | request | no | yes |
| `research-persistent` | container | high | managed | persistent | restricted | approval | no for human direct requests; scheduler/agent requests may require approval | yes |
| `red-zone` | microVM contract | critical | read-only root + managed writable areas | ephemeral | deny | approval | yes | yes |

## `safe-dev`
Best for low-risk development and quick experiments where the operator wants a short-lived managed workspace.

- Runtime class: container
- Risk class: low
- CPU / memory / disk: 2 CPU, 2048 MB RAM, 8192 MB disk
- Persistence: ephemeral
- Network: restricted
- Audit level: basic
- Secret allowlist: empty by default

## `model-local`
Best for medium-risk local-model and heavier tool workflows that need longer-lived managed storage.

- Runtime class: container
- Risk class: medium
- CPU / memory / disk: 4 CPU, 8192 MB RAM, 51200 MB disk
- Persistence: persistent
- Network: restricted
- Audit level: detailed
- Secret allowlist: empty by default
- Exports require approval before release

## `research-persistent`
Best for higher-risk research that still fits the container path but needs stronger review and retention.

- Runtime class: container
- Risk class: high
- CPU / memory / disk: 8 CPU, 16384 MB RAM, 102400 MB disk
- Persistence: persistent
- Network: restricted
- Audit level: forensic
- Secret allowlist: empty by default
- Exports are approval-gated and quarantine-based
- Non-human creation patterns are stricter than `safe-dev`

## `red-zone`
Reserved for critical-risk workflows that need a deny-by-default network posture and a future microVM backend.

- Runtime class: microVM contract
- Risk class: critical
- CPU / memory / disk: 4 CPU, 4096 MB RAM, 16384 MB disk
- Filesystem: read-only root with managed writable areas
- Persistence: ephemeral
- Network: deny
- Audit level: forensic
- Start approval: always required
- Export approval: always required

Honesty boundary: the public core exposes the policy contract for this profile today, but it does **not** yet ship a real Firecracker-class runtime backend.

## Approval workflow
Profile approval posture affects both lab creation and export release.

1. The operator chooses a profile.
2. Policy evaluation decides whether the requested action can auto-approve or must create an approval record.
3. Approval-gated actions remain pending until an explicit operator decision lands.
4. Reconciliation expires stale approvals and records `approval.expired` audit events.

In practice:
- `safe-dev` auto-approves normal lab requests and exports.
- `model-local` can start normally but export release requires approval.
- `research-persistent` is stricter on export posture and risky non-human usage.
- `red-zone` requires approval for both lab creation and export release.

## Export workflow
All profiles share the same public-core export path shape:

1. Artifacts are written to the managed guest export path (`/lab/exports/...`).
2. `POST /exports` validates the path and stages the artifact into quarantine.
3. LabOS records hash, size, provenance, and approval requirement metadata.
4. Approval-gated profiles require an explicit approval decision before release.
5. Release copies the artifact into managed release storage.

## Storage model
Profiles define persistence expectations, but storage still stays inside LabOS-managed paths.

- `ephemeral` profiles still receive managed storage roots; the distinction is lifecycle intent, not arbitrary host writes.
- `persistent` profiles retain metadata and managed storage posture for longer-lived workflows.
- No profile grants direct host-home mounts or Docker socket passthrough.
- Allowed secret names start empty for every built-in profile.

## Related docs
- `docs/policies.md`
- `docs/api.md`
- `docs/cli.md`
- `docs/architecture.md`

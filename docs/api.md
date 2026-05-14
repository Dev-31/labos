# LabOS API Guide

Phase 1 currently exposes the first stable control-plane surface for health, profile discovery, managed storage-backed lab metadata, snapshot capture/restore, and export quarantine workflows.

## Current endpoints

### `GET /health`
Returns basic service status.

### `GET /profiles`
Lists the built-in policy profiles shipped with the public core.

### `GET /profiles/{profile_name}`
Returns a single built-in profile.

If the profile does not exist, LabOS returns:

```json
{"detail": "resource_not_found", "resource": "profile"}
```

### `POST /labs`
Creates a lab request record from a named profile.

Example request:

```json
{
  "profile_name": "safe-dev",
  "requester_type": "human"
}
```

Example response:

```json
{
  "id": "<uuid>",
  "profile_name": "safe-dev",
  "state": "approved",
  "runtime_class": "container",
  "storage": {
    "persistence_mode": "ephemeral",
    "root_path": "./.labos/storage/labs/<uuid>",
    "workspace_path": "./.labos/storage/labs/<uuid>/workspace",
    "exports_path": "./.labos/storage/labs/<uuid>/exports",
    "quarantine_path": "./.labos/storage/labs/<uuid>/quarantine",
    "snapshots_path": "./.labos/storage/labs/<uuid>/snapshots",
    "workspace_mount_target": "/workspace"
  },
  "created_at": "2026-05-14T00:00:00Z",
  "updated_at": "2026-05-14T00:00:00Z"
}
```

Current API behavior is honest:
- this records governed lab requests in metadata
- this allocates a managed lab filesystem layout and stores the allocation in metadata
- it does **not** provision a container or microVM yet
- approval-requiring profiles remain in `pending_approval`

### `GET /labs`
Lists recorded lab requests.

### `GET /labs/{lab_id}`
Fetches one recorded lab request.

If the lab does not exist, LabOS returns:

```json
{"detail": "resource_not_found", "resource": "lab"}
```

### `POST /runs`
Creates a queued run record for an existing lab request.

Example request:

```json
{
  "lab_id": "<lab-id>",
  "command": "python -m pytest"
}
```

Example response:

```json
{
  "id": "<uuid>",
  "lab_id": "<lab-id>",
  "state": "queued",
  "command": "python -m pytest",
  "created_at": "2026-05-14T00:00:00Z",
  "updated_at": "2026-05-14T00:00:00Z"
}
```

Current API behavior is honest:
- this records governed run intent in metadata
- it does **not** execute inside Docker or a microVM yet
- the runtime adapter work remains a later roadmap phase

### `GET /runs`
Lists recorded run requests.

### `GET /runs/{run_id}`
Fetches one recorded run request.

If the run does not exist, LabOS returns:

```json
{"detail": "resource_not_found", "resource": "run"}
```

### `GET /approvals`
Lists recorded approval metadata rows.

Each row includes resource-scoped approval details such as:
- `resource_type`
- `resource_id`
- `action`
- `state`
- `reason`
- `requested_by`
- `decided_by`
- `expires_at`

### `POST /approvals/{approval_id}/approve`
Approves a pending approval request and applies the governed side effect.

Example request:

```json
{
  "actor": "operator",
  "comment": "manual review accepted"
}
```

### `POST /approvals/{approval_id}/deny`
Rejects a pending approval request and records the denial metadata.

Example request:

```json
{
  "actor": "operator",
  "comment": "artifact denied by manual review"
}
```

### `GET /snapshots`
Lists recorded snapshot metadata rows.

### `POST /snapshots`
Creates a managed workspace snapshot for container labs.

Current API behavior is honest:
- snapshots currently archive the managed workspace directory only
- restore rehydrates managed workspace contents for container labs only
- microVM/runtime-memory snapshot semantics are not implemented yet

### `POST /snapshots/{snapshot_id}/restore`
Restores a managed workspace snapshot into another container-backed lab.

### `POST /exports`
Stages an artifact from the managed guest export path (`/lab/exports/...`) into quarantine, hashes it, and records provenance.

Example request:

```json
{
  "lab_id": "<lab-id>",
  "run_id": "<run-id>",
  "source_path": "/lab/exports/report.txt"
}
```

Example response:

```json
{
  "id": "<uuid>",
  "lab_id": "<lab-id>",
  "run_id": "<run-id>",
  "source_path": "/lab/exports/report.txt",
  "state": "quarantined",
  "quarantine_path": "./.labos/storage/labs/<lab-id>/quarantine/<export-id>/report.txt",
  "released_path": null,
  "approval_required": false,
  "sha256": "<sha256>",
  "size_bytes": 17,
  "denial_reason": null,
  "created_at": "2026-05-14T00:00:00Z",
  "updated_at": "2026-05-14T00:00:00Z"
}
```

### `POST /exports/{export_id}/release`
Copies a quarantined artifact into a managed released directory after policy review succeeds.

Current API behavior is honest:
- release is available for non-approval exports now
- high-risk exports return `409 {"detail":"export_approval_required","resource":"export"}` until an approval decision is recorded
- release copies are control-plane managed; labs do not write directly to host release locations

### `POST /exports/{export_id}/deny`
Marks a quarantined export as rejected and records the denial reason.

### `GET /exports`
Lists recorded export metadata rows, including quarantine/release state.

### `GET /events`
Lists recorded audit/event metadata rows.

## Error shape

Request validation errors return a stable machine-readable structure:

```json
{
  "detail": "validation_error",
  "errors": [
    {"field": "body.requester_type", "message": "Field required"}
  ]
}
```

## Honesty boundary

These endpoints currently provide real control-plane behavior for:
- managed lab metadata allocation
- governed run metadata
- container-workspace snapshot create/restore
- export quarantine, release, denial, and audit events

They do not yet promise:
- runtime execution inside Docker or a microVM
- microVM-grade snapshot/memory semantics
- approval decision mutation workflows for high-risk exports
- event streaming subscriptions

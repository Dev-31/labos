# LabOS API Guide

Phase 1 currently exposes the first stable control-plane surface for health, profile discovery, and metadata-backed lab, run, approval, snapshot, export, and event records.

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

### `GET /snapshots`
Lists recorded snapshot metadata rows.

### `GET /exports`
Lists recorded export metadata rows.

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

These endpoints are currently control-plane metadata APIs only. They do not yet promise:
- runtime execution
- snapshot creation semantics
- export quarantine release semantics
- approval mutation workflows
- event streaming

Those behaviors remain separate roadmap phases and should not be inferred from the presence of list/create metadata endpoints alone.

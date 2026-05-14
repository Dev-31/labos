# LabOS API Guide

Phase 1 currently exposes the first stable control-plane surface for health, profile discovery, and lab request metadata.

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
  "created_at": "2026-05-14T00:00:00Z",
  "updated_at": "2026-05-14T00:00:00Z"
}
```

Current API behavior is honest:
- this records governed lab requests in metadata
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

## Next planned API groups

The roadmap still requires additional control-plane groups before v0.1 is complete:
- `/runs`
- `/approvals`
- `/snapshots`
- `/exports`
- `/events`

# LabOS CLI Guide

The LabOS CLI is an operator surface over the same public API documented in `docs/api.md`.

Current Phase 1 stance is honest:
- the CLI wraps control-plane APIs only
- it does not bypass policy, approval, export quarantine, or audit recording
- lab and run commands currently create and inspect governed metadata records
- they do **not** provision containers or execute workloads directly yet

## Configuration

- default API base URL: `http://127.0.0.1:8000`
- override with `LABOS_API_URL`

Examples:

```bash
labos version
labos profiles list
labos labs create safe-dev --requester-type human
labos labs list
labos labs get <lab-id>
labos labs destroy <lab-id>
labos runs start <lab-id> "python -m pytest"
labos runs list
labos snapshots create <lab-id> --run-id <run-id>
labos snapshots list
labos exports request <lab-id> /lab/exports/report.txt --run-id <run-id>
labos exports list
labos approvals list
labos approvals approve <approval-id> --actor operator --comment "manual review accepted"
labos approvals deny <approval-id> --actor operator --comment "artifact denied"
labos events list
```

## Command groups

### `labos profiles`
- `list` — prints the built-in policy profiles as JSON.

### `labos labs`
- `create <profile-name> --requester-type <type> [--base-snapshot-id <snapshot-id>] [--metadata '{...}']`
- `list`
- `get <lab-id>`
- `destroy <lab-id>`

`--metadata` must be a JSON object.

`destroy` removes the managed lab storage tree and marks the lab record as `destroyed`; it does **not** imply container or microVM teardown yet because runtime provisioning is still a later phase.

### `labos runs`
- `start <lab-id> <command> [--metadata '{...}']`
- `list`

`start` currently records governed run intent through `POST /runs`; it does not execute inside Docker or a microVM yet.

### `labos snapshots`
- `create <lab-id> [--run-id <run-id>] [--requester-type <type>]`
- `list`

`create` wraps `POST /snapshots` and records snapshot metadata for the current managed workspace contents only.

### `labos exports`
- `request <lab-id> <source-path> [--run-id <run-id>] [--requester-type <type>]`
- `list`

`request` stages an export through quarantine; it does not bypass approval or release policy.

### `labos approvals`
- `list`
- `approve <approval-id> --actor <actor> [--comment <text>]`
- `deny <approval-id> --actor <actor> [--comment <text>]`

### `labos events`
- `list`

## Output

All current commands emit formatted JSON to stdout so operators and automation can pipe or parse results consistently.

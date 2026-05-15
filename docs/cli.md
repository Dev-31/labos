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
labos release readiness
labos release evidence
labos release smoke-docs
labos release smoke-cli
labos runtime probe-docker
labos scheduler enqueue create-lab --requester-id nightly-safe-dev --profile safe-dev
labos scheduler enqueue start-run --requester-id nightly-run --lab-id <lab-id> --command "python -m pytest"
labos scheduler list
labos scheduler dispatch-next
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

### `labos release`
- `readiness`
- `evidence`
- `smoke-docs [--api-url <url>] [--profile <profile-name>] [--requester-type human|agent|scheduler]`
- `smoke-cli [--api-url <url>] [--profile <profile-name>] [--requester-type human|agent|scheduler]`

`readiness` reports the current Phase 18 release blockers as JSON. Today it checks whether the Git working tree is clean and whether the optional Docker runtime smoke can run on the current host, then exits non-zero while any blocker remains.

`evidence` emits a machine-readable version of the release-checklist evidence template. It includes the current commit SHA, the standard verification commands, the docs surface to re-read before tagging, and the current Docker blocker detail so release notes or issue templates can be pre-filled honestly.

`smoke-docs` exercises the documented release smoke flow against a live API: `GET /health`, `GET /profiles`, `POST /labs`, `GET /labs`, and `DELETE /labs/<id>`. It emits one JSON summary so operators can capture evidence for the docs/API release gate without manually stitching together multiple commands. If the validation fails after the temporary lab is created, the command still attempts cleanup before returning the error.

`smoke-cli` captures the representative CLI release proof: it verifies the top-level help surface is present, then invokes the actual `labos profiles list`, `labos labs create`, `labos labs list`, `labos labs get`, and `labos labs destroy` commands against the live API. The output is one JSON summary suitable for the checklist's CLI-smoke evidence slot. If a later validation command fails after lab creation, the command still attempts cleanup before returning the failure.

### `labos runtime`
- `probe-docker`

`probe-docker` reports whether the optional real-Docker smoke test can run on the current host. It prints JSON with `cli_present`, `daemon_reachable`, `detail`, and `ready`, then exits non-zero when the environment is not actually ready.

### `labos scheduler`
- `enqueue create-lab --requester-id <requester-id> --profile <profile-name> [--scheduled-for <iso8601>] [--max-attempts <n>]`
- `enqueue start-run --requester-id <requester-id> --lab-id <lab-id> --command <command> [--scheduled-for <iso8601>] [--max-attempts <n>]`
- `list`
- `dispatch-next`

`enqueue` only records governed scheduler jobs. `dispatch-next` is an operator-driven worker stub that reuses the same control-plane lab/run creation routes as direct API calls; it does **not** claim a full background scheduler or direct runtime execution yet.

## Output

All current commands emit formatted JSON to stdout so operators and automation can pipe or parse results consistently.

# LabOS

Policy-first research containment platform for risky agent, code, and model experiments.

LabOS is the **public core**: control plane, policy engine, metadata model, runtime contracts, storage rules, export gate, approvals, audit trail, API, CLI, tests, and docs. **Private workloads** such as datasets, strategies, credentials brokers, or trading logic stay outside this repo.

## What it is
- a governed office of isolated labs
- API + CLI first operator surface
- policy-driven runtime, network, storage, approval, and export decisions
- Docker-backed control-plane path today with a microVM-ready contract for later high-risk runtime work

## What it is not
- not a generic Docker launcher
- not a dashboard-first toy
- not a trading bot product
- not an agent self-evolution product in Phase 1
- not a claim that Firecracker-grade isolation already exists in the public core

## Current implementation status
Phase 1 public core currently includes:
- named built-in policy profiles
- governed lab request records with managed storage allocation
- governed run request records with timeout metadata
- snapshot metadata plus managed-workspace archive/restore for container labs
- export quarantine, provenance, and approval-aware release flow
- approval records for high-risk lab creation and approval-gated exports
- audit/event recording across labs, runs, exports, approvals, secret leases, scheduler jobs, and reconciliation
- scheduler job queue/dispatch control-plane hooks
- reconciliation for stale approvals, expired secret leases, timed-out runs, zombie runtime detection, and destroy retry accounting
- operator CLI commands that wrap the public API only

Honesty boundary:
- LabOS does **not** yet provision real labs from the public API.
- LabOS does **not** yet execute run commands inside Docker or a microVM from the public API.
- The runtime adapter layer exists and is tested, but full runtime orchestration remains a later roadmap gate.

## Quickstart
1. Install dependencies:
   ```bash
   uv sync --extra dev
   ```
2. Start local Postgres:
   ```bash
   docker compose up -d postgres
   ```
3. Export the default database URL if needed:
   ```bash
   export LABOS_DATABASE_URL=postgresql+psycopg://labos:labos@localhost:5432/labos
   ```
4. Apply migrations:
   ```bash
   uv run alembic upgrade head
   ```
5. Start the API:
   ```bash
   uv run uvicorn labos.api.app:app --reload
   ```
6. In another shell, verify health and inspect profiles:
   ```bash
   curl http://127.0.0.1:8000/health
   curl http://127.0.0.1:8000/profiles
   ```
7. Create a governed lab request record:
   ```bash
   curl -X POST http://127.0.0.1:8000/labs \
     -H 'content-type: application/json' \
     -d '{"profile_name":"safe-dev","requester_type":"human"}'
   ```
8. Run verification locally:
   ```bash
   uv run pytest -q
   uv run ruff check .
   uv run mypy
   ```

## Local development
### Prerequisites
- Python 3.12+
- `uv`
- Docker Engine / Docker Desktop compatible daemon

### Common commands
```bash
make install
make test
make lint
make typecheck
make check
make run-api
```

### Test focus areas
- `tests/core/` — domain model and policy behavior
- `tests/api/` — public control-plane endpoints
- `tests/cli/` — operator CLI wrappers
- `tests/runtimes/` — runtime adapter behavior and honesty boundaries
- `tests/integration/test_docker_runtime_smoke.py` — optional real-Docker smoke for the adapter path; skips cleanly when no local Docker daemon is available
- `tests/workers/` — scheduler/reconciliation cleanup logic
- `tests/security/` — threat-model enforcement checks

### Docker integration smoke
When a real local Docker daemon is available, run:

```bash
labos release readiness
labos release evidence
labos release smoke-docs
labos release smoke-cli
labos runtime probe-docker
uv run pytest -q tests/integration/test_docker_runtime_smoke.py
```

Run `labos release readiness` first to see the current release blockers in one machine-readable payload. It reports whether the checkout is clean and whether the optional Docker smoke can run on the current host.

Run `labos release evidence` when you want the release-checklist evidence template pre-filled with the current commit SHA, the standard verification commands, the docs surface to re-read, and the current Docker blocker detail.

Then run `labos release smoke-docs` against a live API to exercise the documented health/profile/create/list/destroy flow in one command. It creates a temporary governed lab record with a valid control-plane requester type and destroys it again so the release operator can capture one JSON proof for the docs/API smoke gate. If a later validation step fails after creation, the command still performs best-effort cleanup before surfacing the failure.

Then run `labos release smoke-cli` against that same API to capture one JSON proof for the CLI help/profile/create/list/get/destroy flow. It invokes those representative `labos` commands through the CLI entrypoint itself, so the release checklist gets proof of the real operator surface instead of a direct helper shortcut. If one of the later validation commands fails after creation, LabOS still attempts to destroy the temporary lab record before returning the error.

Then run `labos runtime probe-docker` for the runtime-specific readiness check. It exits non-zero when the Docker CLI is missing or the daemon is unreachable, so release-prep automation can fail honestly before attempting the smoke test.

The smoke test exercises the implemented Docker adapter directly. If Docker is missing or the daemon is unreachable, the test skips and the Phase 18 release gate remains open by design.

## Architecture map
```text
Operator surfaces
  ├── FastAPI control plane (`labos/api/app.py`)
  └── Typer CLI (`labos/cli/main.py`)

Core governance
  ├── Policy engine + profile registry (`labos/core/`, `labos/config/profiles/`)
  ├── Lifecycle / state model (`labos/core/enums.py`, `labos/core/state_machine.py`)
  └── Audit/event model (`labos/core/events.py`)

Durable metadata
  ├── SQLAlchemy schema (`labos/db/schema.py`)
  ├── Session/config (`labos/db/session.py`, `labos/config/settings.py`)
  └── Alembic migrations (`alembic/`)

Storage + security
  ├── Managed storage allocator (`labos/storage/allocator.py`)
  ├── Snapshot manager (`labos/storage/snapshots.py`)
  ├── Export gate (`labos/security/export_gate.py`)
  └── Secret lease broker (`labos/security/secret_broker.py`)

Runtime + workers
  ├── Runtime adapter contract (`labos/runtimes/base.py`)
  ├── Docker adapter (`labos/runtimes/docker_runtime.py`)
  ├── Scheduler service (`labos/workers/scheduler.py`)
  └── Reconciliation service (`labos/workers/reconciler.py`)
```

## Built-in profiles
Detailed profile docs live in `docs/lab-profiles.md` and YAML examples live in `examples/profiles/`.

| Profile | Runtime class | Risk | Persistence | Network | Export posture |
| --- | --- | --- | --- | --- | --- |
| `safe-dev` | container | low | ephemeral | restricted | request-based |
| `model-local` | container | medium | persistent | restricted | approval on export |
| `research-persistent` | container | high | persistent | restricted | approval + quarantine |
| `red-zone` | microVM contract | critical | ephemeral | deny | approval + quarantine |

## Runtime support matrix
| Capability | Status | Notes |
| --- | --- | --- |
| Policy evaluation | supported | Named profiles evaluate into an execution plan. |
| Lab metadata creation | supported | `POST /labs` records governed lab requests and allocates managed storage. |
| Run metadata creation | supported | `POST /runs` records governed run requests and timeout deadlines. |
| Docker runtime adapter contract | supported in code/tests | Runtime adapter behavior is implemented and unit-tested, but not yet wired to public lab provisioning. |
| Snapshot archive/restore | partially supported | Managed workspace archive/restore for container labs only. No VM-memory semantics. |
| Export quarantine/release | supported | Managed path validation, hashing, quarantine, release, and approval-aware denial/approval flow. |
| Scheduler queue/dispatch | supported | Control-plane queue plus explicit dispatch endpoint; not a daemonized scheduler. |
| Firecracker-class runtime | not supported yet | The repo exposes a microVM-ready contract only. |
| Full runtime orchestration from API/CLI | not supported yet | Public surfaces do not claim container or microVM lifecycle execution yet. |

## Storage model
- LabOS allocates a managed root per lab under `LABOS_MANAGED_STORAGE_ROOT`.
- Each lab root contains dedicated `workspace/`, `exports/`, `quarantine/`, and `snapshots/` paths.
- Export releases copy artifacts into a managed `released/<export-id>/` path instead of allowing direct host writes from a lab.
- Snapshot manifests and archives describe managed workspace state only.
- Reconciliation treats managed storage metadata as part of the control-plane truth and marks broken records explicitly instead of silently ignoring drift.

## Approval workflow
1. A policy decision or action marks a lab or export as approval-gated.
2. LabOS records an approval request row with expiry metadata.
3. Operators list requests through `GET /approvals` or `labos approvals list`.
4. Operators approve or deny explicitly.
5. Reconciliation expires stale pending approvals and emits audit events instead of leaving them open forever.

## Export workflow
1. A run or operator writes candidate artifacts into the managed guest export path (`/lab/exports/...`).
2. `POST /exports` validates that the path resolves inside the managed export tree.
3. LabOS copies the artifact into quarantine, hashes it, and records provenance.
4. Approval-gated exports remain blocked until an explicit approval decision lands.
5. Approved exports are released into a managed `released/` path; LabOS does not claim arbitrary host write access.

## Documentation map
- `docs/specs/2026-05-13-labos-design.md` — original product/design spec
- `docs/plans/2026-05-13-labos-implementation-plan.md` — ordered implementation plan
- `ROADMAP.md` — top-level execution roadmap
- `docs/architecture.md` — architecture planes, storage model, runtime support matrix
- `docs/threat-model.md` — containment risks and verification coverage
- `docs/policies.md` — policy guarantees and profile posture summary
- `docs/lab-profiles.md` — per-profile operator guide
- `docs/api.md` — public API contract
- `docs/cli.md` — operator CLI contract
- `docs/repo-sources.md` — external references informing the architecture
- `docs/release-checklist.md` — v0.1 release-readiness checklist and evidence template
- `CHANGELOG.md` — release notes for the public core
- `CONTRIBUTING.md` — contributor workflow and guardrails
- `SECURITY.md` — security reporting and disclosure policy

## Roadmap status
The active release-readiness gate in `ROADMAP.md` / `docs/plans/2026-05-13-labos-roadmap.md` now has release checklist/changelog coverage plus verified tests, lint, type checks, install smoke, docs-command smoke, and a concrete Docker smoke command. The remaining public-core work before a `v0.1.0` tag is running that smoke on a host with a real Docker daemon and then making the final tagging decision.

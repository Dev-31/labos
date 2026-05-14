# LabOS

Policy-first research containment platform for risky agent, code, and model experiments.

## What it is
- governed office of isolated labs
- API + CLI first control plane
- policy-driven runtime, storage, network, export, and approval decisions
- containers by default, microVM-ready for high-risk workloads

## What it is not
- not a generic Docker launcher
- not a trading bot product
- not an agent self-evolution product in Phase 1
- not a dashboard-first toy

## Product rule
Public core here. Private workload packs, datasets, strategies, and sensitive profiles stay outside this repo.

## Quickstart
1. Install dependencies: `uv sync --extra dev`
2. Start local Postgres: `docker compose up -d postgres`
3. Apply the initial metadata schema: `uv run alembic upgrade head`
4. Run the test suite: `uv run pytest`
5. Start the API: `uv run uvicorn labos.api.app:app --reload`
6. Check health: `curl http://127.0.0.1:8000/health`
7. Inspect built-in profiles: `curl http://127.0.0.1:8000/profiles`
8. Create a governed lab request record: `curl -X POST http://127.0.0.1:8000/labs -H 'content-type: application/json' -d '{"profile_name":"safe-dev","requester_type":"human"}'`

## Current docs
- `docs/specs/2026-05-13-labos-design.md`
- `docs/plans/2026-05-13-labos-implementation-plan.md`
- `docs/architecture.md`
- `docs/threat-model.md`
- `docs/repo-sources.md`
- `docs/policies.md`
- `docs/api.md`
- `docs/cli.md`
- `ROADMAP.md`

## Built-in policy profiles
- `safe-dev`
- `model-local`
- `research-persistent`
- `red-zone`

Operator-facing YAML examples live in `examples/profiles/`.

## Database and migrations
- SQLAlchemy models for labs, managed storage allocations, runs, approvals, exports, snapshots, secret leases, and audit events live in `labos/db/schema.py`.
- Alembic migration scaffolding lives in `alembic/` with the initial schema in `alembic/versions/`.
- The default database URL is documented in `.env.example`.

## Managed storage
- LabOS now allocates a managed lab filesystem root for each recorded lab request under `LABOS_MANAGED_STORAGE_ROOT` (default `./.labos/storage`).
- Each lab gets reserved `workspace`, `exports`, `quarantine`, and `snapshots` paths, recorded in durable metadata.
- Export release copies are published under a managed `released/<export-id>/` directory only through the control-plane release endpoint.
- Snapshot restore is currently limited to managed container workspaces.
- High-risk lab creation and high-risk export release now create explicit approval records that can be listed and decided through the API.
- Secret access is now brokered through explicit time-bound lease records; secret names must be allowlisted by profile and resolved from `LABOS_SECRET_<NAME>` at materialization time.
- `GET /events` now returns actor/resource-aware audit rows and supports filter query parameters for event type, actor type, resource, lab, and run scope.
- The CLI currently includes read-only and operator workflows for `profiles`, `labs`, `runs`, `approvals`, and `events` against `LABOS_API_URL` (default `http://127.0.0.1:8000`). See `docs/cli.md` for command examples and current honesty boundaries.

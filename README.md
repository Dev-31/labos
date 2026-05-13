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

## Current docs
- `docs/specs/2026-05-13-labos-design.md`
- `docs/plans/2026-05-13-labos-implementation-plan.md`
- `docs/architecture.md`
- `docs/threat-model.md`
- `docs/repo-sources.md`
- `ROADMAP.md`

## Built-in policy profiles
- `safe-dev`
- `model-local`
- `research-persistent`
- `red-zone`

Operator-facing YAML examples live in `examples/profiles/`.

## Database and migrations
- SQLAlchemy models for labs, runs, approvals, exports, snapshots, and audit events live in `labos/db/schema.py`.
- Alembic migration scaffolding lives in `alembic/` with the initial schema in `alembic/versions/`.
- The default database URL is documented in `.env.example`.

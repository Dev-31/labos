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
3. Run the test suite: `uv run pytest`
4. Start the API: `uv run uvicorn labos.api.app:app --reload`
5. Check health: `curl http://127.0.0.1:8000/health`

## Current docs
- `docs/specs/2026-05-13-labos-design.md`
- `docs/plans/2026-05-13-labos-implementation-plan.md`
- `docs/architecture.md`
- `docs/threat-model.md`
- `docs/repo-sources.md`
- `ROADMAP.md`

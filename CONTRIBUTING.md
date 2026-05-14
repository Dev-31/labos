# Contributing to LabOS

Thanks for contributing to LabOS.

LabOS is a policy-first containment platform. Contributions should make the public core more reliable, more governable, or more understandable without smuggling in private workloads or fake guarantees.

## Ground rules
- Do not add private workloads, datasets, strategies, credentials brokers, or trading logic to this repo.
- Do not claim runtime guarantees the implementation does not provide.
- Do not bypass policy, approval, export quarantine, or audit layers from API or CLI changes.
- Keep docs honest whenever behavior changes.
- Prefer small, coherent changes with tests.

## Development setup
### Prerequisites
- Python 3.12+
- `uv`
- Docker Engine for local Postgres and runtime-adapter checks

### Install
```bash
uv sync --extra dev
```

### Start local dependencies
```bash
docker compose up -d postgres
export LABOS_DATABASE_URL=postgresql+psycopg://labos:labos@localhost:5432/labos
uv run alembic upgrade head
```

### Run the API locally
```bash
uv run uvicorn labos.api.app:app --reload
```

## Verification
Run the full local verification set before opening or updating a change:

```bash
uv run pytest -q
uv run ruff check .
uv run mypy
```

Useful shortcuts:

```bash
make test
make lint
make typecheck
make check
```

## Project layout
- `labos/api/` — FastAPI control plane
- `labos/cli/` — Typer operator CLI
- `labos/core/` — domain model, state machine, policy engine, events
- `labos/db/` — SQLAlchemy schema and session wiring
- `labos/storage/` — managed storage allocation and snapshot helpers
- `labos/security/` — export gate and secret broker
- `labos/runtimes/` — runtime adapter contract and Docker implementation
- `labos/workers/` — scheduler and reconciliation services
- `tests/` — domain, API, CLI, runtime, worker, and security coverage
- `docs/` — product, architecture, policy, API, and operator docs

## Scope guardrails
Contributions should follow the roadmap order.

Good fits:
- policy correctness
- lifecycle/state model improvements
- API and CLI hardening
- storage/export/approval/audit behavior
- worker reliability and cleanup
- honest runtime adapter improvements
- docs and contributor ergonomics

Not acceptable in the public core:
- pre-created demo labs or runtime experiments committed into the repo
- private credentials, datasets, or strategies
- pretending microVM isolation exists before a real backend lands
- features that bypass the public control plane

## Testing guidance
- Add or update focused tests for the slice you changed.
- Prefer red/green development where practical.
- If you touch docs that define required operator surfaces, keep `README.md`, `docs/api.md`, `docs/cli.md`, and related docs in sync.
- If you change migrations, verify them against a temporary database before claiming success.

## Pull request guidance
A good change includes:
- a short summary of what changed
- verification evidence (tests/lint/typecheck)
- updated docs when operator behavior changed
- explicit honesty notes if a capability remains partial or stubbed

## Security
For vulnerabilities or sensitive disclosure, follow `SECURITY.md`.

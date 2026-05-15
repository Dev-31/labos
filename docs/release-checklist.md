# LabOS v0.1 Release Checklist

This checklist is the Phase 18 release-prep gate for the public-core `v0.1.0` release. It is intentionally conservative: do not tag until every checked item has fresh evidence from this tree.

## Scope and honesty guardrails
- Release the **public core only**: control plane, policy engine, metadata/storage/security surfaces, API, CLI, docs, and tests.
- Do **not** add private labs, datasets, secrets, strategies, or trading logic to satisfy release pressure.
- Keep the honesty boundary explicit: the public API does not yet promise real container or microVM lifecycle orchestration.
- Do not claim Firecracker-grade guarantees or VM-memory snapshot semantics.

## Verification commands
Run these from the repo root with the project environment:

```bash
uv run pytest -q
uv run ruff check .
uv run mypy
labos release readiness
labos release smoke-docs
labos release smoke-cli
labos runtime probe-docker
uv run pytest -q tests/integration/test_docker_runtime_smoke.py
```

Record the command outputs or CI links used for the release decision.

Run `labos release readiness` before the Docker-specific checks so the current blockers are explicit in one JSON payload.

If the host does not have a reachable Docker daemon, do not check off the Docker integration gate. Capture the exact `labos runtime probe-docker` failure detail and leave release tagging blocked until the smoke test passes on a real local Docker setup.

## Release checklist
- [ ] Confirm `git status --short` is clean before tagging.
- [ ] Confirm no open code-comment placeholders remain (`TODO`, `FIXME`, `XXX`, `TBD`) outside planning docs.
- [ ] Run the full test suite and capture the passing result.
- [ ] Run Ruff and capture the clean result.
- [ ] Run mypy and capture the clean result.
- [ ] Build/install the package in a clean environment (`uv sync --extra dev` or equivalent container/venv smoke test).
- [ ] Start local dependencies from scratch (`docker compose up -d postgres`).
- [ ] Apply migrations against a fresh database (`uv run alembic upgrade head`).
- [ ] Start the API (`uv run uvicorn labos.api.app:app`).
- [ ] Re-run quickstart/API smoke commands from the docs and verify the responses (`labos release smoke-docs` can capture one JSON proof for the health/profile/create/list/destroy flow).
- [ ] Validate CLI help and representative commands against a live API (`labos release smoke-cli` can capture one JSON proof for the help/profile/create/list/get/destroy flow by invoking the actual CLI commands).
- [ ] Run `labos release readiness` and record any remaining blockers.
- [ ] Run `labos runtime probe-docker` and record the exact readiness output.
- [ ] Validate local Docker integration from scratch, including the adapter honesty boundary and any runtime smoke tests that are actually supported by the repo.
- [ ] Re-read README, `docs/api.md`, and `docs/cli.md` so documentation commands and honesty boundaries still match implementation.
- [ ] Review `SECURITY.md` and threat-model docs for accurate disclosure/reporting instructions.
- [ ] Update `CHANGELOG.md` release notes for the final tag contents.
- [ ] Create an annotated `v0.1.0` tag only after every item above has fresh evidence.

## Evidence template
Copy this block into the release issue, PR, or tag notes:

```text
Commit: <sha>
Tests: <command + pass count>
Lint: <command + result>
Types: <command + result>
Install smoke: <environment + result>
API smoke: <commands + result>
CLI smoke: <commands + result>
Docs validated: README, docs/api.md, docs/cli.md, docs/release-checklist.md
Docker integration notes: <supported runtime checks only>
Honesty boundary confirmed: yes/no
```

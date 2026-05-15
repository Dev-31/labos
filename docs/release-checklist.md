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
labos release evidence
labos release smoke-docs
labos release smoke-cli
labos release smoke-local
labos release smoke-docker
labos runtime probe-docker
uv run pytest -q tests/integration/test_docker_runtime_smoke.py
make release-readiness
make release-evidence
make smoke-docs
make smoke-cli
make smoke-local
make smoke-docker
make probe-docker
```

Record the command outputs or CI links used for the release decision.

Run `labos release readiness` before the Docker-specific checks so the current blockers are explicit in one JSON payload. Record the `next_action`, `pending_steps`, and `tag_ready` fields alongside the blocker list so the release decision is auditable. Also capture `docker.cli_path`, `docker.daemon_error`, `docker.issue_code`, and `docker.remediation` from that payload so the evidence shows whether Docker was missing entirely, merely unreachable, or blocked by daemon permissions.

Run `labos release evidence` when you want the evidence-template fields pre-filled with the current commit SHA, standard verification commands, docs surface, current Docker readiness detail, and the same `next_action` / `pending_steps` / `tag_ready` fields used to justify whether tagging is allowed. Preserve the nested `docker.cli_path`, `docker.daemon_error`, `docker.issue_code`, and `docker.remediation` values in the release record when Docker is the remaining blocker.

If you prefer Make wrappers during release prep, the repo exposes one-step aliases for the same helper surface: `make release-readiness`, `make release-evidence`, `make smoke-docs`, `make smoke-cli`, `make smoke-local`, `make smoke-docker`, and `make probe-docker`.

Use `labos release smoke-local` when you want one bounded command to bootstrap a fresh local SQLite-backed API, run the docs and CLI release smokes against that temporary server, and capture the current Docker smoke payload in the same JSON record.

Use `labos release smoke-docker` when you want one JSON proof for the runtime-side release gate. It first reports the Docker probe result and only runs the real-Docker pytest smoke when the host is actually ready.

If the host does not have a reachable Docker daemon, do not check off the Docker integration gate. Capture the exact `labos runtime probe-docker` failure detail (or the matching `labos release smoke-docker` JSON payload) and leave release tagging blocked until the smoke test passes on a real local Docker setup.

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
- [ ] Optionally rehearse the full local release smoke bundle with `labos release smoke-local` before collecting final per-step evidence.
- [ ] Re-run quickstart/API smoke commands from the docs and verify the responses (`labos release smoke-docs` can capture one JSON proof for the health/profile/create/list/destroy flow and performs best-effort cleanup if a later validation step fails).
- [ ] Validate CLI help and representative commands against a live API (`labos release smoke-cli` can capture one JSON proof for the help/profile/create/list/get/destroy flow by invoking the actual CLI commands, and it also attempts cleanup if the validation fails after lab creation).
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
Next action: <next_action field from labos release readiness>
Pending steps: <pending_steps field from labos release readiness>
Docker CLI path: <docker.cli_path field from labos release readiness>
Docker daemon error: <docker.daemon_error field from labos release readiness>
Docker issue code: <docker.issue_code field from labos release readiness>
Docker remediation: <docker.remediation field from labos release readiness>
Tag ready: <tag_ready field from labos release readiness>
Honesty boundary confirmed: yes/no
```

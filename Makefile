PYTHON ?= python3
UV ?= uv

.PHONY: install test lint typecheck check run-api smoke-docs smoke-cli probe-docker smoke-docker release-evidence

install:
	$(UV) sync --extra dev

test:
	$(UV) run pytest

lint:
	$(UV) run ruff check .

typecheck:
	$(UV) run mypy labos

check: lint typecheck test

run-api:
	$(UV) run uvicorn labos.api.app:app --reload

smoke-docs:
	$(UV) run labos release smoke-docs

smoke-cli:
	$(UV) run labos release smoke-cli

probe-docker:
	$(UV) run labos runtime probe-docker

release-evidence:
	$(UV) run labos release evidence

smoke-docker: probe-docker
	$(UV) run pytest -q tests/integration/test_docker_runtime_smoke.py

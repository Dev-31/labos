PYTHON ?= python3
UV ?= uv

.PHONY: install test lint typecheck check run-api probe-docker smoke-docker

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

probe-docker:
	$(UV) run labos runtime probe-docker

smoke-docker: probe-docker
	$(UV) run pytest -q tests/integration/test_docker_runtime_smoke.py

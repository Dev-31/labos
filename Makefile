PYTHON ?= python3
UV ?= uv

.PHONY: install test lint typecheck check run-api

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

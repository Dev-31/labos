from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


def _read(path: str) -> str:
    return (REPO_ROOT / path).read_text(encoding="utf-8")


def test_readme_documents_operator_onboarding_and_product_boundaries() -> None:
    readme = _read("README.md")

    assert "## Quickstart" in readme
    assert "## Local development" in readme
    assert "## Runtime support matrix" in readme
    assert "## Documentation map" in readme
    assert "public core" in readme.lower()
    assert "private" in readme.lower()



def test_architecture_doc_includes_text_map_runtime_matrix_and_storage_model() -> None:
    architecture = _read("docs/architecture.md")

    assert "## Control-plane map" in architecture
    assert "## Runtime support matrix" in architecture
    assert "## Storage model" in architecture



def test_lab_profiles_doc_covers_all_built_in_profiles() -> None:
    lab_profiles = _read("docs/lab-profiles.md")

    for profile_name in ["safe-dev", "model-local", "research-persistent", "red-zone"]:
        assert f"`{profile_name}`" in lab_profiles

    assert "approval workflow" in lab_profiles.lower()
    assert "export workflow" in lab_profiles.lower()



def test_contributing_doc_covers_setup_verification_and_scope_guardrails() -> None:
    contributing = _read("CONTRIBUTING.md")

    assert "uv sync --extra dev" in contributing
    assert "uv run pytest -q" in contributing
    assert "uv run ruff check ." in contributing
    assert "uv run mypy" in contributing
    assert "Do not add private workloads" in contributing


def test_release_docs_cover_v0_1_readiness_and_current_scope() -> None:
    release_checklist = _read("docs/release-checklist.md")
    changelog = _read("CHANGELOG.md")
    readme = _read("README.md")
    cli_guide = _read("docs/cli.md")

    assert "# LabOS v0.1 Release Checklist" in release_checklist
    assert "## Verification commands" in release_checklist
    assert "uv run pytest -q" in release_checklist
    assert "uv run ruff check ." in release_checklist
    assert "uv run mypy" in release_checklist
    assert "docker" in release_checklist.lower()
    assert "documentation" in release_checklist.lower()
    assert "uv run pytest -q tests/integration/test_docker_runtime_smoke.py" in release_checklist
    assert "labos runtime probe-docker" in release_checklist
    assert "labos release readiness" in release_checklist
    assert "labos release smoke-docs" in release_checklist
    assert "labos release smoke-cli" in release_checklist
    assert "docker integration smoke" in readme.lower()
    assert "labos runtime probe-docker" in readme
    assert "labos release readiness" in readme
    assert "labos release smoke-docs" in readme
    assert "labos release smoke-cli" in readme
    assert "labos release readiness" in cli_guide
    assert "labos release smoke-docs" in cli_guide
    assert "labos release smoke-cli" in cli_guide

    assert "# Changelog" in changelog
    assert "## v0.1.0 (unreleased)" in changelog
    assert "public core" in changelog.lower()
    assert "Honesty boundary" in changelog

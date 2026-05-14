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

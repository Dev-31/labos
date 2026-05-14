from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def clear_labos_api_url(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("LABOS_API_URL", raising=False)

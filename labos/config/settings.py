from __future__ import annotations

from dataclasses import dataclass
from os import getenv
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    app_name: str = "LabOS"
    database_url: str = "sqlite+pysqlite:///./labos.db"
    managed_storage_root: Path = Path("./.labos/storage")
    default_run_timeout_minutes: int = 60


def load_settings() -> Settings:
    return Settings(
        app_name=getenv("LABOS_APP_NAME", "LabOS"),
        database_url=getenv("LABOS_DATABASE_URL", "sqlite+pysqlite:///./labos.db"),
        managed_storage_root=Path(getenv("LABOS_MANAGED_STORAGE_ROOT", "./.labos/storage")),
        default_run_timeout_minutes=int(getenv("LABOS_DEFAULT_RUN_TIMEOUT_MINUTES", "60")),
    )

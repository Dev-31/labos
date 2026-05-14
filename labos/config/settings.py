from __future__ import annotations

from dataclasses import dataclass
from os import getenv


@dataclass(frozen=True)
class Settings:
    app_name: str = "LabOS"
    database_url: str = "sqlite+pysqlite:///./labos.db"


def load_settings() -> Settings:
    return Settings(
        app_name=getenv("LABOS_APP_NAME", "LabOS"),
        database_url=getenv("LABOS_DATABASE_URL", "sqlite+pysqlite:///./labos.db"),
    )

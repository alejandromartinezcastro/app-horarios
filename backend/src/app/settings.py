from __future__ import annotations

from dataclasses import dataclass
import os


@dataclass(frozen=True)
class Settings:
    app_name: str
    app_version: str
    debug: bool
    db_backend: str
    database_url: str | None



def load_settings() -> Settings:
    return Settings(
        app_name=os.getenv("APP_NAME", "app-horarios"),
        app_version=os.getenv("APP_VERSION", "0.1.0"),
        debug=os.getenv("APP_DEBUG", "false").lower() in {"1", "true", "yes"},
        db_backend=os.getenv("DB_BACKEND", "memory"),
        database_url=os.getenv("DATABASE_URL"),
    )

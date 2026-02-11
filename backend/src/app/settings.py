from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path


def _load_local_env_file() -> None:
    """Carga variables desde .env si existe, sin sobrescribir variables exportadas."""
    env_path = Path('.env')
    if not env_path.exists():
        return

    for raw_line in env_path.read_text(encoding='utf-8').splitlines():
        line = raw_line.strip()
        if not line or line.startswith('#') or '=' not in line:
            continue
        key, value = line.split('=', 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        os.environ.setdefault(key, value)


_load_local_env_file()


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

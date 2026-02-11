from __future__ import annotations

from collections.abc import Generator

from app.infra.repositories.project_repository import InMemoryProjectRepository
from app.services.project_service import ProjectService
from app.services.solver_service import SolverService, solver_service
from app.settings import load_settings

settings = load_settings()
_memory_repository = InMemoryProjectRepository()


def _get_memory_project_service() -> ProjectService:
    return ProjectService(repository=_memory_repository)


def _get_postgres_project_service() -> Generator[ProjectService, None, None]:
    from app.infra.db.session import get_db
    from app.infra.repositories.sql_project_repository import SqlProjectRepository

    for db in get_db():
        yield ProjectService(repository=SqlProjectRepository(db))


if settings.db_backend == "postgres":
    get_project_service = _get_postgres_project_service
else:
    get_project_service = _get_memory_project_service


def get_solver_service() -> SolverService:
    return solver_service

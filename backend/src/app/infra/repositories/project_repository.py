from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from threading import Lock
from typing import Any, Protocol
from uuid import uuid4

from app.services.errors import NotFoundError


@dataclass
class ProjectRecord:
    id: str
    name: str
    problem: dict[str, Any]
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    last_solution: dict[str, Any] | None = None


class ProjectRepository(Protocol):
    def list(self) -> list[ProjectRecord]: ...

    def get(self, project_id: str) -> ProjectRecord: ...

    def create(self, name: str, problem: dict[str, Any]) -> ProjectRecord: ...

    def update(
        self,
        project_id: str,
        *,
        name: str | None = None,
        problem: dict[str, Any] | None = None,
    ) -> ProjectRecord: ...

    def delete(self, project_id: str) -> None: ...

    def set_solution(self, project_id: str, solution: dict[str, Any]) -> ProjectRecord: ...


class InMemoryProjectRepository:
    def __init__(self) -> None:
        self._lock = Lock()
        self._projects: dict[str, ProjectRecord] = {}

    def list(self) -> list[ProjectRecord]:
        return sorted(self._projects.values(), key=lambda project: project.created_at)

    def get(self, project_id: str) -> ProjectRecord:
        project = self._projects.get(project_id)
        if project is None:
            raise NotFoundError("Project", project_id)
        return project

    def create(self, name: str, problem: dict[str, Any]) -> ProjectRecord:
        now = datetime.now(timezone.utc)
        project = ProjectRecord(
            id=str(uuid4()),
            name=name.strip(),
            problem=problem,
            created_at=now,
            updated_at=now,
        )
        with self._lock:
            self._projects[project.id] = project
        return project

    def update(
        self,
        project_id: str,
        *,
        name: str | None = None,
        problem: dict[str, Any] | None = None,
    ) -> ProjectRecord:
        with self._lock:
            project = self.get(project_id)
            if name is not None:
                project.name = name.strip()
            if problem is not None:
                project.problem = problem
            project.updated_at = datetime.now(timezone.utc)
            return project

    def delete(self, project_id: str) -> None:
        with self._lock:
            if project_id not in self._projects:
                raise NotFoundError("Project", project_id)
            del self._projects[project_id]

    def set_solution(self, project_id: str, solution: dict[str, Any]) -> ProjectRecord:
        with self._lock:
            project = self.get(project_id)
            project.last_solution = solution
            project.updated_at = datetime.now(timezone.utc)
            return project


project_repository = InMemoryProjectRepository()

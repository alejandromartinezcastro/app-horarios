from __future__ import annotations

from datetime import timezone
from typing import Any
from uuid import uuid4

from sqlalchemy.orm import Session

from app.infra.db.models import ProjectModel
from app.infra.repositories.project_repository import ProjectRecord, ProjectRepository
from app.services.errors import NotFoundError


class SqlProjectRepository(ProjectRepository):
    def __init__(self, db: Session) -> None:
        self._db = db

    def _to_record(self, model: ProjectModel) -> ProjectRecord:
        return ProjectRecord(
            id=model.id,
            name=model.name,
            problem=model.problem,
            last_solution=model.last_solution,
            created_at=model.created_at.astimezone(timezone.utc),
            updated_at=model.updated_at.astimezone(timezone.utc),
        )

    def list(self) -> list[ProjectRecord]:
        rows = self._db.query(ProjectModel).order_by(ProjectModel.created_at.asc()).all()
        return [self._to_record(row) for row in rows]

    def get(self, project_id: str) -> ProjectRecord:
        row = self._db.get(ProjectModel, project_id)
        if row is None:
            raise NotFoundError("Project", project_id)
        return self._to_record(row)

    def create(self, name: str, problem: dict[str, Any]) -> ProjectRecord:
        model = ProjectModel(id=str(uuid4()), name=name.strip(), problem=problem, last_solution=None)
        self._db.add(model)
        self._db.commit()
        self._db.refresh(model)
        return self._to_record(model)

    def update(
        self,
        project_id: str,
        *,
        name: str | None = None,
        problem: dict[str, Any] | None = None,
    ) -> ProjectRecord:
        model = self._db.get(ProjectModel, project_id)
        if model is None:
            raise NotFoundError("Project", project_id)

        if name is not None:
            model.name = name.strip()
        if problem is not None:
            model.problem = problem

        self._db.add(model)
        self._db.commit()
        self._db.refresh(model)
        return self._to_record(model)

    def delete(self, project_id: str) -> None:
        model = self._db.get(ProjectModel, project_id)
        if model is None:
            raise NotFoundError("Project", project_id)
        self._db.delete(model)
        self._db.commit()

    def set_solution(self, project_id: str, solution: dict[str, Any]) -> ProjectRecord:
        model = self._db.get(ProjectModel, project_id)
        if model is None:
            raise NotFoundError("Project", project_id)
        model.last_solution = solution
        self._db.add(model)
        self._db.commit()
        self._db.refresh(model)
        return self._to_record(model)

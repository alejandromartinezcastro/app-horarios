from __future__ import annotations

from app.infra.repositories.project_repository import ProjectRecord, ProjectRepository


class ProjectService:
    def __init__(self, repository: ProjectRepository) -> None:
        self._repository = repository

    def list_projects(self) -> list[ProjectRecord]:
        return self._repository.list()

    def get_project(self, project_id: str) -> ProjectRecord:
        return self._repository.get(project_id)

    def create_project(self, name: str, problem: dict) -> ProjectRecord:
        return self._repository.create(name=name, problem=problem)

    def update_project(self, project_id: str, *, name: str | None = None, problem: dict | None = None) -> ProjectRecord:
        return self._repository.update(project_id, name=name, problem=problem)

    def delete_project(self, project_id: str) -> None:
        self._repository.delete(project_id)

    def attach_solution(self, project_id: str, solution: dict) -> ProjectRecord:
        return self._repository.set_solution(project_id, solution)

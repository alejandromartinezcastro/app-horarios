from __future__ import annotations

from fastapi import APIRouter, Depends, Response, status

from app.api.deps import get_project_service, get_solver_service
from app.api.schemas import (
    ProjectCreateRequest,
    ProjectDetailResponse,
    ProjectSummaryResponse,
    ProjectUpdateRequest,
    SolveResponse,
)
from app.infra.repositories.project_repository import ProjectRecord
from app.services.project_service import ProjectService
from app.services.solver_service import SolverService

router = APIRouter(prefix="/projects", tags=["projects"])


def _to_summary(project: ProjectRecord) -> ProjectSummaryResponse:
    return ProjectSummaryResponse(
        id=project.id,
        name=project.name,
        created_at=project.created_at,
        updated_at=project.updated_at,
    )


def _to_detail(project: ProjectRecord) -> ProjectDetailResponse:
    return ProjectDetailResponse(
        id=project.id,
        name=project.name,
        created_at=project.created_at,
        updated_at=project.updated_at,
        problem=project.problem,
        last_solution=project.last_solution,
    )


@router.get("", response_model=list[ProjectSummaryResponse])
def list_projects(service: ProjectService = Depends(get_project_service)) -> list[ProjectSummaryResponse]:
    return [_to_summary(project) for project in service.list_projects()]


@router.post("", response_model=ProjectDetailResponse, status_code=status.HTTP_201_CREATED)
def create_project(
    body: ProjectCreateRequest,
    service: ProjectService = Depends(get_project_service),
) -> ProjectDetailResponse:
    project = service.create_project(name=body.name, problem=body.problem)
    return _to_detail(project)


@router.get("/{project_id}", response_model=ProjectDetailResponse)
def get_project(
    project_id: str,
    service: ProjectService = Depends(get_project_service),
) -> ProjectDetailResponse:
    return _to_detail(service.get_project(project_id))


@router.put("/{project_id}", response_model=ProjectDetailResponse)
def update_project(
    project_id: str,
    body: ProjectUpdateRequest,
    service: ProjectService = Depends(get_project_service),
) -> ProjectDetailResponse:
    project = service.update_project(project_id, name=body.name, problem=body.problem)
    return _to_detail(project)


@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_project(
    project_id: str,
    service: ProjectService = Depends(get_project_service),
) -> Response:
    service.delete_project(project_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/{project_id}/solve", response_model=SolveResponse)
def solve_project(
    project_id: str,
    project_service: ProjectService = Depends(get_project_service),
    solver_service: SolverService = Depends(get_solver_service),
) -> dict:
    project = project_service.get_project(project_id)
    solution = solver_service.solve_problem(project.problem)
    project_service.attach_solution(project_id, solution)
    return solution

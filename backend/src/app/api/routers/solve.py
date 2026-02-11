from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api.deps import get_solver_service
from app.api.schemas import SolveRequest, SolveResponse, ValidateResponse
from app.services.solver_service import SolverService

router = APIRouter(prefix="/solve", tags=["solve"])


@router.post("/validate", response_model=ValidateResponse)
def validate_problem(
    body: SolveRequest,
    service: SolverService = Depends(get_solver_service),
) -> ValidateResponse:
    report = service.validate_problem(body.problem)
    return ValidateResponse(ok=report.ok, errors=report.errors, warnings=report.warnings)


@router.post("", response_model=SolveResponse)
def solve_problem(
    body: SolveRequest,
    service: SolverService = Depends(get_solver_service),
) -> dict:
    return service.solve_problem(body.problem)

from __future__ import annotations

from typing import Any

from app.domain.core.io import problem_from_dict, solution_to_dict
from app.domain.core.validate import ValidationError, ValidationReport, validate_problem


class SolverService:
    def validate_problem(self, payload: dict[str, Any]) -> ValidationReport:
        problem = problem_from_dict(payload)
        return validate_problem(problem, raise_on_error=False)

    def solve_problem(self, payload: dict[str, Any]) -> dict[str, Any]:
        from app.domain.solver.solve import solve

        problem = problem_from_dict(payload)
        validate_problem(problem)
        solution = solve(problem)
        return solution_to_dict(solution)


solver_service = SolverService()


__all__ = ["SolverService", "solver_service", "ValidationError", "ValidationReport"]

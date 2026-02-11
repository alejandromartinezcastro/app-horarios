from app.services.solver_service import SolverService


def test_solver_service_validate_works_without_solver_runtime() -> None:
    service = SolverService()
    report = service.validate_problem(
        {
            "calendar": {"days": [], "periods_per_day": 0},
            "groups": [],
            "subjects": [],
            "teachers": [],
            "rooms": [],
            "requirements": [],
        }
    )

    assert report.ok is False
    assert report.errors

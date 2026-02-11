from app.domain.core.io import problem_from_dict
from app.domain.core.validate import validate_problem


def test_validate_reports_errors_for_invalid_problem() -> None:
    invalid_problem = {
        "calendar": {"days": [], "periods_per_day": 0},
        "groups": [],
        "subjects": [],
        "teachers": [],
        "rooms": [],
        "requirements": [],
    }

    report = validate_problem(problem_from_dict(invalid_problem), raise_on_error=False)

    assert report.ok is False
    assert any("Calendar.days está vacío." in err for err in report.errors)

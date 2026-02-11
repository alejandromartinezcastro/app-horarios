from app.domain.core.io import problem_from_dict


def test_problem_from_dict_smoke() -> None:
    payload = {
        "calendar": {"days": ["mon", "tue"], "periods_per_day": 6},
        "groups": [{"id": "G1", "size": 20}],
        "subjects": [{"id": "MATH"}],
        "teachers": [{"id": "T1", "can_teach": ["MATH"]}],
        "rooms": [{"id": "R1"}],
        "requirements": [
            {
                "group_id": "G1",
                "subject_id": "MATH",
                "periods_per_week": 3,
                "teacher_policy": "CHOOSE",
            }
        ],
    }

    problem = problem_from_dict(payload)

    assert problem.calendar.periods_per_day == 6
    assert len(problem.groups) == 1
    assert len(problem.requirements) == 1

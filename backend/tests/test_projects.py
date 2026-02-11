from app.infra.repositories.project_repository import InMemoryProjectRepository
from app.services.project_service import ProjectService


def test_project_service_crud_flow() -> None:
    service = ProjectService(repository=InMemoryProjectRepository())

    created = service.create_project(name="Demo", problem={"calendar": {"days": ["mon"], "periods_per_day": 1}})
    assert created.name == "Demo"

    listed = service.list_projects()
    assert len(listed) == 1

    fetched = service.get_project(created.id)
    assert fetched.id == created.id

    updated = service.update_project(created.id, name="Demo 2")
    assert updated.name == "Demo 2"

    service.delete_project(created.id)
    assert service.list_projects() == []


def test_attach_solution_updates_last_solution() -> None:
    service = ProjectService(repository=InMemoryProjectRepository())
    created = service.create_project(name="With solution", problem={"calendar": {"days": ["mon"], "periods_per_day": 1}})

    solution = {"scheduled": [], "teacher_assignment": [], "objective_breakdown": {}}
    updated = service.attach_solution(created.id, solution)

    assert updated.last_solution == solution

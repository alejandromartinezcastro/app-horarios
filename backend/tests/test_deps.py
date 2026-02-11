from app.api.deps import get_project_service
from app.services.project_service import ProjectService


def test_get_project_service_defaults_to_memory() -> None:
    service = get_project_service()
    assert isinstance(service, ProjectService)

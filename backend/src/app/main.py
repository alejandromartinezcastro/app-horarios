from __future__ import annotations

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse

from app.api.routers.health import router as health_router
from app.api.routers.projects import router as projects_router
from app.api.routers.solve import router as solve_router
from app.logging import configure_logging
from app.services.errors import NotFoundError
from app.settings import Settings, load_settings
from app.domain.core.validate import ValidationError


def create_app(settings: Settings | None = None) -> FastAPI:
    active_settings = settings or load_settings()
    configure_logging(debug=active_settings.debug)

    app = FastAPI(title=active_settings.app_name, version=active_settings.app_version)

    @app.exception_handler(NotFoundError)
    async def handle_not_found(_: Request, exc: NotFoundError) -> JSONResponse:
        return JSONResponse(status_code=404, content={"detail": str(exc)})

    @app.exception_handler(ValidationError)
    async def handle_validation(_: Request, exc: ValidationError) -> JSONResponse:
        return JSONResponse(status_code=422, content={"detail": exc.errors})

    @app.exception_handler(ValueError)
    async def handle_value_error(_: Request, exc: ValueError) -> JSONResponse:
        return JSONResponse(status_code=400, content={"detail": str(exc)})

    @app.exception_handler(HTTPException)
    async def passthrough_http(_: Request, exc: HTTPException) -> JSONResponse:
        return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})

    app.include_router(health_router)
    app.include_router(projects_router)
    app.include_router(solve_router)

    return app


app = create_app()

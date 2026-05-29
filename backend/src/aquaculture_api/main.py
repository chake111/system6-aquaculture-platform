import uuid
from collections.abc import Callable

from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse

from aquaculture_api import deps
from aquaculture_api.config import Settings
from aquaculture_api.routes import (
    agent,
    alerts,
    auth,
    demo,
    density,
    edge,
    operations,
    ponds,
    recommendations,
    reports,
)
from aquaculture_api.store import create_store


def create_app(settings: Settings | None = None) -> FastAPI:
    configuration = settings or Settings.from_environment()
    store = create_store(configuration)
    deps.configure(store, configuration)

    application = FastAPI(title="System 6 Aquaculture Monitoring API", version="0.1.0")

    @application.middleware("http")
    async def add_trace_id(request: Request, call_next: Callable[[Request], Response]) -> Response:
        request.state.trace_id = uuid.uuid4().hex
        response = await call_next(request)
        response.headers["X-Trace-Id"] = request.state.trace_id
        return response

    @application.exception_handler(deps.ApiError)
    async def api_error_handler(_request: Request, exc: deps.ApiError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content={"error": {"code": exc.code, "message": exc.message}},
        )

    @application.get("/api/health", tags=["system"])
    def get_health() -> dict[str, str]:
        return {"status": "ok", "system": "system-6-aquaculture"}

    application.include_router(auth.router())
    application.include_router(ponds.router())
    application.include_router(demo.router())
    application.include_router(edge.router())
    application.include_router(recommendations.router())
    application.include_router(alerts.router())
    application.include_router(density.router())
    application.include_router(reports.router())
    application.include_router(operations.router())
    application.include_router(agent.router())

    return application


app = create_app()

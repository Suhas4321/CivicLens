import logging
import time
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.middleware.base import RequestResponseEndpoint
from starlette.responses import Response

from civiclens.api.health import router as health_router
from civiclens.bootstrap.settings import get_settings
from civiclens.infrastructure.telemetry.logging import configure_logging
from civiclens.modules.decisions.api import router as decisions_router
from civiclens.modules.demo_sessions.api import router as demo_sessions_router
from civiclens.modules.intake.api import router as intake_router
from civiclens.modules.planning.api import router as planning_router
from civiclens.modules.workflow_reviews.api import router as workflow_reviews_router

settings = get_settings()
configure_logging(settings.log_level)
logger = logging.getLogger("civiclens.api")


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    logger.info("application_started")
    yield
    logger.info("application_stopped")


app = FastAPI(
    title="CivicLens API",
    version=settings.app_version,
    description="Explainable civic needs-to-project decision intelligence.",
    lifespan=lifespan,
    docs_url="/api/docs" if settings.app_env != "production" else None,
    openapi_url="/api/openapi.json",
)

if settings.app_env in {"local", "test"}:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.web_origins,
        allow_credentials=False,
        allow_methods=["GET", "POST"],
        allow_headers=[
            "Accept",
            "Authorization",
            "Content-Type",
            "Idempotency-Key",
            "X-Correlation-ID",
            "X-Demo-Session-ID",
            "X-Receipt-Capability",
        ],
    )


@app.middleware("http")
async def request_context(request: Request, call_next: RequestResponseEndpoint) -> Response:
    correlation_id = request.headers.get("X-Correlation-ID") or str(uuid4())
    started = time.perf_counter()
    try:
        response = await call_next(request)
    except Exception:
        logger.exception(
            "unhandled_request_error",
            extra={
                "correlation_id": correlation_id,
                "method": request.method,
                "path": request.url.path,
            },
        )
        return JSONResponse(
            status_code=500,
            content={"code": "INTERNAL_ERROR", "correlation_id": correlation_id},
            headers={"X-Correlation-ID": correlation_id},
        )

    duration_ms = round((time.perf_counter() - started) * 1000, 2)
    response.headers["X-Correlation-ID"] = correlation_id
    response.headers["Cache-Control"] = "no-store"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Permissions-Policy"] = "camera=(), geolocation=(), microphone=()"
    logger.info(
        "request_completed",
        extra={
            "correlation_id": correlation_id,
            "method": request.method,
            "path": request.url.path,
            "status_code": response.status_code,
            "duration_ms": duration_ms,
        },
    )
    return response


app.include_router(health_router, prefix="/api/v1")
app.include_router(demo_sessions_router, prefix="/api/v1")
app.include_router(intake_router, prefix="/api/v1")
app.include_router(planning_router, prefix="/api/v1")
app.include_router(decisions_router, prefix="/api/v1")
app.include_router(workflow_reviews_router, prefix="/api/v1")

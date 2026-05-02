"""
Main FastAPI Application

This file is the entry point. It:
  1. Defines the lifespan (startup/shutdown events)
  2. Configures middleware (CORS, request logging)
  3. Registers global exception handlers
  4. Mounts all routers
  5. Exposes /health and /metrics endpoints
"""

import asyncio
import time
# import sys

# from pathlib import Path
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from backend.core.config import settings
from backend.core.database import init_db, close_db, check_db_connection
from backend.core.exceptions import AppException
from backend.core.logging import setup_logging, get_logger
from backend.services.severity import severity_service
from backend.services.websocket_manager import connection_manager

logger = get_logger(__name__)

# sys.path.append(str(Path(__file__).resolve().parent.parent))

# ── Lifespan ──────────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Runs startup logic before the app serves requests,
    and shutdown logic after the last request is handled.
    """
    # ── Startup ───────────────────────────────────────────────
    setup_logging()
    logger.info(
    f"Starting Ambulance Optimizer API | version={settings.APP_VERSION} | env={settings.ENVIRONMENT}"
    )
    # logger.info("Starting Ambulance Optimizer API", version=settings.APP_VERSION,
    #             environment=settings.ENVIRONMENT)


    # Initialise database tables
    await init_db()

    # Load ML model into memory (once — not per request)
    severity_service.load_model()
    logger.info(
    f"Severity model status | loaded={severity_service.is_loaded} | version={severity_service.model_version}"
    )
    # logger.info("Severity model status", loaded=severity_service.is_loaded,
    #             version=severity_service.model_version)

    # Start WebSocket heartbeat as background task
    asyncio.create_task(
        connection_manager.start_heartbeat(settings.WS_HEARTBEAT_INTERVAL)
    )

    logger.info("Application startup complete — ready to serve")
    yield

    # ── Shutdown ──────────────────────────────────────────────
    logger.info("Shutting down application")
    await close_db()
    logger.info("Shutdown complete")


# ── Application ───────────────────────────────────────────────────────────────

app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description=(
        "AI-powered ambulance dispatch system with severity prediction, "
        "resource allocation, and real-time GIS routing."
    ),
    docs_url="/docs" if settings.DEBUG or settings.ENVIRONMENT != "production" else None,
    redoc_url="/redoc" if settings.DEBUG or settings.ENVIRONMENT != "production" else None,
    lifespan=lifespan,
)


# ── Middleware ────────────────────────────────────────────────────────────────

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def request_logging_middleware(request: Request, call_next):
    """Log every request with method, path, status code, and duration."""
    start = time.perf_counter()
    response = await call_next(request)
    duration_ms = round((time.perf_counter() - start) * 1000, 2)

    logger.info(
    f"HTTP {request.method} {request.url.path} "
    f"status={response.status_code} "
    f"time={duration_ms}ms "
    f"client={request.client.host if request.client else 'unknown'}"
    )
    # logger.info(
    #     "HTTP request",
    #     method=request.method,
    #     path=request.url.path,
    #     status_code=response.status_code,
    #     duration_ms=duration_ms,
    #     client=request.client.host if request.client else "unknown",
    # )
    response.headers["X-Response-Time-Ms"] = str(duration_ms)
    return response


# ── Global Exception Handlers ─────────────────────────────────────────────────

@app.exception_handler(AppException)
async def app_exception_handler(request: Request, exc: AppException) -> JSONResponse:
    """Convert all AppException subclasses to structured JSON responses."""
    # logger.warning(
    #     "Application exception",
    #     error_code=exc.error_code,
    #     message=exc.message,
    #     path=request.url.path,
    # )
    logger.warning(
    f"Application exception | error_code={exc.error_code} | message={exc.message} | path={request.url.path}"
    )
    return JSONResponse(status_code=exc.status_code, content=exc.to_dict())


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Catch-all for unexpected errors — never expose internal details."""
    # logger.error("Unhandled exception", error=str(exc), path=request.url.path,
    #              exc_info=True)
    logger.error(f"Unhandled exception: {str(exc)} | Path: {request.url.path}", exc_info=True)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"error": "INTERNAL_ERROR", "message": "An unexpected error occurred."},
    )


# ── Routers ───────────────────────────────────────────────────────────────────

# from backend.routers import incidents, ambulances, dispatch, dashboard  # noqa: E402
from backend.routers.incidents import router as incidents_router
from backend.routers.ambulances import router as ambulances_router
from backend.routers.dispatch import router as dispatch_router
from backend.routers.dashboard import router as dashboard_router


app.include_router(incidents_router,  prefix="/api/v1")
app.include_router(ambulances_router, prefix="/api/v1")
app.include_router(dispatch_router,   prefix="/api/v1")
app.include_router(dashboard_router,  prefix="/api/v1")

# app.include_router(incidents.router,  prefix="/api/v1", tags=["Incidents"])
# app.include_router(ambulances.router, prefix="/api/v1", tags=["Ambulances"])
# app.include_router(dispatch.router,   prefix="/api/v1", tags=["Dispatch"])
# app.include_router(dashboard.router,  prefix="/api/v1", tags=["Dashboard"])


# ── Health + Metrics ──────────────────────────────────────────────────────────

@app.get("/health", tags=["System"])
async def health_check():
    """
    System health endpoint. Returns status of each dependency.
    Used by load balancers and monitoring tools.
    """
    db_ok = await check_db_connection()

    return {
        "status": "healthy" if db_ok else "degraded",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "version": settings.APP_VERSION,
        "environment": settings.ENVIRONMENT,
        "dependencies": {
            "database": "ok" if db_ok else "error",
            "severity_model": "ok" if severity_service.is_loaded else "fallback",
            "model_version": severity_service.model_version,
        },
        "websockets": {
            "connected_dashboards": connection_manager.dashboard_count,
            "connected_ambulances": connection_manager.ambulance_count,
        },
    }


@app.get("/", tags=["System"])
async def root():
    return {
        "service": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "docs": "/docs",
        "health": "/health",
    }

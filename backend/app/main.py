"""FastAPI application entry point."""

from __future__ import annotations

import time
from contextlib import asynccontextmanager

from apscheduler.schedulers.background import BackgroundScheduler
from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.v1 import api_router
from app.core.config import settings
from app.core.logging_config import get_logger, setup_logging
from app.core.storage import ensure_bucket
from app.db.session import SessionLocal
from app.services.exam_engine import sweep_expired_sessions
from app.services.validators import ValidationError

logger = get_logger("app")
_scheduler: BackgroundScheduler | None = None


def _sweep_job() -> None:
    """Close sessions abandoned without a submit - the candidate simply closed the lid."""
    db = SessionLocal()
    try:
        if sweep_expired_sessions(db):
            db.commit()
    except Exception as exc:  # noqa: BLE001 - a sweeper failure must not kill the scheduler
        db.rollback()
        logger.error("Expired-session sweep failed: %s", exc)
    finally:
        db.close()


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _scheduler
    setup_logging()
    logger.info("Starting %s (%s)", settings.APP_NAME, settings.ENVIRONMENT)

    if ensure_bucket():
        logger.info("Object storage ready: bucket %s", settings.S3_BUCKET)
    else:
        logger.warning("Object storage unavailable - image answers and snapshots will be rejected")

    _scheduler = BackgroundScheduler(daemon=True)
    _scheduler.add_job(_sweep_job, "interval", seconds=60, id="expire_sessions")
    _scheduler.start()
    logger.info("Session sweeper started (every 60s)")

    yield

    if _scheduler is not None:
        _scheduler.shutdown(wait=False)
    logger.info("Shutdown complete")


app = FastAPI(
    title=settings.APP_NAME,
    version="0.1.0",
    description=(
        "AI-proctored online examination platform: question bank, randomized papers, "
        "timed exam engine, proctoring intake and AI-assisted subjective grading."
    ),
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.BACKEND_CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Process-Time"],
)


@app.middleware("http")
async def timing_and_logging(request: Request, call_next):
    started = time.perf_counter()
    response = await call_next(request)
    elapsed_ms = (time.perf_counter() - started) * 1000
    response.headers["X-Process-Time"] = f"{elapsed_ms:.1f}ms"
    if elapsed_ms > 1000:
        logger.warning("SLOW %s %s took %.0fms", request.method, request.url.path, elapsed_ms)
    return response


@app.exception_handler(ValidationError)
async def domain_validation_handler(request: Request, exc: ValidationError):
    """Domain rule breaches surface as 422 with a plain message, not a stack trace."""
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, content={"detail": str(exc)}
    )


@app.exception_handler(RequestValidationError)
async def request_validation_handler(request: Request, exc: RequestValidationError):
    """Flatten Pydantic errors into one readable sentence for the UI's toast."""
    messages = []
    for error in exc.errors():
        location = " -> ".join(str(p) for p in error["loc"] if p not in {"body", "query"})
        message = error["msg"].replace("Value error, ", "")
        messages.append(f"{location}: {message}" if location else message)
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={"detail": "; ".join(messages) or "Invalid request"},
    )


@app.get("/health", tags=["meta"])
def health() -> dict:
    return {"status": "ok", "app": settings.APP_NAME, "environment": settings.ENVIRONMENT}


@app.get("/", tags=["meta"])
def root() -> dict:
    return {
        "name": settings.APP_NAME,
        "docs": "/docs",
        "api": settings.API_V1_PREFIX,
    }


app.include_router(api_router, prefix=settings.API_V1_PREFIX)

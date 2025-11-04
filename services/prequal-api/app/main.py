"""FastAPI application entry point for Loan Prequalification API."""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from decimal import Decimal
from typing import Any

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from shared.core.config import settings
from shared.core.database import close_db
from shared.core.logging import configure_logging, get_logger

from app.api.routes import applications, health
from app.kafka.producer import kafka_producer

# Configure structured logging
configure_logging()
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """
    Manage application lifecycle (startup and shutdown).

    Startup:
    - Initialize Kafka producer

    Shutdown:
    - Close Kafka producer
    - Close database connections
    """
    logger.info("Starting Loan Prequalification API", environment=settings.environment)

    # Startup: Initialize Kafka producer
    try:
        await kafka_producer.start()
        logger.info("Application startup complete")
    except Exception as e:
        logger.error("Failed to start Kafka producer", error=str(e))
        raise

    yield

    # Shutdown: Clean up resources
    logger.info("Shutting down application")
    try:
        await kafka_producer.stop()
        await close_db()
        logger.info("Application shutdown complete")
    except Exception as e:
        logger.error("Error during shutdown", error=str(e))


# Create FastAPI application
app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description=(
        "Event-driven microservices system for processing loan prequalification "
        "applications in the Indian financial market. Provides fast, asynchronous "
        "loan eligibility decisions based on PAN numbers and CIBIL score checks."
    ),
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


# Exception handlers
def sanitize_errors(errors: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Convert Decimal and other non-serializable types to strings in validation errors."""
    sanitized = []
    for error in errors:
        error_copy = error.copy()
        # Convert Decimal objects in ctx dict to strings
        if "ctx" in error_copy and isinstance(error_copy["ctx"], dict):
            error_copy["ctx"] = {
                k: str(v) if isinstance(v, Decimal) else v for k, v in error_copy["ctx"].items()
            }
        sanitized.append(error_copy)
    return sanitized


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    """Handle Pydantic validation errors with structured response."""
    errors = sanitize_errors(exc.errors())
    logger.warning(
        "Validation error",
        path=request.url.path,
        errors=errors,
    )

    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "error": "Validation Error",
            "detail": errors,
        },
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Handle unexpected exceptions with generic error response."""
    logger.error(
        "Unhandled exception",
        path=request.url.path,
        error=str(exc),
        exc_info=True,
    )

    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "error": "Internal Server Error",
            "detail": "An unexpected error occurred. Please try again later.",
        },
    )


# Include routers
app.include_router(health.router)
app.include_router(applications.router)


# Root endpoint
@app.get(
    "/",
    summary="API Root",
    description="Welcome endpoint with API information",
    tags=["root"],
)
async def root() -> dict[str, str]:
    """
    Root endpoint providing basic API information.

    Returns links to API documentation.
    """
    return {
        "message": "Welcome to Loan Prequalification API",
        "version": settings.app_version,
        "docs": "/docs",
        "health": "/health",
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level=settings.log_level.lower(),
    )

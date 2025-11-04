"""Health check endpoint for monitoring and orchestration."""

from fastapi import APIRouter, Depends, status
from fastapi.responses import JSONResponse
from shared.core.database import get_db
from shared.core.logging import get_logger
from shared.schemas.application import HealthCheckResponse
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.kafka.producer import KafkaProducerWrapper, get_kafka_producer

logger = get_logger(__name__)
router = APIRouter(tags=["health"])


@router.get(
    "/health",
    response_model=HealthCheckResponse,
    summary="Health Check",
    description="Check the health status of the application and its dependencies",
    responses={
        200: {"description": "System is healthy", "model": HealthCheckResponse},
        503: {"description": "System is unhealthy", "model": HealthCheckResponse},
    },
)
async def health_check(
    db: AsyncSession = Depends(get_db),
    kafka_producer: KafkaProducerWrapper = Depends(get_kafka_producer),
) -> JSONResponse:
    """
    Health check endpoint for monitoring and orchestration.

    Checks:
    - Database connectivity (PostgreSQL)
    - Kafka producer status

    Returns:
    - 200 OK if all systems are healthy
    - 503 Service Unavailable if any system is down
    """
    health_status = {
        "status": "healthy",
        "database": "unknown",
        "kafka": "unknown",
    }

    # Check database connection
    try:
        await db.execute(text("SELECT 1"))
        health_status["database"] = "connected"
        logger.debug("Database health check: OK")
    except Exception as e:
        logger.error("Database health check failed", error=str(e))
        health_status["database"] = "disconnected"
        health_status["status"] = "unhealthy"

    # Check Kafka producer status
    try:
        if kafka_producer.is_started():
            health_status["kafka"] = "connected"
            logger.debug("Kafka health check: OK")
        else:
            raise Exception("Kafka producer not started")
    except Exception as e:
        logger.error("Kafka health check failed", error=str(e))
        health_status["kafka"] = "disconnected"
        health_status["status"] = "unhealthy"

    # Return appropriate status code
    status_code = (
        status.HTTP_200_OK
        if health_status["status"] == "healthy"
        else status.HTTP_503_SERVICE_UNAVAILABLE
    )

    return JSONResponse(content=health_status, status_code=status_code)

"""API routes for loan application endpoints."""

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from shared.core.config import settings
from shared.core.database import get_db
from shared.core.logging import get_logger
from shared.exceptions.exceptions import ApplicationNotFoundError
from shared.schemas.application import (
    ApplicationStatusResponse,
    LoanApplicationRequest,
    LoanApplicationResponse,
)
from sqlalchemy.ext.asyncio import AsyncSession

from app.kafka.producer import KafkaProducerWrapper, get_kafka_producer
from app.services.application_service import ApplicationService

logger = get_logger(__name__)
router = APIRouter(prefix="/applications", tags=["applications"])


def _generate_correlation_id() -> str:
    """Generate a unique correlation ID for request tracing."""
    return str(uuid.uuid4())


@router.post(
    "",
    response_model=LoanApplicationResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Submit Loan Application",
    description="Submit a new loan prequalification application for processing",
    responses={
        202: {
            "description": "Application accepted and queued for processing",
            "model": LoanApplicationResponse,
        },
        422: {"description": "Validation error - invalid request data"},
        500: {"description": "Internal server error"},
    },
)
async def create_application(
    request: LoanApplicationRequest,
    db: AsyncSession = Depends(get_db),
    kafka_producer: KafkaProducerWrapper = Depends(get_kafka_producer),
) -> LoanApplicationResponse:
    """
    Submit a new loan prequalification application.

    This endpoint:
    - Validates application data (PAN format, positive amounts, etc.)
    - Saves application to database with PENDING status
    - Publishes message to Kafka for async processing
    - Returns application ID for status tracking

    The application will be processed asynchronously by:
    1. credit-service: Calculates CIBIL score
    2. decision-service: Applies business rules and updates status
    """
    correlation_id = _generate_correlation_id()

    logger.info(
        "Received loan application request",
        loan_type=request.loan_type,
        correlation_id=correlation_id,
    )

    try:
        service = ApplicationService(
            db=db,
            kafka_producer=kafka_producer,
            topic_name=settings.kafka_topic_applications_submitted,
        )

        response = await service.create_application(
            request=request,
            correlation_id=correlation_id,
        )

        return response

    except Exception as e:
        logger.error(
            "Failed to create application",
            error=str(e),
            correlation_id=correlation_id,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create application. Please try again later.",
        )


@router.get(
    "/{application_id}/status",
    response_model=ApplicationStatusResponse,
    status_code=status.HTTP_200_OK,
    summary="Get Application Status",
    description="Retrieve the current status of a loan application by ID",
    responses={
        200: {
            "description": "Application status retrieved successfully",
            "model": ApplicationStatusResponse,
        },
        404: {"description": "Application not found"},
        500: {"description": "Internal server error"},
    },
)
async def get_application_status(
    application_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    kafka_producer: KafkaProducerWrapper = Depends(get_kafka_producer),
) -> ApplicationStatusResponse:
    """
    Get the current status of a loan application.

    Returns the application status which can be:
    - PENDING: Application is being processed
    - PRE_APPROVED: Applicant meets all criteria
    - REJECTED: Applicant does not meet minimum criteria
    - MANUAL_REVIEW: Borderline case requiring human review

    The status is updated asynchronously after CIBIL score calculation
    and decision engine processing (typically within 5 seconds).
    """
    logger.info("Application status requested", application_id=str(application_id))

    try:
        service = ApplicationService(
            db=db,
            kafka_producer=kafka_producer,
            topic_name=settings.kafka_topic_applications_submitted,
        )

        response = await service.get_application_status(application_id)

        return response

    except ApplicationNotFoundError:
        logger.warning("Application not found for status check", application_id=str(application_id))
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Application with ID {application_id} not found",
        )

    except Exception as e:
        logger.error(
            "Failed to retrieve application status",
            error=str(e),
            application_id=str(application_id),
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve application status. Please try again later.",
        )

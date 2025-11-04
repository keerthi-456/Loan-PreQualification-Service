"""Application service for business logic layer.

This service orchestrates application creation, status retrieval,
and Kafka message publishing.
"""

import uuid
from datetime import datetime

from shared.core.logging import get_logger, mask_pan
from shared.exceptions.exceptions import ApplicationNotFoundError, KafkaPublishError
from shared.models.application import Application
from shared.schemas.application import (
    ApplicationStatusResponse,
    LoanApplicationRequest,
    LoanApplicationResponse,
)
from shared.schemas.kafka_messages import LoanApplicationMessage
from sqlalchemy.ext.asyncio import AsyncSession

from app.kafka.producer import KafkaProducerWrapper
from app.repositories.application_repository import ApplicationRepository

logger = get_logger(__name__)


class ApplicationService:
    """Service layer for application business logic."""

    def __init__(self, db: AsyncSession, kafka_producer: KafkaProducerWrapper, topic_name: str):
        """
        Initialize application service.

        Args:
            db: Async database session
            kafka_producer: Kafka producer instance
            topic_name: Kafka topic for application submissions
        """
        self.repository = ApplicationRepository(db)
        self.kafka_producer = kafka_producer
        self.topic_name = topic_name

    async def create_application(
        self,
        request: LoanApplicationRequest,
        correlation_id: str,
    ) -> LoanApplicationResponse:
        """
        Create a new loan prequalification application.

        This method:
        1. Validates input (already done by Pydantic)
        2. Creates Application model with PENDING status
        3. Saves to database
        4. Publishes message to Kafka
        5. Returns application ID

        Args:
            request: Validated loan application request
            correlation_id: Correlation ID for distributed tracing

        Returns:
            LoanApplicationResponse: Application ID and status

        Raises:
            DatabaseError: If database operation fails
            KafkaPublishError: If Kafka publishing fails
        """
        logger.info(
            "Creating new loan application",
            pan_number=mask_pan(request.pan_number),
            loan_type=request.loan_type,
            correlation_id=correlation_id,
        )

        # Create Application model
        application = Application(
            id=uuid.uuid4(),
            pan_number=request.pan_number,
            applicant_name=request.applicant_name,
            monthly_income_inr=request.monthly_income_inr,
            loan_amount_inr=request.loan_amount_inr,
            loan_type=request.loan_type,
            status="PENDING",
        )

        # Save to database
        try:
            saved_application = await self.repository.save(application)
        except Exception as e:
            logger.error(
                "Failed to save application to database",
                error=str(e),
                correlation_id=correlation_id,
            )
            raise

        # Publish to Kafka
        try:
            await self._publish_application_submitted(saved_application, correlation_id)
        except KafkaPublishError as e:
            # Application is saved but Kafka failed
            # Raise exception to return 500 to client
            # This prevents silent data loss (app in DB but never processed)
            logger.error(
                "Failed to publish application to Kafka after retries",
                application_id=str(saved_application.id),
                error=str(e),
                correlation_id=correlation_id,
            )
            # Re-raise to fail the request with 500
            raise KafkaPublishError(
                f"Failed to publish application {saved_application.id} to Kafka: {str(e)}"
            ) from e

        logger.info(
            "Application created successfully",
            application_id=str(saved_application.id),
            correlation_id=correlation_id,
        )

        return LoanApplicationResponse(
            application_id=saved_application.id,
            status="PENDING",
        )

    async def get_application_status(self, application_id: uuid.UUID) -> ApplicationStatusResponse:
        """
        Retrieve application status by ID.

        Args:
            application_id: UUID of the application

        Returns:
            ApplicationStatusResponse: Application ID and current status

        Raises:
            ApplicationNotFoundError: If application doesn't exist
        """
        logger.debug("Retrieving application status", application_id=str(application_id))

        application = await self.repository.find_by_id(application_id)

        if not application:
            logger.warning("Application not found", application_id=str(application_id))
            raise ApplicationNotFoundError(application_id)

        logger.info(
            "Application status retrieved",
            application_id=str(application_id),
            status=application.status,
        )

        return ApplicationStatusResponse(
            application_id=application.id,
            status=application.status,  # type: ignore
        )

    async def _publish_application_submitted(
        self, application: Application, correlation_id: str
    ) -> None:
        """
        Publish loan application submitted message to Kafka.

        Args:
            application: Application model instance
            correlation_id: Correlation ID for tracing

        Raises:
            KafkaPublishError: If publishing fails after retries
        """
        message = LoanApplicationMessage(
            application_id=application.id,
            pan_number=application.pan_number,
            applicant_name=application.applicant_name,
            monthly_income_inr=application.monthly_income_inr,
            loan_amount_inr=application.loan_amount_inr,
            loan_type=application.loan_type,  # type: ignore
            timestamp=datetime.utcnow(),
            correlation_id=correlation_id,
        )

        logger.debug(
            "Publishing application to Kafka",
            topic=self.topic_name,
            application_id=str(application.id),
            correlation_id=correlation_id,
        )

        await self.kafka_producer.send_and_wait(
            topic=self.topic_name,
            value=message.model_dump(mode="json"),
            key=str(application.id),  # Partition by application_id
        )

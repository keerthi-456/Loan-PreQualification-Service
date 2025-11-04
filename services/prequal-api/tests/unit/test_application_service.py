"""Unit tests for ApplicationService with mocked dependencies.

These tests verify the service layer business logic with mocked
repository and Kafka producer dependencies.
"""

import uuid
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from shared.exceptions.exceptions import ApplicationNotFoundError, KafkaPublishError
from shared.models.application import Application
from shared.schemas.application import LoanApplicationRequest

from app.services.application_service import ApplicationService


@pytest.fixture
def mock_db_session():
    """Create a mock AsyncSession."""
    return AsyncMock()


@pytest.fixture
def mock_kafka_producer():
    """Create a mock KafkaProducerWrapper."""
    producer = MagicMock()
    producer.send_and_wait = AsyncMock()
    return producer


@pytest.fixture
def application_service(mock_db_session, mock_kafka_producer):
    """Create ApplicationService with mocked dependencies."""
    return ApplicationService(
        db=mock_db_session,
        kafka_producer=mock_kafka_producer,
        topic_name="loan_applications_submitted",
    )


class TestApplicationServiceCreateApplication:
    """Test suite for create_application method."""

    @pytest.mark.asyncio
    async def test_create_application_success(self, application_service, mock_kafka_producer):
        """Test successfully creating a new application."""
        # Mock request
        request = LoanApplicationRequest(
            pan_number="ABCDE1234F",
            applicant_name="Rajesh Kumar",
            monthly_income_inr=Decimal("75000.00"),
            loan_amount_inr=Decimal("500000.00"),
            loan_type="PERSONAL",
        )

        # Mock repository save
        with patch.object(application_service.repository, "save") as mock_save:
            mock_application = Application(
                id=uuid.uuid4(),
                pan_number=request.pan_number,
                applicant_name=request.applicant_name,
                monthly_income_inr=request.monthly_income_inr,
                loan_amount_inr=request.loan_amount_inr,
                loan_type=request.loan_type,
                status="PENDING",
            )
            mock_save.return_value = mock_application

            # Create application
            response = await application_service.create_application(
                request=request,
                correlation_id="test-correlation-id",
            )

            # Verify repository was called
            mock_save.assert_awaited_once()

            # Verify Kafka was called
            mock_kafka_producer.send_and_wait.assert_awaited_once()

            # Verify response
            assert response.application_id == mock_application.id
            assert response.status == "PENDING"

    @pytest.mark.asyncio
    async def test_create_application_with_minimal_fields(
        self, application_service, mock_kafka_producer
    ):
        """Test creating application with optional applicant_name as None."""
        request = LoanApplicationRequest(
            pan_number="FGHIJ5678K",
            monthly_income_inr=Decimal("50000.00"),
            loan_amount_inr=Decimal("200000.00"),
            loan_type="AUTO",
        )

        with patch.object(application_service.repository, "save") as mock_save:
            mock_application = Application(
                id=uuid.uuid4(),
                pan_number=request.pan_number,
                applicant_name=None,
                monthly_income_inr=request.monthly_income_inr,
                loan_amount_inr=request.loan_amount_inr,
                loan_type=request.loan_type,  # Use the loan_type from request
                status="PENDING",
            )
            mock_save.return_value = mock_application

            response = await application_service.create_application(
                request=request,
                correlation_id="test-id",
            )

            assert response.application_id == mock_application.id
            assert response.status == "PENDING"

    @pytest.mark.asyncio
    async def test_create_application_database_error_propagates(self, application_service):
        """Test that database errors are propagated."""
        request = LoanApplicationRequest(
            pan_number="ABCDE1234F",
            monthly_income_inr=Decimal("50000.00"),
            loan_amount_inr=Decimal("200000.00"),
            loan_type="PERSONAL",
        )

        # Mock repository to raise exception
        with patch.object(application_service.repository, "save") as mock_save:
            mock_save.side_effect = Exception("Database connection failed")

            with pytest.raises(Exception) as exc_info:
                await application_service.create_application(
                    request=request,
                    correlation_id="test-id",
                )

            assert "Database connection failed" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_create_application_kafka_error_does_not_fail_request(
        self, application_service, mock_kafka_producer
    ):
        """Test that Kafka errors don't fail the request (graceful degradation)."""
        request = LoanApplicationRequest(
            pan_number="ABCDE1234F",
            monthly_income_inr=Decimal("50000.00"),
            loan_amount_inr=Decimal("200000.00"),
            loan_type="PERSONAL",
        )

        with patch.object(application_service.repository, "save") as mock_save:
            mock_application = Application(
                id=uuid.uuid4(),
                pan_number=request.pan_number,
                monthly_income_inr=request.monthly_income_inr,
                loan_amount_inr=request.loan_amount_inr,
                loan_type=request.loan_type,
                status="PENDING",
            )
            mock_save.return_value = mock_application

            # Mock Kafka to raise error with topic and message
            mock_kafka_producer.send_and_wait.side_effect = KafkaPublishError(
                topic="loan_applications_submitted", message="Kafka broker unavailable"
            )

            # Should NOT raise exception (graceful degradation)
            response = await application_service.create_application(
                request=request,
                correlation_id="test-id",
            )

            # Verify application was still created
            assert response.application_id == mock_application.id
            assert response.status == "PENDING"

    @pytest.mark.asyncio
    async def test_create_application_generates_uuid(
        self, application_service, mock_kafka_producer
    ):
        """Test that application IDs are generated as UUIDs."""
        request = LoanApplicationRequest(
            pan_number="ABCDE1234F",
            monthly_income_inr=Decimal("50000.00"),
            loan_amount_inr=Decimal("200000.00"),
            loan_type="PERSONAL",
        )

        with patch.object(application_service.repository, "save") as mock_save:
            # Capture the application passed to save
            saved_app = None

            async def capture_save(app):
                nonlocal saved_app
                saved_app = app
                return app

            mock_save.side_effect = capture_save

            await application_service.create_application(
                request=request,
                correlation_id="test-id",
            )

            # Verify UUID was generated
            assert saved_app is not None
            assert isinstance(saved_app.id, uuid.UUID)
            assert saved_app.status == "PENDING"

    @pytest.mark.asyncio
    async def test_create_application_publishes_to_kafka_with_correct_data(
        self, application_service, mock_kafka_producer
    ):
        """Test that Kafka message contains correct application data."""
        request = LoanApplicationRequest(
            pan_number="ABCDE1234F",
            applicant_name="Test User",
            monthly_income_inr=Decimal("60000.00"),
            loan_amount_inr=Decimal("300000.00"),
            loan_type="HOME",
        )

        with patch.object(application_service.repository, "save") as mock_save:
            app_id = uuid.uuid4()
            mock_application = Application(
                id=app_id,
                pan_number=request.pan_number,
                applicant_name=request.applicant_name,
                monthly_income_inr=request.monthly_income_inr,
                loan_amount_inr=request.loan_amount_inr,
                loan_type=request.loan_type,
                status="PENDING",
            )
            mock_save.return_value = mock_application

            await application_service.create_application(
                request=request,
                correlation_id="test-correlation-id",
            )

            # Verify Kafka message structure
            mock_kafka_producer.send_and_wait.assert_awaited_once()
            call_args = mock_kafka_producer.send_and_wait.call_args

            assert call_args.kwargs["topic"] == "loan_applications_submitted"
            assert call_args.kwargs["key"] == str(app_id)

            message = call_args.kwargs["value"]
            assert message["application_id"] == str(app_id)
            assert message["pan_number"] == "ABCDE1234F"
            assert message["applicant_name"] == "Test User"
            assert message["correlation_id"] == "test-correlation-id"

    @pytest.mark.asyncio
    async def test_create_application_sets_pending_status(
        self, application_service, mock_kafka_producer
    ):
        """Test that new applications are created with PENDING status."""
        request = LoanApplicationRequest(
            pan_number="ABCDE1234F",
            monthly_income_inr=Decimal("50000.00"),
            loan_amount_inr=Decimal("200000.00"),
            loan_type="PERSONAL",
        )

        with patch.object(application_service.repository, "save") as mock_save:
            saved_app = None

            async def capture_save(app):
                nonlocal saved_app
                saved_app = app
                return app

            mock_save.side_effect = capture_save

            response = await application_service.create_application(
                request=request,
                correlation_id="test-id",
            )

            assert saved_app.status == "PENDING"
            assert response.status == "PENDING"


class TestApplicationServiceGetApplicationStatus:
    """Test suite for get_application_status method."""

    @pytest.mark.asyncio
    async def test_get_status_existing_application_pending(self, application_service):
        """Test retrieving status for existing PENDING application."""
        app_id = uuid.uuid4()
        mock_app = Application(
            id=app_id,
            pan_number="ABCDE1234F",
            monthly_income_inr=Decimal("50000.00"),
            loan_amount_inr=Decimal("200000.00"),
            status="PENDING",
        )

        with patch.object(application_service.repository, "find_by_id") as mock_find:
            mock_find.return_value = mock_app

            response = await application_service.get_application_status(app_id)

            mock_find.assert_awaited_once_with(app_id)
            assert response.application_id == app_id
            assert response.status == "PENDING"

    @pytest.mark.asyncio
    async def test_get_status_existing_application_pre_approved(self, application_service):
        """Test retrieving status for PRE_APPROVED application."""
        app_id = uuid.uuid4()
        mock_app = Application(
            id=app_id,
            pan_number="ABCDE1234F",
            monthly_income_inr=Decimal("80000.00"),
            loan_amount_inr=Decimal("500000.00"),
            status="PRE_APPROVED",
            cibil_score=750,
        )

        with patch.object(application_service.repository, "find_by_id") as mock_find:
            mock_find.return_value = mock_app

            response = await application_service.get_application_status(app_id)

            assert response.application_id == app_id
            assert response.status == "PRE_APPROVED"

    @pytest.mark.asyncio
    async def test_get_status_existing_application_rejected(self, application_service):
        """Test retrieving status for REJECTED application."""
        app_id = uuid.uuid4()
        mock_app = Application(
            id=app_id,
            pan_number="FGHIJ5678K",
            monthly_income_inr=Decimal("30000.00"),
            loan_amount_inr=Decimal("200000.00"),
            status="REJECTED",
            cibil_score=600,
        )

        with patch.object(application_service.repository, "find_by_id") as mock_find:
            mock_find.return_value = mock_app

            response = await application_service.get_application_status(app_id)

            assert response.application_id == app_id
            assert response.status == "REJECTED"

    @pytest.mark.asyncio
    async def test_get_status_existing_application_manual_review(self, application_service):
        """Test retrieving status for MANUAL_REVIEW application."""
        app_id = uuid.uuid4()
        mock_app = Application(
            id=app_id,
            pan_number="LMNOP9012Q",
            monthly_income_inr=Decimal("50000.00"),
            loan_amount_inr=Decimal("500000.00"),
            status="MANUAL_REVIEW",
            cibil_score=680,
        )

        with patch.object(application_service.repository, "find_by_id") as mock_find:
            mock_find.return_value = mock_app

            response = await application_service.get_application_status(app_id)

            assert response.application_id == app_id
            assert response.status == "MANUAL_REVIEW"

    @pytest.mark.asyncio
    async def test_get_status_non_existent_raises_not_found(self, application_service):
        """Test that non-existent application raises ApplicationNotFoundError."""
        non_existent_id = uuid.uuid4()

        with patch.object(application_service.repository, "find_by_id") as mock_find:
            mock_find.return_value = None

            with pytest.raises(ApplicationNotFoundError) as exc_info:
                await application_service.get_application_status(non_existent_id)

            assert str(non_existent_id) in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_get_status_calls_repository_with_correct_id(self, application_service):
        """Test that repository is called with correct application ID."""
        app_id = uuid.uuid4()
        mock_app = Application(
            id=app_id,
            pan_number="ABCDE1234F",
            monthly_income_inr=Decimal("50000.00"),
            loan_amount_inr=Decimal("200000.00"),
            status="PENDING",
        )

        with patch.object(application_service.repository, "find_by_id") as mock_find:
            mock_find.return_value = mock_app

            await application_service.get_application_status(app_id)

            mock_find.assert_awaited_once_with(app_id)


class TestApplicationServicePublishApplicationSubmitted:
    """Test suite for _publish_application_submitted private method."""

    @pytest.mark.asyncio
    async def test_publish_creates_correct_message_structure(
        self, application_service, mock_kafka_producer
    ):
        """Test that Kafka message has correct structure."""
        app_id = uuid.uuid4()
        application = Application(
            id=app_id,
            pan_number="ABCDE1234F",
            applicant_name="Test User",
            monthly_income_inr=Decimal("60000.00"),
            loan_amount_inr=Decimal("300000.00"),
            loan_type="HOME",
            status="PENDING",
        )

        await application_service._publish_application_submitted(
            application=application,
            correlation_id="test-correlation-id",
        )

        # Verify Kafka was called
        mock_kafka_producer.send_and_wait.assert_awaited_once()

        # Verify message structure
        call_args = mock_kafka_producer.send_and_wait.call_args
        message = call_args.kwargs["value"]

        assert "application_id" in message
        assert "pan_number" in message
        assert "applicant_name" in message
        assert "monthly_income_inr" in message
        assert "loan_amount_inr" in message
        assert "loan_type" in message
        assert "timestamp" in message
        assert "correlation_id" in message

    @pytest.mark.asyncio
    async def test_publish_uses_application_id_as_key(
        self, application_service, mock_kafka_producer
    ):
        """Test that application ID is used as message key for partitioning."""
        app_id = uuid.uuid4()
        application = Application(
            id=app_id,
            pan_number="ABCDE1234F",
            monthly_income_inr=Decimal("50000.00"),
            loan_amount_inr=Decimal("200000.00"),
            loan_type="PERSONAL",
            status="PENDING",
        )

        await application_service._publish_application_submitted(
            application=application,
            correlation_id="test-id",
        )

        call_args = mock_kafka_producer.send_and_wait.call_args
        assert call_args.kwargs["key"] == str(app_id)

    @pytest.mark.asyncio
    async def test_publish_to_correct_topic(self, application_service, mock_kafka_producer):
        """Test that message is published to correct Kafka topic."""
        application = Application(
            id=uuid.uuid4(),
            pan_number="ABCDE1234F",
            monthly_income_inr=Decimal("50000.00"),
            loan_amount_inr=Decimal("200000.00"),
            loan_type="PERSONAL",
            status="PENDING",
        )

        await application_service._publish_application_submitted(
            application=application,
            correlation_id="test-id",
        )

        call_args = mock_kafka_producer.send_and_wait.call_args
        assert call_args.kwargs["topic"] == "loan_applications_submitted"

    @pytest.mark.asyncio
    async def test_publish_includes_correlation_id(self, application_service, mock_kafka_producer):
        """Test that correlation ID is included in message for tracing."""
        application = Application(
            id=uuid.uuid4(),
            pan_number="ABCDE1234F",
            monthly_income_inr=Decimal("50000.00"),
            loan_amount_inr=Decimal("200000.00"),
            loan_type="PERSONAL",
            status="PENDING",
        )

        correlation_id = "unique-trace-id-12345"
        await application_service._publish_application_submitted(
            application=application,
            correlation_id=correlation_id,
        )

        call_args = mock_kafka_producer.send_and_wait.call_args
        message = call_args.kwargs["value"]
        assert message["correlation_id"] == correlation_id

    @pytest.mark.asyncio
    async def test_publish_with_optional_applicant_name_none(
        self, application_service, mock_kafka_producer
    ):
        """Test publishing message with optional applicant_name set to None."""
        application = Application(
            id=uuid.uuid4(),
            pan_number="FGHIJ5678K",
            applicant_name=None,  # Optional
            monthly_income_inr=Decimal("50000.00"),
            loan_amount_inr=Decimal("200000.00"),
            loan_type="AUTO",  # Required
            status="PENDING",
        )

        await application_service._publish_application_submitted(
            application=application,
            correlation_id="test-id",
        )

        # Should not raise exception
        mock_kafka_producer.send_and_wait.assert_awaited_once()

        call_args = mock_kafka_producer.send_and_wait.call_args
        message = call_args.kwargs["value"]
        assert message["applicant_name"] is None
        assert message["loan_type"] == "AUTO"

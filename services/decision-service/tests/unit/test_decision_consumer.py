"""Unit tests for decision consumer."""

from datetime import datetime
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from app.consumers.decision_consumer import DecisionConsumer


class TestDecisionConsumerStartStop:
    """Test suite for consumer lifecycle management."""

    @pytest.mark.asyncio
    async def test_start_consumer_success(self):
        """Test successful consumer and producer startup."""
        consumer = DecisionConsumer()

        with patch("app.consumers.decision_consumer.AIOKafkaConsumer") as mock_consumer_cls:
            with patch("app.consumers.decision_consumer.AIOKafkaProducer") as mock_producer_cls:
                mock_consumer = AsyncMock()
                mock_producer = AsyncMock()
                mock_consumer_cls.return_value = mock_consumer
                mock_producer_cls.return_value = mock_producer

                await consumer.start()

                assert consumer.running is True
                mock_consumer.start.assert_called_once()
                mock_producer.start.assert_called_once()

    @pytest.mark.asyncio
    async def test_stop_consumer_success(self):
        """Test successful consumer and producer shutdown."""
        consumer = DecisionConsumer()
        consumer.consumer = AsyncMock()
        consumer.producer = AsyncMock()
        consumer.running = True

        await consumer.stop()

        assert consumer.running is False
        consumer.consumer.stop.assert_called_once()
        consumer.producer.stop.assert_called_once()

    @pytest.mark.asyncio
    async def test_start_consumer_failure_raises_exception(self):
        """Test that consumer startup failure raises exception."""
        consumer = DecisionConsumer()

        with patch("app.consumers.decision_consumer.AIOKafkaConsumer") as mock_consumer_cls:
            mock_consumer_cls.return_value.start.side_effect = Exception("Kafka unavailable")

            with pytest.raises(Exception, match="Kafka unavailable"):
                await consumer.start()


class TestDecisionConsumerProcessMessage:
    """Test suite for message processing logic."""

    @pytest.mark.asyncio
    async def test_process_message_preapproved_success(self):
        """Test successful message processing resulting in PRE_APPROVED."""
        consumer = DecisionConsumer()
        consumer.producer = AsyncMock()

        app_id = uuid4()
        message = {
            "application_id": str(app_id),
            "cibil_score": 750,
            "pan_number": "ABCDE1234F",
            "monthly_income_inr": "50000.00",
            "loan_amount_inr": "200000.00",
            "loan_type": "PERSONAL",
            "timestamp": datetime.now().isoformat(),
            "correlation_id": str(uuid4()),
        }

        with patch("app.consumers.decision_consumer.async_session_maker") as mock_session:
            with patch("app.consumers.decision_consumer.make_decision") as mock_decision:
                mock_decision.return_value = "PRE_APPROVED"

                # Mock repository
                mock_repo = MagicMock()
                mock_repo.update_status = AsyncMock(return_value=True)

                # Mock session context manager
                mock_session_instance = AsyncMock()
                mock_session_instance.__aenter__ = AsyncMock(return_value=mock_session_instance)
                mock_session_instance.__aexit__ = AsyncMock(return_value=None)
                mock_session.return_value = mock_session_instance

                with patch(
                    "app.consumers.decision_consumer.ApplicationRepository"
                ) as mock_repo_cls:
                    mock_repo_cls.return_value = mock_repo

                    await consumer.process_message(message)

                    # Verify decision was made
                    mock_decision.assert_called_once_with(
                        cibil_score=750,
                        monthly_income=Decimal("50000.00"),
                        loan_amount=Decimal("200000.00"),
                    )

                    # Verify status was updated
                    mock_repo.update_status.assert_called_once_with(
                        application_id=app_id,
                        status="PRE_APPROVED",
                        cibil_score=750,
                    )

    @pytest.mark.asyncio
    async def test_process_message_rejected_success(self):
        """Test successful message processing resulting in REJECTED."""
        consumer = DecisionConsumer()
        consumer.producer = AsyncMock()

        app_id = uuid4()
        message = {
            "application_id": str(app_id),
            "cibil_score": 600,
            "pan_number": "FGHIJ5678K",
            "monthly_income_inr": "30000.00",
            "loan_amount_inr": "200000.00",
            "loan_type": "PERSONAL",
            "timestamp": datetime.now().isoformat(),
            "correlation_id": str(uuid4()),
        }

        with patch("app.consumers.decision_consumer.async_session_maker") as mock_session:
            with patch("app.consumers.decision_consumer.make_decision") as mock_decision:
                mock_decision.return_value = "REJECTED"

                # Mock repository
                mock_repo = MagicMock()
                mock_repo.update_status = AsyncMock(return_value=True)

                # Mock session
                mock_session_instance = AsyncMock()
                mock_session_instance.__aenter__ = AsyncMock(return_value=mock_session_instance)
                mock_session_instance.__aexit__ = AsyncMock(return_value=None)
                mock_session.return_value = mock_session_instance

                with patch(
                    "app.consumers.decision_consumer.ApplicationRepository"
                ) as mock_repo_cls:
                    mock_repo_cls.return_value = mock_repo

                    await consumer.process_message(message)

                    # Verify status was updated to REJECTED
                    mock_repo.update_status.assert_called_once_with(
                        application_id=app_id,
                        status="REJECTED",
                        cibil_score=600,
                    )

    @pytest.mark.asyncio
    async def test_process_message_manual_review(self):
        """Test message processing resulting in MANUAL_REVIEW."""
        consumer = DecisionConsumer()
        consumer.producer = AsyncMock()

        app_id = uuid4()
        message = {
            "application_id": str(app_id),
            "cibil_score": 700,
            "pan_number": "ABCDE1234F",
            "monthly_income_inr": "35000.00",
            "loan_amount_inr": "200000.00",
            "loan_type": "HOME",
            "timestamp": datetime.now().isoformat(),
            "correlation_id": str(uuid4()),
        }

        with patch("app.consumers.decision_consumer.async_session_maker") as mock_session:
            with patch("app.consumers.decision_consumer.make_decision") as mock_decision:
                mock_decision.return_value = "MANUAL_REVIEW"

                mock_repo = MagicMock()
                mock_repo.update_status = AsyncMock(return_value=True)

                mock_session_instance = AsyncMock()
                mock_session_instance.__aenter__ = AsyncMock(return_value=mock_session_instance)
                mock_session_instance.__aexit__ = AsyncMock(return_value=None)
                mock_session.return_value = mock_session_instance

                with patch(
                    "app.consumers.decision_consumer.ApplicationRepository"
                ) as mock_repo_cls:
                    mock_repo_cls.return_value = mock_repo

                    await consumer.process_message(message)

                    mock_repo.update_status.assert_called_once_with(
                        application_id=app_id,
                        status="MANUAL_REVIEW",
                        cibil_score=700,
                    )

    @pytest.mark.asyncio
    async def test_process_message_idempotency_already_processed(self):
        """Test message processing with idempotency check (already processed)."""
        consumer = DecisionConsumer()
        consumer.producer = AsyncMock()

        app_id = uuid4()
        message = {
            "application_id": str(app_id),
            "cibil_score": 750,
            "pan_number": "ABCDE1234F",
            "monthly_income_inr": "50000.00",
            "loan_amount_inr": "200000.00",
            "loan_type": "PERSONAL",
            "timestamp": datetime.now().isoformat(),
            "correlation_id": str(uuid4()),
        }

        with patch("app.consumers.decision_consumer.async_session_maker") as mock_session:
            with patch("app.consumers.decision_consumer.make_decision") as mock_decision:
                mock_decision.return_value = "PRE_APPROVED"

                # Mock repository to return False (already processed)
                mock_repo = MagicMock()
                mock_repo.update_status = AsyncMock(return_value=False)

                mock_session_instance = AsyncMock()
                mock_session_instance.__aenter__ = AsyncMock(return_value=mock_session_instance)
                mock_session_instance.__aexit__ = AsyncMock(return_value=None)
                mock_session.return_value = mock_session_instance

                with patch(
                    "app.consumers.decision_consumer.ApplicationRepository"
                ) as mock_repo_cls:
                    mock_repo_cls.return_value = mock_repo

                    await consumer.process_message(message)

                    # Verify decision was still made
                    mock_decision.assert_called_once()

                    # Verify update was attempted
                    mock_repo.update_status.assert_called_once()

    @pytest.mark.asyncio
    async def test_process_message_invalid_pydantic_validation(self):
        """Test message processing with invalid message format."""
        consumer = DecisionConsumer()
        consumer.producer = AsyncMock()

        # Missing required field (cibil_score)
        invalid_message = {
            "application_id": str(uuid4()),
            "pan_number": "ABCDE1234F",
            "monthly_income_inr": "50000.00",
            "loan_amount_inr": "200000.00",
            "loan_type": "PERSONAL",
        }

        await consumer.process_message(invalid_message)

        # Verify DLQ was called
        consumer.producer.send.assert_called_once()
        call_args = consumer.producer.send.call_args
        assert "loan_processing_dlq" in str(call_args)

    @pytest.mark.asyncio
    async def test_process_message_database_error(self):
        """Test message processing when database update fails."""
        consumer = DecisionConsumer()
        consumer.producer = AsyncMock()

        app_id = uuid4()
        message = {
            "application_id": str(app_id),
            "cibil_score": 750,
            "pan_number": "ABCDE1234F",
            "monthly_income_inr": "50000.00",
            "loan_amount_inr": "200000.00",
            "loan_type": "PERSONAL",
            "timestamp": datetime.now().isoformat(),
            "correlation_id": str(uuid4()),
        }

        with patch("app.consumers.decision_consumer.async_session_maker") as mock_session:
            with patch("app.consumers.decision_consumer.make_decision") as mock_decision:
                mock_decision.return_value = "PRE_APPROVED"

                # Mock repository to raise database error
                mock_repo = MagicMock()
                mock_repo.update_status = AsyncMock(
                    side_effect=Exception("Database connection failed")
                )

                mock_session_instance = AsyncMock()
                mock_session_instance.__aenter__ = AsyncMock(return_value=mock_session_instance)
                mock_session_instance.__aexit__ = AsyncMock(return_value=None)
                mock_session.return_value = mock_session_instance

                with patch(
                    "app.consumers.decision_consumer.ApplicationRepository"
                ) as mock_repo_cls:
                    mock_repo_cls.return_value = mock_repo

                    await consumer.process_message(message)

                    # Verify DLQ was called
                    assert consumer.producer.send.call_count == 1


class TestDecisionConsumerDLQ:
    """Test suite for Dead Letter Queue functionality."""

    @pytest.mark.asyncio
    async def test_publish_to_dlq_success(self):
        """Test successful DLQ publishing."""
        consumer = DecisionConsumer()
        consumer.producer = AsyncMock()

        message = {"test": "data"}
        error = "Test error message"

        await consumer._publish_to_dlq(message, error)

        consumer.producer.send.assert_called_once()
        call_args = consumer.producer.send.call_args
        assert "loan_processing_dlq" in str(call_args)
        assert call_args[1]["value"]["error"] == error
        assert call_args[1]["value"]["service"] == "decision-service"

    @pytest.mark.asyncio
    async def test_publish_to_dlq_failure_logs_error(self):
        """Test that DLQ publishing failure is logged."""
        consumer = DecisionConsumer()
        consumer.producer = AsyncMock()
        consumer.producer.send.side_effect = Exception("DLQ unavailable")

        message = {"test": "data"}
        error = "Original error"

        # Should not raise exception
        await consumer._publish_to_dlq(message, error)

        consumer.producer.send.assert_called_once()


class TestDecisionConsumerConsumeLoop:
    """Test suite for consumer main loop."""

    @pytest.mark.asyncio
    async def test_consume_loop_not_started_raises_error(self):
        """Test that consume loop fails if consumer not started."""
        consumer = DecisionConsumer()
        consumer.consumer = None

        with pytest.raises(RuntimeError, match="Consumer not started"):
            await consumer.consume()

    @pytest.mark.asyncio
    async def test_consume_loop_processes_messages(self):
        """Test that consume loop processes messages correctly."""
        consumer = DecisionConsumer()
        consumer.producer = AsyncMock()

        # Mock messages
        mock_message1 = MagicMock()
        mock_message1.value = {
            "application_id": str(uuid4()),
            "cibil_score": 750,
            "pan_number": "ABCDE1234F",
            "monthly_income_inr": "50000.00",
            "loan_amount_inr": "200000.00",
            "loan_type": "PERSONAL",
            "timestamp": datetime.now().isoformat(),
            "correlation_id": str(uuid4()),
        }

        mock_message2 = MagicMock()
        mock_message2.value = {
            "application_id": str(uuid4()),
            "cibil_score": 600,
            "pan_number": "FGHIJ5678K",
            "monthly_income_inr": "30000.00",
            "loan_amount_inr": "150000.00",
            "loan_type": "AUTO",
            "timestamp": datetime.now().isoformat(),
            "correlation_id": str(uuid4()),
        }

        # Mock consumer to return messages then stop
        async def async_iterator():
            for msg in [mock_message1, mock_message2]:
                yield msg

        mock_consumer = MagicMock()
        mock_consumer.__aiter__ = lambda self: async_iterator()
        mock_consumer.commit = AsyncMock()  # commit() is async
        consumer.consumer = mock_consumer

        with patch("app.consumers.decision_consumer.async_session_maker") as mock_session:
            with patch("app.consumers.decision_consumer.make_decision") as mock_decision:
                with patch("app.consumers.decision_consumer.shutdown_event") as mock_shutdown:
                    mock_decision.return_value = "PRE_APPROVED"
                    mock_shutdown.is_set.side_effect = [False, False, True]

                    # Mock repository
                    mock_repo = MagicMock()
                    mock_repo.update_status = AsyncMock(return_value=True)

                    mock_session_instance = AsyncMock()
                    mock_session_instance.__aenter__ = AsyncMock(return_value=mock_session_instance)
                    mock_session_instance.__aexit__ = AsyncMock(return_value=None)
                    mock_session.return_value = mock_session_instance

                    with patch(
                        "app.consumers.decision_consumer.ApplicationRepository"
                    ) as mock_repo_cls:
                        mock_repo_cls.return_value = mock_repo

                        await consumer.consume()

                        # Verify both messages were processed
                        assert mock_repo.update_status.call_count == 2

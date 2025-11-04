"""Unit tests for credit consumer."""

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from app.consumers.credit_consumer import CreditConsumer


class TestCreditConsumerStartStop:
    """Test suite for consumer lifecycle management."""

    @pytest.mark.asyncio
    async def test_start_consumer_success(self):
        """Test successful consumer and producer startup."""
        consumer = CreditConsumer()

        with patch("app.consumers.credit_consumer.AIOKafkaConsumer") as mock_consumer_cls:
            with patch("app.consumers.credit_consumer.AIOKafkaProducer") as mock_producer_cls:
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
        consumer = CreditConsumer()
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
        consumer = CreditConsumer()

        with patch("app.consumers.credit_consumer.AIOKafkaConsumer") as mock_consumer_cls:
            mock_consumer_cls.return_value.start.side_effect = Exception("Kafka unavailable")

            with pytest.raises(Exception, match="Kafka unavailable"):
                await consumer.start()


class TestCreditConsumerProcessMessage:
    """Test suite for message processing logic."""

    @pytest.mark.asyncio
    async def test_process_message_success(self):
        """Test successful message processing and publishing."""
        consumer = CreditConsumer()
        consumer.producer = AsyncMock()

        message = {
            "application_id": str(uuid4()),
            "pan_number": "ABCDE1234F",
            "applicant_name": "John Doe",
            "monthly_income_inr": "50000.00",
            "loan_amount_inr": "200000.00",
            "loan_type": "PERSONAL",
            "timestamp": datetime.now().isoformat(),
            "correlation_id": str(uuid4()),
        }

        with patch("app.consumers.credit_consumer.calculate_cibil_score") as mock_calc:
            mock_calc.return_value = 750

            await consumer.process_message(message)

            # Verify CIBIL calculation was called
            mock_calc.assert_called_once()

            # Verify message was published
            consumer.producer.send.assert_called_once()
            call_args = consumer.producer.send.call_args
            assert call_args.kwargs["value"]["cibil_score"] == 750

    @pytest.mark.asyncio
    async def test_process_message_with_special_pan_abcde(self):
        """Test message processing with special PAN ABCDE1234F."""
        consumer = CreditConsumer()
        consumer.producer = AsyncMock()

        message = {
            "application_id": str(uuid4()),
            "pan_number": "ABCDE1234F",
            "applicant_name": "Test User",
            "monthly_income_inr": "60000.00",
            "loan_amount_inr": "300000.00",
            "loan_type": "HOME",
            "timestamp": datetime.now().isoformat(),
            "correlation_id": str(uuid4()),
        }

        with patch("app.consumers.credit_consumer.calculate_cibil_score") as mock_calc:
            mock_calc.return_value = 790  # Special PAN returns 790

            await consumer.process_message(message)

            mock_calc.assert_called_once()
            consumer.producer.send.assert_called_once()

    @pytest.mark.asyncio
    async def test_process_message_invalid_pydantic_validation(self):
        """Test message processing with invalid message format."""
        consumer = CreditConsumer()
        consumer.producer = AsyncMock()

        # Missing required field (pan_number)
        invalid_message = {
            "application_id": str(uuid4()),
            "monthly_income_inr": "50000.00",
            "loan_amount_inr": "200000.00",
            "loan_type": "PERSONAL",
            "timestamp": datetime.now().isoformat(),
            "correlation_id": str(uuid4()),
        }

        await consumer.process_message(invalid_message)

        # Verify DLQ was called (message processing failed)
        consumer.producer.send.assert_called_once()
        call_args = consumer.producer.send.call_args
        assert "loan_processing_dlq" in str(call_args)

    @pytest.mark.asyncio
    async def test_process_message_cibil_calculation_fails(self):
        """Test message processing when CIBIL calculation fails."""
        consumer = CreditConsumer()
        consumer.producer = AsyncMock()

        message = {
            "application_id": str(uuid4()),
            "pan_number": "FGHIJ5678K",
            "monthly_income_inr": "40000.00",
            "loan_amount_inr": "150000.00",
            "loan_type": "AUTO",
            "timestamp": datetime.now().isoformat(),
            "correlation_id": str(uuid4()),
        }

        with patch("app.consumers.credit_consumer.calculate_cibil_score") as mock_calc:
            mock_calc.side_effect = Exception("CIBIL service unavailable")

            await consumer.process_message(message)

            # Verify DLQ was called
            assert consumer.producer.send.call_count == 1
            call_args = consumer.producer.send.call_args
            assert "loan_processing_dlq" in str(call_args)

    @pytest.mark.asyncio
    async def test_process_message_kafka_publish_fails(self):
        """Test message processing when Kafka publish fails."""
        consumer = CreditConsumer()
        consumer.producer = AsyncMock()
        consumer.producer.send.side_effect = Exception("Kafka broker unavailable")

        message = {
            "application_id": str(uuid4()),
            "pan_number": "ABCDE1234F",
            "monthly_income_inr": "50000.00",
            "loan_amount_inr": "200000.00",
            "loan_type": "PERSONAL",
            "timestamp": datetime.now().isoformat(),
            "correlation_id": str(uuid4()),
        }

        with patch("app.consumers.credit_consumer.calculate_cibil_score") as mock_calc:
            mock_calc.return_value = 750

            await consumer.process_message(message)

            # Verify multiple send attempts (original + DLQ)
            assert consumer.producer.send.call_count >= 1


class TestCreditConsumerDLQ:
    """Test suite for Dead Letter Queue functionality."""

    @pytest.mark.asyncio
    async def test_publish_to_dlq_success(self):
        """Test successful DLQ publishing."""
        consumer = CreditConsumer()
        consumer.producer = AsyncMock()

        message = {"test": "data"}
        error = "Test error message"

        await consumer._publish_to_dlq(message, error)

        consumer.producer.send.assert_called_once()
        call_args = consumer.producer.send.call_args
        assert "loan_processing_dlq" in str(call_args)
        assert call_args[1]["value"]["error"] == error
        assert call_args[1]["value"]["service"] == "credit-service"

    @pytest.mark.asyncio
    async def test_publish_to_dlq_failure_logs_error(self):
        """Test that DLQ publishing failure is logged."""
        consumer = CreditConsumer()
        consumer.producer = AsyncMock()
        consumer.producer.send.side_effect = Exception("DLQ unavailable")

        message = {"test": "data"}
        error = "Original error"

        # Should not raise exception
        await consumer._publish_to_dlq(message, error)

        consumer.producer.send.assert_called_once()


class TestCreditConsumerConsumeLoop:
    """Test suite for consumer main loop."""

    @pytest.mark.asyncio
    async def test_consume_loop_not_started_raises_error(self):
        """Test that consume loop fails if consumer not started."""
        consumer = CreditConsumer()
        consumer.consumer = None

        with pytest.raises(RuntimeError, match="Consumer not started"):
            await consumer.consume()

    @pytest.mark.asyncio
    async def test_consume_loop_processes_messages(self):
        """Test that consume loop processes messages correctly."""
        consumer = CreditConsumer()

        # Mock messages
        mock_message1 = MagicMock()
        mock_message1.value = {
            "application_id": str(uuid4()),
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
            "pan_number": "FGHIJ5678K",
            "monthly_income_inr": "40000.00",
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
        mock_consumer.commit = AsyncMock()  # Make commit awaitable
        consumer.consumer = mock_consumer
        consumer.producer = AsyncMock()

        with patch("app.consumers.credit_consumer.calculate_cibil_score") as mock_calc:
            with patch("app.consumers.credit_consumer.shutdown_event") as mock_shutdown:
                mock_calc.return_value = 750
                mock_shutdown.is_set.side_effect = [
                    False,
                    False,
                    True,
                ]  # Process 2 messages then stop

                await consumer.consume()

                # Verify both messages were published
                assert consumer.producer.send.call_count == 2

    @pytest.mark.asyncio
    async def test_consume_loop_with_shutdown_signal(self):
        """Test that consume loop stops when shutdown signal is set."""
        consumer = CreditConsumer()

        # Mock message
        mock_message = MagicMock()
        mock_message.value = {
            "application_id": str(uuid4()),
            "pan_number": "ABCDE1234F",
            "monthly_income_inr": "50000.00",
            "loan_amount_inr": "200000.00",
            "loan_type": "PERSONAL",
            "timestamp": datetime.now().isoformat(),
            "correlation_id": str(uuid4()),
        }

        # Mock consumer that yields one message then shutdown
        async def async_iterator():
            yield mock_message
            # Shutdown event will be set before next iteration

        mock_consumer = MagicMock()
        mock_consumer.__aiter__ = lambda self: async_iterator()
        mock_consumer.commit = AsyncMock()
        consumer.consumer = mock_consumer
        consumer.producer = AsyncMock()

        with patch("app.consumers.credit_consumer.calculate_cibil_score") as mock_calc:
            with patch("app.consumers.credit_consumer.shutdown_event") as mock_shutdown:
                mock_calc.return_value = 750
                # First check False (process message), second check True (stop loop)
                mock_shutdown.is_set.side_effect = [False, True]

                await consumer.consume()

                # Verify message was processed before shutdown
                assert consumer.producer.send.call_count == 1

    @pytest.mark.asyncio
    async def test_consume_loop_kafka_error_raised(self):
        """Test that KafkaError in consume loop is raised."""
        from aiokafka.errors import KafkaError

        consumer = CreditConsumer()

        # Mock consumer that raises KafkaError
        async def async_iterator():
            raise KafkaError("Kafka broker unavailable")
            yield  # Never reached

        mock_consumer = MagicMock()
        mock_consumer.__aiter__ = lambda self: async_iterator()
        consumer.consumer = mock_consumer

        with pytest.raises(KafkaError, match="Kafka broker unavailable"):
            await consumer.consume()

    @pytest.mark.asyncio
    async def test_consume_loop_general_exception_raised(self):
        """Test that general exceptions in consume loop are raised."""
        consumer = CreditConsumer()

        # Mock consumer that raises generic exception
        async def async_iterator():
            raise RuntimeError("Unexpected error in consumer")
            yield  # Never reached

        mock_consumer = MagicMock()
        mock_consumer.__aiter__ = lambda self: async_iterator()
        consumer.consumer = mock_consumer

        with pytest.raises(RuntimeError, match="Unexpected error in consumer"):
            await consumer.consume()


class TestCreditConsumerRun:
    """Test suite for consumer run method."""

    @pytest.mark.asyncio
    async def test_run_executes_start_consume_stop_sequence(self):
        """Test that run() properly executes start, consume, and stop."""
        consumer = CreditConsumer()
        consumer.start = AsyncMock()
        consumer.consume = AsyncMock()
        consumer.stop = AsyncMock()

        await consumer.run()

        # Verify sequence
        consumer.start.assert_called_once()
        consumer.consume.assert_called_once()
        consumer.stop.assert_called_once()

    @pytest.mark.asyncio
    async def test_run_calls_stop_even_when_consume_fails(self):
        """Test that stop() is called even if consume() raises exception."""
        consumer = CreditConsumer()
        consumer.start = AsyncMock()
        consumer.consume = AsyncMock(side_effect=Exception("Consumer failed"))
        consumer.stop = AsyncMock()

        with pytest.raises(Exception, match="Consumer failed"):
            await consumer.run()

        # Verify stop was still called (finally block)
        consumer.stop.assert_called_once()


class TestShutdownSignalHandler:
    """Test suite for signal handling."""

    def test_handle_shutdown_signal_sets_event(self):
        """Test that signal handler sets shutdown event."""
        from app.consumers.credit_consumer import handle_shutdown_signal, shutdown_event

        # Reset event before test
        shutdown_event.clear()

        # Call signal handler
        handle_shutdown_signal(15, None)  # SIGTERM

        # Verify event is set
        assert shutdown_event.is_set()

    def test_handle_shutdown_signal_with_sigint(self):
        """Test signal handler with SIGINT."""
        import signal

        from app.consumers.credit_consumer import handle_shutdown_signal, shutdown_event

        shutdown_event.clear()

        handle_shutdown_signal(signal.SIGINT, None)

        assert shutdown_event.is_set()


class TestMainEntryPoint:
    """Test suite for main() entry point."""

    @pytest.mark.asyncio
    async def test_main_runs_consumer_successfully(self):
        """Test main() function runs consumer successfully."""
        from app.consumers.credit_consumer import main

        with patch("app.consumers.credit_consumer.CreditConsumer") as mock_consumer_cls:
            with patch("app.consumers.credit_consumer.signal.signal") as mock_signal:
                mock_consumer = MagicMock()
                mock_consumer.run = AsyncMock()
                mock_consumer_cls.return_value = mock_consumer

                await main()

                # Verify signal handlers registered
                assert mock_signal.call_count == 2  # SIGTERM and SIGINT

                # Verify consumer ran
                mock_consumer.run.assert_called_once()

    @pytest.mark.asyncio
    async def test_main_handles_keyboard_interrupt(self):
        """Test main() handles KeyboardInterrupt gracefully."""
        from app.consumers.credit_consumer import main

        with patch("app.consumers.credit_consumer.CreditConsumer") as mock_consumer_cls:
            with patch("app.consumers.credit_consumer.signal.signal"):
                mock_consumer = MagicMock()
                mock_consumer.run = AsyncMock(side_effect=KeyboardInterrupt())
                mock_consumer_cls.return_value = mock_consumer

                # Should not raise exception
                await main()

                # Verify consumer.run was called
                mock_consumer.run.assert_called_once()

    @pytest.mark.asyncio
    async def test_main_handles_general_exception(self):
        """Test main() handles general exceptions and exits with code 1."""
        from app.consumers.credit_consumer import main

        with patch("app.consumers.credit_consumer.CreditConsumer") as mock_consumer_cls:
            with patch("app.consumers.credit_consumer.signal.signal"):
                with patch("app.consumers.credit_consumer.sys.exit") as mock_exit:
                    mock_consumer = MagicMock()
                    mock_consumer.run = AsyncMock(side_effect=Exception("Fatal error"))
                    mock_consumer_cls.return_value = mock_consumer

                    await main()

                    # Verify sys.exit(1) was called
                    mock_exit.assert_called_once_with(1)

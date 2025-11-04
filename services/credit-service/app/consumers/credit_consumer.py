"""Kafka consumer for processing loan applications and calculating CIBIL scores."""

import asyncio
import json
import signal
import sys
from typing import Any

from aiokafka import AIOKafkaConsumer, AIOKafkaProducer
from aiokafka.errors import KafkaError
from shared.core.config import settings
from shared.core.logging import get_logger, mask_pan
from shared.schemas.kafka_messages import CreditReportMessage, LoanApplicationMessage

from app.services.credit_service import calculate_cibil_score

logger = get_logger(__name__)

# Graceful shutdown flag
shutdown_event = asyncio.Event()


class CreditConsumer:
    """Kafka consumer for credit score calculation."""

    def __init__(self) -> None:
        """Initialize the credit consumer."""
        self.consumer: AIOKafkaConsumer | None = None
        self.producer: AIOKafkaProducer | None = None
        self.running = False

    async def start(self) -> None:
        """Start the Kafka consumer and producer."""
        try:
            # Initialize consumer
            self.consumer = AIOKafkaConsumer(
                settings.kafka_topic_applications,
                bootstrap_servers=settings.kafka_bootstrap_servers,
                group_id="credit-service-group",
                auto_offset_reset="earliest",
                enable_auto_commit=False,  # Manual commit for reliability
                value_deserializer=lambda m: json.loads(m.decode("utf-8")),
            )

            # Initialize producer for publishing results
            self.producer = AIOKafkaProducer(
                bootstrap_servers=settings.kafka_bootstrap_servers,
                value_serializer=lambda v: json.dumps(v, default=str).encode("utf-8"),
            )

            await self.consumer.start()
            await self.producer.start()

            logger.info(
                "credit_consumer_started",
                topic=settings.kafka_topic_applications,
                group_id="credit-service-group",
            )
            self.running = True

        except Exception as e:
            logger.error("credit_consumer_startup_failed", error=str(e), exc_info=True)
            raise

    async def stop(self) -> None:
        """Stop the Kafka consumer and producer."""
        self.running = False

        if self.consumer:
            await self.consumer.stop()
            logger.info("credit_consumer_stopped")

        if self.producer:
            await self.producer.stop()
            logger.info("credit_producer_stopped")

    async def _publish_to_dlq(self, message: dict[str, Any], error: str) -> None:
        """
        Publish failed message to Dead Letter Queue.

        Args:
            message: Original message that failed processing
            error: Error message describing the failure
        """
        try:
            dlq_message = {
                "original_message": message,
                "error": error,
                "service": "credit-service",
                "timestamp": json.dumps({"iso": "now"}, default=str),
            }

            await self.producer.send(
                settings.kafka_topic_dlq,
                value=dlq_message,
            )

            logger.info(
                "message_sent_to_dlq",
                topic=settings.kafka_topic_dlq,
                error=error,
            )

        except Exception as dlq_error:
            logger.error(
                "failed_to_publish_to_dlq",
                error=str(dlq_error),
                original_error=error,
                exc_info=True,
            )

    async def process_message(self, message: dict[str, Any]) -> None:
        """
        Process a single loan application message.

        Args:
            message: Loan application message from Kafka
        """
        try:
            # Validate message with Pydantic
            app_message = LoanApplicationMessage(**message)

            logger.info(
                "processing_application",
                application_id=str(app_message.application_id),
                pan=mask_pan(app_message.pan_number),
                loan_type=app_message.loan_type,
            )

            # Calculate CIBIL score
            cibil_score = calculate_cibil_score(
                pan_number=app_message.pan_number,
                monthly_income=app_message.monthly_income_inr,
                loan_type=app_message.loan_type,
            )

            logger.info(
                "cibil_score_calculated",
                application_id=str(app_message.application_id),
                cibil_score=cibil_score,
            )

            # Create credit report message
            credit_report = CreditReportMessage(
                application_id=app_message.application_id,
                cibil_score=cibil_score,
                pan_number=app_message.pan_number,
                monthly_income_inr=app_message.monthly_income_inr,
                loan_amount_inr=app_message.loan_amount_inr,
                loan_type=app_message.loan_type,
                timestamp=app_message.timestamp,
                correlation_id=app_message.correlation_id,
            )

            # Publish to credit_reports_generated topic
            await self.producer.send(
                settings.kafka_topic_credit_reports,
                value=credit_report.model_dump(mode="json"),
            )

            logger.info(
                "credit_report_published",
                application_id=str(app_message.application_id),
                topic=settings.kafka_topic_credit_reports,
            )

        except Exception as e:
            logger.error(
                "message_processing_failed",
                error=str(e),
                message=message,
                exc_info=True,
            )
            # Publish to Dead Letter Queue (DLQ) for manual investigation
            await self._publish_to_dlq(message, error=str(e))

    async def consume(self) -> None:
        """Main consume loop."""
        if not self.consumer:
            raise RuntimeError("Consumer not started. Call start() first.")

        try:
            async for msg in self.consumer:
                # Check for shutdown signal
                if shutdown_event.is_set():
                    logger.info("shutdown_signal_received_stopping_consumption")
                    break

                await self.process_message(msg.value)

                # Manual commit after successful processing
                await self.consumer.commit()

        except KafkaError as e:
            logger.error("kafka_error", error=str(e), exc_info=True)
            raise
        except Exception as e:
            logger.error("consume_loop_error", error=str(e), exc_info=True)
            raise

    async def run(self) -> None:
        """Run the consumer (start, consume, stop)."""
        try:
            await self.start()
            await self.consume()
        finally:
            await self.stop()


def handle_shutdown_signal(sig: int, frame: Any) -> None:
    """Handle shutdown signals (SIGTERM, SIGINT)."""
    logger.info("shutdown_signal_received", signal=sig)
    shutdown_event.set()


async def main() -> None:
    """Main entry point for credit-service consumer."""
    # Register signal handlers
    signal.signal(signal.SIGTERM, handle_shutdown_signal)
    signal.signal(signal.SIGINT, handle_shutdown_signal)

    consumer = CreditConsumer()

    try:
        await consumer.run()
    except KeyboardInterrupt:
        logger.info("keyboard_interrupt_received")
    except Exception as e:
        logger.error("credit_service_failed", error=str(e), exc_info=True)
        sys.exit(1)
    finally:
        logger.info("credit_service_shutdown_complete")


if __name__ == "__main__":
    # Configure logging
    from shared.core.logging import configure_logging

    configure_logging()

    # Run the consumer
    asyncio.run(main())

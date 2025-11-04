"""Kafka consumer for processing credit reports and making loan decisions."""

import asyncio
import json
import signal
import sys
from typing import Any

from aiokafka import AIOKafkaConsumer, AIOKafkaProducer
from aiokafka.errors import KafkaError
from pybreaker import CircuitBreaker, CircuitBreakerError
from shared.core.config import settings
from shared.core.database import async_session_maker
from shared.core.logging import get_logger, mask_pan
from shared.schemas.kafka_messages import CreditReportMessage

from app.repositories.application_repository import ApplicationRepository
from app.services.decision_service import make_decision

logger = get_logger(__name__)

# Graceful shutdown flag
shutdown_event = asyncio.Event()

# Circuit breaker for database operations
db_circuit_breaker = CircuitBreaker(
    fail_max=5,  # Open circuit after 5 consecutive failures
    reset_timeout=60,  # Stay open for 60 seconds
    name="database_updates",
)


class DecisionConsumer:
    """Kafka consumer for loan decision processing."""

    def __init__(self) -> None:
        """Initialize the decision consumer."""
        self.consumer: AIOKafkaConsumer | None = None
        self.producer: AIOKafkaProducer | None = None
        self.running = False

    async def start(self) -> None:
        """Start the Kafka consumer and producer."""
        try:
            # Initialize consumer
            self.consumer = AIOKafkaConsumer(
                settings.kafka_topic_credit_reports,
                bootstrap_servers=settings.kafka_bootstrap_servers,
                group_id="decision-service-group",
                auto_offset_reset="earliest",
                enable_auto_commit=False,  # Manual commit for reliability
                value_deserializer=lambda m: json.loads(m.decode("utf-8")),
            )

            # Initialize producer for DLQ
            self.producer = AIOKafkaProducer(
                bootstrap_servers=settings.kafka_bootstrap_servers,
                value_serializer=lambda v: json.dumps(v, default=str).encode("utf-8"),
            )

            await self.consumer.start()
            await self.producer.start()

            logger.info(
                "decision_consumer_started",
                topic=settings.kafka_topic_credit_reports,
                group_id="decision-service-group",
            )
            self.running = True

        except Exception as e:
            logger.error("decision_consumer_startup_failed", error=str(e), exc_info=True)
            raise

    async def stop(self) -> None:
        """Stop the Kafka consumer and producer."""
        self.running = False

        if self.consumer:
            await self.consumer.stop()
            logger.info("decision_consumer_stopped")

        if self.producer:
            await self.producer.stop()
            logger.info("decision_producer_stopped")

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
                "service": "decision-service",
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
        Process a single credit report message and update application status.

        Args:
            message: Credit report message from Kafka
        """
        try:
            # Validate message with Pydantic
            credit_report = CreditReportMessage(**message)

            logger.info(
                "processing_credit_report",
                application_id=str(credit_report.application_id),
                cibil_score=credit_report.cibil_score,
                pan=mask_pan(credit_report.pan_number),
            )

            # Make decision based on CIBIL score and income
            decision = make_decision(
                cibil_score=credit_report.cibil_score,
                monthly_income=credit_report.monthly_income_inr,
                loan_amount=credit_report.loan_amount_inr,
            )

            logger.info(
                "decision_made",
                application_id=str(credit_report.application_id),
                decision=decision,
                cibil_score=credit_report.cibil_score,
            )

            # Update application in database with circuit breaker protection
            try:
                async with async_session_maker() as session:
                    repository = ApplicationRepository(session)

                    # Helper function to wrap with circuit breaker
                    @db_circuit_breaker
                    async def update_with_circuit_breaker():
                        return await repository.update_status(
                            application_id=credit_report.application_id,
                            status=decision,
                            cibil_score=credit_report.cibil_score,
                        )

                    updated = await update_with_circuit_breaker()

                    if updated:
                        logger.info(
                            "application_status_updated",
                            application_id=str(credit_report.application_id),
                            new_status=decision,
                        )
                    else:
                        logger.warning(
                            "application_already_processed",
                            application_id=str(credit_report.application_id),
                            message="Application was not in PENDING status (idempotency check)",
                        )

            except CircuitBreakerError:
                # Circuit is open - database is failing
                logger.error(
                    "circuit_breaker_open_skipping_message",
                    application_id=str(credit_report.application_id),
                    message="Database circuit breaker is open - sending to DLQ",
                )
                # Send to DLQ for later processing
                await self._publish_to_dlq(message, error="Circuit breaker open")
                # Don't re-raise - message is handled via DLQ
                return

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
    """Main entry point for decision-service consumer."""
    # Register signal handlers
    signal.signal(signal.SIGTERM, handle_shutdown_signal)
    signal.signal(signal.SIGINT, handle_shutdown_signal)

    consumer = DecisionConsumer()

    try:
        await consumer.run()
    except KeyboardInterrupt:
        logger.info("keyboard_interrupt_received")
    except Exception as e:
        logger.error("decision_service_failed", error=str(e), exc_info=True)
        sys.exit(1)
    finally:
        logger.info("decision_service_shutdown_complete")


if __name__ == "__main__":
    # Configure logging
    from shared.core.logging import configure_logging

    configure_logging()

    # Run the consumer
    asyncio.run(main())

"""Kafka producer with error handling and retries.

This module provides a wrapper around AIOKafkaProducer with custom JSON
serialization, retry logic, and error handling.
"""

import asyncio
import json
from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from aiokafka import AIOKafkaProducer
from aiokafka.errors import KafkaError
from shared.core.config import settings
from shared.core.logging import get_logger
from shared.exceptions.exceptions import KafkaPublishError

logger = get_logger(__name__)


class KafkaJSONEncoder(json.JSONEncoder):
    """Custom JSON encoder for Kafka messages supporting Decimal, UUID, and datetime."""

    def default(self, obj: Any) -> Any:
        """
        Convert non-serializable objects to JSON-serializable format.

        Args:
            obj: Object to serialize

        Returns:
            JSON-serializable representation
        """
        if isinstance(obj, Decimal):
            # Preserve precision as string
            return str(obj)
        if isinstance(obj, datetime):
            return obj.isoformat()
        if isinstance(obj, UUID):
            return str(obj)
        return super().default(obj)


def _serialize_value(value: dict) -> bytes:
    """Serialize message value to JSON bytes."""
    return json.dumps(value, cls=KafkaJSONEncoder).encode("utf-8")


def _serialize_key(key: str | None) -> bytes | None:
    """Serialize message key to bytes."""
    return key.encode("utf-8") if key else None


class KafkaProducerWrapper:
    """
    Wrapper around AIOKafkaProducer with retry logic and error handling.

    This class manages the Kafka producer lifecycle and provides
    methods for publishing messages with automatic retries.
    """

    def __init__(self) -> None:
        """Initialize Kafka producer wrapper."""
        self._producer: AIOKafkaProducer | None = None
        self._started = False

    async def start(self) -> None:
        """Start the Kafka producer connection."""
        if self._started:
            logger.warning("Kafka producer already started")
            return

        try:
            # aiokafka 0.12.0+ simplified API
            self._producer = AIOKafkaProducer(
                bootstrap_servers=settings.kafka_bootstrap_servers,
                value_serializer=_serialize_value,
                key_serializer=_serialize_key,
            )

            await self._producer.start()
            self._started = True

            logger.info(
                "Kafka producer started",
                bootstrap_servers=settings.kafka_bootstrap_servers,
            )

        except Exception as e:
            logger.error("Failed to start Kafka producer", error=str(e))
            raise KafkaPublishError("producer_start", str(e))

    async def stop(self) -> None:
        """Stop the Kafka producer and close connections."""
        if not self._started or not self._producer:
            logger.warning("Kafka producer not started")
            return

        try:
            await self._producer.stop()
            self._started = False
            logger.info("Kafka producer stopped")

        except Exception as e:
            logger.error("Error stopping Kafka producer", error=str(e))

    async def send_and_wait(
        self,
        topic: str,
        value: dict,
        key: str | None = None,
        max_retries: int = 3,
        timeout: float = 5.0,
    ) -> None:
        """
        Send message to Kafka topic with retries and timeout.

        This method implements exponential backoff retry logic
        for transient failures.

        Args:
            topic: Kafka topic name
            value: Message value (will be JSON serialized)
            key: Message key for partitioning (optional)
            max_retries: Maximum number of retry attempts
            timeout: Timeout in seconds per attempt

        Raises:
            KafkaPublishError: If all retry attempts fail
        """
        if not self._started or not self._producer:
            raise KafkaPublishError(topic, "Producer not started")

        for attempt in range(1, max_retries + 1):
            try:
                # Send message with timeout
                await asyncio.wait_for(
                    self._producer.send_and_wait(topic=topic, value=value, key=key),
                    timeout=timeout,
                )

                logger.info(
                    "Message published to Kafka",
                    topic=topic,
                    key=key,
                    attempt=attempt,
                )
                return

            except asyncio.TimeoutError:
                logger.warning(
                    f"Kafka publish timeout on attempt {attempt}/{max_retries}",
                    topic=topic,
                    timeout=timeout,
                )
                if attempt == max_retries:
                    error_msg = f"Publish timed out after {max_retries} attempts"
                    logger.error("Kafka publish failed", topic=topic, error=error_msg)
                    raise KafkaPublishError(topic, error_msg)

            except KafkaError as e:
                logger.warning(
                    f"Kafka error on attempt {attempt}/{max_retries}",
                    topic=topic,
                    error=str(e),
                )
                if attempt == max_retries:
                    logger.error(
                        "Kafka publish failed after all retries",
                        topic=topic,
                        error=str(e),
                    )
                    raise KafkaPublishError(topic, str(e))

            except Exception as e:
                logger.error(
                    "Unexpected error publishing to Kafka",
                    topic=topic,
                    error=str(e),
                    attempt=attempt,
                )
                if attempt == max_retries:
                    raise KafkaPublishError(topic, str(e))

            # Exponential backoff
            if attempt < max_retries:
                backoff_time = 0.5 * attempt
                logger.debug(
                    "Retrying Kafka publish after backoff",
                    backoff_seconds=backoff_time,
                )
                await asyncio.sleep(backoff_time)

    def is_started(self) -> bool:
        """Check if producer is started."""
        return self._started


# Global producer instance (initialized in FastAPI lifespan)
kafka_producer = KafkaProducerWrapper()


async def get_kafka_producer() -> KafkaProducerWrapper:
    """
    Dependency function for FastAPI routes to get Kafka producer.

    Returns:
        KafkaProducerWrapper: The global Kafka producer instance

    Example:
        @app.post("/applications")
        async def create_application(
            producer: KafkaProducerWrapper = Depends(get_kafka_producer)
        ):
            await producer.send_and_wait("topic", message)
    """
    return kafka_producer

"""Custom exception classes for the application."""

from uuid import UUID


class ApplicationError(Exception):
    """Base exception for application errors."""

    pass


class ApplicationNotFoundError(ApplicationError):
    """Raised when an application is not found by ID."""

    def __init__(self, application_id: UUID) -> None:
        self.application_id = application_id
        super().__init__(f"Application with ID {application_id} not found")


class KafkaPublishError(ApplicationError):
    """Raised when publishing to Kafka fails after retries."""

    def __init__(self, topic: str, message: str) -> None:
        self.topic = topic
        super().__init__(f"Failed to publish to Kafka topic {topic}: {message}")


class DatabaseError(ApplicationError):
    """Raised when database operation fails."""

    pass

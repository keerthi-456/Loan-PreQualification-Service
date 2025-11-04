"""Structured logging configuration using structlog."""

import logging
import sys

import structlog

from shared.core.config import settings


def mask_pan(pan: str) -> str:
    """
    Mask PAN number for logging to protect PII.

    Args:
        pan: PAN number in format ABCDE1234F

    Returns:
        Masked PAN: ABCDE***4F
    """
    if not pan or len(pan) != 10:
        return "INVALID"
    return f"{pan[:5]}***{pan[-2:]}"


def configure_logging() -> None:
    """Configure structured logging for the application."""
    # Configure standard logging to work with structlog
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=getattr(logging, settings.log_level.upper()),
    )

    # Configure structlog
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.stdlib.filter_by_level,
            structlog.stdlib.add_logger_name,
            structlog.stdlib.add_log_level,
            structlog.stdlib.PositionalArgumentsFormatter(),
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.UnicodeDecoder(),
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str) -> structlog.stdlib.BoundLogger:
    """
    Get a structured logger instance.

    Args:
        name: Logger name (usually __name__)

    Returns:
        Configured structlog logger
    """
    return structlog.get_logger(name)

"""Pydantic schemas for Kafka message validation.

These schemas ensure type safety and validation for messages
exchanged between microservices via Kafka topics.
"""

from datetime import datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field


class LoanApplicationMessage(BaseModel):
    """
    Message schema for loan_applications_submitted topic.

    Published by: prequal-api
    Consumed by: credit-service
    """

    application_id: UUID = Field(..., description="Unique application identifier")
    pan_number: str = Field(..., description="10-character PAN number")
    applicant_name: str | None = Field(None, description="Applicant's full name")
    monthly_income_inr: Decimal = Field(..., description="Monthly income in INR")
    loan_amount_inr: Decimal = Field(..., description="Requested loan amount in INR")
    loan_type: Literal["PERSONAL", "HOME", "AUTO"] = Field(..., description="Type of loan")
    timestamp: datetime = Field(..., description="Message creation timestamp")
    correlation_id: str = Field(..., description="Correlation ID for distributed tracing")


class CreditReportMessage(BaseModel):
    """
    Message schema for credit_reports_generated topic.

    Published by: credit-service
    Consumed by: decision-service
    """

    application_id: UUID = Field(..., description="Unique application identifier")
    pan_number: str = Field(..., description="10-character PAN number")
    cibil_score: int = Field(..., ge=300, le=900, description="Simulated CIBIL score (300-900)")
    monthly_income_inr: Decimal = Field(..., description="Monthly income in INR")
    loan_amount_inr: Decimal = Field(..., description="Requested loan amount in INR")
    loan_type: Literal["PERSONAL", "HOME", "AUTO"] = Field(..., description="Type of loan")
    timestamp: datetime = Field(..., description="Message creation timestamp")
    correlation_id: str = Field(..., description="Correlation ID for distributed tracing")


class DeadLetterMessage(BaseModel):
    """
    Message schema for loan_processing_dlq topic (Dead Letter Queue).

    Published by: credit-service, decision-service
    Consumed by: Manual review/alerting service (future)
    """

    original_topic: str = Field(..., description="Topic where message originated")
    original_partition: int = Field(..., description="Original partition number")
    original_offset: int = Field(..., description="Original message offset")
    error_message: str = Field(..., description="Error that caused failure")
    retry_count: int = Field(..., description="Number of retry attempts made")
    failed_at: datetime = Field(..., description="Timestamp when message failed")
    payload: dict = Field(..., description="Original message payload")
    correlation_id: str = Field(..., description="Correlation ID for tracing")

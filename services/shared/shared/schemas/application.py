"""Pydantic schemas for loan application API requests and responses."""

from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class LoanApplicationRequest(BaseModel):
    """Request schema for submitting a new loan prequalification application."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "pan_number": "ABCDE1234F",
                "applicant_name": "Rajesh Kumar",
                "monthly_income_inr": 75000.00,
                "loan_amount_inr": 500000.00,
                "loan_type": "PERSONAL",
            }
        }
    )

    pan_number: str = Field(
        ...,
        pattern=r"^[A-Z]{5}[0-9]{4}[A-Z]$",
        description="10-character Indian PAN number (e.g., ABCDE1234F)",
        min_length=10,
        max_length=10,
    )
    applicant_name: str | None = Field(
        None, min_length=1, max_length=255, description="Full name of the applicant"
    )
    monthly_income_inr: Decimal = Field(
        ...,
        gt=0,
        decimal_places=2,
        description="Gross monthly income in Indian Rupees",
    )
    loan_amount_inr: Decimal = Field(
        ..., gt=0, decimal_places=2, description="Requested loan amount in INR"
    )
    loan_type: Literal["PERSONAL", "HOME", "AUTO"] = Field(
        ..., description="Type of loan: PERSONAL (unsecured), HOME (secured), AUTO"
    )


class LoanApplicationResponse(BaseModel):
    """Response schema for successful loan application submission."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "application_id": "550e8400-e29b-41d4-a716-446655440000",
                "status": "PENDING",
            }
        }
    )

    application_id: UUID = Field(..., description="Unique identifier for the application")
    status: Literal["PENDING"] = Field(
        ..., description="Initial application status (always PENDING)"
    )


class ApplicationStatusResponse(BaseModel):
    """Response schema for checking application status."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "application_id": "550e8400-e29b-41d4-a716-446655440000",
                "status": "PRE_APPROVED",
            }
        }
    )

    application_id: UUID = Field(..., description="Unique identifier for the application")
    status: Literal["PENDING", "PRE_APPROVED", "REJECTED", "MANUAL_REVIEW"] = Field(
        ...,
        description=(
            "Current application status: "
            "PENDING (awaiting processing), "
            "PRE_APPROVED (meets criteria), "
            "REJECTED (does not meet criteria), "
            "MANUAL_REVIEW (borderline case)"
        ),
    )


class HealthCheckResponse(BaseModel):
    """Response schema for health check endpoint."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {"status": "healthy", "database": "connected", "kafka": "connected"}
        }
    )

    status: Literal["healthy", "unhealthy"] = Field(..., description="Overall system health")
    database: Literal["connected", "disconnected"] = Field(
        ..., description="Database connection status"
    )
    kafka: Literal["connected", "disconnected"] = Field(..., description="Kafka connection status")


class ErrorResponse(BaseModel):
    """Standard error response schema."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {"error": "Validation Error", "detail": "Invalid PAN number format"}
        }
    )

    error: str = Field(..., description="Error type or category")
    detail: str | dict = Field(..., description="Detailed error message or validation errors")

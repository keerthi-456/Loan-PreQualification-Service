"""SQLAlchemy ORM model for loan applications."""

import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import DECIMAL, CheckConstraint, Index, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class Application(Base):
    """Loan application model."""

    __tablename__ = "applications"

    # Primary key
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # Application details
    pan_number: Mapped[str] = mapped_column(String(10), nullable=False, index=True)
    applicant_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    monthly_income_inr: Mapped[Decimal] = mapped_column(DECIMAL(12, 2), nullable=False)
    loan_amount_inr: Mapped[Decimal] = mapped_column(DECIMAL(12, 2), nullable=False)
    loan_type: Mapped[str | None] = mapped_column(String(20), nullable=True)

    # Status tracking
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="PENDING", index=True)
    cibil_score: Mapped[int | None] = mapped_column(nullable=True)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(nullable=False, default=func.now(), index=True)
    updated_at: Mapped[datetime] = mapped_column(nullable=False, default=func.now())

    # Constraints
    __table_args__ = (
        CheckConstraint(
            "status IN ('PENDING', 'PRE_APPROVED', 'REJECTED', 'MANUAL_REVIEW')",
            name="valid_status",
        ),
        CheckConstraint(
            "cibil_score IS NULL OR (cibil_score >= 300 AND cibil_score <= 900)",
            name="valid_cibil_score",
        ),
        CheckConstraint("monthly_income_inr > 0", name="positive_income"),
        CheckConstraint("loan_amount_inr > 0", name="positive_loan_amount"),
        Index("idx_applications_created_at", "created_at", postgresql_using="btree"),
    )

    def __repr__(self) -> str:
        return (
            f"<Application(id={self.id}, pan_number={self.pan_number[:5]}***, "
            f"status={self.status})>"
        )

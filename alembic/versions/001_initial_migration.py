"""Initial migration with applications table and trigger.

Revision ID: 001
Revises:
Create Date: 2025-10-30
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op  # type: ignore

# revision identifiers, used by Alembic.
revision: str = "001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create applications table with constraints and trigger."""
    # Create applications table
    op.create_table(
        "applications",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True),  # type: ignore[attr-defined]
        sa.Column("pan_number", sa.String(10), nullable=False),
        sa.Column("applicant_name", sa.String(255), nullable=True),
        sa.Column("monthly_income_inr", sa.DECIMAL(12, 2), nullable=False),
        sa.Column("loan_amount_inr", sa.DECIMAL(12, 2), nullable=False),
        sa.Column("loan_type", sa.String(20), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="PENDING"),
        sa.Column("cibil_score", sa.Integer, nullable=True),
        sa.Column("created_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint(
            "status IN ('PENDING', 'PRE_APPROVED', 'REJECTED', 'MANUAL_REVIEW')",
            name="valid_status",
        ),
        sa.CheckConstraint(
            "cibil_score IS NULL OR (cibil_score >= 300 AND cibil_score <= 900)",
            name="valid_cibil_score",
        ),
        sa.CheckConstraint("monthly_income_inr > 0", name="positive_income"),
        sa.CheckConstraint("loan_amount_inr > 0", name="positive_loan_amount"),
    )

    # Create indexes
    op.create_index("idx_applications_pan_number", "applications", ["pan_number"])
    op.create_index("idx_applications_status", "applications", ["status"])
    op.create_index(
        "idx_applications_created_at",
        "applications",
        ["created_at"],
        postgresql_using="btree",
    )

    # Create trigger function for updated_at
    op.execute(
        """
        CREATE OR REPLACE FUNCTION update_updated_at_column()
        RETURNS TRIGGER AS $$
        BEGIN
            NEW.updated_at = NOW();
            RETURN NEW;
        END;
        $$ language 'plpgsql';
        """
    )

    # Create trigger
    op.execute(
        """
        CREATE TRIGGER update_applications_updated_at
            BEFORE UPDATE ON applications
            FOR EACH ROW
            EXECUTE FUNCTION update_updated_at_column();
        """
    )


def downgrade() -> None:
    """Drop applications table, trigger, and trigger function."""
    op.execute("DROP TRIGGER IF EXISTS update_applications_updated_at ON applications;")
    op.execute("DROP FUNCTION IF EXISTS update_updated_at_column();")
    op.drop_index("idx_applications_created_at", table_name="applications")
    op.drop_index("idx_applications_status", table_name="applications")
    op.drop_index("idx_applications_pan_number", table_name="applications")
    op.drop_table("applications")

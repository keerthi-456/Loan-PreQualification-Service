"""Decision service for loan prequalification logic.

This service applies business rules to determine whether an applicant
should be pre-approved, rejected, or sent for manual review.
"""

from decimal import Decimal

from shared.core.logging import get_logger

logger = get_logger(__name__)


def make_decision(cibil_score: int, monthly_income: Decimal, loan_amount: Decimal) -> str:
    """
    Make prequalification decision based on credit score and income ratio.

    Business Rules:
    1. REJECTED: CIBIL score < 650 (high risk)
    2. PRE_APPROVED: Score >= 650 AND income > required monthly payment
       - Required payment calculated as: loan_amount / 48 (4-year loan)
    3. MANUAL_REVIEW: Score >= 650 AND income <= required monthly payment
       - Good credit but tight financial situation

    Args:
        cibil_score: Applicant's CIBIL score (300-900)
        monthly_income: Gross monthly income in INR
        loan_amount: Requested loan amount in INR

    Returns:
        str: Decision status - "REJECTED", "PRE_APPROVED", or "MANUAL_REVIEW"

    Examples:
        >>> make_decision(600, Decimal("50000"), Decimal("200000"))
        'REJECTED'  # Low CIBIL score

        >>> make_decision(750, Decimal("60000"), Decimal("200000"))
        'PRE_APPROVED'  # Good score and sufficient income

        >>> make_decision(750, Decimal("4000"), Decimal("200000"))
        'MANUAL_REVIEW'  # Good score but tight income
    """
    logger.debug(
        "Making prequalification decision",
        cibil_score=cibil_score,
        monthly_income=str(monthly_income),
        loan_amount=str(loan_amount),
    )

    # Rule 1: Reject if CIBIL score is below minimum threshold
    if cibil_score < 650:
        logger.info(
            "Application REJECTED - CIBIL score below minimum threshold",
            cibil_score=cibil_score,
            threshold=650,
        )
        return "REJECTED"

    # Calculate required monthly payment for a 4-year loan
    # Assumption: Simple division by 48 months (no interest calculation for MVP)
    required_monthly_payment = loan_amount / Decimal("48")

    logger.debug(
        "Calculated required monthly payment",
        required_payment=str(required_monthly_payment),
        monthly_income=str(monthly_income),
    )

    # Rule 2: Pre-approve if income is sufficient
    if monthly_income > required_monthly_payment:
        logger.info(
            "Application PRE_APPROVED - sufficient income ratio",
            cibil_score=cibil_score,
            monthly_income=str(monthly_income),
            required_payment=str(required_monthly_payment),
            income_ratio=float(monthly_income / required_monthly_payment),
        )
        return "PRE_APPROVED"

    # Rule 3: Manual review for borderline cases
    # Good CIBIL score but income is tight (less than or equal to required payment)
    logger.info(
        "Application sent to MANUAL_REVIEW - good score but tight income",
        cibil_score=cibil_score,
        monthly_income=str(monthly_income),
        required_payment=str(required_monthly_payment),
        income_ratio=float(monthly_income / required_monthly_payment),
    )
    return "MANUAL_REVIEW"

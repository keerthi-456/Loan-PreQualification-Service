"""Credit service for CIBIL score simulation.

This service simulates a credit bureau check by calculating a CIBIL score
based on PAN number, monthly income, and loan type.
"""

import random
from decimal import Decimal

from shared.core.logging import get_logger, mask_pan

logger = get_logger(__name__)


def calculate_cibil_score(pan_number: str, monthly_income: Decimal, loan_type: str) -> int:
    """
    Calculate simulated CIBIL score based on application data.

    This is a simulation of credit bureau scoring logic. In production,
    this would integrate with actual credit bureaus like CIBIL, Experian, etc.

    Algorithm:
    - Special test PANs return fixed scores for testing
    - Base score: 650
    - Income adjustments:
        - Monthly income > 75000: +40 points
        - Monthly income < 30000: -20 points
    - Loan type adjustments:
        - PERSONAL (unsecured): -10 points
        - HOME (secured): +10 points
        - AUTO: 0 points (neutral)
    - Random variation: -5 to +5 points (for realism)
    - Final score clamped to valid range: 300-900

    Args:
        pan_number: 10-character PAN number (e.g., ABCDE1234F)
        monthly_income: Gross monthly income in INR
        loan_type: Type of loan (PERSONAL, HOME, AUTO)

    Returns:
        int: Simulated CIBIL score between 300 and 900

    Examples:
        >>> calculate_cibil_score("ABCDE1234F", Decimal("50000"), "PERSONAL")
        790  # Fixed test PAN
        >>> calculate_cibil_score("XXXXX1111X", Decimal("80000"), "HOME")
        # Base 650 + High income 40 + HOME 10 + Random(-5 to +5) = 695-705
    """
    logger.debug(
        "Calculating CIBIL score",
        pan_number=mask_pan(pan_number),
        monthly_income=str(monthly_income),
        loan_type=loan_type,
    )

    # Special test PANs for deterministic testing
    if pan_number == "ABCDE1234F":
        logger.info("Special PAN ABCDE1234F detected, returning fixed score 790")
        return 790

    if pan_number == "FGHIJ5678K":
        logger.info("Special PAN FGHIJ5678K detected, returning fixed score 610")
        return 610

    # Start with base score
    score = 650

    # Apply income-based adjustments
    if monthly_income > Decimal("75000"):
        score += 40
        logger.debug("High income bonus applied: +40 points")
    elif monthly_income < Decimal("30000"):
        score -= 20
        logger.debug("Low income penalty applied: -20 points")

    # Apply loan type adjustments
    if loan_type == "PERSONAL":
        score -= 10
        logger.debug("PERSONAL loan penalty applied: -10 points (unsecured)")
    elif loan_type == "HOME":
        score += 10
        logger.debug("HOME loan bonus applied: +10 points (secured)")
    # AUTO loan type has no adjustment (neutral)

    # Add random variation for realism (-5 to +5)
    random_adjustment = random.randint(-5, 5)
    score += random_adjustment
    logger.debug("Random variation applied", adjustment=random_adjustment)

    # Clamp score to valid CIBIL range (300-900)
    final_score = max(300, min(900, score))

    if final_score != score:
        logger.debug(
            "Score clamped to valid range",
            original_score=score,
            final_score=final_score,
        )

    logger.info(
        "CIBIL score calculated",
        pan_number=mask_pan(pan_number),
        final_score=final_score,
    )

    return final_score

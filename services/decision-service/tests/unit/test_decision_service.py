"""Unit tests for decision engine service.

Following TDD Red-Green-Refactor cycle.
These tests are written BEFORE implementing the decision service.
"""

from decimal import Decimal

from app.services.decision_service import make_decision


class TestDecisionEngine:
    """Test suite for loan prequalification decision logic."""

    def test_low_cibil_score_rejected(self):
        """Test that CIBIL score < 650 results in REJECTED status."""
        decision = make_decision(
            cibil_score=600, monthly_income=Decimal("50000"), loan_amount=Decimal("200000")
        )

        assert decision == "REJECTED"

    def test_cibil_649_rejected(self):
        """Test that CIBIL score of exactly 649 is REJECTED."""

        decision = make_decision(
            cibil_score=649, monthly_income=Decimal("80000"), loan_amount=Decimal("100000")
        )

        assert decision == "REJECTED"

    def test_minimum_cibil_300_rejected(self):
        """Test that minimum CIBIL score of 300 is REJECTED."""

        decision = make_decision(
            cibil_score=300, monthly_income=Decimal("100000"), loan_amount=Decimal("50000")
        )

        assert decision == "REJECTED"

    def test_good_score_sufficient_income_pre_approved(self):
        """Test that score >= 650 with sufficient income results in PRE_APPROVED."""

        # Income: 60000, Loan: 200000
        # Required monthly payment: 200000 / 48 = 4166.67
        # 60000 > 4166.67, so PRE_APPROVED
        decision = make_decision(
            cibil_score=750, monthly_income=Decimal("60000"), loan_amount=Decimal("200000")
        )

        assert decision == "PRE_APPROVED"

    def test_cibil_650_sufficient_income_pre_approved(self):
        """Test that exactly 650 CIBIL with good income is PRE_APPROVED."""

        # Income: 50000, Loan: 200000
        # Required: 200000 / 48 = 4166.67
        # 50000 > 4166.67
        decision = make_decision(
            cibil_score=650, monthly_income=Decimal("50000"), loan_amount=Decimal("200000")
        )

        assert decision == "PRE_APPROVED"

    def test_excellent_score_sufficient_income_pre_approved(self):
        """Test that excellent CIBIL score (900) with good income is PRE_APPROVED."""

        decision = make_decision(
            cibil_score=900, monthly_income=Decimal("100000"), loan_amount=Decimal("500000")
        )

        # Required: 500000 / 48 = 10416.67
        # 100000 > 10416.67
        assert decision == "PRE_APPROVED"

    def test_good_score_tight_income_manual_review(self):
        """Test that score >= 650 but insufficient income results in MANUAL_REVIEW."""

        # Income: 4000, Loan: 200000
        # Required monthly payment: 200000 / 48 = 4166.67
        # 4000 < 4166.67, so MANUAL_REVIEW
        decision = make_decision(
            cibil_score=750, monthly_income=Decimal("4000"), loan_amount=Decimal("200000")
        )

        assert decision == "MANUAL_REVIEW"

    def test_good_score_equal_income_manual_review(self):
        """Test that income exactly equal to required payment goes to MANUAL_REVIEW."""

        # Income: 4166.66, Loan: 200000
        # Required: 200000 / 48 = 4166.666666...
        # 4166.66 < 4166.666666, so MANUAL_REVIEW
        decision = make_decision(
            cibil_score=700, monthly_income=Decimal("4166.66"), loan_amount=Decimal("200000")
        )

        assert decision == "MANUAL_REVIEW"

    def test_cibil_650_insufficient_income_manual_review(self):
        """Test that minimum passing CIBIL (650) with tight income is MANUAL_REVIEW."""

        decision = make_decision(
            cibil_score=650, monthly_income=Decimal("3000"), loan_amount=Decimal("200000")
        )

        # Required: 200000 / 48 = 4166.67
        # 3000 < 4166.67
        assert decision == "MANUAL_REVIEW"

    def test_income_ratio_calculation_small_loan(self):
        """Test decision logic with small loan amount."""

        # Small loan: 50000, Income: 10000
        # Required: 50000 / 48 = 1041.67
        # 10000 > 1041.67
        decision = make_decision(
            cibil_score=700, monthly_income=Decimal("10000"), loan_amount=Decimal("50000")
        )

        assert decision == "PRE_APPROVED"

    def test_income_ratio_calculation_large_loan(self):
        """Test decision logic with large loan amount."""

        # Large loan: 5000000 (50 lakhs), Income: 80000
        # Required: 5000000 / 48 = 104166.67
        # 80000 < 104166.67
        decision = make_decision(
            cibil_score=850, monthly_income=Decimal("80000"), loan_amount=Decimal("5000000")
        )

        assert decision == "MANUAL_REVIEW"

    def test_borderline_income_just_above_threshold(self):
        """Test income just slightly above required threshold."""

        # Income: 4200, Loan: 200000
        # Required: 200000 / 48 = 4166.67
        # 4200 > 4166.67 (just barely)
        decision = make_decision(
            cibil_score=700, monthly_income=Decimal("4200"), loan_amount=Decimal("200000")
        )

        assert decision == "PRE_APPROVED"

    def test_borderline_income_just_below_threshold(self):
        """Test income just slightly below required threshold."""

        # Income: 4100, Loan: 200000
        # Required: 200000 / 48 = 4166.67
        # 4100 < 4166.67 (just barely)
        decision = make_decision(
            cibil_score=700, monthly_income=Decimal("4100"), loan_amount=Decimal("200000")
        )

        assert decision == "MANUAL_REVIEW"

    def test_various_scenarios_comprehensive(self):
        """Test comprehensive scenarios covering all decision paths."""

        test_cases = [
            # (cibil_score, monthly_income, loan_amount, expected_decision)
            (300, Decimal("100000"), Decimal("100000"), "REJECTED"),  # Min CIBIL
            (649, Decimal("100000"), Decimal("100000"), "REJECTED"),  # Just below threshold
            (650, Decimal("100000"), Decimal("100000"), "PRE_APPROVED"),  # Sufficient income
            (700, Decimal("50000"), Decimal("200000"), "PRE_APPROVED"),  # Good case
            (750, Decimal("3000"), Decimal("200000"), "MANUAL_REVIEW"),  # Tight income
            (800, Decimal("4166.66"), Decimal("200000"), "MANUAL_REVIEW"),  # Equal-ish income
            (900, Decimal("200000"), Decimal("1000000"), "PRE_APPROVED"),  # Excellent case
        ]

        for cibil_score, income, loan_amount, expected in test_cases:
            decision = make_decision(
                cibil_score=cibil_score, monthly_income=income, loan_amount=loan_amount
            )
            assert decision == expected, (
                f"Failed for CIBIL={cibil_score}, Income={income}, "
                f"Loan={loan_amount}: expected {expected}, got {decision}"
            )

    def test_valid_decision_statuses_only(self):
        """Test that decision engine only returns valid status values."""

        # Test multiple scenarios
        test_cases = [
            (600, Decimal("50000"), Decimal("200000")),
            (650, Decimal("50000"), Decimal("200000")),
            (750, Decimal("4000"), Decimal("200000")),
            (800, Decimal("100000"), Decimal("500000")),
        ]

        valid_statuses = {"REJECTED", "PRE_APPROVED", "MANUAL_REVIEW"}

        for cibil_score, income, loan_amount in test_cases:
            decision = make_decision(
                cibil_score=cibil_score, monthly_income=income, loan_amount=loan_amount
            )
            assert decision in valid_statuses, f"Invalid decision status returned: {decision}"

    def test_decimal_precision_handling(self):
        """Test that decision logic handles decimal precision correctly."""

        # Test with precise decimal values
        decision = make_decision(
            cibil_score=720,
            monthly_income=Decimal("4166.6666666"),  # Slight variation
            loan_amount=Decimal("199999.99"),
        )

        # Required: 199999.99 / 48 = 4166.666458...
        # 4166.6666666 > 4166.666458, so PRE_APPROVED
        assert decision == "PRE_APPROVED"

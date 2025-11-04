"""Unit tests for CIBIL score calculation service.

Following TDD Red-Green-Refactor cycle.
These tests are written BEFORE implementing the credit service.
"""

import random
from decimal import Decimal

from app.services.credit_service import calculate_cibil_score


class TestCIBILScoreCalculation:
    """Test suite for CIBIL score simulation logic."""

    def test_special_pan_abcde_returns_790(self):
        """Test that special PAN ABCDE1234F always returns fixed score 790."""
        score = calculate_cibil_score(
            pan_number="ABCDE1234F", monthly_income=Decimal("50000"), loan_type="PERSONAL"
        )
        assert score == 790

    def test_special_pan_fghij_returns_610(self):
        """Test that special PAN FGHIJ5678K always returns fixed score 610."""
        score = calculate_cibil_score(
            pan_number="FGHIJ5678K", monthly_income=Decimal("50000"), loan_type="PERSONAL"
        )
        assert score == 610

    def test_high_income_increases_score(self):
        """Test that income > 75000 INR adds bonus points to score."""
        # Mock random to ensure deterministic test
        random.seed(42)  # Set seed for reproducible random variation

        score = calculate_cibil_score(
            pan_number="AAAAA1111A", monthly_income=Decimal("80000"), loan_type="AUTO"
        )

        # Base: 650, High income: +40, AUTO: 0, Random: varies (-5 to +5)
        # Minimum expected: 650 + 40 - 5 = 685
        assert score >= 685
        assert score <= 900

    def test_low_income_decreases_score(self):
        """Test that income < 30000 INR reduces score."""
        random.seed(42)

        score = calculate_cibil_score(
            pan_number="BBBBB2222B", monthly_income=Decimal("25000"), loan_type="HOME"
        )

        # Base: 650, Low income: -20, HOME: +10, Random: varies
        # Maximum expected: 650 - 20 + 10 + 5 = 645
        assert score <= 645
        assert score >= 300

    def test_personal_loan_decreases_score(self):
        """Test that PERSONAL loan type (unsecured) reduces score by 10."""
        random.seed(42)

        score = calculate_cibil_score(
            pan_number="CCCCC3333C", monthly_income=Decimal("50000"), loan_type="PERSONAL"
        )

        # Base: 650, PERSONAL: -10, Random: varies
        # Income 50000 is neutral (no bonus/penalty)
        # Expected range: 650 - 10 - 5 to 650 - 10 + 5 = 635 to 645
        assert 630 <= score <= 650

    def test_home_loan_increases_score(self):
        """Test that HOME loan type (secured) increases score by 10."""
        random.seed(42)

        score = calculate_cibil_score(
            pan_number="DDDDD4444D", monthly_income=Decimal("50000"), loan_type="HOME"
        )

        # Base: 650, HOME: +10, Random: varies
        # Expected range: 650 + 10 - 5 to 650 + 10 + 5 = 655 to 665
        assert 650 <= score <= 670

    def test_auto_loan_neutral_adjustment(self):
        """Test that AUTO loan type has neutral adjustment."""
        random.seed(42)

        score = calculate_cibil_score(
            pan_number="EEEEE5555E", monthly_income=Decimal("50000"), loan_type="AUTO"
        )

        # Base: 650, AUTO: 0, Random: varies
        # Expected range: 650 - 5 to 650 + 5 = 645 to 655
        assert 640 <= score <= 660

    def test_score_clamped_to_minimum_300(self):
        """Test that score is never below 300 (minimum CIBIL score)."""
        score = calculate_cibil_score(
            pan_number="FFFFF6666F",
            monthly_income=Decimal("10000"),  # Very low income
            loan_type="PERSONAL",  # Unsecured (penalty)
        )

        assert score >= 300

    def test_score_clamped_to_maximum_900(self):
        """Test that score is never above 900 (maximum CIBIL score)."""
        score = calculate_cibil_score(
            pan_number="GGGGG7777G",
            monthly_income=Decimal("200000"),  # Very high income
            loan_type="HOME",  # Secured (bonus)
        )

        assert score <= 900

    def test_score_within_valid_range(self):
        """Test that calculated score is always within valid range 300-900."""
        # Test various combinations
        test_cases = [
            ("HHHHH8888H", Decimal("30000"), "PERSONAL"),
            ("IIIII9999I", Decimal("75000"), "HOME"),
            ("JJJJJ0000J", Decimal("100000"), "AUTO"),
            ("KKKKK1111K", Decimal("15000"), "PERSONAL"),
            ("LLLLL2222L", Decimal("150000"), "HOME"),
        ]

        for pan, income, loan_type in test_cases:
            score = calculate_cibil_score(
                pan_number=pan, monthly_income=income, loan_type=loan_type
            )
            assert 300 <= score <= 900, f"Score {score} out of range for PAN {pan}"

    def test_random_variation_applied(self):
        """Test that random variation (-5 to +5) is applied to score."""
        # Run multiple times to check randomness (without special PANs)
        scores = []
        for i in range(20):
            score = calculate_cibil_score(
                pan_number=f"MMMMM{i:04d}M", monthly_income=Decimal("50000"), loan_type="AUTO"
            )
            scores.append(score)

        # With random variation, we should see different scores
        # At least some variation should exist (not all same)
        unique_scores = set(scores)
        assert (
            len(unique_scores) > 1
        ), "Expected variation in scores due to random component, but all scores are identical"

    def test_combined_high_income_home_loan(self):
        """Test combined effect of high income and HOME loan."""
        random.seed(42)

        score = calculate_cibil_score(
            pan_number="NNNNN3333N", monthly_income=Decimal("100000"), loan_type="HOME"
        )

        # Base: 650, High income: +40, HOME: +10, Random: varies
        # Expected minimum: 650 + 40 + 10 - 5 = 695
        assert score >= 695
        assert score <= 900

    def test_combined_low_income_personal_loan(self):
        """Test combined effect of low income and PERSONAL loan."""
        random.seed(42)

        score = calculate_cibil_score(
            pan_number="OOOOO4444O", monthly_income=Decimal("20000"), loan_type="PERSONAL"
        )

        # Base: 650, Low income: -20, PERSONAL: -10, Random: varies
        # Expected maximum: 650 - 20 - 10 + 5 = 625
        assert score <= 625
        assert score >= 300

    def test_medium_income_neutral(self):
        """Test that medium income (between 30000 and 75000) has no adjustment."""
        random.seed(42)

        score = calculate_cibil_score(
            pan_number="PPPPP5555P", monthly_income=Decimal("50000"), loan_type="AUTO"
        )

        # Base: 650, Medium income: 0, AUTO: 0, Random: varies
        # Expected range: 650 - 5 to 650 + 5 = 645 to 655
        assert 640 <= score <= 660

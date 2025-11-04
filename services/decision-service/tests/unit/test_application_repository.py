"""Unit tests for ApplicationRepository.

Following TDD principles with mocked database dependencies.
"""

from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, Mock
from uuid import uuid4

import pytest
from shared.exceptions.exceptions import DatabaseError
from shared.models.application import Application
from sqlalchemy.exc import SQLAlchemyError

from app.repositories.application_repository import ApplicationRepository


class TestApplicationRepositorySave:
    """Test suite for save() method."""

    @pytest.mark.asyncio
    async def test_save_application_success(self):
        """Test successfully saving an application."""
        # Create mock database session with correct sync/async methods
        mock_db = AsyncMock()
        mock_db.add = Mock()  # add() is synchronous
        mock_db.commit = AsyncMock()  # commit() is async
        mock_db.refresh = AsyncMock()  # refresh() is async
        repository = ApplicationRepository(mock_db)

        # Create test application
        app_id = uuid4()
        application = Application(
            id=app_id,
            pan_number="ABCDE1234F",
            applicant_name="John Doe",
            monthly_income_inr=Decimal("50000"),
            loan_amount_inr=Decimal("200000"),
            loan_type="PERSONAL",
            status="PENDING",
        )

        # Execute
        result = await repository.save(application)

        # Verify
        mock_db.add.assert_called_once_with(application)
        mock_db.commit.assert_called_once()
        mock_db.refresh.assert_called_once_with(application)
        assert result == application

    @pytest.mark.asyncio
    async def test_save_application_database_error(self):
        """Test save() handles database errors properly."""
        mock_db = AsyncMock()
        mock_db.add = Mock()  # add() is synchronous
        mock_db.commit = AsyncMock(side_effect=SQLAlchemyError("Database connection failed"))
        mock_db.rollback = AsyncMock()  # rollback() is async
        repository = ApplicationRepository(mock_db)

        application = Application(
            id=uuid4(),
            pan_number="ABCDE1234F",
            monthly_income_inr=Decimal("50000"),
            loan_amount_inr=Decimal("200000"),
            loan_type="PERSONAL",
            status="PENDING",
        )

        # Verify exception is raised and rollback is called
        with pytest.raises(DatabaseError, match="Failed to save application"):
            await repository.save(application)

        mock_db.rollback.assert_called_once()


class TestApplicationRepositoryFindById:
    """Test suite for find_by_id() method."""

    @pytest.mark.asyncio
    async def test_find_by_id_existing_application(self):
        """Test finding an existing application by ID."""
        mock_db = AsyncMock()
        repository = ApplicationRepository(mock_db)

        # Mock application
        app_id = uuid4()
        mock_application = Application(
            id=app_id,
            pan_number="ABCDE1234F",
            monthly_income_inr=Decimal("50000"),
            loan_amount_inr=Decimal("200000"),
            loan_type="PERSONAL",
            status="PRE_APPROVED",
            cibil_score=750,
        )

        # Mock database result
        mock_result = Mock()
        mock_result.scalar_one_or_none.return_value = mock_application
        mock_db.execute.return_value = mock_result

        # Execute
        result = await repository.find_by_id(app_id)

        # Verify
        assert result == mock_application
        mock_db.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_find_by_id_non_existent_returns_none(self):
        """Test finding a non-existent application returns None."""
        mock_db = AsyncMock()
        repository = ApplicationRepository(mock_db)

        # Mock database returns None
        mock_result = Mock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = mock_result

        # Execute
        result = await repository.find_by_id(uuid4())

        # Verify
        assert result is None

    @pytest.mark.asyncio
    async def test_find_by_id_database_error(self):
        """Test find_by_id() handles database errors."""
        mock_db = AsyncMock()
        mock_db.execute.side_effect = SQLAlchemyError("Database query failed")
        repository = ApplicationRepository(mock_db)

        # Verify exception is raised
        with pytest.raises(DatabaseError, match="Failed to find application"):
            await repository.find_by_id(uuid4())


class TestApplicationRepositoryUpdateStatus:
    """Test suite for update_status() method."""

    @pytest.mark.asyncio
    async def test_update_status_success(self):
        """Test successfully updating application status."""
        mock_db = AsyncMock()

        # Create a proper async context manager mock
        class AsyncContextManagerMock:
            async def __aenter__(self):
                return self

            async def __aexit__(self, exc_type, exc_val, exc_tb):
                return None

        # Make begin_nested a regular method (not async) that returns an async context manager
        mock_db.begin_nested = MagicMock(return_value=AsyncContextManagerMock())

        repository = ApplicationRepository(mock_db)

        # Mock finding a PENDING application
        app_id = uuid4()
        mock_application = Application(
            id=app_id,
            pan_number="ABCDE1234F",
            monthly_income_inr=Decimal("50000"),
            loan_amount_inr=Decimal("200000"),
            loan_type="PERSONAL",
            status="PENDING",
        )

        mock_result = Mock()
        mock_result.scalar_one_or_none.return_value = mock_application
        mock_db.execute.return_value = mock_result

        # Execute
        result = await repository.update_status(app_id, "PRE_APPROVED", 750)

        # Verify
        assert result is True
        assert mock_application.status == "PRE_APPROVED"
        assert mock_application.cibil_score == 750
        mock_db.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_update_status_application_not_found(self):
        """Test update_status() when application doesn't exist."""
        mock_db = AsyncMock()

        class AsyncContextManagerMock:
            async def __aenter__(self):
                return self

            async def __aexit__(self, exc_type, exc_val, exc_tb):
                return None

        mock_db.begin_nested = MagicMock(return_value=AsyncContextManagerMock())

        repository = ApplicationRepository(mock_db)

        # Mock database returns no application
        mock_result = Mock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = mock_result

        # Execute
        result = await repository.update_status(uuid4(), "PRE_APPROVED", 750)

        # Verify
        assert result is False
        mock_db.commit.assert_not_called()

    @pytest.mark.asyncio
    async def test_update_status_already_processed_idempotency(self):
        """Test update_status() idempotency check for already processed application."""
        mock_db = AsyncMock()

        class AsyncContextManagerMock:
            async def __aenter__(self):
                return self

            async def __aexit__(self, exc_type, exc_val, exc_tb):
                return None

        mock_db.begin_nested = MagicMock(return_value=AsyncContextManagerMock())

        repository = ApplicationRepository(mock_db)

        # Mock application already processed
        mock_application = Application(
            id=uuid4(),
            pan_number="ABCDE1234F",
            monthly_income_inr=Decimal("50000"),
            loan_amount_inr=Decimal("200000"),
            loan_type="PERSONAL",
            status="PRE_APPROVED",  # Already processed!
        )

        mock_result = Mock()
        mock_result.scalar_one_or_none.return_value = mock_application
        mock_db.execute.return_value = mock_result

        # Execute
        result = await repository.update_status(uuid4(), "REJECTED", 600)

        # Verify idempotency - returns False, no update
        assert result is False
        assert mock_application.status == "PRE_APPROVED"  # Unchanged
        mock_db.commit.assert_not_called()

    @pytest.mark.asyncio
    async def test_update_status_without_cibil_score(self):
        """Test update_status() without providing CIBIL score."""
        mock_db = AsyncMock()

        class AsyncContextManagerMock:
            async def __aenter__(self):
                return self

            async def __aexit__(self, exc_type, exc_val, exc_tb):
                return None

        mock_db.begin_nested = MagicMock(return_value=AsyncContextManagerMock())

        repository = ApplicationRepository(mock_db)

        mock_application = Application(
            id=uuid4(),
            pan_number="ABCDE1234F",
            monthly_income_inr=Decimal("50000"),
            loan_amount_inr=Decimal("200000"),
            loan_type="PERSONAL",
            status="PENDING",
            cibil_score=None,
        )

        mock_result = Mock()
        mock_result.scalar_one_or_none.return_value = mock_application
        mock_db.execute.return_value = mock_result

        # Execute without cibil_score
        result = await repository.update_status(uuid4(), "MANUAL_REVIEW")

        # Verify
        assert result is True
        assert mock_application.status == "MANUAL_REVIEW"
        assert mock_application.cibil_score is None  # Should remain None

    @pytest.mark.asyncio
    async def test_update_status_database_error(self):
        """Test update_status() handles database errors."""
        mock_db = AsyncMock()
        mock_db.rollback = AsyncMock()  # rollback() is async

        # Make begin_nested raise error when entering context
        class FailingAsyncContextManager:
            async def __aenter__(self):
                raise SQLAlchemyError("Database lock failed")

            async def __aexit__(self, exc_type, exc_val, exc_tb):
                return None

        mock_db.begin_nested = MagicMock(return_value=FailingAsyncContextManager())
        repository = ApplicationRepository(mock_db)

        # Verify exception is raised and rollback is called
        with pytest.raises(DatabaseError, match="Failed to update application"):
            await repository.update_status(uuid4(), "PRE_APPROVED", 750)

        mock_db.rollback.assert_called_once()


class TestApplicationRepositoryGetByStatus:
    """Test suite for get_by_status() method."""

    @pytest.mark.asyncio
    async def test_get_by_status_returns_applications(self):
        """Test getting applications by status."""
        mock_db = AsyncMock()
        repository = ApplicationRepository(mock_db)

        # Mock applications
        mock_apps = [
            Application(
                id=uuid4(),
                pan_number="AAAAA1111A",
                monthly_income_inr=Decimal("50000"),
                loan_amount_inr=Decimal("200000"),
                loan_type="PERSONAL",
                status="PENDING",
            ),
            Application(
                id=uuid4(),
                pan_number="BBBBB2222B",
                monthly_income_inr=Decimal("60000"),
                loan_amount_inr=Decimal("300000"),
                loan_type="HOME",
                status="PENDING",
            ),
        ]

        # Mock database result
        mock_result = Mock()
        mock_scalars = Mock()
        mock_scalars.all.return_value = mock_apps
        mock_result.scalars.return_value = mock_scalars
        mock_db.execute.return_value = mock_result

        # Execute
        result = await repository.get_by_status("PENDING")

        # Verify
        assert len(result) == 2
        assert result == mock_apps
        mock_db.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_by_status_empty_result(self):
        """Test get_by_status() with no matching applications."""
        mock_db = AsyncMock()
        repository = ApplicationRepository(mock_db)

        # Mock empty result
        mock_result = Mock()
        mock_scalars = Mock()
        mock_scalars.all.return_value = []
        mock_result.scalars.return_value = mock_scalars
        mock_db.execute.return_value = mock_result

        # Execute
        result = await repository.get_by_status("REJECTED")

        # Verify
        assert result == []

    @pytest.mark.asyncio
    async def test_get_by_status_with_limit(self):
        """Test get_by_status() respects limit parameter."""
        mock_db = AsyncMock()
        repository = ApplicationRepository(mock_db)

        mock_result = Mock()
        mock_scalars = Mock()
        mock_scalars.all.return_value = []
        mock_result.scalars.return_value = mock_scalars
        mock_db.execute.return_value = mock_result

        # Execute with custom limit
        await repository.get_by_status("PRE_APPROVED", limit=50)

        # Verify execute was called (we can't easily verify the limit in the query)
        mock_db.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_by_status_database_error(self):
        """Test get_by_status() handles database errors."""
        mock_db = AsyncMock()
        mock_db.execute.side_effect = SQLAlchemyError("Database query failed")
        repository = ApplicationRepository(mock_db)

        # Verify exception is raised
        with pytest.raises(DatabaseError, match="Failed to get applications"):
            await repository.get_by_status("PENDING")

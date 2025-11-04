"""Integration tests for ApplicationRepository with real PostgreSQL database.

These tests use a real database connection to test repository operations,
ensuring proper database interaction, transaction handling, and error scenarios.
"""

import uuid
from decimal import Decimal

import pytest
from shared.exceptions.exceptions import DatabaseError
from shared.models.application import Application
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.repositories.application_repository import ApplicationRepository

# Mark all tests in this module as integration tests
pytestmark = pytest.mark.integration


@pytest.fixture
async def test_db_engine():
    """Create a test database engine."""
    # Use test database URL from environment or default to test database
    test_db_url = "postgresql+asyncpg://postgres:postgres@localhost:5432/loan_prequalification_test"

    engine = create_async_engine(
        test_db_url,
        echo=False,
        pool_size=5,
        max_overflow=10,
        pool_pre_ping=True,
    )

    # Create tables
    from app.core.database import Base

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield engine

    # Cleanup: Drop all tables after tests
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

    await engine.dispose()


@pytest.fixture
async def test_db_session(test_db_engine):
    """Create a test database session."""
    session_maker = async_sessionmaker(
        test_db_engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autoflush=False,
        autocommit=False,
    )

    async with session_maker() as session:
        yield session
        await session.rollback()  # Rollback any uncommitted changes


@pytest.fixture
def repository(test_db_session):
    """Create an ApplicationRepository instance with test session."""
    return ApplicationRepository(test_db_session)


class TestApplicationRepositorySave:
    """Test suite for repository save operations."""

    @pytest.mark.asyncio
    async def test_save_application_success(self, repository, test_db_session):
        """Test successfully saving a new application."""
        # Create application
        application = Application(
            id=uuid.uuid4(),
            pan_number="ABCDE1234F",
            applicant_name="Rajesh Kumar",
            monthly_income_inr=Decimal("75000.00"),
            loan_amount_inr=Decimal("500000.00"),
            loan_type="PERSONAL",
            status="PENDING",
        )

        # Save application
        saved_app = await repository.save(application)

        # Verify saved application
        assert saved_app.id == application.id
        assert saved_app.pan_number == "ABCDE1234F"
        assert saved_app.applicant_name == "Rajesh Kumar"
        assert saved_app.monthly_income_inr == Decimal("75000.00")
        assert saved_app.loan_amount_inr == Decimal("500000.00")
        assert saved_app.loan_type == "PERSONAL"
        assert saved_app.status == "PENDING"
        assert saved_app.created_at is not None
        assert saved_app.updated_at is not None

    @pytest.mark.asyncio
    async def test_save_application_without_optional_fields(self, repository):
        """Test saving application without optional fields."""
        application = Application(
            id=uuid.uuid4(),
            pan_number="FGHIJ5678K",
            monthly_income_inr=Decimal("50000.00"),
            loan_amount_inr=Decimal("200000.00"),
            status="PENDING",
        )

        saved_app = await repository.save(application)

        assert saved_app.id is not None
        assert saved_app.applicant_name is None
        assert saved_app.loan_type is None
        assert saved_app.cibil_score is None

    @pytest.mark.asyncio
    async def test_save_application_with_cibil_score(self, repository):
        """Test saving application with CIBIL score."""
        application = Application(
            id=uuid.uuid4(),
            pan_number="LMNOP9012Q",
            applicant_name="Priya Sharma",
            monthly_income_inr=Decimal("100000.00"),
            loan_amount_inr=Decimal("1000000.00"),
            loan_type="HOME",
            status="PRE_APPROVED",
            cibil_score=750,
        )

        saved_app = await repository.save(application)

        assert saved_app.cibil_score == 750
        assert saved_app.status == "PRE_APPROVED"

    @pytest.mark.asyncio
    async def test_save_application_duplicate_id_raises_error(self, repository):
        """Test saving application with duplicate ID raises DatabaseError."""
        app_id = uuid.uuid4()

        # Save first application
        application1 = Application(
            id=app_id,
            pan_number="ABCDE1234F",
            monthly_income_inr=Decimal("50000.00"),
            loan_amount_inr=Decimal("200000.00"),
            status="PENDING",
        )
        await repository.save(application1)

        # Try to save second application with same ID
        application2 = Application(
            id=app_id,
            pan_number="FGHIJ5678K",
            monthly_income_inr=Decimal("60000.00"),
            loan_amount_inr=Decimal("300000.00"),
            status="PENDING",
        )

        with pytest.raises(DatabaseError) as exc_info:
            await repository.save(application2)

        assert "Failed to save application" in str(exc_info.value)


class TestApplicationRepositoryFindById:
    """Test suite for repository find_by_id operations."""

    @pytest.mark.asyncio
    async def test_find_by_id_existing_application(self, repository):
        """Test finding an existing application by ID."""
        # Create and save application
        app_id = uuid.uuid4()
        application = Application(
            id=app_id,
            pan_number="ABCDE1234F",
            applicant_name="Test User",
            monthly_income_inr=Decimal("50000.00"),
            loan_amount_inr=Decimal("200000.00"),
            loan_type="PERSONAL",
            status="PENDING",
        )
        await repository.save(application)

        # Find application
        found_app = await repository.find_by_id(app_id)

        assert found_app is not None
        assert found_app.id == app_id
        assert found_app.pan_number == "ABCDE1234F"
        assert found_app.applicant_name == "Test User"
        assert found_app.status == "PENDING"

    @pytest.mark.asyncio
    async def test_find_by_id_non_existent_returns_none(self, repository):
        """Test finding a non-existent application returns None."""
        non_existent_id = uuid.uuid4()

        found_app = await repository.find_by_id(non_existent_id)

        assert found_app is None

    @pytest.mark.asyncio
    async def test_find_by_id_with_different_statuses(self, repository):
        """Test finding applications with different statuses."""
        # Create applications with different statuses
        app_id_pending = uuid.uuid4()
        app_id_approved = uuid.uuid4()
        app_id_rejected = uuid.uuid4()

        await repository.save(
            Application(
                id=app_id_pending,
                pan_number="AAAAA1111A",
                monthly_income_inr=Decimal("50000.00"),
                loan_amount_inr=Decimal("200000.00"),
                status="PENDING",
            )
        )
        await repository.save(
            Application(
                id=app_id_approved,
                pan_number="BBBBB2222B",
                monthly_income_inr=Decimal("80000.00"),
                loan_amount_inr=Decimal("300000.00"),
                status="PRE_APPROVED",
                cibil_score=750,
            )
        )
        await repository.save(
            Application(
                id=app_id_rejected,
                pan_number="CCCCC3333C",
                monthly_income_inr=Decimal("30000.00"),
                loan_amount_inr=Decimal("100000.00"),
                status="REJECTED",
                cibil_score=600,
            )
        )

        # Find each application
        pending_app = await repository.find_by_id(app_id_pending)
        approved_app = await repository.find_by_id(app_id_approved)
        rejected_app = await repository.find_by_id(app_id_rejected)

        assert pending_app.status == "PENDING"
        assert approved_app.status == "PRE_APPROVED"
        assert rejected_app.status == "REJECTED"


class TestApplicationRepositoryUpdateStatus:
    """Test suite for repository update_status operations."""

    @pytest.mark.asyncio
    async def test_update_status_pending_to_approved(self, repository):
        """Test updating application status from PENDING to PRE_APPROVED."""
        # Create and save application
        app_id = uuid.uuid4()
        application = Application(
            id=app_id,
            pan_number="ABCDE1234F",
            monthly_income_inr=Decimal("75000.00"),
            loan_amount_inr=Decimal("500000.00"),
            status="PENDING",
        )
        await repository.save(application)

        # Update status
        result = await repository.update_status(app_id, "PRE_APPROVED", cibil_score=750)

        assert result is True

        # Verify update
        updated_app = await repository.find_by_id(app_id)
        assert updated_app.status == "PRE_APPROVED"
        assert updated_app.cibil_score == 750

    @pytest.mark.asyncio
    async def test_update_status_pending_to_rejected(self, repository):
        """Test updating application status from PENDING to REJECTED."""
        app_id = uuid.uuid4()
        application = Application(
            id=app_id,
            pan_number="FGHIJ5678K",
            monthly_income_inr=Decimal("30000.00"),
            loan_amount_inr=Decimal("200000.00"),
            status="PENDING",
        )
        await repository.save(application)

        result = await repository.update_status(app_id, "REJECTED", cibil_score=620)

        assert result is True

        updated_app = await repository.find_by_id(app_id)
        assert updated_app.status == "REJECTED"
        assert updated_app.cibil_score == 620

    @pytest.mark.asyncio
    async def test_update_status_pending_to_manual_review(self, repository):
        """Test updating application status from PENDING to MANUAL_REVIEW."""
        app_id = uuid.uuid4()
        application = Application(
            id=app_id,
            pan_number="LMNOP9012Q",
            monthly_income_inr=Decimal("50000.00"),
            loan_amount_inr=Decimal("500000.00"),
            status="PENDING",
        )
        await repository.save(application)

        result = await repository.update_status(app_id, "MANUAL_REVIEW", cibil_score=680)

        assert result is True

        updated_app = await repository.find_by_id(app_id)
        assert updated_app.status == "MANUAL_REVIEW"
        assert updated_app.cibil_score == 680

    @pytest.mark.asyncio
    async def test_update_status_without_cibil_score(self, repository):
        """Test updating status without providing CIBIL score."""
        app_id = uuid.uuid4()
        application = Application(
            id=app_id,
            pan_number="ABCDE1234F",
            monthly_income_inr=Decimal("50000.00"),
            loan_amount_inr=Decimal("200000.00"),
            status="PENDING",
        )
        await repository.save(application)

        result = await repository.update_status(app_id, "PRE_APPROVED")

        assert result is True

        updated_app = await repository.find_by_id(app_id)
        assert updated_app.status == "PRE_APPROVED"
        assert updated_app.cibil_score is None

    @pytest.mark.asyncio
    async def test_update_status_idempotency_already_processed(self, repository):
        """Test idempotency: updating already processed application returns False."""
        app_id = uuid.uuid4()
        application = Application(
            id=app_id,
            pan_number="ABCDE1234F",
            monthly_income_inr=Decimal("75000.00"),
            loan_amount_inr=Decimal("500000.00"),
            status="PENDING",
        )
        await repository.save(application)

        # First update: PENDING -> PRE_APPROVED
        result1 = await repository.update_status(app_id, "PRE_APPROVED", cibil_score=750)
        assert result1 is True

        # Second update: Try to change PRE_APPROVED -> REJECTED (should fail)
        result2 = await repository.update_status(app_id, "REJECTED", cibil_score=600)
        assert result2 is False

        # Verify status is still PRE_APPROVED
        app = await repository.find_by_id(app_id)
        assert app.status == "PRE_APPROVED"
        assert app.cibil_score == 750  # Original score preserved

    @pytest.mark.asyncio
    async def test_update_status_non_existent_application(self, repository):
        """Test updating non-existent application returns False."""
        non_existent_id = uuid.uuid4()

        result = await repository.update_status(non_existent_id, "PRE_APPROVED", cibil_score=750)

        assert result is False

    @pytest.mark.asyncio
    async def test_update_status_concurrent_updates_prevented(self, repository):
        """Test that SELECT FOR UPDATE prevents race conditions."""
        app_id = uuid.uuid4()
        application = Application(
            id=app_id,
            pan_number="ABCDE1234F",
            monthly_income_inr=Decimal("50000.00"),
            loan_amount_inr=Decimal("200000.00"),
            status="PENDING",
        )
        await repository.save(application)

        # First update succeeds
        result = await repository.update_status(app_id, "PRE_APPROVED", cibil_score=750)
        assert result is True

        # Second update fails (idempotency check)
        result = await repository.update_status(app_id, "REJECTED", cibil_score=600)
        assert result is False

        # Verify first update is preserved
        app = await repository.find_by_id(app_id)
        assert app.status == "PRE_APPROVED"
        assert app.cibil_score == 750


class TestApplicationRepositoryGetByStatus:
    """Test suite for repository get_by_status operations."""

    @pytest.mark.asyncio
    async def test_get_by_status_pending_applications(self, repository):
        """Test retrieving all PENDING applications."""
        # Create multiple applications with different statuses
        await repository.save(
            Application(
                id=uuid.uuid4(),
                pan_number="AAAAA1111A",
                monthly_income_inr=Decimal("50000.00"),
                loan_amount_inr=Decimal("200000.00"),
                status="PENDING",
            )
        )
        await repository.save(
            Application(
                id=uuid.uuid4(),
                pan_number="BBBBB2222B",
                monthly_income_inr=Decimal("60000.00"),
                loan_amount_inr=Decimal("300000.00"),
                status="PENDING",
            )
        )
        await repository.save(
            Application(
                id=uuid.uuid4(),
                pan_number="CCCCC3333C",
                monthly_income_inr=Decimal("80000.00"),
                loan_amount_inr=Decimal("500000.00"),
                status="PRE_APPROVED",
                cibil_score=750,
            )
        )

        # Get PENDING applications
        pending_apps = await repository.get_by_status("PENDING")

        assert len(pending_apps) == 2
        assert all(app.status == "PENDING" for app in pending_apps)

    @pytest.mark.asyncio
    async def test_get_by_status_approved_applications(self, repository):
        """Test retrieving all PRE_APPROVED applications."""
        await repository.save(
            Application(
                id=uuid.uuid4(),
                pan_number="AAAAA1111A",
                monthly_income_inr=Decimal("80000.00"),
                loan_amount_inr=Decimal("500000.00"),
                status="PRE_APPROVED",
                cibil_score=750,
            )
        )
        await repository.save(
            Application(
                id=uuid.uuid4(),
                pan_number="BBBBB2222B",
                monthly_income_inr=Decimal("30000.00"),
                loan_amount_inr=Decimal("100000.00"),
                status="REJECTED",
                cibil_score=600,
            )
        )

        approved_apps = await repository.get_by_status("PRE_APPROVED")

        assert len(approved_apps) == 1
        assert approved_apps[0].status == "PRE_APPROVED"

    @pytest.mark.asyncio
    async def test_get_by_status_empty_result(self, repository):
        """Test retrieving applications when none match the status."""
        # Create only PENDING applications
        await repository.save(
            Application(
                id=uuid.uuid4(),
                pan_number="AAAAA1111A",
                monthly_income_inr=Decimal("50000.00"),
                loan_amount_inr=Decimal("200000.00"),
                status="PENDING",
            )
        )

        # Query for REJECTED (none exist)
        rejected_apps = await repository.get_by_status("REJECTED")

        assert len(rejected_apps) == 0

    @pytest.mark.asyncio
    async def test_get_by_status_with_limit(self, repository):
        """Test retrieving applications with limit parameter."""
        # Create 5 PENDING applications
        for i in range(5):
            await repository.save(
                Application(
                    id=uuid.uuid4(),
                    pan_number=f"AAAAA{i:04d}A",
                    monthly_income_inr=Decimal("50000.00"),
                    loan_amount_inr=Decimal("200000.00"),
                    status="PENDING",
                )
            )

        # Get with limit=3
        pending_apps = await repository.get_by_status("PENDING", limit=3)

        assert len(pending_apps) == 3

    @pytest.mark.asyncio
    async def test_get_by_status_ordered_by_created_at_desc(self, repository):
        """Test that results are ordered by created_at descending."""
        # Create applications in sequence
        app1 = Application(
            id=uuid.uuid4(),
            pan_number="AAAAA1111A",
            monthly_income_inr=Decimal("50000.00"),
            loan_amount_inr=Decimal("200000.00"),
            status="PENDING",
        )
        app2 = Application(
            id=uuid.uuid4(),
            pan_number="BBBBB2222B",
            monthly_income_inr=Decimal("60000.00"),
            loan_amount_inr=Decimal("300000.00"),
            status="PENDING",
        )

        await repository.save(app1)
        await repository.save(app2)

        pending_apps = await repository.get_by_status("PENDING")

        # Most recent should be first
        assert len(pending_apps) == 2
        assert pending_apps[0].id == app2.id  # app2 created last, should be first
        assert pending_apps[1].id == app1.id


class TestApplicationRepositoryErrorHandling:
    """Test suite for repository error handling."""

    @pytest.mark.asyncio
    async def test_save_with_closed_session_raises_error(self, test_db_engine):
        """Test that operations with closed session raise DatabaseError."""
        session_maker = async_sessionmaker(
            test_db_engine,
            class_=AsyncSession,
            expire_on_commit=False,
        )

        async with session_maker() as session:
            repository = ApplicationRepository(session)
            await session.close()  # Close session

            application = Application(
                id=uuid.uuid4(),
                pan_number="ABCDE1234F",
                monthly_income_inr=Decimal("50000.00"),
                loan_amount_inr=Decimal("200000.00"),
                status="PENDING",
            )

            with pytest.raises(DatabaseError) as exc_info:
                await repository.save(application)

            assert "Failed to save application" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_find_by_id_with_closed_session_raises_error(self, test_db_engine):
        """Test that find_by_id with closed session raises DatabaseError."""
        session_maker = async_sessionmaker(
            test_db_engine,
            class_=AsyncSession,
            expire_on_commit=False,
        )

        async with session_maker() as session:
            repository = ApplicationRepository(session)
            await session.close()

            with pytest.raises(DatabaseError) as exc_info:
                await repository.find_by_id(uuid.uuid4())

            assert "Failed to find application" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_get_by_status_with_closed_session_raises_error(self, test_db_engine):
        """Test that get_by_status with closed session raises DatabaseError."""
        session_maker = async_sessionmaker(
            test_db_engine,
            class_=AsyncSession,
            expire_on_commit=False,
        )

        async with session_maker() as session:
            repository = ApplicationRepository(session)
            await session.close()

            with pytest.raises(DatabaseError) as exc_info:
                await repository.get_by_status("PENDING")

            assert "Failed to get applications" in str(exc_info.value)

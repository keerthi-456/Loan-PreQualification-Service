"""Repository layer for application database operations.

This module provides async database access methods for the Application model,
following the Repository pattern for separation of concerns.
"""

from uuid import UUID

from shared.core.logging import get_logger
from shared.exceptions.exceptions import DatabaseError
from shared.models.application import Application
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

logger = get_logger(__name__)


class ApplicationRepository:
    """Repository for managing Application database operations."""

    def __init__(self, db: AsyncSession):
        """
        Initialize repository with database session.

        Args:
            db: Async SQLAlchemy database session
        """
        self.db = db

    async def save(self, application: Application) -> Application:
        """
        Save a new application to the database.

        Args:
            application: Application model instance to save

        Returns:
            Application: Saved application with generated ID

        Raises:
            DatabaseError: If database operation fails
        """
        try:
            self.db.add(application)
            await self.db.commit()
            await self.db.refresh(application)

            logger.info(
                "Application saved to database",
                application_id=str(application.id),
                status=application.status,
            )

            return application

        except SQLAlchemyError as e:
            await self.db.rollback()
            logger.error(
                "Failed to save application",
                error=str(e),
                application_id=str(application.id) if application.id else "unknown",
            )
            raise DatabaseError(f"Failed to save application: {str(e)}")

    async def find_by_id(self, application_id: UUID) -> Application | None:
        """
        Find an application by its ID.

        Args:
            application_id: UUID of the application to find

        Returns:
            Application | None: Application if found, None otherwise

        Raises:
            DatabaseError: If database operation fails
        """
        try:
            query = select(Application).where(Application.id == application_id)
            result = await self.db.execute(query)
            application = result.scalar_one_or_none()

            if application:
                logger.debug("Application found", application_id=str(application_id))
            else:
                logger.debug("Application not found", application_id=str(application_id))

            return application

        except SQLAlchemyError as e:
            logger.error(
                "Failed to find application",
                error=str(e),
                application_id=str(application_id),
            )
            raise DatabaseError(f"Failed to find application: {str(e)}")

    async def update_status(
        self, application_id: UUID, status: str, cibil_score: int | None = None
    ) -> bool:
        """
        Update application status and optionally CIBIL score.

        This method implements idempotency using SELECT FOR UPDATE to prevent
        race conditions. It only updates applications in PENDING status.

        Args:
            application_id: UUID of application to update
            status: New status (PRE_APPROVED, REJECTED, MANUAL_REVIEW)
            cibil_score: CIBIL score to set (optional)

        Returns:
            bool: True if updated, False if already processed or not found

        Raises:
            DatabaseError: If database operation fails
        """
        try:
            async with self.db.begin_nested():
                # Lock row to prevent concurrent updates
                query = (
                    select(Application).where(Application.id == application_id).with_for_update()
                )
                result = await self.db.execute(query)
                application = result.scalar_one_or_none()

                if not application:
                    logger.warning(
                        "Cannot update: Application not found",
                        application_id=str(application_id),
                    )
                    return False

                # Idempotency check: only update if still PENDING
                if application.status != "PENDING":
                    logger.warning(
                        "Cannot update: Application already processed (idempotency check)",
                        application_id=str(application_id),
                        current_status=application.status,
                        attempted_status=status,
                    )
                    return False

                # Update status and CIBIL score
                application.status = status
                if cibil_score is not None:
                    application.cibil_score = cibil_score

                # updated_at will be automatically updated by database trigger

            await self.db.commit()

            logger.info(
                "Application status updated",
                application_id=str(application_id),
                new_status=status,
                cibil_score=cibil_score,
            )

            return True

        except SQLAlchemyError as e:
            await self.db.rollback()
            logger.error(
                "Failed to update application status",
                error=str(e),
                application_id=str(application_id),
            )
            raise DatabaseError(f"Failed to update application: {str(e)}")

    async def get_by_status(self, status: str, limit: int = 100) -> list[Application]:
        """
        Get applications by status (for monitoring/debugging).

        Args:
            status: Status to filter by
            limit: Maximum number of applications to return

        Returns:
            list[Application]: List of applications with given status

        Raises:
            DatabaseError: If database operation fails
        """
        try:
            query = (
                select(Application)
                .where(Application.status == status)
                .order_by(Application.created_at.desc())
                .limit(limit)
            )
            result = await self.db.execute(query)
            applications = result.scalars().all()

            logger.debug(
                "Applications retrieved by status",
                status=status,
                count=len(applications),
            )

            return list(applications)

        except SQLAlchemyError as e:
            logger.error("Failed to get applications by status", error=str(e), status=status)
            raise DatabaseError(f"Failed to get applications: {str(e)}")

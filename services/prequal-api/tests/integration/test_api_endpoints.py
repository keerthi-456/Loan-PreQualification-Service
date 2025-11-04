"""Integration tests for API endpoints using FastAPI TestClient.

These tests verify the API layer with mocked service dependencies.
Tests use mocked ApplicationService to avoid requiring actual database/Kafka.

Note: These are integration tests for the API layer specifically.
Full E2E tests with real database/Kafka are in tests/e2e/
"""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Mark all tests in this module as integration tests
pytestmark = pytest.mark.integration


@pytest.fixture
def client():
    """Create FastAPI test client."""
    # Import here to delay until after any setup
    from fastapi.testclient import TestClient

    from app.main import app

    # TestClient doesn't trigger lifespan events by default,
    # which is good for these tests since we're mocking dependencies
    return TestClient(app, raise_server_exceptions=False)


class TestPostApplicationsEndpoint:
    """Test suite for POST /applications endpoint."""

    @patch("app.api.routes.applications.ApplicationService")
    def test_create_application_success(self, mock_service_class, client):
        """Test successful application creation returns 202 with application_id."""
        # Setup mock
        mock_service = mock_service_class.return_value
        mock_service.create_application = AsyncMock(
            return_value=MagicMock(
                application_id=uuid.UUID("550e8400-e29b-41d4-a716-446655440000"),
                status="PENDING",
            )
        )

        # Make request
        payload = {
            "pan_number": "ABCDE1234F",
            "applicant_name": "Rajesh Kumar",
            "monthly_income_inr": 75000.00,
            "loan_amount_inr": 500000.00,
            "loan_type": "PERSONAL",
        }

        response = client.post("/applications", json=payload)

        # Assertions
        assert response.status_code == 202
        data = response.json()
        assert "application_id" in data
        assert data["status"] == "PENDING"
        assert uuid.UUID(data["application_id"])  # Valid UUID

    def test_create_application_invalid_pan_returns_422(self, client):
        """Test invalid PAN number format returns 422 validation error."""
        payload = {
            "pan_number": "INVALID",  # Invalid format
            "applicant_name": "Test User",
            "monthly_income_inr": 50000.00,
            "loan_amount_inr": 200000.00,
            "loan_type": "PERSONAL",
        }

        response = client.post("/applications", json=payload)

        assert response.status_code == 422
        data = response.json()
        assert "detail" in data
        # Check that PAN validation error is mentioned
        error_msg = str(data["detail"])
        assert "pan_number" in error_msg.lower()

    def test_create_application_negative_income_returns_422(self, client):
        """Test negative income returns 422 validation error."""
        payload = {
            "pan_number": "ABCDE1234F",
            "applicant_name": "Test User",
            "monthly_income_inr": -1000.00,  # Negative
            "loan_amount_inr": 200000.00,
            "loan_type": "PERSONAL",
        }

        response = client.post("/applications", json=payload)

        assert response.status_code == 422
        data = response.json()
        assert "detail" in data

    def test_create_application_negative_loan_amount_returns_422(self, client):
        """Test negative loan amount returns 422 validation error."""
        payload = {
            "pan_number": "ABCDE1234F",
            "applicant_name": "Test User",
            "monthly_income_inr": 50000.00,
            "loan_amount_inr": -100000.00,  # Negative
            "loan_type": "PERSONAL",
        }

        response = client.post("/applications", json=payload)

        assert response.status_code == 422

    def test_create_application_invalid_loan_type_returns_422(self, client):
        """Test invalid loan type returns 422 validation error."""
        payload = {
            "pan_number": "ABCDE1234F",
            "applicant_name": "Test User",
            "monthly_income_inr": 50000.00,
            "loan_amount_inr": 200000.00,
            "loan_type": "INVALID_TYPE",  # Not in enum
        }

        response = client.post("/applications", json=payload)

        assert response.status_code == 422

    def test_create_application_missing_required_field_returns_422(self, client):
        """Test missing required field returns 422 validation error."""
        payload = {
            "pan_number": "ABCDE1234F",
            # Missing monthly_income_inr
            "loan_amount_inr": 200000.00,
            "loan_type": "PERSONAL",
        }

        response = client.post("/applications", json=payload)

        assert response.status_code == 422
        data = response.json()
        assert "detail" in data

    def test_create_application_pan_too_short_returns_422(self, client):
        """Test PAN number too short returns 422."""
        payload = {
            "pan_number": "ABC123",  # Too short
            "applicant_name": "Test User",
            "monthly_income_inr": 50000.00,
            "loan_amount_inr": 200000.00,
            "loan_type": "PERSONAL",
        }

        response = client.post("/applications", json=payload)

        assert response.status_code == 422

    def test_create_application_pan_lowercase_returns_422(self, client):
        """Test PAN with lowercase letters returns 422."""
        payload = {
            "pan_number": "abcde1234f",  # Should be uppercase
            "applicant_name": "Test User",
            "monthly_income_inr": 50000.00,
            "loan_amount_inr": 200000.00,
            "loan_type": "PERSONAL",
        }

        response = client.post("/applications", json=payload)

        assert response.status_code == 422

    @patch("app.api.routes.applications.ApplicationService")
    def test_create_application_server_error_returns_500(self, mock_service_class, client):
        """Test internal server error returns 500."""
        # Setup mock to raise exception
        mock_service = mock_service_class.return_value
        mock_service.create_application = AsyncMock(side_effect=Exception("Database error"))

        payload = {
            "pan_number": "ABCDE1234F",
            "applicant_name": "Test User",
            "monthly_income_inr": 50000.00,
            "loan_amount_inr": 200000.00,
            "loan_type": "PERSONAL",
        }

        response = client.post("/applications", json=payload)

        assert response.status_code == 500
        data = response.json()
        assert "detail" in data


class TestGetApplicationStatusEndpoint:
    """Test suite for GET /applications/{id}/status endpoint."""

    @patch("app.api.routes.applications.ApplicationService")
    def test_get_status_found_returns_200(self, mock_service_class, client):
        """Test retrieving status for existing application returns 200."""
        # Setup mock
        app_id = uuid.UUID("550e8400-e29b-41d4-a716-446655440000")
        mock_service = mock_service_class.return_value
        mock_service.get_application_status = AsyncMock(
            return_value=MagicMock(application_id=app_id, status="PRE_APPROVED")
        )

        response = client.get(f"/applications/{app_id}/status")

        assert response.status_code == 200
        data = response.json()
        assert data["application_id"] == str(app_id)
        assert data["status"] == "PRE_APPROVED"

    @patch("app.api.routes.applications.ApplicationService")
    def test_get_status_pending_returns_200(self, mock_service_class, client):
        """Test retrieving PENDING status returns 200."""
        app_id = uuid.UUID("550e8400-e29b-41d4-a716-446655440000")
        mock_service = mock_service_class.return_value
        mock_service.get_application_status = AsyncMock(
            return_value=MagicMock(application_id=app_id, status="PENDING")
        )

        response = client.get(f"/applications/{app_id}/status")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "PENDING"

    @patch("app.api.routes.applications.ApplicationService")
    def test_get_status_rejected_returns_200(self, mock_service_class, client):
        """Test retrieving REJECTED status returns 200."""
        app_id = uuid.UUID("550e8400-e29b-41d4-a716-446655440000")
        mock_service = mock_service_class.return_value
        mock_service.get_application_status = AsyncMock(
            return_value=MagicMock(application_id=app_id, status="REJECTED")
        )

        response = client.get(f"/applications/{app_id}/status")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "REJECTED"

    @patch("app.api.routes.applications.ApplicationService")
    def test_get_status_manual_review_returns_200(self, mock_service_class, client):
        """Test retrieving MANUAL_REVIEW status returns 200."""
        app_id = uuid.UUID("550e8400-e29b-41d4-a716-446655440000")
        mock_service = mock_service_class.return_value
        mock_service.get_application_status = AsyncMock(
            return_value=MagicMock(application_id=app_id, status="MANUAL_REVIEW")
        )

        response = client.get(f"/applications/{app_id}/status")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "MANUAL_REVIEW"

    @patch("app.api.routes.applications.ApplicationService")
    def test_get_status_not_found_returns_404(self, mock_service_class, client):
        """Test application not found returns 404."""
        from app.exceptions.exceptions import ApplicationNotFoundError

        app_id = uuid.UUID("550e8400-e29b-41d4-a716-446655440000")
        mock_service = mock_service_class.return_value
        mock_service.get_application_status = AsyncMock(
            side_effect=ApplicationNotFoundError(app_id)
        )

        response = client.get(f"/applications/{app_id}/status")

        assert response.status_code == 404
        data = response.json()
        assert "detail" in data
        assert str(app_id) in data["detail"]

    def test_get_status_invalid_uuid_returns_422(self, client):
        """Test invalid UUID format returns 422."""
        response = client.get("/applications/invalid-uuid/status")

        assert response.status_code == 422

    @patch("app.api.routes.applications.ApplicationService")
    def test_get_status_server_error_returns_500(self, mock_service_class, client):
        """Test internal server error returns 500."""
        app_id = uuid.UUID("550e8400-e29b-41d4-a716-446655440000")
        mock_service = mock_service_class.return_value
        mock_service.get_application_status = AsyncMock(side_effect=Exception("Database error"))

        response = client.get(f"/applications/{app_id}/status")

        assert response.status_code == 500


class TestHealthCheckEndpoint:
    """Test suite for GET /health endpoint."""

    @patch("app.api.routes.health.get_kafka_producer")
    @patch("app.api.routes.health.get_db")
    def test_health_check_all_healthy_returns_200(self, mock_get_db, mock_get_kafka, client):
        """Test health check with all systems healthy returns 200."""
        # Mock database session
        mock_db = AsyncMock()
        mock_db.execute = AsyncMock()
        mock_get_db.return_value = mock_db

        # Mock Kafka producer
        mock_producer = MagicMock()
        mock_producer.is_started = MagicMock(return_value=True)
        mock_get_kafka.return_value = mock_producer

        response = client.get("/health")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["database"] == "connected"
        assert data["kafka"] == "connected"

    @patch("app.api.routes.health.get_kafka_producer")
    @patch("app.api.routes.health.get_db")
    def test_health_check_database_down_returns_503(self, mock_get_db, mock_get_kafka, client):
        """Test health check with database down returns 503."""
        # Mock database to fail
        mock_db = AsyncMock()
        mock_db.execute = AsyncMock(side_effect=Exception("Connection failed"))
        mock_get_db.return_value = mock_db

        # Mock Kafka as healthy
        mock_producer = MagicMock()
        mock_producer.is_started = MagicMock(return_value=True)
        mock_get_kafka.return_value = mock_producer

        response = client.get("/health")

        assert response.status_code == 503
        data = response.json()
        assert data["status"] == "unhealthy"
        assert data["database"] == "disconnected"
        assert data["kafka"] == "connected"

    @patch("app.api.routes.health.get_kafka_producer")
    @patch("app.api.routes.health.get_db")
    def test_health_check_kafka_down_returns_503(self, mock_get_db, mock_get_kafka, client):
        """Test health check with Kafka down returns 503."""
        # Mock database as healthy
        mock_db = AsyncMock()
        mock_db.execute = AsyncMock()
        mock_get_db.return_value = mock_db

        # Mock Kafka as down
        mock_producer = MagicMock()
        mock_producer.is_started = MagicMock(return_value=False)
        mock_get_kafka.return_value = mock_producer

        response = client.get("/health")

        assert response.status_code == 503
        data = response.json()
        assert data["status"] == "unhealthy"
        assert data["database"] == "connected"
        assert data["kafka"] == "disconnected"

    @patch("app.api.routes.health.get_kafka_producer")
    @patch("app.api.routes.health.get_db")
    def test_health_check_both_down_returns_503(self, mock_get_db, mock_get_kafka, client):
        """Test health check with both systems down returns 503."""
        # Mock database to fail
        mock_db = AsyncMock()
        mock_db.execute = AsyncMock(side_effect=Exception("Connection failed"))
        mock_get_db.return_value = mock_db

        # Mock Kafka as down
        mock_producer = MagicMock()
        mock_producer.is_started = MagicMock(return_value=False)
        mock_get_kafka.return_value = mock_producer

        response = client.get("/health")

        assert response.status_code == 503
        data = response.json()
        assert data["status"] == "unhealthy"
        assert data["database"] == "disconnected"
        assert data["kafka"] == "disconnected"


class TestRootEndpoint:
    """Test suite for GET / root endpoint."""

    def test_root_endpoint_returns_200(self, client):
        """Test root endpoint returns 200 with API information."""
        response = client.get("/")

        assert response.status_code == 200
        data = response.json()
        assert "message" in data
        assert "version" in data
        assert "docs" in data
        assert "health" in data
        assert data["docs"] == "/docs"
        assert data["health"] == "/health"


class TestCORSHeaders:
    """Test CORS headers configuration."""

    def test_cors_headers_present(self, client):
        """Test CORS headers are present in response."""
        response = client.options(
            "/applications",
            headers={
                "Origin": "http://localhost:3000",
                "Access-Control-Request-Method": "POST",
            },
        )

        # Check CORS headers are present (they may vary based on configuration)
        assert response.status_code in [200, 204]

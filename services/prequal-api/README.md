# prequal-api

FastAPI REST API service for loan prequalification applications.

## Overview

This microservice provides a REST API for:
- Submitting loan prequalification applications
- Checking application status
- Health checks

## API Endpoints

### POST /applications
Submit a new loan prequalification application.

**Request:**
```json
{
  "pan_number": "ABCDE1234F",
  "applicant_name": "John Doe",
  "monthly_income_inr": 50000,
  "loan_amount_inr": 200000,
  "loan_type": "PERSONAL"
}
```

**Response (202 Accepted):**
```json
{
  "application_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "PENDING"
}
```

### GET /applications/{application_id}/status
Check the status of an application.

**Response (200 OK):**
```json
{
  "application_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "PRE_APPROVED"
}
```

### GET /health
Health check endpoint.

**Response (200 OK):**
```json
{
  "status": "healthy",
  "database": "connected",
  "kafka": "connected"
}
```

## Dependencies

- FastAPI - REST API framework
- PostgreSQL - Database (via shared library)
- Kafka - Event publishing
- Shared library - Common models, schemas, config

## Environment Variables

```bash
# Database
DATABASE_URL=postgresql+asyncpg://user:pass@localhost:5432/dbname

# Kafka
KAFKA_BOOTSTRAP_SERVERS=localhost:9092
KAFKA_TOPIC_APPLICATIONS=loan_applications_submitted

# API Config
API_HOST=0.0.0.0
API_PORT=8000
API_RELOAD=false

# Logging
LOG_LEVEL=INFO
```

## Running Locally

### Install Dependencies
```bash
cd services/prequal-api
poetry install
```

### Run Development Server
```bash
poetry run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### Run Tests
```bash
poetry run pytest tests/ -v
```

## Docker

### Build Image
```bash
docker build -f services/prequal-api/Dockerfile -t prequal-api .
```

### Run Container
```bash
docker run -p 8000:8000 \
  -e DATABASE_URL=postgresql+asyncpg://... \
  -e KAFKA_BOOTSTRAP_SERVERS=kafka:9092 \
  prequal-api
```

## API Documentation

Interactive API documentation is available at:
- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`

## Architecture

```
prequal-api/
├── app/
│   ├── api/routes/          - FastAPI route handlers
│   ├── services/            - Application service layer
│   ├── repositories/        - Database access layer
│   ├── kafka/               - Kafka producer
│   └── main.py              - FastAPI application entry point
└── tests/
    ├── unit/                - Unit tests
    └── integration/         - Integration tests
```

## Event Publishing

When an application is submitted, this service publishes a message to the `loan_applications_submitted` Kafka topic, which triggers the credit-service to calculate the CIBIL score.

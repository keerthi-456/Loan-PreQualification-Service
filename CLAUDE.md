# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**Loan Prequalification Service** - An event-driven microservices system for processing loan prequalification applications in the Indian financial market. The system uses FastAPI, PostgreSQL, and Apache Kafka to provide fast, asynchronous loan eligibility decisions based on PAN numbers and CIBIL score checks.

## Architecture

### High-Level Design

The system consists of three independent microservices communicating via Kafka:

1. **prequal-api (FastAPI)**: REST API that accepts loan applications, stores them in PostgreSQL with `PENDING` status, and publishes to Kafka
2. **credit-service**: Kafka consumer that simulates CIBIL score checks based on PAN number and income
3. **decision-service**: Kafka consumer that applies business rules and updates application status to `PRE_APPROVED`, `REJECTED`, or `MANUAL_REVIEW`

### Event Flow

```
User → POST /applications → prequal-api → PostgreSQL (PENDING) → Kafka (loan_applications_submitted)
→ credit-service → Kafka (credit_reports_generated)
→ decision-service → PostgreSQL (final status)
User → GET /applications/{id}/status → prequal-api → PostgreSQL → Response
```

### Technology Stack

- **Python**: 3.11+
- **Framework**: FastAPI 0.104+ with async/await
- **Database**: PostgreSQL with asyncpg + SQLAlchemy 2.0 (async)
- **Message Broker**: Apache Kafka (kafka-python or aiokafka)
- **Dependency Management**: Poetry
- **Testing**: pytest, pytest-asyncio, pytest-cov (85%+ coverage required)
- **Code Quality**: Ruff (linting), Black (formatting), mypy (type checking)
- **Orchestration**: Docker Compose for local development

## Development Commands

**Note**: The project is currently in the design phase. Once implemented, these commands will be used:

### Testing
```bash
make test                  # Run all tests with coverage (requires 85%+ coverage)
make test-unit            # Run unit tests only
make test-integration     # Run integration tests with Docker Compose
pytest tests/unit/        # Run specific test directory
```

### Code Quality
```bash
make lint                 # Run Ruff linting
make format               # Run Black formatting
make type-check          # Run mypy type checking
pre-commit run --all-files  # Run all pre-commit hooks
```

### Local Development
```bash
make run-local           # Start all services with docker-compose
make db-migrate          # Run Alembic database migrations
docker-compose up        # Start PostgreSQL + Kafka + all services
docker-compose down      # Stop all services
```

### Database
```bash
alembic revision --autogenerate -m "description"  # Create new migration
alembic upgrade head     # Apply migrations
```

## Project Structure

**Expected structure** (to be implemented following `/development` command guidelines):

```
project/
├── src/
│   └── app/
│       ├── api/
│       │   ├── routes/          # FastAPI routers for REST endpoints
│       │   ├── dependencies.py  # Dependency injection (DB sessions, services)
│       │   └── middleware.py    # Custom middleware
│       ├── services/            # Business logic layer (async)
│       ├── repositories/        # Data access layer (async DB operations)
│       ├── models/              # SQLAlchemy ORM models
│       ├── schemas/             # Pydantic models for validation
│       ├── kafka/
│       │   ├── producer.py      # Kafka message producer
│       │   └── consumer.py      # Kafka consumer with graceful shutdown
│       ├── core/
│       │   ├── config.py        # Environment configuration
│       │   ├── database.py      # Async database setup & pooling
│       │   └── logging.py       # Structured logging with correlation IDs
│       ├── exceptions/          # Custom exception classes
│       └── main.py              # FastAPI application entry point
├── tests/
│   ├── unit/                    # Unit tests with mocked dependencies
│   ├── integration/             # Integration tests with Docker Compose
│   └── conftest.py              # Pytest fixtures
├── alembic/                     # Database migration scripts
├── docker/                      # Service-specific Dockerfiles
├── docker-compose.yml           # Local orchestration (PostgreSQL, Kafka, Zookeeper, services)
├── pyproject.toml               # Poetry dependencies & tool configuration
├── Makefile                     # Standardized development commands
├── .pre-commit-config.yaml      # Ruff, Black, mypy hooks
└── README.md
```

## Data Model

### applications Table (PostgreSQL)

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | UUID | Primary Key | Unique application identifier |
| pan_number | VARCHAR(10) | Not Null | Indian PAN card number |
| applicant_name | VARCHAR(255) | | Applicant's full name |
| monthly_income_inr | DECIMAL(12,2) | Not Null | Gross monthly income in INR |
| loan_amount_inr | DECIMAL(12,2) | Not Null | Requested loan amount |
| loan_type | VARCHAR(20) | | PERSONAL, HOME, or AUTO |
| status | VARCHAR(20) | Not Null | PENDING → PRE_APPROVED/REJECTED/MANUAL_REVIEW |
| cibil_score | INTEGER | Nullable | Simulated score (300-900) |
| created_at | TIMESTAMP | Default: NOW() | Application creation time |
| updated_at | TIMESTAMP | Default: NOW() | Last update time |

**Index**: Create index on `pan_number` for faster lookups

## Business Logic

### CIBIL Score Simulation (credit-service)

Special test PANs:
- `ABCDE1234F` → 790 (pre-approved candidate)
- `FGHIJ5678K` → 610 (borderline/reject candidate)

Default scoring algorithm:
```
base_score = 650
if monthly_income > 75000: +40
if monthly_income < 30000: -20
if loan_type == "PERSONAL": -10 (unsecured)
if loan_type == "HOME": +10 (secured)
random adjustment: -5 to +5
final_score = clamp(result, 300, 900)
```

### Decision Rules (decision-service)

```
if cibil_score < 650:
    status = REJECTED

elif monthly_income > (loan_amount / 48):  # 4-year loan EMI check
    status = PRE_APPROVED

else:
    status = MANUAL_REVIEW  # Good score but tight income ratio
```

## Kafka Topics & Message Schemas

### Topic: loan_applications_submitted
Published by: prequal-api
Consumed by: credit-service

Message schema (Pydantic):
```python
{
  "application_id": "uuid",
  "pan_number": "string",
  "applicant_name": "string",
  "monthly_income_inr": "decimal",
  "loan_amount_inr": "decimal",
  "loan_type": "string"
}
```

### Topic: credit_reports_generated
Published by: credit-service
Consumed by: decision-service

Message schema (Pydantic):
```python
{
  "application_id": "uuid",
  "cibil_score": "integer",
  "pan_number": "string",
  "monthly_income_inr": "decimal",
  "loan_amount_inr": "decimal",
  "loan_type": "string"
}
```

## API Endpoints (prequal-api)

### POST /applications
Submit a new loan prequalification application.

**Request Body**:
```json
{
  "pan_number": "ABCDE1234F",
  "applicant_name": "John Doe",
  "monthly_income_inr": 50000,
  "loan_amount_inr": 200000,
  "loan_type": "PERSONAL"
}
```

**Response (202 Accepted)**:
```json
{
  "application_id": "uuid",
  "status": "PENDING"
}
```

### GET /applications/{application_id}/status
Check the status of an application.

**Response (200 OK)**:
```json
{
  "application_id": "uuid",
  "status": "PRE_APPROVED"  // or PENDING, REJECTED, MANUAL_REVIEW
}
```

## Development Workflow

### TDD Approach (Mandatory)
Follow the **Red-Green-Refactor** cycle as specified in `.claude/commands/development.md`:

1. **RED**: Write failing unit tests for business logic first
2. **GREEN**: Implement minimum code to make tests pass
3. **REFACTOR**: Improve design while keeping tests green
4. **INTEGRATE**: Add integration tests after unit tests pass
5. **COVERAGE**: Ensure 85%+ test coverage

### Layered Architecture Pattern
```
Router (FastAPI) → Service (business logic) → Repository (data access) → Database
                                          ↓
                                    Kafka Producer

Consumer → Service → Repository → Database
```

### Key Implementation Requirements

- **Async/Await**: All I/O-bound operations must be async (database, Kafka, HTTP)
- **Pydantic Validation**: All request/response models and Kafka messages
- **Error Handling**: Custom exception handlers with structured logging
- **Idempotency**: Kafka consumers must handle duplicate messages safely
- **Graceful Shutdown**: Signal handlers for clean Kafka consumer shutdown
- **Connection Pooling**: Configure asyncpg connection pool for PostgreSQL
- **DLQ Strategy**: Dead letter queue for failed message processing
- **Correlation IDs**: For message tracing across services
- **Type Hints**: Complete type annotations validated by mypy

## Testing Strategy

### Unit Tests
- Mock all external dependencies (Kafka, database)
- Test service layer business logic in isolation
- Use `unittest.mock` and `pytest` fixtures
- Focus on CIBIL calculation and decision rules

### Integration Tests
- Use Docker Compose to spin up PostgreSQL + Kafka
- Test full API workflows end-to-end
- Verify Kafka message production/consumption
- Test database transactions and migrations

### API Tests
- Use FastAPI's `TestClient`
- Test all endpoints with valid/invalid inputs
- Verify HTTP status codes and response schemas
- Test Pydantic validation errors (422 responses)

### Consumer Tests
- Mock Kafka consumers
- Test message processing logic
- Verify database updates after message consumption
- Test error handling and retry logic

## Custom Slash Commands

The repository has custom Claude Code commands in `.claude/commands/`:

- **/tech-design**: Create technical design documents from requirements (uses `docs/requirements.md`)
- **/development**: Implement features following TDD with FastAPI best practices
- **/tech-deisgn-review**: Review technical design documents
- **/code-review**: Review implementation code

**Usage example**:
```
/tech-design Requirements are in docs/requirements.md file. Save tech design as tech-design.md file
/development Tech design is in tech-design.md
```

## Quality Gates (Must Pass)

- Zero linting errors (Ruff)
- Code formatted with Black
- Type hints validated with mypy
- Test coverage ≥ 85%
- All pre-commit hooks passing
- No security vulnerabilities
- API response time < 200ms
- Complete OpenAPI documentation with examples

## Important Notes

- **Environment Variables**: Store in `.env` file (already in `.gitignore`)
- **Secrets**: NEVER commit API keys or credentials to git
- **Database Migrations**: Always use Alembic, never manual schema changes
- **Kafka Consumer Groups**: Use unique group IDs for each service
- **Error Messages**: Provide clear, actionable error messages in API responses
- **Logging**: Use structured logging with correlation IDs for distributed tracing
- **Documentation**: FastAPI auto-generates OpenAPI docs at `/docs` endpoint

## Development Best Practices

1. Always use `async def` for I/O-bound functions
2. Use context managers for database sessions: `async with db.session() as session:`
3. Implement proper exception handling with custom exception classes
4. Keep functions small and focused (< 20 lines)
5. Use dependency injection for testability
6. Design idempotent Kafka consumers (handle retries safely)
7. Handle graceful shutdown with signal handlers (SIGTERM, SIGINT)
8. Log consumer lag metrics for monitoring
9. Use `asyncio.gather()` for concurrent async operations
10. Apply SOLID principles throughout the codebase

## Reference Documents

- **Requirements**: `docs/requirements.md` - Complete functional scope and user stories
- **Development Guidelines**: `.claude/commands/development.md` - TDD workflow and standards
- **Tech Design Template**: `.claude/commands/tech-design.md` - Architecture design template

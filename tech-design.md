# Technical Design: Loan Prequalification Service

## 1. Overview
- **Estimated Complexity**: Medium
- **Target Environment**: Local development with docker-compose
- **Primary Technologies**: Python 3.11+, FastAPI, PostgreSQL, Apache Kafka
- **Expected Load**: < 100 messages/sec, < 5 sec processing latency
- **Test Coverage Target**: 90%+ for critical paths (business logic, decision engine)

## 2. Business Requirements Summary

The Loan Prequalification Service is an event-driven microservices system that provides instant loan eligibility decisions for the Indian financial market. The system accepts minimal loan application data (including PAN number), asynchronously simulates a CIBIL score check, and applies business rules to determine prequalification status.

**Key Business Goals:**
- Fast user-facing API response (< 200ms for submission)
- Decoupled, resilient background processing
- Simulation of credit bureau integration (CIBIL scores)
- Support for Indian financial instruments (PAN number validation)
- Clear status tracking for applicants

**Prequalification States:**
- `PENDING`: Application received, awaiting processing
- `PRE_APPROVED`: Applicant meets all criteria
- `REJECTED`: Applicant does not meet minimum criteria
- `MANUAL_REVIEW`: Borderline case requiring human review

## 3. Technical Requirements

### 3.1 Functional Requirements

**FR-1: Application Submission (prequal-api)**
- Accept POST requests with loan application data
- Validate PAN number format (10 alphanumeric characters)
- Store application in PostgreSQL with `PENDING` status
- Publish message to `loan_applications_submitted` Kafka topic
- Return 202 Accepted with `application_id`

**FR-2: Status Retrieval (prequal-api)**
- Accept GET requests for application status by ID
- Return current application status from database
- Return 404 if application ID not found

**FR-3: Credit Score Simulation (credit-service)**
- Consume messages from `loan_applications_submitted` topic
- Calculate simulated CIBIL score (300-900 range) based on:
  - PAN number (special test cases)
  - Monthly income
  - Loan type
- Publish results to `credit_reports_generated` topic

**FR-4: Decision Engine (decision-service)**
- Consume messages from `credit_reports_generated` topic
- Apply business rules:
  - Reject if CIBIL score < 650
  - Pre-approve if score ≥ 650 AND income > (loan_amount / 48)
  - Manual review if score ≥ 650 AND income ≤ (loan_amount / 48)
- Update application status in PostgreSQL

**FR-5: Data Validation**
- Pydantic models for all API requests/responses
- Pydantic models for all Kafka message schemas
- Return 422 for validation errors with clear messages

### 3.2 Non-Functional Requirements

**NFR-1: Performance**
- API response time: < 200ms (p95)
- Message processing latency: < 5 seconds end-to-end
- Support up to 100 messages/sec throughput

**NFR-2: Reliability**
- Circuit breaker pattern for failure handling
- Dead Letter Queue (DLQ) for failed messages
- Idempotent consumer processing (handle duplicate messages)
- Graceful shutdown for Kafka consumers (SIGTERM/SIGINT)

**NFR-3: Observability**
- Structured JSON logging with correlation IDs
- Health check endpoints for all services
- Consumer lag monitoring
- Database connection pool metrics

**NFR-4: Code Quality**
- Zero linting errors (Ruff)
- Code formatted with Black
- Type hints validated by mypy
- Test coverage ≥ 90% for business logic
- Pre-commit hooks enforcing quality gates

**NFR-5: Scalability**
- Async/await for all I/O operations
- PostgreSQL connection pooling
- Kafka consumer groups for horizontal scaling
- Stateless service design

## 4. Architecture Overview

### 4.1 High-Level Design

```
┌─────────────┐
│   User      │
└──────┬──────┘
       │ HTTP (POST/GET)
       ▼
┌─────────────────────────────────────────────────────────┐
│  prequal-api (FastAPI)                                  │
│  - POST /applications                                   │
│  - GET /applications/{id}/status                        │
│  - GET /health                                          │
└──────┬───────────────────────────┬──────────────────────┘
       │                           │
       │ Write/Read                │ Publish
       ▼                           ▼
┌──────────────┐          ┌────────────────────┐
│ PostgreSQL   │          │  Apache Kafka      │
│  applications│          │  (3 topics)        │
│  table       │          └─────┬──────────────┘
└──────▲───────┘                │
       │                        │ loan_applications_submitted
       │                        ▼
       │              ┌─────────────────────────┐
       │              │  credit-service         │
       │              │  (Kafka Consumer)       │
       │              │  - CIBIL Simulation     │
       │              └──────────┬──────────────┘
       │                         │
       │                         │ credit_reports_generated
       │                         ▼
       │              ┌─────────────────────────┐
       │              │  decision-service       │
       │              │  (Kafka Consumer)       │
       │              │  - Decision Engine      │
       │              └──────────┬──────────────┘
       │                         │
       └─────────────────────────┘ Update status
```

**Event Flow:**
1. User submits application → prequal-api → PostgreSQL (`PENDING`) → Kafka
2. credit-service consumes → calculates CIBIL score → publishes to Kafka
3. decision-service consumes → applies rules → updates PostgreSQL (final status)
4. User polls status → prequal-api → PostgreSQL → returns current status

### 4.2 Affected Microservices

**New Services (to be created):**

1. **prequal-api** (FastAPI REST API)
   - Serves HTTP endpoints
   - Kafka producer (aiokafka)
     - Single global AIOKafkaProducer instance
     - Started during application lifespan startup
     - Injected into routes via dependency injection
     - Closed during application shutdown
   - PostgreSQL client (async)
   - Port: 8000
   - CORS middleware configured for web clients

2. **credit-service** (Python Kafka Consumer)
   - Kafka consumer (group: `credit-service-group`)
   - Kafka producer (aiokafka)
   - Stateless processing
   - Graceful shutdown handling

3. **decision-service** (Python Kafka Consumer)
   - Kafka consumer (group: `decision-service-group`)
   - PostgreSQL client (async)
   - Updates application records with idempotency
   - Circuit breaker for database operations

**External Dependencies:**
- PostgreSQL 15+ (database)
- Apache Kafka 3.x + Zookeeper (message broker)
- All orchestrated via docker-compose

## 5. Detailed Design

### 5.1 Data Model

#### PostgreSQL Schema

**applications Table**

```sql
CREATE TABLE applications (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    pan_number VARCHAR(10) NOT NULL,
    applicant_name VARCHAR(255),
    monthly_income_inr DECIMAL(12, 2) NOT NULL,
    loan_amount_inr DECIMAL(12, 2) NOT NULL,
    loan_type VARCHAR(20),
    status VARCHAR(20) NOT NULL DEFAULT 'PENDING',
    cibil_score INTEGER,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW(),

    -- Constraints
    CONSTRAINT valid_status CHECK (status IN ('PENDING', 'PRE_APPROVED', 'REJECTED', 'MANUAL_REVIEW')),
    CONSTRAINT valid_cibil_score CHECK (cibil_score IS NULL OR (cibil_score >= 300 AND cibil_score <= 900)),
    CONSTRAINT positive_income CHECK (monthly_income_inr > 0),
    CONSTRAINT positive_loan_amount CHECK (loan_amount_inr > 0)
);

-- Index for faster status lookups
CREATE INDEX idx_applications_pan_number ON applications(pan_number);
CREATE INDEX idx_applications_status ON applications(status);
CREATE INDEX idx_applications_created_at ON applications(created_at DESC);

-- Trigger to automatically update updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

CREATE TRIGGER update_applications_updated_at
    BEFORE UPDATE ON applications
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();
```

**Migration Strategy:**
- Use Alembic for database migrations
- Initial migration creates `applications` table with trigger
- Future migrations for schema evolution
- Include trigger creation in Alembic migration using `op.execute()`

**Database Connection Management:**
- AsyncPG connection pool (min: 5, max: 20 connections)
- Connection timeout: 30 seconds
- Statement timeout: 10 seconds
- Connection string format: `postgresql+asyncpg://user:pass@host:5432/dbname`
- Health checks on pool acquisition
- Pool recycling: 3600 seconds (1 hour)

### 5.2 API Design

#### CORS Configuration

```python
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="Loan Prequalification API")

# CORS Configuration for web clients
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],  # Frontend dev server
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

# For production, use environment variable:
# ALLOWED_ORIGINS = os.getenv("ALLOWED_ORIGINS", "").split(",")
```

#### prequal-api Endpoints

**1. POST /applications**

*Purpose:* Submit new loan prequalification application

*Request:*
```json
{
  "pan_number": "ABCDE1234F",
  "applicant_name": "Rajesh Kumar",
  "monthly_income_inr": 75000.00,
  "loan_amount_inr": 500000.00,
  "loan_type": "PERSONAL"
}
```

*Pydantic Request Model:*
```python
class LoanApplicationRequest(BaseModel):
    pan_number: str = Field(..., pattern="^[A-Z]{5}[0-9]{4}[A-Z]$", description="10-character PAN")
    applicant_name: str = Field(..., min_length=1, max_length=255)
    monthly_income_inr: Decimal = Field(..., gt=0, decimal_places=2)
    loan_amount_inr: Decimal = Field(..., gt=0, decimal_places=2)
    loan_type: Literal["PERSONAL", "HOME", "AUTO"]
```

*Response (202 Accepted):*
```json
{
  "application_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "PENDING"
}
```

*Pydantic Response Model:*
```python
class LoanApplicationResponse(BaseModel):
    application_id: UUID
    status: Literal["PENDING"]
```

*Error Responses:*
- 422 Unprocessable Entity: Validation errors
- 500 Internal Server Error: System errors

---

**2. GET /applications/{application_id}/status**

*Purpose:* Retrieve current application status

*Path Parameters:*
- `application_id`: UUID

*Response (200 OK):*
```json
{
  "application_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "PRE_APPROVED"
}
```

*Pydantic Response Model:*
```python
class ApplicationStatusResponse(BaseModel):
    application_id: UUID
    status: Literal["PENDING", "PRE_APPROVED", "REJECTED", "MANUAL_REVIEW"]
```

*Error Responses:*
- 404 Not Found: Application ID not found
- 500 Internal Server Error: System errors

---

**3. GET /health**

*Purpose:* Health check endpoint for monitoring

*Response (200 OK):*
```json
{
  "status": "healthy",
  "database": "connected",
  "kafka": "connected"
}
```

*Response (503 Service Unavailable):*
```json
{
  "status": "unhealthy",
  "database": "disconnected",
  "kafka": "connected"
}
```

### 5.3 Service Layer Design

#### prequal-api Service Architecture

**Layer Structure:**
```
routes/ (FastAPI routers)
  └─> services/ (business logic)
       └─> repositories/ (data access)
            └─> database (PostgreSQL)
       └─> kafka/producer (message publishing)
```

**ApplicationService (Business Logic):**
- `create_application(request: LoanApplicationRequest) -> LoanApplicationResponse`
  - Validate input via Pydantic
  - Generate UUID
  - Save to database via repository
  - Publish to Kafka via producer
  - Return application ID

- `get_application_status(application_id: UUID) -> ApplicationStatusResponse`
  - Fetch from database via repository
  - Return status or raise 404

**ApplicationRepository (Data Access):**
- `save(application: Application) -> Application`
  - Async database insert
  - Handle constraint violations

- `find_by_id(application_id: UUID) -> Optional[Application]`
  - Async database query
  - Return None if not found

- `update_status(application_id: UUID, status: str, cibil_score: int) -> None`
  - Async database update
  - Used by decision-service

**KafkaProducer (Message Publishing):**
- `publish_application_submitted(application: Application) -> None`
  - Serialize to JSON
  - Publish to `loan_applications_submitted` topic
  - Handle publish failures with retry (3 attempts)

#### credit-service Architecture

**Service Logic:**
- `process_application(message: LoanApplicationMessage) -> CreditReport`
  - Calculate simulated CIBIL score
  - Apply special PAN rules
  - Apply income-based adjustments
  - Apply loan type adjustments
  - Add random variation (-5 to +5)
  - Clamp score to 300-900 range

**CIBIL Calculation Algorithm:**
```python
def calculate_cibil_score(pan_number: str, monthly_income: Decimal, loan_type: str) -> int:
    # Special test PANs
    if pan_number == "ABCDE1234F":
        return 790
    if pan_number == "FGHIJ5678K":
        return 610

    # Base score
    score = 650

    # Income adjustments
    if monthly_income > 75000:
        score += 40
    elif monthly_income < 30000:
        score -= 20

    # Loan type adjustments
    if loan_type == "PERSONAL":
        score -= 10  # Unsecured
    elif loan_type == "HOME":
        score += 10  # Secured

    # Random variation
    score += random.randint(-5, 5)

    # Clamp to valid range
    return max(300, min(900, score))
```

#### decision-service Architecture

**Decision Engine Logic:**
- `process_credit_report(message: CreditReportMessage) -> Decision`
  - Apply business rules
  - Return decision status

**Decision Rules:**
```python
def make_decision(cibil_score: int, monthly_income: Decimal, loan_amount: Decimal) -> str:
    # Reject low credit scores
    if cibil_score < 650:
        return "REJECTED"

    # Check income-to-loan ratio (4-year loan assumption)
    required_monthly_payment = loan_amount / 48

    if monthly_income > required_monthly_payment:
        return "PRE_APPROVED"
    else:
        return "MANUAL_REVIEW"  # Good score but tight finances
```

### 5.4 Integration Points

#### Kafka Topic Architecture

**Topic 1: loan_applications_submitted**
- **Producer:** prequal-api
- **Consumer:** credit-service
- **Partitions:** 3 (for load distribution)
- **Replication Factor:** 1 (local dev)
- **Retention:** 7 days

**Topic 2: credit_reports_generated**
- **Producer:** credit-service
- **Consumer:** decision-service
- **Partitions:** 3
- **Replication Factor:** 1
- **Retention:** 7 days

**Topic 3: loan_application_dlq** (Dead Letter Queue)
- **Producer:** credit-service, decision-service (on persistent failures)
- **Consumer:** Manual review/alerting service (future)
- **Partitions:** 1
- **Replication Factor:** 1
- **Retention:** 30 days

### 5.5 Event-Driven Components

#### Message Schemas (Pydantic Models)

**LoanApplicationMessage (loan_applications_submitted):**
```python
class LoanApplicationMessage(BaseModel):
    application_id: UUID
    pan_number: str
    applicant_name: str
    monthly_income_inr: Decimal
    loan_amount_inr: Decimal
    loan_type: str
    timestamp: datetime
    correlation_id: str  # For distributed tracing
```

**CreditReportMessage (credit_reports_generated):**
```python
class CreditReportMessage(BaseModel):
    application_id: UUID
    pan_number: str
    cibil_score: int
    monthly_income_inr: Decimal
    loan_amount_inr: Decimal
    loan_type: str
    timestamp: datetime
    correlation_id: str
```

**DeadLetterMessage (loan_application_dlq):**
```python
class DeadLetterMessage(BaseModel):
    original_topic: str
    original_partition: int
    original_offset: int
    error_message: str
    retry_count: int
    failed_at: datetime
    payload: dict  # Original message
```

#### Kafka Producer Configuration

**Custom JSON Encoder for Decimal/UUID Types:**
```python
import json
from decimal import Decimal
from datetime import datetime
from uuid import UUID

class KafkaJSONEncoder(json.JSONEncoder):
    """Custom JSON encoder for Kafka messages."""
    def default(self, obj):
        if isinstance(obj, Decimal):
            return str(obj)  # Preserve precision as string
        if isinstance(obj, datetime):
            return obj.isoformat()
        if isinstance(obj, UUID):
            return str(obj)
        return super().default(obj)
```

**prequal-api Producer (using aiokafka):**
```python
from aiokafka import AIOKafkaProducer

producer = AIOKafkaProducer(
    bootstrap_servers='localhost:9092',
    acks='all',  # Wait for all replicas
    retries=3,
    max_in_flight_requests_per_connection=1,  # Ensure ordering
    compression_type='gzip',
    key_serializer=lambda k: str(k).encode('utf-8') if k else None,
    value_serializer=lambda v: json.dumps(v, cls=KafkaJSONEncoder).encode('utf-8')
)

# Start producer in FastAPI lifespan event
await producer.start()
```

**Message Publishing with Retry:**
```python
async def publish_application_submitted(
    producer: AIOKafkaProducer,
    application: Application,
    correlation_id: str
) -> None:
    """Publish message with retries and timeout."""
    message = {
        "application_id": str(application.id),
        "pan_number": application.pan_number,
        # ... other fields
        "correlation_id": correlation_id
    }

    for attempt in range(1, 4):  # 3 attempts
        try:
            await asyncio.wait_for(
                producer.send_and_wait(
                    topic="loan_applications_submitted",
                    key=str(application.id),  # Partition by application_id
                    value=message
                ),
                timeout=5.0
            )
            logger.info("Published to Kafka", application_id=application.id, attempt=attempt)
            return
        except Exception as e:
            logger.warning(f"Kafka publish attempt {attempt} failed", error=str(e))
            if attempt == 3:
                logger.error("Failed to publish after 3 attempts", application_id=application.id)
                # Application already saved in DB - alert for manual intervention
            else:
                await asyncio.sleep(0.5 * attempt)  # Exponential backoff
```

**credit-service Producer:**
- Same configuration as prequal-api
- Additional error handling for network failures

#### Kafka Consumer Configuration

**Decimal Deserializer:**
```python
def deserialize_kafka_message(data: dict) -> dict:
    """Convert string decimals back to Decimal objects."""
    if 'monthly_income_inr' in data:
        data['monthly_income_inr'] = Decimal(data['monthly_income_inr'])
    if 'loan_amount_inr' in data:
        data['loan_amount_inr'] = Decimal(data['loan_amount_inr'])
    return data
```

**credit-service Consumer (using aiokafka):**
```python
from aiokafka import AIOKafkaConsumer

consumer = AIOKafkaConsumer(
    'loan_applications_submitted',
    bootstrap_servers='localhost:9092',
    group_id='credit-service-group',
    auto_offset_reset='earliest',
    enable_auto_commit=False,  # Manual commit for reliability
    max_poll_records=10,
    session_timeout_ms=30000,
    value_deserializer=lambda m: json.loads(m.decode('utf-8'))
)

await consumer.start()
```

**decision-service Consumer:**
- Same configuration with `group_id='decision-service-group'`
- Consumes from `credit_reports_generated` topic

#### Consumer Error Handling Strategy

**Circuit Breaker Implementation (using pybreaker):**
```python
from pybreaker import CircuitBreaker

# Configure circuit breaker for database operations in decision-service
db_circuit_breaker = CircuitBreaker(
    fail_max=5,  # Open circuit after 5 consecutive failures
    timeout_duration=60,  # Stay open for 60 seconds
    name="database_updates"
)

@db_circuit_breaker
async def update_application_with_decision(
    db: AsyncSession,
    application_id: UUID,
    status: str,
    cibil_score: int
) -> None:
    """Update application with circuit breaker protection."""
    await update_application_status(db, application_id, status, cibil_score)

# In consumer loop
try:
    await update_application_with_decision(...)
    await consumer.commit()
except CircuitBreakerError:
    logger.error("Circuit breaker open - skipping message")
    await publish_to_dlq(message, "Circuit breaker open")
    await consumer.commit()  # Commit to avoid reprocessing
```

**Idempotency Implementation (decision-service):**
```python
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

async def update_application_status(
    db: AsyncSession,
    application_id: UUID,
    new_status: str,
    cibil_score: int
) -> bool:
    """
    Update application status idempotently using SELECT FOR UPDATE.
    Returns True if updated, False if already processed.
    """
    async with db.begin():
        # Lock row to prevent concurrent updates
        query = select(Application).where(
            Application.id == application_id
        ).with_for_update()

        result = await db.execute(query)
        application = result.scalar_one_or_none()

        if not application:
            raise ApplicationNotFoundError(application_id)

        # Idempotency check: only update if still PENDING
        if application.status != "PENDING":
            logger.warning(
                "Application already processed",
                application_id=application_id,
                current_status=application.status
            )
            return False

        # Update to final state
        application.status = new_status
        application.cibil_score = cibil_score
        # updated_at automatically updated by trigger

        await db.commit()
        return True
```

**Retry Logic with Exponential Backoff:**
```python
async def process_message_with_retry(message):
    """Process message with exponential backoff retry."""
    retry_delays = [0, 5, 15]  # seconds

    for attempt, delay in enumerate(retry_delays, start=1):
        try:
            if delay > 0:
                await asyncio.sleep(delay)

            await process_message(message)
            return True  # Success

        except Exception as e:
            logger.warning(
                f"Processing attempt {attempt} failed",
                error=str(e),
                attempt=attempt
            )

            if attempt == len(retry_delays):
                # Final failure - send to DLQ
                await publish_to_dlq(message, str(e))
                logger.error("Message processing failed after retries")
                return False

    return False
```

**Graceful Shutdown (aiokafka):**
```python
import signal
import asyncio

class GracefulConsumer:
    def __init__(self, consumer: AIOKafkaConsumer):
        self.consumer = consumer
        self.running = True

    def setup_signals(self):
        """Register signal handlers for graceful shutdown."""
        signal.signal(signal.SIGTERM, self._handle_shutdown)
        signal.signal(signal.SIGINT, self._handle_shutdown)

    def _handle_shutdown(self, signum, frame):
        """Handle shutdown signals."""
        logger.info(f"Received signal {signum}, shutting down gracefully...")
        self.running = False

    async def consume(self):
        """Main consumer loop with graceful shutdown."""
        try:
            async for message in self.consumer:
                if not self.running:
                    break

                await self.process_message(message)
                await self.consumer.commit()
        finally:
            await self.consumer.stop()
            logger.info("Consumer stopped gracefully")
```

## 6. Implementation Plan

### 6.1 Dependencies

**Technical Dependencies:**
- PostgreSQL database must be running before services start
- Kafka + Zookeeper must be running before services start
- Database schema must be migrated before first application submission

**Service Startup Order:**
1. PostgreSQL
2. Zookeeper
3. Kafka (create topics automatically)
4. Run Alembic migrations
5. prequal-api
6. credit-service
7. decision-service

**Business Dependencies:**
- None (greenfield project)

### 6.2 Poetry Configuration

**Key Dependencies (pyproject.toml):**

```toml
[tool.poetry.dependencies]
python = "^3.11"
fastapi = "^0.104.0"
uvicorn = {extras = ["standard"], version = "^0.24.0"}
pydantic = {extras = ["email"], version = "^2.0"}
sqlalchemy = {extras = ["asyncio"], version = "^2.0"}
asyncpg = "^0.29.0"
alembic = "^1.12.0"
aiokafka = "^0.8.1"  # Async Kafka client (changed from kafka-python)
python-dotenv = "^1.0.0"
structlog = "^23.2.0"  # Structured logging
pybreaker = "^1.0.1"  # Circuit breaker pattern
httpx = "^0.25.2"  # Async HTTP client for tests

[tool.poetry.dev-dependencies]
pytest = "^7.4.0"
pytest-asyncio = "^0.21.0"
pytest-cov = "^4.1.0"
pytest-mock = "^3.12.0"
ruff = "^0.1.0"
black = "^23.10.0"
mypy = "^1.6.0"
pre-commit = "^3.5.0"

[tool.ruff]
line-length = 100
target-version = "py311"

[tool.black]
line-length = 100
target-version = ['py311']

[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]
python_files = "test_*.py"
python_functions = "test_*"
addopts = "--cov=src --cov-report=html --cov-report=term --cov-fail-under=90"

[tool.mypy]
python_version = "3.11"
strict = true
warn_return_any = true
warn_unused_configs = true
disallow_untyped_defs = true
```

**Package Installation:**
```bash
poetry install --no-root
poetry add fastapi uvicorn[standard] sqlalchemy[asyncio] asyncpg alembic aiokafka structlog pybreaker httpx
poetry add --dev pytest pytest-asyncio pytest-cov ruff black mypy pre-commit
```

## 7. Testing Strategy

### 7.1 Unit Testing (pytest)

**Target Coverage:** 90%+ for business logic

**Scope:**
- Service layer functions (CIBIL calculation, decision rules)
- Repository layer database operations
- Kafka producer/consumer message handling
- Pydantic model validation

**Example Test Structure:**

```python
# tests/unit/services/test_credit_service.py
import pytest
from src.app.services.credit_service import calculate_cibil_score

def test_special_pan_abcde_returns_790():
    """Test special PAN ABCDE1234F returns fixed score 790"""
    score = calculate_cibil_score("ABCDE1234F", 50000, "PERSONAL")
    assert score == 790

def test_high_income_increases_score():
    """Test income > 75000 adds bonus points"""
    score = calculate_cibil_score("AAAAA1111A", 80000, "PERSONAL")
    assert score >= 650 + 40 - 10 - 5  # base + income bonus - personal - min random

def test_score_clamped_to_valid_range():
    """Test score is always between 300-900"""
    score = calculate_cibil_score("AAAAA1111A", 10000, "PERSONAL")
    assert 300 <= score <= 900
```

```python
# tests/unit/services/test_decision_service.py
import pytest
from src.app.services.decision_service import make_decision
from decimal import Decimal

def test_low_cibil_score_rejected():
    """Test CIBIL score < 650 results in REJECTED"""
    decision = make_decision(600, Decimal('50000'), Decimal('200000'))
    assert decision == "REJECTED"

def test_good_score_sufficient_income_approved():
    """Test score >= 650 with good income ratio results in PRE_APPROVED"""
    decision = make_decision(750, Decimal('60000'), Decimal('200000'))
    # 60000 > (200000 / 48 = 4166.67)
    assert decision == "PRE_APPROVED"

def test_good_score_tight_income_manual_review():
    """Test score >= 650 but tight income ratio results in MANUAL_REVIEW"""
    decision = make_decision(750, Decimal('4000'), Decimal('200000'))
    # 4000 < (200000 / 48 = 4166.67)
    assert decision == "MANUAL_REVIEW"
```

**Mocking Strategy:**
- Mock database connections with `pytest-asyncio` fixtures
- Mock Kafka producers/consumers with `unittest.mock`
- Use `pytest-mock` for simplified mocking

### 7.2 Integration Testing

**Scope:**
- Full API endpoint testing with real database
- Kafka message production and consumption
- End-to-end workflow validation

**Setup:**
- Use Docker Compose to spin up PostgreSQL and Kafka
- Run Alembic migrations before tests
- Clean database after each test

**Example Integration Test:**

```python
# tests/integration/test_api_endpoints.py
import pytest
from httpx import AsyncClient
from src.app.main import app

@pytest.mark.asyncio
async def test_submit_application_returns_202(async_client: AsyncClient, db_session):
    """Test POST /applications returns 202 with application_id"""
    payload = {
        "pan_number": "ABCDE1234F",
        "applicant_name": "Test User",
        "monthly_income_inr": 50000,
        "loan_amount_inr": 200000,
        "loan_type": "PERSONAL"
    }

    response = await async_client.post("/applications", json=payload)

    assert response.status_code == 202
    data = response.json()
    assert "application_id" in data
    assert data["status"] == "PENDING"

@pytest.mark.asyncio
async def test_invalid_pan_returns_422(async_client: AsyncClient):
    """Test invalid PAN number returns 422 validation error"""
    payload = {
        "pan_number": "INVALID",
        "applicant_name": "Test User",
        "monthly_income_inr": 50000,
        "loan_amount_inr": 200000,
        "loan_type": "PERSONAL"
    }

    response = await async_client.post("/applications", json=payload)

    assert response.status_code == 422
```

### 7.3 End-to-End Testing

**Scope:**
- Complete workflow from submission to final decision
- Verify Kafka message flow between services
- Validate database state changes

**Example E2E Test:**

```python
# tests/e2e/test_full_workflow.py
import pytest
import asyncio
from httpx import AsyncClient

@pytest.mark.asyncio
async def test_pre_approved_workflow(async_client: AsyncClient):
    """Test full workflow results in PRE_APPROVED status"""
    # Submit application
    payload = {
        "pan_number": "ABCDE1234F",  # Special PAN with score 790
        "applicant_name": "Rajesh Kumar",
        "monthly_income_inr": 80000,  # High income
        "loan_amount_inr": 200000,
        "loan_type": "HOME"
    }

    submit_response = await async_client.post("/applications", json=payload)
    assert submit_response.status_code == 202
    application_id = submit_response.json()["application_id"]

    # Wait for async processing (with timeout)
    max_wait = 10  # seconds
    for _ in range(max_wait):
        status_response = await async_client.get(f"/applications/{application_id}/status")
        status = status_response.json()["status"]

        if status != "PENDING":
            break

        await asyncio.sleep(1)

    # Verify final status
    assert status == "PRE_APPROVED"
```

## 8. Deployment Considerations

### 8.1 Docker Configuration

**Dockerfile for prequal-api:**

```dockerfile
FROM python:3.11-slim

WORKDIR /app

# Install Poetry
RUN pip install poetry

# Copy dependency files
COPY pyproject.toml poetry.lock ./

# Install dependencies (without dev dependencies)
RUN poetry config virtualenvs.create false \
    && poetry install --no-dev --no-interaction --no-ansi

# Copy application code
COPY src/ ./src/
COPY alembic/ ./alembic/
COPY alembic.ini ./

# Health check
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import requests; requests.get('http://localhost:8000/health')"

# Run migrations and start server
CMD alembic upgrade head && uvicorn src.app.main:app --host 0.0.0.0 --port 8000
```

**Dockerfile for credit-service and decision-service:**

```dockerfile
FROM python:3.11-slim

WORKDIR /app

RUN pip install poetry

COPY pyproject.toml poetry.lock ./
RUN poetry config virtualenvs.create false \
    && poetry install --no-dev --no-interaction --no-ansi

COPY src/ ./src/

# No health check for consumers (monitor via Kafka lag)

CMD python -m src.app.consumers.credit_consumer
```

### 8.2 Local Development

**docker-compose.yml:**

```yaml
version: '3.8'

services:
  postgres:
    image: postgres:15
    environment:
      POSTGRES_USER: loanapp
      POSTGRES_PASSWORD: loanapp
      POSTGRES_DB: loanapp
    ports:
      - "5432:5432"
    volumes:
      - postgres_data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U loanapp"]
      interval: 10s
      timeout: 5s
      retries: 5

  zookeeper:
    image: confluentinc/cp-zookeeper:7.5.0
    environment:
      ZOOKEEPER_CLIENT_PORT: 2181
      ZOOKEEPER_TICK_TIME: 2000
    ports:
      - "2181:2181"

  kafka:
    image: confluentinc/cp-kafka:7.5.0
    depends_on:
      - zookeeper
    ports:
      - "9092:9092"
    environment:
      KAFKA_BROKER_ID: 1
      KAFKA_ZOOKEEPER_CONNECT: zookeeper:2181
      KAFKA_ADVERTISED_LISTENERS: PLAINTEXT://localhost:9092
      KAFKA_OFFSETS_TOPIC_REPLICATION_FACTOR: 1
      KAFKA_AUTO_CREATE_TOPICS_ENABLE: "true"
    healthcheck:
      test: ["CMD", "kafka-broker-api-versions", "--bootstrap-server", "localhost:9092"]
      interval: 10s
      timeout: 10s
      retries: 5

  prequal-api:
    build:
      context: .
      dockerfile: docker/Dockerfile.api
    ports:
      - "8000:8000"
    depends_on:
      postgres:
        condition: service_healthy
      kafka:
        condition: service_healthy
    environment:
      DATABASE_URL: postgresql+asyncpg://loanapp:loanapp@postgres:5432/loanapp
      KAFKA_BOOTSTRAP_SERVERS: kafka:9092
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      timeout: 5s
      retries: 3

  credit-service:
    build:
      context: .
      dockerfile: docker/Dockerfile.credit
    depends_on:
      kafka:
        condition: service_healthy
    environment:
      KAFKA_BOOTSTRAP_SERVERS: kafka:9092

  decision-service:
    build:
      context: .
      dockerfile: docker/Dockerfile.decision
    depends_on:
      postgres:
        condition: service_healthy
      kafka:
        condition: service_healthy
    environment:
      DATABASE_URL: postgresql+asyncpg://loanapp:loanapp@postgres:5432/loanapp
      KAFKA_BOOTSTRAP_SERVERS: kafka:9092

volumes:
  postgres_data:
```

**Environment Variables (.env):**

```bash
# Database
DATABASE_URL=postgresql+asyncpg://loanapp:loanapp@localhost:5432/loanapp
DB_POOL_SIZE=20
DB_MAX_OVERFLOW=10

# Kafka
KAFKA_BOOTSTRAP_SERVERS=localhost:9092
KAFKA_CONSUMER_GROUP_CREDIT=credit-service-group
KAFKA_CONSUMER_GROUP_DECISION=decision-service-group

# Application
LOG_LEVEL=INFO
ENVIRONMENT=local
```

## 9. Monitoring & Observability

### 9.1 Structured Logging

**Log Format (JSON):**
```json
{
  "timestamp": "2025-01-15T10:30:45.123Z",
  "level": "INFO",
  "service": "prequal-api",
  "correlation_id": "550e8400-e29b-41d4-a716-446655440000",
  "message": "Application submitted successfully",
  "application_id": "550e8400-e29b-41d4-a716-446655440000",
  "pan_number": "ABCDE1234F",
  "duration_ms": 45
}
```

**Logging Strategy:**
- Use Python `structlog` library
- Generate correlation IDs in API layer
- Propagate correlation IDs through Kafka messages
- Log all service entry/exit points
- Log all errors with stack traces

**structlog Configuration:**
```python
import structlog
import logging

def configure_logging():
    """Configure structured logging for the application."""
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.dev.set_exc_info,
            structlog.processors.JSONRenderer()
        ],
        wrapper_class=structlog.make_filtering_bound_logger(logging.INFO),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=False
    )

# In main.py startup
configure_logging()
logger = structlog.get_logger()
```

**PAN Masking Utility:**
```python
def mask_pan(pan: str) -> str:
    """Mask PAN number for logging: ABCDE1234F -> ABCDE***4F"""
    if len(pan) != 10:
        return "INVALID"
    return f"{pan[:5]}***{pan[-2:]}"

# Usage
logger.info("Application submitted", pan_number=mask_pan(application.pan_number))
```

### 9.2 Health Check Endpoints

**prequal-api Health Check:**

```python
from sqlalchemy import text
from fastapi.responses import JSONResponse

@app.get("/health")
async def health_check(
    db: AsyncSession = Depends(get_db),
    producer: AIOKafkaProducer = Depends(get_kafka_producer)
):
    """Health check endpoint for orchestration and monitoring"""
    health_status = {
        "status": "healthy",
        "database": "unknown",
        "kafka": "unknown"
    }

    # Check database connection
    try:
        await db.execute(text("SELECT 1"))
        health_status["database"] = "connected"
    except Exception as e:
        logger.error("Database health check failed", error=str(e))
        health_status["database"] = "disconnected"
        health_status["status"] = "unhealthy"

    # Check Kafka producer connection (aiokafka)
    try:
        # For aiokafka, check if producer is started and not closed
        if producer._closed:
            raise Exception("Producer is closed")
        health_status["kafka"] = "connected"
    except Exception as e:
        logger.error("Kafka health check failed", error=str(e))
        health_status["kafka"] = "disconnected"
        health_status["status"] = "unhealthy"

    status_code = 200 if health_status["status"] == "healthy" else 503
    return JSONResponse(content=health_status, status_code=status_code)
```

**Database and Kafka Lifecycle Management:**

```python
from contextlib import asynccontextmanager
from fastapi import FastAPI
from aiokafka import AIOKafkaProducer

# Global instances
engine = None
async_session_maker = None
kafka_producer = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage database and Kafka connection lifecycle."""
    global engine, async_session_maker, kafka_producer

    # Startup
    engine = create_async_engine(
        settings.database_url,
        pool_size=20,
        max_overflow=10,
        pool_timeout=30,
        pool_recycle=3600,
        echo=False
    )
    async_session_maker = sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False
    )

    # Start Kafka producer
    kafka_producer = AIOKafkaProducer(
        bootstrap_servers=settings.kafka_bootstrap_servers,
        # ... other config
    )
    await kafka_producer.start()

    logger.info("Application started - DB and Kafka initialized")
    yield

    # Shutdown
    await kafka_producer.stop()
    await engine.dispose()
    logger.info("Application shutdown - connections closed")

app = FastAPI(lifespan=lifespan)

# Dependency for routes
async def get_db() -> AsyncSession:
    async with async_session_maker() as session:
        yield session

async def get_kafka_producer() -> AIOKafkaProducer:
    return kafka_producer
```

### 9.3 Consumer Lag Monitoring

**Metrics to Track:**
- Messages per second consumed
- Consumer lag (messages behind head of partition)
- Processing time per message
- Error rate (failed messages / total messages)

**Implementation:**
- Log consumer lag every 60 seconds
- Alert if lag > 1000 messages
- Track processing time in logs

## 10. Security Considerations

### 10.1 Data Validation

**Pydantic Models:**
- All API requests validated with Pydantic models
- PAN number regex validation: `^[A-Z]{5}[0-9]{4}[A-Z]$`
- Positive number constraints for income and loan amounts
- Enum validation for loan types and statuses

**SQL Injection Prevention:**
- Use SQLAlchemy ORM with parameterized queries
- Never construct raw SQL with user input

### 10.2 Error Handling

**API Error Responses:**
```python
# Custom exception handler
@app.exception_handler(ValidationError)
async def validation_exception_handler(request: Request, exc: ValidationError):
    return JSONResponse(
        status_code=422,
        content={
            "error": "Validation Error",
            "details": exc.errors()
        }
    )

@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={
            "error": "Internal Server Error",
            "message": "An unexpected error occurred"
        }
    )
```

**Sensitive Data:**
- Never log full PAN numbers (mask last 4 characters)
- Never return detailed error messages to clients
- Use generic error messages in production

### 10.3 Secrets Management

**Local Development:**
- Store secrets in `.env` file (add to `.gitignore`)
- Use `python-dotenv` to load environment variables

**Production Considerations:**
- Use environment variables injected by orchestration platform
- Never commit secrets to version control
- Rotate database passwords regularly

## 11. CI/CD Pipeline

### 11.1 Pre-commit Hooks

**.pre-commit-config.yaml:**

```yaml
repos:
  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.1.5
    hooks:
      - id: ruff
        args: [--fix, --exit-non-zero-on-fix]

  - repo: https://github.com/psf/black
    rev: 23.10.0
    hooks:
      - id: black
        language_version: python3.11

  - repo: https://github.com/pre-commit/mirrors-mypy
    rev: v1.6.1
    hooks:
      - id: mypy
        additional_dependencies: [types-all]
        args: [--strict, --ignore-missing-imports]

  - repo: https://github.com/pre-commit/pre-commit-hooks
    rev: v4.5.0
    hooks:
      - id: trailing-whitespace
      - id: end-of-file-fixer
      - id: check-yaml
      - id: check-added-large-files
```

**Installation:**
```bash
pre-commit install
```

**Manual Run:**
```bash
pre-commit run --all-files
```

### 11.2 Makefile Commands

**Makefile:**

```makefile
.PHONY: install lint format type-check test test-unit test-integration run-local db-migrate clean

install:
	poetry install

lint:
	poetry run ruff check src/ tests/

format:
	poetry run black src/ tests/
	poetry run ruff check --fix src/ tests/

type-check:
	poetry run mypy src/

test:
	poetry run pytest tests/ --cov=src --cov-report=html --cov-report=term --cov-fail-under=90

test-unit:
	poetry run pytest tests/unit/ --cov=src/app/services --cov-fail-under=95

test-integration:
	docker-compose up -d postgres kafka
	poetry run pytest tests/integration/
	docker-compose down

run-local:
	docker-compose up --build

db-migrate:
	poetry run alembic upgrade head

clean:
	docker-compose down -v
	rm -rf .pytest_cache
	rm -rf htmlcov
	rm -rf .coverage
	find . -type d -name __pycache__ -exec rm -rf {} +
```

**Usage Examples:**
```bash
make install          # Install dependencies
make lint             # Run linting
make format           # Format code
make type-check       # Run mypy type checking
make test             # Run all tests with coverage
make test-unit        # Run only unit tests
make run-local        # Start all services with docker-compose
make db-migrate       # Run database migrations
make clean            # Clean up containers and cache
```

### 11.3 Quality Gates

**Required Checks Before Commit:**
1. ✅ Ruff linting passes (no errors)
2. ✅ Black formatting applied
3. ✅ Mypy type checking passes
4. ✅ No trailing whitespace
5. ✅ No large files added

**Required Checks Before PR:**
1. ✅ All pre-commit hooks pass
2. ✅ Test coverage ≥ 90% (overall), 95% (business logic)
3. ✅ All tests pass (unit + integration)
4. ✅ No TODO/FIXME comments in production code
5. ✅ OpenAPI docs generate correctly

## 12. Risk Assessment

### 12.1 Technical Risks

| Risk | Impact | Probability | Mitigation |
|------|--------|-------------|------------|
| Kafka message loss | High | Low | Use `acks=all`, retries, and DLQ for failed messages |
| Database connection pool exhaustion | High | Medium | Configure appropriate pool size (20), implement connection timeouts |
| Consumer processing failures | Medium | Medium | Circuit breaker, exponential backoff, DLQ |
| Race conditions in status updates | Medium | Low | Use database transactions with SELECT FOR UPDATE |
| Duplicate message processing | Medium | Medium | Implement idempotency checks using application_id |
| API performance degradation | Medium | Low | Use async/await, connection pooling, index database properly |
| Test flakiness in integration tests | Low | Medium | Use docker-compose health checks, proper teardown |

### 12.2 Operational Risks

| Risk | Impact | Probability | Mitigation |
|------|--------|-------------|------------|
| Consumer lag buildup | High | Medium | Monitor consumer lag, scale consumers horizontally via consumer groups |
| Data corruption in database | High | Low | Database constraints, Pydantic validation, regular backups |
| Service startup dependency issues | Medium | High | Use docker-compose depends_on with health checks |
| Debugging distributed traces | Medium | High | Implement correlation IDs across all services |
| Local development environment drift | Low | Medium | Use docker-compose for consistent environments |

## 13. Open Questions

### 13.1 Business Logic Clarifications

1. **PAN Number Validation:**
   - Should we validate PAN number checksums or just format?
   - Current decision: Format only (regex pattern)

2. **Loan Type Support:**
   - Are there additional loan types beyond PERSONAL, HOME, AUTO?
   - Should we support custom loan types?
   - Current decision: Fixed enum of three types

3. **Application Expiry:**
   - How long should applications remain in PENDING state before expiring?
   - Current decision: No expiry (can be added later)

### 13.2 Technical Implementation Questions

1. **Database Migrations:**
   - Should we support rollback migrations?
   - Current decision: Yes, use Alembic reversible migrations

2. **Kafka Partitioning Strategy:**
   - Should we partition by application_id, pan_number, or round-robin?
   - Current decision: Round-robin (3 partitions) for simplicity

3. **Monitoring and Alerting:**
   - What alerting thresholds should we set for consumer lag?
   - Current decision: Log-based monitoring, alert threshold > 1000 messages

4. **API Versioning:**
   - Should we version the API endpoints (e.g., /v1/applications)?
   - Current decision: No versioning for MVP, can add later

5. **Rate Limiting:**
   - Should we implement rate limiting on API endpoints?
   - Current decision: Not in scope for MVP

### 13.3 Testing Clarifications

1. **Load Testing:**
   - Should we perform load testing to validate < 100 msgs/sec throughput?
   - Current decision: Not required for MVP, manual testing sufficient

2. **Mock vs Real Kafka in Tests:**
   - Should unit tests use real Kafka or mocks?
   - Current decision: Mocks for unit tests, real Kafka for integration tests

---

## Next Steps

1. **Review and Approval:**
   - Review this technical design with stakeholders
   - Address any open questions or clarifications
   - Get sign-off on architecture decisions

2. **Implementation Planning:**
   - Use `/development` command to implement following TDD approach
   - Start with database schema and migrations
   - Implement prequal-api first (API + repository + Kafka producer)
   - Implement credit-service (consumer + business logic)
   - Implement decision-service (consumer + decision engine)

3. **Quality Assurance:**
   - Write unit tests alongside implementation (TDD)
   - Add integration tests after services are functional
   - Ensure 90%+ test coverage before completion

4. **Documentation:**
   - Update README.md with setup instructions
   - Document API endpoints in OpenAPI spec
   - Add architectural diagrams (optional)

---

## Revision History

### Version 1.1 (2025-10-30) - Implementation-Ready Update

**Critical Fixes Applied:**

1. **Kafka Library Fix** ⚠️ HIGH PRIORITY
   - Changed from `kafka-python` (synchronous) to `aiokafka` (async)
   - Updated all producer/consumer configurations
   - Added proper lifecycle management

2. **Idempotency Implementation** ⚠️ HIGH PRIORITY
   - Added concrete SELECT FOR UPDATE implementation
   - Documented database transaction patterns
   - Included code examples for decision-service

3. **Circuit Breaker Implementation** ⚠️ MEDIUM PRIORITY
   - Added `pybreaker` library configuration
   - Detailed usage patterns for database operations
   - Integration with consumer error handling

4. **Producer Error Handling** ⚠️ MEDIUM-HIGH PRIORITY
   - Clarified retry strategy with exponential backoff
   - Added timeout handling (5 seconds per attempt)
   - Documented failure scenarios

**Important Enhancements:**

5. **PostgreSQL Trigger** - Auto-update `updated_at` timestamp
6. **Kafka Message Serialization** - Custom JSON encoder for Decimal/UUID types
7. **Message Key Strategy** - Partition by application_id for ordering
8. **Missing Dependencies** - Added structlog, pybreaker, httpx
9. **structlog Configuration** - Complete setup with PAN masking
10. **Health Check Fix** - Updated for aiokafka compatibility
11. **Lifecycle Management** - Database and Kafka connection handling
12. **CORS Configuration** - Middleware setup for web clients

**Files Modified:**
- Section 4.2: Enhanced service descriptions
- Section 5.1: Added trigger and connection details
- Section 5.2: Added CORS configuration
- Section 5.5: Complete rewrite with concrete implementations
- Section 6.2: Updated dependencies
- Section 9.1: Added structlog configuration
- Section 9.2: Fixed health check and added lifecycle management

**Implementation Readiness:** 95% (up from 85%)

---

**Design Version:** 1.1
**Last Updated:** 2025-10-30
**Author:** Technical Architecture Team
**Reviewed By:** Senior Technical Reviewer

# decision-service

Kafka consumer microservice for making loan prequalification decisions based on credit reports.

## Overview

This microservice:
- Consumes messages from `credit_reports_generated` Kafka topic
- Applies business rules to make loan decisions
- Updates application status in PostgreSQL database

## Decision Logic

### Rules

```
IF cibil_score < 650:
    REJECT

ELSE IF monthly_income > (loan_amount / 48):
    PRE_APPROVE   (4-year loan, sufficient income)

ELSE:
    MANUAL_REVIEW (good score but tight income ratio)
```

### Outcomes
- **PRE_APPROVED**: CIBIL ≥ 650 AND sufficient income
- **REJECTED**: CIBIL < 650
- **MANUAL_REVIEW**: CIBIL ≥ 650 BUT insufficient income

## Kafka Topics

### Consumes From
- **Topic**: `credit_reports_generated`
- **Group ID**: `decision-service-group`
- **Format**: JSON

**Message Schema:**
```json
{
  "application_id": "uuid",
  "cibil_score": 685,
  "pan_number": "ABCDE1234F",
  "monthly_income_inr": 50000,
  "loan_amount_inr": 200000,
  "loan_type": "PERSONAL"
}
```

## Database Updates

Updates `applications` table:
- Sets `status` to PRE_APPROVED | REJECTED | MANUAL_REVIEW
- Sets `cibil_score` from credit report
- Uses **idempotent updates** (only updates if status=PENDING)

## Environment Variables

```bash
# Database
DATABASE_URL=postgresql+asyncpg://user:pass@localhost:5432/dbname

# Kafka
KAFKA_BOOTSTRAP_SERVERS=localhost:9092
KAFKA_TOPIC_CREDIT_REPORTS=credit_reports_generated

# Logging
LOG_LEVEL=INFO
```

## Running Locally

### Install Dependencies
```bash
cd services/decision-service
poetry install
```

### Run Consumer
```bash
poetry run python -m app.main
```

### Run Tests
```bash
poetry run pytest tests/ -v
```

## Docker

### Build Image
```bash
docker build -f services/decision-service/Dockerfile -t decision-service .
```

### Run Container
```bash
docker run \
  -e DATABASE_URL=postgresql+asyncpg://... \
  -e KAFKA_BOOTSTRAP_SERVERS=kafka:9092 \
  decision-service
```

## Architecture

```
┌─────────────────────────────────────────┐
│       decision-service                  │
├─────────────────────────────────────────┤
│  app/                                   │
│   ├── consumers/                        │
│   │   └── decision_consumer.py  ← Entry│
│   ├── services/                         │
│   │   └── decision_service.py   ← Logic│
│   └── repositories/                     │
│       └── application_repository.py     │
└─────────────────────────────────────────┘
         ▲                │
         │                ▼
  credit_reports      PostgreSQL
  (Kafka Topic)       (Database)
```

## Idempotency

The consumer is idempotent:
- Only updates applications with `status='PENDING'`
- If already processed, logs warning and continues
- Prevents duplicate processing in case of retries

## Graceful Shutdown

The consumer handles SIGTERM and SIGINT signals gracefully:
- Stops consuming new messages
- Finishes processing current message
- Commits offsets
- Closes Kafka and database connections

## Error Handling

- Validation errors are logged and skipped
- Database errors are logged and the consumer retries
- Kafka errors are logged and the consumer retries
- Unprocessable messages are logged (DLQ could be added)

## Testing

Unit tests cover:
- Decision logic (16 tests)
- CIBIL score thresholds
- Income ratio calculations
- All decision outcomes
- Edge cases and boundary conditions

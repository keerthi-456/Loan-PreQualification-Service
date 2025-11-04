# credit-service

Kafka consumer microservice for calculating CIBIL credit scores for loan applications.

## Overview

This microservice:
- Consumes messages from `loan_applications_submitted` Kafka topic
- Calculates CIBIL scores based on PAN number and income
- Publishes results to `credit_reports_generated` Kafka topic

## CIBIL Score Calculation Logic

### Special Test PANs
- `ABCDE1234F` → 790 (pre-approved candidate)
- `FGHIJ5678K` → 610 (borderline/reject candidate)

### Scoring Algorithm
```
base_score = 650

Income adjustments:
- monthly_income > 75000: +40
- monthly_income < 30000: -20

Loan type adjustments:
- PERSONAL: -10 (unsecured)
- HOME: +10 (secured)
- AUTO: 0 (neutral)

Random variation: -5 to +5

Final score clamped to: 300-900
```

## Kafka Topics

### Consumes From
- **Topic**: `loan_applications_submitted`
- **Group ID**: `credit-service-group`
- **Format**: JSON

**Message Schema:**
```json
{
  "application_id": "uuid",
  "pan_number": "ABCDE1234F",
  "applicant_name": "John Doe",
  "monthly_income_inr": 50000,
  "loan_amount_inr": 200000,
  "loan_type": "PERSONAL"
}
```

### Publishes To
- **Topic**: `credit_reports_generated`
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

## Environment Variables

```bash
# Kafka
KAFKA_BOOTSTRAP_SERVERS=localhost:9092
KAFKA_TOPIC_APPLICATIONS=loan_applications_submitted
KAFKA_TOPIC_CREDIT_REPORTS=credit_reports_generated

# Logging
LOG_LEVEL=INFO
```

## Running Locally

### Install Dependencies
```bash
cd services/credit-service
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
docker build -f services/credit-service/Dockerfile -t credit-service .
```

### Run Container
```bash
docker run \
  -e KAFKA_BOOTSTRAP_SERVERS=kafka:9092 \
  credit-service
```

## Architecture

```
┌─────────────────────────────────────────┐
│         credit-service                  │
├─────────────────────────────────────────┤
│  app/                                   │
│   ├── consumers/                        │
│   │   └── credit_consumer.py  ← Entry  │
│   └── services/                         │
│       └── credit_service.py   ← Logic  │
└─────────────────────────────────────────┘
         ▲                │
         │                ▼
    loan_apps      credit_reports
  (Kafka Topic)    (Kafka Topic)
```

## Graceful Shutdown

The consumer handles SIGTERM and SIGINT signals gracefully:
- Stops consuming new messages
- Finishes processing current message
- Commits offsets
- Closes Kafka connections

## Error Handling

- Validation errors are logged and skipped
- Kafka errors are logged and the consumer retries
- Unprocessable messages are logged (DLQ could be added)

## Testing

Unit tests cover:
- CIBIL score calculation logic (14 tests)
- Special PAN handling
- Income-based adjustments
- Loan type adjustments
- Score clamping (300-900 range)

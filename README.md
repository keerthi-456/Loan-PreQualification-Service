# Loan Prequalification Service

Event-driven microservices system for processing loan prequalification applications in the Indian financial market.

## 🏗️ Architecture

The system consists of **3 independent microservices** communicating via Apache Kafka:

```
┌──────────────┐         ┌──────────────┐         ┌──────────────┐
│  prequal-api │────────>│credit-service│────────>│decision-service│
│  (REST API)  │  Kafka  │(CIBIL calc)  │  Kafka  │(Decision rule)│
└──────────────┘         └──────────────┘         └──────────────┘
       │                                                    │
       ▼                                                    ▼
  PostgreSQL                                          PostgreSQL
```

### Microservices

1. **prequal-api** - FastAPI REST API
   - POST /applications - Submit loan application
   - GET /applications/{id}/status - Check status
   - GET /health - Health check

2. **credit-service** - Kafka Consumer
   - Calculates CIBIL credit scores
   - Publishes credit reports to Kafka

3. **decision-service** - Kafka Consumer
   - Makes loan prequalification decisions
   - Updates database with final status

## 🚀 Quick Start

### Prerequisites

- Docker & Docker Compose
- Python 3.11+ (for local development)
- Poetry (for local development)

### One-Command Startup

\`\`\`bash
make docker-up
\`\`\`

This starts:
- PostgreSQL database
- Zookeeper
- Kafka broker
- prequal-api (port 8000)
- credit-service
- decision-service

### Access the API

- **API Base**: http://localhost:8000
- **API Documentation**: http://localhost:8000/docs
- **Health Check**: http://localhost:8000/health

## 📝 API Usage

### Submit Application

\`\`\`bash
curl -X POST http://localhost:8000/applications \\
  -H "Content-Type: application/json" \\
  -d '{
    "pan_number": "ABCDE1234F",
    "applicant_name": "Rajesh Kumar",
    "monthly_income_inr": 75000,
    "loan_amount_inr": 500000,
    "loan_type": "PERSONAL"
  }'
\`\`\`

## 🐳 Docker Commands

\`\`\`bash
make docker-up           # Start all services
make docker-down         # Stop all services
make docker-logs         # View logs
make docker-ps           # Show running containers
\`\`\`

## 📁 Project Structure

See [RESTRUCTURING_PLAN.md](RESTRUCTURING_PLAN.md) for complete details.

\`\`\`
services/
├── prequal-api/         ← FastAPI REST API
├── credit-service/      ← CIBIL Consumer
├── decision-service/    ← Decision Consumer
└── shared/             ← Common Library
\`\`\`

## 📚 Documentation

- [services/prequal-api/README.md](services/prequal-api/README.md)
- [services/credit-service/README.md](services/credit-service/README.md)
- [services/decision-service/README.md](services/decision-service/README.md)
- [RESTRUCTURING_PLAN.md](RESTRUCTURING_PLAN.md)

## 📈 Project Status

**100% Complete** - All microservices implemented and ready to run! 🎉

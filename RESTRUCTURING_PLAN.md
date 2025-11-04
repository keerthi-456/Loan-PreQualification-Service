# Microservices Restructuring Plan

**Date**: 2025-11-03
**Objective**: Reorganize monorepo into clear microservice boundaries
**Approach**: Separate folders per microservice with shared library

---

## 🎯 Goals

1. **Clear Separation**: Each microservice in its own folder
2. **Independent Deployment**: Each service can be built/deployed separately
3. **Shared Code**: Common code in a shared library
4. **Smaller Docker Images**: Only include service-specific code
5. **Better Maintainability**: Clear ownership and boundaries

---

## 📊 Current Structure (Before)

```
loan-prequalification-service/
├── src/
│   └── app/                     ← Everything mixed together
│       ├── api/routes/          ← Only for prequal-api
│       ├── services/            ← Used by all microservices
│       ├── consumers/           ← Empty (should have consumers)
│       ├── kafka/               ← Shared
│       ├── core/                ← Shared
│       ├── models/              ← Shared
│       ├── repositories/        ← Shared
│       ├── schemas/             ← Shared
│       ├── exceptions/          ← Shared
│       └── main.py              ← Only for prequal-api
├── tests/
│   ├── unit/services/           ← Mixed tests
│   └── integration/             ← prequal-api tests only
├── alembic/                     ← Database migrations
└── pyproject.toml               ← Single dependency file
```

**Problems:**
- ❌ Can't distinguish which code belongs to which service
- ❌ Deploying any service means including ALL code
- ❌ Changes to one service affect all services
- ❌ Testing is unclear (which tests for which service?)
- ❌ Docker images would be bloated

---

## 🏗️ New Structure (After)

```
loan-prequalification-service/
├── services/                    ← All microservices
│   ├── prequal-api/
│   │   ├── app/
│   │   │   ├── api/
│   │   │   │   └── routes/
│   │   │   │       ├── applications.py
│   │   │   │       └── health.py
│   │   │   ├── services/
│   │   │   │   └── application_service.py
│   │   │   ├── repositories/
│   │   │   │   └── application_repository.py
│   │   │   ├── kafka/
│   │   │   │   └── producer.py
│   │   │   └── main.py
│   │   ├── tests/
│   │   │   ├── unit/
│   │   │   └── integration/
│   │   ├── Dockerfile
│   │   ├── pyproject.toml       ← Service-specific dependencies
│   │   └── README.md
│   │
│   ├── credit-service/
│   │   ├── app/
│   │   │   ├── consumers/
│   │   │   │   └── credit_consumer.py  ← NEW
│   │   │   ├── services/
│   │   │   │   └── credit_service.py
│   │   │   ├── kafka/
│   │   │   │   └── producer.py
│   │   │   └── main.py           ← NEW
│   │   ├── tests/
│   │   │   └── unit/
│   │   ├── Dockerfile
│   │   ├── pyproject.toml
│   │   └── README.md
│   │
│   ├── decision-service/
│   │   ├── app/
│   │   │   ├── consumers/
│   │   │   │   └── decision_consumer.py  ← NEW
│   │   │   ├── services/
│   │   │   │   └── decision_service.py
│   │   │   ├── repositories/
│   │   │   │   └── application_repository.py
│   │   │   └── main.py           ← NEW
│   │   ├── tests/
│   │   │   └── unit/
│   │   ├── Dockerfile
│   │   ├── pyproject.toml
│   │   └── README.md
│   │
│   └── shared/                   ← Common library
│       ├── shared/
│       │   ├── models/
│       │   │   └── application.py
│       │   ├── schemas/
│       │   │   ├── application.py
│       │   │   └── kafka_messages.py
│       │   ├── core/
│       │   │   ├── config.py
│       │   │   ├── database.py
│       │   │   └── logging.py
│       │   └── exceptions/
│       │       └── exceptions.py
│       ├── pyproject.toml
│       └── README.md
│
├── alembic/                      ← Keep at root (shared migrations)
├── docker-compose.yml            ← NEW
├── Makefile                      ← Update with new commands
├── pyproject.toml                ← Root workspace config
└── README.md                     ← Update with new structure
```

**Benefits:**
- ✅ Crystal clear microservice boundaries
- ✅ Each service is independently deployable
- ✅ Smaller Docker images (only service code + shared lib)
- ✅ Clear test ownership
- ✅ Easy to scale teams (one team per service)
- ✅ Shared code is explicitly a "library"

---

## 📦 File Movement Plan

### 1. prequal-api (API Service)

**Move these files:**
```
FROM                                    TO
------------------------------------------------------------------------
src/app/main.py                    →   services/prequal-api/app/main.py
src/app/api/routes/                →   services/prequal-api/app/api/routes/
src/app/repositories/              →   services/prequal-api/app/repositories/
src/app/services/application_*     →   services/prequal-api/app/services/
src/app/kafka/producer.py          →   services/prequal-api/app/kafka/producer.py
tests/integration/                 →   services/prequal-api/tests/integration/
```

**Create new files:**
- `services/prequal-api/Dockerfile`
- `services/prequal-api/pyproject.toml`
- `services/prequal-api/README.md`

### 2. credit-service (CIBIL Consumer)

**Move these files:**
```
FROM                                    TO
------------------------------------------------------------------------
src/app/services/credit_service.py →   services/credit-service/app/services/credit_service.py
tests/unit/services/test_credit_*  →   services/credit-service/tests/unit/
```

**Create new files:**
- `services/credit-service/app/main.py` ← NEW entry point
- `services/credit-service/app/consumers/credit_consumer.py` ← NEW
- `services/credit-service/app/kafka/producer.py` ← NEW (copy pattern)
- `services/credit-service/Dockerfile`
- `services/credit-service/pyproject.toml`
- `services/credit-service/README.md`

### 3. decision-service (Decision Consumer)

**Move these files:**
```
FROM                                    TO
------------------------------------------------------------------------
src/app/services/decision_service.py →  services/decision-service/app/services/decision_service.py
src/app/repositories/              →    services/decision-service/app/repositories/
tests/unit/services/test_decision_* →   services/decision-service/tests/unit/
```

**Create new files:**
- `services/decision-service/app/main.py` ← NEW entry point
- `services/decision-service/app/consumers/decision_consumer.py` ← NEW
- `services/decision-service/Dockerfile`
- `services/decision-service/pyproject.toml`
- `services/decision-service/README.md`

### 4. shared (Common Library)

**Move these files:**
```
FROM                                    TO
------------------------------------------------------------------------
src/app/models/                    →   services/shared/shared/models/
src/app/schemas/                   →   services/shared/shared/schemas/
src/app/core/                      →   services/shared/shared/core/
src/app/exceptions/                →   services/shared/shared/exceptions/
```

**Create new files:**
- `services/shared/pyproject.toml` ← Installable package
- `services/shared/README.md`

---

## 🔧 Import Changes

### Before (Current)
```python
from app.models.application import Application
from app.services.credit_service import calculate_cibil_score
from app.core.config import settings
```

### After (New)
```python
# In any microservice
from shared.models.application import Application
from shared.core.config import settings
from shared.schemas.kafka_messages import LoanApplicationMessage

# Service-specific imports
# In prequal-api
from app.services.application_service import ApplicationService

# In credit-service
from app.services.credit_service import calculate_cibil_score
```

---

## 🐳 Docker Strategy

### Each Microservice Dockerfile

```dockerfile
# services/prequal-api/Dockerfile
FROM python:3.11-slim

WORKDIR /app

# Install shared library first
COPY services/shared /tmp/shared
RUN pip install /tmp/shared

# Install service dependencies
COPY services/prequal-api/pyproject.toml .
RUN pip install poetry && poetry install --no-dev

# Copy service code
COPY services/prequal-api/app ./app

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### docker-compose.yml

```yaml
version: '3.8'

services:
  postgres:
    image: postgres:15
    environment:
      POSTGRES_DB: loan_prequalification
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: postgres
    ports:
      - "5432:5432"

  zookeeper:
    image: confluentinc/cp-zookeeper:latest
    environment:
      ZOOKEEPER_CLIENT_PORT: 2181

  kafka:
    image: confluentinc/cp-kafka:latest
    depends_on:
      - zookeeper
    environment:
      KAFKA_ZOOKEEPER_CONNECT: zookeeper:2181
      KAFKA_ADVERTISED_LISTENERS: PLAINTEXT://kafka:9092
    ports:
      - "9092:9092"

  prequal-api:
    build:
      context: .
      dockerfile: services/prequal-api/Dockerfile
    ports:
      - "8000:8000"
    depends_on:
      - postgres
      - kafka
    environment:
      DATABASE_URL: postgresql+asyncpg://postgres:postgres@postgres:5432/loan_prequalification
      KAFKA_BOOTSTRAP_SERVERS: kafka:9092

  credit-service:
    build:
      context: .
      dockerfile: services/credit-service/Dockerfile
    depends_on:
      - kafka
    environment:
      KAFKA_BOOTSTRAP_SERVERS: kafka:9092

  decision-service:
    build:
      context: .
      dockerfile: services/decision-service/Dockerfile
    depends_on:
      - kafka
      - postgres
    environment:
      DATABASE_URL: postgresql+asyncpg://postgres:postgres@postgres:5432/loan_prequalification
      KAFKA_BOOTSTRAP_SERVERS: kafka:9092
```

---

## 📝 Dependencies Management

### Root pyproject.toml (Workspace)
```toml
[tool.poetry]
name = "loan-prequalification-service"
version = "1.0.0"
description = "Microservices workspace"

# Workspace configuration (Poetry doesn't support workspaces natively,
# but we can document the structure)
```

### services/shared/pyproject.toml
```toml
[tool.poetry]
name = "loan-prequalification-shared"
version = "1.0.0"
packages = [{include = "shared"}]

[tool.poetry.dependencies]
python = "^3.11"
pydantic = "^2.0"
pydantic-settings = "^2.0"
sqlalchemy = {extras = ["asyncio"], version = "^2.0"}
structlog = "^23.2.0"
```

### services/prequal-api/pyproject.toml
```toml
[tool.poetry]
name = "prequal-api"
version = "1.0.0"
packages = [{include = "app"}]

[tool.poetry.dependencies]
python = "^3.11"
fastapi = "^0.104.0"
uvicorn = {extras = ["standard"], version = "^0.24.0"}
aiokafka = "^0.8.1"
asyncpg = "^0.29.0"
loan-prequalification-shared = {path = "../shared", develop = true}
```

### services/credit-service/pyproject.toml
```toml
[tool.poetry]
name = "credit-service"
version = "1.0.0"
packages = [{include = "app"}]

[tool.poetry.dependencies]
python = "^3.11"
aiokafka = "^0.8.1"
loan-prequalification-shared = {path = "../shared", develop = true}
```

### services/decision-service/pyproject.toml
```toml
[tool.poetry]
name = "decision-service"
version = "1.0.0"
packages = [{include = "app"}]

[tool.poetry.dependencies]
python = "^3.11"
aiokafka = "^0.8.1"
asyncpg = "^0.29.0"
loan-prequalification-shared = {path = "../shared", develop = true}
```

---

## ✅ Migration Steps

### Phase 1: Setup New Structure (No Breaking Changes)
1. Create `services/` directory
2. Create `services/shared/` with copied code
3. Create `services/prequal-api/` structure
4. Create `services/credit-service/` structure
5. Create `services/decision-service/` structure

### Phase 2: Move prequal-api (First Service)
1. Copy files to `services/prequal-api/`
2. Update imports to use `shared.*`
3. Create Dockerfile
4. Test that prequal-api works standalone

### Phase 3: Move credit-service
1. Copy credit_service.py
2. Create consumer entry point
3. Update imports
4. Create Dockerfile
5. Test consumer

### Phase 4: Move decision-service
1. Copy decision_service.py
2. Create consumer entry point
3. Update imports
4. Create Dockerfile
5. Test consumer

### Phase 5: Create Docker Compose
1. Create docker-compose.yml
2. Test full system integration
3. Run E2E tests

### Phase 6: Clean Up
1. Delete old `src/` directory
2. Update all documentation
3. Update README.md
4. Archive RESTRUCTURING_PLAN.md

---

## 🧪 Testing Strategy

### During Migration
- ✅ Keep all unit tests passing after each move
- ✅ Test each microservice independently
- ✅ Test with docker-compose before cleanup

### After Migration
- Run all unit tests: `make test-unit`
- Run integration tests: `make test-integration`
- Run E2E tests: `make test-e2e`
- Manual smoke testing of each service

---

## 📚 Documentation Updates

Files to update:
- `README.md` - New structure, setup instructions
- `DEVELOPMENT.md` - Update file paths
- `CLAUDE.md` - Update project structure section
- `PHASE2_COMPLETE.md` - Note restructuring
- Create `services/*/README.md` for each service

---

## ⚠️ Risks & Mitigation

| Risk | Impact | Mitigation |
|------|--------|------------|
| Breaking existing code | High | Test after each step |
| Import path errors | Medium | Use find/replace, test thoroughly |
| Lost git history | Low | Use `git mv` to preserve history |
| Broken tests | Medium | Update test paths incrementally |
| CI/CD pipeline breaks | High | Update CI config in parallel |

---

## 🎯 Expected Outcome

After restructuring:
- ✅ 3 independent microservices
- ✅ 1 shared library
- ✅ Clear boundaries and ownership
- ✅ Smaller Docker images
- ✅ Independent deployment capability
- ✅ Better developer experience
- ✅ Scalable architecture

---

## 📊 Estimated Effort

| Phase | Time Estimate | Complexity |
|-------|---------------|------------|
| Phase 1: Setup | 1 hour | Low |
| Phase 2: prequal-api | 2 hours | Medium |
| Phase 3: credit-service | 1.5 hours | Medium |
| Phase 4: decision-service | 1.5 hours | Medium |
| Phase 5: Docker Compose | 2 hours | Medium-High |
| Phase 6: Cleanup | 1 hour | Low |
| **Total** | **9 hours** | **Medium** |

---

**Status**: ⏸️ Awaiting approval to proceed
**Next Step**: Begin Phase 1 - Setup new structure

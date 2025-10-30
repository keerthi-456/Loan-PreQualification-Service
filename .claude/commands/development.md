# Development Backend Python FastAPI Command

## Command Configuration

**Command name:** `development-backend-python-fastapi`

**Command usage:**
/clear
/development-backend-python-fastapi Tech design is in tech-design.md
/cost
Copy
## Command Details

You are a Senior Python Developer and Solutions Architect with 10+ years of experience in building scalable event-driven microservices using Python and modern async frameworks.

Please use the following Tech Design as a reference for your development: **$TECH_DESIGN**

## Technical Stack

### Core Technologies
- **Python**: 3.11+
- **Framework**: FastAPI 0.104+
- **Validation**: Pydantic 2.0+
- **Database**: PostgreSQL with asyncpg
- **ORM**: SQLAlchemy 2.0+ (async)
- **Message Broker**: Apache Kafka with kafka-python or aiokafka
- **Dependency Management**: Poetry
- **Testing**: pytest, pytest-asyncio, pytest-cov
- **Code Quality**: Ruff (linting), Black (formatting), mypy (type checking)
- **Containerization**: Docker, Docker Compose
- **Documentation**: FastAPI automatic OpenAPI 3.0

## Development Methodology

### TDD Approach (Mandatory)
Follow the Red-Green-Refactor cycle:

1. **🔴 RED**: Write failing unit tests for business logic first
2. **🟢 GREEN**: Implement minimum code to make tests pass
3. **🔄 REFACTOR**: Improve design while keeping tests green
4. **🔗 INTEGRATE**: Add integration tests after unit tests pass
5. **📊 COVERAGE**: Ensure 85%+ test coverage

### Test-Driven Development Flow
Write Test → Run Test (Fail) → Write Code → Run Test (Pass) → Refactor → Repeat
Copy
## Architecture Patterns

### Layered Architecture
Router → Service → Repository → Database
→ Producer → Kafka
Consumer → Service → Repository → Database
Copy
### Key Components
- **Routers**: FastAPI route handlers (async)
- **Services**: Business logic layer with async methods
- **Repositories**: Data access layer with async database operations
- **Schemas**: Pydantic models for validation and serialization
- **Producers**: Kafka message producers
- **Consumers**: Kafka message consumers
- **Models**: SQLAlchemy ORM models
- **Dependencies**: Dependency injection for database sessions and services

## Implementation Requirements

### REST API Standards
- ✅ Proper HTTP status codes (200, 201, 202, 400, 404, 422, 500)
- ✅ Input validation using Pydantic models
- ✅ Global exception handling with custom exception handlers
- ✅ Structured logging with correlation IDs
- ✅ Async/await for all I/O-bound operations
- ✅ Response models for type safety and documentation

### Event-Driven Standards
- ✅ Well-defined Kafka topic structure
- ✅ Pydantic schemas for message validation
- ✅ Producer with error handling and retries
- ✅ Consumer with graceful shutdown
- ✅ Idempotent message processing
- ✅ Dead letter queue (DLQ) strategy
- ✅ Consumer lag monitoring approach

### Database Standards
- ✅ Async database operations with asyncpg
- ✅ Connection pooling configuration
- ✅ Database migrations with Alembic
- ✅ Proper transaction management
- ✅ Optimized queries with proper indexing

### Infrastructure
- ✅ Docker Compose for local orchestration
- ✅ Health check endpoints
- ✅ Graceful shutdown handling
- ✅ Environment-based configuration
- ✅ Secrets management

## Testing Strategy

### Test Types & Approaches

| Test Type | Framework | Purpose |
|-----------|-----------|----------|
| **Unit Tests** | pytest + unittest.mock | Service layer with mocked dependencies |
| **Repository Tests** | pytest + pytest-asyncio | Database layer with test database |
| **Router Tests** | pytest + TestClient | API endpoints testing |
| **Integration Tests** | pytest + Docker Compose | Full application with Kafka and PostgreSQL |
| **Consumer Tests** | pytest + mocked Kafka | Consumer logic testing |
| **End-to-End Tests** | pytest | Complete workflow validation |

### Testing Best Practices
- Use `pytest` fixtures for reusable test components
- Mock external dependencies (Kafka, database) in unit tests
- Use `pytest-asyncio` for async test functions
- Use `TestClient` from FastAPI for API testing
- Use Docker Compose for integration tests
- Achieve 85%+ code coverage with `pytest-cov`

## Quality Gates

### Code Quality Requirements
- ❌ Zero linting errors (Ruff)
- ✨ Code formatted with Black
- 🔍 Type hints validated with mypy
- 📊 Test coverage ≥ 85%
- 🔒 No security vulnerabilities (Bandit, Safety)
- ⚡ API response time < 200ms
- 📚 Complete OpenAPI documentation with examples
- ✅ All pre-commit hooks passing

## Project Structure
project/
├── src/
│   └── app/
│       ├── api/
│       │   ├── routes/          # FastAPI routers
│       │   ├── dependencies.py  # Dependency injection
│       │   └── middleware.py    # Custom middleware
│       ├── services/            # Business logic
│       ├── repositories/        # Data access layer
│       ├── models/              # SQLAlchemy ORM models
│       ├── schemas/             # Pydantic models
│       ├── kafka/
│       │   ├── producer.py      # Kafka producer
│       │   └── consumer.py      # Kafka consumer
│       ├── core/
│       │   ├── config.py        # Configuration
│       │   ├── database.py      # Database setup
│       │   └── logging.py       # Logging configuration
│       ├── exceptions/          # Custom exceptions
│       └── main.py              # Application entry point
├── tests/
│   ├── unit/                    # Unit tests
│   ├── integration/             # Integration tests
│   └── conftest.py              # Pytest fixtures
├── alembic/                     # Database migrations
├── docker/                      # Dockerfiles
├── docker-compose.yml           # Local orchestration
├── pyproject.toml               # Poetry configuration
├── Makefile                     # Development commands
├── .pre-commit-config.yaml      # Pre-commit hooks
└── README.md                    # Documentation
Copy
## Development Guidelines

### Code Standards
1. **Follow PEP 8** and use Black for formatting
2. **Use type hints** for all function signatures
3. **Use async/await** for all I/O-bound operations
4. **Apply SOLID principles**
5. **Write self-documenting code** with clear variable names
6. **Use Pydantic** for all data validation
7. **Handle exceptions** explicitly with custom exception classes
8. **Use dependency injection** for testability
9. **Keep functions small** and focused (< 20 lines)
10. **Use context managers** for resource management

### Async Best Practices
- Use `async def` for I/O-bound functions
- Use `await` for async operations
- Use `asyncio.gather()` for concurrent operations
- Properly manage database sessions with async context managers
- Use async database drivers (asyncpg, aiokafka)
- Handle connection lifecycle properly (startup/shutdown events)

### Kafka Best Practices
- Design idempotent consumers
- Implement proper error handling and retries
- Use consumer groups for scalability
- Handle graceful shutdown with signal handlers
- Implement DLQ for failed messages
- Log consumer lag metrics
- Use correlation IDs for message tracing

### Documentation Requirements
- **OpenAPI 3.0**: Automatic generation via FastAPI with examples
- **Docstrings**: Google-style docstrings for all public functions and classes
- **Type Hints**: Complete type annotations
- **README**: Comprehensive setup, usage, and deployment instructions
- **Architecture Diagram**: System architecture visualization

## CI/CD Configuration

### Pre-commit Hooks
```yaml
# .pre-commit-config.yaml
repos:
  - repo: https://github.com/astral-sh/ruff-pre-commit
    hooks:
      - id: ruff
        args: [--fix]
  - repo: https://github.com/psf/black
    hooks:
      - id: black
  - repo: https://github.com/pre-commit/mirrors-mypy
    hooks:
      - id: mypy
Makefile Commands
makefileCopylint:           # Run Ruff linting
format:         # Run Black formatting
type-check:     # Run mypy type checking
test:           # Run pytest with coverage
test-unit:      # Run unit tests only
test-integration: # Run integration tests
run-local:      # Start services with docker-compose
db-migrate:     # Run Alembic migrations
clean:          # Clean temporary files
Expected Deliverables
Generate complete implementation including:
Core Application

 FastAPI application with proper project structure
 All architectural layers (Routers, Services, Repositories)
 Pydantic schemas for validation and serialization
 SQLAlchemy models with proper relationships
 Alembic migrations for database schema

Event-Driven Components

 Kafka producer with error handling
 Kafka consumer with graceful shutdown
 Message schemas with Pydantic models
 DLQ implementation for failed messages

Testing Suite

 Unit tests with mocked dependencies
 Integration tests with Docker Compose
 API tests using TestClient
 Consumer tests with mocked Kafka
 pytest fixtures for reusable test components
 85%+ test coverage verified with pytest-cov

Quality & Documentation

 Pre-commit hooks configured (Ruff, Black, mypy)
 Makefile with standard commands
 Docker Compose configuration
 OpenAPI documentation with examples
 README.md with comprehensive documentation
 Type hints throughout the codebase

Configuration & Deployment

 Poetry configuration (pyproject.toml)
 Environment configuration (.env support)
 Docker configuration for services
 Health check endpoints
 Logging configuration with structured logging
 Error handling with custom exception handlers

Code Quality Checklist
Before considering implementation complete, verify:

 All code passes Ruff linting
 All code is formatted with Black
 All functions have type hints
 Mypy type checking passes
 Test coverage ≥ 85%
 All tests pass
 Pre-commit hooks configured and passing
 OpenAPI documentation is complete
 README has setup instructions
 Docker Compose works for local development
 Database migrations are tested
 Kafka producers/consumers handle errors gracefully
 Async patterns are used correctly
 Connection pooling is configured
 Health check endpoints work
 Structured logging is implemented
 Exception handling is comprehensive


Note: All implementations must follow enterprise-grade standards, leverage async/await patterns properly, handle event-driven scenarios robustly, and be production-ready with comprehensive testing and documentation.

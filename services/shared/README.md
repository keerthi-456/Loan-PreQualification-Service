# Shared Library

Common code shared across all microservices in the loan prequalification system.

## What's Included

- **models/** - SQLAlchemy ORM models (Application model)
- **schemas/** - Pydantic schemas for validation
  - `application.py` - API request/response models
  - `kafka_messages.py` - Kafka message schemas
- **core/** - Core infrastructure
  - `config.py` - Environment configuration
  - `database.py` - Database connection and session management
  - `logging.py` - Structured logging configuration
- **exceptions/** - Custom exception classes

## Installation

This library is installed as a local dependency in each microservice:

```toml
[tool.poetry.dependencies]
loan-prequalification-shared = {path = "../shared", develop = true}
```

## Usage

```python
# Import shared models
from shared.models.application import Application

# Import shared schemas
from shared.schemas.application import LoanApplicationRequest
from shared.schemas.kafka_messages import LoanApplicationMessage

# Import configuration
from shared.core.config import settings

# Import database utilities
from shared.core.database import get_db, Base

# Import logging
from shared.core.logging import get_logger

# Import exceptions
from shared.exceptions.exceptions import ApplicationNotFoundError
```

## Development

To install for development:

```bash
cd services/shared
poetry install
```

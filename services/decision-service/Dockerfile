# Multi-stage build for decision-service microservice
FROM python:3.11-slim as builder

# Install system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Install Poetry
RUN pip install poetry==1.7.0

# Set working directory
WORKDIR /build

# Copy shared library
COPY services/shared /build/shared
WORKDIR /build/shared
RUN poetry build

# Copy service dependencies
WORKDIR /build/decision-service
COPY services/decision-service/pyproject.toml services/decision-service/poetry.lock* ./

# Install dependencies
RUN poetry config virtualenvs.create false \
    && poetry install --no-dev --no-root

# Install built shared library
RUN pip install /build/shared/dist/*.whl

# Final stage
FROM python:3.11-slim

# Install runtime dependencies
RUN apt-get update && apt-get install -y \
    libpq5 \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user
RUN useradd -m -u 1000 appuser

# Set working directory
WORKDIR /app

# Copy installed packages from builder
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Copy application code
COPY services/decision-service/app ./app

# Change ownership
RUN chown -R appuser:appuser /app

# Switch to non-root user
USER appuser

# Run application
CMD ["python", "-m", "app.main"]

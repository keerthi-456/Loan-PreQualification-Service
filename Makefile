.PHONY: help install lint format type-check test test-unit test-integration docker-up docker-down docker-logs docker-ps docker-build docker-clean db-migrate db-rollback clean

help: ## Show this help message
	@echo 'Usage: make [target]'
	@echo ''
	@echo 'Available targets:'
	@awk 'BEGIN {FS = ":.*?## "} /^[a-zA-Z_-]+:.*?## / {printf "  %-20s %s\n", $$1, $$2}' $(MAKEFILE_LIST)

install: ## Install dependencies with Poetry
	poetry install

lint: ## Run Ruff linting
	poetry run ruff check src/ tests/

format: ## Format code with Black and Ruff
	poetry run black src/ tests/
	poetry run ruff check --fix src/ tests/

type-check: ## Run mypy type checking
	poetry run mypy src/

test: ## Run all tests with coverage
	poetry run pytest tests/ --cov=src/app --cov-report=html --cov-report=term --cov-fail-under=85

test-unit: ## Run only unit tests
	poetry run pytest tests/unit/ --cov=src/app/services --cov-report=term --no-cov-on-fail

test-integration: ## Run integration tests with Docker Compose
	docker-compose up -d postgres kafka
	sleep 10
	poetry run pytest tests/integration/ --no-cov
	docker-compose down

run-local: ## Start all services with docker-compose
	docker-compose up --build

run-api: ## Run FastAPI development server locally
	poetry run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

db-migrate: ## Run Alembic database migrations
	poetry run alembic upgrade head

db-rollback: ## Rollback last migration
	poetry run alembic downgrade -1

clean: ## Clean up containers, cache, and temporary files
	docker-compose down -v
	rm -rf .pytest_cache
	rm -rf htmlcov
	rm -rf .coverage
	rm -rf .ruff_cache
	rm -rf .mypy_cache
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete

pre-commit-install: ## Install pre-commit hooks
	poetry run pre-commit install

pre-commit-run: ## Run pre-commit hooks on all files
	poetry run pre-commit run --all-files

docker-build: ## Build Docker images
	docker-compose build

docker-logs: ## Show Docker container logs
	docker-compose logs -f

docker-ps: ## Show running Docker containers
	docker-compose ps

docker-up: ## Start all services with docker-compose
	docker-compose up -d
	@echo ""
	@echo "Services are starting..."
	@echo "API: http://localhost:8000"
	@echo "Docs: http://localhost:8000/docs"
	@echo "Health: http://localhost:8000/health"
	@echo ""
	@echo "To view logs: make docker-logs"

docker-down: ## Stop all Docker containers
	docker-compose down

docker-restart: ## Restart all Docker containers
	docker-compose restart

docker-clean: ## Stop and remove all containers, networks, and volumes
	docker-compose down -v
	docker system prune -f

docker-shell-prequal: ## Open shell in prequal-api container
	docker exec -it loan-prequal-api /bin/sh

docker-shell-credit: ## Open shell in credit-service container
	docker exec -it loan-credit-service /bin/sh

docker-shell-decision: ## Open shell in decision-service container
	docker exec -it loan-decision-service /bin/sh

docker-shell-postgres: ## Open PostgreSQL shell
	docker exec -it loan-postgres psql -U postgres -d loan_prequalification

test-e2e: ## Run end-to-end tests with full system
	@echo "Starting full system..."
	docker-compose up -d
	@echo "Waiting for services to be ready..."
	sleep 30
	@echo "Running E2E tests..."
	# TODO: Create E2E tests
	@echo "E2E tests not implemented yet"
	docker-compose down

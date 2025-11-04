#!/bin/bash
# Per-service test runner for monorepo structure
# Runs tests for each service independently and aggregates coverage

set -e

echo "=========================================="
echo "Running Per-Service Test Suite"
echo "=========================================="

# Clean up old coverage data
rm -f .coverage .coverage.*
rm -rf htmlcov

# Array to track test results
declare -a FAILED_SERVICES=()

# Function to run tests for a service
run_service_tests() {
    local service_name=$1
    local service_path=$2

    echo ""
    echo "=========================================="
    echo "Testing: $service_name"
    echo "=========================================="

    # Run from project root to use root virtualenv
    set +e  # Don't exit on error
    poetry run pytest "$service_path/tests/" -v --cov="$service_path/app" --cov-report= 2>&1
    EXIT_CODE=$?
    set -e  # Re-enable exit on error

    # Check exit code to track failures
    if [ $EXIT_CODE -eq 0 ]; then
        echo "✅ $service_name tests PASSED"
    else
        echo "⚠️  $service_name had test failures (coverage still collected)"
        FAILED_SERVICES+=("$service_name")
    fi

    # Rename coverage data
    if [ -f .coverage ]; then
        mv .coverage ".coverage.$service_name"
        echo "📊 Coverage data saved for $service_name"
    else
        echo "⚠️  No coverage file found for $service_name"
    fi
}

# Store original directory
PROJECT_ROOT=$(pwd)

# Run tests for each service
run_service_tests "prequal-api" "services/prequal-api"
run_service_tests "credit-service" "services/credit-service"
run_service_tests "decision-service" "services/decision-service"

# Combine coverage data
echo ""
echo "=========================================="
echo "Combining Coverage Data"
echo "=========================================="

if ls .coverage.* 1> /dev/null 2>&1; then
    # List coverage files found
    echo "Found coverage files:"
    ls -1 .coverage.*

    poetry run coverage combine
    echo "✅ Coverage data combined"
else
    echo "⚠️  No coverage data found"
    exit 1
fi

# Generate coverage report
echo ""
echo "=========================================="
echo "Coverage Report"
echo "=========================================="

# Show per-file coverage
poetry run coverage report

# Generate HTML report
poetry run coverage html

# Get total coverage percentage
COVERAGE=$(poetry run coverage report | grep TOTAL | awk '{print $NF}' | sed 's/%//')

echo ""
echo "=========================================="
echo "Test Summary"
echo "=========================================="
echo "Total Coverage: ${COVERAGE}%"
echo "Target Coverage: 85%"

if [ ${#FAILED_SERVICES[@]} -eq 0 ]; then
    echo "✅ All service tests passed"
else
    echo "❌ Failed services: ${FAILED_SERVICES[*]}"
fi

# Check if coverage meets threshold
if (( $(echo "$COVERAGE >= 85" | bc -l) )); then
    echo "✅ Coverage threshold met!"
    exit 0
else
    echo "❌ Coverage below 85% threshold"
    echo "   Current: ${COVERAGE}%"
    echo "   Required: 85%"
    exit 1
fi

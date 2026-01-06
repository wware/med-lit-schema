#!/bin/bash -xe

echo "=========================================="
echo "Running Linters and Tests"
echo "=========================================="

# Ensure uv is available
if ! command -v uv &> /dev/null; then
    echo "Error: uv not found. Please install uv first."
    echo "See: https://docs.astral.sh/uv/getting-started/installation/"
    exit 1
fi

echo ""
echo "UV Version:"
uv --version

echo ""
echo "=========================================="
echo "Running ruff check..."
echo "=========================================="
uv run ruff check .

echo ""
echo "=========================================="
echo "Running ruff format check..."
echo "=========================================="
uv run ruff format --check .

echo ""
echo "=========================================="
echo "Running black check..."
echo "=========================================="
uv run black --check .

echo ""
echo "=========================================="
echo "Running flake8..."
echo "=========================================="
uv run flake8 . --count --show-source --statistics --exclude=.venv

echo ""
echo "=========================================="
echo "Running pylint..."
echo "=========================================="
uv run pylint *.py tests/*.py || true  # Don't fail on pylint warnings

echo ""
echo "=========================================="
echo "Stopping any existing containers..."
echo "=========================================="
# Stop and remove any existing containers to avoid conflicts
docker compose down 2>/dev/null || true
# Also try to stop containers by name in case they're from a different compose file
docker stop med-lit-postgres med-lit-redis 2>/dev/null || true
docker rm med-lit-postgres med-lit-redis 2>/dev/null || true

echo ""
echo "=========================================="
echo "Starting Docker services (PostgreSQL & Redis)..."
echo "=========================================="
docker compose up -d postgres redis

# Wait for services to be healthy
echo "Waiting for services to be ready..."
timeout=60
elapsed=0
while [ $elapsed -lt $timeout ]; do
    if docker compose ps postgres redis | grep -q "healthy"; then
        echo "Services are ready!"
        break
    fi
    sleep 2
    elapsed=$((elapsed + 2))
    echo "  Waiting... (${elapsed}s)"
done

# Check if services are actually ready
if ! docker compose ps postgres redis | grep -q "healthy"; then
    echo "Warning: Services may not be fully ready, but continuing..."
fi

# Setup database schema if needed
echo ""
echo "Setting up database schema..."
export DATABASE_URL="postgresql://postgres:postgres@localhost:5432/medlit"
uv run python setup_database.py || echo "Warning: Database setup may have failed, but continuing..."

echo ""
echo "=========================================="
echo "Running pytest..."
echo "=========================================="
# Run pytest and capture exit code
pytest_exit_code=0
uv run pytest tests/ -v || pytest_exit_code=$?

echo ""
echo "=========================================="
echo "Stopping Docker services..."
echo "=========================================="
docker compose down

# Exit with pytest exit code
if [ $pytest_exit_code -ne 0 ]; then
    echo ""
    echo "=========================================="
    echo "Tests failed with exit code: $pytest_exit_code"
    echo "=========================================="
    exit $pytest_exit_code
fi

echo ""
echo "=========================================="
echo "All checks passed!"
echo "=========================================="

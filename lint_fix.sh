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
uv run ruff check --fix .

echo ""
echo "=========================================="
echo "Running ruff format check..."
echo "=========================================="
uv run ruff format .

echo ""
echo "=========================================="
echo "Running black check..."
echo "=========================================="
uv run black .

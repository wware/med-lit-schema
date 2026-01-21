#!/bin/bash -xe

echo "=========================================="
echo "Running Linters"
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
uv run pylint *.py tests/*.py

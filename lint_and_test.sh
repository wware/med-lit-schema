#!/bin/bash -xe

export PYTHONFILES=$(git ls-files | grep -E '\.py$')
export PYTHONPATH=$(pwd)

uv run ruff check --fix $PYTHONFILES
uv run black $PYTHONFILES
uv run pylint -E --ignore-imports=yes $PYTHONFILES || true
uv run flake8 $PYTHONFILES
# uv run mypy $PYTHONFILES
if [ -f docker-compose.yml ]; then
    uv run docker compose -f docker-compose.yml up -d postgres
    uv run pytest tests/
    uv run docker compose -f docker-compose.yml down
else
    echo "Warning: docker-compose.yml not found, skipping database tests"
    uv run pytest tests/ --ignore=tests/test_entity_sqlmodel.py
fi

# Developer Guide

This section is for people **contributing** to the codebase - understanding the architecture, running the pipeline, writing tests, or extending functionality.

## Contents

- [Architecture](architecture.md) - Domain/persistence separation, mapper pattern, design rationale
- [Ingestion Pipeline](ingestion.md) - Download, NER, claims, evidence, and graph stages
- [Testing](testing.md) - Test strategy, running tests, writing new tests
- [Docker Setup](docker.md) - Docker Compose for local development

## Key Commands

```bash
# Development
uv sync                    # Install dependencies
uv run pytest              # Run all tests
uv run black . --check     # Check formatting

# Database
docker compose up -d postgres redis
uv run python setup_database.py --database-url postgresql://postgres:postgres@localhost:5432/medlit

# Pipeline
bash ingest/pipeline.sh --storage postgres
```

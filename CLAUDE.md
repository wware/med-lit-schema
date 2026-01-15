# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Medical Knowledge Graph Schema - a Python library for building and querying a medical literature knowledge graph. Extracts entities and relationships from PubMed/PMC papers with full provenance tracking.

## Commands

### Development Setup
```bash
uv sync                    # Install dependencies
uv run pytest              # Run all tests
uv run pytest -x           # Stop on first failure
uv run pytest tests/test_mapper.py  # Run single test file
uv run pytest -k "test_disease"     # Run tests matching pattern
```

### Linting
```bash
uv run black . --check     # Check formatting (line-length 200)
uv run ruff check .        # Lint check
uv run black .             # Auto-format
```

### Database Setup
```bash
docker compose up -d postgres redis  # Start PostgreSQL + Redis
uv run python setup_database.py --database-url postgresql://postgres:postgres@localhost:5432/medlit
```

### API Server
```bash
docker compose up api                    # Run API server via Docker
uv run uvicorn query.server:app --port 8000  # Run API directly
```
API docs at `http://localhost:8000/docs`, GraphQL at `/graphiql`

### Ingestion Pipeline
```bash
# Full pipeline with Docker Compose
bash ingest/pipeline.sh --storage postgres

# Individual stages
uv run python ingest/download_pipeline.py --search "BRCA1" --output-dir ingest/pmc_xmls
uv run python ingest/provenance_pipeline.py --input-dir ingest/pmc_xmls --output-dir output --storage sqlite
uv run python ingest/ner_pipeline.py --xml-dir ingest/pmc_xmls --output-dir output --storage sqlite  # Uses biobert-fast with 4 workers by default
uv run python ingest/ner_pipeline.py --xml-dir ingest/pmc_xmls --output-dir output --ner-backend ollama --ollama-host http://localhost:11434  # LLM-based
uv run python ingest/ner_pipeline.py --xml-dir ingest/pmc_xmls --output-dir output --workers 1  # Single-threaded for debugging
uv run python ingest/claims_pipeline.py --output-dir output --storage sqlite
uv run python ingest/evidence_pipeline.py --output-dir output --storage sqlite
uv run python ingest/graph_pipeline.py --output-dir output --storage sqlite
```

## Architecture

### Domain/Persistence Separation

The codebase separates domain logic from database concerns:

1. **Domain Models** (`entity.py`, `relationship.py`, `base.py`) - Pure Pydantic models with rich inheritance (Disease, Gene, Drug inherit from BaseMedicalEntity). Use for business logic, API responses, and ingestion.

2. **Persistence Models** (`storage/models/`) - SQLModel classes using single-table inheritance. All entity types in one `Entity` table with type discriminator. JSON serialization for arrays/embeddings.

3. **Mapper** (`mapper.py`) - Converts between domain and persistence models via `to_persistence()` and `to_domain()`.

### Key Directories

- **Root Python files**: Core domain models and mapper
- **`storage/`**: Storage interfaces and backend implementations (SQLite, PostgreSQL)
- **`ingest/`**: Pipeline stages for processing PMC papers (download → NER → claims → evidence → graph)
- **`query/`**: FastAPI server with REST, GraphQL, and MCP endpoints; Python query client
- **`tests/`**: Pytest test suite

### Storage Backends

- **SQLite** (`storage/backends/sqlite.py`): Development/testing. Optional sqlite-vec for vectors.
- **PostgreSQL** (`storage/backends/postgres.py`): Production. Uses pgvector for embedding search.

Both implement `PipelineStorageInterface` from `storage/interfaces.py`.

### Entity Resolution

All entities use canonical IDs from medical ontologies (UMLS, HGNC, RxNorm, UniProt) to unify mentions across papers. The `InMemoryEntityCollection` (aliased as `EntityCollection`) maintains the authoritative entity registry.

## Code Conventions

- Always use `uv run python` instead of `python` directly
- Always use `uv add <package>` instead of `pip install`
- Use descriptive variable and class names
- Pydantic fields should have meaningful `description` strings
- Prefer immutable data (tuple, frozenset, frozen Pydantic models)
- Line length: 200 characters (configured in pyproject.toml)
- Docstrings: Use Markdown-friendly format with blank lines between sections

## Key Design Principles

1. **Provenance First**: All relationships MUST include evidence with paper_id, section_type, paragraph_idx, study_type
2. **Evidence Quality Weighting**: Confidence scores auto-calculated from study type (RCT=1.0, meta_analysis=0.95, etc.)
3. **Standards-Based IDs**: UMLS for diseases, HGNC for genes, RxNorm for drugs, UniProt for proteins
4. **Pydantic Validation**: Runtime validation prevents invalid medical data from entering the system

# Storage Layer

The storage layer provides a clean abstraction for data persistence in the medical literature knowledge graph, separating infrastructure concerns (database operations) from domain logic (ingest processing).

## Architecture

The storage layer is organized into three main components:

```
storage/
├── interfaces.py           # Abstract base classes defining storage contracts
├── backends/              # Concrete backend implementations
│   ├── sqlite.py          # SQLite implementation for development/testing
│   ├── postgres.py        # PostgreSQL+pgvector for production
│   └── sqlite_entity_collection.py  # Entity collection with vector search
└── models/                # SQLModel persistence schemas
    ├── entity.py          # Entity table with polymorphic types
    ├── relationship.py    # Relationship table
    ├── paper.py           # Paper metadata
    └── evidence.py        # Evidence items
```

## Key Concepts

### Storage Abstraction

The storage layer uses abstract interfaces (`PipelineStorageInterface`, `PaperStorageInterface`, etc.) that allow the ingest process to work with different storage backends without code changes. This enables:

- **Development flexibility**: Use SQLite for local development and testing
- **Production scalability**: Switch to PostgreSQL+pgvector for production
- **Easy testing**: Mock storage backends for unit tests
- **Future extensibility**: Add new backends (Neo4j, MongoDB, etc.) without changing ingest code

### Domain vs Persistence Models

- **Domain Models** (`entity.py`, `relationship.py`): Rich Pydantic models used in application logic
- **Persistence Models** (`storage/models/`): Flattened SQLModel schemas optimized for database storage
- **Mappers** (`mapper.py`): Bidirectional conversion between domain and persistence models

This separation keeps domain logic clean while optimizing database performance.

## Quick Start

### SQLite (Development/Testing)

```python
from med_lit_schema.storage.backends.sqlite import SQLitePipelineStorage
from med_lit_schema.entity import Disease, EntityType

# Create in-memory database
storage = SQLitePipelineStorage(":memory:")

# Or use a file
storage = SQLitePipelineStorage("my_database.db")

# Add entities
disease = Disease(
    entity_id="C0006142",
    entity_type=EntityType.DISEASE,
    name="Breast Cancer",
    synonyms=["Breast Carcinoma"],
    source="umls"
)
storage.entities.add_disease(disease)

# Retrieve entities
retrieved = storage.entities.get_by_id("C0006142")
print(f"Found: {retrieved.name}")

# Add papers and relationships
storage.add_paper(paper)
storage.add_relationship(relationship)

# Don't forget to close
storage.close()
```

### PostgreSQL (Production)

```python
from med_lit_schema.storage.backends.postgres import PostgresPipelineStorage

# Connect to PostgreSQL
storage = PostgresPipelineStorage(
    "postgresql://user:password@localhost:5432/medlit"
)

# Same API as SQLite
storage.entities.add_disease(disease)
retrieved = storage.entities.get_by_id("C0006142")

storage.close()
```

## When to Use Which Backend

### SQLite
**Use for:**
- Local development
- Testing and CI/CD
- Small datasets (< 100k entities)
- Single-user applications
- Prototyping

**Advantages:**
- No setup required
- Fast for small datasets
- Portable (single file)
- Great for testing

**Limitations:**
- Limited vector search support
- Single-writer constraints
- No advanced PostgreSQL features

### PostgreSQL
**Use for:**
- Production deployments
- Large datasets (> 100k entities)
- Multi-user applications
- When you need pgvector for semantic search
- When you need concurrent writes

**Advantages:**
- Excellent performance at scale
- pgvector extension for semantic search
- Concurrent read/write support
- Advanced indexing and query optimization
- JSONB support for flexible schemas

**Setup Required:**
- PostgreSQL 12+ installation
- pgvector extension
- See [DATABASE_SETUP.md](../DATABASE_SETUP.md) for details

## Import Examples

```python
# Interfaces
from med_lit_schema.storage.interfaces import (
    PipelineStorageInterface,
    PaperStorageInterface,
    RelationshipStorageInterface,
    EvidenceStorageInterface
)

# Backends
from med_lit_schema.storage.backends.sqlite import SQLitePipelineStorage
from med_lit_schema.storage.backends.postgres import PostgresPipelineStorage

# Models (typically used via mapper.py)
from med_lit_schema.storage.models.entity import Entity, EntityType
from med_lit_schema.storage.models.relationship import Relationship
```

## Directory Structure

- **`interfaces.py`**: Abstract base classes defining the storage contract
- **`backends/`**: Concrete implementations for different databases
  - See [backends/README.md](backends/README.md) for backend comparison
- **`models/`**: SQLModel schemas for database persistence
  - See [models/README.md](models/README.md) for schema documentation
- **`NEO4J_COMPATIBILITY.md`**: Guide for Neo4j integration (future)

## Testing

Storage layer tests are organized in `tests/storage/`:

```bash
# Run all storage tests
pytest tests/storage/ -v

# Test specific backend
pytest tests/storage/backends/test_sqlite.py -v

# Test models
pytest tests/storage/models/test_entity.py -v
```

See [tests/storage/README.md](../tests/storage/README.md) for more details.

## Further Reading

- [Storage Backends Comparison](backends/README.md)
- [Database Schema Documentation](models/README.md)
- [Neo4j Compatibility Guide](NEO4J_COMPATIBILITY.md)
- [Database Setup Guide](../DATABASE_SETUP.md)
- [Testing Guide](../tests/storage/README.md)

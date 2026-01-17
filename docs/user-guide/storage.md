# Storage Options

The knowledge graph supports multiple storage backends through a pluggable architecture.

## Overview

| Backend | Use Case | Vector Search | Notes |
|---------|----------|---------------|-------|
| SQLite | Development, testing | sqlite-vec (optional) | Lightweight, single file |
| PostgreSQL | Production | pgvector | Full-featured, scalable |

Both backends implement `PipelineStorageInterface` from `storage/interfaces.py`.

## SQLite (Development)

Best for local development and testing.

### Setup

```python
from med_lit_schema.storage.backends.sqlite import SQLitePipelineStorage

# File-based
storage = SQLitePipelineStorage("my_database.db")

# In-memory (for tests)
storage = SQLitePipelineStorage(":memory:")
```

### Command Line

```bash
# Run ingest with SQLite
uv run python ingest/ner_pipeline.py \
    --xml-dir ingest/pmc_xmls \
    --storage sqlite \
    --output-dir output
```

### Vector Search (Optional)

SQLite supports vector search via sqlite-vec extension:

```bash
# Install sqlite-vec
uv add sqlite-vec
```

## PostgreSQL (Production)

Recommended for production deployments with pgvector for embedding search.

### Setup

**1. Start PostgreSQL:**

```bash
docker compose up -d postgres
```

**2. Initialize the database:**

```bash
export DB_URL="postgresql://postgres:postgres@localhost:5432/medlit"
uv run python setup_database.py --database-url $DB_URL
```

**3. Connect from Python:**

```python
from med_lit_schema.storage.backends.postgres import PostgresPipelineStorage

storage = PostgresPipelineStorage(
    "postgresql://postgres:postgres@localhost:5432/medlit"
)
```

### Command Line

```bash
export DB_URL="postgresql://postgres:postgres@localhost:5432/medlit"

uv run python ingest/ner_pipeline.py \
    --xml-dir ingest/pmc_xmls \
    --storage postgres \
    --database-url $DB_URL \
    --output-dir output
```

### Database Reset

To start fresh:

```bash
# Drop and recreate
dropdb medlit
createdb medlit

# Re-initialize schema
uv run python setup_database.py --database-url $DB_URL
```

## Storage Interface

Both backends implement the same interface:

```python
class PipelineStorageInterface(ABC):
    @property
    @abstractmethod
    def entities(self) -> EntityStorageInterface:
        """Access entity storage."""
        pass

    @abstractmethod
    def add_paper(self, paper: Paper) -> None:
        """Store a paper."""
        pass

    @abstractmethod
    def add_relationship(self, relationship: BaseMedicalRelationship) -> None:
        """Store a relationship."""
        pass

    @abstractmethod
    def get_relationships_by_predicate(
        self, predicate: str, limit: int = 100
    ) -> list[BaseMedicalRelationship]:
        """Query relationships by predicate type."""
        pass
```

### Custom Backends

You can implement your own storage backend by implementing `PipelineStorageInterface`:

```python
from med_lit_schema.storage.interfaces import PipelineStorageInterface

class MyCustomStorage(PipelineStorageInterface):
    def __init__(self, connection_string: str):
        # Your initialization
        pass

    # Implement all abstract methods...
```

## Docker Compose Configuration

The `docker-compose.yml` includes PostgreSQL with pgvector:

```yaml
services:
  postgres:
    image: pgvector/pgvector:pg16
    environment:
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: postgres
      POSTGRES_DB: medlit
    ports:
      - "5432:5432"
    volumes:
      - postgres_data:/var/lib/postgresql/data
```

Start with:

```bash
docker compose up -d postgres
```

## Schema Details

### Entities Table (Single-Table Inheritance)

All entity types stored in one table with type discriminator:

```sql
CREATE TABLE entities (
    id TEXT PRIMARY KEY,
    entity_type TEXT NOT NULL,  -- discriminator
    name TEXT NOT NULL,
    synonyms JSONB,
    embedding vector(384),
    -- Type-specific fields (nullable)
    umls_id TEXT,    -- Disease
    hgnc_id TEXT,    -- Gene
    rxnorm_id TEXT,  -- Drug
    ...
);
```

### Relationships Table

```sql
CREATE TABLE relationships (
    id SERIAL PRIMARY KEY,
    subject_id TEXT NOT NULL,
    predicate TEXT NOT NULL,
    object_id TEXT NOT NULL,
    confidence FLOAT,
    source_papers JSONB,
    evidence JSONB,
    embedding vector(384)
);
```

## Next Steps

- [Architecture](../developer-guide/architecture.md) - Domain/persistence separation
- [Ingestion Pipeline](../developer-guide/ingestion.md) - Populate the database

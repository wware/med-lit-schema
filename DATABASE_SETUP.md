# Database Setup

This project uses SQLModel to define database schemas, which automatically generate PostgreSQL tables.

## Quick Start

```bash
# Set up database with all features
python setup_database.py --database-url postgresql://user:pass@localhost:5432/medgraph

# Or skip vector index creation (faster for development)
python setup_database.py --database-url postgresql://user:pass@localhost:5432/medgraph --skip-vector-index
```

## What Gets Created

### 1. **PostgreSQL Extensions**
- `uuid-ossp` - UUID generation for relationships and evidence
- `vector` - pgvector extension for semantic similarity search

### 2. **Tables** (from SQLModel definitions)
- `entities` - All medical entities (diseases, genes, drugs, etc.)
- `relationships` - Connections between entities (TREATS, CAUSES, etc.)
- `evidence` - Paper citations supporting relationships
- `papers` - Source documents

### 3. **Database Features**

#### Indexes
- Standard B-tree indexes on foreign keys and commonly queried columns
- **HNSW vector index** on `entities.embedding` for fast cosine similarity search

#### Constraints
- **Foreign keys with CASCADE delete** - Deleting an entity removes its relationships
- **UNIQUE constraint** on `(subject_id, object_id, predicate)` - Prevents duplicate triples

#### Triggers
- **Auto-updating timestamps** - `updated_at` columns automatically update on row modification

## Migration from `migration.sql`

The old `migration.sql` file is **now redundant**. All schema definitions live in:
- `entity_sqlmodel.py`
- `relationship_sqlmodel.py`
- `evidence_sqlmodel.py`
- `paper_sqlmodel.py`

### Key Differences

| Feature | Old (migration.sql) | New (SQLModel) |
|---------|---------------------|----------------|
| Schema definition | Hand-written SQL DDL | Python SQLModel classes |
| Foreign keys | ✅ | ✅ |
| CASCADE delete | ✅ | ✅ |
| Vector index | ✅ | ✅ (via setup script) |
| Triggers | ✅ | ✅ (via setup script) |
| JSONB properties | ❌ | ✅ |
| Type safety | ❌ | ✅ |
| Single source of truth | ❌ | ✅ |

## Advanced Usage

### Custom Setup

```python
from sqlalchemy import create_engine
from sqlmodel import SQLModel
from setup_database import create_extensions, create_triggers, create_vector_index

engine = create_engine("postgresql://user:pass@localhost/mydb")

# Minimal setup (tables only)
SQLModel.metadata.create_all(engine)

# Full setup (extensions, triggers, indexes)
create_extensions(engine)
SQLModel.metadata.create_all(engine)
create_triggers(engine)
create_vector_index(engine)
```

### Vector Index Considerations

The HNSW index creation can be slow on large tables. Options:

1. **Skip during development**: Use `--skip-vector-index` flag
2. **Create later**: Populate data first, then run:
   ```sql
   CREATE INDEX idx_entities_embedding ON entities
   USING hnsw (embedding vector_cosine_ops);
   ```
3. **Tune HNSW parameters**: Adjust `m` and `ef_construction` for speed/accuracy tradeoff

## Testing

```bash
# Run database tests (requires docker-compose)
./check.sh
```

The test suite uses the setup script to create a fresh test database for each run.

## Embedding Dimension

The default setup assumes 768-dimensional embeddings (e.g., PubMedBERT). If using different models:

- **OpenAI embeddings (1536-dim)**: Change `vector(768)` to `vector(1536)` in `setup_database.py`
- **sentence-transformers (384-dim)**: Change to `vector(384)`

You can also store embeddings as TEXT initially and convert to vector type later once you've decided on an embedding model.

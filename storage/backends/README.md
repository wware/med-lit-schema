# Storage Backends

This directory contains concrete implementations of the storage interfaces for different database backends.

## Available Backends

### SQLite (`sqlite.py`)

SQLite implementation for development, testing, and small-scale deployments.

**Features:**
- In-memory or file-based storage
- No external dependencies
- Fast for small datasets
- JSON-based entity storage
- Basic vector search (via sqlite-vec extension if available)

**Use Cases:**
- Local development
- Automated testing
- CI/CD ingests
- Small projects (< 100k entities)
- Prototyping

**Connection Examples:**
```python
from med_lit_schema.storage.backends.sqlite import SQLitePipelineStorage

# In-memory database (data lost on close)
storage = SQLitePipelineStorage(":memory:")

# Persistent file database
storage = SQLitePipelineStorage("data/knowledge_graph.db")

# Relative path
storage = SQLitePipelineStorage("./output/my_db.db")
```

### PostgreSQL (`postgres.py`)

PostgreSQL+pgvector implementation for production deployments.

**Features:**
- Full ACID compliance
- Concurrent read/write operations
- pgvector extension for efficient semantic search
- JSONB support for flexible schemas
- Advanced indexing (HNSW, IVFFlat)
- Optimized for large datasets

**Use Cases:**
- Production deployments
- Large datasets (> 100k entities)
- Multi-user applications
- Applications requiring semantic search
- When you need robust concurrent access

**Connection Examples:**
```python
from med_lit_schema.storage.backends.postgres import PostgresPipelineStorage

# Basic connection
storage = PostgresPipelineStorage(
    "postgresql://user:password@localhost:5432/medlit"
)

# With connection pooling
storage = PostgresPipelineStorage(
    "postgresql://user:password@localhost:5432/medlit",
    pool_size=10,
    max_overflow=20
)

# Environment variable
import os
storage = PostgresPipelineStorage(os.environ["DATABASE_URL"])
```

### SQLite Entity Collection (`sqlite_entity_collection.py`)

Specialized entity collection using SQLite with optional vector search support.

**Features:**
- Implements `EntityCollectionInterface`
- JSON-based entity storage
- Optional sqlite-vec integration for embedding search
- Fallback to Python-based cosine similarity if sqlite-vec unavailable

**Use Cases:**
- When you need entity collection interface with SQLite
- Prototyping entity search functionality
- Testing entity resolution logic

## Performance Characteristics

| Feature | SQLite | PostgreSQL |
|---------|--------|------------|
| Setup | None | Moderate |
| Small datasets (< 10k) | Excellent | Good |
| Medium datasets (10k-100k) | Good | Excellent |
| Large datasets (> 100k) | Poor | Excellent |
| Concurrent writes | Poor | Excellent |
| Concurrent reads | Good | Excellent |
| Vector search | Basic | Excellent (pgvector) |
| Semantic search | Limited | Excellent |
| Memory usage | Low | Moderate |
| Disk usage | Low | Moderate |

## Configuration Examples

### SQLite Best Practices

```python
from med_lit_schema.storage.backends.sqlite import SQLitePipelineStorage
from pathlib import Path

# Ensure directory exists
db_path = Path("data/knowledge_graph.db")
db_path.parent.mkdir(parents=True, exist_ok=True)

# Create storage
storage = SQLitePipelineStorage(str(db_path))

# Enable WAL mode for better concurrent access
storage.conn.execute("PRAGMA journal_mode=WAL")

# Optimize for performance
storage.conn.execute("PRAGMA synchronous=NORMAL")
storage.conn.execute("PRAGMA cache_size=-64000")  # 64MB cache

# Use the storage
# ...

# Always close when done
storage.close()
```

### PostgreSQL Best Practices

```python
from med_lit_schema.storage.backends.postgres import PostgresPipelineStorage
import os

# Use environment variables for security
DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql://medlit:password@localhost:5432/medlit"
)

# Production configuration
storage = PostgresPipelineStorage(
    DATABASE_URL,
    pool_size=20,           # Connection pool size
    max_overflow=40,        # Max connections beyond pool_size
    pool_timeout=30,        # Timeout for getting connection
    pool_recycle=3600,      # Recycle connections after 1 hour
)

# For Django/async environments, you might want:
# - pool_pre_ping=True (test connections before using)
# - echo=False (disable SQL logging in production)
```

## Implementing a New Backend

To add a new storage backend (e.g., Neo4j, MongoDB):

1. **Implement the interfaces** in `storage/interfaces.py`:
   - `PaperStorageInterface`
   - `RelationshipStorageInterface`
   - `EvidenceStorageInterface`
   - `PipelineStorageInterface`

2. **Create a new file** (e.g., `storage/backends/neo4j.py`):

```python
from med_lit_schema.storage.interfaces import (
    PipelineStorageInterface,
    PaperStorageInterface,
    # ... other interfaces
)

class Neo4jPaperStorage(PaperStorageInterface):
    def __init__(self, driver):
        self.driver = driver
    
    def add_paper(self, paper: Paper) -> None:
        # Your implementation
        pass
    
    # ... implement all abstract methods

class Neo4jPipelineStorage(PipelineStorageInterface):
    def __init__(self, uri: str, username: str, password: str):
        from neo4j import GraphDatabase
        self.driver = GraphDatabase.driver(uri, auth=(username, password))
        self._papers = Neo4jPaperStorage(self.driver)
        # ... initialize other components
    
    @property
    def entities(self) -> EntityCollectionInterface:
        return self._entities
    
    # ... implement all abstract methods
```

3. **Add tests** in `tests/storage/backends/test_neo4j.py`

4. **Update documentation** in this README

5. **Add example** in `storage/README.md`

## Connection String Formats

### SQLite
```
:memory:                    # In-memory database
relative/path/db.sqlite     # Relative path
/absolute/path/db.sqlite    # Absolute path
```

### PostgreSQL
```
postgresql://[user[:password]@][host][:port][/dbname][?param1=value1&...]

Examples:
postgresql://localhost/medlit
postgresql://user:pass@localhost:5432/medlit
postgresql://user:pass@db.example.com:5432/medlit?sslmode=require
```

### Environment Variables
```bash
# SQLite
export SQLITE_DB_PATH="data/knowledge_graph.db"

# PostgreSQL
export DATABASE_URL="postgresql://user:pass@localhost:5432/medlit"
export POSTGRES_HOST="localhost"
export POSTGRES_PORT="5432"
export POSTGRES_DB="medlit"
export POSTGRES_USER="user"
export POSTGRES_PASSWORD="password"
```

## Troubleshooting

### SQLite Issues

**"Database is locked" error:**
- Enable WAL mode: `PRAGMA journal_mode=WAL`
- Ensure you're closing connections properly
- Consider PostgreSQL for concurrent access

**Slow performance:**
- Add appropriate indexes
- Use transactions for bulk inserts
- Increase cache size: `PRAGMA cache_size=-64000`

**sqlite-vec not found:**
- Vector search falls back to Python implementation
- Install from: https://github.com/asg017/sqlite-vec
- Not critical for basic functionality

### PostgreSQL Issues

**Connection refused:**
- Check PostgreSQL is running: `systemctl status postgresql`
- Verify connection parameters
- Check firewall settings

**"Extension pgvector not found":**
- Install pgvector: `sudo apt install postgresql-pgvector`
- Or compile from source: https://github.com/pgvector/pgvector
- Enable: `CREATE EXTENSION vector;`

**Slow queries:**
- Add indexes on frequently queried columns
- Use `EXPLAIN ANALYZE` to debug queries
- Consider HNSW indexes for vector search
- Adjust `shared_buffers` and other PostgreSQL settings

## Further Reading

- [Storage Layer Overview](../README.md)
- [Database Schema Documentation](../models/README.md)
- [Database Setup Guide](../../DATABASE_SETUP.md)
- [Neo4j Compatibility](../NEO4J_COMPATIBILITY.md)

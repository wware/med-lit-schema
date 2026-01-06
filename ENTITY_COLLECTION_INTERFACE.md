# EntityCollection Interface Pattern

This document explains the EntityCollection interface pattern and how to implement custom storage backends.

## Overview

The `EntityCollection` has been refactored to use an interface pattern that enables pluggable storage backends. This allows applications to use in-memory storage for testing/development and database backends for production.

## Available Implementations

### InMemoryEntityCollection (Default)

The built-in implementation using Python dictionaries:

```python
from schema.entity import InMemoryEntityCollection, Disease

# Create an in-memory collection
collection = InMemoryEntityCollection()

# Add entities
disease = Disease(
    entity_id="C0006142",
    name="Breast Cancer",
    entity_type="disease"
)
collection.add_disease(disease)

# Retrieve entities
retrieved = collection.get_by_id("C0006142")
print(f"Found: {retrieved.name}")

# Count entities
print(f"Total entities: {collection.entity_count}")

# Save to JSONL file
collection.save("entities.jsonl")

# Load from JSONL file
loaded = InMemoryEntityCollection.load("entities.jsonl")
```

**Best for:**
- Testing
- Development environments
- Small datasets (< 100k entities)
- Prototyping

## Backward Compatibility

The `EntityCollection` name is now an alias for `InMemoryEntityCollection`. All existing code continues to work:

```python
from schema.entity import EntityCollection  # Still works!

collection = EntityCollection()  # Creates InMemoryEntityCollection
```

## Custom Implementations

To create a custom storage backend, implement the `EntityCollectionInterface`:

### PostgreSQL Example

```python
from schema.entity import EntityCollectionInterface, Disease, Gene, BaseMedicalEntity
import psycopg2
import json

class PostgresEntityCollection(EntityCollectionInterface):
    """PostgreSQL-backed entity collection for production use."""
    
    def __init__(self, connection_string: str):
        self.conn = psycopg2.connect(connection_string)
        self._create_tables()
    
    def _create_tables(self):
        """Create entities table if it doesn't exist."""
        with self.conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS entities (
                    id VARCHAR(255) PRIMARY KEY,
                    entity_type VARCHAR(50) NOT NULL,
                    name TEXT NOT NULL,
                    properties JSONB NOT NULL,
                    embedding vector(768),  -- for pgvector support
                    created_at TIMESTAMP DEFAULT NOW()
                )
            """)
            cur.execute("""
                CREATE INDEX IF NOT EXISTS idx_entity_type 
                ON entities(entity_type)
            """)
        self.conn.commit()
    
    def add_disease(self, entity: Disease) -> None:
        with self.conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO entities (id, entity_type, name, properties)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (id) DO UPDATE 
                SET name = EXCLUDED.name, properties = EXCLUDED.properties
                """,
                (entity.entity_id, "disease", entity.name, 
                 json.dumps(entity.model_dump()))
            )
        self.conn.commit()
    
    def add_gene(self, entity: Gene) -> None:
        with self.conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO entities (id, entity_type, name, properties)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (id) DO UPDATE 
                SET name = EXCLUDED.name, properties = EXCLUDED.properties
                """,
                (entity.entity_id, "gene", entity.name, 
                 json.dumps(entity.model_dump()))
            )
        self.conn.commit()
    
    # ... implement other add_* methods similarly ...
    
    def get_by_id(self, entity_id: str) -> BaseMedicalEntity | None:
        with self.conn.cursor() as cur:
            cur.execute(
                "SELECT properties FROM entities WHERE id = %s",
                (entity_id,)
            )
            row = cur.fetchone()
            if row:
                data = json.loads(row[0])
                entity_type = data.get('entity_type')
                
                # Reconstruct the appropriate entity type
                if entity_type == 'disease':
                    return Disease.model_validate(data)
                elif entity_type == 'gene':
                    return Gene.model_validate(data)
                # ... handle other types ...
        return None
    
    def get_by_umls(self, umls_id: str) -> Disease | None:
        with self.conn.cursor() as cur:
            cur.execute(
                """
                SELECT properties FROM entities 
                WHERE entity_type = 'disease' 
                AND properties->>'umls_id' = %s
                """,
                (umls_id,)
            )
            row = cur.fetchone()
            if row:
                return Disease.model_validate(json.loads(row[0]))
        return None
    
    def get_by_hgnc(self, hgnc_id: str) -> Gene | None:
        with self.conn.cursor() as cur:
            cur.execute(
                """
                SELECT properties FROM entities 
                WHERE entity_type = 'gene' 
                AND properties->>'hgnc_id' = %s
                """,
                (hgnc_id,)
            )
            row = cur.fetchone()
            if row:
                return Gene.model_validate(json.loads(row[0]))
        return None
    
    def find_by_embedding(
        self, 
        query_embedding: list[float], 
        top_k: int = 5,
        threshold: float = 0.85
    ) -> list[tuple[BaseMedicalEntity, float]]:
        """Find similar entities using pgvector cosine similarity."""
        # Requires pgvector extension
        with self.conn.cursor() as cur:
            cur.execute(
                """
                SELECT properties, 
                       1 - (embedding <=> %s::vector) as similarity
                FROM entities
                WHERE embedding IS NOT NULL
                  AND 1 - (embedding <=> %s::vector) >= %s
                ORDER BY similarity DESC
                LIMIT %s
                """,
                (query_embedding, query_embedding, threshold, top_k)
            )
            results = []
            for row in cur.fetchall():
                data = json.loads(row[0])
                entity_type = data.get('entity_type')
                
                # Reconstruct entity
                if entity_type == 'disease':
                    entity = Disease.model_validate(data)
                elif entity_type == 'gene':
                    entity = Gene.model_validate(data)
                # ... handle other types ...
                
                results.append((entity, row[1]))
            
            return results
    
    @property
    def entity_count(self) -> int:
        with self.conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM entities")
            return cur.fetchone()[0]
```

### Redis Example

```python
import redis
import json

class RedisEntityCollection(EntityCollectionInterface):
    """Redis-backed entity collection for fast caching."""
    
    def __init__(self, redis_client: redis.Redis):
        self.redis = redis_client
    
    def add_disease(self, entity: Disease) -> None:
        key = f"entity:{entity.entity_id}"
        value = entity.model_dump_json()
        
        # Store entity
        self.redis.set(key, value)
        
        # Add to type-specific index
        self.redis.sadd("entities:disease", entity.entity_id)
        
        # Add to global entity set
        self.redis.sadd("entities:all", entity.entity_id)
    
    def get_by_id(self, entity_id: str) -> BaseMedicalEntity | None:
        key = f"entity:{entity_id}"
        data = self.redis.get(key)
        
        if data:
            obj = json.loads(data)
            entity_type = obj.get('entity_type')
            
            if entity_type == 'disease':
                return Disease.model_validate(obj)
            elif entity_type == 'gene':
                return Gene.model_validate(obj)
            # ... handle other types ...
        
        return None
    
    @property
    def entity_count(self) -> int:
        return self.redis.scard("entities:all")
```

## Usage with Dependency Injection

The interface pattern enables clean dependency injection:

```python
from schema.entity import EntityCollectionInterface

def extract_entities_from_paper(
    paper_text: str,
    collection: EntityCollectionInterface
) -> None:
    """
    Extract entities from paper text and store them.
    
    This function doesn't need to know which storage backend is used.
    """
    # Extract disease entities
    disease = Disease(
        entity_id="C0001",
        name="Extracted Disease",
        entity_type="disease"
    )
    collection.add_disease(disease)
    
    # Extract gene entities
    gene = Gene(
        entity_id="G0001",
        name="Extracted Gene",
        entity_type="gene"
    )
    collection.add_gene(gene)

# Development/Testing
from schema.entity import InMemoryEntityCollection
dev_collection = InMemoryEntityCollection()
extract_entities_from_paper("paper text...", dev_collection)

# Production with PostgreSQL
postgres_collection = PostgresEntityCollection(
    "postgresql://user:pass@localhost/medgraph"
)
extract_entities_from_paper("paper text...", postgres_collection)

# Production with Redis
import redis
r = redis.Redis(host='localhost', port=6379, db=0)
redis_collection = RedisEntityCollection(r)
extract_entities_from_paper("paper text...", redis_collection)
```

## Migration Guide

### For Existing Code

No changes required! The `EntityCollection` alias ensures backward compatibility:

```python
# Old code - still works
from schema.entity import EntityCollection
collection = EntityCollection()
```

### For New Code

Use the explicit implementation name:

```python
# New code - be explicit
from schema.entity import InMemoryEntityCollection
collection = InMemoryEntityCollection()
```

Or use the interface for type hints:

```python
from schema.entity import EntityCollectionInterface, InMemoryEntityCollection

def process_entities(collection: EntityCollectionInterface):
    """Accepts any storage backend implementation."""
    pass

# Works with any implementation
process_entities(InMemoryEntityCollection())
```

## When to Use Each Implementation

### InMemoryEntityCollection
- ✅ Unit tests
- ✅ Integration tests
- ✅ Development environments
- ✅ Small datasets (< 100k entities)
- ✅ Quick prototyping
- ❌ Production with large datasets
- ❌ Multi-instance deployments

### PostgresEntityCollection
- ✅ Production deployments
- ✅ Large datasets (millions of entities)
- ✅ Complex queries and joins
- ✅ ACID transactions
- ✅ Relational data requirements
- ❌ High-throughput read operations
- ❌ Simple key-value lookups

### RedisEntityCollection
- ✅ High-throughput reads
- ✅ Caching layer
- ✅ Fast key-value lookups
- ✅ Session storage
- ✅ Real-time applications
- ❌ Complex queries
- ❌ Large entities (> 1MB)
- ❌ Long-term persistence

## Testing Custom Implementations

When creating a custom implementation, ensure it passes these basic tests:

```python
def test_custom_implementation(your_collection: EntityCollectionInterface):
    """Generic test suite for any EntityCollectionInterface implementation."""
    
    # Test adding entities
    disease = Disease(entity_id="TEST001", name="Test", entity_type="disease")
    your_collection.add_disease(disease)
    
    # Test retrieval
    retrieved = your_collection.get_by_id("TEST001")
    assert retrieved is not None
    assert retrieved.name == "Test"
    
    # Test count
    assert your_collection.entity_count > 0
    
    # Test adding more entity types
    gene = Gene(entity_id="TEST002", name="Gene", entity_type="gene")
    your_collection.add_gene(gene)
    assert your_collection.entity_count == 2
```

## Benefits

1. **Flexibility**: Choose the storage backend that fits your needs
2. **Testability**: Use in-memory for fast tests, database for integration tests
3. **Scalability**: Switch to database-backed storage as data grows
4. **Maintainability**: Clear separation between domain logic and storage
5. **SOLID Principles**: Follows Dependency Inversion Principle

## See Also

- API Reference: `schema.entity.EntityCollectionInterface`
- Implementation: `schema.entity.InMemoryEntityCollection`
- Tests: `tests/test_entity_collection_interface.py`

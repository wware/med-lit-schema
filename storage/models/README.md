# Storage Models (SQLModel Schemas)

This directory contains SQLModel persistence schemas that define the database structure for storing medical literature knowledge graphs.

## Overview

These are **Persistence Models** - flattened database representations optimized for storage and querying. They differ from **Domain Models** (in `entity.py`, `relationship.py`) which are rich Pydantic models used in application logic.

**Key Principle:** Domain models are for application logic, persistence models are for database storage. The `mapper.py` module handles bidirectional conversion.

## Available Models

### Entity (`entity.py`)

Single table with polymorphic inheritance for all entity types.

**Design:**
- One table for all entity types (Disease, Gene, Drug, Protein, etc.)
- Polymorphic discriminator column (`entity_type`)
- All entity-specific fields in one table (nullable)
- No JOINs needed for queries
- JSONB properties for flexible attributes
- Optional pgvector support for semantic search

**Key Fields:**
```python
entity_id: str              # Primary key (e.g., "C0006142", "HGNC:1100")
entity_type: EntityType     # Discriminator (disease, gene, drug, etc.)
name: str                   # Entity name
synonyms: JSON              # Alternative names
embedding: Optional[bytes]  # Vector embedding for semantic search
properties: Optional[JSON]  # Flexible JSONB properties
created_at: datetime        # Auto-managed timestamp
updated_at: datetime        # Auto-updated timestamp
```

**Indexes:**
- Primary key on `entity_id`
- Index on `entity_type` for filtering
- HNSW index on `embedding` for vector search (PostgreSQL only)

**Example:**
```python
from med_lit_schema.storage.models.entity import Entity, EntityType

entity = Entity(
    entity_id="C0006142",
    entity_type=EntityType.DISEASE,
    name="Breast Cancer",
    synonyms=["Breast Carcinoma", "Mammary Carcinoma"],
    umls_id="C0006142",
    properties={"prevalence": "common", "severity": "high"}
)
```

### Relationship (`relationship.py`)

Table for storing relationships between entities.

**Design:**
- Subject-Predicate-Object triple structure
- Confidence scores and evidence tracking
- Support for relationship-specific properties
- Timestamps for tracking changes

**Key Fields:**
```python
relationship_id: str        # UUID primary key
subject_id: str            # Foreign key to entities
object_id: str             # Foreign key to entities
predicate: str             # Relationship type (treats, causes, etc.)
confidence: Optional[float] # Confidence score (0.0 - 1.0)
source_papers: JSON        # Paper IDs supporting this relationship
properties: Optional[JSON]  # Relationship-specific attributes
created_at: datetime       # Auto-managed timestamp
updated_at: datetime       # Auto-updated timestamp
```

**Indexes:**
- Primary key on `relationship_id`
- Composite index on `(subject_id, predicate, object_id)` for lookups
- Index on `predicate` for filtering by type

**Example:**
```python
from med_lit_schema.storage.models.relationship import Relationship

relationship = Relationship(
    relationship_id="rel_123",
    subject_id="RxNorm:1187832",  # Olaparib
    object_id="C0006142",         # Breast Cancer
    predicate="treats",
    confidence=0.95,
    source_papers=["PMC123456", "PMC789012"],
    properties={
        "efficacy": "high",
        "response_rate": 0.59
    }
)
```

### Paper (`paper.py`)

Table for storing paper metadata and content.

**Key Fields:**
```python
paper_id: str              # Primary key (e.g., "PMC123456")
title: str                 # Paper title
abstract: Optional[str]    # Abstract text
authors: JSON              # List of author objects
journal: Optional[str]     # Journal name
publication_date: Optional[datetime]
doi: Optional[str]         # Digital Object Identifier
pmid: Optional[str]        # PubMed ID
pmcid: Optional[str]       # PubMed Central ID
properties: Optional[JSON]  # Additional metadata
created_at: datetime       # Auto-managed timestamp
updated_at: datetime       # Auto-updated timestamp
```

**Example:**
```python
from med_lit_schema.storage.models.paper import Paper

paper = Paper(
    paper_id="PMC123456",
    title="Efficacy of Olaparib in BRCA-mutated Breast Cancer",
    abstract="This study examines...",
    authors=[
        {"name": "Smith J", "affiliation": "Harvard Medical School"},
        {"name": "Jones A", "affiliation": "MIT"}
    ],
    journal="Nature Medicine",
    doi="10.1038/nm.1234"
)
```

### Evidence (`evidence.py`)

Table for storing quantitative evidence supporting/refuting relationships.

**Key Fields:**
```python
evidence_id: str           # UUID primary key
relationship_id: str       # Foreign key to relationships
paper_id: str              # Foreign key to papers
evidence_type: str         # Type of evidence (clinical_trial, meta_analysis, etc.)
sample_size: Optional[int] # Study sample size
p_value: Optional[float]   # Statistical significance
effect_size: Optional[float] # Magnitude of effect
confidence: Optional[float] # Evidence confidence (0.0 - 1.0)
properties: Optional[JSON]  # Additional evidence attributes
created_at: datetime       # Auto-managed timestamp
updated_at: datetime       # Auto-updated timestamp
```

**Example:**
```python
from med_lit_schema.storage.models.evidence import Evidence

evidence = Evidence(
    evidence_id="ev_123",
    relationship_id="rel_123",
    paper_id="PMC123456",
    evidence_type="clinical_trial",
    sample_size=302,
    p_value=0.001,
    effect_size=0.59,
    confidence=0.95,
    properties={"phase": 3, "blinded": True}
)
```

## Mapping Domain ↔ Persistence

The `mapper.py` module provides functions for converting between domain and persistence models:

```python
from med_lit_schema.mapper import (
    to_persistence,           # Domain → Persistence
    to_domain,               # Persistence → Domain
    relationship_to_persistence,
    relationship_to_domain,
)

# Domain → Persistence
from med_lit_schema.entity import Disease
domain_disease = Disease(entity_id="C0006142", name="Breast Cancer")
persistence_entity = to_persistence(domain_disease)

# Persistence → Domain
domain_entity = to_domain(persistence_entity)

# Relationships work similarly
from med_lit_schema.relationship import Treats
domain_rel = Treats(subject_id="drug_id", object_id="disease_id", ...)
persistence_rel = relationship_to_persistence(domain_rel)
domain_rel_restored = relationship_to_domain(persistence_rel)
```

## Database Tables

When using PostgreSQL, tables are created with these names:

- `entities` - Entity table
- `relationships` - Relationship table  
- `papers` - Paper metadata table
- `evidences` - Evidence table

**Auto-generated features:**
- `created_at`: Set automatically on insert
- `updated_at`: Updated automatically via trigger (PostgreSQL) or application (SQLite)
- UUIDs: Generated for relationships and evidence if not provided

## Migration Considerations

### Adding New Fields

When adding fields to persistence models:

1. **Add field to SQLModel class**:
```python
class Entity(SQLModel, table=True):
    # ... existing fields ...
    new_field: Optional[str] = Field(default=None, nullable=True)
```

2. **Generate migration** (if using Alembic):
```bash
alembic revision --autogenerate -m "Add new_field to Entity"
alembic upgrade head
```

3. **Update mapper.py** to handle the new field

4. **Update domain models** if needed

### Removing Fields

Removing fields requires:
1. Update domain models
2. Update mapper.py
3. Create migration to drop column
4. Ensure backward compatibility during transition

### Changing Field Types

Type changes require careful migration:
1. Add new field with new type
2. Migrate data from old to new field
3. Update application code
4. Remove old field

## Relationship to Domain Objects

| Domain Model | Persistence Model | Notes |
|--------------|------------------|-------|
| `Disease`, `Gene`, `Drug`, etc. | `Entity` | Single table inheritance |
| `Treats`, `Causes`, etc. | `Relationship` | Generic relationship table |
| `Paper` | `Paper` | Direct mapping |
| `EvidenceItem` | `Evidence` | Direct mapping |

## Performance Optimization

### Indexes

All models include appropriate indexes:

**Entity:**
- Primary key: `entity_id`
- Index: `entity_type` for filtering
- Index: `umls_id`, `hgnc_id` for lookups
- HNSW: `embedding` for vector search (PostgreSQL)

**Relationship:**
- Primary key: `relationship_id`
- Composite: `(subject_id, predicate, object_id)` for lookups
- Index: `predicate` for filtering

### JSONB vs Separate Columns

Use JSONB (`properties`) for:
- Flexible/optional attributes
- Rarely queried fields
- Entity-type specific data

Use separate columns for:
- Frequently queried fields
- Fields requiring indexes
- Fields with strict types

### Vector Search

For semantic search:
1. Store embeddings in `embedding` field (as bytes)
2. Use HNSW index in PostgreSQL: `CREATE INDEX ON entities USING hnsw (embedding vector_cosine_ops)`
3. Query with: `SELECT * FROM entities ORDER BY embedding <=> query_vector LIMIT 10`

## Testing

Models are tested in `tests/storage/models/`:

```bash
# Test entity model
pytest tests/storage/models/test_entity.py -v

# Test all models
pytest tests/storage/models/ -v
```

## Further Reading

- [Storage Layer Overview](../README.md)
- [Storage Backends](../backends/README.md)
- [Database Setup Guide](../../DATABASE_SETUP.md)
- [Mapper Documentation](../../mapper.py)

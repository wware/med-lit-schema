# Architecture

The schema implements a **Domain/Persistence separation pattern** that cleanly separates application logic from database storage concerns.

## Overview

```
Data enters as Domain Objects → Mapper converts to Persistence Objects → Saved to DB
```

This architecture follows the principle that "how the code thinks about entities" should be different from "how the database stores entities."

## Architecture Layers

### 1. Domain Models (`entity.py`, `relationship.py`)

**Purpose:** "How the code thinks about entities."

**Technology:** Pure Pydantic v2 models with rich inheritance hierarchy.

**Characteristics:**

- Rich class hierarchy: `Disease`, `Gene`, `Drug` inherit from `BaseMedicalEntity`
- Type safety with Pydantic validation
- Clean OOP without ORM concerns
- Standards-based IDs (UMLS, HGNC, RxNorm, UniProt)

**Use Cases:**

- Ingestion scripts processing PubMed/PMC papers
- API request/response models (FastAPI)
- Business logic and transformations
- Client libraries

**Example:**

```python
from med_lit_schema.entity import Disease

disease = Disease(
    entity_id="C0006142",
    name="Breast Cancer",
    synonyms=["Breast Carcinoma"],
    umls_id="C0006142",
    source="umls"
)
```

### 2. Persistence Models (`storage/models/`)

**Purpose:** "How the database stores entities."

**Technology:** SQLModel (SQLAlchemy + Pydantic hybrid).

**Characteristics:**

- Single-table inheritance: All entity types in one `Entity` table
- Type discriminator column for polymorphism
- JSON serialization for complex fields (arrays, embeddings)
- Optimized for queries without JOINs

**Example:**

```python
from med_lit_schema.storage.models.entity import Entity
import json

entity = Entity(
    id="C0006142",
    entity_type="disease",
    name="Breast Cancer",
    synonyms=json.dumps(["Breast Carcinoma"]),
    umls_id="C0006142"
)
```

### 3. Mapper Layer (`mapper.py`)

**Purpose:** Convert between Domain and Persistence representations.

```python
from med_lit_schema.mapper import to_persistence, to_domain

# Domain → Persistence (for saving)
persistence_entity = to_persistence(disease)

# Persistence → Domain (for querying)
domain_entity = to_domain(persistence_entity)
```

## Why Separate Domain and Persistence?

**Alternative (Single Model):**

```python
# This mixes ORM concerns with business logic
class Disease(SQLModel, table=True):
    ...
```

**Problems:**

- ORM annotations pollute domain logic
- Database migrations affect application code
- Hard to use without database (API clients, tests)
- SQLAlchemy dependencies leak into business logic

**Our Approach (Separation):**

- Domain models work without database
- Can optimize database schema independently
- Easier to swap database implementations
- Better testability

## Why Single-Table Inheritance?

**Alternative approaches:**

1. **Joined-Table Inheritance** - Separate table per entity type
   - Requires JOINs for polymorphic queries
   - Complex migrations

2. **Multiple Tables** - No inheritance
   - Can't query across entity types
   - Duplicates common fields

3. **Single-Table Inheritance** (our choice)
   - No JOINs needed
   - Simple queries: `SELECT * FROM entities WHERE entity_type = 'disease'`
   - Easy migrations (ALTER TABLE ADD COLUMN)
   - Proven pattern (Django, Rails)

**Trade-offs:**

- Many nullable columns (acceptable)
- JSON serialization for arrays (enables flexible storage)

## Key Files

| File | Purpose |
|------|---------|
| `entity.py` | Domain models for entities |
| `relationship.py` | Domain models for relationships |
| `base.py` | Base classes and enums |
| `mapper.py` | Domain ↔ Persistence conversion |
| `storage/models/entity.py` | Persistence model for entities |
| `storage/models/relationship.py` | Persistence model for relationships |
| `storage/interfaces.py` | Abstract storage interfaces |
| `storage/backends/sqlite.py` | SQLite implementation |
| `storage/backends/postgres.py` | PostgreSQL implementation |

## Implementation Status

| Component | Status |
|-----------|--------|
| Domain Models | Complete |
| Persistence Models | Complete |
| Mapper Layer | Complete |
| SQLite Backend | Complete |
| PostgreSQL Backend | Complete |
| Integration Examples | In Progress |

## Next Steps

- [Ingestion Pipeline](ingestion.md) - How data flows through the system
- [Testing](testing.md) - Test strategy and coverage

# Schema Architecture: Domain/Persistence Separation Pattern

## Overview

The schema directory implements a **Domain/Persistence separation pattern** that cleanly separates application logic from database storage concerns. This architecture follows the principle that "how the code thinks about entities" should be different from "how the database stores entities."

This document explains:
1. The current architecture and design rationale
2. What has been implemented
3. What is missing (integration examples)
4. Implementation roadmap to complete the architecture

## Architecture Layers

### 1. Domain Models (`schema/entity.py`)

**Purpose**: "How the code thinks about entities."

**Technology**: Pure Pydantic v2 models with rich inheritance hierarchy.

**Design Characteristics**:
- **Rich class hierarchy**: `Disease`, `Gene`, `Drug`, `Protein`, etc., all inherit from `BaseMedicalEntity`
- **Type safety**: Strongly-typed with Pydantic validation
- **Clean OOP**: Pythonic object-oriented design without ORM concerns
- **Flexible**: Easy to extend and modify without database migrations
- **Standards-based**: Uses UMLS, HGNC, RxNorm, UniProt for canonical IDs

**Use Cases**:
- Ingestion pipelines processing PubMed/PMC papers
- API request/response models (FastAPI)
- Business logic and complex transformations
- Client libraries (Python, TypeScript)
- MCP server for LLM integration

**Example**:
```python
from schema import Disease, EntityType

disease = Disease(
    entity_id="C0006142",
    entity_type=EntityType.DISEASE,
    name="Breast Cancer",
    synonyms=["Breast Carcinoma", "Mammary Cancer"],
    abbreviations=["BC"],
    umls_id="C0006142",
    mesh_id="D001943",
    icd10_codes=["C50.9"],
    category="genetic",
    source="umls"
)
```

### 2. Persistence Models (`schema/entity_sqlmodel.py`)

**Purpose**: "How the database stores entities."

**Technology**: SQLModel (SQLAlchemy + Pydantic hybrid).

**Design Characteristics**:
- **Single-table inheritance**: All entity types stored in one `Entity` table
- **Flattened structure**: Type-specific fields are nullable columns
- **JSON serialization**: Complex fields (arrays, embeddings) stored as JSON strings
- **Optimized queries**: No JOINs needed to query "all entities"
- **Easier migrations**: Schema changes don't require complex table relationships

**Why Single-Table Inheritance?**
- ✅ **Performance**: Query all entities without JOINs
- ✅ **Simplicity**: One table to index, backup, and maintain
- ✅ **Flexibility**: Easy to add new entity types (just add columns)
- ✅ **Robustness**: Proven pattern for polymorphic data

**Trade-offs**:
- ⚠️ Many nullable columns (acceptable for medical domain)
- ⚠️ JSON serialization for arrays (acceptable, enables flexible storage)

**Example**:
```python
from schema.entity_sqlmodel import Entity, EntityType
import json

# Flattened persistence model
entity = Entity(
    id="C0006142",
    entity_type=EntityType.DISEASE.value,
    name="Breast Cancer",
    synonyms=json.dumps(["Breast Carcinoma", "Mammary Cancer"]),
    abbreviations=json.dumps(["BC"]),
    umls_id="C0006142",
    mesh_id="D001943",
    icd10_codes=json.dumps(["C50.9"]),
    disease_category="genetic",
    source="umls"
)
```

### 3. Mapper Layer (`schema/mapper.py`)

**Purpose**: Convert between Domain and Persistence representations.

**Expected Location**: `schema/mapper.py`

**Expected Functions**:
```python
def to_persistence(domain: BaseMedicalEntity) -> Entity:
    """Convert domain model to persistence model for database storage."""
    ...

def to_domain(persistence: Entity) -> BaseMedicalEntity:
    """Convert persistence model back to domain model."""
    ...
```

**The Documented Workflow** (from `schema/README.md`):
```
Data enters as Domain Objects → Mapper converts to Persistence Objects → Saved to DB
```

**The Current Reality**:
The mapper layer is implemented and tested.

## Current Implementation Status

### ✅ What's Implemented

1.  **Domain Models (`schema/entity.py`)**
    - ✅ Complete entity hierarchy with 14+ entity types
    - ✅ `BaseMedicalEntity` base class with common fields
    - ✅ Rich Pydantic validation
    - ✅ Evidence tracking with `EvidenceItem` class
    - ✅ `EntityCollection` for canonical entity management
    - ✅ Full ontology support (UMLS, HGNC, RxNorm, UniProt, etc.)

2.  **Persistence Models (`schema/entity_sqlmodel.py`)**
    - ✅ Single `Entity` table with polymorphic discriminator
    - ✅ All entity-specific fields as nullable columns
    - ✅ JSON serialization for arrays and embeddings
    - ✅ SQLModel integration (SQLAlchemy + Pydantic)

3.  **Relationship Domain Models (`schema/relationship.py`)**
    - ✅ Domain models for relationships (`Treats`, `Causes`, etc.)
    - ✅ Mandatory evidence tracking (provenance-first design)
    - ✅ `BaseMedicalRelationship` with confidence scoring
    - ✅ 30+ relationship types across clinical/molecular/provenance domains

4.  **Mapper Layer (`schema/mapper.py`)**
    - ✅ `to_persistence()` and `to_domain()` functions for entities
    - ✅ `relationship_to_persistence()` and `relationship_to_domain()` functions for relationships
    - ✅ Handles JSON serialization/deserialization for arrays and embeddings

5.  **Persistence Models for Relationships (`schema/relationship_sqlmodel.py`)**
    - ✅ Single `Relationship` table with predicate as discriminator
    - ✅ All relationship-specific fields as nullable columns
    - ✅ SQLModel integration

6.  **Testing**
    - ✅ Domain model tests (`tests/test_schema_entity.py`)
    - ✅ Persistence model tests (`tests/test_entity_sqlmodel.py`)
    - ✅ Validation tests for entity creation and queries
    - ✅ Mapper tests for entities (`tests/test_mapper.py`)
    - ✅ Mapper tests for relationships (`tests/test_relationship_mapper.py`)

### ❌ What's Missing

1.  **Integration**
    - ❌ `EntityCollection` doesn't use persistence layer
    - ❌ No database connection examples
    - ❌ No API layer demonstrating the full workflow

### ⚠️ Known Issues

1.  **Polymorphic SQLAlchemy Configuration**
    - The original intention was to enable polymorphic queries (e.g., `select(DiseaseEntity)`).
    - This feature proved difficult to implement correctly with `SQLModel` due to subtle instrumentation issues.
    - For now, polymorphic queries are **disabled and will not be pursued further** due to complexity vs. benefit.
    - Explicit filtering (`WHERE entity_type = 'disease'`) is used instead.
    - Polymorphic queries are not supported; explicit filtering by `entity_type` is used instead.

## Implementation Roadmap

### Phase 1: Core Mapper (COMPLETE)

**Goal**: Implement the missing mapper layer to complete the documented architecture.

**Tasks**:
1. Create `schema/mapper.py` with core functions
2. Implement `to_persistence()` for all entity types
3. Implement `to_domain()` for all entity types
4. Handle JSON serialization for arrays and embeddings
5. Support polymorphic conversion (detect entity type and return correct class)

### Phase 2: Mapper Tests (COMPLETE)

**Goal**: Comprehensive test coverage for mapper functions.

**Tasks**:
1. Create `tests/test_mapper.py`
2. Test round-trip conversion for all entity types
3. Test JSON serialization/deserialization
4. Test edge cases (empty arrays, null fields)
5. Test error handling (unknown entity types)

### Phase 3: Polymorphic Query Configuration (ABANDONED FOR NOW)

**Goal**: Determine if polymorphic SQLAlchemy configuration should be enabled.

**Decision**: Abandoned due to implementation complexities. Explicit filtering by `entity_type` is used instead.

### Phase 4: Relationship Persistence (COMPLETE)

**Goal**: Add persistence layer for relationships (not just entities).

**Tasks**:
1. Create `schema/relationship_sqlmodel.py`
2. Design single-table or multi-table approach for relationships
3. Implement relationship persistence models
4. Add mapper functions for relationships
5. Add tests for relationship persistence

### Phase 5: Integration Examples (Priority: HIGH)

**Goal**: Demonstrate the full workflow in production-like scenarios.

**Tasks**:
1. Update `EntityCollection` to use persistence layer
2. Add database connection examples
3. Create end-to-end example: load entities → query → save
4. Add API examples using FastAPI with mapper
5. Document best practices for using the architecture

**Estimated Effort**: 2-3 days

## Key Design Rationale

### Why Separate Domain and Persistence Models?

**Alternative Approach (Single Model)**:
```python
# Combine domain + persistence in one class
class Disease(SQLModel, table=True):
    # This mixes ORM concerns with business logic
    ...
```

**Rejected Because**:
- ❌ ORM annotations pollute domain logic
- ❌ Database migrations affect application code
- ❌ Hard to use in contexts without database (API clients, tests)
- ❌ SQLAlchemy dependencies leak into business logic

**Our Approach (Separation)**:
```python
# Domain: Pure Pydantic, no database concerns
class Disease(BaseMedicalEntity):
    ...

# Persistence: SQLModel, database-optimized
class Entity(SQLModel, table=True):
    ...

# Mapper: Bridge between the two
def to_persistence(disease: Disease) -> Entity:
    ...
```

**Benefits**:
- ✅ Clean separation of concerns
- ✅ Domain models work without database (tests, client libraries)
- ✅ Can optimize database schema independently
- ✅ Easier to swap database implementation
- ✅ Better testability (mock mapper in tests)

### Why Single-Table Inheritance for Persistence?

**Alternative Approaches**:

1. **Joined-Table Inheritance** (separate table per entity type)
   ```sql
   CREATE TABLE entities (...);
   CREATE TABLE diseases (...) INHERITS entities;
   CREATE TABLE genes (...) INHERITS entities;
   ```
   - ❌ Requires JOINs for polymorphic queries
   - ❌ Complex migrations when adding fields
   - ❌ Harder to query "all entities"

2. **Multiple Tables** (no inheritance)
   ```sql
   CREATE TABLE diseases (...);
   CREATE TABLE genes (...);
   CREATE TABLE drugs (...);
   ```
   - ❌ Can't query across entity types
   - ❌ Relationship tables need multiple foreign keys
   - ❌ Duplicates common fields

3. **Single-Table Inheritance** (current approach)
   ```sql
   CREATE TABLE entities (
     id TEXT PRIMARY KEY,
     entity_type TEXT,  -- discriminator
     name TEXT,
     -- Disease fields (nullable)
     umls_id TEXT,
     -- Gene fields (nullable)
     hgnc_id TEXT,
     ...
   );
   ```
   - ✅ No JOINs needed
   - ✅ Simple queries: `SELECT * FROM entities WHERE entity_type = 'disease'`
   - ✅ Easy migrations (ALTER TABLE ADD COLUMN)
   - ✅ Proven pattern (used by Django, Rails, etc.)

## Related Documentation

- **[README.md](README.md)** - Schema overview and design philosophy
- **[entity.py](entity.py)** - Domain model implementations
- **[entity_sqlmodel.py](entity_sqlmodel.py)** - Persistence model implementation
- **[relationship.py](relationship.py)** - Relationship domain models
- **[mapper.py](mapper.py)** - Mapper functions for domain/persistence conversion
- **[tests/test_schema_entity.py](tests/test_schema_entity.py)** - Domain model tests
- **[tests/test_entity_sqlmodel.py](tests/test_entity_sqlmodel.py)** - Persistence model tests

## Summary

The schema architecture is now **~90% complete**:
- ✅ Domain models fully implemented
- ✅ Persistence models fully implemented
- ✅ Mapper layer implemented and tested
- ✅ Relationship persistence implemented and tested
- ❌ Integration layer still missing

The documented workflow ("Domain Objects → Mapper → Persistence → DB") is now fully functional for both entities and relationships.

**Next Steps**:
1. Implement Phase 5: Integration Examples.
2. Update documentation with usage examples for the complete mapper.
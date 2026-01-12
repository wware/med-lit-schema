# Medical Knowledge Graph Query Interface

This directory contains tools for querying the medical knowledge graph in a storage-agnostic way.

## Overview

Our storage system is agnostic across:

* SQLite with sqlite-vec
* PostgreSQL with pgvector
* Neo4j

This query interface provides a unified, fluent API that works across all backends, with current support for PostgreSQL and planned support for Neo4j.

## Getting Started

### Interactive Exploration

Use the Jupyter notebook to explore queries interactively:

```bash
# Install dependencies
pip install jupyter matplotlib pandas psycopg2-binary

# Start Jupyter
jupyter notebook query/explore_queries.ipynb
```

The notebook includes comprehensive examples of:
- Entity and relationship queries
- Multi-hop graph traversals
- Semantic search
- Drug repurposing queries
- Differential diagnosis
- Evidence quality filtering

### Python Client Library

#### Installation

The query client is part of the `med-lit-schema` package. Install dependencies:

```bash
pip install psycopg2-binary pandas
# Optional for visualizations:
pip install matplotlib plotly
```

#### Basic Usage

```python
from query.client import GraphQuery, find_treatments

# High-level convenience functions
treatments = find_treatments("breast cancer", min_confidence=0.8)
print(f"Found {treatments.count} treatments")

# Display as DataFrame
df = treatments.to_dataframe()
print(df.head())

# Or build custom queries with fluent API
query = GraphQuery()
results = query.relationships(
    predicate="TREATS",
    min_confidence=0.8
).order_by("confidence", "desc").limit(20).execute()

print(f"Query took {results.query_time_ms:.2f}ms")
```

#### Advanced Queries

```python
# Entity queries with filters
drugs = GraphQuery().entities(
    entity_type="drug"
).filter(fda_approved="true").limit(50).execute()

# Multi-hop traversal (mechanism of action)
from query.client import find_drug_mechanisms
mechanisms = find_drug_mechanisms("tamoxifen", max_hops=3)

# Semantic search (requires embeddings)
similar = GraphQuery().semantic_search(
    "PARP inhibitor",
    entity_type="drug",
    top_k=10,
    threshold=0.7
).execute()

# Complex filtering
high_quality = GraphQuery().relationships(
    predicate="TREATS",
    min_confidence=0.8
).with_evidence(study_types=["rct", "meta_analysis"]).execute()
```

## Query Examples

### 1. Entity Queries

```python
# Find all entities of a type
drugs = GraphQuery().entities(entity_type="drug").limit(100).execute()

# Filter by properties
fda_drugs = GraphQuery().entities(
    entity_type="drug"
).filter(fda_approved="true").execute()

# Search by name
disease = GraphQuery().entities(
    entity_type="disease"
).filter(name="diabetes").execute()
```

### 2. Relationship Queries

```python
# Find relationships by predicate
treats = GraphQuery().relationships(predicate="TREATS").limit(100).execute()

# Filter by confidence
high_conf = GraphQuery().relationships(
    predicate="TREATS",
    min_confidence=0.8
).order_by("confidence", "desc").execute()

# Get all relationships for an entity
entity_rels = GraphQuery().relationships(
    subject_id="drug_123"
).execute()
```

### 3. Multi-Hop Traversals

```python
# Drug → Disease → Symptom (2-hop)
path = GraphQuery().traverse(
    start={"entity_id": "drug_123"},
    path=["TREATS:disease", "HAS_SYMPTOM:symptom"],
    max_hops=2
).execute()

# Drug → Protein → Gene → Disease (3-hop mechanism)
moa = GraphQuery().traverse(
    start={"entity_type": "drug", "name": "aspirin"},
    path=["TARGETS:protein", "ENCODED_BY:gene", "ASSOCIATED_WITH:disease"],
    max_hops=3
).execute()
```

### 4. Evidence and Provenance

```python
# Relationships with evidence
with_evidence = GraphQuery().relationships(
    predicate="TREATS",
    min_confidence=0.7
).with_evidence(study_types=["rct", "meta_analysis"]).execute()

# Show source papers
for result in with_evidence.results:
    print(f"{result['subject_id']} → {result['object_id']}")
    print(f"  Papers: {result['source_papers']}")
    print(f"  Confidence: {result['confidence']}")
```

### 5. Semantic Search

```python
# Find similar entities by embedding
similar_drugs = GraphQuery().semantic_search(
    "chemotherapy agent",
    entity_type="drug",
    top_k=20
).execute()

# Hybrid semantic + structural
# (combine semantic_search with other filters)
```

### 6. Medical Use Cases

#### Drug Repurposing

```python
# Find drugs targeting proteins associated with a disease
# Disease → Gene/Protein → Drug
# Filter for FDA-approved drugs not already indicated for this disease
```

#### Differential Diagnosis

```python
from query.client import search_by_symptoms

# Find diseases matching symptom combinations
candidates = search_by_symptoms(
    symptoms=["fever", "cough", "fatigue"],
    min_match=2
)
```

#### Mechanism of Action

```python
from query.client import find_drug_mechanisms

# Multi-hop path from drug to clinical outcome
mechanisms = find_drug_mechanisms("metformin", max_hops=4)
```

## API Reference

### GraphQuery Class

The main query builder with fluent API:

```python
GraphQuery(connection_string: Optional[str] = None)
```

**Methods:**

- `entities(entity_type, filters)` - Query entities
- `relationships(predicate, subject_id, object_id, min_confidence)` - Query relationships
- `traverse(start, path, max_hops)` - Multi-hop traversal
- `semantic_search(query_text, entity_type, top_k, threshold)` - Semantic search
- `filter(**kwargs)` - Add filters
- `limit(n)` - Limit results
- `order_by(field, direction)` - Order results
- `with_evidence(study_types)` - Include evidence
- `execute()` - Execute query and return results
- `to_sql()` - Generate SQL (for debugging)
- `to_cypher()` - Generate Cypher for Neo4j (future)

### QueryResults Class

Results object returned by `execute()`:

```python
@dataclass
class QueryResults:
    results: List[Dict[str, Any]]  # Result rows
    count: int                      # Number of results
    query_time_ms: float            # Query execution time
    query_sql: Optional[str]        # SQL that was executed
    
    def to_dataframe()  # Convert to pandas DataFrame
    def to_json()       # Convert to JSON string
```

### Convenience Functions

Pre-built queries for common use cases:

```python
find_treatments(disease, min_confidence, study_types)
find_disease_genes(disease, min_confidence)
find_drug_mechanisms(drug, max_hops)
search_by_symptoms(symptoms, min_match)
```

## Configuration

Set the database connection string via environment variable:

```bash
export DATABASE_URL="postgresql://user:password@localhost:5432/medlit"
```

Or pass it directly:

```python
query = GraphQuery(connection_string="postgresql://...")
```

## Implementation Notes

### Current Implementation

- ✅ PostgreSQL backend with SQLModel
- ✅ Entity and relationship queries
- ✅ Confidence filtering
- ✅ Property-based filtering
- ✅ Result conversion to pandas DataFrame

### Planned Features

- ⚠️ Recursive CTEs for multi-hop traversals
- ⚠️ Evidence table joins
- ⚠️ Semantic search with pgvector
- ⚠️ Neo4j Cypher generation
- ⚠️ Query optimization and caching

### Design Principles

1. **Storage-agnostic** - Abstract interface works across backends
2. **Fluent API** - Method chaining for readable queries
3. **Type-safe** - Full type hints for IDE support
4. **Well-documented** - Clear examples and docstrings
5. **Testable** - Easy to unit test query building

## Resources

- **Notebook**: `explore_queries.ipynb` - Interactive examples
- **Client**: `client.py` - Python query library
- **Notes**: `NOTES.md` - Design discussions
- **Schema**: `../storage/models/` - Database schema

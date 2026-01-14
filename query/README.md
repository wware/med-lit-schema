# Medical Knowledge Graph Query Interface

This directory contains tools for querying the medical knowledge graph in a storage-agnostic way.

## Overview

This query system provides multiple ways to access the medical knowledge graph:

1. **FastAPI Server** - RESTful, GraphQL, and MCP (Model Context Protocol) endpoints for remote access
2. **Python Client Library** - Fluent API for direct database queries
3. **Jupyter Notebook** - Interactive exploration interface

Our storage system is agnostic across:

* SQLite with sqlite-vec
* PostgreSQL with pgvector
* Neo4j

The FastAPI server and Python client provide unified interfaces that work across all backends, with current support for PostgreSQL and planned support for Neo4j.

## API Server

A production-ready FastAPI server provides three ways to query the knowledge graph:

### Starting the Server

#### With Docker Compose (Recommended)

```bash
docker-compose up api
```

The server will be available at `http://localhost:8000`.

#### Direct with uvicorn

```bash
uv run uvicorn main:app --host 0.0.0.0 --port 8000
```

### API Endpoints

#### 1. REST API

Self-documenting REST endpoints at `/docs`:

**Entities:**
- `GET /api/v1/entities/{entity_id}` - Get entity by ID
- `GET /api/v1/entities?entity_type=drug&limit=100` - List/search entities

**Relationships:**
- `GET /api/v1/relationships?predicate=TREATS&limit=100` - Query relationships
- `GET /api/v1/relationships?subject_id={id}` - Get relationships for entity

**Papers:**
- `GET /api/v1/papers/{paper_id}` - Get research paper by ID

**Semantic Search:**
- `POST /api/v1/search/semantic` - Semantic similarity search
  ```json
  {
    "query_text": "PARP inhibitors for cancer",
    "top_k": 10,
    "threshold": 0.7
  }
  ```

**Examples:**

```bash
# Get all drugs
curl "http://localhost:8000/api/v1/entities?entity_type=drug&limit=10"

# Find treatments
curl "http://localhost:8000/api/v1/relationships?predicate=TREATS&limit=20"

# Semantic search
curl -X POST "http://localhost:8000/api/v1/search/semantic" \
  -H "Content-Type: application/json" \
  -d '{"query_text": "breast cancer treatments", "top_k": 10}'
```

#### 2. GraphQL API

Interactive GraphiQL interface at `/graphiql` with example queries dropdown menu.

The interface includes pre-built example queries:
- Get Entity by ID
- Search Entities
- Find Treatments
- Get Paper
- Filter by Subject
- Multiple Queries

Simply select an example from the dropdown menu to populate the query editor.

**Note:** The GraphQL schema uses JSON scalar types, so queries return entire objects as JSON rather than allowing field selection. This is a simplified implementation - for full type safety, structured GraphQL types can be added.

**Available Queries:**

```graphql
# Returns entire paper as JSON
query GetPaper {
  paper(id: "pmid_12345678")
}

# Returns entire entity as JSON
query GetEntity {
  entity(id: "drug_aspirin")
}

# Returns array of entities as JSON
query SearchEntities {
  entities(limit: 10, offset: 0)
}

# Returns array of relationships as JSON
query GetRelationships {
  relationships(
    predicate: "TREATS"
    limit: 20
  )
}
```

**Example with cURL:**

```bash
curl -X POST "http://localhost:8000/graphql" \
  -H "Content-Type: application/json" \
  -d '{"query": "{ entity(id: \"drug_aspirin\") }"}'
```

#### 3. MCP (Model Context Protocol)

AI agent integration endpoints at `/mcp` and `/mcp/sse`.

**Available Tools:**

- `find_treatments(disease_name, limit)` - Find drugs that treat a disease
- `find_related_genes(disease_name, limit)` - Find genes associated with a disease
- `get_entity(entity_id)` - Retrieve entity by canonical ID
- `search_entities(query, entity_type, limit)` - Search entities by name
- `get_paper(paper_id)` - Retrieve research paper by ID

These tools are designed for AI agents (like Claude) to query the knowledge graph naturally.

**Example MCP Configuration:**

```json
{
  "mcpServers": {
    "medical-knowledge": {
      "url": "http://localhost:8000/mcp/sse"
    }
  }
}
```

### Health Check

```bash
curl http://localhost:8000/health
```

Returns: `{"status": "healthy"}`

### API Documentation

Visit `http://localhost:8000/docs` for interactive Swagger UI documentation of all REST endpoints.

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

**API Server (Complete):**
- ✅ FastAPI server with REST, GraphQL, and MCP endpoints
- ✅ PostgreSQL backend with singleton storage factory
- ✅ Semantic search with sentence-transformers embeddings
- ✅ Docker containerization with docker-compose
- ✅ Self-documenting via Swagger UI and GraphiQL
- ✅ Health checks and connection lifecycle management

**Python Client Library:**
- ✅ PostgreSQL backend with SQLModel
- ✅ Entity and relationship queries
- ✅ Confidence filtering
- ✅ Property-based filtering
- ✅ Result conversion to pandas DataFrame

### Planned Features

**Python Client Library:**
- ⚠️ Recursive CTEs for multi-hop traversals
- ⚠️ Evidence table joins
- ⚠️ Semantic search with pgvector
- ⚠️ Neo4j Cypher generation
- ⚠️ Query optimization and caching

**API Server Enhancements:**
- ⚠️ Full GraphQL type safety (currently uses JSON scalars)
- ⚠️ Entity semantic search (currently only relationship search)
- ⚠️ Full-text search endpoints
- ⚠️ Response caching (Redis)
- ⚠️ Rate limiting
- ⚠️ Comprehensive test coverage

### Design Principles

1. **Storage-agnostic** - Abstract interface works across backends
2. **Fluent API** - Method chaining for readable queries
3. **Type-safe** - Full type hints for IDE support
4. **Well-documented** - Clear examples and docstrings
5. **Testable** - Easy to unit test query building

## Resources

**API Server:**
- **Server**: `server.py` - FastAPI application
- **REST API**: `routers/rest_api.py` - RESTful endpoints
- **GraphQL**: `graphql_schema.py` - GraphQL schema and resolvers
- **MCP**: `routers/mcp_api.py` - Model Context Protocol tools
- **Storage**: `storage_factory.py` - Database connection management
- **Docs**: `IMPLEMENTATION_PLAN.md` - Complete implementation details
- **Architecture**: `API_ARCHITECTURE.md` - System design

**Python Client Library:**
- **Notebook**: `explore_queries.ipynb` - Interactive examples
- **Client**: `client.py` - Python query library
- **Notes**: `NOTES.md` - Design discussions

**Database Schema:**
- **Models**: `../storage/models/` - Pydantic data models

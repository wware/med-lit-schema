# Querying the Knowledge Graph

Multiple ways to query the medical knowledge graph: REST API, GraphQL, MCP, and Python client.

## Starting the Server

### With Docker Compose (Recommended)

```bash
docker compose up -d postgres redis
docker compose up api
```

The server will be available at `http://localhost:8000`.

### Direct with uvicorn

```bash
uv run uvicorn query.server:app --host 0.0.0.0 --port 8000
```

## REST API

Self-documenting REST endpoints at `/docs`.

### Endpoints

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

### Examples

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

## GraphQL API

Interactive GraphiQL interface at `/graphiql` with example queries dropdown.

### Available Queries

```graphql
# Get a paper
query GetPaper {
  paper(id: "pmid_12345678")
}

# Get an entity
query GetEntity {
  entity(id: "drug_aspirin")
}

# Search entities
query SearchEntities {
  entities(limit: 10, offset: 0)
}

# Get relationships
query GetRelationships {
  relationships(
    predicate: "TREATS"
    limit: 20
  )
}
```

### Example with cURL

```bash
curl -X POST "http://localhost:8000/graphql" \
  -H "Content-Type: application/json" \
  -d '{"query": "{ entity(id: \"drug_aspirin\") }"}'
```

## MCP (Model Context Protocol)

AI agent integration endpoints at `/mcp` and `/mcp/sse`.

### Available Tools

| Tool | Description |
|------|-------------|
| `find_treatments(disease_name, limit)` | Find drugs that treat a disease |
| `find_related_genes(disease_name, limit)` | Find genes associated with a disease |
| `get_entity(entity_id)` | Retrieve entity by canonical ID |
| `search_entities(query, entity_type, limit)` | Search entities by name |
| `get_paper(paper_id)` | Retrieve research paper by ID |

These tools are designed for AI agents (like Claude) to query the knowledge graph naturally.

## Python Client

Direct database access with a fluent API.

```python
from med_lit_schema.storage.backends.postgres import PostgresPipelineStorage

# Connect to database
storage = PostgresPipelineStorage("postgresql://user:pass@localhost/medlit")

# Query entities
diseases = storage.entities.get_by_type("disease", limit=100)
drug = storage.entities.get_by_id("RxNorm:1187832")

# Query relationships
treatments = storage.get_relationships_by_predicate("TREATS", limit=50)
drug_relationships = storage.get_relationships_by_subject(drug.entity_id)

# Semantic search (requires embeddings)
similar = storage.find_similar_entities(query_embedding, top_k=10)
```

## Query Patterns

### Find treatments for a disease

```bash
# REST
curl "http://localhost:8000/api/v1/relationships?predicate=TREATS&object_id=C0006142"

# GraphQL
query { relationships(predicate: "TREATS", objectId: "C0006142") }
```

### Find all relationships for an entity

```bash
# REST
curl "http://localhost:8000/api/v1/relationships?subject_id=RxNorm:1187832"
```

### Multi-hop queries

For complex multi-hop queries (e.g., "drugs that treat diseases caused by gene X"), use the Python client or construct multiple API calls.

```python
# Find diseases caused by BRCA1
caused_by_brca1 = storage.get_relationships_by_predicate(
    "INCREASES_RISK",
    subject_id="HGNC:1100"
)
disease_ids = [r.object_id for r in caused_by_brca1]

# Find treatments for those diseases
treatments = []
for disease_id in disease_ids:
    treats = storage.get_relationships_by_predicate(
        "TREATS",
        object_id=disease_id
    )
    treatments.extend(treats)
```

## Next Steps

- [Storage Options](storage.md) - Database backend configuration
- [Developer Guide](../developer-guide/index.md) - API architecture details

# Quickstart

Get up and running with the medical knowledge graph in 5 minutes.

## Installation

```bash
# Install the library
uv add med-lit-schema

# Or for development
git clone https://github.com/wware/med-lit-schema
cd med-lit-schema
uv sync
```

## Basic Usage

### Create Entities

```python
from med_lit_schema.entity import Disease, Drug, Gene
from med_lit_schema.base import EntityType

# Create a disease entity with canonical UMLS ID
disease = Disease(
    entity_id="C0006142",
    name="Breast Cancer",
    synonyms=["Breast Carcinoma", "Mammary Cancer"],
    umls_id="C0006142",
    source="umls"
)

# Create a drug entity with RxNorm ID
drug = Drug(
    entity_id="RxNorm:1187832",
    name="Olaparib",
    drug_class="PARP inhibitor"
)

# Create a gene entity with HGNC ID
gene = Gene(
    entity_id="HGNC:1100",
    name="BRCA1",
    symbol="BRCA1",
    hgnc_id="HGNC:1100"
)
```

### Create Relationships with Evidence

```python
from med_lit_schema.relationship import create_relationship
from med_lit_schema.base import PredicateType

# Create a "treats" relationship with provenance
treats = create_relationship(
    PredicateType.TREATS,
    subject_id=drug.entity_id,
    object_id=disease.entity_id,
    source_papers=["PMC999"],
    confidence=0.85
)

# Create a "increases risk" relationship
risk = create_relationship(
    PredicateType.INCREASES_RISK,
    subject_id=gene.entity_id,
    object_id=disease.entity_id,
    source_papers=["PMC888", "PMC777"],
    confidence=0.92
)
```

### Store in Database

```python
from med_lit_schema.storage.backends.sqlite import SQLitePipelineStorage

# For development: SQLite
storage = SQLitePipelineStorage("my_database.db")

# Store entities and relationships
storage.entities.add_disease(disease)
storage.entities.add_drug(drug)
storage.entities.add_gene(gene)
storage.add_relationship(treats)
storage.add_relationship(risk)
```

## Start the API Server

```bash
# Start database
docker compose up -d postgres redis

# Run the API
uv run uvicorn query.server:app --port 8000
```

Then visit:

- REST API docs: `http://localhost:8000/docs`
- GraphQL playground: `http://localhost:8000/graphiql`

## Query Examples

### REST API

```bash
# Get all drugs
curl "http://localhost:8000/api/v1/entities?entity_type=drug&limit=10"

# Find treatments for a disease
curl "http://localhost:8000/api/v1/relationships?predicate=TREATS&limit=20"

# Semantic search
curl -X POST "http://localhost:8000/api/v1/search/semantic" \
  -H "Content-Type: application/json" \
  -d '{"query_text": "breast cancer treatments", "top_k": 10}'
```

### GraphQL

```graphql
query FindTreatments {
  relationships(predicate: "TREATS", limit: 20)
}

query GetEntity {
  entity(id: "C0006142")
}
```

## Next Steps

- [Core Concepts](concepts.md) - Understand canonical IDs, provenance, and evidence
- [Querying](querying.md) - Full API reference and query patterns
- [Storage Options](storage.md) - PostgreSQL for production

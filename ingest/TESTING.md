# Ingest Testing Guide

## Overview

The ingest process uses ABC-style storage interfaces that support both SQLite (for testing) and PostgreSQL+pgvector (for production). This guide explains how to test the ingest components.

## Testing with In-Memory SQLite

The `SQLitePipelineStorage` supports `:memory:` for in-memory databases, making it ideal for testing:

```python
from med_lit_schema.pipeline.sqlite_storage import SQLitePipelineStorage

# In-memory database (no file created)
storage = SQLitePipelineStorage(":memory:")

# Or use a temporary file
from pathlib import Path
from tempfile import NamedTemporaryFile
with NamedTemporaryFile(delete=False, suffix='.db') as tmp:
    storage = SQLitePipelineStorage(Path(tmp.name))
```

## Test Coverage

### What We Can Test

1. **Storage Interfaces**
   - Entity storage and retrieval
   - Paper storage and retrieval
   - Relationship storage and retrieval
   - Evidence storage and retrieval
   - Count operations

2. **Entity Models**
   - Disease, Gene, Drug creation
   - Entity resolution (synonyms)
   - Canonical ID lookups (UMLS, HGNC, RxNorm)

3. **Relationship Models**
   - Relationship creation with `create_relationship()`
   - Predicate types (TREATS, CAUSES, etc.)
   - Evidence attachment

4. **Evidence Models**
   - EvidenceItem creation
   - Evidence metrics (sample size, p-value)
   - Evidence linking to papers and relationships

5. **Provenance Ingest**
   - XML parsing
   - Paper metadata extraction
   - Author, journal, date extraction

### What Requires Real Data

1. **NER Ingest**
   - Requires BioBERT model download
   - Needs actual PMC XML files
   - Entity extraction from text

2. **Claims Ingest**
   - Requires entity resolution (linking mentions to canonical IDs)
   - Needs paragraph-level text
   - Pattern matching or LLM extraction

3. **Embeddings Ingest**
   - Requires sentence-transformers models
   - Needs text to embed
   - Vector similarity search

## Running Tests

### Using pytest

Create test files in `tests/` directory:

```python
# tests/test_pipeline_storage.py
import pytest
from med_lit_schema.pipeline.sqlite_storage import SQLitePipelineStorage
from med_lit_schema.entity import Disease, EntityType

def test_entity_storage():
    storage = SQLitePipelineStorage(":memory:")
    disease = Disease(
        entity_id="C0006142",
        entity_type=EntityType.DISEASE,
        name="Breast Cancer",
        source="umls"
    )
    storage.entities.add_disease(disease)
    retrieved = storage.entities.get_by_id("C0006142")
    assert retrieved.name == "Breast Cancer"
    storage.close()
```

Run with:
```bash
uv run pytest tests/test_pipeline_storage.py -v
```

### Using Fake Papers

Create representative fake PMC XML files for integration testing:

```python
# Create fake XML
xml_content = """<?xml version="1.0"?>
<article>
  <front>
    <article-meta>
      <article-id pub-id-type="pmcid">PMC999999</article-id>
      <title-group>
        <article-title>Test Paper</article-title>
      </title-group>
      <abstract><p>Test abstract</p></abstract>
    </article-meta>
  </front>
  <body>
    <sec><title>Results</title>
      <p>Olaparib treats breast cancer.</p>
    </sec>
  </body>
</article>"""

# Parse and store
from med_lit_schema.ingest.provenance_pipeline import parse_pmc_xml
paper = parse_pmc_xml(Path("fake_paper.xml"))
storage.papers.add_paper(paper)
```

## Example Test Script

Here's a complete example that tests the full ingest:

```python
#!/usr/bin/env -S uv run python
"""Test ingest with fake papers."""

from med_lit_schema.pipeline.sqlite_storage import SQLitePipelineStorage
from med_lit_schema.entity import Paper, Disease, EntityType
from med_lit_schema.relationship import create_relationship
from med_lit_schema.base import PredicateType

# Use in-memory database
storage = SQLitePipelineStorage(":memory:")

# Create entities
disease = Disease(
    entity_id="C0006142",
    entity_type=EntityType.DISEASE,
    name="Breast Cancer",
    source="umls"
)
storage.entities.add_disease(disease)

# Create relationship
rel = create_relationship(
    predicate=PredicateType.TREATS,
    subject_id="RxNorm:1187832",
    object_id="C0006142",
    confidence=0.95
)
storage.relationships.add_relationship(rel)

# Verify
assert storage.entities.entity_count == 1
assert storage.relationships.relationship_count == 1
print("✓ All tests passed!")

storage.close()
```

## Testing Vector Similarity Search

### SQLite with sqlite-vec

To test vector similarity search with SQLite:

1. Install sqlite-vec extension from https://github.com/asg017/sqlite-vec
2. The `SQLiteEntityCollection` automatically tries to load sqlite-vec
3. Falls back to Python-based cosine similarity if extension not available

### PostgreSQL with pgvector

To test with PostgreSQL:

1. Install pgvector extension in PostgreSQL
2. Use `PostgresPipelineStorage` with a PostgreSQL connection
3. Vector similarity search uses pgvector's `<=>` operator

## End-to-End Testing

The `tests/test_provenance_pipeline.py` file includes an end-to-end test that validates a complete paper ingestion flow:

- Creates entities
- Creates relationships
- Links evidence to relationships
- Verifies all data is stored and retrievable

Run the full test suite:
```bash
uv run pytest tests/ -v
```

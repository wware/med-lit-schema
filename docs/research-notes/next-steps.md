# Next Steps

Current priorities and roadmap for the project.

!!! note "Source"
    This summarizes `ingest/NEXT_STEPS.md` - see that file for detailed implementation notes.

## Recent Progress

All 5 pipeline stages are working end-to-end with PostgreSQL:

| Stage | Status | Notes |
|-------|--------|-------|
| Download | Complete | PMC XML download via NCBI API |
| Provenance | Complete | 105 papers processed |
| NER | Complete | 396 entities, 1,056 extraction edges |
| Claims | Complete | 273 relationships extracted |
| Evidence | Complete | 0 items (expected - see below) |

## Known Limitations

### Evidence Extraction Returns Zero Items

The evidence pipeline finds zero quantitative items because:

- Relationship text comes from abstracts
- Statistical data (sample sizes, p-values) is typically in Results sections
- Current regex patterns don't match abstract language

**To fix:** Process full paper text, not just abstracts.

### PostgreSQL Relationship Embeddings

Relationship embedding storage is not implemented for PostgreSQL.

**Current workaround:** Use `--skip-embeddings` flag in claims pipeline.

**To fix:** Implement `PostgresRelationshipEmbeddingStorage` in `storage/backends/postgres.py`.

### Entity Resolution

Relationships use placeholder IDs like `PLACEHOLDER_SUBJECT_PMC12775696_claim_2`.

**To fix:** Link placeholder IDs to canonical entities via:
- Name matching
- Synonym matching
- Embedding similarity

## Priority Tasks

### 1. Implement PostgreSQL Relationship Embeddings

**Priority:** High

```python
# In storage/backends/postgres.py
def store_relationship_embedding(
    self, subject_id: str, predicate: str, object_id: str,
    embedding: list[float], model_name: str
) -> None:
    """Store embedding using pgvector."""
    ...
```

### 2. Entity Resolution

**Priority:** High

Link placeholder relationship IDs to canonical entities for proper graph traversal.

### 3. Improve Evidence Extraction

**Priority:** Medium

- Parse full paper Results sections
- Implement more sophisticated NLP patterns
- Link relationships to paragraphs with statistical data

## Future Considerations

### Python Packaging

Package published to test.pypi.org. Planning pypi.org release after more progress.

### Full-Text Processing

Current pipeline processes abstracts only. Full-text would:
- Improve evidence extraction
- Enable richer relationship extraction
- Require more storage and processing time

## Related Documentation

- [Ingestion Pipeline](../developer-guide/ingestion.md) - Pipeline details
- [Architecture](../developer-guide/architecture.md) - Design decisions

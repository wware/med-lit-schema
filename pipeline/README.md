# Pipeline Storage Refactoring

## Overview

The pipeline has been refactored to use ABC-style storage interfaces, allowing different storage backends (SQLite for testing, PostgreSQL+pgvector for production) to be used interchangeably.

## Storage Interfaces

All storage is accessed through `PipelineStorageInterface` which provides:
- `entities`: EntityCollectionInterface (from entity.py)
- `papers`: PaperStorageInterface
- `relationships`: RelationshipStorageInterface  
- `evidence`: EvidenceStorageInterface

## Implementations

### SQLitePipelineStorage
- **Location**: `pipeline/sqlite_storage.py`
- **Use case**: Testing, development, small datasets
- **Initialization**: `SQLitePipelineStorage(Path("output/pipeline.db"))`
- **Features**: 
  - Uses `sqlite-vec` extension for vector similarity search (optional)
  - Falls back to Python-based cosine similarity if extension not available
  - Install sqlite-vec from https://github.com/asg017/sqlite-vec for embedding search

### PostgresPipelineStorage
- **Location**: `pipeline/postgres_storage.py`
- **Use case**: Production, large datasets, vector search
- **Initialization**: `PostgresPipelineStorage("postgresql://user:pass@localhost/dbname")`

## Usage Pattern

```python
from pipeline.storage_interfaces import PipelineStorageInterface
from pipeline.sqlite_storage import SQLitePipelineStorage
# or
from pipeline.postgres_storage import PostgresPipelineStorage

# Initialize storage (client chooses backend)
storage: PipelineStorageInterface = SQLitePipelineStorage(Path("output/pipeline.db"))
# or
storage: PipelineStorageInterface = PostgresPipelineStorage(database_url)

# Use storage in pipeline
storage.entities.add_disease(disease)
storage.papers.add_paper(paper)
storage.relationships.add_relationship(relationship)
storage.evidence.add_evidence(evidence_item)

# Clean up
storage.close()
```

## Refactored Pipeline Files

All pipeline stages have been refactored to use the new schema and storage interfaces:

- **`ner_pipeline_refactored.py`**: Entity extraction using BioBERT NER
- **`provenance_pipeline_refactored.py`**: Paper metadata and document structure extraction
- **`claims_pipeline_refactored.py`**: Relationship extraction from text (placeholder)
- **`evidence_pipeline_refactored.py`**: Evidence metrics extraction (placeholder)

These refactored versions:
- Accept `--storage sqlite` or `--storage postgres` arguments
- Use the new schema models (Paper, BaseRelationship, EvidenceItem, etc.)
- Store data via storage interfaces instead of direct database access
- Support both SQLite (with sqlite-vec) and PostgreSQL+pgvector backends

## Migration Notes

- Old SQLite direct access → Use `SQLitePipelineStorage`
- Old PostgreSQL+AGE → Use `PostgresPipelineStorage` (replaces AGE with pgvector)
- Old models (ExtractionEdge, old Claim, etc.) → Use new schema models
- Domain models are automatically converted to/from persistence models via `mapper.py`

## Next Steps

The refactored pipeline files provide the structure and interfaces, but some functionality is still placeholder:
- Entity resolution in claims extraction (linking mentions to canonical IDs)
- Full integration with provenance data for paragraph-level tracking
- Complete evidence extraction with all metrics

These can be implemented incrementally while using the storage interfaces.

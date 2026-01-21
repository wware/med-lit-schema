# Migration to kgraph/kgserver

This document describes the migration of med-lit-schema functionality to kgraph and kgserver.

## Overview

med-lit-schema has been refactored into:
- **kgraph/examples/medlit/** - Domain extension for knowledge graph ingestion
- **kgserver** - Generic knowledge graph server that loads bundles

## What's Been Migrated

### Domain Models
✅ **Migrated to**: `kgraph/examples/medlit/entities.py`
- Disease, Gene, Drug, Protein, Symptom, Procedure, Biomarker, Pathway entities
- Canonical ID support (UMLS, HGNC, RxNorm, UniProt)
- Entity status (canonical/provisional)

### Relationships
✅ **Migrated to**: `kgraph/examples/medlit/relationships.py`
- MedicalClaimRelationship (Pattern A: one class for all predicates)
- Predicate vocabulary and validation rules
- Evidence and provenance tracking

### Documents
✅ **Migrated to**: `kgraph/examples/medlit/documents.py`
- JournalArticle(BaseDocument) mapping from Paper format
- Metadata preservation (study type, sample size, MeSH terms)
- Extraction provenance tracking

### Domain Schema
✅ **Migrated to**: `kgraph/examples/medlit/domain.py`
- MedLitDomainSchema with entity/relationship/document registries
- Promotion configuration for medical entities
- Predicate validation rules

### Pipeline Components
✅ **Migrated to**: `kgraph/examples/medlit/pipeline/`
- JournalArticleParser - Parses Paper JSON format
- MedLitEntityExtractor - Extracts entity mentions
- MedLitEntityResolver - Resolves to canonical entities
- MedLitRelationshipExtractor - Extracts relationships with evidence
- SimpleMedLitEmbeddingGenerator - Hash-based embeddings (placeholder)

### Ingestion Script
✅ **Migrated to**: `kgraph/examples/medlit/scripts/ingest.py`
- Processes Paper JSON files
- Generates kgraph-compatible bundles
- Ready to process 100+ papers

## What's Been Removed (Obsolete)

### Storage Layer
❌ **Removed** - Replaced by kgraph/kgserver
- `storage/` directory - All storage interfaces, backends, and models
- kgraph uses bundle export (JSONL files)
- kgserver loads bundles into its own storage

### Query/API Layer
❌ **Removed** - Replaced by kgserver
- `query/` directory - All API/server code
- `main.py` - Replaced by kgserver/main.py
- kgserver provides domain-agnostic query API

### Domain-to-Persistence Mapping
❌ **Removed** - No longer needed
- `mapper.py` - Domain-to-persistence mapping
- kgraph uses bundles, no persistence layer needed

### Entity Collection Interface
❌ **Removed** - Replaced by kgraph's EntityStorageInterface
- `ENTITY_COLLECTION_INTERFACE.md` - Obsolete interface docs
- kgraph's storage interfaces are more general

## What Remains (To Be Migrated or Kept)

### Ingestion Pipeline (`ingest/` directory)
⚠️ **Keep for now** - Logic can be adapted for kgraph
- `ingest/pmc_parser.py` - PMC XML parsing (can be ported to JournalArticleParser)
- `ingest/ner_pipeline.py` - NER extraction (can be adapted for MedLitEntityExtractor)
- `ingest/claims_pipeline.py` - Relationship extraction (can be adapted for MedLitRelationshipExtractor)
- `ingest/embeddings_pipeline.py` - Embedding generation (can be adapted)

**Action**: Port useful extraction logic to kgraph's pipeline components, then can remove.

### Domain Models (`entity.py`, `relationship.py`, `base.py`)
⚠️ **Keep for reference** - Ported to kgraph, but keep originals during migration
- Domain models have been ported to `kgraph/examples/medlit/`
- Keep originals for reference during migration
- Can be removed once migration is complete and tested

### Tests (`tests/` directory)
⚠️ **Keep for reference** - Tests should be rewritten for kgraph
- Tests are tied to the old architecture
- Useful as reference for what to test in the new architecture
- Can be removed once kgraph tests are comprehensive

### Documentation (`docs/` directory)
⚠️ **Keep for reference** - Update for kgraph/kgserver
- Architecture docs may still be useful
- User guides may need updates for kgraph/kgserver
- Keep until migration is complete

### Output Data (`output/` directory)
✅ **Keep** - Generated data files
- `output/json_papers/` - Paper JSON files used by kgraph ingestion
- `output/entities.jsonl` - May be useful for reference
- `output/extraction_provenance.json` - Useful for reference

## Using the kgraph Extension

### Process Papers and Generate Bundle

```bash
cd /path/to/kgraph
uv run python -m examples.medlit.scripts.ingest \
    --input-dir /path/to/med-lit-schema/output/json_papers \
    --output-dir medlit_bundle
```

### Load Bundle in kgserver

The generated bundle can be loaded by kgserver:

```bash
cd /path/to/kgserver
# Copy bundle to kgserver
cp -r /path/to/kgraph/medlit_bundle /path/to/kgserver/bundles/

# Start kgserver (it will load the bundle automatically)
uvicorn main:app --reload
```

## Next Steps

1. **Port extraction logic** from `ingest/` to kgraph pipeline components
2. **Update tests** to use kgraph architecture
3. **Update documentation** to reflect kgraph/kgserver architecture
4. **Remove domain models** from med-lit-schema once migration verified
5. **Remove ingestion pipeline** once logic is ported

## References

- [kgraph med-lit extension](../../kgraph/examples/medlit/README.md)
- [kgraph med-lit TODO](../../kgraph/examples/medlit/TODO.md)
- [kgraph architecture](../../kgraph/docs/architecture.md)
- [kgserver architecture](../../kgserver/docs/architecture.md)

# med-lit-schema TODO

This document tracks remaining work for med-lit-schema, including migration to kgraph and enhancements.

## Migration Status

See [MIGRATION_TO_KGRAPH.md](./MIGRATION_TO_KGRAPH.md) for details on what's been migrated to kgraph/kgserver.

## Remaining Migration Tasks

### 1. Port PMC XML Parser to kgraph
**Status**: Not Started  
**Priority**: Medium  
**Component**: `kgraph/examples/medlit/pipeline/parser.py`

**Current State**:
- `JournalArticleParser` only handles JSON format
- PMC XML parsing raises `NotImplementedError`

**Action**:
- Port logic from `ingest/pmc_parser.py` to `JournalArticleParser`
- Handle JATS XML format (standard for PMC)
- Extract metadata, abstract, full text, sections

**Reference**: `ingest/pmc_parser.py` has complete implementation

---

### 2. Port NER Extraction Logic to kgraph
**Status**: Not Started  
**Priority**: High  
**Component**: `kgraph/examples/medlit/pipeline/mentions.py`

**Current State**:
- `MedLitEntityExtractor` only extracts from pre-extracted entities in Paper JSON
- Returns empty list if no pre-extracted entities found

**Action**:
- Port NER extraction logic from `ingest/ner_pipeline.py`
- Support BioBERT, scispaCy, and Ollama-based extraction
- Map NER labels to entity types (disease, drug, gene, etc.)

**Reference**: 
- `ingest/ner_pipeline.py` - Complete NER pipeline with multiple backends
- See [kgraph TODO](../../kgraph/examples/medlit/TODO.md) for implementation details

---

### 3. Port Relationship Extraction Logic to kgraph
**Status**: Not Started  
**Priority**: High  
**Component**: `kgraph/examples/medlit/pipeline/relationships.py`

**Current State**:
- `MedLitRelationshipExtractor` only extracts from pre-extracted relationships in Paper JSON
- Returns empty list if no pre-extracted relationships found

**Action**:
- Port pattern-based extraction from `ingest/claims_pipeline.py`
- Add LLM-based extraction (Ollama/OpenAI)
- Support evidence extraction and provenance tracking

**Reference**:
- `ingest/claims_pipeline.py` - Pattern-based relationship extraction
- See [kgraph TODO](../../kgraph/examples/medlit/TODO.md) for LLM extraction details

---

### 4. Port Embedding Generation Logic to kgraph
**Status**: Not Started  
**Priority**: Medium  
**Component**: `kgraph/examples/medlit/pipeline/embeddings.py`

**Current State**:
- `SimpleMedLitEmbeddingGenerator` uses hash-based embeddings (placeholder)

**Action**:
- Port embedding generation from `ingest/embeddings_pipeline.py`
- Support BioBERT, SciBERT, OpenAI embeddings
- Add Ollama embedding support

**Reference**:
- `ingest/embeddings_pipeline.py` - Embedding generation pipeline
- `ingest/ollama_embedding_generator.py` - Ollama embedding implementation

---

## Enhancement Tasks

### 5. Improve Entity Resolution
**Status**: Not Started  
**Priority**: Medium

**Current State**:
- `MedLitEntityResolver` only uses canonical_id_hint from pre-extracted entities
- Creates provisional entities if no canonical ID found
- No embedding-based similarity matching

**Enhancements Needed**:
- Add embedding-based similarity matching
- Add external authority lookup (UMLS, HGNC, RxNorm APIs)
- Improve entity deduplication

**Reference**: See [kgraph TODO](../../kgraph/examples/medlit/TODO.md) for details

---

### 6. Add Comprehensive Tests
**Status**: Not Started  
**Priority**: Medium

**Current State**:
- Tests in `tests/` are tied to old architecture
- Need tests for kgraph pipeline components

**Action**:
- Rewrite tests for kgraph architecture
- Test entity extraction, resolution, relationship extraction
- Test bundle generation
- Test end-to-end ingestion flow

---

### 7. Update Documentation
**Status**: Not Started  
**Priority**: Low

**Current State**:
- Documentation in `docs/` reflects old architecture
- Need updates for kgraph/kgserver

**Action**:
- Update architecture docs for kgraph/kgserver
- Update user guides for new ingestion flow
- Document bundle format and usage

---

## Cleanup Tasks

### 8. Remove Obsolete Domain Models
**Status**: Pending  
**Priority**: Low

**Action**:
- Remove `entity.py`, `relationship.py`, `base.py` once migration verified
- Keep for reference during migration

---

### 9. Remove Obsolete Ingestion Pipeline
**Status**: Pending  
**Priority**: Low

**Action**:
- Remove `ingest/` directory once logic is ported to kgraph
- Keep for reference during migration

---

### 10. Remove Obsolete Tests
**Status**: Pending  
**Priority**: Low

**Action**:
- Remove `tests/` directory once kgraph tests are comprehensive
- Keep for reference during migration

---

## Priority Summary

**High Priority** (Enable core functionality):
1. Port NER extraction logic to kgraph
2. Port relationship extraction logic to kgraph

**Medium Priority** (Improve functionality):
3. Port PMC XML parser to kgraph
4. Port embedding generation logic to kgraph
5. Improve entity resolution
6. Add comprehensive tests

**Low Priority** (Cleanup):
7. Update documentation
8. Remove obsolete domain models
9. Remove obsolete ingestion pipeline
10. Remove obsolete tests

## References

- [kgraph med-lit extension](../../kgraph/examples/medlit/README.md)
- [kgraph med-lit TODO](../../kgraph/examples/medlit/TODO.md) - Detailed implementation guide
- [Migration guide](./MIGRATION_TO_KGRAPH.md)

# Medical Literature Domain Extension for kgraph

This package provides a kgraph domain extension for extracting knowledge from biomedical journal articles. It transforms med-lit-schema into a kgraph extension that produces bundles.

## Architecture

### Key Design Decisions

1. **Papers are NOT documents.jsonl**: Source papers are `JournalArticle(BaseDocument)` instances used for extraction, not documentation assets. The `documents.jsonl` in bundles is for human-readable documentation only.

2. **Canonical IDs**: Entities use authoritative identifiers (UMLS, HGNC, RxNorm, UniProt) directly in `entity_id`, with additional mappings in `canonical_ids`.

3. **Pattern A Relationships**: All medical predicates (TREATS, CAUSES, INCREASES_RISK, etc.) use a single `MedicalClaimRelationship` class. The `predicate` field distinguishes the relationship type.

4. **Rich Metadata**: Paper metadata (study type, sample size, MeSH terms) and extraction provenance are preserved in `BaseDocument.metadata` and `BaseRelationship.metadata`.

## Domain Components

### Documents

- **JournalArticle**: Maps from med-lit-schema's `Paper` to kgraph's `BaseDocument`
  - `paper_id` → `document_id` (prefer `doi:`, else `pmid:`, else `paper_id`)
  - `PaperMetadata` → `metadata` dict
  - `extraction_provenance` → `metadata["extraction"]`

### Entities

- **DiseaseEntity**: Uses UMLS IDs (e.g., `C0006142`)
- **GeneEntity**: Uses HGNC IDs (e.g., `HGNC:1100`)
- **DrugEntity**: Uses RxNorm IDs (e.g., `RxNorm:1187832`)
- **ProteinEntity**: Uses UniProt IDs (e.g., `P38398`)
- **SymptomEntity**, **ProcedureEntity**, **BiomarkerEntity**, **PathwayEntity**

### Relationships

- **MedicalClaimRelationship**: Single class for all medical predicates
  - Supports TREATS, CAUSES, INCREASES_RISK, ASSOCIATED_WITH, INTERACTS_WITH, etc.
  - Evidence and provenance stored in `metadata`
  - Multi-paper aggregation via `source_documents` tuple

### Domain Schema

- **MedLitDomainSchema**: Defines entity types, relationship types, document types
  - Promotion config: min_usage_count=2, min_confidence=0.75
  - Predicate validation via `get_valid_predicates()` (e.g., Drug→Disease supports TREATS)

## Pipeline Components

### Parser

- **JournalArticleParser**: Converts raw input (JSON, PMC XML) to `JournalArticle`
  - Supports JSON format (from med-lit-schema's Paper)
  - Supports PMC XML format (JATS XML parsing)

### Entity Extractor

- **MedLitEntityExtractor**: Extract entity mentions from journal articles
  - Currently extracts from pre-extracted entities in Paper JSON
  - TODO: Add NER model extraction (BioBERT, scispaCy, Ollama)

### Entity Resolver

- **MedLitEntityResolver**: Resolves mentions to canonical entities
  - Uses canonical_id_hint from pre-extracted entities
  - Creates canonical entities with authoritative IDs (UMLS, HGNC, etc.)
  - Creates provisional entities when no canonical ID available

### Relationship Extractor

- **MedLitRelationshipExtractor**: Extracts relationships with evidence
  - Currently extracts from pre-extracted relationships in Paper JSON
  - TODO: Add pattern-based and LLM-based extraction

### Embedding Generator

- **SimpleMedLitEmbeddingGenerator**: Hash-based embeddings (placeholder)
  - TODO: Add BioBERT, SciBERT, or OpenAI embeddings

## Usage

### Process Papers and Generate Bundle

```bash
cd /path/to/med-lit-schema
uv run python -m medlit_kgraph.scripts.ingest \
    --input-dir output/json_papers \
    --output-dir medlit_bundle \
    --content-type json
```

### Process PMC XML Files

```bash
uv run python -m medlit_kgraph.scripts.ingest \
    --input-dir ingest/pmc_xmls \
    --output-dir medlit_bundle \
    --content-type xml
```

### Load Bundle in kgserver

The generated bundle can be loaded by kgserver:

```bash
cd /path/to/kgserver
# Copy bundle to kgserver
cp -r /path/to/med-lit-schema/medlit_bundle /path/to/kgserver/bundles/

# Start kgserver (it will load the bundle automatically)
uvicorn main:app --reload
```

## Next Steps

See [TODO.md](../TODO.md) for remaining work:
1. Port NER extraction logic (BioBERT, scispaCy, Ollama)
2. Port relationship extraction logic (pattern-based, LLM)
3. Port embedding generation logic
4. Improve entity resolution with embedding similarity

## References

- [kgraph architecture](../../kgraph/docs/architecture.md)
- [kgraph domain extension guide](../../kgraph/docs/domains.md)
- [Sherlock example](../../kgraph/examples/sherlock/) - Reference implementation

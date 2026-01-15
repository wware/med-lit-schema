# Ingestion Pipeline Architecture

## Pipeline Execution

The `pipeline.sh` script is a **command generator** that emits shell commands to stdout. This allows you to:
- Preview commands before running
- Save to a file for editing (skip stages, modify parameters)
- Pipe directly to bash for execution

```bash
# Preview
bash ingest/pipeline.sh --storage sqlite

# Execute directly
bash ingest/pipeline.sh --storage sqlite | bash

# Save, edit, run
bash ingest/pipeline.sh --storage sqlite > my_run.sh
vim my_run.sh  # comment out stages you don't need
bash my_run.sh
```

## Block Diagram

```
┌─────────────┐    ┌──────────────┐    ┌─────────────┐    ┌──────────────┐
│  PubMed API │───▶│ Stage 1:     │───▶│ Stage 2:    │───▶│ PostgreSQL   │
│  (XML)      │    │ NER Pipeline │    │ Provenance  │    │ (Structured) │
└─────────────┘    │ (LLM)        │    │ Pipeline    │    └──────────────┘
                   └──────────────┘    └─────────────┘
                          │                    │
                          ▼                    ▼
                   ┌──────────────┐    ┌─────────────┐
                   │ JSONL Output │    │ Paper DB    │
                   │ (Edges)      │    │ (Metadata)  │
                   └──────────────┘    └─────────────┘
```

## Success Criteria

### Stage 1 (NER Pipeline - Entity & Edge Extraction)
**Input:** PMC XML files
**Output:** `output/extraction_edges.jsonl`

✅ **Success Conditions:**
1. Each line is valid JSON with required fields: `id`, `subject`, `object`, `provenance`, `extractor`, `confidence`
2. Entity references have: `id` (canonical format TYPE:name), `name`, `type`
3. Entity types MUST be valid (disease, drug, gene, protein, etc.)
4. Provenance includes: `source_type`, `source_id`
5. Extractor includes: `name`, `provider`
6. Confidence in range [0, 1]
7. No duplicate edge IDs

❌ **Failure Conditions:**
1. Malformed JSON
2. Missing required fields
3. Invalid entity types
4. Empty output for valid input
5. LLM timeout without retry

### Stage 2 (Provenance Pipeline)
**Input:** PMC XML files
**Output:** PostgreSQL/SQLite `papers` table

✅ **Success Conditions:**
1. Paper metadata extracted (title, authors, journal, dates)
2. Document structure preserved (sections, paragraphs)
3. PMC IDs properly linked

## Contract Tests

Contract tests validate pipeline outputs using Pydantic models:
- See `tests/test_ingestion_contracts.py`

Currently implemented:
- `EdgeContract` - validates `output/extraction_edges.jsonl`
- `EntityContract` - validates entity JSONL (future)

Run tests:
```bash
uv run pytest tests/test_ingestion_contracts.py -v
```

# Ingestion Pipeline

The ingestion process extracts structured knowledge from medical literature (PMC XML files).

## Overview

The pipeline extracts:

- **Entities:** Diseases, genes, drugs, proteins, and other biomedical entities
- **Relationships:** Semantic relationships (e.g., "Drug X treats Disease Y")
- **Evidence:** Quantitative metrics (sample sizes, p-values, etc.)
- **Papers:** Metadata and structure of source papers

## Pipeline Stages

| Stage | Script | Purpose |
|-------|--------|---------|
| 0 | `download_pipeline.py` | Download PMC XML files |
| 1 | `ner_pipeline.py` | Entity extraction (NER) |
| 2 | `provenance_pipeline.py` | Paper metadata and structure |
| 3 | `embeddings_pipeline.py` | Semantic embeddings (optional) |
| 4 | `claims_pipeline.py` | Relationship extraction |
| 5 | `evidence_pipeline.py` | Evidence metrics extraction |
| 6 | `graph_pipeline.py` | Knowledge graph construction |

## Quick Start

### Using pipeline.sh

The `pipeline.sh` script is a **command generator** - it emits shell commands to stdout.

```bash
# Preview commands
bash ingest/pipeline.sh --storage sqlite

# Run directly
bash ingest/pipeline.sh --storage sqlite | bash

# Save for editing
bash ingest/pipeline.sh --storage sqlite > run.sh
```

**Options:**

- `--skip-download` - Skip Stage 0 (use existing papers)
- `--no-ollama` - Exclude Ollama from Docker Compose
- `--storage sqlite|postgres` - Choose storage backend
- `--database-url URL` - PostgreSQL connection string
- `--xml-dir DIR` - PMC XML directory (default: `ingest/pmc_xmls`)
- `--output-dir DIR` - Output directory (default: `output`)

### Manual Execution

```bash
export DB_URL="postgresql://postgres:postgres@localhost:5432/medlit"

# Stage 0: Download papers
uv run python ingest/download_pipeline.py \
    --search "BRCA1 AND breast cancer" \
    --max-results 50 \
    --output-dir ingest/pmc_xmls

# Stage 1: Setup database
uv run python setup_database.py --database-url $DB_URL

# Stage 2: Extract metadata
uv run python ingest/provenance_pipeline.py \
    --input-dir ingest/pmc_xmls \
    --output-dir output \
    --storage postgres \
    --database-url $DB_URL

# Stage 3: Extract entities
uv run python ingest/ner_pipeline.py \
    --xml-dir ingest/pmc_xmls \
    --output-dir output \
    --storage postgres \
    --database-url $DB_URL

# Stage 4: Extract claims
uv run python ingest/claims_pipeline.py \
    --output-dir output \
    --storage postgres \
    --database-url $DB_URL

# Stage 5: Extract evidence
uv run python ingest/evidence_pipeline.py \
    --output-dir output \
    --storage postgres \
    --database-url $DB_URL

# Stage 6: Build graph
uv run python ingest/graph_pipeline.py \
    --output-dir output \
    --storage postgres \
    --database-url $DB_URL
```

## NER Backends

The NER pipeline supports multiple backends:

| Backend | Flag | Description |
|---------|------|-------------|
| biobert-fast | `--ner-backend biobert-fast` | Default. HuggingFace model |
| spacy | `--ner-backend spacy` | Fastest. Requires scispaCy |
| ollama | `--ner-backend ollama` | LLM-based extraction |
| biobert | `--ner-backend biobert` | Original BioBERT (slowest) |

**Multiprocessing:** Use `--workers N` for parallel processing (default: 4).

```bash
# Single-threaded (debugging)
uv run python ingest/ner_pipeline.py --workers 1 ...

# With Ollama LLM
uv run python ingest/ner_pipeline.py --ner-backend ollama --ollama-host http://localhost:11434 ...
```

## GPU Acceleration

For GPU acceleration with Lambda Labs or similar:

```bash
# Set Ollama host
export OLLAMA_HOST=http://<LAMBDA_IP>:11434

# Run without local Ollama
bash ingest/pipeline.sh --skip-download --no-ollama | bash
```

## Outputs

After running the pipeline:

**PostgreSQL:**

- `papers` table: Paper metadata with extraction provenance
- `entities` table: Canonical entities
- `relationships` table: Relationships/claims between entities
- `evidence` table: Quantitative evidence items

**JSONL files (output/):**

- `extraction_edges.jsonl`: NER extraction edges
- `extraction_provenance.json`: Detailed provenance tracking

## Known Limitations

### Evidence Extraction

The evidence pipeline may find zero quantitative evidence items. This is expected when processing abstracts only - statistical data is typically in Results sections of full papers.

### Relationship Embeddings (PostgreSQL)

Relationship embedding storage is not yet implemented for PostgreSQL. Use `--skip-embeddings` flag.

## Next Steps

- [Testing](testing.md) - Running and writing tests
- [Docker Setup](docker.md) - Docker Compose configuration

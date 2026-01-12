# Docker-Compose Setup Guide

This guide walks through setting up the complete docker-compose stack with persistent data
and running the ingestion pipeline.

## Prerequisites

- Docker and docker-compose installed
- `uv` installed for running Python commands
- PMC XML files in `ingest/download/pmc_xmls/` directory

## Step 1: Start the Docker Stack

Start all services (postgres, redis, ollama):

```bash
docker-compose up -d
```

Check that all services are running:

```bash
docker-compose ps
```

You should see `med-lit-postgres`, `med-lit-redis`, and `med-lit-ollama` all in "Up" state.

## Step 2: Pull the Ollama Embedding Model

Pull the nomic-embed-text model into the Ollama container:

```bash
docker exec -it med-lit-ollama ollama pull nomic-embed-text
```

This will download the model (may take a few minutes). Verify it's installed:

```bash
docker exec -it med-lit-ollama ollama list
```

## Step 3: Set Database URL

Set the PostgreSQL connection string as an environment variable:

```bash
export DB_URL="postgresql://postgres:postgres@localhost:5432/medlit"
```

Add this to your `~/.bashrc` or `~/.zshrc` to make it permanent.

## Step 4: Run the Ingestion Pipeline

Now run the 5-stage pipeline from NEXT_STEPS.md:

### Stage 1: Parse XML Files and Generate Provenance

```bash
uv run python ingest/provenance_pipeline.py \
  --input-dir ingest/download/pmc_xmls \
  --output-dir output
```

Creates:
- `output/provenance.db` - Paper metadata, sections, paragraphs
- `output/entities.db` - Entity collection

### Stage 2: Generate Embeddings

```bash
uv run python ingest/embeddings_pipeline.py \
  --output-dir output \
  --model nomic-embed-text
```

Generates embeddings for entities and paragraphs using local Ollama (via localhost:11434).

### Stage 3: Extract Biomedical Entities (NER)

```bash
uv run python ingest/ner_pipeline.py \
  --xml-dir ingest/download/pmc_xmls \
  --output-dir output \
  --storage postgres \
  --database-url $DB_URL
```

Extracts entities and stores them in PostgreSQL. Also creates:
- `output/extraction_edges.jsonl`
- `output/extraction_provenance.json`

### Stage 4: Extract Claims (Relationships)

```bash
uv run python ingest/claims_pipeline.py \
  --output-dir output \
  --storage postgres \
  --database-url $DB_URL
```

Extracts semantic relationships between entities.

### Stage 5: Extract Evidence

```bash
uv run python ingest/evidence_pipeline.py \
  --output-dir output \
  --storage postgres \
  --database-url $DB_URL
```

Extracts quantitative evidence supporting relationships.

## Data Persistence

All data is stored in Docker volumes on your local hard disk:

- **postgres-data**: PostgreSQL database (the final knowledge graph)
- **redis-data**: Redis cache
- **ollama-data**: Ollama models (nomic-embed-text)

These volumes persist even when containers are stopped. To view volumes:

```bash
docker volume ls | grep med-lit
```

To inspect a volume's location:

```bash
docker volume inspect med-lit-postgres_postgres-data
```

## Managing the Stack

**Stop services** (preserves data):
```bash
docker-compose down
```

**Start services** again:
```bash
docker-compose up -d
```

**View logs**:
```bash
docker-compose logs -f postgres
docker-compose logs -f ollama
```

**Reset everything** (destroys all data):
```bash
docker-compose down -v  # Warning: removes volumes!
```

## Optional: GUI Tools

Start pgAdmin (PostgreSQL GUI) and Redis Commander:

```bash
docker-compose --profile tools up -d
```

- **pgAdmin**: http://localhost:5050 (admin@medlit.local / admin)
- **Redis Commander**: http://localhost:8081

## Troubleshooting

**Ollama not responding:**
```bash
docker-compose logs ollama
docker exec -it med-lit-ollama ollama list
```

**PostgreSQL connection errors:**
```bash
docker-compose logs postgres
docker exec -it med-lit-postgres psql -U postgres -d medlit -c '\dt'
```

**Check service health:**
```bash
docker-compose ps
```

All services should show "healthy" in the status.

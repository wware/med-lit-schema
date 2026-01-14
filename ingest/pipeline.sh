#!/bin/bash -xe

# Stop any running containers
docker compose down

# Start Docker services (PostgreSQL & Redis)
docker compose up -d postgres redis ollama

# Wait for PostgreSQL to be ready
echo "Waiting for PostgreSQL to be ready..."
until docker exec med-lit-postgres pg_isready -U postgres; do
  echo "  Waiting for PostgreSQL..."
  sleep 2
done
echo "PostgreSQL is ready!"
echo ""

# Set your database URL (adjust user/password/host/port/database as needed)
export DB_URL="postgresql://postgres:postgres@localhost:5432/medlit"

# Stage 1: Setup PostgreSQL Database (creates tables)
uv run python setup_database.py --database-url $DB_URL

# Stage 2: Run Provenance Pipeline (to populate papers table in PostgreSQL)
uv run python ingest/provenance_pipeline.py --input-dir ingest/download/pmc_xmls --output-dir output --storage postgres \
    --database-url $DB_URL

# Stage 3: Extract entities (NER) and store in PostgreSQL
uv run python ingest/ner_pipeline.py --xml-dir ingest/download/pmc_xmls --output-dir output --storage postgres \
    --database-url $DB_URL --ollama-host "${OLLAMA_HOST:-http://localhost:11434}"

# Stage 4: Extract claims
uv run python ingest/claims_pipeline.py --output-dir output --storage postgres \
    --database-url $DB_URL --ollama-host "${OLLAMA_HOST:-http://localhost:11434}"
    # --skip-embeddings

# Stage 5: Extract evidence
uv run python ingest/evidence_pipeline.py --output-dir output --storage postgres \
    --database-url $DB_URL

# Stop Docker services
docker compose down

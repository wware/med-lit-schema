# Docker Setup

Docker Compose configuration for local development.

## Quick Start

```bash
# Start all services
docker compose up -d

# Start specific services
docker compose up -d postgres redis

# View logs
docker compose logs -f

# Stop services
docker compose down
```

## Services

### PostgreSQL + pgvector

Production-ready database with vector search support.

```yaml
postgres:
  image: pgvector/pgvector:pg16
  environment:
    POSTGRES_USER: postgres
    POSTGRES_PASSWORD: postgres
    POSTGRES_DB: medlit
  ports:
    - "5432:5432"
```

**Connection string:** `postgresql://postgres:postgres@localhost:5432/medlit`

### Redis

Caching and session storage.

```yaml
redis:
  image: redis:7-alpine
  ports:
    - "6379:6379"
```

### Ollama (Optional)

Local LLM for NER and embeddings.

```yaml
ollama:
  image: ollama/ollama
  ports:
    - "11434:11434"
  volumes:
    - ollama_data:/root/.ollama
```

**Setup models:**

```bash
docker compose exec ollama ollama pull nomic-embed-text
docker compose exec ollama ollama pull llama3.1:8b
```

### API Server

```yaml
api:
  build: .
  command: uvicorn query.server:app --host 0.0.0.0 --port 8000
  ports:
    - "8000:8000"
  environment:
    - DATABASE_URL=postgresql://postgres:postgres@postgres:5432/medlit
  depends_on:
    - postgres
```

## Development Workflow

### Initial Setup

```bash
# Start database
docker compose up -d postgres redis

# Wait for PostgreSQL
uv run python ingest/wait_for_postgres.py \
    --database-url postgresql://postgres:postgres@localhost:5432/medlit

# Initialize schema
uv run python setup_database.py \
    --database-url postgresql://postgres:postgres@localhost:5432/medlit
```

### Running the Pipeline

```bash
# With Docker Compose PostgreSQL
export DB_URL="postgresql://postgres:postgres@localhost:5432/medlit"
bash ingest/pipeline.sh --storage postgres | bash
```

### API Development

```bash
# Run API via Docker
docker compose up api

# Or run directly (faster iteration)
uv run uvicorn query.server:app --reload --port 8000
```

## GPU Acceleration (Lambda Labs)

For GPU-accelerated inference:

```bash
# Set remote Ollama host
export OLLAMA_HOST=http://<LAMBDA_IP>:11434

# Run without local Ollama
bash ingest/pipeline.sh --skip-download --no-ollama | bash
```

See `ingest/CLOUD_OLLAMA.md` for detailed Lambda Labs setup.

## Database Operations

### Reset Database

```bash
# Drop and recreate
dropdb medlit
createdb medlit

# Re-initialize
uv run python setup_database.py \
    --database-url postgresql://postgres:postgres@localhost:5432/medlit
```

### Connect via psql

```bash
docker compose exec postgres psql -U postgres -d medlit
```

### View Data

```sql
-- Count entities by type
SELECT entity_type, COUNT(*) FROM entities GROUP BY entity_type;

-- Count relationships by predicate
SELECT predicate, COUNT(*) FROM relationships GROUP BY predicate;

-- Recent papers
SELECT id, title FROM papers ORDER BY created_at DESC LIMIT 10;
```

## Troubleshooting

### PostgreSQL not ready

```bash
# Wait script
uv run python ingest/wait_for_postgres.py --database-url $DB_URL --timeout 60
```

### Port conflicts

```bash
# Check what's using a port
lsof -i :5432

# Use different ports in docker-compose.override.yml
```

### Volume cleanup

```bash
# Remove all volumes (data loss!)
docker compose down -v
```

## Next Steps

- [Ingestion Pipeline](ingestion.md) - Run the full pipeline
- [Architecture](architecture.md) - Understand the codebase

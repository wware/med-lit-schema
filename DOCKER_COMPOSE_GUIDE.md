# Docker Compose Setup - Quick Start Guide

This docker-compose configuration brings up PostgreSQL (with pgvector) and Redis for local development and testing.

## Quick Start

```bash
# Start both services
docker compose up -d

# Check status
docker compose ps

# View logs
docker compose logs -f

# Stop services
docker compose down

# Stop and remove volumes (destroys data)
docker compose down -v
```

## Services Included

### Core Services (Always Running)

1. **PostgreSQL with pgvector** (`postgres`)
   - Port: 5432
   - Database: medlit
   - User: postgres
   - Password: postgres
   - Connection string: `postgresql://postgres:postgres@localhost:5432/medlit`

2. **Redis** (`redis`)
   - Port: 6379
   - Persistence: Enabled (RDB + AOF)
   - Max memory: 2GB (with LRU eviction)
   - Connection string: `redis://localhost:6379/0`

### Optional Tools (Use with --profile tools)

3. **Redis Commander** (`redis-commander`)
   - Web UI for Redis management
   - URL: http://localhost:8081
   - Start with: `docker compose --profile tools up redis-commander -d`

4. **pgAdmin** (`pgadmin`)
   - Web UI for PostgreSQL management
   - URL: http://localhost:5050
   - Email: admin@medlit.local
   - Password: admin
   - Start with: `docker compose --profile tools up pgadmin -d`

## Usage Examples

### Initialize Database Schema

```bash
# Set environment variable
export DATABASE_URL="postgresql://postgres:postgres@localhost:5432/medlit"

# Run setup script
python setup_database.py
```

### Connect to PostgreSQL

```bash
# Using psql in the container
docker compose exec postgres psql -U postgres -d medlit

# From host (requires psql installed)
psql -h localhost -U postgres -d medlit

# Enable pgvector extension
docker compose exec postgres psql -U postgres -d medlit -c "CREATE EXTENSION IF NOT EXISTS vector;"
```

### Connect to Redis

```bash
# Using redis-cli in the container
docker compose exec redis redis-cli

# From host (requires redis-cli installed)
redis-cli -h localhost -p 6379

# Test connection
redis-cli ping
```

### Python Application Usage

```python
# PostgreSQL
from sqlalchemy import create_engine

DATABASE_URL = "postgresql://postgres:postgres@localhost:5432/medlit"
engine = create_engine(DATABASE_URL)

# Redis
import redis

redis_client = redis.from_url("redis://localhost:6379/0")
```

### Using Management Tools

Start Redis Commander and pgAdmin:

```bash
docker compose --profile tools up -d
```

Access:
- Redis Commander: http://localhost:8081
- pgAdmin: http://localhost:5050

To add PostgreSQL server in pgAdmin:
1. Open http://localhost:5050
2. Right-click "Servers" → "Register" → "Server"
3. General tab: Name = "Local MedLit"
4. Connection tab:
   - Host: postgres (or host.docker.internal on Mac/Windows)
   - Port: 5432
   - Database: medlit
   - Username: postgres
   - Password: postgres

## Data Persistence

Data is stored in named Docker volumes:
- `postgres-data`: PostgreSQL data
- `redis-data`: Redis persistence files
- `pgadmin-data`: pgAdmin configuration

### Backup Data

```bash
# Backup PostgreSQL
docker compose exec -T postgres pg_dump -U postgres medlit > backup.sql

# Backup Redis
docker compose exec redis redis-cli SAVE
docker compose cp redis:/data/dump.rdb ./redis-backup.rdb
```

### Restore Data

```bash
# Restore PostgreSQL
docker compose exec -T postgres psql -U postgres medlit < backup.sql

# Restore Redis
docker compose stop redis
docker compose cp ./redis-backup.rdb redis:/data/dump.rdb
docker compose start redis
```

### Reset Everything

```bash
# Stop and remove all data
docker compose down -v

# Start fresh
docker compose up -d
```

## Performance Tuning

### PostgreSQL

Edit `docker-compose.yml` to add PostgreSQL configuration:

```yaml
environment:
  POSTGRES_INITDB_ARGS: >-
    -c shared_buffers=256MB
    -c work_mem=16MB
    -c maintenance_work_mem=64MB
    -c effective_cache_size=1GB
```

Or create `postgresql.conf` and mount it:

```yaml
volumes:
  - ./postgresql.conf:/etc/postgresql/postgresql.conf
command: postgres -c config_file=/etc/postgresql/postgresql.conf
```

### Redis

Modify Redis command in `docker-compose.yml`:

```yaml
command: >
  redis-server
  --save 60 1
  --maxmemory 4gb
  --maxmemory-policy allkeys-lru
```

## Troubleshooting

### Port Already in Use

If ports 5432 or 6379 are already taken:

```yaml
# Change port mappings
ports:
  - "5433:5432"  # Map to different host port
  - "6380:6379"
```

### Can't Connect from Host

Make sure services are running:

```bash
docker compose ps
docker compose logs postgres
docker compose logs redis
```

### Reset Corrupted Data

```bash
docker compose down -v
docker volume rm med-lit-schema_postgres-data med-lit-schema_redis-data
docker compose up -d
```

### Check Resource Usage

```bash
docker stats
```

## Environment-Specific Overrides

Create `docker-compose.override.yml` for local customizations:

```yaml
# docker-compose.override.yml
version: '3.8'

services:
  postgres:
    environment:
      POSTGRES_PASSWORD: my-secure-password
    
  redis:
    command: redis-server --maxmemory 4gb
```

This file is automatically loaded and won't be committed to git.

## Integration Testing

Run tests against these containers:

```python
import pytest
from sqlalchemy import create_engine
import redis

@pytest.fixture(scope="session")
def db_engine():
    """Provide database engine for tests"""
    engine = create_engine(
        "postgresql://postgres:postgres@localhost:5432/medlit"
    )
    yield engine
    engine.dispose()

@pytest.fixture(scope="session")
def redis_client():
    """Provide Redis client for tests"""
    client = redis.from_url("redis://localhost:6379/0")
    yield client
    client.flushdb()  # Clean up after tests
    client.close()

def test_entity_storage(db_engine, redis_client):
    # Your tests here
    pass
```

## Production Notes

This setup is for **development/testing only**. For production:

1. **Change passwords** - Don't use default credentials
2. **Use secrets management** - AWS Secrets Manager, HashiCorp Vault
3. **Enable SSL/TLS** - Encrypt data in transit
4. **Configure backups** - Automated daily backups
5. **Set resource limits** - Memory and CPU constraints
6. **Use managed services** - RDS, ElastiCache for production
7. **Monitor everything** - CloudWatch, Prometheus, Grafana

## Additional Commands

```bash
# View container logs
docker compose logs -f postgres
docker compose logs -f redis

# Restart a service
docker compose restart postgres

# Stop a specific service
docker compose stop redis

# Execute commands in containers
docker compose exec postgres psql -U postgres -c "SELECT version();"
docker compose exec redis redis-cli INFO server

# Scale services (for load testing)
docker compose up -d --scale redis=3

# Pull latest images
docker compose pull

# Rebuild containers
docker compose up -d --build
```

## Next Steps

1. Initialize the database schema: `python setup_database.py`
2. Run tests: `pytest tests/`
3. Start your application

## Support

For issues or questions:
- PostgreSQL: Check logs with `docker compose logs postgres`
- Redis: Check logs with `docker compose logs redis`
- Network: Verify with `docker network ls` and `docker network inspect`

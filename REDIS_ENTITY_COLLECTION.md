# Redis EntityCollection Setup Guide

This guide covers setting up Redis for the EntityCollection - the canonical registry of medical entities used for entity resolution and linking.

## Overview

Redis provides fast key-value storage for the EntityCollection, enabling:
- Sub-millisecond entity lookups by ID
- Fast synonym and abbreviation matching
- Efficient entity resolution during paper processing
- Optional persistence for durability

## Why Redis for EntityCollection?

**Use Cases:**
- Entity ID resolution (map mentions → canonical IDs)
- Fast lookups during ingestion pipeline (millions of entities)
- Caching embeddings for semantic search
- Session storage for entity linking workflows

**Trade-offs vs PostgreSQL:**
- ✅ **Faster**: 100x faster for simple key-value lookups
- ✅ **Simpler**: No schema migrations, just key-value pairs
- ❌ **Less queryable**: No complex joins or relationships
- ❌ **More memory**: Entire dataset must fit in RAM

**Decision Guide:**
- Use **Redis** for: EntityCollection, entity ID lookups, caching
- Use **PostgreSQL** for: Relationships, provenance, complex queries

## Local Development with Docker

### Basic Docker Run Command

```bash
docker run -d \
  --name med-lit-redis \
  -p 6379:6379 \
  redis:7-alpine
```

### With Persistence (Recommended)

Redis can persist data to disk using RDB snapshots or AOF (Append-Only File).

#### RDB Snapshots (Default)

```bash
docker run -d \
  --name med-lit-redis \
  -p 6379:6379 \
  -v med-lit-redis-data:/data \
  redis:7-alpine redis-server --save 60 1 --loglevel warning
```

**Explanation:**
- `--save 60 1`: Save snapshot if at least 1 key changed in 60 seconds
- Default snapshots: Every 60s if ≥1 change, 300s if ≥10, 900s if ≥10000
- Data saved to `/data` (mapped to named volume)

#### AOF (Append-Only File) for Maximum Durability

```bash
docker run -d \
  --name med-lit-redis \
  -p 6379:6379 \
  -v med-lit-redis-data:/data \
  redis:7-alpine redis-server --appendonly yes --appendfsync everysec
```

**Explanation:**
- `--appendonly yes`: Enable AOF
- `--appendfsync everysec`: Sync to disk every second (good balance)
- Alternative: `--appendfsync always` (slower, max durability)

### With Redis Configuration File

For more control, use a custom redis.conf:

```bash
# Create redis.conf
cat > redis.conf << 'EOF'
# Network
bind 0.0.0.0
port 6379
timeout 300

# Persistence
save 900 1
save 300 10
save 60 10000
appendonly yes
appendfsync everysec

# Memory
maxmemory 2gb
maxmemory-policy allkeys-lru

# Performance
tcp-backlog 511
tcp-keepalive 300
EOF

# Run with custom config
docker run -d \
  --name med-lit-redis \
  -p 6379:6379 \
  -v $(pwd)/redis.conf:/usr/local/etc/redis/redis.conf \
  -v med-lit-redis-data:/data \
  redis:7-alpine redis-server /usr/local/etc/redis/redis.conf
```

### Connecting to Redis

```bash
# Using redis-cli in the container
docker exec -it med-lit-redis redis-cli

# Or connect from your host (requires redis-cli installed)
redis-cli -h localhost -p 6379

# Test connection
redis-cli ping
# Should return: PONG
```

### Docker Compose Setup (Recommended)

```yaml
# docker-compose.yml
version: '3.8'

services:
  redis:
    image: redis:7-alpine
    container_name: med-lit-redis
    ports:
      - "6379:6379"
    volumes:
      - redis-data:/data
      - ./redis.conf:/usr/local/etc/redis/redis.conf
    command: redis-server /usr/local/etc/redis/redis.conf
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 10s
      timeout: 5s
      retries: 5
    restart: unless-stopped

volumes:
  redis-data:
```

Run with:
```bash
docker compose up -d
```

## Python EntityCollection Implementation

### Basic Redis-backed EntityCollection

```python
import redis
import json
from typing import Optional
from pydantic import BaseModel

class EntityCollection:
    """Redis-backed entity collection for fast lookups"""

    def __init__(self, redis_url: str = "redis://localhost:6379/0"):
        self.redis = redis.from_url(redis_url, decode_responses=True)

    def add_entity(self, entity: BaseModel) -> None:
        """Add an entity to the collection"""
        entity_dict = entity.model_dump()
        entity_id = entity_dict['entity_id']

        # Store main entity record
        self.redis.set(
            f"entity:{entity_id}",
            json.dumps(entity_dict)
        )

        # Index by entity type
        entity_type = entity.__class__.__name__
        self.redis.sadd(f"type:{entity_type}", entity_id)

        # Index synonyms for fast lookup
        for synonym in entity_dict.get('synonyms', []):
            self.redis.sadd(f"synonym:{synonym.lower()}", entity_id)

        # Index by ontology IDs (UMLS, HGNC, etc.)
        for ont_type in ['umls_id', 'hgnc_id', 'rxnorm_id', 'uniprot_id']:
            ont_id = entity_dict.get(ont_type)
            if ont_id:
                self.redis.set(f"{ont_type}:{ont_id}", entity_id)

    def get_by_id(self, entity_id: str) -> Optional[dict]:
        """Retrieve entity by canonical ID"""
        data = self.redis.get(f"entity:{entity_id}")
        return json.loads(data) if data else None

    def get_by_umls(self, umls_id: str) -> Optional[dict]:
        """Retrieve entity by UMLS ID"""
        entity_id = self.redis.get(f"umls_id:{umls_id}")
        return self.get_by_id(entity_id) if entity_id else None

    def resolve_mention(self, mention: str) -> Optional[str]:
        """Resolve a text mention to canonical entity ID"""
        # Try exact synonym match
        entity_ids = self.redis.smembers(f"synonym:{mention.lower()}")
        if entity_ids:
            return list(entity_ids)[0]  # Return first match

        # Could add fuzzy matching or embedding search here
        return None

    def get_entities_by_type(self, entity_type: str) -> list[str]:
        """Get all entity IDs of a given type"""
        return list(self.redis.smembers(f"type:{entity_type}"))

    def count_entities(self) -> int:
        """Total number of entities"""
        return len(self.redis.keys("entity:*"))


# Example usage
from schema.entity import Disease, Gene, InMemoryEntityCollection

collection = InMemoryEntityCollection()

# Add entities
collection.add_entity(Disease(
    entity_id="C0006142",
    name="Breast Cancer",
    synonyms=["Breast Carcinoma", "BC"],
    umls_id="C0006142"
))

collection.add_entity(Gene(
    entity_id="HGNC:1100",
    name="BRCA1",
    synonyms=["breast cancer 1"],
    hgnc_id="HGNC:1100"
))

# Retrieve by ID
entity = collection.get_by_id("C0006142")

# Resolve mention
entity_id = collection.resolve_mention("BC")  # → C0006142

# Get all diseases
diseases = collection.get_entities_by_type("Disease")
```

### Advanced: With Embeddings for Semantic Search

```python
import numpy as np
from redis.commands.search.field import VectorField, TextField, TagField
from redis.commands.search.indexer import IndexDefinition, IndexType
from redis.commands.search.query import Query

class EntityCollectionWithSearch(EntityCollection):
    """Redis-backed collection with vector similarity search"""

    def __init__(self, redis_url: str = "redis://localhost:6379/0"):
        super().__init__(redis_url)
        self._create_search_index()

    def _create_search_index(self):
        """Create RediSearch index for vector similarity"""
        try:
            # Create index for vector search
            self.redis.ft("entities").create_index([
                TextField("name"),
                TagField("entity_type"),
                VectorField("embedding",
                    "FLAT",
                    {
                        "TYPE": "FLOAT32",
                        "DIM": 768,  # Adjust to your embedding size
                        "DISTANCE_METRIC": "COSINE"
                    }
                )
            ],
            definition=IndexDefinition(prefix=["entity:"], index_type=IndexType.HASH)
            )
        except Exception as e:
            # Index might already exist
            pass

    def add_entity_with_embedding(self, entity: BaseModel, embedding: np.ndarray):
        """Add entity with vector embedding"""
        self.add_entity(entity)

        # Store embedding for vector search
        entity_id = entity.entity_id
        self.redis.hset(
            f"entity:{entity_id}",
            mapping={
                "embedding": embedding.astype(np.float32).tobytes()
            }
        )

    def semantic_search(self, query_embedding: np.ndarray, k: int = 5):
        """Find k most similar entities by embedding"""
        query = (
            Query(f"*=>[KNN {k} @embedding $vec AS score]")
            .return_fields("entity_id", "name", "score")
            .sort_by("score")
            .dialect(2)
        )

        result = self.redis.ft("entities").search(
            query,
            query_params={
                "vec": query_embedding.astype(np.float32).tobytes()
            }
        )

        return [
            {
                "entity_id": doc.entity_id,
                "name": doc.name,
                "score": float(doc.score)
            }
            for doc in result.docs
        ]
```

## AWS Production Deployment

### ElastiCache for Redis

AWS ElastiCache provides managed Redis with automatic failover, backups, and scaling.

#### Creating ElastiCache Cluster

**Via AWS Console:**

1. Navigate to ElastiCache → Redis clusters → Create
2. Choose cluster mode:
   - **Disabled** (simpler, single primary)
   - **Enabled** (sharded, for >100GB data)
3. Select Redis version 7.0 or later
4. Choose node type:
   - Development: cache.t3.micro (0.5 GB RAM)
   - Production: cache.r6g.large (13.07 GB RAM)
5. Set number of replicas (recommend 1-2 for HA)
6. Configure VPC, subnet group, security group
7. Enable encryption in transit (TLS)
8. Enable automatic backups
9. Create cluster

**Via AWS CLI:**

```bash
aws elasticache create-replication-group \
  --replication-group-id med-lit-redis \
  --replication-group-description "Medical Literature Entity Collection" \
  --engine redis \
  --engine-version 7.0 \
  --cache-node-type cache.r6g.large \
  --num-cache-clusters 2 \
  --automatic-failover-enabled \
  --multi-az-enabled \
  --cache-subnet-group-name my-subnet-group \
  --security-group-ids sg-xxxxx \
  --at-rest-encryption-enabled \
  --transit-encryption-enabled \
  --snapshot-retention-limit 7 \
  --snapshot-window "03:00-05:00" \
  --preferred-maintenance-window "sun:05:00-sun:07:00" \
  --tags Key=Project,Value=MedLit Key=Environment,Value=Production
```

#### Security Configuration

**Security Group Rules:**

```bash
# Allow Redis from application tier
aws ec2 authorize-security-group-ingress \
  --group-id sg-xxxxx \
  --protocol tcp \
  --port 6379 \
  --source-group sg-app-tier
```

**Best Practices:**
- Never expose ElastiCache to public internet
- Use VPC and security groups for network isolation
- Enable encryption in transit (TLS)
- Enable encryption at rest
- Use IAM authentication where possible

#### Connection from Application

```python
import redis
import boto3
import json

def get_redis_endpoint(cluster_id: str, region: str = 'us-east-1'):
    """Get ElastiCache endpoint from AWS"""
    client = boto3.client('elasticache', region_name=region)

    response = client.describe_replication_groups(
        ReplicationGroupId=cluster_id
    )

    # Get primary endpoint
    endpoint = response['ReplicationGroups'][0]['NodeGroups'][0]['PrimaryEndpoint']

    return {
        'host': endpoint['Address'],
        'port': endpoint['Port']
    }

# Get endpoint
endpoint = get_redis_endpoint('med-lit-redis')

# Connect with TLS
redis_client = redis.Redis(
    host=endpoint['host'],
    port=endpoint['port'],
    ssl=True,
    ssl_cert_reqs='required',
    decode_responses=True,
    socket_connect_timeout=5,
    socket_keepalive=True,
    health_check_interval=30
)

# Use with EntityCollection
collection = EntityCollection(
    redis_url=f"rediss://{endpoint['host']}:{endpoint['port']}/0"
)
```

#### Monitoring and Performance

**CloudWatch Metrics to Monitor:**
- `CPUUtilization` - Keep under 90%
- `DatabaseMemoryUsagePercentage` - Monitor memory pressure
- `EngineCPUUtilization` - Redis-specific CPU
- `CacheHits` / `CacheMisses` - Hit ratio should be >90%
- `NetworkBytesIn` / `NetworkBytesOut`
- `ReplicationLag` - For replicas

**Set Up Alarms:**

```bash
# High memory usage alarm
aws cloudwatch put-metric-alarm \
  --alarm-name medlit-redis-high-memory \
  --alarm-description "Redis memory usage above 80%" \
  --metric-name DatabaseMemoryUsagePercentage \
  --namespace AWS/ElastiCache \
  --statistic Average \
  --period 300 \
  --threshold 80 \
  --comparison-operator GreaterThanThreshold \
  --evaluation-periods 2 \
  --dimensions Name=CacheClusterId,Value=med-lit-redis-001
```

#### Backup and Disaster Recovery

**Automated Backups:**

ElastiCache automatically creates daily snapshots:

```bash
# View snapshots
aws elasticache describe-snapshots \
  --replication-group-id med-lit-redis

# Manual snapshot
aws elasticache create-snapshot \
  --replication-group-id med-lit-redis \
  --snapshot-name medlit-manual-snapshot-$(date +%Y%m%d)
```

**Restore from Snapshot:**

```bash
aws elasticache create-replication-group \
  --replication-group-id med-lit-redis-restored \
  --replication-group-description "Restored from snapshot" \
  --snapshot-name medlit-manual-snapshot-20260106 \
  --cache-node-type cache.r6g.large \
  --engine redis
```

**Cross-Region Replication:**

For disaster recovery:

```bash
# Create global datastore (Redis 5.0.6+)
aws elasticache create-global-replication-group \
  --global-replication-group-id-suffix medlit-global \
  --primary-replication-group-id med-lit-redis \
  --global-replication-group-description "Global entity collection"

# Add secondary region
aws elasticache create-replication-group \
  --replication-group-id med-lit-redis-eu \
  --replication-group-description "EU replica" \
  --global-replication-group-id medlit-global \
  --region eu-west-1
```

#### Scaling Strategies

**Vertical Scaling (Node Size):**

```bash
# Modify node type
aws elasticache modify-replication-group \
  --replication-group-id med-lit-redis \
  --cache-node-type cache.r6g.xlarge \
  --apply-immediately
```

**Horizontal Scaling (Add Replicas):**

```bash
# Increase replica count
aws elasticache increase-replica-count \
  --replication-group-id med-lit-redis \
  --new-replica-count 2 \
  --apply-immediately
```

**Cluster Mode (Sharding):**

For datasets >100 GB, use cluster mode:

```bash
aws elasticache create-replication-group \
  --replication-group-id med-lit-redis-cluster \
  --replication-group-description "Sharded cluster" \
  --engine redis \
  --cache-node-type cache.r6g.large \
  --num-node-groups 3 \
  --replicas-per-node-group 1 \
  --cache-parameter-group-name default.redis7.cluster.on
```

**Connection Pooling:**

```python
import redis.connection

# Configure connection pool
pool = redis.ConnectionPool(
    host=endpoint['host'],
    port=endpoint['port'],
    max_connections=50,
    socket_connect_timeout=5,
    socket_keepalive=True,
    ssl=True
)

redis_client = redis.Redis(connection_pool=pool)
```

### Cost Optimization

**Recommendations:**
1. Use Reserved Nodes for production (up to 55% savings)
2. Right-size instances (monitor memory usage)
3. Use Graviton2 instances (r6g family) for 35% better price/performance
4. Reduce snapshot retention if not needed
5. Use cluster mode only if data >100 GB

**Estimated Monthly Costs (us-east-1):**
- cache.t3.micro (0.5 GB): ~$12/month
- cache.r6g.large (13 GB): ~$110/month (on-demand), ~$70/month (1-year RI)
- cache.r6g.xlarge (26 GB): ~$220/month (on-demand)
- Backup storage: $0.085/GB/month

### MemoryDB for Redis Alternative

For applications requiring strong consistency and durability:

```bash
aws memorydb create-cluster \
  --cluster-name med-lit-memorydb \
  --node-type db.r6g.large \
  --num-shards 1 \
  --num-replicas-per-shard 1 \
  --subnet-group-name my-subnet-group \
  --security-group-ids sg-xxxxx \
  --tls-enabled \
  --snapshot-retention-limit 7
```

**MemoryDB vs ElastiCache:**
- ✅ **Durable**: All data persisted to disk (multi-AZ transaction log)
- ✅ **Consistent**: Strong consistency guarantees
- ❌ **More expensive**: ~2x cost of ElastiCache
- ❌ **Newer**: Less battle-tested than ElastiCache

**When to use MemoryDB:**
- Critical data that can't be lost
- Need strong consistency (not eventual)
- Primary data store (not just cache)

**When to use ElastiCache:**
- Caching layer (data can be regenerated)
- High performance > durability
- Cost-sensitive applications

## Data Loading Strategy

### Initial Population

```python
import json
from schema.entity import Disease, Gene, Drug
from typing import Iterator

def load_entities_from_jsonl(filepath: str) -> Iterator[dict]:
    """Stream entities from JSONL file"""
    with open(filepath, 'r') as f:
        for line in f:
            yield json.loads(line)

def populate_redis(collection, entities_file: str):
    """Bulk load entities into Redis"""
    # Use pipeline for batch writes
    pipe = collection.redis.pipeline()

    count = 0
    for entity_dict in load_entities_from_jsonl(entities_file):
        # Determine entity type and create appropriate object
        entity_type = entity_dict['entity_type']
        if entity_type == 'Disease':
            entity = Disease(**entity_dict)
        elif entity_type == 'Gene':
            entity = Gene(**entity_dict)
        # ... etc

        # Add to pipeline
        collection.add_entity(entity)

        count += 1
        if count % 1000 == 0:
            pipe.execute()  # Execute batch
            print(f"Loaded {count} entities...")

    pipe.execute()  # Final batch
    print(f"Total loaded: {count} entities")

# Usage
from schema.entity import InMemoryEntityCollection

collection = InMemoryEntityCollection()
populate_redis(collection, 'entities.jsonl')
```

### Ongoing Updates

For production, sync from authoritative source (S3):

```python
import boto3

def sync_from_s3(bucket: str, key: str, collection):
    """Download latest entity collection from S3 and load to Redis"""
    s3 = boto3.client('s3')

    # Download file
    s3.download_file(bucket, key, '/tmp/entities.jsonl')

    # Clear existing data (careful!)
    collection.redis.flushdb()

    # Load new data
    populate_redis(collection, '/tmp/entities.jsonl')

# Run daily or on-demand
sync_from_s3('med-lit-artifacts', 'entity-collections/v2/entities.jsonl', collection)
```

## Hybrid Architecture: Redis + PostgreSQL

**Best Practice:** Use both together

```
┌─────────────────────────────────────────────────────┐
│                 Application Layer                   │
└──────────────┬────────────────────┬─────────────────┘
               │                    │
               ▼                    ▼
      ┌─────────────────┐   ┌────────────────────┐
      │     Redis       │   │    PostgreSQL      │
      │ (EntityColln)   │   │ (Relationships)    │
      ├─────────────────┤   ├────────────────────┤
      │ • Entity lookup │   │ • Relationships    │
      │ • Caching       │   │ • Provenance       │
      │ • Resolution    │   │ • Evidence         │
      │ • Fast reads    │   │ • Complex queries  │
      └─────────────────┘   └────────────────────┘
```

**Workflow:**
1. Load canonical entities into Redis (fast lookup)
2. Store relationships in PostgreSQL (queryability)
3. During ingestion:
   - Use Redis to resolve mentions → canonical IDs
   - Store relationships in PostgreSQL with those IDs

**Benefits:**
- Redis handles high-throughput entity resolution
- PostgreSQL handles complex analytical queries
- Each system optimized for its use case

## Troubleshooting

### Common Issues

**Connection refused:**
```bash
# Check Redis is running
docker ps | grep redis

# Test connection
redis-cli -h localhost -p 6379 ping
```

**Out of memory:**
```redis
# Check memory usage
INFO memory

# Check maxmemory policy
CONFIG GET maxmemory-policy

# Set eviction policy (for cache use)
CONFIG SET maxmemory-policy allkeys-lru
```

**Slow performance:**
```redis
# Check slow queries
SLOWLOG GET 10

# Monitor commands in real-time
MONITOR  # (use sparingly in production)

# Check latency
redis-cli --latency
```

### Useful Redis Commands

```bash
# Entity lookup
GET entity:C0006142

# Count entities
DBSIZE

# Find all diseases
SMEMBERS type:Disease

# Check synonym index
SMEMBERS synonym:bc

# Memory usage of specific key
MEMORY USAGE entity:C0006142

# Export all data
redis-cli --rdb /tmp/dump.rdb
```

## Migration Strategy

### Moving from local to AWS ElastiCache

```bash
# 1. Create snapshot of local Redis
redis-cli --rdb /tmp/redis_snapshot.rdb

# 2. Upload to S3
aws s3 cp /tmp/redis_snapshot.rdb s3://my-bucket/redis-backup/

# 3. Create ElastiCache cluster from S3 snapshot
aws elasticache create-replication-group \
  --replication-group-id med-lit-redis \
  --snapshot-arns arn:aws:s3:::my-bucket/redis-backup/redis_snapshot.rdb \
  --cache-node-type cache.r6g.large \
  ...

# 4. Update application to use ElastiCache endpoint
```

## Additional Resources

- [Redis Documentation](https://redis.io/docs/)
- [AWS ElastiCache for Redis](https://docs.aws.amazon.com/AmazonElastiCache/latest/red-ug/WhatIs.html)
- [redis-py Documentation](https://redis-py.readthedocs.io/)
- [RediSearch Documentation](https://redis.io/docs/stack/search/)
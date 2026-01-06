# Database Setup Guide

This guide covers setting up PostgreSQL with pgvector extension for the medical literature knowledge graph.

## Overview

The schema uses PostgreSQL with the pgvector extension to support:
- Relational data for entities and relationships
- Vector similarity search for embeddings
- JSONB fields for flexible metadata storage

## Local Development with Docker

### Prerequisites

- Docker installed on your machine
- Python 3.11+ with uv or pip

### Running PostgreSQL with pgvector

The pgvector extension enables vector similarity search for entity embeddings and semantic queries.

#### Basic Docker Run Command

```bash
docker run -d \
  --name med-lit-postgres \
  -e POSTGRES_PASSWORD=postgres \
  -e POSTGRES_USER=postgres \
  -e POSTGRES_DB=medlit \
  -p 5432:5432 \
  pgvector/pgvector:pg16
```

#### With Persistent Storage

For development work where you want to preserve data between container restarts:

```bash
docker run -d \
  --name med-lit-postgres \
  -e POSTGRES_PASSWORD=postgres \
  -e POSTGRES_USER=postgres \
  -e POSTGRES_DB=medlit \
  -p 5432:5432 \
  -v med-lit-pgdata:/var/lib/postgresql/data \
  pgvector/pgvector:pg16
```

#### Environment Variables Explained

- `POSTGRES_PASSWORD`: Database superuser password (change in production!)
- `POSTGRES_USER`: Database superuser username
- `POSTGRES_DB`: Default database name to create
- `-p 5432:5432`: Maps container port 5432 to host port 5432
- `-v med-lit-pgdata:/var/lib/postgresql/data`: Named volume for data persistence

### Connecting to the Database

Once the container is running:

```bash
# Using psql directly in the container
docker exec -it med-lit-postgres psql -U postgres -d medlit

# Or connect from your host machine
psql -h localhost -U postgres -d medlit
```

### Initialize the Schema

```bash
# Set connection string
export DATABASE_URL="postgresql://postgres:postgres@localhost:5432/medlit"

# Run the setup script
python setup_database.py
```

### Docker Compose Setup (Alternative)

For a more reproducible development environment:

```yaml
# docker-compose.yml
version: '3.8'

services:
  postgres:
    image: pgvector/pgvector:pg16
    container_name: med-lit-postgres
    environment:
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: postgres
      POSTGRES_DB: medlit
    ports:
      - "5432:5432"
    volumes:
      - pgdata:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U postgres"]
      interval: 10s
      timeout: 5s
      retries: 5

volumes:
  pgdata:
```

Run with:
```bash
docker compose up -d
```

## AWS Production Deployment

### RDS PostgreSQL with pgvector

AWS RDS supports pgvector extension on PostgreSQL 15.2+ and 16.1+.

#### Creating RDS Instance

**Via AWS Console:**

1. Navigate to RDS → Create database
2. Choose PostgreSQL
3. Select version 16.1 or later (pgvector support)
4. Choose instance size:
   - Development: db.t3.medium (2 vCPU, 4 GB RAM)
   - Production: db.r6g.xlarge (4 vCPU, 32 GB RAM) or larger
5. Configure storage:
   - General Purpose SSD (gp3) recommended
   - Enable autoscaling for production (suggest 100-500 GB initial, scale to 1 TB)
6. Set master username and password
7. Configure VPC, subnet group, and security group
8. Enable automated backups (7-35 days retention)
9. Create database

**Via AWS CLI:**

```bash
aws rds create-db-instance \
  --db-instance-identifier med-lit-postgres \
  --db-instance-class db.r6g.xlarge \
  --engine postgres \
  --engine-version 16.1 \
  --master-username postgres \
  --master-user-password <your-secure-password> \
  --allocated-storage 100 \
  --storage-type gp3 \
  --storage-encrypted \
  --vpc-security-group-ids sg-xxxxx \
  --db-subnet-group-name my-subnet-group \
  --backup-retention-period 7 \
  --preferred-backup-window "03:00-04:00" \
  --preferred-maintenance-window "sun:04:00-sun:05:00" \
  --enable-cloudwatch-logs-exports '["postgresql"]' \
  --tags Key=Project,Value=MedLit Key=Environment,Value=Production
```

#### Enabling pgvector Extension

After RDS instance is available:

```sql
-- Connect to your RDS instance
psql -h <rds-endpoint> -U postgres -d medlit

-- Enable the extension (requires rds_superuser role)
CREATE EXTENSION IF NOT EXISTS vector;

-- Verify installation
SELECT * FROM pg_extension WHERE extname = 'vector';
```

#### Security Configuration

**Security Group Rules:**

```bash
# Allow PostgreSQL from application tier
aws ec2 authorize-security-group-ingress \
  --group-id sg-xxxxx \
  --protocol tcp \
  --port 5432 \
  --source-group sg-app-tier

# For VPN/bastion access (temporary development)
aws ec2 authorize-security-group-ingress \
  --group-id sg-xxxxx \
  --protocol tcp \
  --port 5432 \
  --cidr 10.0.0.0/16
```

**Best Practices:**
- Never expose RDS to 0.0.0.0/0 (public internet)
- Use security groups to restrict access to application tier
- Enable SSL/TLS for all connections
- Store credentials in AWS Secrets Manager

#### Connection from Application

**Using Secrets Manager:**

```python
import boto3
import json
from sqlalchemy import create_engine

def get_db_credentials(secret_name: str, region: str = 'us-east-1'):
    """Retrieve database credentials from Secrets Manager"""
    client = boto3.client('secretsmanager', region_name=region)
    response = client.get_secret_value(SecretId=secret_name)
    return json.loads(response['SecretString'])

# Get credentials
creds = get_db_credentials('medlit/postgres/prod')

# Build connection string
DATABASE_URL = (
    f"postgresql://{creds['username']}:{creds['password']}"
    f"@{creds['host']}:{creds['port']}/{creds['dbname']}"
    "?sslmode=require"
)

# Create SQLAlchemy engine
engine = create_engine(
    DATABASE_URL,
    pool_size=10,
    max_overflow=20,
    pool_pre_ping=True,  # Verify connections before using
    pool_recycle=3600    # Recycle connections every hour
)
```

**Environment Variables (for Lambda/ECS):**

```bash
export DB_HOST=medlit-postgres.xxxxx.us-east-1.rds.amazonaws.com
export DB_PORT=5432
export DB_NAME=medlit
export DB_USER=postgres
export DB_PASSWORD_SECRET_ARN=arn:aws:secretsmanager:us-east-1:xxxxx:secret:medlit-xxxxx
```

#### Monitoring and Performance

**CloudWatch Metrics to Monitor:**
- `CPUUtilization` - Keep under 80%
- `DatabaseConnections` - Monitor connection pool usage
- `FreeableMemory` - Should not drop too low
- `ReadLatency` / `WriteLatency` - Track query performance
- `NetworkReceiveThroughput` / `NetworkTransmitThroughput`

**Performance Insights:**
Enable RDS Performance Insights for query-level monitoring:

```bash
aws rds modify-db-instance \
  --db-instance-identifier med-lit-postgres \
  --enable-performance-insights \
  --performance-insights-retention-period 7
```

#### Backup and Disaster Recovery

**Automated Backups:**
- Enabled by default with 7-day retention
- Point-in-time recovery available
- Backups stored in S3 (encrypted)

**Manual Snapshots:**

```bash
# Create snapshot
aws rds create-db-snapshot \
  --db-instance-identifier med-lit-postgres \
  --db-snapshot-identifier medlit-manual-snapshot-$(date +%Y%m%d)

# Restore from snapshot
aws rds restore-db-instance-from-db-snapshot \
  --db-instance-identifier med-lit-postgres-restored \
  --db-snapshot-identifier medlit-manual-snapshot-20260106
```

**Cross-Region Replication:**

For disaster recovery, set up a read replica in another region:

```bash
aws rds create-db-instance-read-replica \
  --db-instance-identifier med-lit-postgres-replica-eu \
  --source-db-instance-identifier arn:aws:rds:us-east-1:xxxxx:db:med-lit-postgres \
  --region eu-west-1
```

#### Scaling Considerations

**Vertical Scaling (Instance Size):**
- Modify instance class during maintenance window
- Minimal downtime (usually < 1 minute)
- Plan for peak load capacity

**Horizontal Scaling (Read Replicas):**
```bash
aws rds create-db-instance-read-replica \
  --db-instance-identifier med-lit-postgres-read-replica-1 \
  --source-db-instance-identifier med-lit-postgres
```

**Connection Pooling:**
Use RDS Proxy for better connection management:

```bash
aws rds create-db-proxy \
  --db-proxy-name med-lit-rds-proxy \
  --engine-family POSTGRESQL \
  --auth '[{"AuthScheme":"SECRETS","SecretArn":"arn:aws:secretsmanager:...","IAMAuth":"DISABLED"}]' \
  --role-arn arn:aws:iam::xxxxx:role/RDSProxyRole \
  --vpc-subnet-ids subnet-xxxxx subnet-yyyyy \
  --require-tls
```

### Cost Optimization

**Recommendations:**
1. Use Reserved Instances for production (up to 60% savings)
2. Enable storage autoscaling to avoid over-provisioning
3. Use Aurora PostgreSQL for massive scale (serverless option available)
4. Set up CloudWatch alarms to detect idle instances
5. Use Graviton2 instances (db.r6g family) for better price/performance

**Estimated Monthly Costs (us-east-1):**
- db.t3.medium (dev): ~$60/month
- db.r6g.xlarge (prod): ~$280/month (on-demand), ~$180/month (1-year RI)
- Storage (100 GB gp3): ~$11.50/month
- Backup storage (first 100 GB free)

## Aurora PostgreSQL Alternative

For very large scale deployments, consider Aurora PostgreSQL:

```bash
aws rds create-db-cluster \
  --db-cluster-identifier med-lit-aurora-cluster \
  --engine aurora-postgresql \
  --engine-version 16.1 \
  --master-username postgres \
  --master-user-password <password> \
  --db-subnet-group-name my-subnet-group \
  --vpc-security-group-ids sg-xxxxx \
  --storage-encrypted

# Add instances to cluster
aws rds create-db-instance \
  --db-instance-identifier med-lit-aurora-instance-1 \
  --db-instance-class db.r6g.xlarge \
  --engine aurora-postgresql \
  --db-cluster-identifier med-lit-aurora-cluster
```

**Aurora Benefits:**
- Serverless v2 option (auto-scaling)
- Better replication (up to 15 read replicas)
- Faster failover (< 30 seconds)
- Global database for multi-region

**Trade-offs:**
- Higher cost (~2x RDS for equivalent capacity)
- More complex architecture
- Worth it for >1TB databases with high read load

## Troubleshooting

### Common Issues

**Connection timeout:**
- Check security group allows traffic from your IP/application
- Verify RDS instance is in available state
- Test with `telnet <endpoint> 5432`

**pgvector extension not found:**
- Ensure PostgreSQL version is 15.2+ or 16.1+
- Run `CREATE EXTENSION vector;` as superuser/rds_superuser
- Check `SELECT * FROM pg_available_extensions WHERE name = 'vector';`

**Slow queries:**
- Enable Performance Insights
- Check for missing indexes on frequently queried columns
- Review connection pool settings
- Consider read replicas for read-heavy workloads

### Useful SQL Commands

```sql
-- Check database size
SELECT pg_size_pretty(pg_database_size('medlit'));

-- Check active connections
SELECT count(*) FROM pg_stat_activity WHERE datname = 'medlit';

-- Check table sizes
SELECT
  schemaname,
  tablename,
  pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) AS size
FROM pg_tables
WHERE schemaname = 'public'
ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC;

-- Check vector index status
SELECT
  schemaname,
  tablename,
  indexname,
  indexdef
FROM pg_indexes
WHERE indexdef LIKE '%vector%';
```

## Migration Strategy

When moving from local development to AWS:

1. **Export local data:**
   ```bash
   pg_dump -h localhost -U postgres medlit > medlit_export.sql
   ```

2. **Create RDS instance** (see AWS section above)

3. **Import to RDS:**
   ```bash
   psql -h <rds-endpoint> -U postgres medlit < medlit_export.sql
   ```

4. **Verify data:**
   ```sql
   SELECT count(*) FROM entities;
   SELECT count(*) FROM relationships;
   ```

5. **Update application config** to use RDS endpoint

## Additional Resources

- [pgvector GitHub](https://github.com/pgvector/pgvector)
- [AWS RDS PostgreSQL](https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/CHAP_PostgreSQL.html)
- [RDS Performance Insights](https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/USER_PerfInsights.html)
- [SQLModel Documentation](https://sqlmodel.tiangolo.com/)
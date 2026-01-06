#!/usr/bin/env python3
"""
Verify Docker Compose setup and initialize services.

This script:
1. Tests PostgreSQL connection
2. Enables pgvector extension
3. Tests Redis connection
4. Creates basic database schema if needed
"""

import sys
import time
from typing import Tuple

try:
    import psycopg2
    import redis
    from sqlalchemy import create_engine, text
except ImportError:
    print("Error: Required packages not installed.")
    print("Install with: pip install psycopg2-binary redis sqlalchemy")
    sys.exit(1)


def test_postgres(
    host: str = "localhost",
    port: int = 5432,
    user: str = "postgres",
    password: str = "postgres",
    database: str = "medlit",
    max_retries: int = 5
) -> Tuple[bool, str]:
    """Test PostgreSQL connection and enable pgvector."""
    
    for attempt in range(max_retries):
        try:
            # Test connection
            conn = psycopg2.connect(
                host=host,
                port=port,
                user=user,
                password=password,
                database=database
            )
            cur = conn.cursor()
            
            # Get PostgreSQL version
            cur.execute("SELECT version();")
            version = cur.fetchone()[0]
            
            # Enable pgvector extension
            cur.execute("CREATE EXTENSION IF NOT EXISTS vector;")
            conn.commit()
            
            # Verify pgvector is available
            cur.execute(
                "SELECT * FROM pg_extension WHERE extname = 'vector';"
            )
            pgvector_installed = cur.fetchone() is not None
            
            cur.close()
            conn.close()
            
            if pgvector_installed:
                return True, f"PostgreSQL connected successfully\n  Version: {version[:50]}...\n  pgvector: Installed"
            else:
                return False, "pgvector extension not available"
                
        except psycopg2.OperationalError as e:
            if attempt < max_retries - 1:
                print(f"  Attempt {attempt + 1}/{max_retries}: Waiting for PostgreSQL...")
                time.sleep(2)
            else:
                return False, f"Connection failed: {str(e)}"
        except Exception as e:
            return False, f"Error: {str(e)}"
    
    return False, "Max retries exceeded"


def test_redis(
    host: str = "localhost",
    port: int = 6379,
    db: int = 0,
    max_retries: int = 5
) -> Tuple[bool, str]:
    """Test Redis connection."""
    
    for attempt in range(max_retries):
        try:
            client = redis.Redis(host=host, port=port, db=db, decode_responses=True)
            
            # Test ping
            pong = client.ping()
            if not pong:
                return False, "Redis ping failed"
            
            # Get Redis info
            info = client.info('server')
            version = info.get('redis_version', 'unknown')
            
            # Test write/read
            test_key = "__init_test__"
            client.set(test_key, "test_value")
            value = client.get(test_key)
            client.delete(test_key)
            
            if value != "test_value":
                return False, "Redis read/write test failed"
            
            client.close()
            
            return True, f"Redis connected successfully\n  Version: {version}\n  Read/Write: OK"
            
        except redis.exceptions.ConnectionError:
            if attempt < max_retries - 1:
                print(f"  Attempt {attempt + 1}/{max_retries}: Waiting for Redis...")
                time.sleep(2)
            else:
                return False, "Connection failed"
        except Exception as e:
            return False, f"Error: {str(e)}"
    
    return False, "Max retries exceeded"


def create_basic_schema(database_url: str) -> Tuple[bool, str]:
    """Create basic tables if they don't exist."""
    
    try:
        engine = create_engine(database_url)
        
        with engine.connect() as conn:
            # Check if tables exist
            result = conn.execute(text("""
                SELECT COUNT(*)
                FROM information_schema.tables
                WHERE table_schema = 'public'
                AND table_name IN ('entities', 'relationships', 'papers')
            """))
            
            existing_tables = result.scalar()
            
            if existing_tables > 0:
                return True, f"Schema exists ({existing_tables} core tables found)"
            else:
                return True, "No schema found - run setup_database.py to create tables"
        
    except Exception as e:
        return False, f"Error checking schema: {str(e)}"


def main():
    """Main verification routine."""
    
    print("=" * 60)
    print("Docker Compose Setup Verification")
    print("=" * 60)
    print()
    
    # Test PostgreSQL
    print("Testing PostgreSQL...")
    pg_success, pg_message = test_postgres()
    
    if pg_success:
        print(f"✓ {pg_message}")
    else:
        print(f"✗ {pg_message}")
        print("\nTroubleshooting:")
        print("  1. Check if container is running: docker compose ps")
        print("  2. Check logs: docker compose logs postgres")
        print("  3. Verify port mapping: docker compose port postgres 5432")
    
    print()
    
    # Test Redis
    print("Testing Redis...")
    redis_success, redis_message = test_redis()
    
    if redis_success:
        print(f"✓ {redis_message}")
    else:
        print(f"✗ {redis_message}")
        print("\nTroubleshooting:")
        print("  1. Check if container is running: docker compose ps")
        print("  2. Check logs: docker compose logs redis")
        print("  3. Verify port mapping: docker compose port redis 6379")
    
    print()
    
    # Check schema if PostgreSQL is working
    if pg_success:
        print("Checking database schema...")
        schema_success, schema_message = create_basic_schema(
            "postgresql://postgres:postgres@localhost:5432/medlit"
        )
        
        if schema_success:
            print(f"✓ {schema_message}")
        else:
            print(f"✗ {schema_message}")
    
    print()
    print("=" * 60)
    
    if pg_success and redis_success:
        print("✓ All systems ready!")
        print()
        print("Connection strings:")
        print("  PostgreSQL: postgresql://postgres:postgres@localhost:5432/medlit")
        print("  Redis: redis://localhost:6379/0")
        print()
        print("Next steps:")
        print("  1. Run setup_database.py to create schema")
        print("  2. Load test data or run your application")
        return 0
    else:
        print("✗ Setup incomplete - please fix errors above")
        return 1


if __name__ == "__main__":
    sys.exit(main())
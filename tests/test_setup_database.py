"""
Tests for setup_database.py

These tests ensure that setup_database.py works correctly when called in isolation,
without the SQLModel classes being imported first. This is important because
setup_database.py is meant to be used as a standalone script.
"""

import os
import tempfile
from pathlib import Path

import pytest
from sqlalchemy import create_engine, inspect, text
from sqlmodel import SQLModel

from med_lit_schema.setup_database import setup_database


@pytest.fixture
def temp_database():
    """Create a temporary PostgreSQL database for testing."""
    # Use DATABASE_URL from environment or default
    base_db_url = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/medlit")
    
    # Create a unique database name for this test
    import uuid
    test_db_name = f"test_setup_{uuid.uuid4().hex[:8]}"
    
    # Connect to postgres database to create test database
    from sqlalchemy import create_engine as create_base_engine
    base_engine = create_base_engine(base_db_url.rsplit("/", 1)[0] + "/postgres")
    
    with base_engine.connect() as conn:
        conn.execute(text(f"DROP DATABASE IF EXISTS {test_db_name}"))
        conn.execute(text(f"CREATE DATABASE {test_db_name}"))
        conn.commit()
    
    test_db_url = base_db_url.rsplit("/", 1)[0] + f"/{test_db_name}"
    
    yield test_db_url
    
    # Cleanup: drop test database
    with base_engine.connect() as conn:
        # Terminate any connections to the test database
        conn.execute(text(f"""
            SELECT pg_terminate_backend(pid)
            FROM pg_stat_activity
            WHERE datname = '{test_db_name}' AND pid <> pg_backend_pid()
        """))
        conn.execute(text(f"DROP DATABASE IF EXISTS {test_db_name}"))
        conn.commit()
    
    base_engine.dispose()


def test_setup_database_creates_tables(temp_database):
    """Test that setup_database creates all required tables."""
    # Call setup_database without importing models first
    # This simulates the real-world usage where setup_database.py is called standalone
    setup_database(temp_database, skip_vector_index=True)
    
    # Verify tables were created
    engine = create_engine(temp_database)
    inspector = inspect(engine)
    tables = inspector.get_table_names()
    
    # Check that required tables exist
    assert "entities" in tables, "entities table should be created"
    assert "relationships" in tables, "relationships table should be created"
    
    # Verify entities table has expected columns
    entity_columns = [col["name"] for col in inspector.get_columns("entities")]
    assert "id" in entity_columns
    assert "entity_type" in entity_columns
    assert "name" in entity_columns
    assert "embedding" in entity_columns
    
    # Verify relationships table has expected columns
    rel_columns = [col["name"] for col in inspector.get_columns("relationships")]
    assert "id" in rel_columns
    assert "subject_id" in rel_columns
    assert "object_id" in rel_columns
    assert "predicate" in rel_columns
    
    engine.dispose()


def test_setup_database_creates_extensions(temp_database):
    """Test that setup_database creates required PostgreSQL extensions."""
    setup_database(temp_database, skip_vector_index=True)
    
    engine = create_engine(temp_database)
    with engine.connect() as conn:
        # Check that vector extension is enabled
        result = conn.execute(text("""
            SELECT EXISTS(
                SELECT 1 FROM pg_extension WHERE extname = 'vector'
            )
        """)).fetchone()
        assert result[0], "vector extension should be enabled"
        
        # Check that uuid-ossp extension is enabled
        result = conn.execute(text("""
            SELECT EXISTS(
                SELECT 1 FROM pg_extension WHERE extname = 'uuid-ossp'
            )
        """)).fetchone()
        assert result[0], "uuid-ossp extension should be enabled"
    
    engine.dispose()


def test_setup_database_sets_embedding_column_type(temp_database):
    """Test that setup_database sets embedding column to vector(768) type."""
    setup_database(temp_database, skip_vector_index=True)
    
    engine = create_engine(temp_database)
    with engine.connect() as conn:
        # Check that embedding column is vector type
        result = conn.execute(text("""
            SELECT data_type, udt_name
            FROM information_schema.columns
            WHERE table_name = 'entities' AND column_name = 'embedding'
        """)).fetchone()
        
        assert result is not None, "embedding column should exist"
        # vector type shows up as USER-DEFINED with udt_name = 'vector'
        assert result[1] == "vector", f"embedding column should be vector type, got {result}"
    
    engine.dispose()


def test_setup_database_creates_triggers(temp_database):
    """Test that setup_database creates update triggers."""
    setup_database(temp_database, skip_vector_index=True)
    
    engine = create_engine(temp_database)
    with engine.connect() as conn:
        # Check that trigger function exists
        result = conn.execute(text("""
            SELECT EXISTS(
                SELECT 1 FROM pg_proc WHERE proname = 'update_updated_at_column'
            )
        """)).fetchone()
        assert result[0], "update_updated_at_column function should exist"
        
        # Check that triggers exist on entities table
        result = conn.execute(text("""
            SELECT COUNT(*) FROM pg_trigger
            WHERE tgname = 'update_entities_updated_at'
            AND tgrelid = 'entities'::regclass
        """)).fetchone()
        assert result[0] > 0, "update_entities_updated_at trigger should exist"
        
        # Check that triggers exist on relationships table
        result = conn.execute(text("""
            SELECT COUNT(*) FROM pg_trigger
            WHERE tgname = 'update_relationships_updated_at'
            AND tgrelid = 'relationships'::regclass
        """)).fetchone()
        assert result[0] > 0, "update_relationships_updated_at trigger should exist"
    
    engine.dispose()


def test_setup_database_can_insert_after_setup(temp_database):
    """Test that after setup_database, we can actually insert data."""
    setup_database(temp_database, skip_vector_index=True)
    
    engine = create_engine(temp_database)
    with engine.connect() as conn:
        # Insert a test entity
        conn.execute(text("""
            INSERT INTO entities (id, entity_type, name, mentions, source)
            VALUES ('TEST:001', 'disease', 'Test Disease', 0, 'test')
        """))
        conn.commit()
        
        # Verify it was inserted
        result = conn.execute(text("""
            SELECT id, name FROM entities WHERE id = 'TEST:001'
        """)).fetchone()
        
        assert result is not None
        assert result[0] == "TEST:001"
        assert result[1] == "Test Disease"
    
    engine.dispose()

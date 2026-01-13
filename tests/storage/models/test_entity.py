"""
Tests for the SQLModel `Entity` persistence model.

This test suite validates the functionality of the single `Entity` class,
which uses a discriminator (`entity_type`) to represent various kinds of
domain entities in a single database table.

Key areas tested:
- **Creation**: Ensures that entities of different types (Disease, Gene, Drug)
  can be successfully created and persisted.
- **Field Integrity**: Verifies that all fields, including standard attributes
  and JSON-serialized ones (like `synonyms`), are stored and retrieved correctly.
- **Polymorphic Queries**: Confirms that queries can retrieve all entities
  regardless of their type.
- **Type-Specific Queries**: Tests the ability to filter and query for entities
  of a specific type (e.g., only `DISEASE`).
- **Database Setup**: Includes fixtures to manage a temporary PostgreSQL
  database connection and session, ensuring tests run in a clean, isolated
  environment.

These tests are designed to run against a PostgreSQL database, as they rely
on features like the `JSONB` data type, which is not available in SQLite.

Prerequisites:
- A running PostgreSQL instance (can be started with `docker-compose up -d postgres`).
- `DATABASE_URL` environment variable set to the PostgreSQL connection string.

To run these tests:
    pytest tests/storage/models/test_entity.py -v
"""

import json
import os

import pytest
from sqlalchemy import text
from sqlalchemy.exc import OperationalError
from sqlmodel import Session, SQLModel, create_engine, select

from med_lit_schema.storage.models.entity import Entity, EntityType


# Check if PostgreSQL is available
def postgres_available():
    """Check if PostgreSQL database is accessible."""
    database_url = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/medlit")
    try:
        engine = create_engine(database_url, echo=False)
        with engine.connect():
            pass
        engine.dispose()
        return True
    except (OperationalError, Exception):
        return False


pytestmark = pytest.mark.skipif(not postgres_available(), reason="PostgreSQL not available. Start with: docker-compose up -d postgres")


@pytest.fixture(scope="module")
def engine():
    """Create PostgreSQL database connection for testing"""
    # Use DATABASE_URL from environment or default to docker-compose connection
    database_url = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/medlit")
    engine = create_engine(database_url, echo=False)

    # Create tables if they don't exist
    SQLModel.metadata.create_all(engine)

    # Enable pgvector extension if not already enabled
    with engine.connect() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector;"))
        conn.commit()

    yield engine

    # Cleanup: drop all tables after tests
    SQLModel.metadata.drop_all(engine)
    engine.dispose()


@pytest.fixture
def session(engine):
    """Create database session"""
    # Clean up any existing data before each test
    with Session(engine) as session:
        # Clear all entities
        session.exec(text("TRUNCATE TABLE entities CASCADE"))
        session.commit()

        yield session

        # Clean up after test
        session.rollback()


def test_create_disease(session):
    """Test creating a Disease entity"""
    disease = Entity(
        id="UMLS:C0006142",
        entity_type=EntityType.DISEASE.value,
        name="Breast Cancer",
        synonyms=json.dumps(["Breast Carcinoma", "Mammary Cancer"]),
        abbreviations=json.dumps(["BC"]),
        umls_id="C0006142",
        mesh_id="D001943",
        icd10_codes=json.dumps(["C50.9"]),
        disease_category="genetic",
    )

    session.add(disease)
    session.commit()
    session.refresh(disease)

    assert disease.id == "UMLS:C0006142"
    assert disease.name == "Breast Cancer"
    assert disease.entity_type == EntityType.DISEASE.value
    assert disease.umls_id == "C0006142"

    # Check JSON string content
    synonyms = json.loads(disease.synonyms)
    assert len(synonyms) == 2
    assert "BC" in json.loads(disease.abbreviations)


def test_create_gene(session):
    """Test creating a Gene entity"""
    gene = Entity(
        id="HGNC:1100",
        entity_type=EntityType.GENE.value,
        name="BRCA1 DNA repair associated",
        synonyms=json.dumps(["BRCA1", "breast cancer 1"]),
        symbol="BRCA1",
        hgnc_id="HGNC:1100",
        chromosome="17q21.31",
        entrez_id="672",
    )

    session.add(gene)
    session.commit()
    session.refresh(gene)

    assert gene.id == "HGNC:1100"
    assert gene.symbol == "BRCA1"
    assert gene.entity_type == EntityType.GENE.value


def test_polymorphic_query_all_entities(session):
    """Test querying all entities"""
    # Create entities of different types
    disease = Entity(id="D1", entity_type=EntityType.DISEASE.value, name="Disease 1", umls_id="C001")
    gene = Entity(id="G1", entity_type=EntityType.GENE.value, name="Gene 1", symbol="GENE1")
    drug = Entity(id="DR1", entity_type=EntityType.DRUG.value, name="Drug 1", rxnorm_id="R001")

    session.add_all([disease, gene, drug])
    session.commit()

    # Query all entities
    statement = select(Entity)
    entities = session.exec(statement).all()

    assert len(entities) == 3

    # Check types
    entity_types = {e.entity_type for e in entities}
    assert EntityType.DISEASE.value in entity_types
    assert EntityType.GENE.value in entity_types
    assert EntityType.DRUG.value in entity_types


def test_query_specific_type(session):
    """Test querying specific entity type by filtering"""
    # Create multiple diseases
    d1 = Entity(id="D1", entity_type=EntityType.DISEASE.value, name="Disease 1", umls_id="C001")
    d2 = Entity(id="D2", entity_type=EntityType.DISEASE.value, name="Disease 2", umls_id="C002")
    gene = Entity(id="G1", entity_type=EntityType.GENE.value, name="Gene 1", symbol="GENE1")

    session.add_all([d1, d2, gene])
    session.commit()

    # Query only diseases
    statement = select(Entity).where(Entity.entity_type == EntityType.DISEASE.value)
    diseases = session.exec(statement).all()

    assert len(diseases) == 2
    assert all(d.entity_type == EntityType.DISEASE.value for d in diseases)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

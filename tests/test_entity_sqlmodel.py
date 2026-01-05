"""
Test suite for SQLModel entity schema (Single Class).

Tests:
1. Entity creation (using Entity type directly)
2. Queries by type
3. Field access
4. Database persistence
"""

import json

import pytest
from sqlmodel import Session, SQLModel, create_engine, select

from schema.entity_sqlmodel import Entity, EntityType


@pytest.fixture
def engine():
    """Create in-memory SQLite database for testing"""
    engine = create_engine("sqlite:///:memory:", echo=False)
    SQLModel.metadata.create_all(engine)
    return engine


@pytest.fixture
def session(engine):
    """Create database session"""
    with Session(engine) as session:
        yield session


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

"""
Tests for pipeline storage interfaces.

Run with: uv run pytest tests/test_pipeline_storage.py -v
"""

import pytest
from pathlib import Path
from datetime import datetime
import socket
import platform

# These imports should work once the package is installed
try:
    from med_lit_schema.pipeline.sqlite_storage import SQLitePipelineStorage
    from med_lit_schema.pipeline.storage_interfaces import PipelineStorageInterface
    from med_lit_schema.entity import (
        Paper, Disease, Gene, Drug, EntityType, EvidenceItem,
        PaperMetadata, ExtractionProvenance, ExtractionPipelineInfo, ExecutionInfo, PromptInfo
    )
    from med_lit_schema.relationship import create_relationship
    from med_lit_schema.base import PredicateType
    from med_lit_schema.entity import AssertedRelationship
except ImportError:
    # Fallback for development
    pytest.skip("Package not installed - run 'uv pip install -e .' first", allow_module_level=True)


@pytest.fixture
def storage():
    """Create in-memory SQLite storage for testing."""
    storage = SQLitePipelineStorage(":memory:")
    yield storage
    storage.close()


def test_entity_storage(storage):
    """Test entity storage and retrieval."""
    # Create disease
    disease = Disease(
        entity_id="C0006142",
        entity_type=EntityType.DISEASE,
        name="Breast Cancer",
        synonyms=["Breast Carcinoma"],
        source="umls"
    )
    storage.entities.add_disease(disease)
    
    # Retrieve
    retrieved = storage.entities.get_by_id("C0006142")
    assert retrieved is not None
    assert retrieved.name == "Breast Cancer"
    assert len(retrieved.synonyms) == 1
    
    # Test count
    assert storage.entities.entity_count == 1


def test_paper_storage(storage):
    """Test paper storage and retrieval."""
    pipeline_info = ExtractionPipelineInfo(
        name="test",
        version="1.0.0",
        git_commit="abc123",
        git_commit_short="abc123",
        git_branch="main",
        git_dirty=False,
        repo_url="https://test.com"
    )
    
    execution_info = ExecutionInfo(
        timestamp=datetime.now().isoformat(),
        hostname=socket.gethostname(),
        python_version=platform.python_version(),
        duration_seconds=None
    )
    
    paper = Paper(
        paper_id="PMC123456",
        title="Test Paper on Breast Cancer",
        abstract="This is a test abstract.",
        authors=["Smith, John", "Doe, Jane"],
        publication_date="2023-06-15",
        journal="Test Journal",
        entities=[],
        relationships=[],
        metadata=PaperMetadata(),
            extraction_provenance=ExtractionProvenance(
                extraction_pipeline=pipeline_info,
                models={},
                prompt=PromptInfo(version="v1", template="test", checksum=None),
                execution=execution_info,
                entity_resolution=None
            )
    )
    
    storage.papers.add_paper(paper)
    
    retrieved = storage.papers.get_paper("PMC123456")
    assert retrieved is not None
    assert retrieved.title == "Test Paper on Breast Cancer"
    assert len(retrieved.authors) == 2
    
    assert storage.papers.paper_count == 1


def test_relationship_storage(storage):
    """Test relationship storage and retrieval."""
    relationship = create_relationship(
        predicate=PredicateType.TREATS,
        subject_id="RxNorm:1187832",  # Olaparib
        object_id="C0006142",  # Breast Cancer
        confidence=0.95,
        source_papers=["PMC123456"]
    )
    
    storage.relationships.add_relationship(relationship)
    
    retrieved = storage.relationships.get_relationship(
        "RxNorm:1187832",
        "treats",
        "C0006142"
    )
    
    assert retrieved is not None
    assert retrieved.confidence == 0.95
    assert retrieved.predicate == PredicateType.TREATS
    
    assert storage.relationships.relationship_count == 1


def test_evidence_storage(storage):
    """Test evidence storage and retrieval."""
    evidence = EvidenceItem(
        paper_id="PMC123456",
        confidence=0.9,
        section_type="results",
        text_span="Olaparib significantly improved progression-free survival",
        study_type="rct",
        sample_size=302
    )
    
    storage.evidence.add_evidence(evidence)
    
    evidence_list = storage.evidence.get_evidence_by_paper("PMC123456")
    assert len(evidence_list) > 0
    assert evidence_list[0].sample_size == 302
    
    assert storage.evidence.evidence_count > 0


def test_multiple_entities(storage):
    """Test storing multiple entity types."""
    # Disease
    disease = Disease(
        entity_id="C0006142",
        entity_type=EntityType.DISEASE,
        name="Breast Cancer",
        source="umls"
    )
    storage.entities.add_disease(disease)
    
    # Gene
    gene = Gene(
        entity_id="HGNC:1100",
        entity_type=EntityType.GENE,
        name="BRCA1",
        hgnc_id="HGNC:1100",
        source="hgnc"
    )
    storage.entities.add_gene(gene)
    
    # Drug
    drug = Drug(
        entity_id="RxNorm:1187832",
        entity_type=EntityType.DRUG,
        name="Olaparib",
        rxnorm_id="RxNorm:1187832",
        source="rxnorm"
    )
    storage.entities.add_drug(drug)
    
    assert storage.entities.entity_count == 3
    
    # Test retrieval by canonical ID
    retrieved_gene = storage.entities.get_by_hgnc("HGNC:1100")
    assert retrieved_gene is not None
    assert retrieved_gene.name == "BRCA1"


def test_relationship_search(storage):
    """Test finding relationships by criteria."""
    # Create multiple relationships
    rel1 = create_relationship(
        predicate=PredicateType.TREATS,
        subject_id="RxNorm:1187832",
        object_id="C0006142",
        confidence=0.95
    )
    storage.relationships.add_relationship(rel1)
    
    rel2 = create_relationship(
        predicate=PredicateType.INCREASES_RISK,
        subject_id="HGNC:1100",
        object_id="C0006142",
        confidence=0.9
    )
    storage.relationships.add_relationship(rel2)
    
    # Find by predicate
    treats_rels = storage.relationships.find_relationships(predicate="treats")
    assert len(treats_rels) == 1
    
    # Find by object
    breast_cancer_rels = storage.relationships.find_relationships(object_id="C0006142")
    assert len(breast_cancer_rels) == 2


def test_complete_paper_ingestion(storage):
    """Test complete end-to-end paper ingestion with entities, relationships, and evidence."""
    # Step 1: Create entities
    disease = Disease(
        entity_id="C0006142",
        entity_type=EntityType.DISEASE,
        name="Breast Cancer",
        source="umls"
    )
    storage.entities.add_disease(disease)
    
    drug = Drug(
        entity_id="RxNorm:1187832",
        entity_type=EntityType.DRUG,
        name="Olaparib",
        rxnorm_id="RxNorm:1187832",
        source="rxnorm"
    )
    storage.entities.add_drug(drug)
    
    # Step 2: Create paper with entities and relationships
    from med_lit_schema.base import EntityReference
    
    paper_entities = [
        EntityReference(id="C0006142", name="Breast Cancer", type=EntityType.DISEASE),
        EntityReference(id="RxNorm:1187832", name="Olaparib", type=EntityType.DRUG),
    ]
    
    # Create relationship for storage
    relationship = create_relationship(
        predicate=PredicateType.TREATS,
        subject_id="RxNorm:1187832",
        object_id="C0006142",
        confidence=0.95,
        source_papers=["PMC123456"]
    )
    storage.relationships.add_relationship(relationship)
    
    # Create AssertedRelationship for Paper model (different from BaseRelationship)
    paper_relationships = [
        AssertedRelationship(
            subject_id="RxNorm:1187832",
            predicate=PredicateType.TREATS,
            object_id="C0006142",
            confidence=0.95,
            evidence="Olaparib significantly improved progression-free survival",
            section="results"
        )
    ]
    
    # Create paper with entities and relationships attached
    pipeline_info = ExtractionPipelineInfo(
        name="test",
        version="1.0.0",
        git_commit="abc123",
        git_commit_short="abc123",
        git_branch="main",
        git_dirty=False,
        repo_url="https://test.com"
    )
    
    execution_info = ExecutionInfo(
        timestamp=datetime.now().isoformat(),
        hostname=socket.gethostname(),
        python_version=platform.python_version(),
        duration_seconds=None
    )
    
    paper = Paper(
        paper_id="PMC123456",
        title="Efficacy of Olaparib in BRCA-Mutated Breast Cancer",
        abstract="Olaparib treatment significantly improved progression-free survival in BRCA-mutated breast cancer patients.",
        authors=["Smith, John", "Johnson, Alice"],
        publication_date="2023-06-15",
        journal="New England Journal of Medicine",
        entities=paper_entities,
        relationships=paper_relationships,
        metadata=PaperMetadata(),
        extraction_provenance=ExtractionProvenance(
            extraction_pipeline=pipeline_info,
            models={},
            prompt=PromptInfo(version="v1", template="test", checksum=None),
            execution=execution_info,
            entity_resolution=None
        )
    )
    storage.papers.add_paper(paper)
    
    # Step 3: Create evidence linking to the relationship
    evidence = EvidenceItem(
        paper_id="PMC123456",
        confidence=0.9,
        section_type="results",
        text_span="Olaparib significantly improved progression-free survival",
        study_type="rct",
        sample_size=302
    )
    storage.evidence.add_evidence(evidence)
    
    # Step 4: Verify complete ingestion
    # Verify paper
    retrieved_paper = storage.papers.get_paper("PMC123456")
    assert retrieved_paper is not None
    assert len(retrieved_paper.entities) == 2
    assert len(retrieved_paper.relationships) == 1
    
    # Verify entities exist
    assert storage.entities.get_by_id("C0006142") is not None
    assert storage.entities.get_by_id("RxNorm:1187832") is not None
    
    # Verify relationship exists and links to paper
    retrieved_rel = storage.relationships.get_relationship(
        "RxNorm:1187832",
        "treats",
        "C0006142"
    )
    assert retrieved_rel is not None
    assert "PMC123456" in retrieved_rel.source_papers
    
    # Verify evidence links to paper
    evidence_list = storage.evidence.get_evidence_by_paper("PMC123456")
    assert len(evidence_list) > 0
    
    # Verify counts
    assert storage.papers.paper_count == 1
    assert storage.entities.entity_count == 2
    assert storage.relationships.relationship_count == 1
    assert storage.evidence.evidence_count > 0
    
    print("\n✓ Complete paper ingestion validated:")
    print(f"  - Paper: {retrieved_paper.title}")
    print(f"  - Entities: {storage.entities.entity_count}")
    print(f"  - Relationships: {storage.relationships.relationship_count}")
    print(f"  - Evidence items: {storage.evidence.evidence_count}")

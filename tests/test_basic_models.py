"""
Basic smoke tests for core models.

Tests basic model creation and serialization without requiring full ingest setup.

Run with: uv run pytest tests/test_basic_models.py -v
"""

import pytest
from datetime import datetime
import socket
import platform

from med_lit_schema.entity import (
    Paper,
    Disease,
    EntityType,
    EvidenceItem,
    PaperMetadata,
    ExtractionProvenance,
    ExtractionPipelineInfo,
    ExecutionInfo,
    PromptInfo,
)
from med_lit_schema.relationship import create_relationship
from med_lit_schema.base import PredicateType


@pytest.fixture
def ingest_info():
    """
    Create test ingest info.

    Attributes:

        name: Pipeline name
        version: Pipeline version
        git_commit: Full git commit hash
        git_commit_short: Short git commit hash
        git_branch: Git branch name
        git_dirty: Whether working directory has uncommitted changes
        repo_url: Repository URL

    """
    return ExtractionPipelineInfo(
        name="test",
        version="1.0.0",
        git_commit="abc123",
        git_commit_short="abc123",
        git_branch="main",
        git_dirty=False,
        repo_url="https://test.com",
    )


@pytest.fixture
def execution_info():
    """
    Create test execution info.

    Attributes:

        timestamp: ISO format timestamp
        hostname: Machine hostname
        python_version: Python version string
        duration_seconds: Optional execution duration

    """
    return ExecutionInfo(
        timestamp=datetime.now().isoformat(),
        hostname=socket.gethostname(),
        python_version=platform.python_version(),
        duration_seconds=None,
    )


def test_disease_model_creation():
    """Test creating a Disease entity."""
    disease = Disease(
        entity_id="C0006142",
        entity_type=EntityType.DISEASE,
        name="Breast Cancer",
        synonyms=["Breast Carcinoma"],
        source="umls",
    )

    assert disease.entity_id == "C0006142"
    assert disease.name == "Breast Cancer"
    assert len(disease.synonyms) == 1
    assert disease.entity_type == EntityType.DISEASE


def test_disease_model_serialization():
    """Test serializing and deserializing a Disease entity."""
    disease = Disease(
        entity_id="C0006142",
        entity_type=EntityType.DISEASE,
        name="Breast Cancer",
        synonyms=["Breast Carcinoma"],
        source="umls",
    )

    # Serialize to JSON
    json_str = disease.model_dump_json()
    assert isinstance(json_str, str)

    # Deserialize from JSON
    retrieved = Disease.model_validate_json(json_str)
    assert retrieved.entity_id == disease.entity_id
    assert retrieved.name == disease.name
    assert retrieved.synonyms == disease.synonyms


def test_paper_model_creation(ingest_info, execution_info):
    """Test creating a Paper model."""
    paper = Paper(
        paper_id="PMC123456",
        title="Test Paper",
        abstract="This is a test abstract.",
        authors=["Smith, John"],
        publication_date="2023-06-15",
        journal="Test Journal",
        entities=[],
        relationships=[],
        metadata=PaperMetadata(),
        extraction_provenance=ExtractionProvenance(
            extraction_pipeline=ingest_info,
            models={},
            prompt=PromptInfo(version="v1", template="test", checksum=None),
            execution=execution_info,
            entity_resolution=None,
        ),
    )

    assert paper.paper_id == "PMC123456"
    assert paper.title == "Test Paper"
    assert len(paper.authors) == 1
    assert paper.journal == "Test Journal"


def test_paper_model_with_metadata(ingest_info, execution_info):
    """Test Paper model with complete metadata."""
    paper = Paper(
        paper_id="PMC123456",
        title="Test Paper on Breast Cancer",
        abstract="Detailed abstract about breast cancer treatment.",
        authors=["Smith, John", "Doe, Jane"],
        publication_date="2023-06-15",
        journal="Test Journal",
        pmid="12345678",
        doi="10.1234/test.2023.001",
        entities=[],
        relationships=[],
        metadata=PaperMetadata(),
        extraction_provenance=ExtractionProvenance(
            extraction_pipeline=ingest_info,
            models={},
            prompt=PromptInfo(version="v1", template="test", checksum=None),
            execution=execution_info,
            entity_resolution=None,
        ),
    )

    assert paper.pmid == "12345678"
    assert paper.doi == "10.1234/test.2023.001"
    assert len(paper.authors) == 2


def test_relationship_creation():
    """Test creating a relationship."""
    relationship = create_relationship(
        predicate=PredicateType.TREATS,
        subject_id="RxNorm:1187832",
        object_id="C0006142",
        confidence=0.95,
        source_papers=["PMC123456"],
    )

    assert relationship.predicate == PredicateType.TREATS
    assert relationship.subject_id == "RxNorm:1187832"
    assert relationship.object_id == "C0006142"
    assert relationship.confidence == 0.95
    assert "PMC123456" in relationship.source_papers


def test_relationship_confidence_validation():
    """Test that relationship confidence is validated."""
    # Valid confidence
    rel = create_relationship(
        predicate=PredicateType.TREATS,
        subject_id="RxNorm:1187832",
        object_id="C0006142",
        confidence=0.5,
    )
    assert rel.confidence == 0.5

    # Test boundary values
    rel_low = create_relationship(
        predicate=PredicateType.TREATS,
        subject_id="RxNorm:1187832",
        object_id="C0006142",
        confidence=0.0,
    )
    assert rel_low.confidence == 0.0

    rel_high = create_relationship(
        predicate=PredicateType.TREATS,
        subject_id="RxNorm:1187832",
        object_id="C0006142",
        confidence=1.0,
    )
    assert rel_high.confidence == 1.0


def test_evidence_item_creation():
    """Test creating an evidence item."""
    evidence = EvidenceItem(
        paper_id="PMC123456",
        confidence=0.9,
        section_type="results",
        text_span="Olaparib significantly improved progression-free survival",
        study_type="rct",
        sample_size=302,
    )

    assert evidence.paper_id == "PMC123456"
    assert evidence.confidence == 0.9
    assert evidence.section_type == "results"
    assert evidence.study_type == "rct"
    assert evidence.sample_size == 302


def test_evidence_item_optional_fields():
    """Test creating evidence with minimal required fields."""
    evidence = EvidenceItem(
        paper_id="PMC123456",
        confidence=0.8,
        section_type="methods",
        text_span="Test text",
    )

    assert evidence.paper_id == "PMC123456"
    assert evidence.confidence == 0.8
    assert evidence.study_type is None
    assert evidence.sample_size is None


def test_entity_type_enum():
    """Test EntityType enum values."""
    assert EntityType.DISEASE.value == "disease"
    assert EntityType.GENE.value == "gene"
    assert EntityType.DRUG.value == "drug"
    assert EntityType.PROTEIN.value == "protein"


def test_predicate_type_enum():
    """Test PredicateType enum values."""
    assert PredicateType.TREATS.value == "treats"
    assert PredicateType.INCREASES_RISK.value == "increases_risk"
    assert PredicateType.ASSOCIATED_WITH.value == "associated_with"


def test_paper_serialization(ingest_info, execution_info):
    """Test serializing and deserializing a Paper model."""
    paper = Paper(
        paper_id="PMC123456",
        title="Test Paper",
        abstract="Test abstract",
        authors=["Smith, John"],
        publication_date="2023-06-15",
        journal="Test Journal",
        entities=[],
        relationships=[],
        metadata=PaperMetadata(),
        extraction_provenance=ExtractionProvenance(
            extraction_pipeline=ingest_info,
            models={},
            prompt=PromptInfo(version="v1", template="test", checksum=None),
            execution=execution_info,
            entity_resolution=None,
        ),
    )

    # Serialize
    json_str = paper.model_dump_json()
    assert isinstance(json_str, str)

    # Deserialize
    retrieved = Paper.model_validate_json(json_str)
    assert retrieved.paper_id == paper.paper_id
    assert retrieved.title == paper.title
    assert retrieved.authors == paper.authors

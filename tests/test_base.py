"""Tests for Pydantic models in base.py."""

import pytest
from pydantic import ValidationError

from med_lit_schema.base import (
    ClaimPredicate,
    PredicateType,
    Provenance,
    EvidenceType,
    ModelInfo,
)


def test_claim_predicate_validation():
    """Test that ClaimPredicate validates predicate_type correctly."""
    # Valid case
    cp = ClaimPredicate(
        predicate_type=PredicateType.CAUSES,
        description="Smoking causes cancer",
    )
    assert cp.predicate_type == PredicateType.CAUSES

    # Invalid predicate type
    with pytest.raises(ValidationError):
        ClaimPredicate(
            predicate_type="IS_A",
            description="Invalid predicate",
        )


def test_provenance_model():
    """Test that Provenance model correctly handles required and optional fields."""
    # Minimal valid case
    prov = Provenance(source_type="paper", source_id="doi:12345")
    assert prov.source_type == "paper"
    assert prov.source_id == "doi:12345"
    assert prov.source_version is None
    assert prov.notes is None

    # Full case
    prov_full = Provenance(
        source_type="database",
        source_id="DB001",
        source_version="v2.3",
        notes="Manually curated entry.",
    )
    assert prov_full.source_version == "v2.3"
    assert "Manually curated" in prov_full.notes

    # Missing required fields
    with pytest.raises(ValidationError):
        Provenance(source_type="paper")  # Missing source_id
    with pytest.raises(ValidationError):
        Provenance(source_id="doi:12345")  # Missing source_type


def test_evidence_type_model():
    """Test that EvidenceType model enforces required fields."""
    # Valid case
    et = EvidenceType(
        ontology_id="ECO:0000059",
        ontology_label="experimental evidence",
        description="Evidence from a controlled experiment.",
    )
    assert et.ontology_id == "ECO:0000059"
    assert et.description is not None

    # Missing required fields
    with pytest.raises(ValidationError):
        EvidenceType(ontology_label="experimental evidence")
    with pytest.raises(ValidationError):
        EvidenceType(ontology_id="ECO:0000059")


def test_model_info_validation():
    """Test that ModelInfo model validates required and optional fields."""
    # Valid case
    mi = ModelInfo(
        name="gemini-1.5-pro",
        provider="google",
        temperature=0.7,
        version="v1.latest",
    )
    assert mi.name == "gemini-1.5-pro"
    assert mi.provider == "google"

    # Test optional fields
    mi_minimal = ModelInfo(name="distilbert-base-cased", provider="huggingface")
    assert mi_minimal.temperature is None
    assert mi_minimal.version is None

    # Missing required fields
    with pytest.raises(ValidationError):
        ModelInfo(provider="anthropic")  # Missing name
    with pytest.raises(ValidationError):
        ModelInfo(name="claude-3-opus")  # Missing provider

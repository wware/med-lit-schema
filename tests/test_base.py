"""
Tests for the Pydantic models defined in `base.py`.

This test suite validates the core data structures used throughout the schema,
ensuring they enforce the expected constraints and behaviors.

Key models and aspects tested:
- `ClaimPredicate`: Verifies that the `predicate_type` field only accepts
  valid members of the `PredicateType` enum, rejecting arbitrary strings.
- `Provenance`: Checks that the model correctly handles both minimal
  (required fields only) and fully populated instances. It also ensures that
  `ValidationError` is raised if required fields like `source_type` or
  `source_id` are missing.
- `EvidenceType`: Validates the creation and field requirements for the
  `EvidenceType` model, which links to external ontologies like ECO.
- `ModelInfo`: Ensures that the model for capturing information about
  machine learning models correctly validates required fields (`name`, `provider`)
  and handles optional ones (`temperature`, `version`).

These tests are crucial for maintaining the integrity and reliability of the
foundational data models of the schema.

Run with: pytest tests/test_base.py -v
"""

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
    """
    Test that the `ClaimPredicate` model successfully validates correct `predicate_type`
    enum members and raises a `ValidationError` for invalid string inputs.

    This ensures that only predefined predicate types are accepted.
    """
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
    """
    Test the `Provenance` model's data validation.

    It checks that a minimal instance with only required fields (`source_type`,
    `source_id`) is valid, a full instance with all optional fields is correctly
    populated, and that `ValidationError` is raised if any of the required
    fields are missing.
    """
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
    """
    Test the `EvidenceType` model's data validation.

    It ensures that an instance with all required fields (`ontology_id`,
    `ontology_label`) is created successfully and that a `ValidationError`
    is raised if any of these fields are missing.
    """
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
    """
    Test the `ModelInfo` model's data validation.

    This test verifies that a `ModelInfo` instance can be created with all
    required (`name`, `provider`) and optional (`temperature`, `version`)
    fields. It also confirms that an instance is valid with only the required
    fields, and that a `ValidationError` is raised if any of the required
    fields are missing.
    """
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
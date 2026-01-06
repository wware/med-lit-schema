"""
Test that provenance (evidence) is actually enforced as documented.

The project claims "provenance is mandatory" but we need to verify this is
actually enforced by Pydantic validation, not just documentation.
"""

import pytest
from pydantic import ValidationError

from med_lit_schema.relationship import (
    Treats,
    Causes,
    IncreasesRisk,
    PredicateType,
)
from med_lit_schema.entity import EvidenceItem


def test_relationship_without_evidence_or_source_papers():
    """
    CRITICAL: Test what happens when neither evidence nor source_papers are provided.

    Based on the documentation, this SHOULD fail. However, the current implementation
    allows empty lists for both evidence and source_papers, which may not match
    the design intent.

    This test documents current behavior and will help catch unintended changes.
    """
    # Currently this DOES NOT fail - but should it?
    treats = Treats(
        subject_id="RxNorm:1187832",  # Olaparib
        object_id="UMLS:C0006142",  # Breast Cancer
        predicate=PredicateType.TREATS,
        response_rate=0.59,
        # Note: No evidence, no source_papers
    )

    # Current behavior: relationship is created with empty evidence
    assert treats.evidence == []
    assert treats.source_papers == []
    assert treats.evidence_count == 0

    # TODO: If provenance should be mandatory, add min_length=1 to these fields:
    # evidence: list[EvidenceItem] = Field(default_factory=list, min_length=1)
    # source_papers: list[str] = Field(default_factory=list, min_length=1)


def test_relationship_with_source_papers_only():
    """
    Test lightweight provenance (just paper IDs, no detailed Evidence objects).

    This is explicitly supported by the schema design - you can provide just
    source_papers for lightweight tracking without full EvidenceItem objects.
    """
    treats = Treats(
        subject_id="RxNorm:1187832",
        object_id="UMLS:C0006142",
        predicate=PredicateType.TREATS,
        source_papers=["PMC123", "PMC456"],
        evidence_count=2,
        confidence=0.85,
        response_rate=0.59,
    )

    assert len(treats.source_papers) == 2
    assert "PMC123" in treats.source_papers
    assert treats.evidence_count == 2
    assert treats.evidence == []  # No detailed evidence, just paper IDs


def test_relationship_with_evidence_objects():
    """
    Test rich provenance with detailed EvidenceItem objects.

    This is the recommended approach for medical relationships.
    """
    evidence = EvidenceItem(
        paper_id="PMC999888",
        section_type="results",
        paragraph_idx=8,
        text_span="Olaparib showed 59% response rate in BRCA-mutated breast cancer patients",
        extraction_method="table_parser",
        confidence=0.92,
        study_type="rct",
        sample_size=302,
    )

    treats = Treats(
        subject_id="RxNorm:1187832",
        object_id="UMLS:C0006142",
        predicate=PredicateType.TREATS,
        evidence=[evidence],
        source_papers=["PMC999888"],  # Should match evidence[0].paper_id
        evidence_count=1,
        response_rate=0.59,
        confidence=0.92,
    )

    assert len(treats.evidence) == 1
    assert treats.evidence[0].paper_id == "PMC999888"
    assert treats.evidence[0].study_type == "rct"
    assert treats.evidence[0].sample_size == 302


def test_evidence_missing_required_paper_id_fails():
    """
    Evidence MUST have a paper_id - this is truly mandatory.
    """
    with pytest.raises(ValidationError) as exc_info:
        EvidenceItem(
            # Missing paper_id - should fail
            section_type="results",
            confidence=0.85,
        )

    # Verify the error is about missing paper_id
    error_dict = exc_info.value.errors()[0]
    assert error_dict["type"] == "missing"
    assert "paper_id" in str(error_dict["loc"])


def test_evidence_with_minimal_fields():
    """
    Evidence only requires paper_id - everything else is optional.
    """
    evidence = EvidenceItem(paper_id="PMC123")

    assert evidence.paper_id == "PMC123"
    assert evidence.confidence == 0.5  # default
    assert evidence.section_type is None
    assert evidence.paragraph_idx is None
    assert evidence.study_type is None


def test_empty_evidence_list_is_allowed():
    """
    Current behavior: Empty evidence list is allowed.

    This documents that provenance is NOT currently enforced at the Pydantic level.
    If this should change, add min_length=1 to the Field definition.
    """
    treats = Treats(
        subject_id="RxNorm:1187832",
        object_id="UMLS:C0006142",
        predicate=PredicateType.TREATS,
        evidence=[],  # Empty list currently allowed
        response_rate=0.59,
    )

    assert treats.evidence == []


def test_confidence_score_bounds():
    """
    Confidence must be between 0.0 and 1.0.
    """
    # Valid confidence scores
    for conf in [0.0, 0.5, 0.99, 1.0]:
        treats = Treats(
            subject_id="RxNorm:1",
            object_id="UMLS:C1",
            predicate=PredicateType.TREATS,
            source_papers=["PMC1"],
            confidence=conf,
        )
        assert treats.confidence == conf

    # Invalid confidence - too high
    with pytest.raises(ValidationError):
        Treats(
            subject_id="RxNorm:1",
            object_id="UMLS:C1",
            predicate=PredicateType.TREATS,
            source_papers=["PMC1"],
            confidence=1.5,  # > 1.0 should fail
        )

    # Invalid confidence - negative
    with pytest.raises(ValidationError):
        Treats(
            subject_id="RxNorm:1",
            object_id="UMLS:C1",
            predicate=PredicateType.TREATS,
            source_papers=["PMC1"],
            confidence=-0.1,  # < 0.0 should fail
        )


def test_evidence_confidence_bounds():
    """
    Evidence confidence must also be between 0.0 and 1.0.
    """
    # Valid
    evidence = EvidenceItem(paper_id="PMC123", confidence=0.95)
    assert evidence.confidence == 0.95

    # Invalid - too high
    with pytest.raises(ValidationError):
        EvidenceItem(paper_id="PMC123", confidence=1.1)

    # Invalid - negative
    with pytest.raises(ValidationError):
        EvidenceItem(paper_id="PMC123", confidence=-0.5)


def test_multiple_evidence_from_different_papers():
    """
    Test aggregating evidence from multiple papers.
    """
    evidence1 = EvidenceItem(paper_id="PMC111", study_type="rct", confidence=0.9, sample_size=100)
    evidence2 = EvidenceItem(paper_id="PMC222", study_type="observational", confidence=0.7, sample_size=500)
    evidence3 = EvidenceItem(paper_id="PMC333", study_type="meta_analysis", confidence=0.95, sample_size=2000)

    treats = Treats(
        subject_id="RxNorm:1187832",
        object_id="UMLS:C0006142",
        predicate=PredicateType.TREATS,
        evidence=[evidence1, evidence2, evidence3],
        source_papers=["PMC111", "PMC222", "PMC333"],
        evidence_count=3,
        confidence=0.85,  # Weighted average of evidence
    )

    assert len(treats.evidence) == 3
    assert treats.evidence_count == 3
    assert len(treats.source_papers) == 3

    # Evidence should include different study types
    study_types = [e.study_type for e in treats.evidence]
    assert "rct" in study_types
    assert "observational" in study_types
    assert "meta_analysis" in study_types


def test_contradictory_evidence_tracking():
    """
    Test tracking papers that contradict a relationship.
    """
    treats = Treats(
        subject_id="RxNorm:1",
        object_id="UMLS:C1",
        predicate=PredicateType.TREATS,
        source_papers=["PMC111", "PMC222"],  # Papers supporting
        contradicted_by=["PMC333", "PMC444"],  # Papers contradicting
        evidence_count=2,
        confidence=0.6,  # Lower confidence due to contradictions
    )

    assert len(treats.source_papers) == 2
    assert len(treats.contradicted_by) == 2
    assert "PMC333" in treats.contradicted_by


def test_different_relationship_types_with_evidence():
    """
    Test that evidence works consistently across different relationship types.
    """
    # Causes relationship
    causes = Causes(
        subject_id="UMLS:C0006142",  # Breast Cancer
        object_id="UMLS:C0030193",  # Pain
        predicate=PredicateType.CAUSES,
        source_papers=["PMC555"],
        frequency="often",
        onset="late",
        confidence=0.75,
    )
    assert causes.source_papers == ["PMC555"]

    # IncreasesRisk relationship
    risk = IncreasesRisk(
        subject_id="HGNC:1100",  # BRCA1
        object_id="UMLS:C0006142",  # Breast Cancer
        predicate=PredicateType.INCREASES_RISK,
        source_papers=["PMC123", "PMC456"],
        evidence_count=2,
        risk_ratio=5.0,
        penetrance=0.72,
        confidence=0.92,
    )
    assert len(risk.source_papers) == 2
    assert risk.risk_ratio == 5.0

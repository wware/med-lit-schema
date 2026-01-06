"""
Tests for hypothesis and evidence relationships (PREDICTS, REFUTES, TESTED_BY, GENERATES).

These relationships enable tracking scientific hypotheses and their validation through evidence.
"""

import pytest
from med_lit_schema.relationship import (
    Predicts,
    Refutes,
    TestedBy,
    Generates,
    PredicateType,
    create_relationship,
)
from med_lit_schema.entity import EvidenceItem


def test_predicts_relationship():
    """Test hypothesis predicting an outcome"""
    predicts = Predicts(
        subject_id="HYPOTHESIS:amyloid_cascade",
        predicate=PredicateType.PREDICTS,
        object_id="C0002395",  # Alzheimer's disease
        prediction_type="positive",
        testable=True,
        conditions="In presence of beta-amyloid plaques",
        source_papers=["PMC123456"],
        confidence=0.8,
    )

    assert predicts.predicate == PredicateType.PREDICTS
    assert predicts.subject_id == "HYPOTHESIS:amyloid_cascade"
    assert predicts.object_id == "C0002395"
    assert predicts.prediction_type == "positive"
    assert predicts.testable is True
    assert "PMC123456" in predicts.source_papers


def test_refutes_relationship():
    """Test evidence refuting a hypothesis"""
    refutes = Refutes(
        subject_id="PMC999888",
        predicate=PredicateType.REFUTES,
        object_id="HYPOTHESIS:amyloid_cascade",
        refutation_strength="moderate",
        alternative_explanation="Tau pathology may be primary driver",
        limitations="Small sample size, limited follow-up",
        source_papers=["PMC999888"],
        confidence=0.75,
    )

    assert refutes.predicate == PredicateType.REFUTES
    assert refutes.refutation_strength == "moderate"
    assert refutes.alternative_explanation is not None
    assert refutes.limitations is not None


def test_tested_by_relationship():
    """Test hypothesis being tested by a study"""
    tested = TestedBy(
        subject_id="HYPOTHESIS:parp_inhibitor_synthetic_lethality",
        predicate=PredicateType.TESTED_BY,
        object_id="PMC999888",
        test_outcome="supported",
        methodology="randomized controlled trial",
        study_design_id="OBI:0000008",
        source_papers=["PMC999888"],
        confidence=0.90,
    )

    assert tested.predicate == PredicateType.TESTED_BY
    assert tested.test_outcome == "supported"
    assert tested.study_design_id == "OBI:0000008"
    assert tested.methodology == "randomized controlled trial"


def test_generates_relationship():
    """Test study generating evidence"""
    generates = Generates(
        subject_id="PMC999888",
        predicate=PredicateType.GENERATES,
        object_id="EVIDENCE_LINE:olaparib_brca_001",
        evidence_type="experimental",
        eco_type="ECO:0007673",  # RCT evidence
        quality_score=0.92,
        source_papers=["PMC999888"],
        confidence=0.95,
    )

    assert generates.predicate == PredicateType.GENERATES
    assert generates.evidence_type == "experimental"
    assert generates.eco_type == "ECO:0007673"
    assert generates.quality_score == 0.92


def test_hypothesis_workflow():
    """Test complete hypothesis testing workflow with multiple relationships"""
    # Step 1: Hypothesis predicts outcome
    predicts = Predicts(
        subject_id="HYPOTHESIS:drug_x_treats_disease_y",
        object_id="DISEASE:improved_survival",
        prediction_type="positive",
        source_papers=["PMC_THEORY_001"],
    )

    # Step 2: Hypothesis tested by clinical trial
    tested = TestedBy(
        subject_id="HYPOTHESIS:drug_x_treats_disease_y",
        object_id="PMC_RCT_001",
        test_outcome="supported",
        study_design_id="OBI:0000008",
        source_papers=["PMC_RCT_001"],
    )

    # Step 3: Trial generates evidence
    generates = Generates(
        subject_id="PMC_RCT_001",
        object_id="EVIDENCE_LINE:drug_x_efficacy",
        eco_type="ECO:0007673",
        source_papers=["PMC_RCT_001"],
    )

    # Verify the workflow
    assert predicts.subject_id == tested.subject_id
    assert tested.object_id == generates.subject_id
    assert tested.test_outcome == "supported"


def test_create_relationship_factory_for_hypothesis_relations():
    """Test factory function creates correct relationship types for new relations"""
    # Test PREDICTS
    predicts = create_relationship(
        PredicateType.PREDICTS,
        subject_id="HYPOTHESIS:001",
        object_id="OUTCOME:001",
        prediction_type="positive",
    )
    assert isinstance(predicts, Predicts)

    # Test REFUTES
    refutes = create_relationship(
        PredicateType.REFUTES,
        subject_id="PMC001",
        object_id="HYPOTHESIS:001",
        refutation_strength="strong",
    )
    assert isinstance(refutes, Refutes)

    # Test TESTED_BY
    tested = create_relationship(
        PredicateType.TESTED_BY,
        subject_id="HYPOTHESIS:001",
        object_id="PMC002",
        test_outcome="supported",
    )
    assert isinstance(tested, TestedBy)

    # Test GENERATES
    generates = create_relationship(
        PredicateType.GENERATES,
        subject_id="PMC003",
        object_id="EVIDENCE:001",
        eco_type="ECO:0007673",
    )
    assert isinstance(generates, Generates)


def test_test_outcome_values():
    """Test that test_outcome accepts valid values"""
    for outcome in ["supported", "refuted", "inconclusive"]:
        tested = TestedBy(
            subject_id="HYPOTHESIS:test",
            object_id="PMC001",
            test_outcome=outcome,
            source_papers=["PMC001"],
        )
        assert tested.test_outcome == outcome


def test_refutation_strength_values():
    """Test that refutation_strength accepts valid values"""
    for strength in ["strong", "moderate", "weak"]:
        refutes = Refutes(
            subject_id="PMC001",
            object_id="HYPOTHESIS:test",
            refutation_strength=strength,
            source_papers=["PMC001"],
        )
        assert refutes.refutation_strength == strength


def test_prediction_type_values():
    """Test that prediction_type accepts valid values"""
    for pred_type in ["positive", "negative", "conditional"]:
        predicts = Predicts(
            subject_id="HYPOTHESIS:test",
            object_id="OUTCOME:001",
            prediction_type=pred_type,
            source_papers=["PMC001"],
        )
        assert predicts.prediction_type == pred_type


def test_generates_quality_score_bounds():
    """Test that quality_score validation works"""
    # Valid quality scores (0.0-1.0)
    generates = Generates(
        subject_id="PMC001",
        object_id="EVIDENCE:001",
        quality_score=0.85,
        source_papers=["PMC001"],
    )
    assert generates.quality_score == 0.85

    # Invalid quality scores should fail validation
    with pytest.raises(Exception):  # Pydantic validation error
        Generates(
            subject_id="PMC001",
            object_id="EVIDENCE:001",
            quality_score=1.5,  # Out of range
            source_papers=["PMC001"],
        )


def test_hypothesis_relationships_with_evidence():
    """Test that hypothesis relationships can include detailed evidence"""
    evidence = EvidenceItem(
        paper_id="PMC999888",
        confidence=0.92,
        section_type="results",
        study_type="rct",
        sample_size=302,
        eco_type="ECO:0007673",
        obi_study_design="OBI:0000008",
        stato_methods=["STATO:0000288"],
    )

    tested = TestedBy(
        subject_id="HYPOTHESIS:parp_inhibitor",
        object_id="PMC999888",
        test_outcome="supported",
        evidence=[evidence],
        source_papers=["PMC999888"],
        confidence=0.92,
    )

    assert len(tested.evidence) == 1
    assert tested.evidence[0].eco_type == "ECO:0007673"
    assert tested.evidence[0].obi_study_design == "OBI:0000008"

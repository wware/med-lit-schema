"""
Tests for ontology-based entities (Hypothesis, StudyDesign, StatisticalMethod, EvidenceLine).

These entities use standardized ontology IDs (ECO, OBI, STATO, IAO, SEPIO) to enable
structured representation of scientific methodology and evidence.
"""

import pytest
from med_lit_schema.entity import (
    Hypothesis,
    StudyDesign,
    StatisticalMethod,
    EvidenceLine,
    EntityCollection,
    EntityType,
)


def test_hypothesis_creation_and_validation():
    """Test creating a hypothesis entity with ontology IDs"""
    hypothesis = Hypothesis(
        entity_id="HYPOTHESIS:amyloid_cascade_alzheimers",
        name="Amyloid Cascade Hypothesis",
        iao_id="IAO:0000018",
        sepio_id="SEPIO:0000001",
        proposed_by="PMC123456",
        proposed_date="1992",
        status="controversial",
        description="Beta-amyloid accumulation drives Alzheimer's disease pathology",
        predicts=["C0002395"],  # Alzheimer's disease
    )

    assert hypothesis.entity_type == EntityType.HYPOTHESIS
    assert hypothesis.entity_id == "HYPOTHESIS:amyloid_cascade_alzheimers"
    assert hypothesis.iao_id == "IAO:0000018"
    assert hypothesis.sepio_id == "SEPIO:0000001"
    assert hypothesis.status == "controversial"
    assert "C0002395" in hypothesis.predicts


def test_study_design_entity():
    """Test creating a study design entity with OBI and STATO IDs"""
    rct = StudyDesign(
        entity_id="OBI:0000008",
        name="Randomized Controlled Trial",
        obi_id="OBI:0000008",
        stato_id="STATO:0000402",
        design_type="interventional",
        evidence_level=1,
        description="Gold standard experimental design with random assignment",
    )

    assert rct.entity_type == EntityType.STUDY_DESIGN
    assert rct.obi_id == "OBI:0000008"
    assert rct.stato_id == "STATO:0000402"
    assert rct.evidence_level == 1
    assert rct.design_type == "interventional"


def test_statistical_method_entity():
    """Test creating a statistical method entity with STATO ID"""
    ttest = StatisticalMethod(
        entity_id="STATO:0000288",
        name="Student's t-test",
        stato_id="STATO:0000288",
        method_type="hypothesis_test",
        description="Parametric test comparing means of two groups",
        assumptions=["Normal distribution", "Equal variances", "Independence"],
    )

    assert ttest.entity_type == EntityType.STATISTICAL_METHOD
    assert ttest.stato_id == "STATO:0000288"
    assert ttest.method_type == "hypothesis_test"
    assert len(ttest.assumptions) == 3


def test_evidence_line_entity():
    """Test creating an evidence line entity with SEPIO framework"""
    evidence = EvidenceLine(
        entity_id="EVIDENCE_LINE:olaparib_brca_001",
        name="Clinical evidence for Olaparib in BRCA-mutated breast cancer",
        sepio_type="SEPIO:0000084",
        eco_type="ECO:0007673",
        assertion_id="ASSERTION:olaparib_brca",
        supports=["HYPOTHESIS:parp_inhibitor_synthetic_lethality"],
        evidence_items=["PMC999888", "PMC888777"],
        strength="strong",
        provenance="Meta-analysis of 3 RCTs",
    )

    assert evidence.entity_type == EntityType.EVIDENCE_LINE
    assert evidence.sepio_type == "SEPIO:0000084"
    assert evidence.eco_type == "ECO:0007673"
    assert evidence.strength == "strong"
    assert len(evidence.supports) == 1
    assert len(evidence.evidence_items) == 2


def test_entity_collection_with_ontology_entities(tmp_path):
    """Test adding and retrieving ontology-based entities from collection"""
    collection = EntityCollection()

    # Add one of each new entity type
    hypothesis = Hypothesis(
        entity_id="HYPOTHESIS:test_hyp",
        name="Test Hypothesis",
        iao_id="IAO:0000018",
        status="proposed",
    )
    study = StudyDesign(
        entity_id="OBI:0000008",
        name="RCT",
        obi_id="OBI:0000008",
        evidence_level=1,
    )
    method = StatisticalMethod(
        entity_id="STATO:0000288",
        name="t-test",
        stato_id="STATO:0000288",
    )
    evidence = EvidenceLine(
        entity_id="EVIDENCE:001",
        name="Evidence line 1",
        sepio_type="SEPIO:0000084",
    )

    collection.add_hypothesis(hypothesis)
    collection.add_study_design(study)
    collection.add_statistical_method(method)
    collection.add_evidence_line(evidence)

    # Check they're stored correctly
    assert collection.entity_count >= 4
    assert collection.get_by_id("HYPOTHESIS:test_hyp") is not None
    assert collection.get_by_id("OBI:0000008") is not None
    assert collection.get_by_id("STATO:0000288") is not None
    assert collection.get_by_id("EVIDENCE:001") is not None

    # Test save/load roundtrip
    fpath = tmp_path / "ontology_entities.jsonl"
    collection.save(str(fpath))

    loaded = EntityCollection.load(str(fpath))
    assert loaded.entity_count >= 4
    assert loaded.get_by_id("HYPOTHESIS:test_hyp").name == "Test Hypothesis"
    assert loaded.get_by_id("OBI:0000008").evidence_level == 1


def test_hypothesis_status_transitions():
    """Test that hypothesis status field accepts valid values"""
    for status in ["proposed", "supported", "controversial", "refuted"]:
        hyp = Hypothesis(
            entity_id=f"HYP:{status}",
            name=f"Hypothesis with status {status}",
            status=status,
        )
        assert hyp.status == status


def test_study_design_evidence_levels():
    """Test that evidence level validation works correctly"""
    # Valid evidence levels (1-5)
    for level in [1, 2, 3, 4, 5]:
        design = StudyDesign(
            entity_id=f"DESIGN:{level}",
            name=f"Design level {level}",
            evidence_level=level,
        )
        assert design.evidence_level == level

    # Invalid evidence levels should fail validation
    with pytest.raises(Exception):  # Pydantic validation error
        StudyDesign(
            entity_id="DESIGN:invalid",
            name="Invalid design",
            evidence_level=6,  # Out of range
        )


def test_evidence_line_strength_values():
    """Test that evidence line strength accepts valid values"""
    for strength in ["strong", "moderate", "weak"]:
        evidence = EvidenceLine(
            entity_id=f"EVIDENCE:{strength}",
            name=f"Evidence with {strength} strength",
            strength=strength,
        )
        assert evidence.strength == strength

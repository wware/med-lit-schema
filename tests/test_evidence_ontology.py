"""
Tests for enhanced Evidence class with ontology references (ECO, OBI, STATO).

The Evidence class now supports standardized classification of evidence types,
study designs, and statistical methods using biomedical ontology IDs.
"""

from schema.entity import EvidenceItem


def test_evidence_with_eco_type():
    """Test Evidence with ECO (Evidence & Conclusion Ontology) type ID"""
    evidence = EvidenceItem(
        paper_id="PMC999888",
        confidence=0.92,
        eco_type="ECO:0007673",  # RCT evidence
    )

    assert evidence.eco_type == "ECO:0007673"
    assert evidence.paper_id == "PMC999888"


def test_evidence_with_obi_study_design():
    """Test Evidence with OBI (Ontology for Biomedical Investigations) study design ID"""
    evidence = EvidenceItem(
        paper_id="PMC999888",
        confidence=0.85,
        study_type="rct",
        obi_study_design="OBI:0000008",  # Randomized controlled trial
    )

    assert evidence.obi_study_design == "OBI:0000008"
    assert evidence.study_type == "rct"


def test_evidence_with_stato_methods():
    """Test Evidence with STATO (Statistics Ontology) statistical method IDs"""
    evidence = EvidenceItem(
        paper_id="PMC999888",
        confidence=0.88,
        stato_methods=["STATO:0000288", "STATO:0000376"],  # t-test, Kaplan-Meier
    )

    assert len(evidence.stato_methods) == 2
    assert "STATO:0000288" in evidence.stato_methods
    assert "STATO:0000376" in evidence.stato_methods


def test_evidence_with_all_ontology_references():
    """Test Evidence with complete ontology classification"""
    evidence = EvidenceItem(
        paper_id="PMC999888",
        confidence=0.92,
        section_type="results",
        paragraph_idx=8,
        sentence_idx=3,
        text_span="Olaparib showed significant efficacy in BRCA-mutated breast cancer",
        extraction_method="table_parser",
        study_type="rct",
        sample_size=302,
        publication_date="2021-03-15",
        # Ontology references
        eco_type="ECO:0007673",  # RCT evidence
        obi_study_design="OBI:0000008",  # Randomized controlled trial
        stato_methods=["STATO:0000288", "STATO:0000376"],  # t-test, Kaplan-Meier
    )

    # Verify all fields
    assert evidence.paper_id == "PMC999888"
    assert evidence.confidence == 0.92
    assert evidence.study_type == "rct"
    assert evidence.sample_size == 302

    # Verify ontology references
    assert evidence.eco_type == "ECO:0007673"
    assert evidence.obi_study_design == "OBI:0000008"
    assert len(evidence.stato_methods) == 2


def test_evidence_ontology_fields_are_optional():
    """Test that ontology fields are optional and can be omitted"""
    # Evidence without any ontology IDs should still be valid
    evidence = EvidenceItem(
        paper_id="PMC123456",
        confidence=0.7,
        study_type="observational",
    )

    assert evidence.paper_id == "PMC123456"
    assert evidence.eco_type is None
    assert evidence.obi_study_design is None
    assert evidence.stato_methods == []


def test_evidence_eco_hierarchy():
    """Test representing ECO evidence hierarchy"""
    # Different levels of clinical evidence
    rct_evidence = EvidenceItem(
        paper_id="PMC_RCT_001",
        eco_type="ECO:0007673",  # RCT evidence
        confidence=1.0,
    )

    cohort_evidence = EvidenceItem(
        paper_id="PMC_COHORT_001",
        eco_type="ECO:0007674",  # Cohort study evidence
        confidence=0.8,
    )

    case_control_evidence = EvidenceItem(
        paper_id="PMC_CASE_CONTROL_001",
        eco_type="ECO:0007675",  # Case-control study evidence
        confidence=0.6,
    )

    case_report_evidence = EvidenceItem(
        paper_id="PMC_CASE_REPORT_001",
        eco_type="ECO:0007676",  # Case report evidence
        confidence=0.4,
    )

    # Verify different evidence types have appropriate confidence mappings
    assert rct_evidence.confidence > cohort_evidence.confidence
    assert cohort_evidence.confidence > case_control_evidence.confidence
    assert case_control_evidence.confidence > case_report_evidence.confidence


def test_evidence_study_type_to_eco_mapping():
    """Test that study_type field can be mapped to ECO IDs"""
    # Mapping study types to ECO evidence types
    study_type_to_eco = {
        "rct": "ECO:0007673",
        "observational": "ECO:0007674",
        "case_report": "ECO:0007676",
        "meta_analysis": "ECO:0000033",
    }

    for study_type, eco_id in study_type_to_eco.items():
        evidence = EvidenceItem(
            paper_id=f"PMC_{study_type}",
            study_type=study_type,
            eco_type=eco_id,
        )
        assert evidence.study_type == study_type
        assert evidence.eco_type == eco_id


def test_evidence_with_multiple_statistical_methods():
    """Test Evidence can track multiple statistical methods used"""
    evidence = EvidenceItem(
        paper_id="PMC999888",
        confidence=0.90,
        stato_methods=[
            "STATO:0000288",  # t-test
            "STATO:0000039",  # chi-squared test
            "STATO:0000376",  # Kaplan-Meier
            "STATO:0000304",  # Cox proportional hazards
        ],
    )

    assert len(evidence.stato_methods) == 4
    assert "STATO:0000288" in evidence.stato_methods  # t-test
    assert "STATO:0000304" in evidence.stato_methods  # Cox model


def test_evidence_serialization_with_ontology_ids():
    """Test that Evidence with ontology IDs can be serialized/deserialized"""
    evidence = EvidenceItem(
        paper_id="PMC999888",
        confidence=0.92,
        eco_type="ECO:0007673",
        obi_study_design="OBI:0000008",
        stato_methods=["STATO:0000288"],
    )

    # Serialize to dict
    data = evidence.model_dump()

    # Verify ontology fields are in the dict
    assert data["eco_type"] == "ECO:0007673"
    assert data["obi_study_design"] == "OBI:0000008"
    assert "STATO:0000288" in data["stato_methods"]

    # Deserialize back
    evidence2 = EvidenceItem.model_validate(data)
    assert evidence2.eco_type == evidence.eco_type
    assert evidence2.obi_study_design == evidence.obi_study_design
    assert evidence2.stato_methods == evidence.stato_methods


def test_evidence_empty_stato_methods_list():
    """Test that stato_methods defaults to empty list"""
    evidence = EvidenceItem(
        paper_id="PMC123",
        confidence=0.5,
    )

    assert evidence.stato_methods == []
    assert isinstance(evidence.stato_methods, list)

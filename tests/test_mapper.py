"""
Tests for mapper functions converting between domain and persistence models.
"""

import json
import pytest

from med_lit_schema.entity import (
    Disease,
    Gene,
    Drug,
    Protein,
    Mutation,
    Symptom,
    Biomarker,
    Pathway,
    Procedure,
    Hypothesis,
    StudyDesign,
    StatisticalMethod,
    EvidenceLine,
    EntityType,
)
from med_lit_schema.storage.models.entity import Entity
from med_lit_schema.mapper import to_persistence, to_domain


def test_disease_roundtrip():
    """Test domain → persistence → domain conversion for Disease."""
    # Create domain model
    disease = Disease(
        entity_id="C0006142",
        entity_type=EntityType.DISEASE,
        name="Breast Cancer",
        synonyms=["Breast Carcinoma", "Mammary Cancer"],
        abbreviations=["BC"],
        umls_id="C0006142",
        mesh_id="D001943",
        icd10_codes=["C50.9"],
        category="genetic",
        source="umls",
    )

    # Convert to persistence
    entity = to_persistence(disease)
    assert entity.id == "C0006142"
    assert entity.entity_type == "disease"
    assert entity.name == "Breast Cancer"
    assert json.loads(entity.synonyms) == ["Breast Carcinoma", "Mammary Cancer"]
    assert entity.umls_id == "C0006142"

    # Convert back to domain
    disease2 = to_domain(entity)
    assert isinstance(disease2, Disease)
    assert disease2.entity_id == disease.entity_id
    assert disease2.name == disease.name
    assert disease2.synonyms == disease.synonyms
    assert disease2.umls_id == disease.umls_id
    assert disease2 == disease


def test_gene_roundtrip():
    """Test domain → persistence → domain conversion for Gene."""
    gene = Gene(
        entity_id="HGNC:1100",
        entity_type=EntityType.GENE,
        name="BRCA1",
        symbol="BRCA1",
        hgnc_id="HGNC:1100",
        chromosome="17q21.31",
        source="hgnc",
    )

    entity = to_persistence(gene)
    gene2 = to_domain(entity)

    assert isinstance(gene2, Gene)
    assert gene2.entity_id == gene.entity_id
    assert gene2.symbol == gene.symbol
    assert gene2 == gene


def test_drug_roundtrip():
    """Test domain → persistence → domain conversion for Drug."""
    drug = Drug(
        entity_id="RxNorm:1187832",
        name="Olaparib",
        synonyms=["AZD2281"],
        rxnorm_id="1187832",
        brand_names=["Lynparza"],
        drug_class="PARP inhibitor",
        mechanism="Inhibits poly ADP-ribose polymerase enzymes",
    )

    entity = to_persistence(drug)
    drug2 = to_domain(entity)

    assert isinstance(drug2, Drug)
    assert drug2.entity_id == drug.entity_id
    assert drug2.rxnorm_id == drug.rxnorm_id
    assert drug2 == drug


def test_protein_roundtrip():
    """Test domain → persistence → domain conversion for Protein."""
    protein = Protein(
        entity_id="P38398",
        name="Breast cancer type 1 susceptibility protein",
        synonyms=["BRCA1"],
        uniprot_id="P38398",
        gene_id="HGNC:1100",
        function="DNA repair and tumor suppression",
        pathways=["DNA damage response", "Homologous recombination"],
    )

    entity = to_persistence(protein)
    protein2 = to_domain(entity)

    assert isinstance(protein2, Protein)
    assert protein2.entity_id == protein.entity_id
    assert protein2.uniprot_id == protein.uniprot_id
    assert protein2 == protein


def test_mutation_roundtrip():
    """Test domain → persistence → domain conversion for Mutation."""
    mutation = Mutation(
        entity_id="MUT:BRCA1_c.5266dupC",
        name="BRCA1 c.5266dupC",
        gene_id="HGNC:1100",
        variant_type="Insertion",
        notation="c.5266dupC",
        consequence="Frameshift",
    )

    entity = to_persistence(mutation)
    mutation2 = to_domain(entity)

    assert isinstance(mutation2, Mutation)
    assert mutation2.entity_id == mutation.entity_id
    assert mutation2.gene_id == mutation.gene_id
    assert mutation2 == mutation


def test_symptom_roundtrip():
    """Test domain → persistence → domain conversion for Symptom."""
    symptom = Symptom(
        entity_id="SYMP:C0015672",
        name="Fatigue",
        severity_scale="Mild, Moderate, Severe",
    )

    entity = to_persistence(symptom)
    symptom2 = to_domain(entity)

    assert isinstance(symptom2, Symptom)
    assert symptom2.entity_id == symptom.entity_id
    assert symptom2.severity_scale == symptom.severity_scale
    assert symptom2 == symptom


def test_procedure_roundtrip():
    """Test domain → persistence → domain conversion for Procedure."""
    procedure = Procedure(
        entity_id="PROC:C0005435",
        name="Biopsy",
        type="Diagnostic",
        invasiveness="Minimally invasive",
    )

    entity = to_persistence(procedure)
    procedure2 = to_domain(entity)

    assert isinstance(procedure2, Procedure)
    assert procedure2.entity_id == procedure.entity_id
    assert procedure2.type == procedure.type
    assert procedure2 == procedure


def test_biomarker_roundtrip():
    """Test domain → persistence → domain conversion for Biomarker."""
    biomarker = Biomarker(
        entity_id="BIOM:LN12345",
        name="Prostate-Specific Antigen",
        loinc_code="12345-6",
        measurement_type="Blood",
        normal_range="<4 ng/mL",
    )

    entity = to_persistence(biomarker)
    biomarker2 = to_domain(entity)

    assert isinstance(biomarker2, Biomarker)
    assert biomarker2.entity_id == biomarker.entity_id
    assert biomarker2.loinc_code == biomarker.loinc_code
    assert biomarker2 == biomarker


def test_pathway_roundtrip():
    """Test domain → persistence → domain conversion for Pathway."""
    pathway = Pathway(
        entity_id="PATH:hsa04110",
        name="Cell cycle",
        kegg_id="hsa04110",
        reactome_id="R-HSA-1640170",
        category="signaling",
        genes_involved=["HGNC:1100", "HGNC:1101"],
    )

    entity = to_persistence(pathway)
    pathway2 = to_domain(entity)

    assert isinstance(pathway2, Pathway)
    assert pathway2.entity_id == pathway.entity_id
    assert pathway2.kegg_id == pathway.kegg_id
    assert pathway2 == pathway


def test_hypothesis_roundtrip():
    """Test domain → persistence → domain conversion for Hypothesis."""
    hypothesis = Hypothesis(
        entity_id="HYP:001",
        name="Amyloid cascade hypothesis",
        description="The amyloid cascade hypothesis postulates that the deposition of amyloid-β is the causative agent in Alzheimer's disease.",
        predicts=["C0002395"],
    )

    entity = to_persistence(hypothesis)
    hypothesis2 = to_domain(entity)

    assert isinstance(hypothesis2, Hypothesis)
    assert hypothesis2.entity_id == hypothesis.entity_id
    assert hypothesis2.description == hypothesis.description
    assert hypothesis2 == hypothesis


def test_study_design_roundtrip():
    """Test domain → persistence → domain conversion for StudyDesign."""
    study_design = StudyDesign(
        entity_id="OBI:0000008",
        name="Randomized Controlled Trial",
        description="A study in which a number of similar people are randomly assigned to 2 or more groups to test a specific drug, treatment, or other intervention.",
    )

    entity = to_persistence(study_design)
    study_design2 = to_domain(entity)

    assert isinstance(study_design2, StudyDesign)
    assert study_design2.entity_id == study_design.entity_id
    assert study_design2.description == study_design.description
    assert study_design2 == study_design


def test_statistical_method_roundtrip():
    """Test domain → persistence → domain conversion for StatisticalMethod."""
    stat_method = StatisticalMethod(
        entity_id="STATO:0000288",
        name="Student's t-test",
        description="A statistical test that is used to compare the means of two groups.",
        assumptions=[
            "The two samples are independent.",
            "The data in each group are approximately normally distributed.",
        ],
    )

    entity = to_persistence(stat_method)
    stat_method2 = to_domain(entity)

    assert isinstance(stat_method2, StatisticalMethod)
    assert stat_method2.entity_id == stat_method.entity_id
    assert stat_method2.description == stat_method.description
    assert stat_method2 == stat_method


def test_evidence_line_roundtrip():
    """Test domain → persistence → domain conversion for EvidenceLine."""
    evidence_line = EvidenceLine(
        entity_id="EV:001",
        name="Evidence for Drug X treating Disease Y",
        supports=["HYP:001"],
        refutes=[],
        evidence_items=["PMC12345", "PMC67890"],
    )

    entity = to_persistence(evidence_line)
    evidence_line2 = to_domain(entity)

    assert isinstance(evidence_line2, EvidenceLine)
    assert evidence_line2.entity_id == evidence_line.entity_id
    assert evidence_line2.supports == evidence_line.supports
    assert evidence_line2 == evidence_line


def test_json_array_handling():
    """Test that arrays are properly serialized/deserialized."""
    disease = Disease(
        entity_id="C0001",
        entity_type=EntityType.DISEASE,
        name="Test Disease",
        synonyms=["Syn1", "Syn2", "Syn3"],
        abbreviations=["TD"],
        icd10_codes=["C01", "C02"],
    )

    entity = to_persistence(disease)

    # Check JSON strings are valid
    assert isinstance(entity.synonyms, str)
    assert json.loads(entity.synonyms) == ["Syn1", "Syn2", "Syn3"]

    # Round-trip preserves arrays
    disease2 = to_domain(entity)
    assert disease2.synonyms == disease.synonyms
    assert disease2.icd10_codes == disease.icd10_codes


def test_empty_arrays():
    """Test handling of empty arrays."""
    disease = Disease(
        entity_id="C0002",
        entity_type=EntityType.DISEASE,
        name="Test",
        synonyms=[],
        abbreviations=[],
    )  # Empty  # Empty

    entity = to_persistence(disease)
    disease2 = to_domain(entity)

    assert disease2.synonyms == []
    assert disease2.abbreviations == []


def test_unknown_entity_type():
    """Test error handling for unknown entity types."""
    entity = Entity(id="UNKNOWN:123", entity_type="unknown_type", name="Unknown")

    with pytest.raises(ValueError, match="Unknown entity type"):
        to_domain(entity)


# ============================================================================
# Note: Row Object Handling Tests
# ============================================================================
# The mapper was updated in Z.diff to handle SQLAlchemy Row objects in addition
# to Pydantic model instances. Comprehensive tests for Row handling are in:
#   tests/test_mapper_row_handling.py
#
# Those tests cover:
# - Handling Row objects with .Entity attribute
# - Handling Row objects with ._mapping dict
# - Handling tuple/list-like Row objects
# - Relationship Row objects
# - NULL predicate error handling
# - Integration tests with actual storage queries
#
# TODO: Consider adding type annotations to all mapper functions
# TODO: Add docstrings with Args/Returns for mapper functions

"""
Tests for provenance ingest including XML parsing.

Tests the full ingest with representative fake papers.

Run with: uv run pytest tests/test_provenance_ingest.py -v
"""

import pytest
from pathlib import Path
from tempfile import TemporaryDirectory

from med_lit_schema.entity import (
    Disease,
    Gene,
    Drug,
    EntityType,
    EvidenceItem,
    Paper,
    PaperMetadata,
)
from med_lit_schema.relationship import create_relationship
from med_lit_schema.base import PredicateType
from med_lit_schema.storage.backends.sqlite import SQLitePipelineStorage


def create_fake_pmc_xml(
    paper_id: str,
    title: str,
    abstract: str,
    authors: list[str],
    journal: str,
    pub_date: str,
    pmid: str = None,
    doi: str = None,
) -> str:
    """
    Create a fake PMC XML file content for testing.

    Attributes:

        paper_id: PMC identifier
        title: Article title
        abstract: Article abstract
        authors: List of author names in format "Last, First"
        journal: Journal name
        pub_date: Publication date in YYYY-MM-DD format
        pmid: Optional PubMed ID
        doi: Optional DOI

    """
    xml_template = f"""<?xml version="1.0" encoding="UTF-8"?>
<pmc-articleset>
<article xmlns:xlink="http://www.w3.org/1999/xlink">
  <front>
    <article-meta>
      <article-id pub-id-type="pmcid">{paper_id}</article-id>
      {f'<article-id pub-id-type="pmid">{pmid}</article-id>' if pmid else ""}
      {f'<article-id pub-id-type="doi">{doi}</article-id>' if doi else ""}
      <title-group>
        <article-title>{title}</article-title>
      </title-group>
      <contrib-group>
        {"".join([f'<contrib contrib-type="author"><name><surname>{a.split(", ")[0]}</surname><given-names>{a.split(", ")[1] if ", " in a else ""}</given-names></name></contrib>' for a in authors])}
      </contrib-group>
      <pub-date pub-type="ppub">
        <year>{pub_date.split("-")[0]}</year>
        <month>{pub_date.split("-")[1]}</month>
        <day>{pub_date.split("-")[2]}</day>
      </pub-date>
      <abstract>
        <p>{abstract}</p>
      </abstract>
    </article-meta>
    <journal-meta>
      <journal-title>{journal}</journal-title>
    </journal-meta>
  </front>
  <body>
    <sec>
      <title>Introduction</title>
      <p>This study investigates the relationship between BRCA1 mutations and breast cancer.</p>
    </sec>
    <sec>
      <title>Methods</title>
      <p>We analyzed 302 patients with BRCA1 mutations using next-generation sequencing.</p>
    </sec>
    <sec>
      <title>Results</title>
      <p>Olaparib treatment significantly improved progression-free survival in BRCA-mutated breast cancer patients. The drug inhibits PARP enzymes and causes synthetic lethality in BRCA-deficient cells.</p>
    </sec>
    <sec>
      <title>Discussion</title>
      <p>Our findings demonstrate that PARP inhibitors like olaparib are effective treatments for BRCA-mutated cancers.</p>
    </sec>
  </body>
</article>
</pmc-articleset>"""
    return xml_template


@pytest.fixture
def tmp_storage():
    """Create a temporary database and directory for testing."""
    with TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        storage = SQLitePipelineStorage(db_path)
        yield storage, Path(tmpdir)
        storage.close()


def test_xml_parsing_with_full_metadata():
    """Test parsing PMC XML with complete metadata."""
    from med_lit_schema.ingest.provenance_pipeline import parse_pmc_xml

    with TemporaryDirectory() as tmpdir:
        xml_dir = Path(tmpdir)

        # Create fake PMC XML with full metadata
        paper_xml = create_fake_pmc_xml(
            paper_id="PMC999999",
            title="Efficacy of Olaparib in BRCA-Mutated Breast Cancer",
            abstract="Background: PARP inhibitors have shown promise in treating BRCA-mutated cancers. Methods: We conducted a randomized controlled trial of 302 patients. Results: Olaparib significantly improved progression-free survival compared to placebo.",
            authors=["Smith, John", "Johnson, Alice", "Williams, Bob"],
            journal="New England Journal of Medicine",
            pub_date="2023-06-15",
            pmid="34567890",
            doi="10.1234/nejm.2023.001",
        )

        xml_path = xml_dir / "PMC999999.xml"
        xml_path.write_text(paper_xml)

        # Parse the XML
        paper = parse_pmc_xml(xml_path)

        # Assertions
        assert paper is not None
        assert paper.paper_id == "PMC999999"
        assert "Olaparib" in paper.title
        assert len(paper.authors) == 3
        assert paper.journal == "New England Journal of Medicine"
        assert paper.publication_date == "2023-06-15"


def test_xml_parsing_minimal_metadata():
    """Test parsing PMC XML with minimal metadata."""
    from med_lit_schema.ingest.provenance_pipeline import parse_pmc_xml

    with TemporaryDirectory() as tmpdir:
        xml_dir = Path(tmpdir)

        # Create fake PMC XML with minimal metadata
        paper_xml = create_fake_pmc_xml(
            paper_id="PMC888888",
            title="HIV Infection and AIDS Development",
            abstract="This study examines the relationship between HIV infection and the development of AIDS.",
            authors=["Brown, Mary", "Davis, Robert"],
            journal="Nature Medicine",
            pub_date="2022-03-20",
        )

        xml_path = xml_dir / "PMC888888.xml"
        xml_path.write_text(paper_xml)

        # Parse the XML
        paper = parse_pmc_xml(xml_path)

        # Assertions
        assert paper is not None
        assert paper.paper_id == "PMC888888"
        assert "HIV" in paper.title
        assert len(paper.authors) == 2


def test_paper_storage_after_parsing(tmp_storage):
    """Test storing parsed papers in the database."""
    storage, _ = tmp_storage
    from med_lit_schema.ingest.provenance_pipeline import parse_pmc_xml

    with TemporaryDirectory() as tmpdir:
        xml_dir = Path(tmpdir)

        # Create and parse two papers
        paper1_xml = create_fake_pmc_xml(
            paper_id="PMC999999",
            title="Efficacy of Olaparib in BRCA-Mutated Breast Cancer",
            abstract="Background: PARP inhibitors have shown promise.",
            authors=["Smith, John", "Johnson, Alice"],
            journal="NEJM",
            pub_date="2023-06-15",
        )

        paper2_xml = create_fake_pmc_xml(
            paper_id="PMC888888",
            title="HIV Infection and AIDS Development",
            abstract="This study examines HIV and AIDS.",
            authors=["Brown, Mary"],
            journal="Nature Medicine",
            pub_date="2022-03-20",
        )

        (xml_dir / "PMC999999.xml").write_text(paper1_xml)
        (xml_dir / "PMC888888.xml").write_text(paper2_xml)

        paper1 = parse_pmc_xml(xml_dir / "PMC999999.xml")
        paper2 = parse_pmc_xml(xml_dir / "PMC888888.xml")

        # Store papers
        storage.papers.add_paper(paper1)
        storage.papers.add_paper(paper2)

        # Verify storage
        assert storage.papers.paper_count == 2

        # Verify retrieval
        retrieved1 = storage.papers.get_paper("PMC999999")
        assert retrieved1 is not None
        assert len(retrieved1.authors) == 2

        retrieved2 = storage.papers.get_paper("PMC888888")
        assert retrieved2 is not None
        assert len(retrieved2.authors) == 1


def test_entity_extraction_and_storage(tmp_storage):
    """Test entity extraction and storage."""
    storage, _ = tmp_storage
    # Create and store various entity types
    breast_cancer = Disease(
        entity_id="C0006142",
        entity_type=EntityType.DISEASE,
        name="Breast Cancer",
        synonyms=["Breast Carcinoma"],
        source="umls",
    )
    storage.entities.add_disease(breast_cancer)

    brca1 = Gene(
        entity_id="HGNC:1100",
        entity_type=EntityType.GENE,
        name="BRCA1",
        synonyms=["BRCA1 gene"],
        hgnc_id="HGNC:1100",
        source="hgnc",
    )
    storage.entities.add_gene(brca1)

    olaparib = Drug(
        entity_id="RxNorm:1187832",
        entity_type=EntityType.DRUG,
        name="Olaparib",
        synonyms=["Lynparza"],
        rxnorm_id="RxNorm:1187832",
        source="rxnorm",
    )
    storage.entities.add_drug(olaparib)

    # Verify count
    assert storage.entities.entity_count == 3

    # Test retrieval by different methods
    retrieved_disease = storage.entities.get_by_id("C0006142")
    assert retrieved_disease is not None
    assert retrieved_disease.name == "Breast Cancer"

    retrieved_gene = storage.entities.get_by_hgnc("HGNC:1100")
    assert retrieved_gene is not None
    assert retrieved_gene.name == "BRCA1"


def test_relationships_with_papers(tmp_storage):
    """Test relationship storage and linking to papers."""
    storage, _ = tmp_storage
    # Create relationships
    treats_rel = create_relationship(
        predicate=PredicateType.TREATS,
        subject_id="RxNorm:1187832",  # Olaparib
        object_id="C0006142",  # Breast Cancer
        confidence=0.95,
        source_papers=["PMC999999"],
    )
    storage.relationships.add_relationship(treats_rel)

    risk_rel = create_relationship(
        predicate=PredicateType.INCREASES_RISK,
        subject_id="HGNC:1100",  # BRCA1
        object_id="C0006142",  # Breast Cancer
        confidence=0.9,
        source_papers=["PMC999999"],
    )
    storage.relationships.add_relationship(risk_rel)

    # Verify count
    assert storage.relationships.relationship_count == 2

    # Test retrieval
    retrieved = storage.relationships.get_relationship("RxNorm:1187832", "treats", "C0006142")
    assert retrieved is not None
    assert retrieved.confidence == 0.95
    assert "PMC999999" in retrieved.source_papers

    # Test finding relationships
    all_treats = storage.relationships.find_relationships(predicate="treats")
    assert len(all_treats) == 1

    breast_cancer_rels = storage.relationships.find_relationships(object_id="C0006142")
    assert len(breast_cancer_rels) == 2


def test_evidence_linking(tmp_storage):
    """Test evidence storage and linking to papers."""
    storage, _ = tmp_storage
    # Create evidence
    evidence1 = EvidenceItem(
        paper_id="PMC999999",
        confidence=0.9,
        section_type="results",
        text_span="Olaparib treatment significantly improved progression-free survival",
        study_type="rct",
        sample_size=302,
    )
    storage.evidence.add_evidence(evidence1)

    evidence2 = EvidenceItem(
        paper_id="PMC999999",
        confidence=0.85,
        section_type="discussion",
        text_span="PARP inhibitors are effective treatments",
        study_type="rct",
        sample_size=302,
    )
    storage.evidence.add_evidence(evidence2)

    # Verify count
    assert storage.evidence.evidence_count >= 2

    # Test retrieval by paper
    evidence_list = storage.evidence.get_evidence_by_paper("PMC999999")
    assert len(evidence_list) >= 2
    assert all(e.paper_id == "PMC999999" for e in evidence_list)


def test_complete_provenance_flow(tmp_storage):
    """Test complete end-to-end provenance flow from XML to storage."""
    storage, _ = tmp_storage
    from med_lit_schema.ingest.provenance_pipeline import parse_pmc_xml

    with TemporaryDirectory() as tmpdir:
        xml_dir = Path(tmpdir)

        # Step 1: Create and parse XML
        paper_xml = create_fake_pmc_xml(
            paper_id="PMC111111",
            title="Complete Provenance Test Paper",
            abstract="Testing complete provenance flow.",
            authors=["Test, Author"],
            journal="Test Journal",
            pub_date="2024-01-01",
            pmid="11111111",
            doi="10.1111/test.2024.001",
        )

        xml_path = xml_dir / "PMC111111.xml"
        xml_path.write_text(paper_xml)

        paper = parse_pmc_xml(xml_path)

        # Step 2: Store paper
        storage.papers.add_paper(paper)

        # Step 3: Create and store entities
        disease = Disease(entity_id="C0001", entity_type=EntityType.DISEASE, name="Test Disease", source="umls")
        storage.entities.add_disease(disease)

        # Step 4: Create and store relationship
        relationship = create_relationship(
            predicate=PredicateType.ASSOCIATED_WITH,
            subject_id="C0001",
            object_id="C0001",
            confidence=0.8,
            source_papers=["PMC111111"],
        )
        storage.relationships.add_relationship(relationship)

        # Step 5: Create and store evidence
        evidence = EvidenceItem(
            paper_id="PMC111111",
            confidence=0.8,
            section_type="results",
            text_span="Test evidence text",
            study_type="observational",
            sample_size=100,
        )
        storage.evidence.add_evidence(evidence)

        # Verify complete provenance chain
        assert storage.papers.paper_count >= 1
        assert storage.entities.entity_count >= 1
        assert storage.relationships.relationship_count >= 1
        assert storage.evidence.evidence_count >= 1

        # Verify links
        retrieved_paper = storage.papers.get_paper("PMC111111")
        assert retrieved_paper is not None
        assert retrieved_paper.extraction_provenance is not None

        retrieved_rel = storage.relationships.get_relationship("C0001", "associated_with", "C0001")
        assert "PMC111111" in retrieved_rel.source_papers


# ============================================================================
# Optional Provenance Tests (added for Z.diff regression testing)
# ============================================================================


def test_paper_without_provenance(tmp_storage):
    """
    Test that Paper can be created and stored without extraction_provenance.

    The Paper model was updated in Z.diff to make extraction_provenance optional.
    This test ensures the provenance ingest pipeline handles this correctly.
    """
    storage, xml_dir = tmp_storage

    # Create paper without provenance
    paper = Paper(
        paper_id="PMC_NO_PROV",
        title="Paper Without Provenance",
        abstract="Test abstract",
        authors=["Test, Author"],
        publication_date="2024-01-01",
        journal="Test Journal",
        entities=[],
        relationships=[],
        metadata=PaperMetadata(pmc_id="PMC_NO_PROV"),
        extraction_provenance=None,  # Explicitly None
    )

    # Should be able to store it
    storage.papers.add_paper(paper)

    # Should be able to retrieve it
    retrieved = storage.papers.get_paper("PMC_NO_PROV")
    assert retrieved is not None
    assert retrieved.paper_id == "PMC_NO_PROV"
    assert retrieved.extraction_provenance is None


def test_paper_provenance_field_is_optional():
    """
    Test that extraction_provenance field is optional in Paper model.

    This is a schema-level test to verify the field definition.
    """
    from med_lit_schema.entity import Paper

    # Check field definition
    schema = Paper.model_json_schema()

    # extraction_provenance should not be in required fields
    required = schema.get("required", [])
    assert "extraction_provenance" not in required

    # Field should be defined in properties
    properties = schema.get("properties", {})
    assert "extraction_provenance" in properties


def test_provenance_ingest_mixed_papers():
    """
    Test ingesting multiple papers with mixed provenance (some with, some without).

    This simulates a real-world scenario where some papers have provenance
    tracking and others don't.
    """
    storage = SQLitePipelineStorage(":memory:")

    # Paper 1: With provenance
    from med_lit_schema.entity import ExtractionProvenance, ExtractionPipelineInfo, ExecutionInfo, PromptInfo
    from datetime import datetime
    import socket
    import platform

    pipeline_info = ExtractionPipelineInfo(name="test", version="1.0.0", git_commit="abc", git_commit_short="abc", git_branch="main", git_dirty=False, repo_url="https://test.com")

    execution_info = ExecutionInfo(
        timestamp=datetime.now().isoformat(),
        hostname=socket.gethostname(),
        python_version=platform.python_version(),
        duration_seconds=10,
    )

    provenance = ExtractionProvenance(
        extraction_pipeline=pipeline_info,
        models={},
        prompt=PromptInfo(version="v1", template="test", checksum=None),
        execution=execution_info,
        entity_resolution=None,
    )

    paper1 = Paper(
        paper_id="PMC_WITH",
        title="With Provenance",
        abstract="Test",
        authors=["Test"],
        publication_date="2024-01-01",
        journal="Test",
        entities=[],
        relationships=[],
        metadata=PaperMetadata(),
        extraction_provenance=provenance,
    )

    # Paper 2: Without provenance
    paper2 = Paper(
        paper_id="PMC_WITHOUT",
        title="Without Provenance",
        abstract="Test",
        authors=["Test"],
        publication_date="2024-01-01",
        journal="Test",
        entities=[],
        relationships=[],
        metadata=PaperMetadata(),
        extraction_provenance=None,
    )

    # Store both
    storage.papers.add_paper(paper1)
    storage.papers.add_paper(paper2)

    # Verify both are stored correctly
    retrieved1 = storage.papers.get_paper("PMC_WITH")
    assert retrieved1.extraction_provenance is not None

    retrieved2 = storage.papers.get_paper("PMC_WITHOUT")
    assert retrieved2.extraction_provenance is None

    assert storage.papers.paper_count == 2

    storage.close()


# TODO: Add tests for provenance pipeline context manager support
# The provenance pipeline was refactored to use context managers in Z.diff
# Consider adding tests like:
# - test_provenance_pipeline_uses_context_manager()
# - test_provenance_pipeline_closes_storage_on_error()

# TODO: Add tests for JSON output directory feature
# The provenance pipeline gained --json-output-dir flag in Z.diff
# Consider adding tests like:
# - test_provenance_pipeline_saves_json_output()
# - test_json_output_contains_all_paper_fields()

# TODO: Add performance tests for large XML batches
# Test provenance pipeline performance with 100+ XML files

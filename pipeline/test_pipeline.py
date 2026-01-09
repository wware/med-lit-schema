#!/usr/bin/env -S uv run python
"""
Test script for pipeline using in-memory SQLite.

Tests the full pipeline with representative fake papers.

Run with: ./pipeline/test_pipeline.py
Or: uv run python pipeline/test_pipeline.py
"""

from pathlib import Path
from tempfile import TemporaryDirectory

# Import pipeline components
from med_lit_schema.pipeline.storage_interfaces import PipelineStorageInterface
from med_lit_schema.pipeline.sqlite_storage import SQLitePipelineStorage
from med_lit_schema.entity import Paper, Disease, Drug, EntityType
from med_lit_schema.relationship import create_relationship
from med_lit_schema.base import PredicateType


def create_fake_pmc_xml(paper_id: str, title: str, abstract: str, authors: list[str], journal: str, pub_date: str, pmid: str = None, doi: str = None) -> str:
    """Create a fake PMC XML file content."""
    xml_template = f"""<?xml version="1.0" encoding="UTF-8"?>
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
</article>"""
    return xml_template


def test_storage_interfaces():
    """Test basic storage interface functionality."""
    print("=" * 60)
    print("Testing Storage Interfaces")
    print("=" * 60)

    # Create in-memory SQLite storage
    # Note: SQLitePipelineStorage expects a Path, but we can use a temporary file
    # or modify it to accept ":memory:" - for now, use a temp file
    from tempfile import NamedTemporaryFile

    with NamedTemporaryFile(delete=False, suffix=".db") as tmp:
        db_path = Path(tmp.name)

    try:
        storage: PipelineStorageInterface = SQLitePipelineStorage(db_path)

        # Test 1: Entity storage
        print("\n1. Testing Entity Storage...")
        disease = Disease(entity_id="C0006142", entity_type=EntityType.DISEASE, name="Breast Cancer", synonyms=["Breast Carcinoma", "Mammary Carcinoma"], source="umls")
        storage.entities.add_disease(disease)

        retrieved = storage.entities.get_by_id("C0006142")
        assert retrieved is not None, "Failed to retrieve disease"
        assert retrieved.name == "Breast Cancer", "Disease name mismatch"
        print(f"   ✓ Stored and retrieved: {retrieved.name}")

        # Test 2: Paper storage
        print("\n2. Testing Paper Storage...")
        from med_lit_schema.entity import PaperMetadata, ExtractionProvenance, ExtractionPipelineInfo, ExecutionInfo
        from datetime import datetime
        import socket
        import platform

        paper = Paper(
            paper_id="PMC123456",
            title="Test Paper on Breast Cancer",
            abstract="This is a test abstract about breast cancer treatment.",
            authors=["Smith, John", "Doe, Jane"],
            publication_date="2023-06-15",
            journal="Test Journal",
            entities=[],
            relationships=[],
            metadata=PaperMetadata(),
            extraction_provenance=ExtractionProvenance(
                extraction_pipeline=ExtractionPipelineInfo(
                    name="test", version="1.0.0", git_commit="abc123", git_commit_short="abc123", git_branch="main", git_dirty=False, repo_url="https://test.com"
                ),
                models={},
                prompt=None,
                execution=ExecutionInfo(timestamp=datetime.now().isoformat(), hostname=socket.gethostname(), python_version=platform.python_version(), duration_seconds=None),
                entity_resolution=None,
            ),
        )
        storage.papers.add_paper(paper)

        retrieved_paper = storage.papers.get_paper("PMC123456")
        assert retrieved_paper is not None, "Failed to retrieve paper"
        assert retrieved_paper.title == "Test Paper on Breast Cancer", "Paper title mismatch"
        print(f"   ✓ Stored and retrieved: {retrieved_paper.title}")

        # Test 3: Relationship storage
        print("\n3. Testing Relationship Storage...")
        relationship = create_relationship(
            predicate=PredicateType.TREATS,
            subject_id="RxNorm:1187832",  # Olaparib
            object_id="C0006142",  # Breast Cancer
            confidence=0.95,
            source_papers=["PMC123456"],
        )
        storage.relationships.add_relationship(relationship)

        retrieved_rel = storage.relationships.get_relationship("RxNorm:1187832", "treats", "C0006142")
        assert retrieved_rel is not None, "Failed to retrieve relationship"
        assert retrieved_rel.confidence == 0.95, "Relationship confidence mismatch"
        print(f"   ✓ Stored and retrieved relationship: {retrieved_rel.predicate.value}")

        # Test 4: Evidence storage
        print("\n4. Testing Evidence Storage...")
        from med_lit_schema.entity import EvidenceItem

        evidence = EvidenceItem(
            paper_id="PMC123456", confidence=0.9, section_type="results", text_span="Olaparib treatment significantly improved progression-free survival", study_type="rct", sample_size=302
        )
        storage.evidence.add_evidence(evidence)

        evidence_list = storage.evidence.get_evidence_by_paper("PMC123456")
        assert len(evidence_list) > 0, "Failed to retrieve evidence"
        print(f"   ✓ Stored and retrieved {len(evidence_list)} evidence item(s)")

        # Test 5: Counts
        print("\n5. Testing Counts...")
        print(f"   Entities: {storage.entities.entity_count}")
        print(f"   Papers: {storage.papers.paper_count}")
        print(f"   Relationships: {storage.relationships.relationship_count}")
        print(f"   Evidence: {storage.evidence.evidence_count}")

        storage.close()
        print("\n✓ All storage interface tests passed!")
        return True

    except Exception as e:
        print(f"\n✗ Test failed: {e}")
        import traceback

        traceback.print_exc()
        return False
    finally:
        # Clean up temp file
        if db_path.exists():
            db_path.unlink()


def test_provenance_pipeline():
    """Test provenance pipeline with fake papers."""
    print("\n" + "=" * 60)
    print("Testing Provenance Pipeline")
    print("=" * 60)

    from tempfile import NamedTemporaryFile

    with NamedTemporaryFile(delete=False, suffix=".db") as tmp:
        db_path = Path(tmp.name)

    try:
        storage = SQLitePipelineStorage(db_path)

        # Create fake PMC XML files
        with TemporaryDirectory() as tmpdir:
            xml_dir = Path(tmpdir)

            # Paper 1: Olaparib and BRCA
            paper1_xml = create_fake_pmc_xml(
                paper_id="PMC999999",
                title="Efficacy of Olaparib in BRCA-Mutated Breast Cancer",
                abstract="Background: PARP inhibitors have shown promise in treating BRCA-mutated cancers. Methods: We conducted a randomized controlled trial of 302 patients. Results: Olaparib significantly improved progression-free survival compared to placebo.",
                authors=["Smith, John", "Johnson, Alice", "Williams, Bob"],
                journal="New England Journal of Medicine",
                pub_date="2023-06-15",
                pmid="34567890",
                doi="10.1234/nejm.2023.001",
            )

            # Paper 2: HIV and AIDS
            paper2_xml = create_fake_pmc_xml(
                paper_id="PMC888888",
                title="HIV Infection and AIDS Development",
                abstract="This study examines the relationship between HIV infection and the development of AIDS. We found that HIV causes AIDS through depletion of CD4+ T cells.",
                authors=["Brown, Mary", "Davis, Robert"],
                journal="Nature Medicine",
                pub_date="2022-03-20",
                pmid="23456789",
                doi="10.5678/natmed.2022.002",
            )

            # Write XML files
            (xml_dir / "PMC999999.xml").write_text(paper1_xml)
            (xml_dir / "PMC888888.xml").write_text(paper2_xml)

            # Test parsing
            print("\n1. Testing XML Parsing...")
            from med_lit_schema.pipeline.provenance_pipeline import parse_pmc_xml

            paper1 = parse_pmc_xml(xml_dir / "PMC999999.xml")
            assert paper1 is not None, "Failed to parse paper 1"
            assert paper1.paper_id == "PMC999999", "Paper ID mismatch"
            assert "Olaparib" in paper1.title, "Title mismatch"
            print(f"   ✓ Parsed paper 1: {paper1.title[:50]}...")

            paper2 = parse_pmc_xml(xml_dir / "PMC888888.xml")
            assert paper2 is not None, "Failed to parse paper 2"
            assert paper2.paper_id == "PMC888888", "Paper ID mismatch"
            print(f"   ✓ Parsed paper 2: {paper2.title[:50]}...")

            # Test storage
            print("\n2. Testing Paper Storage...")
            storage.papers.add_paper(paper1)
            storage.papers.add_paper(paper2)

            assert storage.papers.paper_count == 2, "Paper count mismatch"
            print(f"   ✓ Stored {storage.papers.paper_count} papers")

            # Test retrieval
            retrieved1 = storage.papers.get_paper("PMC999999")
            assert retrieved1 is not None, "Failed to retrieve paper 1"
            assert len(retrieved1.authors) == 3, "Author count mismatch"
            print(f"   ✓ Retrieved paper with {len(retrieved1.authors)} authors")

        storage.close()
        print("\n✓ Provenance pipeline tests passed!")
        return True

    except Exception as e:
        print(f"\n✗ Test failed: {e}")
        import traceback

        traceback.print_exc()
        return False
    finally:
        if db_path.exists():
            db_path.unlink()


def test_entity_extraction():
    """Test entity extraction and storage."""
    print("\n" + "=" * 60)
    print("Testing Entity Extraction")
    print("=" * 60)

    from tempfile import NamedTemporaryFile

    with NamedTemporaryFile(delete=False, suffix=".db") as tmp:
        db_path = Path(tmp.name)

    try:
        storage = SQLitePipelineStorage(db_path)

        # Create test entities
        print("\n1. Testing Entity Creation...")

        # Disease
        breast_cancer = Disease(entity_id="C0006142", entity_type=EntityType.DISEASE, name="Breast Cancer", synonyms=["Breast Carcinoma"], source="umls")
        storage.entities.add_disease(breast_cancer)

        # Gene
        from med_lit_schema.entity import Gene

        brca1 = Gene(entity_id="HGNC:1100", entity_type=EntityType.GENE, name="BRCA1", synonyms=["BRCA1 gene"], hgnc_id="HGNC:1100", source="hgnc")
        storage.entities.add_gene(brca1)

        # Drug
        olaparib = Drug(entity_id="RxNorm:1187832", entity_type=EntityType.DRUG, name="Olaparib", synonyms=["Lynparza"], rxnorm_id="RxNorm:1187832", source="rxnorm")
        storage.entities.add_drug(olaparib)

        print(f"   ✓ Created {storage.entities.entity_count} entities")

        # Test retrieval
        print("\n2. Testing Entity Retrieval...")
        retrieved_disease = storage.entities.get_by_id("C0006142")
        assert retrieved_disease is not None, "Failed to retrieve disease"
        print(f"   ✓ Retrieved: {retrieved_disease.name}")

        retrieved_gene = storage.entities.get_by_hgnc("HGNC:1100")
        assert retrieved_gene is not None, "Failed to retrieve gene by HGNC"
        print(f"   ✓ Retrieved gene by HGNC: {retrieved_gene.name}")

        storage.close()
        print("\n✓ Entity extraction tests passed!")
        return True

    except Exception as e:
        print(f"\n✗ Test failed: {e}")
        import traceback

        traceback.print_exc()
        return False
    finally:
        if db_path.exists():
            db_path.unlink()


def test_relationships():
    """Test relationship storage and retrieval."""
    print("\n" + "=" * 60)
    print("Testing Relationships")
    print("=" * 60)

    from tempfile import NamedTemporaryFile

    with NamedTemporaryFile(delete=False, suffix=".db") as tmp:
        db_path = Path(tmp.name)

    try:
        storage = SQLitePipelineStorage(db_path)

        # Create relationships
        print("\n1. Testing Relationship Creation...")

        # Olaparib treats Breast Cancer
        treats_rel = create_relationship(
            predicate=PredicateType.TREATS,
            subject_id="RxNorm:1187832",  # Olaparib
            object_id="C0006142",  # Breast Cancer
            confidence=0.95,
            source_papers=["PMC999999"],
        )
        storage.relationships.add_relationship(treats_rel)

        # BRCA1 increases risk of Breast Cancer
        risk_rel = create_relationship(
            predicate=PredicateType.INCREASES_RISK,
            subject_id="HGNC:1100",  # BRCA1
            object_id="C0006142",  # Breast Cancer
            confidence=0.9,
            source_papers=["PMC999999"],
        )
        storage.relationships.add_relationship(risk_rel)

        print(f"   ✓ Created {storage.relationships.relationship_count} relationships")

        # Test retrieval
        print("\n2. Testing Relationship Retrieval...")
        retrieved = storage.relationships.get_relationship("RxNorm:1187832", "treats", "C0006142")
        assert retrieved is not None, "Failed to retrieve relationship"
        assert retrieved.confidence == 0.95, "Confidence mismatch"
        print(f"   ✓ Retrieved: {retrieved.predicate.value} (confidence: {retrieved.confidence})")

        # Test finding relationships
        print("\n3. Testing Relationship Search...")
        all_treats = storage.relationships.find_relationships(predicate="treats")
        print(f"   ✓ Found {len(all_treats)} 'treats' relationships")

        breast_cancer_rels = storage.relationships.find_relationships(object_id="C0006142")
        print(f"   ✓ Found {len(breast_cancer_rels)} relationships involving Breast Cancer")

        storage.close()
        print("\n✓ Relationship tests passed!")
        return True

    except Exception as e:
        print(f"\n✗ Test failed: {e}")
        import traceback

        traceback.print_exc()
        return False
    finally:
        if db_path.exists():
            db_path.unlink()


def main():
    """Run all tests."""
    print("\n" + "=" * 60)
    print("Pipeline Test Suite")
    print("=" * 60)

    tests = [
        ("Storage Interfaces", test_storage_interfaces),
        ("Provenance Pipeline", test_provenance_pipeline),
        ("Entity Extraction", test_entity_extraction),
        ("Relationships", test_relationships),
    ]

    results = []
    for test_name, test_func in tests:
        try:
            result = test_func()
            results.append((test_name, result))
        except Exception as e:
            print(f"\n✗ {test_name} crashed: {e}")
            import traceback

            traceback.print_exc()
            results.append((test_name, False))

    # Summary
    print("\n" + "=" * 60)
    print("Test Summary")
    print("=" * 60)
    for test_name, result in results:
        status = "✓ PASSED" if result else "✗ FAILED"
        print(f"{test_name}: {status}")

    all_passed = all(result for _, result in results)
    print("\n" + ("=" * 60))
    if all_passed:
        print("All tests passed! ✓")
    else:
        print("Some tests failed. ✗")
    print("=" * 60)

    return 0 if all_passed else 1


if __name__ == "__main__":
    exit(main())

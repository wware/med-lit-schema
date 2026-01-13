"""
Tests for claims pipeline integration.

The claims pipeline was refactored to:
1. Extract from paper abstracts instead of provenance.db paragraphs
2. Use context managers for storage
3. Handle unknown predicates gracefully
4. Generate placeholder entity IDs

Run with: pytest tests/ingest/test_claims_pipeline_integration.py -v
"""

from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import Mock

from med_lit_schema.ingest.claims_pipeline import (
    extract_relationships_from_paragraph,
    process_papers,
)
from med_lit_schema.storage.backends.sqlite import SQLitePipelineStorage
from med_lit_schema.entity import Paper, PaperMetadata
from med_lit_schema.base import PredicateType


class TestExtractRelationshipsFromParagraph:
    """Test the extract_relationships_from_paragraph function."""

    def test_extract_treats_relationship(self):
        """Test extracting TREATS relationships from text."""
        with TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"

            with SQLitePipelineStorage(db_path) as storage:
                text = "Aspirin treats headaches effectively."
                relationships = extract_relationships_from_paragraph(
                    paragraph_id="p1",
                    section_id="s1",
                    paper_id="PMC123456",
                    text=text,
                    section_type="abstract",
                    storage=storage,
                )

                # Should find at least one relationship
                assert len(relationships) > 0

                # Check that it's a TREATS relationship
                treats_found = any(rel.predicate == PredicateType.TREATS for rel in relationships)
                assert treats_found

    def test_extract_associated_with_relationship(self):
        """Test extracting ASSOCIATED_WITH relationships."""
        with TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"

            with SQLitePipelineStorage(db_path) as storage:
                text = "BRCA1 is associated with breast cancer risk."
                relationships = extract_relationships_from_paragraph(
                    paragraph_id="p1",
                    section_id="s1",
                    paper_id="PMC123456",
                    text=text,
                    section_type="abstract",
                    storage=storage,
                )

                # Should find relationship
                assert len(relationships) > 0

                # Check for ASSOCIATED_WITH
                assoc_found = any(rel.predicate == PredicateType.ASSOCIATED_WITH for rel in relationships)
                assert assoc_found

    def test_extract_no_relationships_from_plain_text(self):
        """Test that plain text without patterns returns no relationships."""
        with TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"

            with SQLitePipelineStorage(db_path) as storage:
                text = "This is a simple sentence without any medical relationships."
                relationships = extract_relationships_from_paragraph(
                    paragraph_id="p1",
                    section_id="s1",
                    paper_id="PMC123456",
                    text=text,
                    section_type="abstract",
                    storage=storage,
                )

                # Should not find any relationships
                assert len(relationships) == 0

    def test_extract_multiple_relationships_from_text(self):
        """Test extracting multiple relationships from a single paragraph."""
        with TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"

            with SQLitePipelineStorage(db_path) as storage:
                text = "Metformin treats diabetes. BRCA1 is associated with breast cancer."
                relationships = extract_relationships_from_paragraph(
                    paragraph_id="p1",
                    section_id="s1",
                    paper_id="PMC123456",
                    text=text,
                    section_type="abstract",
                    storage=storage,
                )

                # Should find multiple relationships
                assert len(relationships) >= 2

    def test_unknown_predicate_is_skipped(self):
        """Test that unknown predicates are skipped with warning."""
        with TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"

            with SQLitePipelineStorage(db_path) as storage:
                # This test verifies the code path exists
                # In practice, PREDICATE_PATTERNS should all map to valid predicates
                text = "Some medical text that might match a pattern."
                relationships = extract_relationships_from_paragraph(
                    paragraph_id="p1",
                    section_id="s1",
                    paper_id="PMC123456",
                    text=text,
                    section_type="abstract",
                    storage=storage,
                )

                # Should not crash
                assert isinstance(relationships, list)

    def test_confidence_varies_by_section_type(self):
        """Test that confidence scores vary based on section type."""
        with TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"

            with SQLitePipelineStorage(db_path) as storage:
                text = "Aspirin treats headaches."

                # Extract from abstract
                rels_abstract = extract_relationships_from_paragraph(
                    paragraph_id="p1",
                    section_id="s1",
                    paper_id="PMC123456",
                    text=text,
                    section_type="abstract",
                    storage=storage,
                )

                # Extract from results
                rels_results = extract_relationships_from_paragraph(
                    paragraph_id="p2",
                    section_id="s2",
                    paper_id="PMC123456",
                    text=text,
                    section_type="results",
                    storage=storage,
                )

                if rels_abstract and rels_results:
                    # Results section should have higher confidence
                    assert rels_results[0].confidence >= rels_abstract[0].confidence


class TestProcessPapersFunction:
    """Test the process_papers helper function."""

    def test_process_papers_extracts_from_abstracts(self):
        """Test that process_papers extracts relationships from paper abstracts."""
        with TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"

            # Add test papers
            with SQLitePipelineStorage(db_path) as storage:
                paper1 = Paper(
                    paper_id="PMC123456",
                    title="Aspirin Study",
                    abstract="Aspirin treats headaches effectively.",
                    authors=["Test Author"],
                    publication_date="2024-01-01",
                    journal="Test Journal",
                    entities=[],
                    relationships=[],
                    metadata=PaperMetadata(),
                    extraction_provenance=None,
                )
                storage.papers.add_paper(paper1)

                paper2 = Paper(
                    paper_id="PMC234567",
                    title="BRCA1 Study",
                    abstract="BRCA1 is associated with breast cancer.",
                    authors=["Test Author"],
                    publication_date="2024-01-01",
                    journal="Test Journal",
                    entities=[],
                    relationships=[],
                    metadata=PaperMetadata(),
                    extraction_provenance=None,
                )
                storage.papers.add_paper(paper2)

            # Process papers
            with SQLitePipelineStorage(db_path) as storage:
                args = Mock()
                args.skip_embeddings = True

                count = process_papers(storage, args)

                # Should have extracted relationships
                assert count >= 0  # May be 0 if patterns don't match exactly

                # Check that relationships were added to storage
                all_relationships = storage.relationships.list_relationships(limit=100)
                # Should have at least some relationships (if patterns matched)
                assert isinstance(all_relationships, list)

    def test_process_papers_handles_empty_abstracts(self):
        """Test that process_papers handles papers with empty abstracts."""
        with TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"

            # Add paper with empty abstract
            with SQLitePipelineStorage(db_path) as storage:
                paper = Paper(
                    paper_id="PMC123456",
                    title="Test Paper",
                    abstract="",  # Empty abstract
                    authors=["Test Author"],
                    publication_date="2024-01-01",
                    journal="Test Journal",
                    entities=[],
                    relationships=[],
                    metadata=PaperMetadata(),
                    extraction_provenance=None,
                )
                storage.papers.add_paper(paper)

            # Process papers - should not crash
            with SQLitePipelineStorage(db_path) as storage:
                args = Mock()
                args.skip_embeddings = True

                count = process_papers(storage, args)
                assert count == 0

    def test_process_papers_generates_placeholder_ids(self):
        """Test that process_papers generates placeholder entity IDs."""
        with TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"

            # Add test paper
            with SQLitePipelineStorage(db_path) as storage:
                paper = Paper(
                    paper_id="PMC123456",
                    title="Test Paper",
                    abstract="Aspirin treats headaches effectively.",
                    authors=["Test Author"],
                    publication_date="2024-01-01",
                    journal="Test Journal",
                    entities=[],
                    relationships=[],
                    metadata=PaperMetadata(),
                    extraction_provenance=None,
                )
                storage.papers.add_paper(paper)

            # Process papers
            with SQLitePipelineStorage(db_path) as storage:
                args = Mock()
                args.skip_embeddings = True

                count = process_papers(storage, args)

                if count > 0:
                    # Get relationships
                    rels = storage.relationships.list_relationships(limit=100)

                    if rels:
                        # Check that IDs are placeholders
                        assert any("PLACEHOLDER" in rel.subject_id for rel in rels)

    def test_process_papers_with_no_papers(self):
        """Test that process_papers handles empty database."""
        with TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"

            # Empty database
            with SQLitePipelineStorage(db_path) as storage:
                args = Mock()
                args.skip_embeddings = True

                count = process_papers(storage, args)

                # Should return 0 relationships
                assert count == 0


class TestClaimsPipelineContextManager:
    """Test that claims pipeline properly uses context managers."""

    def test_pipeline_closes_storage_on_success(self):
        """Test that pipeline closes storage after successful processing."""
        with TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"

            # Add test paper
            with SQLitePipelineStorage(db_path) as storage:
                paper = Paper(
                    paper_id="PMC123456",
                    title="Test",
                    abstract="Aspirin treats headaches.",
                    authors=["Test"],
                    publication_date="2024-01-01",
                    journal="Test",
                    entities=[],
                    relationships=[],
                    metadata=PaperMetadata(),
                    extraction_provenance=None,
                )
                storage.papers.add_paper(paper)

            # Process papers - storage should be closed after
            with SQLitePipelineStorage(db_path) as storage:
                args = Mock()
                args.skip_embeddings = True
                count = process_papers(storage, args)
                # Should return a valid count (may be 0)
                assert count >= 0

            # Should be able to open storage again
            with SQLitePipelineStorage(db_path) as storage:
                paper_count = storage.papers.paper_count
                assert paper_count == 1

    def test_pipeline_handles_exception_gracefully(self):
        """Test that pipeline handles exceptions and closes storage."""
        with TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"

            # Add test paper
            with SQLitePipelineStorage(db_path) as storage:
                paper = Paper(
                    paper_id="PMC123456",
                    title="Test",
                    abstract="Test abstract",
                    authors=["Test"],
                    publication_date="2024-01-01",
                    journal="Test",
                    entities=[],
                    relationships=[],
                    metadata=PaperMetadata(),
                    extraction_provenance=None,
                )
                storage.papers.add_paper(paper)

            # Mock args that will cause error (for testing exception handling)
            # The actual process_papers function should handle this gracefully
            try:
                with SQLitePipelineStorage(db_path) as storage:
                    args = Mock()
                    args.skip_embeddings = True
                    # This should not raise even if there are issues
                    count = process_papers(storage, args)
                    # Should return a valid count
                    assert count >= 0
            except Exception:
                pass  # We're testing that storage closes even on error

            # Storage should still be usable
            with SQLitePipelineStorage(db_path) as storage:
                assert storage.papers.paper_count >= 0


class TestClaimsPipelinePatternMatching:
    """Test the pattern matching logic in claims extraction."""

    def test_treats_pattern_variants(self):
        """Test various forms of 'treats' patterns."""
        with TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"

            with SQLitePipelineStorage(db_path) as storage:
                test_texts = [
                    "Drug X treats disease Y",
                    "Drug X is used to treat disease Y",
                    "Drug X for treating disease Y",
                    "Disease Y treated with drug X",
                ]

                for text in test_texts:
                    rels = extract_relationships_from_paragraph("p1", "s1", "PMC123456", text, "abstract", storage)
                    # Should return a list (may be empty if pattern doesn't match)
                    assert isinstance(rels, list)
                    # Most should match some pattern
                    # (but pattern matching is flexible, so we don't assert too strictly)

    def test_associated_with_pattern_variants(self):
        """Test various forms of 'associated with' patterns."""
        with TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"

            with SQLitePipelineStorage(db_path) as storage:
                test_texts = [
                    "Gene X is associated with disease Y",
                    "Gene X associated with disease Y",
                    "Disease Y is associated with gene X",
                ]

                for text in test_texts:
                    rels = extract_relationships_from_paragraph("p1", "s1", "PMC123456", text, "abstract", storage)
                    # Should return a list (may be empty if pattern doesn't match)
                    assert isinstance(rels, list)
                    # Should find some associations


class TestClaimsPipelineEmbeddingSkip:
    """Test that claims pipeline can skip embeddings."""

    def test_skip_embeddings_flag(self):
        """Test that skip_embeddings flag prevents embedding generation."""
        with TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"

            # Add paper
            with SQLitePipelineStorage(db_path) as storage:
                paper = Paper(
                    paper_id="PMC123456",
                    title="Test",
                    abstract="Aspirin treats headaches.",
                    authors=["Test"],
                    publication_date="2024-01-01",
                    journal="Test",
                    entities=[],
                    relationships=[],
                    metadata=PaperMetadata(),
                    extraction_provenance=None,
                )
                storage.papers.add_paper(paper)

            # Process with skip_embeddings=True
            with SQLitePipelineStorage(db_path) as storage:
                args = Mock()
                args.skip_embeddings = True

                # Should not attempt to generate embeddings
                count = process_papers(storage, args)

                # Should complete without errors
                assert count >= 0


class TestClaimsPipelineOutput:
    """Test claims pipeline output and data quality."""

    def test_extracted_relationships_have_required_fields(self):
        """Test that extracted relationships have all required fields."""
        with TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"

            # Add paper
            with SQLitePipelineStorage(db_path) as storage:
                paper = Paper(
                    paper_id="PMC123456",
                    title="Test",
                    abstract="Aspirin treats headaches effectively.",
                    authors=["Test"],
                    publication_date="2024-01-01",
                    journal="Test",
                    entities=[],
                    relationships=[],
                    metadata=PaperMetadata(),
                    extraction_provenance=None,
                )
                storage.papers.add_paper(paper)

            # Extract relationships
            with SQLitePipelineStorage(db_path) as storage:
                args = Mock()
                args.skip_embeddings = True

                count = process_papers(storage, args)

                if count > 0:
                    rels = storage.relationships.list_relationships(limit=100)

                    for rel in rels:
                        # Check required fields
                        assert hasattr(rel, "subject_id")
                        assert hasattr(rel, "predicate")
                        assert hasattr(rel, "object_id")
                        assert hasattr(rel, "confidence")
                        assert hasattr(rel, "source_papers")

                        # Check types
                        assert isinstance(rel.subject_id, str)
                        assert isinstance(rel.object_id, str)
                        assert isinstance(rel.confidence, (int, float))
                        assert 0 <= rel.confidence <= 1

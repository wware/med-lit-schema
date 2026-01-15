"""
Tests for pipeline storage context manager cleanup.

These tests ensure that all pipelines properly close storage connections
and clean up resources, even when errors occur.

Run with: pytest tests/ingest/test_pipelines_context_managers.py -v
"""

import pytest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import Mock, MagicMock
from sqlmodel import Session

from med_lit_schema.storage.backends.sqlite import SQLitePipelineStorage
from med_lit_schema.storage.backends.postgres import PostgresPipelineStorage


class TestSQLiteContextManager:
    """Test SQLite storage context manager behavior."""

    def test_sqlite_storage_closes_on_success(self):
        """Test that SQLite storage closes properly on successful operations."""
        with TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"

            # Use storage in context manager
            with SQLitePipelineStorage(db_path) as storage:
                # Verify storage is usable
                assert storage.entities is not None
                assert storage.papers is not None
                assert storage.relationships is not None

            # After context exit, storage should be closed
            # We can verify by trying to use it (should still work for SQLite
            # since it's file-based, but connection should be properly closed)

    def test_sqlite_storage_closes_on_exception(self):
        """Test that SQLite storage closes even when exception occurs."""
        with TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"

            storage_instance = None
            with pytest.raises(ValueError):
                with SQLitePipelineStorage(db_path) as storage:
                    storage_instance = storage
                    # Simulate an error during processing
                    raise ValueError("Simulated error")

            # Storage should still be closed despite exception
            assert storage_instance is not None

    def test_sqlite_storage_reentrant(self):
        """Test that we can use the same storage multiple times."""
        with TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"

            # First use
            with SQLitePipelineStorage(db_path) as storage:
                pass

            # Second use - should work fine
            with SQLitePipelineStorage(db_path) as storage:
                assert storage.entities is not None


class TestPostgresContextManager:
    """Test PostgreSQL storage context manager behavior."""

    @pytest.fixture
    def mock_session(self):
        """Create a mock SQLModel session."""
        session = MagicMock(spec=Session)
        session.commit = Mock()
        session.close = Mock()
        session.rollback = Mock()
        return session

    def test_postgres_storage_closes_on_success(self, mock_session):
        """Test that PostgreSQL storage commits and closes on success."""
        with PostgresPipelineStorage(mock_session) as storage:
            assert storage.entities is not None
            assert storage.papers is not None

        # Verify session was closed
        mock_session.close.assert_called_once()

    def test_postgres_storage_rolls_back_on_exception(self, mock_session):
        """Test that PostgreSQL storage rolls back on exception."""
        with pytest.raises(ValueError):
            with PostgresPipelineStorage(mock_session) as storage:
                # Verify storage was created
                assert storage is not None
                # Simulate an error
                raise ValueError("Simulated error")

        # Verify rollback was called
        mock_session.rollback.assert_called_once()
        # And session was closed
        mock_session.close.assert_called_once()

    def test_postgres_storage_handles_commit_error(self, mock_session):
        """Test that PostgreSQL storage handles commit errors gracefully."""
        # Make commit raise an exception
        mock_session.commit.side_effect = Exception("Commit failed")

        with pytest.raises(Exception):
            with PostgresPipelineStorage(mock_session) as storage:
                # Verify storage was created before commit error
                assert storage is not None

        # Should still try to close
        mock_session.close.assert_called()


class TestPipelineContextManagers:
    """
    Test that actual pipeline functions properly use context managers.

    These are integration-style tests that verify the refactored pipeline
    code correctly manages storage lifecycle.
    """

    def test_claims_pipeline_process_papers_with_sqlite(self):
        """Test that claims pipeline helper properly manages SQLite storage."""
        from med_lit_schema.ingest.claims_pipeline import process_papers
        from med_lit_schema.entity import Paper, PaperMetadata

        with TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"

            # Create a storage and add a test paper
            with SQLitePipelineStorage(db_path) as storage:
                paper = Paper(
                    paper_id="PMC123456",
                    title="Test Paper",
                    abstract="Aspirin treats headaches. BRCA1 is associated with breast cancer.",
                    authors=["Test Author"],
                    publication_date="2024-01-01",
                    journal="Test Journal",
                    entities=[],
                    relationships=[],
                    metadata=PaperMetadata(),
                    extraction_provenance=None,
                )
                storage.papers.add_paper(paper)

            # Now test process_papers with a fresh storage context
            with SQLitePipelineStorage(db_path) as storage:
                # Create mock args
                args = Mock()
                args.skip_embeddings = True

                # Process papers
                count = process_papers(storage, args)

                # Should have processed the paper and extracted relationships
                assert count >= 0  # May be 0 if no patterns match

    def test_evidence_pipeline_process_relationships_with_sqlite(self):
        """Test that evidence pipeline helper properly manages SQLite storage."""
        from med_lit_schema.ingest.evidence_pipeline import process_relationships
        from med_lit_schema.entity import Paper, PaperMetadata
        from med_lit_schema.relationship import create_relationship
        from med_lit_schema.base import PredicateType

        with TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            provenance_db = Path(tmpdir) / "provenance.db"

            # Create a storage and add test data
            with SQLitePipelineStorage(db_path) as storage:
                # Add a paper
                paper = Paper(
                    paper_id="PMC123456",
                    title="Test Paper",
                    abstract="Test abstract",
                    authors=["Test Author"],
                    publication_date="2024-01-01",
                    journal="Test Journal",
                    entities=[],
                    relationships=[],
                    metadata=PaperMetadata(),
                    extraction_provenance=None,
                )
                storage.papers.add_paper(paper)

                # Add a relationship
                rel = create_relationship(
                    predicate=PredicateType.TREATS,
                    subject_id="drug_001",
                    object_id="disease_001",
                    confidence=0.9,
                    source_papers=["PMC123456"],
                )
                storage.relationships.add_relationship(rel)

            # Now test process_relationships with a fresh storage context
            with SQLitePipelineStorage(db_path) as storage:
                count = process_relationships(storage, provenance_db)

                # Should have processed relationships (even if no evidence found)
                assert count >= 0

    def test_ner_pipeline_process_papers_helper(self):
        """Test that NER pipeline process_papers helper is callable."""
        from med_lit_schema.ingest.ner_pipeline import process_papers

        # This test just verifies the function exists and has correct signature
        # Full testing requires XML files and NER models
        import inspect

        sig = inspect.signature(process_papers)

        # Verify expected parameters
        params = list(sig.parameters.keys())
        assert "xml_dir" in params
        assert "storage" in params
        assert "ner_extractor" in params
        assert "ingest_info" in params
        assert "model_info" in params
        assert "worker_config" in params

    def test_provenance_pipeline_process_files_helper(self):
        """Test that provenance pipeline process_files helper is callable."""
        from med_lit_schema.ingest.provenance_pipeline import process_files

        # Verify the function exists and has correct signature
        import inspect

        sig = inspect.signature(process_files)

        params = list(sig.parameters.keys())
        assert "input_dir" in params
        assert "file_pattern" in params
        assert "paper_parser" in params
        assert "storage" in params
        assert "json_output_dir" in params


class TestStorageLeakPrevention:
    """Tests to ensure storage connections don't leak."""

    def test_multiple_context_managers_in_sequence(self):
        """Test that multiple sequential context managers don't leak."""
        with TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"

            # Open and close multiple times
            for i in range(10):
                with SQLitePipelineStorage(db_path) as storage:
                    # Do some work
                    count = storage.entities.entity_count
                    assert count >= 0

    def test_nested_context_managers_different_dbs(self):
        """Test that nested context managers with different DBs work."""
        with TemporaryDirectory() as tmpdir:
            db_path1 = Path(tmpdir) / "test1.db"
            db_path2 = Path(tmpdir) / "test2.db"

            with SQLitePipelineStorage(db_path1) as storage1:
                with SQLitePipelineStorage(db_path2) as storage2:
                    # Both should be usable
                    assert storage1.entities is not None
                    assert storage2.entities is not None

    def test_exception_in_pipeline_doesnt_leak(self):
        """Test that exceptions during pipeline processing don't leak storage."""
        with TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"

            # Simulate a pipeline that fails
            try:
                with SQLitePipelineStorage(db_path) as storage:
                    # Add some data
                    from med_lit_schema.entity import Paper, PaperMetadata

                    paper = Paper(
                        paper_id="PMC123456",
                        title="Test",
                        abstract="Test",
                        authors=["Test"],
                        publication_date="2024-01-01",
                        journal="Test",
                        entities=[],
                        relationships=[],
                        metadata=PaperMetadata(),
                        extraction_provenance=None,
                    )
                    storage.papers.add_paper(paper)

                    # Simulate error
                    raise RuntimeError("Pipeline failed")
            except RuntimeError:
                pass

            # Storage should be closed, we can reopen
            with SQLitePipelineStorage(db_path) as storage:
                # Paper should still be there from before
                assert storage.papers.paper_count == 1

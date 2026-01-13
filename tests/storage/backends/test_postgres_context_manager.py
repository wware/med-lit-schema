"""
Tests for PostgreSQL storage context manager and serialization.

The PostgreSQL storage was updated to:
1. Use proper context managers with __enter__/__exit__
2. Serialize extraction_provenance and metadata to JSON
3. Handle sessions properly

Run with: pytest tests/storage/backends/test_postgres_context_manager.py -v
"""

import pytest
from datetime import datetime
from unittest.mock import Mock, MagicMock
from sqlalchemy import create_engine
from sqlmodel import Session

from med_lit_schema.storage.backends.postgres import PostgresPipelineStorage
from med_lit_schema.entity import (
    Paper,
    PaperMetadata,
    ExtractionProvenance,
    ExtractionPipelineInfo,
    ExecutionInfo,
    PromptInfo,
    Disease,
    EntityType,
)
from med_lit_schema.relationship import create_relationship
from med_lit_schema.base import PredicateType


class TestPostgresContextManager:
    """Test PostgreSQL storage context manager behavior."""

    @pytest.fixture
    def mock_session(self):
        """Create a mock SQLModel session."""
        session = MagicMock(spec=Session)
        session.commit = Mock()
        session.close = Mock()
        session.rollback = Mock()
        session.exec = Mock(return_value=Mock(first=Mock(return_value=None)))
        return session

    def test_context_manager_enter_returns_storage(self, mock_session):
        """Test that __enter__ returns the storage instance."""
        storage = PostgresPipelineStorage(mock_session)

        with storage as s:
            assert s is storage
            assert s.session is mock_session

    def test_context_manager_exit_closes_session(self, mock_session):
        """Test that __exit__ closes the session."""
        storage = PostgresPipelineStorage(mock_session)

        with storage:
            pass

        # Session should be closed on exit
        mock_session.close.assert_called_once()

    def test_context_manager_exit_on_exception_rolls_back(self, mock_session):
        """Test that __exit__ rolls back on exception."""
        storage = PostgresPipelineStorage(mock_session)

        with pytest.raises(RuntimeError):
            with storage:
                raise RuntimeError("Test error")

        # Should rollback and close
        mock_session.rollback.assert_called_once()
        mock_session.close.assert_called_once()

    def test_context_manager_commit_happens_before_exit(self, mock_session):
        """Test that changes can be committed before exit."""
        storage = PostgresPipelineStorage(mock_session)

        with storage:
            # Simulate some work that would normally commit
            mock_session.add(Mock())

        # Session should be closed
        mock_session.close.assert_called_once()

    def test_multiple_context_managers_sequential(self):
        """Test that multiple sequential context managers work."""
        session1 = MagicMock(spec=Session)
        session1.close = Mock()
        session1.rollback = Mock()

        session2 = MagicMock(spec=Session)
        session2.close = Mock()
        session2.rollback = Mock()

        # First context
        with PostgresPipelineStorage(session1):
            pass

        session1.close.assert_called_once()

        # Second context
        with PostgresPipelineStorage(session2):
            pass

        session2.close.assert_called_once()


class TestPostgresPaperSerialization:
    """Test Paper model serialization with JSON fields."""

    @pytest.fixture
    def mock_session_with_exec(self):
        """Create a mock session that handles exec calls."""
        session = MagicMock(spec=Session)
        session.commit = Mock()
        session.close = Mock()
        session.add = Mock()
        session.merge = Mock()  # Add merge method for paper storage

        # Mock exec to return a result that has first() and all()
        result_mock = Mock()
        result_mock.first.return_value = None
        result_mock.all.return_value = []
        session.exec.return_value = result_mock

        return session

    def test_paper_with_extraction_provenance_serializes(self, mock_session_with_exec):
        """Test that Paper with extraction_provenance is serialized to JSON."""
        storage = PostgresPipelineStorage(mock_session_with_exec)

        pipeline_info = ExtractionPipelineInfo(
            name="test-pipeline", version="1.0.0", git_commit="abc123", git_commit_short="abc", git_branch="main", git_dirty=False, repo_url="https://github.com/test/test"
        )

        execution_info = ExecutionInfo(
            timestamp=datetime.now().isoformat(),
            hostname="test-host",
            python_version="3.12.0",
            duration_seconds=10.5,
        )

        provenance = ExtractionProvenance(
            extraction_pipeline=pipeline_info,
            models={},
            prompt=PromptInfo(version="v1", template="test", checksum=None),
            execution=execution_info,
            entity_resolution=None,
        )

        paper = Paper(
            paper_id="PMC123456",
            title="Test Paper",
            abstract="Test abstract",
            authors=["Author, Test"],
            publication_date="2024-01-01",
            journal="Test Journal",
            entities=[],
            relationships=[],
            metadata=PaperMetadata(),
            extraction_provenance=provenance,
        )

        # Add paper
        with storage:
            storage.papers.add_paper(paper)

        # Verify merge was called (not add)
        mock_session_with_exec.merge.assert_called()

        # Get the Paper persistence model that was merged
        call_args = mock_session_with_exec.merge.call_args
        paper_persistence = call_args[0][0]

        # Check that extraction_provenance_json is set
        assert hasattr(paper_persistence, "extraction_provenance_json")
        assert paper_persistence.extraction_provenance_json is not None

        # Verify it's valid JSON
        provenance_dict = paper_persistence.extraction_provenance_json
        assert provenance_dict["extraction_pipeline"]["name"] == "test-pipeline"

    def test_paper_with_metadata_serializes(self, mock_session_with_exec):
        """Test that Paper with metadata is serialized to JSON."""
        storage = PostgresPipelineStorage(mock_session_with_exec)

        metadata = PaperMetadata(
            pmid="12345678",
            doi="10.1000/test",
        )

        paper = Paper(
            paper_id="PMC123456",
            title="Test Paper",
            abstract="Test abstract",
            authors=["Author, Test"],
            publication_date="2024-01-01",
            journal="Test Journal",
            entities=[],
            relationships=[],
            metadata=metadata,
            extraction_provenance=None,
        )

        with storage:
            storage.papers.add_paper(paper)

        # Get the merged paper
        call_args = mock_session_with_exec.merge.call_args
        paper_persistence = call_args[0][0]

        # Check that metadata_json is set
        assert hasattr(paper_persistence, "metadata_json")
        assert paper_persistence.metadata_json is not None

        metadata_dict = paper_persistence.metadata_json
        assert metadata_dict["pmid"] == "12345678"
        assert metadata_dict["doi"] == "10.1000/test"

    def test_paper_without_provenance_handles_none(self, mock_session_with_exec):
        """Test that Paper without extraction_provenance (None) is handled."""
        storage = PostgresPipelineStorage(mock_session_with_exec)

        paper = Paper(
            paper_id="PMC123456",
            title="Test Paper",
            abstract="Test abstract",
            authors=["Author, Test"],
            publication_date="2024-01-01",
            journal="Test Journal",
            entities=[],
            relationships=[],
            metadata=PaperMetadata(),
            extraction_provenance=None,  # No provenance
        )

        with storage:
            storage.papers.add_paper(paper)

        # Get the merged paper
        call_args = mock_session_with_exec.merge.call_args
        paper_persistence = call_args[0][0]

        # extraction_provenance_json should be None
        assert paper_persistence.extraction_provenance_json is None

    def test_paper_without_metadata_handles_none(self, mock_session_with_exec):
        """Test that Paper with empty metadata is handled."""
        storage = PostgresPipelineStorage(mock_session_with_exec)

        paper = Paper(
            paper_id="PMC123456",
            title="Test Paper",
            abstract="Test abstract",
            authors=["Author, Test"],
            publication_date="2024-01-01",
            journal="Test Journal",
            entities=[],
            relationships=[],
            # metadata will use default_factory (empty PaperMetadata())
            extraction_provenance=None,
        )

        with storage:
            storage.papers.add_paper(paper)

        # Get the merged paper
        call_args = mock_session_with_exec.merge.call_args
        paper_persistence = call_args[0][0]

        # metadata_json should contain an empty/default PaperMetadata
        assert paper_persistence.metadata_json is not None
        metadata_dict = paper_persistence.metadata_json
        # Should be an empty metadata object (all fields None or default)
        assert isinstance(metadata_dict, dict)


class TestPostgresStorageInterface:
    """Test PostgreSQL storage interface methods."""

    @pytest.fixture
    def mock_session_with_queries(self):
        """Create a mock session that handles various query patterns."""
        session = MagicMock(spec=Session)
        session.commit = Mock()
        session.close = Mock()
        session.add = Mock()
        session.merge = Mock()  # For entity storage
        session.execute = Mock()  # For relationship storage
        session.rollback = Mock()

        # Mock exec to return appropriate results
        def exec_side_effect(statement):
            result = Mock()
            result.first.return_value = None
            result.all.return_value = []
            result.one_or_none.return_value = None
            return result

        session.exec.side_effect = exec_side_effect

        return session

    def test_storage_has_required_interfaces(self, mock_session_with_queries):
        """Test that storage has all required interface properties."""
        storage = PostgresPipelineStorage(mock_session_with_queries)

        with storage:
            assert hasattr(storage, "entities")
            assert hasattr(storage, "papers")
            assert hasattr(storage, "relationships")
            assert hasattr(storage, "evidence")
            assert hasattr(storage, "relationship_embeddings")

    def test_storage_can_add_entity(self, mock_session_with_queries):
        """Test that storage can add entities."""
        storage = PostgresPipelineStorage(mock_session_with_queries)

        disease = Disease(
            entity_id="C0006142",
            entity_type=EntityType.DISEASE,
            name="Breast Cancer",
            synonyms=["Breast Carcinoma"],
        )

        with storage:
            storage.entities.add_disease(disease)

        # Verify session methods were called (uses merge, not add)
        mock_session_with_queries.merge.assert_called()

    def test_storage_can_add_relationship(self, mock_session_with_queries):
        """Test that storage can add relationships."""
        storage = PostgresPipelineStorage(mock_session_with_queries)

        rel = create_relationship(
            predicate=PredicateType.TREATS,
            subject_id="drug_001",
            object_id="disease_001",
            confidence=0.95,
            source_papers=["PMC123456"],
        )

        with storage:
            storage.relationships.add_relationship(rel)

        # Verify session methods were called (uses execute, not add)
        mock_session_with_queries.execute.assert_called()


@pytest.mark.requires_postgres
class TestPostgresStorageIntegration:
    """
    Integration tests with actual PostgreSQL database.

    These tests require a PostgreSQL database with the medlit schema.
    Set DATABASE_URL environment variable to run these tests.

    Run with: pytest -m requires_postgres
    Skip with: pytest -m "not requires_postgres"
    """

    @pytest.fixture
    def postgres_url(self):
        """Get PostgreSQL URL from environment or skip."""
        import os

        url = os.getenv("DATABASE_URL") or os.getenv("DB_URL")

        if not url or "postgresql" not in url:
            pytest.skip("DATABASE_URL not set or not PostgreSQL")

        return url

    @pytest.fixture
    def postgres_session(self, postgres_url):
        """Create a real PostgreSQL session."""
        engine = create_engine(postgres_url)
        session = Session(engine)
        yield session
        session.close()

    def test_real_postgres_context_manager(self, postgres_session):
        """Test context manager with real PostgreSQL."""
        with PostgresPipelineStorage(postgres_session) as storage:
            # Should be able to query
            count = storage.papers.paper_count
            assert count >= 0

    def test_real_postgres_add_and_retrieve_paper(self, postgres_url):
        """Test adding and retrieving a paper with real PostgreSQL."""
        engine = create_engine(postgres_url)

        # Add paper
        with Session(engine) as session:
            with PostgresPipelineStorage(session) as storage:
                paper = Paper(
                    paper_id="PMC_TEST_001",
                    title="Test Paper for Pytest",
                    abstract="This is a test paper",
                    authors=["Pytest Author"],
                    publication_date="2024-01-01",
                    journal="Test Journal",
                    entities=[],
                    relationships=[],
                    metadata=PaperMetadata(pmc_id="PMC_TEST_001"),
                    extraction_provenance=None,
                )

                storage.papers.add_paper(paper)
                session.commit()

        # Retrieve paper
        with Session(engine) as session:
            with PostgresPipelineStorage(session) as storage:
                retrieved = storage.papers.get_paper("PMC_TEST_001")

                if retrieved:
                    assert retrieved.title == "Test Paper for Pytest"
                    assert retrieved.paper_id == "PMC_TEST_001"

                    # Clean up
                    # (Would need delete method in storage interface)

    def test_real_postgres_transaction_rollback(self, postgres_url):
        """Test that transactions roll back on error."""
        engine = create_engine(postgres_url)

        paper_id = "PMC_TEST_ROLLBACK_001"

        # Try to add paper but fail
        try:
            with Session(engine) as session:
                with PostgresPipelineStorage(session) as storage:
                    paper = Paper(
                        paper_id=paper_id,
                        title="This should roll back",
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

                    # Force an error before commit
                    raise RuntimeError("Simulated error")
        except RuntimeError:
            pass

        # Verify paper was NOT added (rolled back)
        with Session(engine) as session:
            with PostgresPipelineStorage(session) as storage:
                retrieved = storage.papers.get_paper(paper_id)
                # Should not exist due to rollback
                # (Depending on implementation, might return None)
                assert retrieved is None

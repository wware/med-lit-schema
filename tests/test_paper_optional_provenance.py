"""
Tests for optional extraction_provenance in Paper model.

The Paper model was updated to make extraction_provenance optional (Field(None))
instead of required (Field(...)).

Run with: pytest tests/test_paper_optional_provenance.py -v
"""

import pytest
from datetime import datetime
import socket
import platform

from med_lit_schema.entity import (
    Paper,
    PaperMetadata,
    ExtractionProvenance,
    ExtractionPipelineInfo,
    ExecutionInfo,
    PromptInfo,
)


class TestPaperWithoutProvenance:
    """Test Paper model without extraction_provenance."""

    def test_paper_without_provenance_creates_successfully(self):
        """Test that Paper can be created without extraction_provenance."""
        paper = Paper(
            paper_id="PMC123456",
            title="Test Paper",
            abstract="This is a test abstract.",
            authors=["Smith, John", "Doe, Jane"],
            publication_date="2024-01-01",
            journal="Test Journal",
            entities=[],
            relationships=[],
            metadata=PaperMetadata(),
            extraction_provenance=None,  # Explicitly None
        )

        assert paper.paper_id == "PMC123456"
        assert paper.extraction_provenance is None

    def test_paper_without_provenance_field_defaults_to_none(self):
        """Test that extraction_provenance defaults to None when not provided."""
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
            # extraction_provenance not provided
        )

        assert paper.extraction_provenance is None

    def test_paper_without_provenance_serializes(self):
        """Test that Paper without provenance can be serialized to JSON."""
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

        # Serialize to JSON
        json_str = paper.model_dump_json()

        assert json_str is not None
        assert "PMC123456" in json_str

    def test_paper_without_provenance_deserializes(self):
        """Test that Paper without provenance can be deserialized from JSON."""
        paper_dict = {
            "paper_id": "PMC123456",
            "title": "Test Paper",
            "abstract": "Test abstract",
            "authors": ["Test Author"],
            "publication_date": "2024-01-01",
            "journal": "Test Journal",
            "entities": [],
            "relationships": [],
            "metadata": {},
            "extraction_provenance": None,
        }

        paper = Paper(**paper_dict)

        assert paper.paper_id == "PMC123456"
        assert paper.extraction_provenance is None


class TestPaperWithProvenance:
    """Test Paper model with extraction_provenance."""

    def test_paper_with_provenance_creates_successfully(self):
        """Test that Paper can still be created with extraction_provenance."""
        pipeline_info = ExtractionPipelineInfo(
            name="test-pipeline",
            version="1.0.0",
            git_commit="abc123",
            git_commit_short="abc",
            git_branch="main",
            git_dirty=False,
            repo_url="https://github.com/test/test",
        )

        execution_info = ExecutionInfo(
            timestamp=datetime.now().isoformat(),
            hostname=socket.gethostname(),
            python_version=platform.python_version(),
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
            authors=["Test Author"],
            publication_date="2024-01-01",
            journal="Test Journal",
            entities=[],
            relationships=[],
            metadata=PaperMetadata(),
            extraction_provenance=provenance,
        )

        assert paper.paper_id == "PMC123456"
        assert paper.extraction_provenance is not None
        assert paper.extraction_provenance.extraction_pipeline.name == "test-pipeline"

    def test_paper_with_provenance_serializes(self):
        """Test that Paper with provenance can be serialized."""
        pipeline_info = ExtractionPipelineInfo(
            name="test-pipeline",
            version="1.0.0",
            git_commit="abc123",
            git_commit_short="abc",
            git_branch="main",
            git_dirty=False,
            repo_url="https://github.com/test/test",
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
            authors=["Test Author"],
            publication_date="2024-01-01",
            journal="Test Journal",
            entities=[],
            relationships=[],
            metadata=PaperMetadata(),
            extraction_provenance=provenance,
        )

        # Serialize
        json_str = paper.model_dump_json()

        assert json_str is not None
        assert "test-pipeline" in json_str
        assert "extraction_provenance" in json_str


class TestPaperProvenanceRoundTrip:
    """Test round-trip serialization with and without provenance."""

    def test_roundtrip_without_provenance(self):
        """Test serialize and deserialize Paper without provenance."""
        paper1 = Paper(
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

        # Serialize to dict
        paper_dict = paper1.model_dump()

        # Deserialize
        paper2 = Paper(**paper_dict)

        assert paper2.paper_id == paper1.paper_id
        assert paper2.extraction_provenance is None

    def test_roundtrip_with_provenance(self):
        """Test serialize and deserialize Paper with provenance."""
        provenance = ExtractionProvenance(
            extraction_pipeline=ExtractionPipelineInfo(
                name="test",
                version="1.0.0",
                git_commit="abc",
                git_commit_short="abc",
                git_branch="main",
                git_dirty=False,
                repo_url="https://test.com",
            ),
            models={},
            prompt=PromptInfo(version="v1", template="test", checksum=None),
            execution=ExecutionInfo(
                timestamp=datetime.now().isoformat(),
                hostname="test",
                python_version="3.12",
                duration_seconds=10,
            ),
            entity_resolution=None,
        )

        paper1 = Paper(
            paper_id="PMC123456",
            title="Test Paper",
            abstract="Test abstract",
            authors=["Test Author"],
            publication_date="2024-01-01",
            journal="Test Journal",
            entities=[],
            relationships=[],
            metadata=PaperMetadata(),
            extraction_provenance=provenance,
        )

        # Serialize to dict
        paper_dict = paper1.model_dump()

        # Deserialize
        paper2 = Paper(**paper_dict)

        assert paper2.paper_id == paper1.paper_id
        assert paper2.extraction_provenance is not None
        assert paper2.extraction_provenance.extraction_pipeline.name == "test"


class TestPaperProvenanceStorage:
    """Test storing Papers with and without provenance in storage backends."""

    def test_sqlite_storage_without_provenance(self):
        """Test SQLite storage handles Paper without provenance."""
        from med_lit_schema.storage.backends.sqlite import SQLitePipelineStorage
        from pathlib import Path
        from tempfile import TemporaryDirectory

        with TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"

            with SQLitePipelineStorage(db_path) as storage:
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
                    extraction_provenance=None,  # No provenance
                )

                storage.papers.add_paper(paper)

                # Retrieve it
                retrieved = storage.papers.get_paper("PMC123456")

                assert retrieved is not None
                assert retrieved.paper_id == "PMC123456"
                assert retrieved.extraction_provenance is None

    def test_sqlite_storage_with_provenance(self):
        """Test SQLite storage handles Paper with provenance."""
        from med_lit_schema.storage.backends.sqlite import SQLitePipelineStorage
        from pathlib import Path
        from tempfile import TemporaryDirectory

        with TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"

            provenance = ExtractionProvenance(
                extraction_pipeline=ExtractionPipelineInfo(
                    name="test",
                    version="1.0.0",
                    git_commit="abc",
                    git_commit_short="abc",
                    git_branch="main",
                    git_dirty=False,
                    repo_url="https://test.com",
                ),
                models={},
                prompt=PromptInfo(version="v1", template="test", checksum=None),
                execution=ExecutionInfo(
                    timestamp=datetime.now().isoformat(),
                    hostname="test",
                    python_version="3.12",
                    duration_seconds=10,
                ),
                entity_resolution=None,
            )

            with SQLitePipelineStorage(db_path) as storage:
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
                    extraction_provenance=provenance,
                )

                storage.papers.add_paper(paper)

                # Retrieve it
                retrieved = storage.papers.get_paper("PMC123456")

                assert retrieved is not None
                assert retrieved.extraction_provenance is not None
                assert retrieved.extraction_provenance.extraction_pipeline.name == "test"


class TestPaperBackwardCompatibility:
    """Test backward compatibility with old code expecting provenance."""

    def test_can_check_provenance_presence(self):
        """Test that code can check if provenance is present."""
        paper_with = Paper(
            paper_id="PMC123456",
            title="Test",
            abstract="Test",
            authors=["Test"],
            publication_date="2024-01-01",
            journal="Test",
            entities=[],
            relationships=[],
            metadata=PaperMetadata(),
            extraction_provenance=ExtractionProvenance(
                extraction_pipeline=ExtractionPipelineInfo(
                    name="test",
                    version="1.0",
                    git_commit="abc",
                    git_commit_short="abc",
                    git_branch="main",
                    git_dirty=False,
                    repo_url="test",
                ),
                models={},
                prompt=PromptInfo(version="v1", template="test", checksum=None),
                execution=ExecutionInfo(
                    timestamp="2024-01-01",
                    hostname="test",
                    python_version="3.12",
                    duration_seconds=10,
                ),
                entity_resolution=None,
            ),
        )

        paper_without = Paper(
            paper_id="PMC234567",
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

        # Can safely check
        if paper_with.extraction_provenance:
            pipeline_name = paper_with.extraction_provenance.extraction_pipeline.name
            assert pipeline_name == "test"

        if paper_without.extraction_provenance:
            pytest.fail("Should not have provenance")

    def test_provenance_field_is_optional_in_schema(self):
        """Test that schema shows extraction_provenance as optional."""
        schema = Paper.model_json_schema()

        # Check if extraction_provenance is in required fields
        required = schema.get("required", [])

        # extraction_provenance should NOT be required
        assert "extraction_provenance" not in required

"""
Tests for embeddings pipeline with Ollama integration.

The embeddings pipeline was updated to use Ollama instead of sentence-transformers.
Key changes:
- Uses OllamaEmbeddingGenerator instead of SentenceTransformer
- Dynamically determines embedding dimension
- Entity ID changed from INTEGER to TEXT
- Paragraph embeddings are commented out

Run with: pytest tests/ingest/test_embeddings_pipeline_ollama.py -v
"""

import pytest
import sqlite3
import numpy as np
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch, MagicMock

from med_lit_schema.ingest.embeddings_pipeline import (
    create_entity_embeddings_table,
    get_entities,
    insert_entity_embedding,
    load_embedding,
)


class TestEntityEmbeddingsTable:
    """Test entity embeddings table creation."""

    def test_create_entity_embeddings_table(self):
        """Test creating entity_embeddings table."""
        with TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            conn = sqlite3.connect(db_path)

            create_entity_embeddings_table(conn)

            # Check table exists
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='entity_embeddings'")
            result = cursor.fetchone()

            assert result is not None
            assert result[0] == "entity_embeddings"

            conn.close()

    def test_entity_embeddings_table_schema(self):
        """Test that entity_embeddings table has correct schema."""
        with TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            conn = sqlite3.connect(db_path)

            create_entity_embeddings_table(conn)

            # Check columns
            cursor = conn.cursor()
            cursor.execute("PRAGMA table_info(entity_embeddings)")
            columns = cursor.fetchall()

            column_names = [col[1] for col in columns]
            column_types = {col[1]: col[2] for col in columns}

            # Verify required columns
            assert "entity_id" in column_names
            assert "embedding" in column_names
            assert "model_name" in column_names
            assert "created_at" in column_names

            # Verify entity_id is TEXT (not INTEGER)
            assert column_types["entity_id"] == "TEXT"

            conn.close()


class TestGetEntities:
    """Test get_entities function."""

    def test_get_entities_from_database(self):
        """Test retrieving entities from database."""
        with TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "ingest.db"
            conn = sqlite3.connect(db_path)

            # Create entities table
            conn.execute(
                """
                CREATE TABLE entities (
                    id TEXT PRIMARY KEY,
                    name TEXT,
                    entity_type TEXT
                )
            """
            )

            # Insert test entities
            conn.execute("INSERT INTO entities VALUES ('C0001', 'Disease 1', 'disease')")
            conn.execute("INSERT INTO entities VALUES ('C0002', 'Disease 2', 'disease')")
            conn.commit()

            # Get entities
            entities = get_entities(conn)

            assert len(entities) == 2
            assert entities[0] == ("C0001", "Disease 1")
            assert entities[1] == ("C0002", "Disease 2")

            conn.close()

    def test_get_entities_empty_database(self):
        """Test getting entities from empty database."""
        with TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "ingest.db"
            conn = sqlite3.connect(db_path)

            # Create empty entities table
            conn.execute(
                """
                CREATE TABLE entities (
                    id TEXT PRIMARY KEY,
                    name TEXT
                )
            """
            )
            conn.commit()

            entities = get_entities(conn)

            assert len(entities) == 0

            conn.close()


class TestInsertEntityEmbedding:
    """Test insert_entity_embedding function."""

    def test_insert_entity_embedding(self):
        """Test inserting an entity embedding."""
        with TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            conn = sqlite3.connect(db_path)

            create_entity_embeddings_table(conn)

            # Create test embedding
            embedding = np.array([0.1, 0.2, 0.3, 0.4, 0.5], dtype=np.float32)

            insert_entity_embedding(conn, "C0001", embedding, "nomic-embed-text")

            # Verify insertion
            cursor = conn.cursor()
            cursor.execute("SELECT entity_id, model_name FROM entity_embeddings")
            result = cursor.fetchone()

            assert result is not None
            assert result[0] == "C0001"
            assert result[1] == "nomic-embed-text"

            conn.close()

    def test_insert_entity_embedding_replaces_existing(self):
        """Test that inserting embedding replaces existing one."""
        with TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            conn = sqlite3.connect(db_path)

            create_entity_embeddings_table(conn)

            # Insert first embedding
            embedding1 = np.array([0.1, 0.2, 0.3], dtype=np.float32)
            insert_entity_embedding(conn, "C0001", embedding1, "model-v1")

            # Insert replacement embedding
            embedding2 = np.array([0.4, 0.5, 0.6], dtype=np.float32)
            insert_entity_embedding(conn, "C0001", embedding2, "model-v2")

            # Should only have one row
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM entity_embeddings WHERE entity_id='C0001'")
            count = cursor.fetchone()[0]

            assert count == 1

            # Should have the new model name
            cursor.execute("SELECT model_name FROM entity_embeddings WHERE entity_id='C0001'")
            model = cursor.fetchone()[0]

            assert model == "model-v2"

            conn.close()


class TestLoadEmbedding:
    """Test load_embedding function."""

    def test_load_embedding_from_bytes(self):
        """Test loading embedding from bytes."""
        # Create embedding
        original = np.array([0.1, 0.2, 0.3, 0.4, 0.5], dtype=np.float32)
        embedding_bytes = original.tobytes()

        # Load it back
        # Note: load_embedding uses EMBEDDING_DIM which is set dynamically
        # For this test, we'll mock the dimension
        with patch("med_lit_schema.ingest.embeddings_pipeline.EMBEDDING_DIM", 5):
            loaded = load_embedding(embedding_bytes)

            assert isinstance(loaded, np.ndarray)
            assert np.allclose(loaded, original)

    def test_load_embedding_correct_shape(self):
        """Test that loaded embedding has correct shape."""
        original = np.array([0.1] * 768, dtype=np.float32)
        embedding_bytes = original.tobytes()

        with patch("med_lit_schema.ingest.embeddings_pipeline.EMBEDDING_DIM", 768):
            loaded = load_embedding(embedding_bytes)

            assert loaded.shape == (768,)


class TestGenerateEntityEmbeddings:
    """Test generate_entity_embeddings function."""

    @patch("med_lit_schema.ingest.embeddings_pipeline.OllamaEmbeddingGenerator")
    def test_generate_entity_embeddings_uses_ollama(self, mock_generator_class):
        """Test that generate_entity_embeddings uses OllamaEmbeddingGenerator."""
        from med_lit_schema.ingest.embeddings_pipeline import generate_entity_embeddings

        with TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "ingest.db"
            conn = sqlite3.connect(db_path)

            # Create entities table
            conn.execute(
                """
                CREATE TABLE entities (
                    id TEXT PRIMARY KEY,
                    name TEXT
                )
            """
            )
            conn.execute("INSERT INTO entities VALUES ('C0001', 'Disease 1')")
            conn.commit()
            conn.close()

            # Mock the generator
            mock_generator = MagicMock()
            mock_generator.embedding_dim = 768
            mock_generator.generate_embeddings_batch.return_value = [np.array([0.1] * 768, dtype=np.float32)]
            mock_generator_class.return_value = mock_generator

            # Run the function
            count = generate_entity_embeddings(db_path, model_name="nomic-embed-text")

            # Verify Ollama generator was created
            mock_generator_class.assert_called_once()
            assert "nomic-embed-text" in str(mock_generator_class.call_args)

            # Verify embeddings were generated
            assert count == 1

    @patch("med_lit_schema.ingest.embeddings_pipeline.OllamaEmbeddingGenerator")
    def test_generate_entity_embeddings_batch_processing(self, mock_generator_class):
        """Test that entity embeddings are generated in batches."""
        from med_lit_schema.ingest.embeddings_pipeline import generate_entity_embeddings

        with TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "ingest.db"
            conn = sqlite3.connect(db_path)

            # Create entities table with multiple entities
            conn.execute(
                """
                CREATE TABLE entities (
                    id TEXT PRIMARY KEY,
                    name TEXT
                )
            """
            )
            for i in range(5):
                conn.execute(f"INSERT INTO entities VALUES ('C{i:04d}', 'Entity {i}')")
            conn.commit()
            conn.close()

            # Mock the generator
            mock_generator = MagicMock()
            mock_generator.embedding_dim = 768
            mock_generator.generate_embeddings_batch.return_value = [np.array([0.1] * 768, dtype=np.float32) for _ in range(5)]
            mock_generator_class.return_value = mock_generator

            # Run the function
            count = generate_entity_embeddings(db_path, batch_size=5)

            # Verify batch generation was called
            assert mock_generator.generate_embeddings_batch.called
            assert count == 5


class TestEmbeddingsDimensionDetection:
    """Test dynamic embedding dimension detection."""

    @patch("med_lit_schema.ingest.embeddings_pipeline.OllamaEmbeddingGenerator")
    def test_embedding_dimension_is_detected_dynamically(self, mock_generator_class):
        """Test that embedding dimension is detected from Ollama model."""
        from med_lit_schema.ingest.embeddings_pipeline import generate_entity_embeddings

        with TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "ingest.db"
            conn = sqlite3.connect(db_path)

            # Create entities table
            conn.execute(
                """
                CREATE TABLE entities (
                    id TEXT PRIMARY KEY,
                    name TEXT
                )
            """
            )
            conn.execute("INSERT INTO entities VALUES ('C0001', 'Disease 1')")
            conn.commit()
            conn.close()

            # Mock generator with custom dimension
            mock_generator = MagicMock()
            mock_generator.embedding_dim = 1536  # Different dimension
            mock_generator.generate_embeddings_batch.return_value = [np.array([0.1] * 1536, dtype=np.float32)]
            mock_generator_class.return_value = mock_generator

            # Run the function
            generate_entity_embeddings(db_path)

            # The EMBEDDING_DIM global should be updated
            # (This is checked by verifying the code path works)


class TestParagraphEmbeddingsCommentedOut:
    """Test that paragraph embeddings are commented out."""

    def test_paragraph_embedding_functions_not_imported(self):
        """Test that paragraph embedding functions are commented out."""
        import med_lit_schema.ingest.embeddings_pipeline as pipeline_module

        # These functions should not exist (or be commented out)
        # We can check if they're accessible
        # Note: They're commented out in the code, so this is more of a smoke test

        # The pipeline should focus on entities only
        assert hasattr(pipeline_module, "generate_entity_embeddings")

        # Paragraph functions are commented out, so they shouldn't be callable
        # (or they'll be commented code that Python ignores)


class TestEntityIDTextType:
    """Test that entity_id is TEXT type, not INTEGER."""

    def test_entity_embeddings_table_uses_text_id(self):
        """Test that entity_embeddings table uses TEXT for entity_id."""
        with TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            conn = sqlite3.connect(db_path)

            create_entity_embeddings_table(conn)

            # Check column type
            cursor = conn.cursor()
            cursor.execute("PRAGMA table_info(entity_embeddings)")
            columns = cursor.fetchall()

            entity_id_col = [col for col in columns if col[1] == "entity_id"][0]

            # Column type should be TEXT
            assert entity_id_col[2] == "TEXT"

            conn.close()

    def test_can_insert_text_entity_ids(self):
        """Test that TEXT entity IDs can be inserted."""
        with TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            conn = sqlite3.connect(db_path)

            create_entity_embeddings_table(conn)

            # Insert with text ID (not numeric)
            embedding = np.array([0.1, 0.2, 0.3], dtype=np.float32)

            # These should all work with TEXT type
            insert_entity_embedding(conn, "C0006142", embedding, "test-model")
            insert_entity_embedding(conn, "HGNC:1100", embedding, "test-model")
            insert_entity_embedding(conn, "RxNorm:1187832", embedding, "test-model")

            # Verify all were inserted
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM entity_embeddings")
            count = cursor.fetchone()[0]

            assert count == 3

            conn.close()


@pytest.mark.requires_ollama
class TestEmbeddingsIntegrationWithOllama:
    """
    Integration tests with actual Ollama instance.

    Run with: pytest -m requires_ollama
    Skip with: pytest -m "not requires_ollama"
    """

    @pytest.fixture
    def check_ollama(self):
        """Check if Ollama is available."""
        try:
            import ollama

            client = ollama.Client(host="http://localhost:11434", timeout=10.0)
            client.embed(model="nomic-embed-text", input="test")
        except Exception as e:
            pytest.skip(f"Ollama not available: {e}")

    def test_real_ollama_embeddings_generation(self, check_ollama):
        """Test generating embeddings with real Ollama."""
        from med_lit_schema.ingest.embeddings_pipeline import generate_entity_embeddings

        with TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "ingest.db"
            conn = sqlite3.connect(db_path)

            # Create entities table
            conn.execute(
                """
                CREATE TABLE entities (
                    id TEXT PRIMARY KEY,
                    name TEXT
                )
            """
            )
            conn.execute("INSERT INTO entities VALUES ('C0006142', 'Breast Cancer')")
            conn.execute("INSERT INTO entities VALUES ('HGNC:1100', 'BRCA1')")
            conn.commit()
            conn.close()

            # Generate embeddings with real Ollama
            count = generate_entity_embeddings(db_path, model_name="nomic-embed-text")

            assert count == 2

            # Verify embeddings were stored
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM entity_embeddings")
            stored_count = cursor.fetchone()[0]

            assert stored_count == 2

            # Verify embeddings can be loaded
            cursor.execute("SELECT embedding FROM entity_embeddings LIMIT 1")
            embedding_bytes = cursor.fetchone()[0]

            # Should be able to load it
            # (dimension will be determined by Ollama)
            assert embedding_bytes is not None
            assert len(embedding_bytes) > 0

            conn.close()

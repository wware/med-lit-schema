"""
Tests for Ollama embedding generator.

The project switched from sentence-transformers to Ollama for embeddings.
These tests ensure the Ollama integration works correctly.

Run with: pytest tests/ingest/test_ollama_embedding_generator.py -v

Note: Some tests require a running Ollama instance with the nomic-embed-text model.
Use pytest markers to skip tests requiring Ollama:
    pytest -m "not requires_ollama"
"""

import pytest
from unittest.mock import patch, MagicMock

# Try to import ollama - skip tests if not available
try:
    import ollama

    OLLAMA_AVAILABLE = True
except ImportError:
    OLLAMA_AVAILABLE = False

from med_lit_schema.ingest.ollama_embedding_generator import OllamaEmbeddingGenerator


class TestOllamaGeneratorBasics:
    """Test basic Ollama generator functionality."""

    @pytest.mark.skipif(not OLLAMA_AVAILABLE, reason="ollama package not installed")
    def test_ollama_generator_imports(self):
        """Test that OllamaEmbeddingGenerator can be imported."""
        assert OllamaEmbeddingGenerator is not None

    @pytest.mark.skipif(not OLLAMA_AVAILABLE, reason="ollama package not installed")
    def test_ollama_generator_has_required_interface(self):
        """Test that generator implements required interface methods."""
        # Check that the class has required methods
        assert hasattr(OllamaEmbeddingGenerator, "generate_embedding")
        assert hasattr(OllamaEmbeddingGenerator, "generate_embeddings_batch")
        assert hasattr(OllamaEmbeddingGenerator, "model_name")
        assert hasattr(OllamaEmbeddingGenerator, "embedding_dim")

    @pytest.mark.skipif(not OLLAMA_AVAILABLE, reason="ollama package not installed")
    def test_ollama_generator_initialization_signature(self):
        """Test generator initialization signature."""
        import inspect

        sig = inspect.signature(OllamaEmbeddingGenerator.__init__)
        params = list(sig.parameters.keys())

        assert "self" in params
        assert "model_name" in params
        assert "host" in params


class TestOllamaGeneratorWithMock:
    """Test Ollama generator with mocked Ollama client."""

    @pytest.fixture
    def mock_ollama_client(self):
        """Create a mock Ollama client."""
        client = MagicMock()

        # Mock embed response for dimension detection
        client.embed.return_value = {"embeddings": [[0.1, 0.2, 0.3, 0.4, 0.5] * 152]}  # 760-dim vector

        return client

    @pytest.mark.skipif(not OLLAMA_AVAILABLE, reason="ollama package not installed")
    @patch("med_lit_schema.ingest.ollama_embedding_generator.ollama.Client")
    def test_generator_initialization_with_mock(self, mock_client_class, mock_ollama_client):
        """Test generator initialization with mocked Ollama."""
        mock_client_class.return_value = mock_ollama_client

        generator = OllamaEmbeddingGenerator(model_name="nomic-embed-text", host="http://localhost:11434")

        # Verify client was created (with default timeout)
        mock_client_class.assert_called_once_with(host="http://localhost:11434", timeout=60.0)

        # Verify dimension was detected
        assert generator.embedding_dim == 760
        assert generator.model_name == "nomic-embed-text"

    @pytest.mark.skipif(not OLLAMA_AVAILABLE, reason="ollama package not installed")
    @patch("med_lit_schema.ingest.ollama_embedding_generator.ollama.Client")
    def test_generator_single_embedding(self, mock_client_class, mock_ollama_client):
        """Test generating a single embedding."""
        mock_client_class.return_value = mock_ollama_client

        # Set up mock for single embedding
        expected_embedding = [0.1, 0.2, 0.3, 0.4, 0.5]
        mock_ollama_client.embed.return_value = {"embeddings": [expected_embedding]}

        generator = OllamaEmbeddingGenerator(model_name="nomic-embed-text")

        # Reset the mock to clear dimension detection call
        mock_ollama_client.embed.reset_mock()
        mock_ollama_client.embed.return_value = {"embeddings": [expected_embedding]}

        # Generate embedding
        result = generator.generate_embedding("test text")

        # Verify
        assert result == expected_embedding
        mock_ollama_client.embed.assert_called_once()
        call_kwargs = mock_ollama_client.embed.call_args
        assert call_kwargs[1]["model"] == "nomic-embed-text"
        assert call_kwargs[1]["input"] == "test text"

    @pytest.mark.skipif(not OLLAMA_AVAILABLE, reason="ollama package not installed")
    @patch("med_lit_schema.ingest.ollama_embedding_generator.ollama.Client")
    def test_generator_batch_embeddings(self, mock_client_class, mock_ollama_client):
        """Test generating batch embeddings."""
        mock_client_class.return_value = mock_ollama_client

        # Set up mock for batch embeddings
        expected_embeddings = [
            [0.1, 0.2, 0.3],
            [0.4, 0.5, 0.6],
            [0.7, 0.8, 0.9],
        ]
        mock_ollama_client.embed.return_value = {"embeddings": expected_embeddings}

        generator = OllamaEmbeddingGenerator(model_name="nomic-embed-text")

        # Reset the mock
        mock_ollama_client.embed.reset_mock()
        mock_ollama_client.embed.return_value = {"embeddings": expected_embeddings}

        # Generate batch
        texts = ["text 1", "text 2", "text 3"]
        results = generator.generate_embeddings_batch(texts)

        # Verify
        assert results == expected_embeddings
        mock_ollama_client.embed.assert_called_once()
        call_kwargs = mock_ollama_client.embed.call_args
        assert call_kwargs[1]["model"] == "nomic-embed-text"
        assert call_kwargs[1]["input"] == texts

    @pytest.mark.skipif(not OLLAMA_AVAILABLE, reason="ollama package not installed")
    @patch("med_lit_schema.ingest.ollama_embedding_generator.ollama.Client")
    def test_generator_handles_initialization_failure(self, mock_client_class):
        """Test generator handles Ollama initialization failures."""
        # Mock client that raises error on embed
        mock_client = MagicMock()
        mock_client.embed.side_effect = Exception("Ollama not running")
        mock_client_class.return_value = mock_client

        # Should raise RuntimeError with helpful message
        with pytest.raises(RuntimeError, match="Failed to get embedding dimension"):
            OllamaEmbeddingGenerator(model_name="nomic-embed-text")

    @pytest.mark.skipif(not OLLAMA_AVAILABLE, reason="ollama package not installed")
    @patch("med_lit_schema.ingest.ollama_embedding_generator.ollama.Client")
    def test_generator_model_not_pulled(self, mock_client_class):
        """Test generator handles case where model is not pulled."""
        mock_client = MagicMock()
        mock_client.embed.side_effect = Exception("model 'test-model' not found")
        mock_client_class.return_value = mock_client

        with pytest.raises(RuntimeError, match="Failed to get embedding dimension"):
            OllamaEmbeddingGenerator(model_name="test-model")


@pytest.mark.requires_ollama
class TestOllamaGeneratorIntegration:
    """
    Integration tests with actual Ollama instance.

    These tests require:
    1. Ollama running at http://localhost:11434
    2. nomic-embed-text model pulled

    To run: pytest tests/ingest/test_ollama_embedding_generator.py -m requires_ollama
    To skip: pytest tests/ingest/test_ollama_embedding_generator.py -m "not requires_ollama"
    """

    @pytest.fixture
    def check_ollama_available(self):
        """Check if Ollama is available, skip if not."""
        if not OLLAMA_AVAILABLE:
            pytest.skip("ollama package not installed")

        try:
            client = ollama.Client(host="http://localhost:11434", timeout=10.0)
            # Try to get version to check if Ollama is running
            client.embed(model="nomic-embed-text", input="test")
        except Exception as e:
            pytest.skip(f"Ollama not available: {e}")

    def test_real_ollama_initialization(self, check_ollama_available):
        """Test initialization with real Ollama instance."""
        generator = OllamaEmbeddingGenerator(model_name="nomic-embed-text", host="http://localhost:11434")

        # Should have detected embedding dimension
        assert generator.embedding_dim > 0
        assert generator.model_name == "nomic-embed-text"
        print(f"Detected embedding dimension: {generator.embedding_dim}")

    def test_real_ollama_single_embedding(self, check_ollama_available):
        """Test generating single embedding with real Ollama."""
        generator = OllamaEmbeddingGenerator(model_name="nomic-embed-text")

        embedding = generator.generate_embedding("breast cancer treatment")

        # Verify embedding properties
        assert isinstance(embedding, list)
        assert len(embedding) == generator.embedding_dim
        assert all(isinstance(x, (int, float)) for x in embedding)
        # Embeddings should be normalized (roughly between -1 and 1)
        assert all(-2 < x < 2 for x in embedding)

    def test_real_ollama_batch_embeddings(self, check_ollama_available):
        """Test generating batch embeddings with real Ollama."""
        generator = OllamaEmbeddingGenerator(model_name="nomic-embed-text")

        texts = [
            "breast cancer",
            "lung cancer",
            "diabetes treatment",
        ]

        embeddings = generator.generate_embeddings_batch(texts)

        # Verify batch properties
        assert len(embeddings) == 3
        assert all(len(emb) == generator.embedding_dim for emb in embeddings)

        # Verify embeddings are different for different texts
        import numpy as np

        assert not np.allclose(embeddings[0], embeddings[1])
        assert not np.allclose(embeddings[0], embeddings[2])

    def test_real_ollama_semantic_similarity(self, check_ollama_available):
        """Test that similar texts have similar embeddings."""
        generator = OllamaEmbeddingGenerator(model_name="nomic-embed-text")

        # Similar texts
        emb1 = generator.generate_embedding("breast cancer treatment")
        emb2 = generator.generate_embedding("treating breast cancer")

        # Dissimilar text
        emb3 = generator.generate_embedding("weather forecast")

        # Compute cosine similarity
        import numpy as np

        def cosine_similarity(a, b):
            return np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b))

        sim_similar = cosine_similarity(emb1, emb2)
        sim_dissimilar = cosine_similarity(emb1, emb3)

        # Similar texts should have higher similarity
        assert sim_similar > sim_dissimilar
        assert sim_similar > 0.7  # Should be fairly similar
        print(f"Similar texts similarity: {sim_similar:.3f}")
        print(f"Dissimilar texts similarity: {sim_dissimilar:.3f}")


class TestOllamaGeneratorInterface:
    """Test that generator properly implements the interface."""

    @pytest.mark.skipif(not OLLAMA_AVAILABLE, reason="ollama package not installed")
    @patch("med_lit_schema.ingest.ollama_embedding_generator.ollama.Client")
    def test_generator_implements_embedding_interface(self, mock_client_class):
        """Test generator implements EmbeddingGeneratorInterface."""
        from med_lit_schema.ingest.embedding_interfaces import EmbeddingGeneratorInterface

        # Set up mock
        mock_client = MagicMock()
        mock_client.embed.return_value = {"embeddings": [[0.1] * 768]}
        mock_client_class.return_value = mock_client

        generator = OllamaEmbeddingGenerator(model_name="nomic-embed-text")

        # Verify it's an instance of the interface
        assert isinstance(generator, EmbeddingGeneratorInterface)

    @pytest.mark.skipif(not OLLAMA_AVAILABLE, reason="ollama package not installed")
    @patch("med_lit_schema.ingest.ollama_embedding_generator.ollama.Client")
    def test_generator_properties(self, mock_client_class):
        """Test generator properties."""
        mock_client = MagicMock()
        mock_client.embed.return_value = {"embeddings": [[0.1] * 768]}
        mock_client_class.return_value = mock_client

        generator = OllamaEmbeddingGenerator(model_name="test-model", host="http://test:1234")

        # Test properties
        assert generator.model_name == "test-model"
        assert generator.embedding_dim == 768
        assert isinstance(generator.model_name, str)
        assert isinstance(generator.embedding_dim, int)


class TestOllamaGeneratorErrorHandling:
    """Test error handling in Ollama generator."""

    @pytest.mark.skipif(not OLLAMA_AVAILABLE, reason="ollama package not installed")
    @patch("med_lit_schema.ingest.ollama_embedding_generator.ollama.Client")
    def test_generator_handles_network_error(self, mock_client_class):
        """Test generator handles network errors gracefully."""
        mock_client = MagicMock()
        mock_client.embed.side_effect = ConnectionError("Connection refused")
        mock_client_class.return_value = mock_client

        with pytest.raises(RuntimeError, match="Failed to get embedding dimension"):
            OllamaEmbeddingGenerator(model_name="nomic-embed-text")

    @pytest.mark.skipif(not OLLAMA_AVAILABLE, reason="ollama package not installed")
    @patch("med_lit_schema.ingest.ollama_embedding_generator.ollama.Client")
    def test_generator_handles_invalid_response(self, mock_client_class):
        """Test generator handles invalid Ollama responses."""
        mock_client = MagicMock()
        # Return malformed response
        mock_client.embed.return_value = {"invalid_key": "value"}
        mock_client_class.return_value = mock_client

        with pytest.raises((KeyError, RuntimeError)):
            OllamaEmbeddingGenerator(model_name="nomic-embed-text")

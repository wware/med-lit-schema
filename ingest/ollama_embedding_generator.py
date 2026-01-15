"""
Ollama-based embedding generator implementation.

Provides an implementation of EmbeddingGeneratorInterface that uses a local Ollama instance.
"""

from typing import Optional, List
import ollama

from .embedding_interfaces import EmbeddingGeneratorInterface


class OllamaEmbeddingGenerator(EmbeddingGeneratorInterface):
    """Ollama-based embedding generator."""

    def __init__(self, model_name: str, host: str = "http://localhost:11434", timeout: float = 60.0):
        """
        Initialize the Ollama embedding generator.

        Args:
            model_name: Name of the Ollama model (e.g., "nomic-embed-text")
            host: URL of the Ollama host (e.g., "http://localhost:11434")
            timeout: Timeout in seconds for HTTP requests (default: 60.0)
        """
        self._model_name = model_name
        self._client = ollama.Client(host=host, timeout=timeout)

        # Known embedding dimensions for common models (fallback if connection fails)
        KNOWN_DIMENSIONS = {
            "nomic-embed-text": 768,
            "nomic-embed-text-v1": 768,
            "all-minilm": 384,
            "all-mpnet-base-v2": 768,
        }

        # Determine embedding dimension by encoding a dummy string
        # This requires the model to be downloaded and available
        try:
            dummy_embedding = self._client.embed(model=self._model_name, input="dummy text")
            self._embedding_dim = len(dummy_embedding["embeddings"][0])
        except Exception as e:
            # Fallback to known dimensions if connection fails
            if model_name in KNOWN_DIMENSIONS:
                self._embedding_dim = KNOWN_DIMENSIONS[model_name]
                print(f"Warning: Could not connect to Ollama at {host} to determine embedding dimension.")
                print(f"Using known dimension {self._embedding_dim} for model '{model_name}'.")
                print(f"Connection error: {e}")
            else:
                raise RuntimeError(
                    f"Failed to get embedding dimension from Ollama model '{model_name}'. "
                    f"Ensure the model is pulled and Ollama is running at {host}. "
                    f"Error: {e}"
                )

    def generate_embedding(self, text: str) -> List[float]:
        """Generate a single embedding for text."""
        response = self._client.embed(model=self._model_name, input=text)
        return response["embeddings"][0]

    def generate_embeddings_batch(self, texts: List[str], batch_size: Optional[int] = None) -> List[List[float]]:
        """Generate embeddings for multiple texts in batch."""
        # Ollama's embed function can take multiple prompts directly
        responses = self._client.embed(model=self._model_name, input=texts)
        return responses["embeddings"]

    @property
    def model_name(self) -> str:
        """Name/identifier of the embedding model."""
        return self._model_name

    @property
    def embedding_dim(self) -> int:
        """Dimensionality of embeddings produced by this model."""
        return self._embedding_dim

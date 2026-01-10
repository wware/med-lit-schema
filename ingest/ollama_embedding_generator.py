"""
Ollama-based embedding generator implementation.

Provides an implementation of EmbeddingGeneratorInterface that uses a local Ollama instance.
"""

from typing import Optional, List
import ollama

from .embedding_interfaces import EmbeddingGeneratorInterface


class OllamaEmbeddingGenerator(EmbeddingGeneratorInterface):
    """Ollama-based embedding generator."""

    def __init__(self, model_name: str, host: str = "http://localhost:11434"):
        """
        Initialize the Ollama embedding generator.

        Args:
            model_name: Name of the Ollama model (e.g., "nomic-embed-text")
            host: URL of the Ollama host (e.g., "http://localhost:11434")
        """
        self._model_name = model_name
        self._client = ollama.Client(host=host)

        # Determine embedding dimension by encoding a dummy string
        # This requires the model to be downloaded and available
        try:
            dummy_embedding = self._client.embed(model=self._model_name, prompt="dummy text")
            self._embedding_dim = len(dummy_embedding["embedding"])
        except Exception as e:
            raise RuntimeError(f"Failed to get embedding dimension from Ollama model '{model_name}'. "
                               f"Ensure the model is pulled and Ollama is running. Error: {e}")

    def generate_embedding(self, text: str) -> List[float]:
        """Generate a single embedding for text."""
        response = self._client.embed(model=self._model_name, prompt=text)
        return response["embedding"]

    def generate_embeddings_batch(self, texts: List[str], batch_size: Optional[int] = None) -> List[List[float]]:
        """Generate embeddings for multiple texts in batch."""
        # Ollama's embed function can take multiple prompts directly
        responses = self._client.embed(model=self._model_name, prompt=texts)
        return [res["embedding"] for res in responses]

    @property
    def model_name(self) -> str:
        """Name/identifier of the embedding model."""
        return self._model_name

    @property
    def embedding_dim(self) -> int:
        """Dimensionality of embeddings produced by this model."""
        return self._embedding_dim

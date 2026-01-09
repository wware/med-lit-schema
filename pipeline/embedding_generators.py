"""
Embedding generator implementations.

Provides concrete implementations of EmbeddingGeneratorInterface.
"""

from typing import Optional

from sentence_transformers import SentenceTransformer

from .embedding_interfaces import EmbeddingGeneratorInterface


class SentenceTransformerEmbeddingGenerator(EmbeddingGeneratorInterface):
    """SentenceTransformer-based embedding generator."""

    def __init__(self, model_name: str = "sentence-transformers/all-mpnet-base-v2", device: Optional[str] = None):
        """
        Initialize the embedding generator.

        Args:
            model_name: Name of the sentence-transformers model
            device: Device to run on ('cpu', 'cuda', etc.). If None, auto-detects.
        """
        self._model_name = model_name
        self._model = SentenceTransformer(model_name, device=device)
        # Get embedding dimension by encoding a dummy string
        dummy_embedding = self._model.encode(["dummy"], convert_to_numpy=True)
        self._embedding_dim = len(dummy_embedding[0])

    def generate_embedding(self, text: str) -> list[float]:
        """Generate a single embedding for text."""
        embedding = self._model.encode([text], convert_to_numpy=True)[0]
        return embedding.tolist()

    def generate_embeddings_batch(self, texts: list[str], batch_size: Optional[int] = None) -> list[list[float]]:
        """Generate embeddings for multiple texts in batch."""
        if not texts:
            return []

        embeddings = self._model.encode(
            texts,
            batch_size=batch_size or 32,
            show_progress_bar=len(texts) > 100,
            convert_to_numpy=True,
        )
        return [emb.tolist() for emb in embeddings]

    @property
    def model_name(self) -> str:
        """Name/identifier of the embedding model."""
        return self._model_name

    @property
    def embedding_dim(self) -> int:
        """Dimensionality of embeddings produced by this model."""
        return self._embedding_dim

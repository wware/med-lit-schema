"""Embedding generation for medical entities.

Provides embedding generator implementations using various backends.
Ports logic from med-lit-schema's ingest/embeddings_pipeline.py.
"""

from kgraph.pipeline.embedding import EmbeddingGeneratorInterface

from .embedding_providers import (
    create_embedding_generator,
    HashEmbeddingGenerator,
    OllamaEmbeddingGenerator,
    SentenceTransformerEmbeddingGenerator,
)


class SimpleMedLitEmbeddingGenerator(HashEmbeddingGenerator):
    """Simple hash-based embedding generator (backward compatibility alias).

    This is a placeholder implementation. For production use, use
    create_embedding_generator() to get Ollama or sentence-transformers generators.
    """

    def __init__(self, dimension: int = 32):
        """Initialize hash-based embedding generator."""
        super().__init__(dimension=dimension)


# Re-export for convenience
__all__ = [
    "SimpleMedLitEmbeddingGenerator",
    "OllamaEmbeddingGenerator",
    "SentenceTransformerEmbeddingGenerator",
    "HashEmbeddingGenerator",
    "create_embedding_generator",
]

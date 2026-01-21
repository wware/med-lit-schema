"""Embedding generation for medical entities.

Simple hash-based embedding generator for now. Can be enhanced with
biomedical embedding models (BioBERT, etc.) later.
Ports logic from med-lit-schema's ingest/embeddings_pipeline.py.
"""

import hashlib
from typing import Sequence

from kgraph.pipeline.embedding import EmbeddingGeneratorInterface


class SimpleMedLitEmbeddingGenerator(EmbeddingGeneratorInterface):
    """Simple hash-based embedding generator for medical entities.

    This is a placeholder implementation. For production use, consider:
    - BioBERT embeddings
    - scispaCy embeddings
    - OpenAI/Anthropic embeddings
    - Specialized biomedical embedding models
    - Ollama embeddings (see med-lit-schema/ingest/ollama_embedding_generator.py)
    """

    @property
    def dimension(self) -> int:
        return 32

    async def generate(self, text: str) -> tuple[float, ...]:
        """Generate embedding for a single text.

        Args:
            text: The text to generate an embedding for.

        Returns:
            Tuple of float values representing the embedding vector.
        """
        h = hashlib.sha256(text.lower().encode("utf-8")).digest()
        values = [b / 255.0 for b in h[: self.dimension]]
        mag = sum(v * v for v in values) ** 0.5
        if mag == 0:
            return tuple(0.0 for _ in values)
        return tuple(v / mag for v in values)

    async def generate_batch(self, texts: Sequence[str]) -> list[tuple[float, ...]]:
        """Generate embeddings for multiple texts.

        Args:
            texts: Sequence of texts to generate embeddings for.

        Returns:
            List of embedding tuples in the same order as input texts.
        """
        return [await self.generate(t) for t in texts]

"""
Embedding generation interfaces for ingest.

These ABC interfaces allow the ingest to work with different embedding backends:
- SentenceTransformer for local embeddings
- OpenAI/Cohere/etc. for API-based embeddings
- Custom models for domain-specific embeddings
"""

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Optional


if TYPE_CHECKING:
    pass


class EmbeddingGeneratorInterface(ABC):
    """Abstract interface for generating embeddings from text."""

    @abstractmethod
    def generate_embedding(self, text: str) -> list[float]:
        """
        Generate a single embedding for text.

        Args:
            text: Text to embed

        Returns:
            Embedding vector as list of floats
        """
        pass

    @abstractmethod
    def generate_embeddings_batch(self, texts: list[str], batch_size: Optional[int] = None) -> list[list[float]]:
        """
        Generate embeddings for multiple texts in batch.

        Args:
            texts: List of texts to embed
            batch_size: Optional batch size for processing

        Returns:
            List of embedding vectors
        """
        pass

    @property
    @abstractmethod
    def model_name(self) -> str:
        """Name/identifier of the embedding model."""
        pass

    @property
    @abstractmethod
    def embedding_dim(self) -> int:
        """Dimensionality of embeddings produced by this model."""
        pass


class RelationshipEmbeddingStorageInterface(ABC):
    """Abstract interface for storing relationship embeddings.

    Relationships are identified by their canonical triple: (subject_id, predicate, object_id).
    """

    @abstractmethod
    def store_relationship_embedding(self, subject_id: str, predicate: str, object_id: str, embedding: list[float], model_name: str) -> None:
        """
        Store an embedding for a relationship.

        Args:
            subject_id: Subject entity ID
            predicate: Predicate type
            object_id: Object entity ID
            embedding: Embedding vector
            model_name: Name of the model that generated the embedding
        """
        pass

    @abstractmethod
    def get_relationship_embedding(self, subject_id: str, predicate: str, object_id: str) -> Optional[list[float]]:
        """
        Get the embedding for a relationship.

        Args:
            subject_id: Subject entity ID
            predicate: Predicate type
            object_id: Object entity ID

        Returns:
            Embedding vector or None if not found
        """
        pass

    @abstractmethod
    def find_similar_relationships(self, query_embedding: list[float], top_k: int = 5, threshold: float = 0.85) -> list[tuple[tuple[str, str, str], float]]:
        """
        Find relationships similar to query embedding.

        Args:
            query_embedding: Query embedding vector
            top_k: Maximum number of results to return
            threshold: Minimum similarity threshold

        Returns:
            List of ((subject_id, predicate, object_id), similarity_score) tuples
        """
        pass

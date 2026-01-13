"""
Storage interfaces for ingest data persistence.

These ABC interfaces allow the ingest to work with different storage backends:
- SQLite for testing/development
- PostgreSQL+pgvector for production

All implementations use the domain models from entity.py and relationship.py,
with automatic conversion to/from persistence models via mapper.py.
"""

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Optional

# Use string annotations for forward references to avoid import issues
if TYPE_CHECKING:
    from med_lit_schema.entity import Paper, EvidenceItem, EntityCollectionInterface
    from med_lit_schema.relationship import BaseRelationship
    from med_lit_schema.ingest.embedding_interfaces import RelationshipEmbeddingStorageInterface


class PaperStorageInterface(ABC):
    """Abstract interface for paper storage and retrieval."""

    @abstractmethod
    def add_paper(self, paper: "Paper") -> None:
        """Add or update a paper in storage."""
        pass

    @abstractmethod
    def get_paper(self, paper_id: str) -> Optional["Paper"]:
        """Get a paper by ID."""
        pass

    @abstractmethod
    def list_papers(self, limit: Optional[int] = None, offset: int = 0) -> list["Paper"]:
        """List papers, optionally with pagination."""
        pass

    @property
    @abstractmethod
    def paper_count(self) -> int:
        """Total number of papers in storage."""
        pass


class RelationshipStorageInterface(ABC):
    """Abstract interface for relationship storage and retrieval."""

    @abstractmethod
    def add_relationship(self, relationship: "BaseRelationship") -> None:
        """Add or update a relationship in storage."""
        pass

    @abstractmethod
    def get_relationship(self, subject_id: str, predicate: str, object_id: str) -> Optional["BaseRelationship"]:
        """Get a relationship by its canonical triple (subject_id, predicate, object_id)."""
        pass

    @abstractmethod
    def find_relationships(
        self,
        subject_id: Optional[str] = None,
        predicate: Optional[str] = None,
        object_id: Optional[str] = None,
        limit: Optional[int] = None,
    ) -> list["BaseRelationship"]:
        """Find relationships matching criteria."""
        pass

    @abstractmethod
    def list_relationships(self, limit: Optional[int] = None, offset: int = 0) -> list["BaseRelationship"]:
        """List relationships, optionally with pagination."""
        pass

    @property
    @abstractmethod
    def relationship_count(self) -> int:
        """Total number of relationships in storage."""
        pass


class EvidenceStorageInterface(ABC):
    """Abstract interface for evidence storage and retrieval."""

    @abstractmethod
    def add_evidence(self, evidence: "EvidenceItem") -> None:
        """Add or update evidence in storage."""
        pass

    @abstractmethod
    def get_evidence_by_paper(self, paper_id: str) -> list["EvidenceItem"]:
        """Get all evidence items for a paper."""
        pass

    @abstractmethod
    def get_evidence_for_relationship(self, subject_id: str, predicate: str, object_id: str) -> list["EvidenceItem"]:
        """Get all evidence items supporting a relationship."""
        pass

    @property
    @abstractmethod
    def evidence_count(self) -> int:
        """Total number of evidence items in storage."""
        pass


class PipelineStorageInterface(ABC):
    """Combined interface for all ingest storage needs.

    This is the main interface that ingest stages should use.
    It combines entity, paper, relationship, and evidence storage.
    """

    @property
    @abstractmethod
    def entities(self) -> "EntityCollectionInterface":
        """Access to entity storage."""
        pass

    @property
    @abstractmethod
    def papers(self) -> PaperStorageInterface:
        """Access to paper storage."""
        pass

    @property
    @abstractmethod
    def relationships(self) -> RelationshipStorageInterface:
        """Access to relationship storage."""
        pass

    @property
    @abstractmethod
    def evidence(self) -> EvidenceStorageInterface:
        """Access to evidence storage."""
        pass

    @property
    @abstractmethod
    def relationship_embeddings(self) -> "RelationshipEmbeddingStorageInterface":
        """Access to relationship embedding storage."""
        pass

    @abstractmethod
    def close(self) -> None:
        """Close connections and clean up resources."""
        pass

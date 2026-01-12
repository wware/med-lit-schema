"""
PostgreSQL+pgvector implementation of ingest storage interfaces.

This implementation uses PostgreSQL with pgvector for production storage.
It uses SQLModel persistence models and mapper functions for domain ↔ persistence conversion.
"""

from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from med_lit_schema.entity import (
        Disease,
        Gene,
        Drug,
        Protein,
        Hypothesis,
        StudyDesign,
        StatisticalMethod,
        EvidenceLine,
        BaseMedicalEntity,
    )

from sqlalchemy import create_engine, select
from sqlmodel import Session

from med_lit_schema.storage.interfaces import (
    PaperStorageInterface,
    RelationshipStorageInterface,
    EvidenceStorageInterface,
    PipelineStorageInterface,
)
from med_lit_schema.ingest.embedding_interfaces import RelationshipEmbeddingStorageInterface
from med_lit_schema.entity import (
    Paper,
    EvidenceItem,
    EntityCollectionInterface,
)
from med_lit_schema.relationship import BaseRelationship
from med_lit_schema.mapper import (
    to_persistence as entity_to_persistence,
    to_domain as entity_to_domain,
    relationship_to_persistence,
    relationship_to_domain,
)
from med_lit_schema.storage.models.entity import Entity
from med_lit_schema.storage.models.relationship import Relationship
from med_lit_schema.storage.models.paper import Paper as PaperPersistence
from med_lit_schema.storage.models.evidence import Evidence as EvidencePersistence


class PostgresPaperStorage(PaperStorageInterface):
    """PostgreSQL implementation of paper storage."""

    def __init__(self, session: Session):
        self.session = session

    def add_paper(self, paper: Paper) -> None:
        """Add or update a paper in storage."""
        # Convert domain model to persistence model
        # Note: PaperPersistence is simplified - full Paper domain model has more fields
        # that would need to be stored in a JSONB field or separate tables
        persistence = PaperPersistence(
            id=paper.paper_id,
            title=paper.title,
            abstract=paper.abstract,
            authors=", ".join(paper.authors) if paper.authors else None,
            publication_date=paper.publication_date,
            journal=paper.journal,
            doi=paper.doi,
            pubmed_id=paper.pmid,
            entity_count=len(paper.entities),
            relationship_count=len(paper.relationships),
        )

        # Use merge to handle updates
        self.session.merge(persistence)
        self.session.commit()

        # Note: Full Paper model also has metadata and extraction_provenance
        # which would need to be stored separately or in a JSONB field

    def get_paper(self, paper_id: str) -> Optional[Paper]:
        """Get a paper by ID."""
        persistence = self.session.get(PaperPersistence, paper_id)
        if not persistence:
            return None

        # Convert back to domain model
        # Note: This is a simplified conversion - full implementation would
        # need to load entities, relationships, metadata, and provenance separately
        from ..entity import PaperMetadata, ExtractionProvenance

        return Paper(
            paper_id=persistence.id,
            title=persistence.title,
            abstract=persistence.abstract or "",
            authors=persistence.authors.split(", ") if persistence.authors else [],
            publication_date=persistence.publication_date,
            journal=persistence.journal,
            doi=persistence.doi,
            pmid=persistence.pubmed_id,
            entities=[],  # Would need to load separately
            relationships=[],  # Would need to load separately
            metadata=PaperMetadata(),  # Would need to load from separate storage
            extraction_provenance=ExtractionProvenance(
                extraction_pipeline=None,  # Would need to load
                models={},
                prompt=None,
                execution=None,
            ),
        )

    def list_papers(self, limit: Optional[int] = None, offset: int = 0) -> list[Paper]:
        """List papers, optionally with pagination."""
        statement = select(PaperPersistence).offset(offset)
        if limit:
            statement = statement.limit(limit)
        persistences = self.session.exec(statement).all()

        # Convert to domain models (simplified)
        return [self._persistence_to_domain(p) for p in persistences]

    def _persistence_to_domain(self, persistence: PaperPersistence) -> Paper:
        """Convert persistence model to domain model."""
        from ..entity import PaperMetadata, ExtractionProvenance

        return Paper(
            paper_id=persistence.id,
            title=persistence.title,
            abstract=persistence.abstract or "",
            authors=persistence.authors.split(", ") if persistence.authors else [],
            publication_date=persistence.publication_date,
            journal=persistence.journal,
            doi=persistence.doi,
            pmid=persistence.pubmed_id,
            entities=[],  # Would need to load separately
            relationships=[],  # Would need to load separately
            metadata=PaperMetadata(),
            extraction_provenance=ExtractionProvenance(
                extraction_pipeline=None,
                models={},
                prompt=None,
                execution=None,
            ),
        )

    @property
    def paper_count(self) -> int:
        """Total number of papers in storage."""
        statement = select(PaperPersistence)
        return len(list(self.session.exec(statement).all()))


class PostgresRelationshipStorage(RelationshipStorageInterface):
    """PostgreSQL implementation of relationship storage."""

    def __init__(self, session: Session):
        self.session = session

    def add_relationship(self, relationship: BaseRelationship) -> None:
        """Add or update a relationship in storage."""
        persistence = relationship_to_persistence(relationship)
        self.session.merge(persistence)
        self.session.commit()

    def get_relationship(self, subject_id: str, predicate: str, object_id: str) -> Optional[BaseRelationship]:
        """Get a relationship by its canonical triple."""
        statement = select(Relationship).where(
            Relationship.subject_id == subject_id,
            Relationship.predicate == predicate,
            Relationship.object_id == object_id,
        )
        persistence = self.session.exec(statement).first()
        if persistence:
            return relationship_to_domain(persistence)
        return None

    def find_relationships(
        self,
        subject_id: Optional[str] = None,
        predicate: Optional[str] = None,
        object_id: Optional[str] = None,
        limit: Optional[int] = None,
    ) -> list[BaseRelationship]:
        """Find relationships matching criteria."""
        statement = select(Relationship)

        if subject_id:
            statement = statement.where(Relationship.subject_id == subject_id)
        if predicate:
            statement = statement.where(Relationship.predicate == predicate)
        if object_id:
            statement = statement.where(Relationship.object_id == object_id)

        if limit:
            statement = statement.limit(limit)

        persistences = self.session.exec(statement).all()
        return [relationship_to_domain(p) for p in persistences]

    @property
    def relationship_count(self) -> int:
        """Total number of relationships in storage."""
        statement = select(Relationship)
        return len(list(self.session.exec(statement).all()))


class PostgresEvidenceStorage(EvidenceStorageInterface):
    """PostgreSQL implementation of evidence storage.

    Note: The Evidence SQLModel uses integer IDs and foreign keys, while
    EvidenceItem domain model uses string paper_id. This implementation
    stores EvidenceItem data in the metadata JSONB field.
    """

    def __init__(self, session: Session):
        self.session = session

    def add_evidence(self, evidence: EvidenceItem) -> None:
        """Add or update evidence in storage."""
        # Store EvidenceItem in metadata JSONB field
        # Note: This is a simplified approach - full implementation would
        # need to handle relationship_id and paper_id foreign keys properly
        persistence = EvidencePersistence(
            evidence_type=evidence.study_type or "unknown",
            confidence_score=evidence.confidence,
            metadata_=evidence.model_dump(),
        )
        self.session.add(persistence)
        self.session.commit()

    def get_evidence_by_paper(self, paper_id: str) -> list[EvidenceItem]:
        """Get all evidence items for a paper."""
        # Query by paper_id stored in metadata
        statement = select(EvidencePersistence).where(EvidencePersistence.metadata_["paper_id"].astext == paper_id)
        persistences = self.session.exec(statement).all()
        return [EvidenceItem.model_validate(p.metadata_) for p in persistences]

    def get_evidence_for_relationship(self, subject_id: str, predicate: str, object_id: str) -> list[EvidenceItem]:
        """Get all evidence items supporting a relationship."""
        # Query by relationship info stored in metadata
        statement = select(EvidencePersistence).where(
            EvidencePersistence.metadata_["subject_id"].astext == subject_id,
            EvidencePersistence.metadata_["predicate"].astext == predicate,
            EvidencePersistence.metadata_["object_id"].astext == object_id,
        )
        persistences = self.session.exec(statement).all()
        return [EvidenceItem.model_validate(p.metadata_) for p in persistences]

    @property
    def evidence_count(self) -> int:
        """Total number of evidence items in storage."""
        statement = select(EvidencePersistence)
        return len(list(self.session.exec(statement).all()))


class PostgresEntityCollection(EntityCollectionInterface):
    """PostgreSQL implementation of entity collection using SQLModel."""

    def __init__(self, session: Session):
        self.session = session

    def add_disease(self, entity: "Disease") -> None:
        """Add a disease entity to the collection."""
        persistence = entity_to_persistence(entity)
        self.session.merge(persistence)
        self.session.commit()

    def add_gene(self, entity: "Gene") -> None:
        """Add a gene entity to the collection."""
        persistence = entity_to_persistence(entity)
        self.session.merge(persistence)
        self.session.commit()

    def add_drug(self, entity: "Drug") -> None:
        """Add a drug entity to the collection."""
        persistence = entity_to_persistence(entity)
        self.session.merge(persistence)
        self.session.commit()

    def add_protein(self, entity: "Protein") -> None:
        """Add a protein entity to the collection."""
        persistence = entity_to_persistence(entity)
        self.session.merge(persistence)
        self.session.commit()

    def add_hypothesis(self, entity: "Hypothesis") -> None:
        """Add a hypothesis entity to the collection."""
        persistence = entity_to_persistence(entity)
        self.session.merge(persistence)
        self.session.commit()

    def add_study_design(self, entity: "StudyDesign") -> None:
        """Add a study design entity to the collection."""
        persistence = entity_to_persistence(entity)
        self.session.merge(persistence)
        self.session.commit()

    def add_statistical_method(self, entity: "StatisticalMethod") -> None:
        """Add a statistical method entity to the collection."""
        persistence = entity_to_persistence(entity)
        self.session.merge(persistence)
        self.session.commit()

    def add_evidence_line(self, entity: "EvidenceLine") -> None:
        """Add an evidence line entity to the collection."""
        persistence = entity_to_persistence(entity)
        self.session.merge(persistence)
        self.session.commit()

    def get_by_id(self, entity_id: str) -> Optional["BaseMedicalEntity"]:
        """Get entity by ID, searching across all types."""
        persistence = self.session.get(Entity, entity_id)
        if persistence:
            return entity_to_domain(persistence)
        return None

    def get_by_umls(self, umls_id: str) -> Optional["Disease"]:
        """Get disease by UMLS ID."""
        statement = select(Entity).where(Entity.umls_id == umls_id, Entity.entity_type == "disease")
        persistence = self.session.exec(statement).first()
        if persistence:
            domain = entity_to_domain(persistence)
            if isinstance(domain, Disease):
                return domain
        return None

    def get_by_hgnc(self, hgnc_id: str) -> Optional["Gene"]:
        """Get gene by HGNC ID."""
        statement = select(Entity).where(Entity.hgnc_id == hgnc_id, Entity.entity_type == "gene")
        persistence = self.session.exec(statement).first()
        if persistence:
            domain = entity_to_domain(persistence)
            if isinstance(domain, Gene):
                return domain
        return None

    def find_by_embedding(self, query_embedding: list[float], top_k: int = 5, threshold: float = 0.85) -> list[tuple["BaseMedicalEntity", float]]:
        """Find entities similar to query embedding using pgvector."""
        # Use pgvector cosine similarity
        # Note: This requires the embedding column to be vector type
        from sqlalchemy import func, cast
        from pgvector.sqlalchemy import Vector

        # Convert list to vector for query
        import json

        embedding_json = json.dumps(query_embedding)

        # Use 1 - cosine_distance for similarity
        statement = (
            select(Entity, (1 - func.cosine_distance(cast(Entity.embedding, Vector), cast(embedding_json, Vector))).label("similarity"))
            .where(Entity.embedding.isnot(None))
            .order_by("similarity")
            .limit(top_k)
        )

        results = self.session.exec(statement).all()
        entities_with_scores = []
        for entity_persistence, similarity in results:
            if similarity >= threshold:
                domain = entity_to_domain(entity_persistence)
                entities_with_scores.append((domain, float(similarity)))

        return entities_with_scores

    def list_entities(self, limit: Optional[int] = None, offset: int = 0) -> list["BaseMedicalEntity"]:
        """List entities, optionally with pagination."""
        statement = select(Entity).offset(offset)
        if limit is not None:
            statement = statement.limit(limit)

        persistences = self.session.exec(statement).all()
        return [entity_to_domain(p) for p in persistences]

    @property
    def entity_count(self) -> int:
        """Total number of entities across all types."""
        statement = select(Entity)
        return len(list(self.session.exec(statement).all()))


class PostgresRelationshipEmbeddingStorage(RelationshipEmbeddingStorageInterface):
    """PostgreSQL+pgvector implementation of relationship embedding storage."""

    def __init__(self, session: Session):
        self.session = session

    def store_relationship_embedding(self, subject_id: str, predicate: str, object_id: str, embedding: list[float], model_name: str) -> None:
        """Store an embedding for a relationship."""
        # TODO: Implement pgvector-based storage
        raise NotImplementedError("PostgreSQL relationship embedding storage not yet implemented")

    def get_relationship_embedding(self, subject_id: str, predicate: str, object_id: str) -> Optional[list[float]]:
        """Get the embedding for a relationship."""
        # TODO: Implement pgvector-based retrieval
        raise NotImplementedError("PostgreSQL relationship embedding storage not yet implemented")

    def find_similar_relationships(self, query_embedding: list[float], top_k: int = 5, threshold: float = 0.85) -> list[tuple[tuple[str, str, str], float]]:
        """Find relationships similar to query embedding."""
        # TODO: Implement pgvector-based similarity search
        raise NotImplementedError("PostgreSQL relationship embedding storage not yet implemented")


class PostgresPipelineStorage(PipelineStorageInterface):
    """PostgreSQL+pgvector implementation of combined ingest storage.

    Uses PostgreSQL with pgvector for production storage.
    """

    def __init__(self, database_url: str):
        """Initialize PostgreSQL storage.

        Args:
            database_url: PostgreSQL connection string
        """
        self.engine = create_engine(database_url)
        self.session = Session(self.engine)

        # Initialize storage components
        self._papers = PostgresPaperStorage(self.session)
        self._relationships = PostgresRelationshipStorage(self.session)
        self._evidence = PostgresEvidenceStorage(self.session)
        self._relationship_embeddings = PostgresRelationshipEmbeddingStorage(self.session)
        self._entities = PostgresEntityCollection(self.session)

    @property
    def entities(self) -> EntityCollectionInterface:
        """Access to entity storage."""
        return self._entities

    @property
    def papers(self) -> PaperStorageInterface:
        """Access to paper storage."""
        return self._papers

    @property
    def relationships(self) -> RelationshipStorageInterface:
        """Access to relationship storage."""
        return self._relationships

    @property
    def evidence(self) -> EvidenceStorageInterface:
        """Access to evidence storage."""
        return self._evidence

    @property
    def relationship_embeddings(self) -> RelationshipEmbeddingStorageInterface:
        """Access to relationship embedding storage."""
        return self._relationship_embeddings

    def close(self) -> None:
        """Close connections and clean up resources."""
        self.session.close()
        self.engine.dispose()

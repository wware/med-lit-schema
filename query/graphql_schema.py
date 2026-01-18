"""
GraphQL schema for the Medical Literature Knowledge Graph API.

This schema uses proper Strawberry types for type safety and better GraphQL introspection.
"""

import strawberry
from typing import List, Optional
from strawberry.types import Info


@strawberry.type
class Entity:
    """Medical entity GraphQL type."""
    entity_id: str
    name: str
    entity_type: str
    synonyms: Optional[List[str]] = None
    source: Optional[str] = None


@strawberry.type
class Paper:
    """Research paper GraphQL type."""
    id: str
    title: str
    authors: Optional[List[str]] = None
    abstract: Optional[str] = None
    doi: Optional[str] = None
    pmid: Optional[str] = None


@strawberry.type
class Relationship:
    """Relationship GraphQL type."""
    id: Optional[int] = None
    subject_id: str
    predicate: str
    object_id: str
    confidence: Optional[float] = None
    source_papers: Optional[List[str]] = None


@strawberry.type
class Query:
    @strawberry.field
    def paper(self, info: Info, id: str) -> Optional[Paper]:
        """Retrieve a single paper by its ID."""
        storage = info.context["storage"]
        paper = storage.papers.get_paper(paper_id=id)
        if paper:
            return Paper(
                id=paper.id,
                title=paper.title,
                authors=getattr(paper, 'authors', None),
                abstract=getattr(paper, 'abstract', None),
                doi=getattr(paper, 'doi', None),
                pmid=getattr(paper, 'pmid', None),
            )
        return None

    @strawberry.field
    def entity(self, info: Info, id: str) -> Optional[Entity]:
        """Retrieve a single medical entity by its canonical ID."""
        storage = info.context["storage"]
        entity = storage.entities.get_by_id(entity_id=id)
        if entity:
            entity_type = entity.entity_type.value if hasattr(entity.entity_type, 'value') else str(entity.entity_type)
            return Entity(
                entity_id=entity.entity_id,
                name=entity.name,
                entity_type=entity_type,
                synonyms=getattr(entity, 'synonyms', None),
                source=getattr(entity, 'source', None),
            )
        return None

    @strawberry.field
    def entities(
        self,
        info: Info,
        limit: int = 100,
        offset: int = 0,
    ) -> List[Entity]:
        """List all medical entities with pagination."""
        storage = info.context["storage"]
        entities = storage.entities.list_entities(limit=limit, offset=offset)
        
        result = []
        for e in entities:
            entity_type = e.entity_type.value if hasattr(e.entity_type, 'value') else str(e.entity_type)
            result.append(Entity(
                entity_id=e.entity_id,
                name=e.name,
                entity_type=entity_type,
                synonyms=getattr(e, 'synonyms', None),
                source=getattr(e, 'source', None),
            ))
        
        return result

    @strawberry.field
    def relationships(
        self,
        info: Info,
        subject_id: Optional[str] = None,
        predicate: Optional[str] = None,
        object_id: Optional[str] = None,
        limit: int = 100,
    ) -> List[Relationship]:
        """Find relationships based on subject, predicate, or object."""
        storage = info.context["storage"]
        relationships = storage.relationships.find_relationships(
            subject_id=subject_id,
            predicate=predicate,
            object_id=object_id,
            limit=limit,
        )
        
        result = []
        for rel in relationships:
            result.append(Relationship(
                id=getattr(rel, 'id', None),
                subject_id=rel.subject_id,
                predicate=rel.predicate,
                object_id=rel.object_id,
                confidence=getattr(rel, 'confidence', None),
                source_papers=getattr(rel, 'source_papers', None),
            ))
        
        return result

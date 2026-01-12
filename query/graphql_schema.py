"""
GraphQL schema for the Medical Literature Knowledge Graph API.

This is a simplified schema that avoids complex nested type conversions.
For production use, consider using manual type definitions or resolving
the Pydantic integration issues with nested models.
"""

import strawberry
from typing import List, Optional
from strawberry.scalars import JSON
from .storage_factory import get_storage


@strawberry.type
class Query:
    @strawberry.field
    def paper(self, id: str) -> Optional[JSON]:
        """
        Retrieve a single paper by its ID.

        Note: Returns a JSON-serializable dict. For full type safety,
        define explicit Strawberry types for all nested models.
        """
        storage = get_storage()
        paper = storage.papers.get_paper(paper_id=id)
        if paper:
            return paper.model_dump()
        return None

    @strawberry.field
    def entity(self, id: str) -> Optional[JSON]:
        """
        Retrieve a single medical entity by its canonical ID.

        Note: Returns a JSON-serializable dict. For full type safety,
        define explicit Strawberry types for all entity types.
        """
        storage = get_storage()
        entity = storage.entities.get_by_id(entity_id=id)
        if entity:
            return entity.model_dump()
        return None

    @strawberry.field
    def entities(
        self,
        limit: int = 100,
        offset: int = 0,
    ) -> List[JSON]:
        """
        List all medical entities with pagination.

        Note: Returns JSON-serializable dicts. For full type safety,
        define explicit Strawberry types for all entity types.
        """
        storage = get_storage()
        entities = storage.entities.list_entities(limit=limit, offset=offset)
        return [entity.model_dump() for entity in entities]

    @strawberry.field
    def relationships(
        self,
        subject_id: Optional[str] = None,
        predicate: Optional[str] = None,
        object_id: Optional[str] = None,
        limit: int = 100,
    ) -> List[JSON]:
        """
        Find relationships based on subject, predicate, or object.

        Note: Returns JSON-serializable dicts. For full type safety,
        define explicit Strawberry types for all relationship types.
        """
        storage = get_storage()
        relationships = storage.relationships.find_relationships(
            subject_id=subject_id,
            predicate=predicate,
            object_id=object_id,
            limit=limit,
        )
        return [rel.model_dump() for rel in relationships]

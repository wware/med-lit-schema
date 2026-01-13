"""
REST API router for the Medical Literature Knowledge Graph.
"""

from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from med_lit_schema.entity import BaseMedicalEntity, Paper
from med_lit_schema.relationship import BaseRelationship
from med_lit_schema.storage.interfaces import PipelineStorageInterface
from med_lit_schema.ingest.embedding_generators import SentenceTransformerEmbeddingGenerator

from ..storage_factory import get_storage

router = APIRouter(prefix="/api/v1")


class SemanticSearchRequest(BaseModel):
    """
    Request model for semantic search.

    Attributes:

        query_text: Natural language query text to search for
        top_k: Maximum number of results to return (default: 10)
        threshold: Minimum similarity threshold (0.0-1.0, default: 0.7)
    """

    query_text: str = Field(..., description="Natural language query text to search for")
    top_k: int = Field(10, ge=1, le=100, description="Maximum number of results to return")
    threshold: float = Field(0.7, ge=0.0, le=1.0, description="Minimum similarity threshold")


class SemanticSearchResult(BaseModel):
    """
    Result model for semantic search.

    Attributes:

        subject_id: Subject entity canonical ID
        predicate: Relationship predicate
        object_id: Object entity canonical ID
        similarity_score: Similarity score (0.0-1.0)
    """

    subject_id: str = Field(..., description="Subject entity canonical ID")
    predicate: str = Field(..., description="Relationship predicate")
    object_id: str = Field(..., description="Object entity canonical ID")
    similarity_score: float = Field(..., description="Similarity score (0.0-1.0)")


# Initialize embedding generator singleton
_embedding_generator: Optional[SentenceTransformerEmbeddingGenerator] = None


def get_embedding_generator() -> SentenceTransformerEmbeddingGenerator:
    """Get or create the embedding generator singleton."""
    global _embedding_generator
    if _embedding_generator is None:
        _embedding_generator = SentenceTransformerEmbeddingGenerator()
    return _embedding_generator


@router.get(
    "/papers/{paper_id}",
    response_model=Paper,
    summary="Get a single paper by its ID",
)
async def get_paper_by_id(paper_id: str, storage: PipelineStorageInterface = Depends(get_storage)):
    """
    Retrieve a single research paper by its unique identifier (e.g., PMC ID, DOI, PMID).
    """
    paper = storage.papers.get_paper(paper_id=paper_id)
    if not paper:
        raise HTTPException(status_code=404, detail="Paper not found")
    return paper


@router.get(
    "/entities/{entity_id}",
    response_model=BaseMedicalEntity,
    summary="Get a single entity by its canonical ID",
)
async def get_entity_by_id(entity_id: str, storage: PipelineStorageInterface = Depends(get_storage)):
    """
    Retrieve a single medical entity (e.g., Disease, Gene, Drug) by its
    canonical identifier (e.g., UMLS ID, HGNC ID).
    """
    entity = storage.entities.get_by_id(entity_id=entity_id)
    if not entity:
        raise HTTPException(status_code=404, detail="Entity not found")
    return entity


@router.get(
    "/entities",
    response_model=List[BaseMedicalEntity],
    summary="List all entities",
)
async def list_entities(limit: int = 100, offset: int = 0, storage: PipelineStorageInterface = Depends(get_storage)):
    """
    List all medical entities in the knowledge graph.

    - **limit**: Maximum number of entities to return.
    - **offset**: Number of entities to skip for pagination.
    """
    return storage.entities.list_entities(limit=limit, offset=offset)


@router.get(
    "/relationships",
    response_model=List[BaseRelationship],
    summary="Find relationships between entities",
)
async def find_relationships(
    subject_id: Optional[str] = None,
    predicate: Optional[str] = None,
    object_id: Optional[str] = None,
    limit: int = 100,
    storage: PipelineStorageInterface = Depends(get_storage),
):
    """
    Find relationships based on subject, predicate, or object.

    - **subject_id**: Canonical ID of the subject entity.
    - **predicate**: Type of the relationship (e.g., 'TREATS', 'CAUSES').
    - **object_id**: Canonical ID of the object entity.
    - **limit**: Maximum number of relationships to return.
    """
    relationships = storage.relationships.find_relationships(
        subject_id=subject_id,
        predicate=predicate,
        object_id=object_id,
        limit=limit,
    )
    return relationships


@router.post(
    "/search/semantic",
    response_model=List[SemanticSearchResult],
    summary="Semantic search for relationships",
)
async def semantic_search(
    request: SemanticSearchRequest,
    storage: PipelineStorageInterface = Depends(get_storage),
    embedding_gen: SentenceTransformerEmbeddingGenerator = Depends(get_embedding_generator),
):
    """
    Perform semantic search to find relationships similar to the query text.

    This endpoint generates an embedding for the query text and searches for
    similar relationships in the knowledge graph using vector similarity.

    - **query_text**: Natural language query describing what to search for
    - **top_k**: Maximum number of results to return (1-100)
    - **threshold**: Minimum similarity threshold (0.0-1.0)

    Example:

        >>> {
        ...     "query_text": "drugs that treat diabetes",
        ...     "top_k": 10,
        ...     "threshold": 0.7
        ... }
    """
    # Generate embedding for the query text
    query_embedding = embedding_gen.generate_embedding(request.query_text)

    # Search for similar relationships
    similar_relationships = storage.relationship_embeddings.find_similar_relationships(
        query_embedding=query_embedding,
        top_k=request.top_k,
        threshold=request.threshold,
    )

    # Format results
    results = [
        SemanticSearchResult(
            subject_id=subject_id,
            predicate=predicate,
            object_id=object_id,
            similarity_score=score,
        )
        for (subject_id, predicate, object_id), score in similar_relationships
    ]

    return results

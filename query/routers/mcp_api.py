"""
MCP (Model Context Protocol) API integration for AI agent access.

This module provides AI-friendly tools for querying the medical knowledge graph,
designed for integration with LLMs like Claude, GPT, etc.
"""

from typing import List, Optional

from mcp.server import FastMCP

from med_lit_schema.entity import Disease, Drug, Gene

from ..storage_factory import get_storage


# Create FastMCP server instance
mcp_server = FastMCP(
    name="Medical Knowledge Graph",
    instructions="Query interface for medical literature knowledge graph with tools for finding treatments, genes, entities, and papers.",
)


# Tool implementations using FastMCP decorators
@mcp_server.tool()
async def find_treatments(disease_name: str, limit: int = 10) -> List[dict]:
    """
    Find drugs that treat a specific disease.

    This tool searches for Disease-TREATS-Drug relationships in the knowledge graph.
    It finds diseases matching the query name and returns all drugs that treat them.

    Args:
        disease_name: Name or partial name of the disease
        limit: Maximum number of treatments to return (default: 10)

    Returns:
        List of treatment dictionaries with drug and disease information
    """
    storage = get_storage()

    # Search for diseases matching the name
    all_entities = storage.entities.list_entities(limit=1000)
    matching_diseases = [entity for entity in all_entities if isinstance(entity, Disease) and disease_name.lower() in entity.name.lower()]

    if not matching_diseases:
        return []

    # Find treatments for each disease
    results = []
    for disease in matching_diseases[:5]:  # Limit to first 5 diseases
        # Find all relationships where this disease is the object and predicate is TREATS
        relationships = storage.relationships.find_relationships(
            predicate="TREATS",
            object_id=disease.canonical_id,
            limit=limit,
        )

        for rel in relationships:
            # Get the drug entity
            drug_entity = storage.entities.get_by_id(rel.subject_id)
            if drug_entity and isinstance(drug_entity, Drug):
                # Count evidence items
                evidence_items = storage.evidence.get_evidence_for_relationship(
                    subject_id=rel.subject_id,
                    predicate=rel.predicate,
                    object_id=rel.object_id,
                )

                results.append(
                    {
                        "drug_id": drug_entity.canonical_id,
                        "drug_name": drug_entity.name,
                        "disease_id": disease.canonical_id,
                        "disease_name": disease.name,
                        "evidence_count": len(evidence_items),
                    }
                )

    return results[:limit]


@mcp_server.tool()
async def find_related_genes(disease_name: str, limit: int = 10) -> List[dict]:
    """
    Find genes associated with or implicated in a disease.

    This tool searches for Disease-Gene relationships in the knowledge graph.

    Args:
        disease_name: Name or partial name of the disease
        limit: Maximum number of genes to return (default: 10)

    Returns:
        List of gene dictionaries with relationship information
    """
    storage = get_storage()

    # Search for diseases matching the name
    all_entities = storage.entities.list_entities(limit=1000)
    matching_diseases = [entity for entity in all_entities if isinstance(entity, Disease) and disease_name.lower() in entity.name.lower()]

    if not matching_diseases:
        return []

    # Find related genes
    results = []
    for disease in matching_diseases[:5]:
        # Find relationships where disease is subject or object
        relationships = storage.relationships.find_relationships(
            subject_id=disease.canonical_id,
            limit=limit * 2,  # Get more to filter
        )
        relationships += storage.relationships.find_relationships(
            object_id=disease.canonical_id,
            limit=limit * 2,
        )

        for rel in relationships:
            # Check if the other entity is a gene
            gene_id = rel.object_id if rel.subject_id == disease.canonical_id else rel.subject_id
            gene_entity = storage.entities.get_by_id(gene_id)

            if gene_entity and isinstance(gene_entity, Gene):
                results.append(
                    {
                        "gene_id": gene_entity.canonical_id,
                        "gene_symbol": gene_entity.symbol,
                        "relationship_type": rel.predicate,
                        "disease_id": disease.canonical_id,
                        "disease_name": disease.name,
                    }
                )

    return results[:limit]


@mcp_server.tool()
async def get_entity(entity_id: str) -> Optional[dict]:
    """
    Retrieve a specific entity (Disease, Drug, Gene, Protein) by its canonical ID.

    Returns the full entity data including all metadata and identifiers.

    Args:
        entity_id: Canonical ID of the entity

    Returns:
        Entity dictionary or None if not found
    """
    storage = get_storage()
    entity = storage.entities.get_by_id(entity_id)

    if entity:
        return entity.model_dump()
    return None


@mcp_server.tool()
async def search_entities(query: str, entity_type: Optional[str] = None, limit: int = 10) -> List[dict]:
    """
    Search for entities matching a query string.

    This performs a simple name-based search. For semantic search,
    use the /api/v1/search/semantic endpoint instead.

    Args:
        query: Search query text
        entity_type: Optional entity type filter (Disease, Drug, Gene, Protein)
        limit: Maximum number of results to return (default: 10)

    Returns:
        List of matching entity dictionaries
    """
    storage = get_storage()

    # Get all entities (in production, this should use proper search)
    all_entities = storage.entities.list_entities(limit=1000)

    # Filter by query and type
    results = []
    query_lower = query.lower()

    for entity in all_entities:
        # Check name match
        if query_lower not in entity.name.lower():
            continue

        # Check type filter
        if entity_type:
            entity_type_name = type(entity).__name__
            if entity_type_name != entity_type:
                continue

        results.append(entity.model_dump())

        if len(results) >= limit:
            break

    return results


@mcp_server.tool()
async def get_paper(paper_id: str) -> Optional[dict]:
    """
    Retrieve a research paper by its ID (PMC, DOI, or PMID).

    Returns the full paper metadata including title, abstract, and identifiers.

    Args:
        paper_id: ID of the paper (PMC, DOI, or PMID)

    Returns:
        Paper dictionary or None if not found
    """
    storage = get_storage()
    paper = storage.papers.get_paper(paper_id)

    if paper:
        return paper.model_dump()
    return None


# Export the MCP server instance for mounting in the main FastAPI app
__all__ = ["mcp_server"]

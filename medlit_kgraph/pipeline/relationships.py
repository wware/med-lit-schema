"""Relationship extraction from journal articles.

Extracts relationships from Paper JSON format or directly from text using pattern matching/LLMs.
Ports logic from med-lit-schema's ingest/claims_pipeline.py.
"""

from datetime import datetime, timezone
from typing import Sequence, Any

from kgraph.document import BaseDocument
from kgraph.entity import BaseEntity
from kgraph.pipeline.interfaces import RelationshipExtractorInterface
from kgraph.relationship import BaseRelationship

from ..domain.relationships import MedicalClaimRelationship


class MedLitRelationshipExtractor(RelationshipExtractorInterface):
    """Extract relationships from journal articles.

    This extractor works with:
    1. Pre-extracted relationships in Paper JSON format (from med-lit-schema)
    2. Direct text extraction using pattern matching (TODO: add LLM extraction)

    Ports logic from med-lit-schema's ingest/claims_pipeline.py.
    """

    async def extract(
        self,
        document: BaseDocument,
        entities: Sequence[BaseEntity],
    ) -> list[BaseRelationship]:
        """Extract relationships from a journal article.

        If the document metadata contains pre-extracted relationships (from med-lit-schema),
        we convert those to BaseRelationship objects. Otherwise, returns empty list.

        TODO: Add pattern-based and LLM-based extraction for raw text.

        Args:
            document: The journal article document.
            entities: The resolved entities from this document.

        Returns:
            List of BaseRelationship objects representing relationships in the paper.
        """
        relationships: list[BaseRelationship] = []

        # Check if document has pre-extracted relationships in metadata
        # (from med-lit-schema's Paper format)
        relationships_data = document.metadata.get("relationships", [])

        if not relationships_data:
            # No pre-extracted relationships - return empty list
            # TODO: Use pattern matching or LLM here to extract from text
            # See med-lit-schema/ingest/claims_pipeline.py for reference
            return relationships

        # Create entity lookup by ID for quick access
        entity_by_id: dict[str, BaseEntity] = {e.entity_id: e for e in entities}

        # Convert pre-extracted relationships to BaseRelationship objects
        for rel_data in relationships_data:
            # Handle both dict format and AssertedRelationship format
            if isinstance(rel_data, dict):
                subject_id = rel_data.get("subject_id", "")
                predicate = rel_data.get("predicate", "")
                object_id = rel_data.get("object_id", "")
                confidence = rel_data.get("confidence", 0.5)
                evidence = rel_data.get("evidence", "")
                section = rel_data.get("section", "")

                # Validate that entities exist
                if subject_id not in entity_by_id or object_id not in entity_by_id:
                    # Skip relationships where entities weren't resolved
                    continue

                # Normalize predicate (lowercase, handle enum values)
                if isinstance(predicate, str):
                    predicate = predicate.lower()
                else:
                    # If it's an enum, get its value
                    predicate = str(predicate).lower()

                # Create relationship with evidence and provenance in metadata
                metadata: dict[str, Any] = {
                    "evidence": evidence,
                    "section": section,
                }

                # Add any additional metadata from the relationship
                if "metadata" in rel_data and isinstance(rel_data["metadata"], dict):
                    metadata.update(rel_data["metadata"])

                relationship = MedicalClaimRelationship(
                    subject_id=subject_id,
                    predicate=predicate,
                    object_id=object_id,
                    confidence=float(confidence),
                    source_documents=(document.document_id,),
                    created_at=datetime.now(timezone.utc),
                    last_updated=None,
                    metadata=metadata,
                )

                relationships.append(relationship)

        return relationships

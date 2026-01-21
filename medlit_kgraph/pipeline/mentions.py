"""Entity mention extraction from journal articles.

Extracts entity mentions from Paper JSON format or directly from text using NER models.
Ports logic from med-lit-schema's ingest/ner_pipeline.py.
"""

from kgraph.document import BaseDocument
from kgraph.entity import EntityMention
from kgraph.pipeline.interfaces import EntityExtractorInterface


class MedLitEntityExtractor(EntityExtractorInterface):
    """Extract entity mentions from journal articles.

    This extractor works with:
    1. Pre-extracted entities in Paper JSON format (from med-lit-schema)
    2. Direct text extraction using NER models (BioBERT, scispaCy, Ollama)

    For now, handles pre-extracted entities. NER model integration is TODO.
    """

    async def extract(self, document: BaseDocument) -> list[EntityMention]:
        """Extract entity mentions from a journal article.

        If the document metadata contains pre-extracted entities (from med-lit-schema),
        we convert those to EntityMention objects. Otherwise, returns empty list.

        TODO: Add NER model extraction for raw text.

        Args:
            document: The journal article document.

        Returns:
            List of EntityMention objects representing entities mentioned in the paper.
        """
        mentions: list[EntityMention] = []

        # Check if document has pre-extracted entities in metadata
        # (from med-lit-schema's Paper format)
        entities_data = document.metadata.get("entities", [])

        if not entities_data:
            # No pre-extracted entities - return empty list
            # TODO: Use NER models here to extract from text
            # See med-lit-schema/ingest/ner_pipeline.py for reference
            return mentions

        # Convert pre-extracted entities to EntityMention objects
        for entity_ref in entities_data:
            # Handle both dict format and EntityReference format
            if isinstance(entity_ref, dict):
                entity_id = entity_ref.get("id", "")
                entity_name = entity_ref.get("name", "")
                entity_type = entity_ref.get("type", "")

                # Map med-lit-schema entity types to kgraph entity types
                # (they should match, but normalize just in case)
                entity_type = entity_type.lower() if entity_type else ""

                # Create mention (we don't have exact text spans, so use 0 offsets)
                # The text is the name as it appeared in the paper
                mention = EntityMention(
                    text=entity_name,
                    entity_type=entity_type,
                    start_offset=0,  # Unknown from pre-extracted format
                    end_offset=0,  # Unknown from pre-extracted format
                    confidence=0.9,  # Assume high confidence for pre-extracted
                    context=None,
                    metadata={
                        "canonical_id_hint": entity_id,
                        "document_id": document.document_id,
                        "pre_extracted": True,
                    },
                )
                mentions.append(mention)

        return mentions

"""Entity mention extraction from journal articles.

Extracts entity mentions from Paper JSON format or directly from text using NER models.
Ports logic from med-lit-schema's ingest/ner_pipeline.py.
"""

from typing import Optional
import re

from kgraph.document import BaseDocument
from kgraph.entity import EntityMention
from kgraph.pipeline.interfaces import EntityExtractorInterface

from .ner_extractors import NERExtractorInterface, create_ner_extractor

# Stopwords for entity filtering
STOPWORDS = frozenset({
    "the", "and", "or", "but", "with", "from", "that", "this",
    "these", "those", "their", "there", "a", "an", "as", "at",
})


class MedLitEntityExtractor(EntityExtractorInterface):
    """Extract entity mentions from journal articles.

    This extractor works with:
    1. Pre-extracted entities in Paper JSON format (from med-lit-schema)
    2. Direct text extraction using NER models (BioBERT, scispaCy, Ollama)

    Supports multiple NER backends via the NERExtractorInterface.
    """

    def __init__(
        self,
        ner_extractor: Optional[NERExtractorInterface] = None,
        ner_provider: str = "none",  # "none", "biobert", "scispacy", "ollama"
        **ner_kwargs,
    ):
        """Initialize entity extractor.

        Args:
            ner_extractor: Optional NER extractor instance
            ner_provider: NER provider name ("none", "biobert", "scispacy", "ollama")
            **ner_kwargs: Provider-specific arguments (e.g., model, host for Ollama)
        """
        if ner_extractor is not None:
            self._ner_extractor = ner_extractor
        elif ner_provider != "none":
            self._ner_extractor = create_ner_extractor(ner_provider, **ner_kwargs)
        else:
            self._ner_extractor = None

    async def extract(self, document: BaseDocument) -> list[EntityMention]:
        """Extract entity mentions from a journal article.

        First checks for pre-extracted entities in metadata. If none found
        and an NER extractor is configured, extracts from document text.

        Args:
            document: The journal article document.

        Returns:
            List of EntityMention objects representing entities mentioned in the paper.
        """
        mentions: list[EntityMention] = []

        # Check if document has pre-extracted entities in metadata
        # (from med-lit-schema's Paper format)
        entities_data = document.metadata.get("entities", [])

        if entities_data:
            # Convert pre-extracted entities to EntityMention objects
            for entity_ref in entities_data:
                if isinstance(entity_ref, dict):
                    entity_id = entity_ref.get("id", "")
                    entity_name = entity_ref.get("name", "")
                    entity_type = entity_ref.get("type", "")

                    # Map med-lit-schema entity types to kgraph entity types
                    entity_type = entity_type.lower() if entity_type else ""

                    mention = EntityMention(
                        text=entity_name,
                        entity_type=entity_type,
                        start_offset=0,  # Unknown from pre-extracted format
                        end_offset=0,
                        confidence=0.9,  # Assume high confidence for pre-extracted
                        context=None,
                        metadata={
                            "canonical_id_hint": entity_id,
                            "document_id": document.document_id,
                            "pre_extracted": True,
                        },
                    )
                    mentions.append(mention)

        # If no pre-extracted entities and NER extractor is available, extract from text
        elif self._ner_extractor is not None:
            # Extract from document sections
            sections = document.get_sections()
            text_chunks = []

            for section_name, section_text in sections:
                if section_text:
                    text_chunks.append(section_text)

            if not text_chunks:
                return mentions

            # Combine text chunks (limit to reasonable size for NER)
            full_text = "\n\n".join(text_chunks)
            # Chunk into smaller pieces if too large (8000 chars per chunk)
            chunk_size = 8000
            chunks = [
                full_text[i : i + chunk_size]
                for i in range(0, len(full_text), chunk_size)
            ]

            # Extract entities from each chunk
            seen_entities: set[str] = set()  # Deduplicate by name

            for chunk in chunks:
                if not chunk.strip():
                    continue

                try:
                    ner_results = self._ner_extractor.extract_entities(chunk)
                except Exception as e:
                    print(f"Warning: NER extraction failed for chunk: {e}")
                    continue

                for ent in ner_results:
                    entity_name = ent.get("word", "").strip()
                    entity_type = ent.get("entity_group", "disease").lower()
                    confidence = float(ent.get("score", 0.5))
                    start = ent.get("start", 0)
                    end = ent.get("end", 0)

                    # Basic hygiene filters
                    if len(entity_name) < 3:
                        continue
                    if entity_name.startswith("##"):
                        continue
                    if entity_name.lower() in STOPWORDS:
                        continue
                    if confidence < 0.5:
                        continue

                    # Deduplicate by name (case-insensitive)
                    entity_key = entity_name.lower()
                    if entity_key in seen_entities:
                        continue
                    seen_entities.add(entity_key)

                    # Find context around the entity
                    context_start = max(0, start - 50)
                    context_end = min(len(chunk), end + 50)
                    context = chunk[context_start:context_end] if context_start < context_end else None

                    mention = EntityMention(
                        text=entity_name,
                        entity_type=entity_type,
                        start_offset=start,
                        end_offset=end,
                        confidence=confidence,
                        context=context,
                        metadata={
                            "document_id": document.document_id,
                            "section": "body",  # Could track section name
                            "extracted_by": self._ner_extractor.__class__.__name__,
                        },
                    )
                    mentions.append(mention)

        return mentions

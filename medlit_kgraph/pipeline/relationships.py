"""Relationship extraction from journal articles.

Extracts relationships from Paper JSON format or directly from text using pattern matching/LLMs.
Ports logic from med-lit-schema's ingest/claims_pipeline.py.
"""

import re
from datetime import datetime, timezone
from typing import Sequence, Any, Optional

from kgraph.document import BaseDocument
from kgraph.entity import BaseEntity
from kgraph.pipeline.interfaces import RelationshipExtractorInterface
from kgraph.relationship import BaseRelationship

from ..domain.relationships import MedicalClaimRelationship
from ..domain.vocab import (
    PREDICATE_TREATS,
    PREDICATE_CAUSES,
    PREDICATE_INCREASES_RISK,
    PREDICATE_PREVENTS,
    PREDICATE_INHIBITS,
    PREDICATE_ASSOCIATED_WITH,
    PREDICATE_INTERACTS_WITH,
    PREDICATE_DIAGNOSED_BY,
    PREDICATE_INDICATES,
)
from .llm_client import LLMClientInterface

# Pattern-based extraction rules
# Format: (predicate, patterns, evidence_type)
PREDICATE_PATTERNS = [
    # Causation
    (PREDICATE_CAUSES, [
        r"\bcaus(e|es|ed|ing)\b.*\b(aids|syndrome|disease|infection)",
        r"\bresponsible for\b",
        r"\bleads? to\b",
        r"\bresults? in\b",
    ], "causal"),
    (PREDICATE_PREVENTS, [
        r"\bprevent(s|ed|ing)?\b",
        r"\bprotect(s|ed|ing)? against\b",
        r"\breduc(e|es|ed|ing) risk\b",
    ], "clinical"),
    (PREDICATE_INHIBITS, [
        r"\binhibit(s|ed|ing)?\b",
        r"\bsuppress(es|ed|ing)?\b",
        r"\bblock(s|ed|ing)?\b",
    ], "molecular"),
    # Clinical
    (PREDICATE_TREATS, [
        r"\btreat(s|ed|ment|ing)?\b",
        r"\btherap(y|eutic|ies)\b",
    ], "clinical"),
    (PREDICATE_DIAGNOSED_BY, [
        r"\bdiagnos(ed|is|tic)?\b.*\bby\b",
        r"\bdetected by\b",
    ], "clinical"),
    # Association
    (PREDICATE_ASSOCIATED_WITH, [
        r"\bassociat(ed|ion)?\b.*\bwith\b",
        r"\blinked to\b",
        r"\bconnected to\b",
    ], "epidemiological"),
    (PREDICATE_INTERACTS_WITH, [
        r"\binteract(s|ed|ion)?\b.*\bwith\b",
        r"\bcombine(s|ed|ing)?\b.*\bwith\b",
    ], "molecular"),
    # Statistical/Evidence
    (PREDICATE_INDICATES, [
        r"\bindicat(es|ed|ing)?\b",
        r"\bsuggest(s|ed|ing)?\b",
        r"\bdemonstrat(es|ed|ing)?\b",
    ], "statistical"),
]


class MedLitRelationshipExtractor(RelationshipExtractorInterface):
    """Extract relationships from journal articles.

    This extractor works with:
    1. Pre-extracted relationships in Paper JSON format (from med-lit-schema)
    2. Pattern-based extraction from text
    3. LLM-based extraction (Ollama, OpenAI)

    Ports logic from med-lit-schema's ingest/claims_pipeline.py.
    """

    def __init__(
        self,
        use_patterns: bool = True,
        use_llm: bool = False,
        llm_client: Optional[LLMClientInterface] = None,
    ):
        """Initialize relationship extractor.

        Args:
            use_patterns: Enable pattern-based extraction
            use_llm: Enable LLM-based extraction
            llm_client: Optional LLM client for LLM extraction
        """
        self.use_patterns = use_patterns
        self.use_llm = use_llm
        self._llm = llm_client

    async def extract(
        self,
        document: BaseDocument,
        entities: Sequence[BaseEntity],
    ) -> list[BaseRelationship]:
        """Extract relationships from a journal article.

        Args:
            document: The journal article document.
            entities: The resolved entities from this document.

        Returns:
            List of BaseRelationship objects representing relationships in the paper.
        """
        relationships: list[BaseRelationship] = []

        # Create entity lookup by ID and name for quick access
        entity_by_id: dict[str, BaseEntity] = {e.entity_id: e for e in entities}
        entity_by_name: dict[str, BaseEntity] = {}
        for e in entities:
            entity_by_name[e.name.lower()] = e
            # Also index synonyms
            for synonym in e.synonyms:
                entity_by_name[synonym.lower()] = e

        # First, check for pre-extracted relationships in metadata
        relationships_data = document.metadata.get("relationships", [])
        if relationships_data:
            for rel_data in relationships_data:
                if isinstance(rel_data, dict):
                    rel = self._parse_pre_extracted_relationship(
                        rel_data, document, entity_by_id
                    )
                    if rel:
                        relationships.append(rel)

        # If no pre-extracted relationships, try extraction from text
        if not relationships_data and (self.use_patterns or self.use_llm):
            # Get document text
            sections = document.get_sections()
            text_chunks = []
            for section_name, section_text in sections:
                if section_text:
                    text_chunks.append((section_name, section_text))

            if text_chunks:
                # Pattern-based extraction
                if self.use_patterns:
                    pattern_rels = await self._extract_with_patterns(
                        text_chunks, document, entities, entity_by_name
                    )
                    relationships.extend(pattern_rels)

                # LLM-based extraction
                if self.use_llm and self._llm:
                    llm_rels = await self._extract_with_llm(
                        text_chunks, document, entities, entity_by_name
                    )
                    relationships.extend(llm_rels)

        return relationships

    def _parse_pre_extracted_relationship(
        self,
        rel_data: dict[str, Any],
        document: BaseDocument,
        entity_by_id: dict[str, BaseEntity],
    ) -> Optional[BaseRelationship]:
        """Parse a pre-extracted relationship from metadata."""
        subject_id = rel_data.get("subject_id", "")
        predicate = rel_data.get("predicate", "")
        object_id = rel_data.get("object_id", "")
        confidence = rel_data.get("confidence", 0.5)
        evidence = rel_data.get("evidence", "")
        section = rel_data.get("section", "")

        # Validate that entities exist
        if subject_id not in entity_by_id or object_id not in entity_by_id:
            return None

        # Normalize predicate
        if isinstance(predicate, str):
            predicate = predicate.lower()
        else:
            predicate = str(predicate).lower()

        metadata: dict[str, Any] = {
            "evidence": evidence,
            "section": section,
        }

        if "metadata" in rel_data and isinstance(rel_data["metadata"], dict):
            metadata.update(rel_data["metadata"])

        return MedicalClaimRelationship(
            subject_id=subject_id,
            predicate=predicate,
            object_id=object_id,
            confidence=float(confidence),
            source_documents=(document.document_id,),
            created_at=datetime.now(timezone.utc),
            last_updated=None,
            metadata=metadata,
        )

    async def _extract_with_patterns(
        self,
        text_chunks: list[tuple[str, str]],
        document: BaseDocument,
        entities: Sequence[BaseEntity],
        entity_by_name: dict[str, BaseEntity],
    ) -> list[BaseRelationship]:
        """Extract relationships using pattern matching."""
        relationships: list[BaseRelationship] = []

        for section_name, text in text_chunks:
            # Split into sentences
            sentences = re.split(r"[.!?]+", text)

            for sentence in sentences:
                sentence = sentence.strip()
                if not sentence or len(sentence) < 20:
                    continue

                # Try each predicate pattern
                for predicate, patterns, evidence_type in PREDICATE_PATTERNS:
                    for pattern in patterns:
                        if re.search(pattern, sentence, re.IGNORECASE):
                            # Found a match - try to find entities in the sentence
                            subject_entity, object_entity = self._find_entities_in_sentence(
                                sentence, entities, entity_by_name
                            )

                            if subject_entity and object_entity:
                                # Base confidence on section type
                                confidence = 0.7
                                if section_name in ["abstract", "results"]:
                                    confidence += 0.1
                                elif section_name == "methods":
                                    confidence -= 0.1
                                confidence = max(0.0, min(1.0, confidence))

                                rel = MedicalClaimRelationship(
                                    subject_id=subject_entity.entity_id,
                                    predicate=predicate,
                                    object_id=object_entity.entity_id,
                                    confidence=confidence,
                                    source_documents=(document.document_id,),
                                    created_at=datetime.now(timezone.utc),
                                    last_updated=None,
                                    metadata={
                                        "evidence": sentence,
                                        "section": section_name,
                                        "extraction_method": "pattern_match",
                                        "evidence_type": evidence_type,
                                    },
                                )
                                relationships.append(rel)
                                break  # Only one predicate per sentence

        return relationships

    def _find_entities_in_sentence(
        self,
        sentence: str,
        entities: Sequence[BaseEntity],
        entity_by_name: dict[str, BaseEntity],
    ) -> tuple[Optional[BaseEntity], Optional[BaseEntity]]:
        """Find two entities mentioned in a sentence."""
        sentence_lower = sentence.lower()
        found_entities: list[BaseEntity] = []

        # Look for entity names in the sentence
        for entity in entities:
            if entity.name.lower() in sentence_lower:
                found_entities.append(entity)
            # Also check synonyms
            for synonym in entity.synonyms:
                if synonym.lower() in sentence_lower:
                    found_entities.append(entity)
                    break

        # Return first two entities found
        if len(found_entities) >= 2:
            return found_entities[0], found_entities[1]
        elif len(found_entities) == 1:
            return found_entities[0], None
        else:
            return None, None

    async def _extract_with_llm(
        self,
        text_chunks: list[tuple[str, str]],
        document: BaseDocument,
        entities: Sequence[BaseEntity],
        entity_by_name: dict[str, BaseEntity],
    ) -> list[BaseRelationship]:
        """Extract relationships using LLM."""
        if not self._llm:
            return []

        # Build entity context for LLM
        entity_list = "\n".join(
            f"- {e.name} ({e.get_entity_type()}): {e.entity_id}"
            for e in entities[:50]  # Limit to avoid huge prompts
        )

        # Combine text chunks
        full_text = "\n\n".join(f"{name}: {text}" for name, text in text_chunks)
        text_sample = full_text[:4000]  # Limit text size

        prompt = f"""Extract medical relationships from the following text.

Entities mentioned in the document:
{entity_list}

Text:
{text_sample}

Extract relationships in JSON format:
[
  {{"subject": "entity_name", "predicate": "treats", "object": "entity_name", "confidence": 0.9, "evidence": "sentence text"}},
  ...
]

Valid predicates: treats, causes, increases_risk, prevents, inhibits, associated_with, interacts_with, diagnosed_by, indicates

Return ONLY the JSON array, no explanation."""

        try:
            response = await self._llm.generate_json(prompt)
            relationships: list[BaseRelationship] = []

            if isinstance(response, list):
                for item in response:
                    if isinstance(item, dict):
                        subject_name = item.get("subject", "").strip()
                        predicate = item.get("predicate", "").lower()
                        object_name = item.get("object", "").strip()
                        confidence = float(item.get("confidence", 0.5))
                        evidence = item.get("evidence", "")

                        # Find entities by name
                        subject_entity = entity_by_name.get(subject_name.lower())
                        object_entity = entity_by_name.get(object_name.lower())

                        if subject_entity and object_entity:
                            rel = MedicalClaimRelationship(
                                subject_id=subject_entity.entity_id,
                                predicate=predicate,
                                object_id=object_entity.entity_id,
                                confidence=confidence,
                                source_documents=(document.document_id,),
                                created_at=datetime.now(timezone.utc),
                                last_updated=None,
                                metadata={
                                    "evidence": evidence,
                                    "extraction_method": "llm",
                                },
                            )
                            relationships.append(rel)

            return relationships

        except Exception as e:
            print(f"Warning: LLM relationship extraction failed: {e}")
            return []

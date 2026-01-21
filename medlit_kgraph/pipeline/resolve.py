"""Entity resolution for medical literature domain.

Resolves entity mentions to canonical entities using UMLS, HGNC, RxNorm, UniProt IDs.
"""

from datetime import datetime, timezone
from typing import Any
import uuid

from pydantic import BaseModel, ConfigDict

from kgraph.domain import DomainSchema
from kgraph.entity import BaseEntity, EntityMention, EntityStatus
from kgraph.pipeline.interfaces import EntityResolverInterface
from kgraph.storage.interfaces import EntityStorageInterface


class MedLitEntityResolver(BaseModel, EntityResolverInterface):
    """Resolve medical entity mentions to canonical or provisional entities.

    Resolution strategy:
    1. If mention has canonical_id_hint (from pre-extracted entities), use that
    2. Check if entity with that ID already exists in storage
    3. If not, create new canonical entity (since we have authoritative IDs)
    4. For mentions without canonical IDs, create provisional entities
    """

    model_config = ConfigDict(frozen=True, arbitrary_types_allowed=True)

    domain: DomainSchema

    async def resolve(
        self,
        mention: EntityMention,
        existing_storage: EntityStorageInterface,
    ) -> tuple[BaseEntity, float]:
        """Resolve a single entity mention to an entity.

        Args:
            mention: The extracted entity mention to resolve.
            existing_storage: Storage interface to query for existing entities.

        Returns:
            Tuple of (resolved_entity, confidence_score).
        """
        entity_type = mention.entity_type
        entity_cls = self.domain.entity_types.get(entity_type)

        if entity_cls is None:
            raise ValueError(f"Unknown entity_type {entity_type!r}")

        # Check for canonical ID hint (from pre-extracted entities)
        canonical_id = mention.metadata.get("canonical_id_hint") if mention.metadata else None

        if canonical_id:
            # Try to find existing entity with this ID
            existing = await existing_storage.get(canonical_id)
            if existing:
                # Entity already exists - return it with high confidence
                return existing, mention.confidence

            # Create new canonical entity with the authoritative ID
            # Extract canonical_ids dict from the ID format
            canonical_ids = self._parse_canonical_id(canonical_id, entity_type)

            entity = entity_cls(
                entity_id=canonical_id,
                status=EntityStatus.CANONICAL,
                name=mention.text,
                synonyms=tuple(),
                embedding=None,  # Will be generated later
                canonical_ids=canonical_ids,
                confidence=mention.confidence,
                usage_count=1,
                created_at=datetime.now(timezone.utc),
                source=mention.metadata.get("document_id", "medlit:extracted") if mention.metadata else "medlit:extracted",
                metadata={},
            )
            return entity, mention.confidence

        # No canonical ID - create provisional entity
        entity = entity_cls(
            entity_id=f"prov:{uuid.uuid4().hex}",
            status=EntityStatus.PROVISIONAL,
            name=mention.text,
            synonyms=tuple(),
            embedding=None,
            canonical_ids={},
            confidence=mention.confidence * 0.5,  # Lower confidence for provisional
            usage_count=1,
            created_at=datetime.now(timezone.utc),
            source=mention.metadata.get("document_id", "unknown") if mention.metadata else "unknown",
            metadata={},
        )

        return entity, entity.confidence

    async def resolve_batch(
        self,
        mentions: list[EntityMention],
        existing_storage: EntityStorageInterface,
    ) -> list[tuple[BaseEntity, float]]:
        """Resolve multiple entity mentions efficiently.

        Args:
            mentions: Sequence of entity mentions to resolve.
            existing_storage: Storage interface to query for existing entities.

        Returns:
            List of (entity, confidence) tuples in the same order as input.
        """
        # Simple sequential resolution for now
        # TODO: Could batch lookups for better performance
        return [await self.resolve(m, existing_storage) for m in mentions]

    def _parse_canonical_id(self, entity_id: str, entity_type: str) -> dict[str, str]:
        """Parse canonical ID into canonical_ids dict.

        Examples:
            "C0006142" (UMLS) -> {"umls": "C0006142"}
            "HGNC:1100" -> {"hgnc": "HGNC:1100"}
            "RxNorm:1187832" -> {"rxnorm": "RxNorm:1187832"}
            "P38398" (UniProt) -> {"uniprot": "P38398"}
        """
        canonical_ids: dict[str, str] = {}

        # Check for prefix format (HGNC:1100, RxNorm:1187832)
        if ":" in entity_id:
            prefix, value = entity_id.split(":", 1)
            prefix_lower = prefix.lower()
            canonical_ids[prefix_lower] = entity_id
        else:
            # No prefix - infer from entity type
            if entity_type == "disease":
                # Assume UMLS format (C followed by digits)
                if entity_id.startswith("C") and entity_id[1:].isdigit():
                    canonical_ids["umls"] = entity_id
            elif entity_type == "gene":
                # Assume HGNC format (but should have prefix)
                canonical_ids["hgnc"] = entity_id
            elif entity_type == "drug":
                # Assume RxNorm format (but should have prefix)
                canonical_ids["rxnorm"] = entity_id
            elif entity_type == "protein":
                # Assume UniProt format (P followed by alphanumeric)
                if entity_id.startswith("P") or entity_id.startswith("Q"):
                    canonical_ids["uniprot"] = entity_id

        return canonical_ids

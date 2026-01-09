#!/usr/bin/env python3
"""
Stage 4: Claims Extraction Pipeline (Refactored)

This pipeline extracts semantic relationships (claims) from paragraphs.
Uses new schema relationship models and storage interfaces.

Usage:
    python claims_pipeline_refactored.py --output-dir output --storage sqlite
"""

import argparse
import re
from pathlib import Path
from typing import Optional

from sentence_transformers import SentenceTransformer
import numpy as np

# Import new schema
try:
    from ..base import PredicateType
    from ..relationship import BaseRelationship, create_relationship, Causes, Treats, AssociatedWith, InteractsWith
    from ..entity import EvidenceItem
    from .storage_interfaces import PipelineStorageInterface
    from .sqlite_storage import SQLitePipelineStorage
    from .postgres_storage import PostgresPipelineStorage
except ImportError:
    # Absolute imports for standalone execution
    from med_lit_schema.base import PredicateType
    from med_lit_schema.relationship import BaseRelationship, create_relationship, Causes, Treats, AssociatedWith, InteractsWith
    from med_lit_schema.entity import EvidenceItem
    from med_lit_schema.pipeline.storage_interfaces import PipelineStorageInterface
    from med_lit_schema.pipeline.sqlite_storage import SQLitePipelineStorage
    from med_lit_schema.pipeline.postgres_storage import PostgresPipelineStorage


# ============================================================================
# Configuration
# ============================================================================

DEFAULT_MODEL = "sentence-transformers/all-mpnet-base-v2"
EMBEDDING_DIM = 768


# ============================================================================
# Predicate Pattern Mapping
# ============================================================================

# Map old string predicates to PredicateType enum
PREDICATE_MAP = {
    "CAUSES": PredicateType.CAUSES,
    "PREVENTS": PredicateType.PREVENTS,
    "INHIBITS": PredicateType.INHIBITS,
    "TREATS": PredicateType.TREATS,
    "ASSOCIATED_WITH": PredicateType.ASSOCIATED_WITH,
    "INTERACTS_WITH": PredicateType.INTERACTS_WITH,
    "INDICATES": PredicateType.INDICATES,
    "DIAGNOSED_BY": PredicateType.DIAGNOSED_BY,
    # Add more mappings as needed
}

# Pattern-based extraction rules
# Format: (predicate_string, patterns, evidence_type)
PREDICATE_PATTERNS = [
    # Causation
    ("CAUSES", [r"\bcaus(e|es|ed|ing)\b.*\b(aids|syndrome|disease|infection)", r"\bresponsible for\b", r"\bleads? to\b", r"\bresults? in\b"], "causal"),
    ("PREVENTS", [r"\bprevent(s|ed|ing)?\b", r"\bprotect(s|ed|ing)? against\b", r"\breduc(e|es|ed|ing) risk\b"], "clinical"),
    ("INHIBITS", [r"\binhibit(s|ed|ing)?\b", r"\bsuppress(es|ed|ing)?\b", r"\bblock(s|ed|ing)?\b"], "molecular"),
    # Clinical
    ("TREATS", [r"\btreat(s|ed|ment|ing)?\b", r"\btherap(y|eutic|ies)\b"], "clinical"),
    ("DIAGNOSED_BY", [r"\bdiagnos(ed|is|tic)?\b.*\bby\b", r"\bdetected by\b"], "clinical"),
    # Association
    ("ASSOCIATED_WITH", [r"\bassociat(ed|ion)?\b.*\bwith\b", r"\blinked to\b", r"\bconnected to\b"], "epidemiological"),
    ("INTERACTS_WITH", [r"\binteract(s|ed|ion)?\b.*\bwith\b", r"\bcombine(s|ed|ing)?\b.*\bwith\b"], "molecular"),
    # Statistical/Evidence
    ("INDICATES", [r"\bindicat(es|ed|ing)?\b", r"\bsuggest(s|ed|ing)?\b", r"\bdemonstrat(es|ed|ing)?\b"], "statistical"),
]


def extract_relationships_from_text(
    text: str,
    paper_id: str,
    section_type: str,
    paragraph_id: Optional[str] = None,
) -> list[BaseRelationship]:
    """
    Extract relationships from text using pattern matching.

    Args:
        text: Text to extract from
        paper_id: Paper ID where text was found
        section_type: Section type (abstract, results, etc.)
        paragraph_id: Optional paragraph ID

    Returns:
        List of extracted relationships
    """
    relationships = []

    # Split into sentences
    sentences = re.split(r"[.!?]+", text)

    for sentence in sentences:
        sentence = sentence.strip()
        if not sentence or len(sentence) < 20:
            continue

        # Try each predicate pattern
        for predicate_str, patterns, evidence_type in PREDICATE_PATTERNS:
            for pattern in patterns:
                if re.search(pattern, sentence, re.IGNORECASE):
                    # Found a match - but we need entity IDs
                    # For now, create a placeholder relationship
                    # TODO: Link to actual entities via entity resolution

                    # Map predicate string to enum
                    predicate = PREDICATE_MAP.get(predicate_str)
                    if not predicate:
                        continue

                    # Base confidence on section type and pattern match
                    confidence = 0.7
                    if section_type in ["results", "abstract"]:
                        confidence += 0.1
                    if section_type == "methods":
                        confidence -= 0.1
                    confidence = max(0.0, min(1.0, confidence))

                    # Create relationship using create_relationship helper
                    # Note: We need subject_id and object_id - these would come from entity resolution
                    # For now, we'll create relationships with placeholder IDs
                    # In a full implementation, you'd extract entity mentions and resolve them

                    # Create evidence item
                    evidence = EvidenceItem(
                        paper_id=paper_id,
                        confidence=confidence,
                        section_type=section_type,
                        paragraph_idx=None,  # Would need paragraph index
                        text_span=sentence,
                        extraction_method="pattern_match",
                        study_type="observational" if evidence_type != "rct" else "rct",
                    )

                    # Create relationship with evidence
                    # Note: This is simplified - full implementation would:
                    # 1. Extract entity mentions from sentence
                    # 2. Resolve to canonical entity IDs
                    # 3. Create relationship with proper subject/object IDs
                    relationship = create_relationship(
                        predicate=predicate,
                        subject_id="PLACEHOLDER_SUBJECT",  # TODO: Replace with actual entity ID
                        object_id="PLACEHOLDER_OBJECT",  # TODO: Replace with actual entity ID
                        confidence=confidence,
                        source_papers=[paper_id],
                        evidence=[evidence],
                    )

                    relationships.append(relationship)

                    # Only match one predicate per sentence
                    break

            # If we found a match, don't try other predicates
            if relationships and relationships[-1].evidence and relationships[-1].evidence[0].text_span == sentence:
                break

    return relationships


def main():
    """Main pipeline execution."""
    parser = argparse.ArgumentParser(description="Stage 4: Claims Extraction Pipeline")
    parser.add_argument("--output-dir", type=str, default="output", help="Output directory")
    parser.add_argument(
        "--storage",
        type=str,
        choices=["sqlite", "postgres"],
        default="sqlite",
        help="Storage backend to use"
    )
    parser.add_argument(
        "--database-url",
        type=str,
        default=None,
        help="Database URL for PostgreSQL (required if --storage=postgres)"
    )
    parser.add_argument(
        "--provenance-db",
        type=str,
        default=None,
        help="Path to provenance.db (for reading paragraphs)"
    )

    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    output_dir.mkdir(exist_ok=True)

    # Initialize storage
    if args.storage == "sqlite":
        db_path = output_dir / "pipeline.db"
        storage: PipelineStorageInterface = SQLitePipelineStorage(db_path)
    elif args.storage == "postgres":
        if not args.database_url:
            print("Error: --database-url required for PostgreSQL storage")
            return 1
        storage = PostgresPipelineStorage(args.database_url)
    else:
        print(f"Error: Unknown storage backend: {args.storage}")
        return 1

    # TODO: Read paragraphs from provenance database or storage
    # For now, this is a placeholder that shows the structure

    print("=" * 60)
    print("Claims Extraction Pipeline")
    print("=" * 60)
    print("\nNote: This is a refactored version that uses new schema.")
    print("Full implementation would:")
    print("  1. Read paragraphs from provenance storage")
    print("  2. Extract entity mentions and resolve to canonical IDs")
    print("  3. Extract relationships using patterns or LLM")
    print("  4. Store relationships using storage interface")
    print("\nStorage initialized:", args.storage)
    print(f"Relationship count: {storage.relationships.relationship_count}")

    # Clean up
    storage.close()

    return 0


if __name__ == "__main__":
    exit(main())

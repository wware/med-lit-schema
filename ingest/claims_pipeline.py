#!/usr/bin/env python3
"""
Stage 4: Claims Extraction Ingest

This ingest extracts semantic relationships (claims) from paragraphs.
Uses new schema relationship models and storage interfaces.

Usage:
    python claims_pipeline.py --output-dir output --storage sqlite
    python claims_pipeline.py --output-dir output --storage postgres --database-url postgresql://...
"""

import argparse
import re
import sqlite3
from pathlib import Path

# Import new schema
try:
    from ..base import PredicateType
    from ..relationship import BaseRelationship, create_relationship
    from ..entity import EvidenceItem
    from ..storage.interfaces import PipelineStorageInterface
    from ..storage.backends.sqlite import SQLitePipelineStorage
    from ..storage.backends.postgres import PostgresPipelineStorage
    from .embedding_interfaces import EmbeddingGeneratorInterface
    from .embedding_generators import SentenceTransformerEmbeddingGenerator
except ImportError:
    # Absolute imports for standalone execution
    from med_lit_schema.base import PredicateType
    from med_lit_schema.relationship import BaseRelationship, create_relationship
    from med_lit_schema.entity import EvidenceItem
    from med_lit_schema.storage.interfaces import PipelineStorageInterface
    from med_lit_schema.storage.backends.sqlite import SQLitePipelineStorage
    from med_lit_schema.storage.backends.postgres import PostgresPipelineStorage
    from med_lit_schema.ingest.embedding_interfaces import EmbeddingGeneratorInterface
    from med_lit_schema.ingest.embedding_generators import SentenceTransformerEmbeddingGenerator


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


# ============================================================================
# Helper Functions
# ============================================================================


def get_paragraphs_from_provenance_db(provenance_db_path: Path) -> list[tuple[str, str, str, str, str]]:
    """
    Retrieve paragraphs with their section and paper information from provenance.db.

    Note: This reads from the old SQLite format. In the future, this should
    read from provenance storage interface when paragraph storage is added.

    Args:
        provenance_db_path: Path to provenance.db

    Returns:
        List of (paragraph_id, section_id, paper_id, text, section_type) tuples
    """
    conn = sqlite3.connect(provenance_db_path)
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT p.paragraph_id, p.section_id, s.paper_id, p.text, s.section_type
        FROM paragraphs p
        JOIN sections s ON p.section_id = s.section_id
        ORDER BY s.paper_id, p.paragraph_id
    """
    )

    result = cursor.fetchall()
    conn.close()
    return result


def extract_relationships_from_paragraph(
    paragraph_id: str,
    section_id: str,
    paper_id: str,
    text: str,
    section_type: str,
    storage: PipelineStorageInterface,
) -> list[BaseRelationship]:
    """
    Extract relationships from a paragraph using pattern matching.

    Args:
        paragraph_id: Paragraph ID
        section_id: Section ID
        paper_id: Paper ID
        text: Paragraph text
        section_type: Section type (abstract, results, etc.)
        storage: Storage interface for entity lookups

    Returns:
        List of extracted relationships
    """
    relationships = []
    claim_counter = 0

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
                    # Found a match
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

                    # TODO: Extract entity mentions and resolve to canonical IDs
                    # For now, we create relationships with placeholder IDs
                    # Full implementation would:
                    # 1. Extract entity mentions from the sentence (using NER or pattern matching)
                    # 2. Match mentions to entities in storage (by name/synonym)
                    # 3. Resolve to canonical entity IDs
                    # 4. Create relationship with proper subject_id and object_id

                    # The old version stored claims with None entity IDs, but the new schema
                    # requires subject_id and object_id to be strings. We use placeholder IDs
                    # that can be resolved later when entity resolution is implemented.

                    # Create evidence item
                    evidence = EvidenceItem(
                        paper_id=paper_id,
                        confidence=confidence,
                        section_type=section_type,
                        paragraph_idx=None,
                        text_span=sentence,
                        extraction_method="pattern_match",
                        study_type="observational" if evidence_type != "rct" else "rct",
                    )

                    # Create relationship with placeholder IDs
                    # These will need to be resolved to actual canonical entity IDs
                    claim_id = f"{paragraph_id}_claim_{claim_counter}"
                    subject_id = f"PLACEHOLDER_SUBJECT_{claim_id}"
                    object_id = f"PLACEHOLDER_OBJECT_{claim_id}"

                    relationship = create_relationship(
                        predicate=predicate,
                        subject_id=subject_id,
                        object_id=object_id,
                        confidence=confidence,
                        source_papers=[paper_id],
                        evidence=[evidence],
                    )

                    relationships.append(relationship)
                    claim_counter += 1

                    # Only match one predicate per sentence
                    break

            # If we found a match, don't try other predicates
            if relationships and relationships[-1].evidence and relationships[-1].evidence[0].text_span == sentence:
                break

    return relationships


def main():
    """Main ingest execution."""
    parser = argparse.ArgumentParser(description="Stage 4: Claims Extraction Pipeline")
    parser.add_argument("--output-dir", type=str, default="output", help="Output directory")
    parser.add_argument("--storage", type=str, choices=["sqlite", "postgres"], default="sqlite", help="Storage backend to use")
    parser.add_argument("--database-url", type=str, default=None, help="Database URL for PostgreSQL (required if --storage=postgres)")
    parser.add_argument("--provenance-db", type=str, default=None, help="Path to provenance.db (defaults to output-dir/provenance.db)")
    parser.add_argument("--skip-embeddings", action="store_true", help="Skip embedding generation")
    parser.add_argument("--embedding-model", type=str, default=DEFAULT_MODEL, help="Embedding model to use (default: sentence-transformers/all-mpnet-base-v2)")
    parser.add_argument("--embedding-batch-size", type=int, default=32, help="Batch size for embedding generation")

    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    output_dir.mkdir(exist_ok=True)

    # Determine provenance DB path
    if args.provenance_db:
        provenance_db_path = Path(args.provenance_db)
    else:
        provenance_db_path = output_dir / "provenance.db"

    if not provenance_db_path.exists():
        print(f"Error: provenance.db not found at {provenance_db_path}")
        print("Please run Stage 2 (provenance extraction) first")
        return 1

    # Initialize storage
    if args.storage == "sqlite":
        db_path = output_dir / "ingest.db"
        storage: PipelineStorageInterface = SQLitePipelineStorage(db_path)
    elif args.storage == "postgres":
        if not args.database_url:
            print("Error: --database-url required for PostgreSQL storage")
            return 1
        storage = PostgresPipelineStorage(args.database_url)
    else:
        print(f"Error: Unknown storage backend: {args.storage}")
        return 1

    print("=" * 60)
    print("Stage 4: Claims Extraction Pipeline")
    print("=" * 60)
    print()

    # Get paragraphs from provenance database
    print(f"Loading paragraphs from {provenance_db_path}...")
    paragraphs = get_paragraphs_from_provenance_db(provenance_db_path)
    print(f"Found {len(paragraphs)} paragraphs")
    print()

    # Extract relationships
    print("Extracting relationships...")
    print("-" * 60)

    total_relationships = 0
    for para_id, sec_id, paper_id, text, sec_type in paragraphs:
        relationships = extract_relationships_from_paragraph(para_id, sec_id, paper_id, text, sec_type, storage)

        for relationship in relationships:
            storage.relationships.add_relationship(relationship)
            total_relationships += 1

        if relationships:
            print(f"{paper_id}: Found {len(relationships)} relationships in {para_id}")

    print()
    print(f"Extracted {total_relationships} relationships")
    print()

    # Generate embeddings if requested
    if not args.skip_embeddings and total_relationships > 0:
        print("Generating relationship embeddings...")
        print("-" * 60)

        # Initialize embedding generator
        embedding_generator: EmbeddingGeneratorInterface = SentenceTransformerEmbeddingGenerator(model_name=args.embedding_model)
        print(f"Using embedding model: {embedding_generator.model_name}")
        print(f"Embedding dimension: {embedding_generator.embedding_dim}")
        print()

        # Get all relationships to embed
        all_relationships = storage.relationships.find_relationships(limit=None)
        print(f"Found {len(all_relationships)} relationships to embed")

        # Extract text spans from relationships for embedding
        texts_to_embed = []
        relationship_triples = []
        for rel in all_relationships:
            # Use evidence text span if available, otherwise construct from relationship
            if rel.evidence and rel.evidence[0].text_span:
                text = rel.evidence[0].text_span
            else:
                # Fallback: construct text from relationship components
                text = f"{rel.subject_id} {rel.predicate.value} {rel.object_id}"

            texts_to_embed.append(text)
            relationship_triples.append((rel.subject_id, rel.predicate.value, rel.object_id))

        if texts_to_embed:
            # Generate embeddings in batches
            print(f"Generating embeddings (batch size: {args.embedding_batch_size})...")
            embeddings = embedding_generator.generate_embeddings_batch(texts_to_embed, batch_size=args.embedding_batch_size)

            # Store embeddings
            print("Storing embeddings...")
            stored_count = 0
            for (subject_id, predicate, object_id), embedding in zip(relationship_triples, embeddings):
                storage.relationship_embeddings.store_relationship_embedding(
                    subject_id=subject_id,
                    predicate=predicate,
                    object_id=object_id,
                    embedding=embedding,
                    model_name=embedding_generator.model_name,
                )
                stored_count += 1

            print(f"Stored {stored_count} relationship embeddings")
            print()

    # Clean up
    storage.close()

    # Print summary
    print("=" * 60)
    print("Claims extraction complete!")
    print(f"Total relationships: {total_relationships}")
    print(f"Storage: {args.storage}")
    print("=" * 60)

    if total_relationships > 0:
        print("\nNote: Relationships created with placeholder entity IDs.")
        print("Entity resolution is needed to replace placeholder IDs with canonical entity IDs.")
        print("Run entity resolution ingest to complete the relationships.")

    return 0


if __name__ == "__main__":
    exit(main())

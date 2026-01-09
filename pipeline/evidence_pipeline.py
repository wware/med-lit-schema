#!/usr/bin/env python3
"""
Stage 5: Evidence Aggregation Pipeline

This pipeline extracts quantitative evidence supporting/refuting relationships.
Uses new schema EvidenceItem model and storage interfaces.

Usage:
    python evidence_pipeline.py --output-dir output --storage sqlite
    python evidence_pipeline.py --output-dir output --storage postgres --database-url postgresql://...
"""

import argparse
import re
import sqlite3
from pathlib import Path
from typing import Optional

# Import new schema
try:
    from ..entity import EvidenceItem
    from .storage_interfaces import PipelineStorageInterface
    from .sqlite_storage import SQLitePipelineStorage
    from .postgres_storage import PostgresPipelineStorage
except ImportError:
    # Absolute imports for standalone execution
    from med_lit_schema.entity import EvidenceItem
    from med_lit_schema.pipeline.storage_interfaces import PipelineStorageInterface
    from med_lit_schema.pipeline.sqlite_storage import SQLitePipelineStorage
    from med_lit_schema.pipeline.postgres_storage import PostgresPipelineStorage


# ============================================================================
# Evidence Extraction Functions
# ============================================================================

def extract_sample_size(text: str) -> Optional[int]:
    """Extract sample size from text."""
    match = re.search(r"\bn\s*=\s*(\d+)", text, re.IGNORECASE)
    if match:
        return int(match.group(1))

    match = re.search(r"\b(\d+)\s+(samples|patients|subjects|nodes|lymph nodes|individuals|cases)", text, re.IGNORECASE)
    if match:
        return int(match.group(1))

    return None


def extract_percentage(text: str) -> Optional[float]:
    """Extract percentage/rate from text."""
    match = re.search(r"(\d+(?:\.\d+)?)\s*%", text)
    if match:
        return float(match.group(1)) / 100.0

    match = re.search(r"(\d+)\s*(?:/|of)\s*(\d+)", text)
    if match:
        numerator = int(match.group(1))
        denominator = int(match.group(2))
        if denominator > 0:
            return numerator / denominator

    return None


def extract_p_value(text: str) -> Optional[float]:
    """Extract p-value from text."""
    match = re.search(r"\bp\s*[<>=]\s*(0?\.\d+|[01](?:\.\d+)?)", text, re.IGNORECASE)
    if match:
        return float(match.group(1))

    match = re.search(r"p\s*-\s*value\s*[<>=]\s*(0?\.\d+|[01](?:\.\d+)?)", text, re.IGNORECASE)
    if match:
        return float(match.group(1))

    return None


def infer_evidence_strength(sample_size: Optional[int], p_value: Optional[float]) -> float:
    """Infer evidence strength from metrics."""
    confidence = 0.5  # Base confidence

    if sample_size:
        if sample_size >= 1000:
            confidence += 0.2
        elif sample_size >= 100:
            confidence += 0.1
        elif sample_size < 10:
            confidence -= 0.1

    if p_value:
        if p_value < 0.001:
            confidence += 0.2
        elif p_value < 0.01:
            confidence += 0.1
        elif p_value >= 0.05:
            confidence -= 0.1

    return max(0.0, min(1.0, confidence))


def get_relationships_from_storage(storage: PipelineStorageInterface) -> list:
    """
    Get all relationships from storage.

    Note: This is a simplified approach. In the future, we could add
    methods to get relationships by paper_id or other criteria.

    Returns:
        List of relationships
    """
    # Get all relationships (with a reasonable limit)
    relationships = storage.relationships.find_relationships(limit=10000)
    return relationships


def get_paragraph_text_from_provenance_db(provenance_db_path: Path, paragraph_id: str) -> Optional[str]:
    """
    Get paragraph text from provenance database.

    Note: This reads from the old SQLite format. In the future, this should
    read from provenance storage interface when paragraph storage is added.

    Args:
        provenance_db_path: Path to provenance.db
        paragraph_id: Paragraph ID

    Returns:
        Paragraph text or None if not found
    """
    conn = sqlite3.connect(provenance_db_path)
    cursor = conn.cursor()

    cursor.execute("SELECT text FROM paragraphs WHERE paragraph_id = ?", (paragraph_id,))
    row = cursor.fetchone()
    conn.close()

    return row[0] if row else None


def extract_evidence_for_relationship(
    relationship,
    paragraph_text: str,
    paper_id: str,
    section_type: Optional[str] = None,
) -> Optional[EvidenceItem]:
    """
    Extract evidence metrics for a relationship from paragraph text.

    Args:
        relationship: BaseRelationship object
        paragraph_text: Text of the paragraph
        paper_id: Paper ID
        section_type: Section type (optional)

    Returns:
        EvidenceItem if evidence found, None otherwise
    """
    # Extract quantitative metrics
    sample_size = extract_sample_size(paragraph_text)
    detection_rate = extract_percentage(paragraph_text)
    p_value = extract_p_value(paragraph_text)

    # If no quantitative evidence found, skip
    if not any([sample_size, detection_rate, p_value]):
        return None

    # Infer evidence strength
    confidence = infer_evidence_strength(sample_size, p_value)

    # Create evidence item
    evidence = EvidenceItem(
        paper_id=paper_id,
        confidence=confidence,
        section_type=section_type or "results",
        text_span=paragraph_text[:500],  # Store snippet of paragraph
        extraction_method="pattern_match",
        study_type="observational",
        sample_size=sample_size,
    )

    return evidence


def main():
    """Main pipeline execution."""
    parser = argparse.ArgumentParser(description="Stage 5: Evidence Aggregation Pipeline")
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
        help="Path to provenance.db (defaults to output-dir/provenance.db)"
    )

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

    print("=" * 60)
    print("Stage 5: Evidence Aggregation Pipeline")
    print("=" * 60)
    print()

    # Get relationships from storage
    print("Loading relationships from storage...")
    relationships = get_relationships_from_storage(storage)
    print(f"Found {len(relationships)} relationships")
    print()

    if len(relationships) == 0:
        print("No relationships found. Please run Stage 4 (claims extraction) first.")
        storage.close()
        return 0

    # Extract evidence
    print("Extracting evidence...")
    print("-" * 60)

    total_evidence = 0
    for relationship in relationships:
        # Get paper ID from relationship
        if not relationship.source_papers:
            continue
        paper_id = relationship.source_papers[0]

        # Try to get paragraph text from evidence if available
        paragraph_text = None
        section_type = None

        if relationship.evidence:
            # Use text from existing evidence (from claims extraction)
            evidence_item = relationship.evidence[0]
            paragraph_text = evidence_item.text_span
            section_type = evidence_item.section_type
        else:
            # No existing evidence - skip this relationship
            # (In full implementation, we could extract from provenance DB)
            continue

        if not paragraph_text:
            continue

        # Extract evidence metrics from the paragraph text
        evidence = extract_evidence_for_relationship(
            relationship,
            paragraph_text,
            paper_id,
            section_type
        )

        if evidence:
            # Add evidence to relationship and store
            relationship.evidence.append(evidence)
            storage.relationships.add_relationship(relationship)
            storage.evidence.add_evidence(evidence)
            total_evidence += 1

            print(f"  {relationship.subject_id} {relationship.predicate.value} {relationship.object_id}:")
            if evidence.sample_size:
                print(f"    Sample size: n={evidence.sample_size}")
            if evidence.confidence:
                print(f"    Confidence: {evidence.confidence:.2f}")

    print()
    print(f"Extracted {total_evidence} evidence items")
    print()

    # Clean up
    storage.close()

    # Print summary
    print("=" * 60)
    print("Evidence aggregation complete!")
    print(f"Total evidence items: {total_evidence}")
    print(f"Storage: {args.storage}")
    print("=" * 60)

    return 0


if __name__ == "__main__":
    exit(main())

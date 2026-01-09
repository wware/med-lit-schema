#!/usr/bin/env python3
"""
Stage 5: Evidence Aggregation Pipeline (Refactored)

This pipeline extracts quantitative evidence supporting/refuting relationships.
Uses new schema EvidenceItem model and storage interfaces.

Usage:
    python evidence_pipeline_refactored.py --output-dir output --storage sqlite
"""

import argparse
import re
from pathlib import Path
from typing import Optional

# Import new schema
try:
    from ..entity import EvidenceItem
    from ..base import EvidenceType
    from .storage_interfaces import PipelineStorageInterface
    from .sqlite_storage import SQLitePipelineStorage
    from .postgres_storage import PostgresPipelineStorage
except ImportError:
    # Absolute imports for standalone execution
    from med_lit_schema.entity import EvidenceItem
    from med_lit_schema.base import EvidenceType
    from med_lit_schema.pipeline.storage_interfaces import PipelineStorageInterface
    from med_lit_schema.pipeline.sqlite_storage import SQLitePipelineStorage
    from med_lit_schema.pipeline.postgres_storage import PostgresPipelineStorage


def extract_sample_size(text: str) -> Optional[int]:
    """Extract sample size from text."""
    match = re.search(r"\bn\s*=\s*(\d+)", text, re.IGNORECASE)
    if match:
        return int(match.group(1))

    match = re.search(r"\b(\d+)\s+(samples|patients|subjects|nodes|lymph nodes|individuals|cases)", text, re.IGNORECASE)
    if match:
        return int(match.group(1))

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

    print("=" * 60)
    print("Evidence Aggregation Pipeline")
    print("=" * 60)
    print("\nNote: This is a refactored version that uses new schema.")
    print("Full implementation would:")
    print("  1. Read relationships from storage")
    print("  2. Extract evidence metrics from supporting paragraphs")
    print("  3. Create EvidenceItem objects with metrics")
    print("  4. Store evidence using storage interface")
    print("\nStorage initialized:", args.storage)
    print(f"Evidence count: {storage.evidence.evidence_count}")

    # Clean up
    storage.close()

    return 0


if __name__ == "__main__":
    exit(main())

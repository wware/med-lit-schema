#!/usr/bin/env python3
"""
Stage 5: Evidence Aggregation Pipeline

This pipeline extracts quantitative evidence supporting/refuting claims.

Database: evidence.db (SQLite)
Tables: evidence, evidence_metrics

This enables:
- Link empirical measurements to claims
- Track supporting and refuting evidence
- Aggregate evidence strength across multiple papers
- Identify methodological details for reproducibility

Current Implementation:
- Pattern-based extraction of quantitative metrics (sample sizes, percentages, p-values)
- Links evidence to claims via paragraph matching
- Future: Can be enhanced with LLM-based evidence extraction

Usage:
    python pmc_evidence_pipeline.py --output-dir output
"""

import argparse
import json
import re
import sqlite3
from pathlib import Path
from typing import Optional

from pydantic import BaseModel, Field


# ============================================================================
# Pydantic Models
# ============================================================================


class Evidence(BaseModel):
    """Represents evidence supporting or refuting a claim."""

    evidence_id: str = Field(..., description="Unique evidence identifier")
    claim_id: str = Field(..., description="Claim ID this evidence relates to")
    supports: bool = Field(..., description="True if supports claim, False if refutes")
    strength: str = Field(..., description="Evidence strength: high, medium, low")
    evidence_type: str = Field(..., description="Method type: in_situ_hybridization, PCR, ELISA, etc.")
    paragraph_id: str = Field(..., description="Paragraph containing the evidence")
    details: str = Field(default="{}", description="JSON with method-specific details")


class EvidenceMetrics(BaseModel):
    """Represents quantitative metrics for evidence."""

    evidence_id: str = Field(..., description="Evidence ID")
    sample_size: Optional[int] = Field(None, description="Sample size (n)")
    detection_rate: Optional[float] = Field(None, description="Detection/success rate (0.0-1.0)")
    p_value: Optional[float] = Field(None, description="Statistical p-value")
    confidence_interval: Optional[str] = Field(None, description="Confidence interval string")
    statistical_test: Optional[str] = Field(None, description="Statistical test used")
    other_metrics: str = Field(default="{}", description="JSON with additional metrics")


# ============================================================================
# Evidence Type Patterns
# ============================================================================

# Keywords indicating evidence types
EVIDENCE_TYPE_KEYWORDS = [
    ("in_situ_hybridization", ["in situ hybridization", "ISH", "hybridization"]),
    ("PCR", ["PCR", "polymerase chain reaction", "RT-PCR", "quantitative PCR", "qPCR"]),
    ("ELISA", ["ELISA", "enzyme-linked immunosorbent assay", "immunoassay"]),
    ("Western_blot", ["Western blot", "immunoblot", "immunoblotting"]),
    ("immunofluorescence", ["immunofluorescence", "immunofluorescent", "IF staining"]),
    ("flow_cytometry", ["flow cytometry", "FACS", "fluorescence-activated cell sorting"]),
    ("cohort_study", ["cohort study", "cohort", "longitudinal study", "follow-up study"]),
    ("case_control", ["case-control", "case control study"]),
    ("clinical_trial", ["clinical trial", "randomized trial", "RCT", "controlled trial"]),
    ("serology", ["serolog", "antibody", "seropositivity", "seroprevalence"]),
    ("microscopy", ["microscopy", "microscopic", "electron microscopy", "EM"]),
    ("culture", ["culture", "viral culture", "cell culture", "isolation"]),
]


# ============================================================================
# Database Functions
# ============================================================================


def create_evidence_db(db_path: Path) -> sqlite3.Connection:
    """
    Create evidence database with schema.

    Args:
        db_path: Path to database file

    Returns:
        SQLite connection
    """
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Create evidence table
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS evidence (
            evidence_id TEXT PRIMARY KEY,
            claim_id TEXT,
            supports BOOLEAN,
            strength TEXT CHECK(strength IN ('high', 'medium', 'low')),
            type TEXT,
            paragraph_id TEXT,
            details TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """
    )

    # Create evidence_metrics table
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS evidence_metrics (
            evidence_id TEXT PRIMARY KEY,
            sample_size INTEGER,
            detection_rate REAL,
            p_value REAL,
            confidence_interval TEXT,
            statistical_test TEXT,
            other_metrics TEXT,
            FOREIGN KEY (evidence_id) REFERENCES evidence(evidence_id) ON DELETE CASCADE
        )
    """
    )

    # Create indexes
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_evidence_claim_id ON evidence(claim_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_evidence_paragraph_id ON evidence(paragraph_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_evidence_type ON evidence(type)")

    conn.commit()
    return conn


def get_claims_with_paragraphs(claims_db_path: Path) -> list[tuple[str, str, str, str]]:
    """
    Get claims with their paragraph information.

    Args:
        claims_db_path: Path to claims.db

    Returns:
        List of (claim_id, paragraph_id, extracted_text, predicate) tuples
    """
    conn = sqlite3.connect(claims_db_path)
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT claim_id, paragraph_id, extracted_text, predicate
        FROM claims
        ORDER BY claim_id
    """
    )

    result = cursor.fetchall()
    conn.close()
    return result


def get_paragraph_text(provenance_db_path: Path, paragraph_id: str) -> Optional[str]:
    """
    Get paragraph text by ID.

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


def insert_evidence(conn: sqlite3.Connection, evidence: Evidence) -> None:
    """Insert evidence into database."""
    cursor = conn.cursor()

    cursor.execute(
        """
        INSERT OR REPLACE INTO evidence
        (evidence_id, claim_id, supports, strength, type, paragraph_id, details)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """,
        (
            evidence.evidence_id,
            evidence.claim_id,
            evidence.supports,
            evidence.strength,
            evidence.evidence_type,
            evidence.paragraph_id,
            evidence.details,
        ),
    )

    conn.commit()


def insert_evidence_metrics(conn: sqlite3.Connection, metrics: EvidenceMetrics) -> None:
    """Insert evidence metrics into database."""
    cursor = conn.cursor()

    cursor.execute(
        """
        INSERT OR REPLACE INTO evidence_metrics
        (evidence_id, sample_size, detection_rate, p_value, confidence_interval,
         statistical_test, other_metrics)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """,
        (
            metrics.evidence_id,
            metrics.sample_size,
            metrics.detection_rate,
            metrics.p_value,
            metrics.confidence_interval,
            metrics.statistical_test,
            metrics.other_metrics,
        ),
    )

    conn.commit()


# ============================================================================
# Evidence Extraction
# ============================================================================


def extract_sample_size(text: str) -> Optional[int]:
    """
    Extract sample size from text.

    Looks for patterns like:
    - n=7, n = 14, (n=100)
    - 7 samples, 14 patients, 100 lymph nodes
    """
    # Pattern: n=NUMBER or n = NUMBER
    match = re.search(r"\bn\s*=\s*(\d+)", text, re.IGNORECASE)
    if match:
        return int(match.group(1))

    # Pattern: NUMBER samples/patients/subjects/nodes
    match = re.search(r"\b(\d+)\s+(samples|patients|subjects|nodes|lymph nodes|individuals|cases)", text, re.IGNORECASE)
    if match:
        return int(match.group(1))

    return None


def extract_percentage(text: str) -> Optional[float]:
    """
    Extract percentage/rate from text.

    Looks for patterns like:
    - 85.7%, 6/7 (85.7%), approximately 86%
    - 6 of 7, 6/7
    """
    # Pattern: XX.X% or XX%
    match = re.search(r"(\d+(?:\.\d+)?)\s*%", text)
    if match:
        return float(match.group(1)) / 100.0

    # Pattern: X/Y or X of Y
    match = re.search(r"(\d+)\s*(?:/|of)\s*(\d+)", text)
    if match:
        numerator = int(match.group(1))
        denominator = int(match.group(2))
        if denominator > 0:
            return numerator / denominator

    return None


def extract_p_value(text: str) -> Optional[float]:
    """
    Extract p-value from text.

    Looks for patterns like:
    - p<0.05, p = 0.01, p-value < 0.001
    """
    # Pattern: p < VALUE or p = VALUE
    match = re.search(r"\bp\s*[<>=]\s*(0?\.\d+|[01](?:\.\d+)?)", text, re.IGNORECASE)
    if match:
        return float(match.group(1))

    return None


def infer_evidence_type(text: str) -> str:
    """
    Infer evidence type from text based on keywords.

    Args:
        text: Text to analyze

    Returns:
        Evidence type string
    """
    text_lower = text.lower()

    for evidence_type, keywords in EVIDENCE_TYPE_KEYWORDS:
        for keyword in keywords:
            if keyword.lower() in text_lower:
                return evidence_type

    # Default to "observational" if no specific method found
    return "observational"


def determine_evidence_strength(sample_size: Optional[int], p_value: Optional[float], detection_rate: Optional[float]) -> str:
    """
    Determine evidence strength based on metrics.

    Args:
        sample_size: Sample size (if available)
        p_value: P-value (if available)
        detection_rate: Detection rate (if available)

    Returns:
        Strength: "high", "medium", or "low"
    """
    score = 0

    # Sample size contribution
    if sample_size:
        if sample_size >= 100:
            score += 2
        elif sample_size >= 10:
            score += 1

    # P-value contribution
    if p_value:
        if p_value < 0.01:
            score += 2
        elif p_value < 0.05:
            score += 1

    # Detection rate contribution
    if detection_rate:
        if detection_rate >= 0.8:
            score += 1
        elif detection_rate >= 0.5:
            score += 0.5

    # Convert score to strength
    if score >= 3:
        return "high"
    elif score >= 1.5:
        return "medium"
    else:
        return "low"


def extract_evidence_from_paragraph(
    claim_id: str, paragraph_id: str, paragraph_text: str, claim_predicate: str
) -> tuple[Optional[Evidence], Optional[EvidenceMetrics]]:
    """
    Extract evidence and metrics from a paragraph related to a claim.

    Args:
        claim_id: Claim ID
        paragraph_id: Paragraph ID
        paragraph_text: Paragraph text
        claim_predicate: Claim predicate type

    Returns:
        Tuple of (Evidence, EvidenceMetrics) or (None, None) if no evidence found
    """
    # Extract quantitative metrics
    sample_size = extract_sample_size(paragraph_text)
    detection_rate = extract_percentage(paragraph_text)
    p_value = extract_p_value(paragraph_text)

    # If no quantitative evidence found, skip
    if not any([sample_size, detection_rate, p_value]):
        return None, None

    # Infer evidence type
    evidence_type = infer_evidence_type(paragraph_text)

    # Determine strength
    strength = determine_evidence_strength(sample_size, p_value, detection_rate)

    # Create evidence ID
    evidence_id = f"{claim_id}_evidence"

    # Assume evidence supports the claim (we could enhance this with LLM-based analysis)
    supports = True

    # Create details JSON
    details = {
        "method": evidence_type,
        "paragraph_text_snippet": paragraph_text[:200] + ("..." if len(paragraph_text) > 200 else ""),
    }

    evidence = Evidence(
        evidence_id=evidence_id,
        claim_id=claim_id,
        supports=supports,
        strength=strength,
        evidence_type=evidence_type,
        paragraph_id=paragraph_id,
        details=json.dumps(details),
    )

    # Create metrics
    other_metrics = {}
    if sample_size:
        other_metrics["sample_size_extracted"] = sample_size
    if detection_rate:
        other_metrics["detection_rate_extracted"] = detection_rate

    metrics = EvidenceMetrics(
        evidence_id=evidence_id,
        sample_size=sample_size,
        detection_rate=detection_rate,
        p_value=p_value,
        confidence_interval=None,  # TODO: Extract confidence intervals
        statistical_test=None,  # TODO: Extract test names
        other_metrics=json.dumps(other_metrics),
    )

    return evidence, metrics


# ============================================================================
# Main Pipeline
# ============================================================================


def main():
    """Main pipeline execution."""
    parser = argparse.ArgumentParser(description="Stage 5: Evidence Aggregation Pipeline")
    parser.add_argument("--output-dir", type=str, default="output", help="Output directory containing databases")

    args = parser.parse_args()

    output_dir = Path(args.output_dir)

    if not output_dir.exists():
        print(f"Error: Output directory not found: {output_dir}")
        return 1

    provenance_db_path = output_dir / "provenance.db"
    claims_db_path = output_dir / "claims.db"
    evidence_db_path = output_dir / "evidence.db"

    if not claims_db_path.exists():
        print(f"Error: claims.db not found at {claims_db_path}")
        print("Please run Stage 4 (claims extraction) first")
        return 1

    if not provenance_db_path.exists():
        print(f"Error: provenance.db not found at {provenance_db_path}")
        print("Please run Stage 2 (provenance extraction) first")
        return 1

    print("=" * 60)
    print("Stage 5: Evidence Aggregation Pipeline")
    print("=" * 60)
    print()

    # Create evidence database
    print(f"Creating evidence database: {evidence_db_path}")
    evidence_conn = create_evidence_db(evidence_db_path)

    # Get claims
    print("Loading claims from claims.db...")
    claims = get_claims_with_paragraphs(claims_db_path)
    print(f"Found {len(claims)} claims")
    print()

    # Extract evidence
    print("Extracting evidence...")
    print("-" * 60)

    total_evidence = 0
    for claim_id, paragraph_id, claim_text, predicate in claims:
        # Get paragraph text
        para_text = get_paragraph_text(provenance_db_path, paragraph_id)
        if not para_text:
            continue

        # Extract evidence
        evidence, metrics = extract_evidence_from_paragraph(claim_id, paragraph_id, para_text, predicate)

        if evidence and metrics:
            insert_evidence(evidence_conn, evidence)
            insert_evidence_metrics(evidence_conn, metrics)
            total_evidence += 1

            print(f"  {claim_id}: Found {evidence.evidence_type} evidence (strength: {evidence.strength})")
            if metrics.sample_size:
                print(f"    Sample size: n={metrics.sample_size}")
            if metrics.detection_rate:
                print(f"    Detection rate: {metrics.detection_rate * 100:.1f}%")
            if metrics.p_value:
                print(f"    P-value: {metrics.p_value}")

    print()
    print(f"Extracted {total_evidence} evidence items")
    print()

    evidence_conn.close()

    # Print summary
    print("=" * 60)
    print("Evidence aggregation complete!")
    print(f"Total evidence items: {total_evidence}")
    print(f"Database: {evidence_db_path}")
    print("=" * 60)

    return 0


if __name__ == "__main__":
    exit(main())

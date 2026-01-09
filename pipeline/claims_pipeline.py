#!/usr/bin/env python3
"""
Stage 4: Claims Extraction Pipeline

This pipeline extracts semantic relationships (claims) from paragraphs.

Database: claims.db (SQLite)
Tables: claims, claim_embeddings

This enables:
- Track what specific papers claim about entity relationships
- Identify contradictory claims across the literature
- Trace claims back to specific paragraphs for verification
- Build evidence chains for causal relationships (e.g., HIV→AIDS)

Current Implementation:
- Pattern-based extraction using regex and keyword matching
- Future: Can be enhanced with LLM-based relationship extraction

Usage:
    python pmc_claims_pipeline.py --output-dir output
"""

import argparse
import re
import sqlite3
from pathlib import Path
from typing import Optional
import numpy as np

from pydantic import BaseModel, Field
from sentence_transformers import SentenceTransformer


# ============================================================================
# Configuration
# ============================================================================

DEFAULT_MODEL = "sentence-transformers/all-mpnet-base-v2"
EMBEDDING_DIM = 768


# ============================================================================
# Pydantic Models
# ============================================================================


class Claim(BaseModel):
    """Represents a claim (semantic relationship) extracted from text."""

    claim_id: str = Field(..., description="Unique claim identifier")
    paper_id: str = Field(..., description="PMC ID of source paper")
    section_id: str = Field(..., description="Section ID where claim was found")
    paragraph_id: str = Field(..., description="Paragraph ID where claim was found")
    subject_entity_id: Optional[int] = Field(None, description="Subject entity ID")
    predicate: str = Field(..., description="Relationship type (CAUSES, INFECTS, etc.)")
    object_entity_id: Optional[int] = Field(None, description="Object entity ID")
    extracted_text: str = Field(..., description="Original sentence containing the claim")
    confidence: float = Field(..., description="Extraction confidence (0.0-1.0)")
    evidence_type: str = Field(..., description="Type of evidence: molecular, clinical, epidemiological, statistical")


# ============================================================================
# Predicate Patterns
# ============================================================================

# Pattern-based extraction rules
# Format: (predicate, patterns, evidence_type)
PREDICATE_PATTERNS = [
    # Causation
    ("CAUSES", [r"\bcaus(e|es|ed|ing)\b.*\b(aids|syndrome|disease|infection)", r"\bresponsible for\b", r"\bleads? to\b", r"\bresults? in\b"], "causal"),
    ("PREVENTS", [r"\bprevent(s|ed|ing)?\b", r"\bprotect(s|ed|ing)? against\b", r"\breduc(e|es|ed|ing) risk\b"], "clinical"),
    ("INHIBITS", [r"\binhibit(s|ed|ing)?\b", r"\bsuppress(es|ed|ing)?\b", r"\bblock(s|ed|ing)?\b"], "molecular"),
    # Detection
    ("DETECTED_IN", [r"\bdetect(ed|ion)?\b.*\bin\b", r"\bfound in\b", r"\bidentified in\b", r"\bobserved in\b"], "molecular"),
    ("ISOLATED_FROM", [r"\bisolat(ed|ion)?\b.*\bfrom\b", r"\bpurified from\b", r"\bobtained from\b"], "molecular"),
    # Association
    ("CORRELATES_WITH", [r"\bcorrelat(es|ed|ion)?\b.*\bwith\b", r"\bassociat(ed|ion)?\b.*\bwith\b"], "statistical"),
    ("ASSOCIATED_WITH", [r"\bassociat(ed|ion)?\b.*\bwith\b", r"\blinked to\b", r"\bconnected to\b"], "epidemiological"),
    # Biological
    ("INFECTS", [r"\binfect(s|ed|ion|ing)?\b", r"\binfectious\b", r"\binfectivity\b"], "molecular"),
    ("BINDS_TO", [r"\bbind(s|ing)?\b.*\bto\b", r"\battach(es|ed|ing)?\b.*\bto\b"], "molecular"),
    ("REPLICATES_IN", [r"\breplicat(e|es|ed|ion|ing)\b.*\bin\b", r"\bproliferat(e|es|ed|ing)\b.*\bin\b"], "molecular"),
    # Clinical
    ("TREATS", [r"\btreat(s|ed|ment|ing)?\b", r"\btherap(y|eutic|ies)\b"], "clinical"),
    ("DIAGNOSED_BY", [r"\bdiagnos(ed|is|tic)?\b.*\bby\b", r"\bdetected by\b"], "clinical"),
    ("PROGRESSES_TO", [r"\bprogress(es|ed|ion)?\b.*\bto\b", r"\bdevelop(s|ed|ing)?\b.*\binto\b"], "clinical"),
    # Statistical/Evidence
    ("INDICATES", [r"\bindicat(es|ed|ing)?\b", r"\bsuggest(s|ed|ing)?\b", r"\bdemonstrat(es|ed|ing)?\b"], "statistical"),
]


# ============================================================================
# Database Functions
# ============================================================================


def create_claims_db(db_path: Path) -> sqlite3.Connection:
    """
    Create claims database with schema.

    Args:
        db_path: Path to database file

    Returns:
        SQLite connection
    """
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Create claims table
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS claims (
            claim_id TEXT PRIMARY KEY,
            paper_id TEXT,
            section_id TEXT,
            paragraph_id TEXT,
            subject_entity_id INTEGER,
            predicate TEXT,
            object_entity_id INTEGER,
            extracted_text TEXT,
            confidence REAL,
            evidence_type TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """
    )

    # Create claim embeddings table
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS claim_embeddings (
            claim_id TEXT PRIMARY KEY,
            embedding BLOB,
            model_name TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (claim_id) REFERENCES claims(claim_id) ON DELETE CASCADE
        )
    """
    )

    # Create indexes
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_claims_paper_id ON claims(paper_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_claims_paragraph_id ON claims(paragraph_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_claims_predicate ON claims(predicate)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_claims_entities ON claims(subject_entity_id, object_entity_id)")

    conn.commit()
    return conn


def get_paragraphs_with_sections(provenance_db_path: Path) -> list[tuple[str, str, str, str, str]]:
    """
    Retrieve paragraphs with their section and paper information.

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


def insert_claim(conn: sqlite3.Connection, claim: Claim) -> None:
    """Insert claim into database."""
    cursor = conn.cursor()

    cursor.execute(
        """
        INSERT OR REPLACE INTO claims
        (claim_id, paper_id, section_id, paragraph_id, subject_entity_id,
         predicate, object_entity_id, extracted_text, confidence, evidence_type)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """,
        (
            claim.claim_id,
            claim.paper_id,
            claim.section_id,
            claim.paragraph_id,
            claim.subject_entity_id,
            claim.predicate,
            claim.object_entity_id,
            claim.extracted_text,
            claim.confidence,
            claim.evidence_type,
        ),
    )

    conn.commit()


def insert_claim_embedding(conn: sqlite3.Connection, claim_id: str, embedding: np.ndarray, model_name: str) -> None:
    """Insert claim embedding into database."""
    cursor = conn.cursor()

    embedding_bytes = embedding.astype(np.float32).tobytes()

    cursor.execute(
        """
        INSERT OR REPLACE INTO claim_embeddings
        (claim_id, embedding, model_name)
        VALUES (?, ?, ?)
    """,
        (claim_id, embedding_bytes, model_name),
    )

    conn.commit()


# ============================================================================
# Claims Extraction
# ============================================================================


def extract_claims_from_paragraph(
    paragraph_id: str, section_id: str, paper_id: str, text: str, section_type: str
) -> list[Claim]:
    """
    Extract claims from a paragraph using pattern matching.

    Args:
        paragraph_id: Paragraph ID
        section_id: Section ID
        paper_id: Paper ID
        text: Paragraph text
        section_type: Section type (abstract, results, etc.)

    Returns:
        List of extracted claims
    """
    claims = []
    claim_counter = 0

    # Split into sentences
    sentences = re.split(r"[.!?]+", text)

    for sentence in sentences:
        sentence = sentence.strip()
        if not sentence or len(sentence) < 20:  # Skip very short fragments
            continue

        # Try each predicate pattern
        for predicate, patterns, evidence_type in PREDICATE_PATTERNS:
            for pattern in patterns:
                if re.search(pattern, sentence, re.IGNORECASE):
                    # Found a match - create a claim
                    claim_id = f"{paragraph_id}_claim_{claim_counter}"

                    # Base confidence on section type and pattern match
                    confidence = 0.7  # Base confidence for pattern match
                    if section_type in ["results", "abstract"]:
                        confidence += 0.1
                    if section_type == "methods":
                        confidence -= 0.1

                    # Clamp confidence to [0, 1]
                    confidence = max(0.0, min(1.0, confidence))

                    claim = Claim(
                        claim_id=claim_id,
                        paper_id=paper_id,
                        section_id=section_id,
                        paragraph_id=paragraph_id,
                        subject_entity_id=None,  # TODO: Link to entities via entity resolution
                        predicate=predicate,
                        object_entity_id=None,  # TODO: Link to entities via entity resolution
                        extracted_text=sentence,
                        confidence=confidence,
                        evidence_type=evidence_type,
                    )

                    claims.append(claim)
                    claim_counter += 1

                    # Only match one predicate per sentence
                    break

            # If we found a match, don't try other predicates
            if claims and claims[-1].extracted_text == sentence:
                break

    return claims


def generate_claim_embeddings(claims_db_path: Path, model_name: str = DEFAULT_MODEL, batch_size: int = 32) -> int:
    """
    Generate embeddings for all claims.

    Args:
        claims_db_path: Path to claims.db
        model_name: Name of sentence-transformers model
        batch_size: Batch size for encoding

    Returns:
        Number of embeddings created
    """
    print(f"Loading embedding model: {model_name}")
    model = SentenceTransformer(model_name)

    conn = sqlite3.connect(claims_db_path)
    cursor = conn.cursor()

    # Get all claims
    cursor.execute("SELECT claim_id, extracted_text FROM claims ORDER BY claim_id")
    claims = cursor.fetchall()

    if not claims:
        print("No claims found")
        conn.close()
        return 0

    print(f"Found {len(claims)} claims")

    # Extract texts
    claim_ids = [c[0] for c in claims]
    claim_texts = [c[1] for c in claims]

    print(f"Generating embeddings (batch size: {batch_size})...")
    embeddings = model.encode(claim_texts, batch_size=batch_size, show_progress_bar=True, convert_to_numpy=True)

    print("Storing embeddings in database...")
    for claim_id, embedding in zip(claim_ids, embeddings):
        insert_claim_embedding(conn, claim_id, embedding, model_name)

    conn.close()

    print(f"Created {len(embeddings)} claim embeddings")
    return len(embeddings)


# ============================================================================
# Main Pipeline
# ============================================================================


def main():
    """Main pipeline execution."""
    parser = argparse.ArgumentParser(description="Stage 4: Claims Extraction Pipeline")
    parser.add_argument("--output-dir", type=str, default="output", help="Output directory containing databases")
    parser.add_argument("--model", type=str, default=DEFAULT_MODEL, help="Sentence-transformers model for embeddings")
    parser.add_argument("--batch-size", type=int, default=32, help="Batch size for embedding generation")
    parser.add_argument("--skip-embeddings", action="store_true", help="Skip embedding generation")

    args = parser.parse_args()

    output_dir = Path(args.output_dir)

    if not output_dir.exists():
        print(f"Error: Output directory not found: {output_dir}")
        return 1

    provenance_db_path = output_dir / "provenance.db"
    claims_db_path = output_dir / "claims.db"

    if not provenance_db_path.exists():
        print(f"Error: provenance.db not found at {provenance_db_path}")
        print("Please run Stage 2 (provenance extraction) first")
        return 1

    print("=" * 60)
    print("Stage 4: Claims Extraction Pipeline")
    print("=" * 60)
    print()

    # Create claims database
    print(f"Creating claims database: {claims_db_path}")
    claims_conn = create_claims_db(claims_db_path)

    # Get paragraphs
    print("Loading paragraphs from provenance.db...")
    paragraphs = get_paragraphs_with_sections(provenance_db_path)
    print(f"Found {len(paragraphs)} paragraphs")
    print()

    # Extract claims
    print("Extracting claims...")
    print("-" * 60)

    total_claims = 0
    for para_id, sec_id, paper_id, text, sec_type in paragraphs:
        claims = extract_claims_from_paragraph(para_id, sec_id, paper_id, text, sec_type)

        for claim in claims:
            insert_claim(claims_conn, claim)
            total_claims += 1

        if claims:
            print(f"{paper_id}: Found {len(claims)} claims in {para_id}")

    print()
    print(f"Extracted {total_claims} claims")
    print()

    # Generate claim embeddings
    if not args.skip_embeddings and total_claims > 0:
        print("Generating claim embeddings...")
        print("-" * 60)
        generate_claim_embeddings(claims_db_path, model_name=args.model, batch_size=args.batch_size)
        print()

    claims_conn.close()

    # Print summary
    print("=" * 60)
    print("Claims extraction complete!")
    print(f"Total claims: {total_claims}")
    print(f"Database: {claims_db_path}")
    print("=" * 60)

    # Show sample claims
    if total_claims > 0:
        print("\nSample claims:")
        conn = sqlite3.connect(claims_db_path)
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT predicate, extracted_text, confidence, evidence_type
            FROM claims
            ORDER BY confidence DESC
            LIMIT 5
        """
        )

        for pred, text, conf, ev_type in cursor.fetchall():
            print(f"\n  [{pred}] (confidence: {conf:.2f}, type: {ev_type})")
            print(f"  {text[:100]}...")

        conn.close()

    return 0


if __name__ == "__main__":
    exit(main())

#!/usr/bin/env python3
"""
Stage 6: Graph Database Ingest

This ingest loads data from SQLite databases into PostgreSQL/AGE graph database.

Database: PostgreSQL with Apache AGE extension
Graph: medical_literature_graph

Node Types:
- Paper: Research papers with metadata
- Entity: Biomedical entities (diseases, genes, etc.)
- Paragraph: Text paragraphs from papers
- Claim: Extracted claims (relationships)
- Evidence: Evidence items with strength ratings

Edge Types:
- CONTAINS: Paper -> Paragraph
- MENTIONS: Paragraph -> Entity
- MAKES_CLAIM: Paper -> Claim
- SUPPORTS: Evidence -> Claim
- RELATES_TO: Claim -> Entity (subject/object)

Usage:
    python pmc_graph_pipeline.py --output-dir output
"""

import argparse
import os
import sqlite3
from pathlib import Path
from typing import Optional
import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT

from pydantic import BaseModel, Field


# ============================================================================
# Configuration
# ============================================================================

# Get PostgreSQL connection info from environment
AGE_HOST = os.getenv("AGE_HOST", "localhost")
AGE_PORT = int(os.getenv("AGE_PORT", "5432"))
AGE_DB = os.getenv("AGE_DB", "age")
AGE_USER = os.getenv("AGE_USER", "age")
AGE_PASSWORD = os.getenv("AGE_PASSWORD", "agepassword")
GRAPH_NAME = "medical_literature_graph"


# ============================================================================
# Pydantic Models
# ============================================================================


class GraphStats(BaseModel):
    """Statistics about the graph database."""

    papers: int = Field(0, description="Number of paper nodes")
    entities: int = Field(0, description="Number of entity nodes")
    paragraphs: int = Field(0, description="Number of paragraph nodes")
    claims: int = Field(0, description="Number of claim nodes")
    evidence: int = Field(0, description="Number of evidence nodes")
    edges: int = Field(0, description="Number of edges")


# ============================================================================
# PostgreSQL/AGE Connection
# ============================================================================


def get_age_connection() -> psycopg2.extensions.connection:
    """
    Create connection to PostgreSQL/AGE database.

    Returns:
        PostgreSQL connection
    """
    conn = psycopg2.connect(
        host=AGE_HOST,
        port=AGE_PORT,
        database=AGE_DB,
        user=AGE_USER,
        password=AGE_PASSWORD,
    )
    conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
    return conn


def init_age_session(cursor: psycopg2.extensions.cursor) -> None:
    """
    EVERY db connection using AGE should use this init function.

    IMPORTANT: This must be called for EVERY cursor/session that uses AGE.
    AGE requires both LOAD and search_path to be set per session.

    Args:
        cursor: PostgreSQL cursor

    Usage:
        with conn.cursor() as cur:
            init_age_session(cur)
            cur.execute(...)
    """
    cursor.execute("LOAD 'age';")
    cursor.execute('SET search_path = ag_catalog, "$user", public;')


def execute_cypher(conn: psycopg2.extensions.connection, query: str, params: Optional[dict] = None) -> list:
    """
    Execute a Cypher query using AGE.

    Args:
        conn: PostgreSQL connection
        query: Cypher query
        params: Query parameters (optional)

    Returns:
        Query results
    """
    with conn.cursor() as cursor:
        # CRITICAL: Initialize AGE for this session
        init_age_session(cursor)

        # AGE requires wrapping Cypher in a SQL SELECT
        if params:
            # For parameterized queries, we need to format them properly
            # This is a simplified version - production code would need proper escaping
            formatted_query = query
            for key, value in params.items():
                if isinstance(value, str):
                    formatted_query = formatted_query.replace(f"${key}", f"'{value}'")
                elif isinstance(value, (int, float)):
                    formatted_query = formatted_query.replace(f"${key}", str(value))
                elif value is None:
                    formatted_query = formatted_query.replace(f"${key}", "null")

            query = formatted_query

        sql = f"SELECT * FROM ag_catalog.cypher('{GRAPH_NAME}', $$ {query} $$) as (result agtype);"

        try:
            cursor.execute(sql)
            results = cursor.fetchall()
            return results
        except Exception as e:
            print(f"Error executing Cypher query: {e}")
            print(f"Query: {query}")
            raise


# ============================================================================
# Data Loading Functions
# ============================================================================


def load_papers(age_conn: psycopg2.extensions.connection, provenance_db_path: Path) -> int:
    """
    Load papers from provenance.db into graph.

    Args:
        age_conn: AGE connection
        provenance_db_path: Path to provenance.db

    Returns:
        Number of papers loaded
    """
    print("Loading papers...")

    conn = sqlite3.connect(provenance_db_path)
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT pmc_id, title, journal, pub_date, pmid
        FROM papers
        ORDER BY pmc_id
    """
    )

    papers = cursor.fetchall()
    conn.close()

    for paper_id, title, journal, pub_date, pmid in papers:
        # Escape single quotes in strings
        title_escaped = title.replace("'", "\\'") if title else ""
        journal_escaped = journal.replace("'", "\\'") if journal else ""

        query = f"""
        CREATE (p:Paper {{
            paper_id: '{paper_id}',
            title: '{title_escaped}',
            journal: '{journal_escaped}',
            pub_date: '{pub_date or ""}',
            pmid: '{pmid or ""}'
        }})
        """

        execute_cypher(age_conn, query)

    print(f"  Loaded {len(papers)} papers")
    return len(papers)


def load_entities(age_conn: psycopg2.extensions.connection, entities_db_path: Path) -> int:
    """
    Load entities from entities.db into graph.

    Args:
        age_conn: AGE connection
        entities_db_path: Path to entities.db

    Returns:
        Number of entities loaded
    """
    print("Loading entities...")

    conn = sqlite3.connect(entities_db_path)
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT id, entity_id, canonical_name, type
        FROM entities
        ORDER BY id
    """
    )

    entities = cursor.fetchall()
    conn.close()

    for id, entity_id, canonical_name, entity_type in entities:
        # Escape single quotes
        entity_id_escaped = entity_id.replace("'", "\\'")
        name_escaped = canonical_name.replace("'", "\\'") if canonical_name else ""

        query = f"""
        CREATE (e:Entity {{
            id: {id},
            entity_id: '{entity_id_escaped}',
            name: '{name_escaped}',
            type: '{entity_type}'
        }})
        """

        execute_cypher(age_conn, query)

    print(f"  Loaded {len(entities)} entities")
    return len(entities)


def load_paragraphs(age_conn: psycopg2.extensions.connection, provenance_db_path: Path) -> int:
    """
    Load paragraphs from provenance.db into graph and create edges.

    Args:
        age_conn: AGE connection
        provenance_db_path: Path to provenance.db

    Returns:
        Number of paragraphs loaded
    """
    print("Loading paragraphs...")

    conn = sqlite3.connect(provenance_db_path)
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT p.paragraph_id, p.section_id, s.paper_id, p.text, s.section_type
        FROM paragraphs p
        JOIN sections s ON p.section_id = s.section_id
        ORDER BY p.paragraph_id
    """
    )

    paragraphs = cursor.fetchall()
    conn.close()

    for para_id, section_id, paper_id, text, section_type in paragraphs:
        # Escape single quotes and limit text length for graph storage
        text_escaped = text.replace("'", "\\'")[:500]  # Truncate to 500 chars for graph

        # Create paragraph node
        query = f"""
        CREATE (p:Paragraph {{
            paragraph_id: '{para_id}',
            section_id: '{section_id}',
            section_type: '{section_type}',
            text: '{text_escaped}'
        }})
        """
        execute_cypher(age_conn, query)

        # Create edge from Paper to Paragraph
        query = f"""
        MATCH (paper:Paper {{paper_id: '{paper_id}'}}),
              (para:Paragraph {{paragraph_id: '{para_id}'}})
        CREATE (paper)-[:CONTAINS]->(para)
        """
        execute_cypher(age_conn, query)

    print(f"  Loaded {len(paragraphs)} paragraphs")
    return len(paragraphs)


def load_claims(age_conn: psycopg2.extensions.connection, claims_db_path: Path) -> int:
    """
    Load claims from claims.db into graph and create edges.

    Args:
        age_conn: AGE connection
        claims_db_path: Path to claims.db

    Returns:
        Number of claims loaded
    """
    print("Loading claims...")

    conn = sqlite3.connect(claims_db_path)
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT claim_id, paper_id, paragraph_id, subject_entity_id, predicate,
               object_entity_id, extracted_text, confidence, evidence_type
        FROM claims
        ORDER BY claim_id
    """
    )

    claims = cursor.fetchall()
    conn.close()

    for claim_id, paper_id, para_id, subj_id, predicate, obj_id, text, confidence, ev_type in claims:
        # Escape single quotes
        text_escaped = text.replace("'", "\\'")[:500]

        # Create claim node
        query = f"""
        CREATE (c:Claim {{
            claim_id: '{claim_id}',
            predicate: '{predicate}',
            text: '{text_escaped}',
            confidence: {confidence},
            evidence_type: '{ev_type}'
        }})
        """
        execute_cypher(age_conn, query)

        # Create edge from Paper to Claim
        query = f"""
        MATCH (paper:Paper {{paper_id: '{paper_id}'}}),
              (claim:Claim {{claim_id: '{claim_id}'}})
        CREATE (paper)-[:MAKES_CLAIM]->(claim)
        """
        execute_cypher(age_conn, query)

        # Create edge from Paragraph to Claim
        query = f"""
        MATCH (para:Paragraph {{paragraph_id: '{para_id}'}}),
              (claim:Claim {{claim_id: '{claim_id}'}})
        CREATE (para)-[:CONTAINS_CLAIM]->(claim)
        """
        execute_cypher(age_conn, query)

        # Create edges to entities if they exist
        if subj_id is not None:
            query = f"""
            MATCH (claim:Claim {{claim_id: '{claim_id}'}}),
                  (entity:Entity {{id: {subj_id}}})
            CREATE (claim)-[:HAS_SUBJECT]->(entity)
            """
            try:
                execute_cypher(age_conn, query)
            except Exception:
                # Entity might not exist - this is OK
                pass

        if obj_id is not None:
            query = f"""
            MATCH (claim:Claim {{claim_id: '{claim_id}'}}),
                  (entity:Entity {{id: {obj_id}}})
            CREATE (claim)-[:HAS_OBJECT]->(entity)
            """
            try:
                execute_cypher(age_conn, query)
            except Exception:
                # Entity might not exist - this is OK
                pass

    print(f"  Loaded {len(claims)} claims")
    return len(claims)


def load_evidence(age_conn: psycopg2.extensions.connection, evidence_db_path: Path) -> int:
    """
    Load evidence from evidence.db into graph and create edges.

    Args:
        age_conn: AGE connection
        evidence_db_path: Path to evidence.db

    Returns:
        Number of evidence items loaded
    """
    print("Loading evidence...")

    conn = sqlite3.connect(evidence_db_path)
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT evidence_id, claim_id, supports, strength, type, paragraph_id
        FROM evidence
        ORDER BY evidence_id
    """
    )

    evidence_items = cursor.fetchall()
    conn.close()

    for ev_id, claim_id, supports, strength, ev_type, paragraph_id in evidence_items:
        # Create evidence node
        supports_val = "true" if supports else "false"
        query = f"""
        CREATE (e:Evidence {{
            evidence_id: '{ev_id}',
            type: '{ev_type}',
            strength: '{strength}',
            supports: {supports_val}
        }})
        """
        execute_cypher(age_conn, query)

        # Create edge from Evidence to Claim
        query = f"""
        MATCH (evidence:Evidence {{evidence_id: '{ev_id}'}}),
              (claim:Claim {{claim_id: '{claim_id}'}})
        CREATE (evidence)-[:SUPPORTS]->(claim)
        """
        execute_cypher(age_conn, query)

    print(f"  Loaded {len(evidence_items)} evidence items")
    return len(evidence_items)


def get_graph_stats(age_conn: psycopg2.extensions.connection) -> GraphStats:
    """
    Get statistics about the graph.

    Args:
        age_conn: AGE connection

    Returns:
        Graph statistics
    """
    stats = GraphStats()

    # Count nodes
    node_type_to_field = {"Paper": "papers", "Entity": "entities", "Paragraph": "paragraphs", "Claim": "claims", "Evidence": "evidence"}

    for node_type, field_name in node_type_to_field.items():
        query = f"MATCH (n:{node_type}) RETURN count(n)"
        result = execute_cypher(age_conn, query)
        if result:
            # AGE returns agtype, we need to parse it
            count_str = str(result[0][0])
            count = int(count_str) if count_str.isdigit() else 0
            setattr(stats, field_name, count)

    # Count edges
    query = "MATCH ()-[r]->() RETURN count(r)"
    result = execute_cypher(age_conn, query)
    if result:
        count_str = str(result[0][0])
        stats.edges = int(count_str) if count_str.isdigit() else 0

    return stats


# ============================================================================
# Main Pipeline
# ============================================================================


def main():
    """Main ingest execution."""
    parser = argparse.ArgumentParser(description="Stage 6: Graph Database Pipeline")
    parser.add_argument("--output-dir", type=str, default="output", help="Output directory containing databases")
    parser.add_argument("--clear", action="store_true", help="Clear existing graph data before loading")

    args = parser.parse_args()

    output_dir = Path(args.output_dir)

    if not output_dir.exists():
        print(f"Error: Output directory not found: {output_dir}")
        return 1

    # Check that all required databases exist
    required_dbs = {
        "provenance.db": output_dir / "provenance.db",
        "entities.db": output_dir / "entities.db",
        "claims.db": output_dir / "claims.db",
        "evidence.db": output_dir / "evidence.db",
    }

    for name, path in required_dbs.items():
        if not path.exists():
            print(f"Error: {name} not found at {path}")
            print("Please run previous stages first")
            return 1

    print("=" * 60)
    print("Stage 6: Graph Database Pipeline")
    print("=" * 60)
    print()

    # Connect to AGE
    print(f"Connecting to PostgreSQL/AGE at {AGE_HOST}:{AGE_PORT}...")
    age_conn = get_age_connection()
    print("Connected to PostgreSQL successfully")
    print("AGE session will be initialized for each query")
    print()

    # Clear existing data if requested
    if args.clear:
        print("Clearing existing graph data...")
        try:
            execute_cypher(age_conn, "MATCH (n) DETACH DELETE n")
            print("  Graph cleared")
        except Exception as e:
            print(f"  Warning: Could not clear graph: {e}")
        print()

    # Load data
    print("Loading data into graph...")
    print("-" * 60)

    stats = GraphStats()
    stats.papers = load_papers(age_conn, required_dbs["provenance.db"])
    stats.entities = load_entities(age_conn, required_dbs["entities.db"])
    stats.paragraphs = load_paragraphs(age_conn, required_dbs["provenance.db"])
    stats.claims = load_claims(age_conn, required_dbs["claims.db"])
    stats.evidence = load_evidence(age_conn, required_dbs["evidence.db"])

    print()

    # Get final stats
    print("Retrieving graph statistics...")
    final_stats = get_graph_stats(age_conn)

    print()
    print("=" * 60)
    print("Graph database loading complete!")
    print("=" * 60)
    print(f"Papers: {final_stats.papers}")
    print(f"Entities: {final_stats.entities}")
    print(f"Paragraphs: {final_stats.paragraphs}")
    print(f"Claims: {final_stats.claims}")
    print(f"Evidence: {final_stats.evidence}")
    print(f"Total edges: {final_stats.edges}")
    print("=" * 60)

    # Show sample queries
    print("\nSample Cypher queries:")
    print("  # Find all claims about HIV:")
    print("  MATCH (c:Claim) WHERE c.text =~ '.*HIV.*' RETURN c")
    print()
    print("  # Find claims with evidence:")
    print("  MATCH (e:Evidence)-[:SUPPORTS]->(c:Claim) RETURN e, c")
    print()
    print("  # Find papers and their claims:")
    print("  MATCH (p:Paper)-[:MAKES_CLAIM]->(c:Claim) RETURN p.title, c.predicate, c.text")
    print()

    age_conn.close()
    return 0


if __name__ == "__main__":
    exit(main())

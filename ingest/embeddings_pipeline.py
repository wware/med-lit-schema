#!/usr/bin/env python3
"""
Stage 3: Embeddings Generation Ingest

This ingest generates semantic embeddings for:
1. Entity names (for entity resolution and similarity matching)
2. Paragraph text (for semantic search and claim extraction)

Database Extensions:
- entities.db: entity_embeddings table
- provenance.db: paragraph_embeddings table

This enables:
- Map entity variants: "HIV" / "HTLV-III" / "LAV" → same canonical entity
- Semantic similarity search for related entities
- Find paragraphs discussing similar topics
- Identify contradictory claims via embedding distance

Usage:
    python pmc_embeddings_pipeline.py --output-dir output
"""

import argparse
import sqlite3
from pathlib import Path
import numpy as np
from typing import Optional
from lxml import etree

from pydantic import BaseModel, Field
from med_lit_schema.ingest.ollama_embedding_generator import OllamaEmbeddingGenerator

# Import storage interfaces
try:
    from ..storage.interfaces import PipelineStorageInterface
    from ..storage.backends.sqlite import SQLitePipelineStorage
    from ..storage.backends.postgres import PostgresPipelineStorage
except ImportError:
    from med_lit_schema.storage.interfaces import PipelineStorageInterface
    from med_lit_schema.storage.backends.sqlite import SQLitePipelineStorage
    from med_lit_schema.storage.backends.postgres import PostgresPipelineStorage

from sqlalchemy import create_engine, text
from sqlmodel import Session


# ============================================================================
# Configuration
# ============================================================================

DEFAULT_MODEL = "nomic-embed-text"
# EMBEDDING_DIM will be dynamically determined by the Ollama model
EMBEDDING_DIM = 768  # Default, will be updated dynamically


# ============================================================================
# Pydantic Models
# ============================================================================


class EntityEmbedding(BaseModel):
    """Represents an entity embedding."""

    entity_id: int = Field(..., description="Entity ID from entities table")
    embedding: list[float] = Field(..., description="Embedding vector")
    model_name: str = Field(..., description="Name of embedding model used")
    created_at: str = Field(..., description="Timestamp when embedding was created")


class ParagraphEmbedding(BaseModel):
    """Represents a paragraph embedding."""

    paragraph_id: str = Field(..., description="Paragraph ID from paragraphs table")
    embedding: list[float] = Field(..., description="Embedding vector")
    model_name: str = Field(..., description="Name of embedding model used")
    created_at: str = Field(..., description="Timestamp when embedding was created")


# ============================================================================
# Database Functions
# ============================================================================


def create_entity_embeddings_table(conn: sqlite3.Connection) -> None:
    """
    Create entity_embeddings table in entities.db.

    Args:
        conn: SQLite connection to entities.db
    """
    cursor = conn.cursor()

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS entity_embeddings (
            entity_id TEXT PRIMARY KEY,
            embedding BLOB,
            model_name TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (entity_id) REFERENCES entities(id) ON DELETE CASCADE
        )
    """
    )

    cursor.execute("CREATE INDEX IF NOT EXISTS idx_entity_embeddings ON entity_embeddings(entity_id)")

    conn.commit()


# def create_paragraph_embeddings_table(conn: sqlite3.Connection) -> None:
#     """
#     Create paragraph_embeddings table in provenance.db.

#     Args:
#         conn: SQLite connection to provenance.db
#     """
#     cursor = conn.cursor()

#     cursor.execute(
#         """
#         CREATE TABLE IF NOT EXISTS paragraph_embeddings (
#             paragraph_id TEXT PRIMARY KEY,
#             embedding BLOB,
#             model_name TEXT,
#             created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
#             FOREIGN KEY (paragraph_id) REFERENCES paragraphs(paragraph_id) ON DELETE CASCADE
#         )
#     """
#     )

#     cursor.execute("CREATE INDEX IF NOT EXISTS idx_paragraph_embeddings ON paragraph_embeddings(paragraph_id)")

#     conn.commit()


def get_entities(conn: sqlite3.Connection) -> list[tuple[int, str]]:
    """
    Retrieve all entities from entities.db.

    Args:
        conn: SQLite connection to entities.db

    Returns:
        List of (entity_id, entity_name) tuples
    """
    cursor = conn.cursor()
    cursor.execute("SELECT id, name FROM entities ORDER BY id")
    return cursor.fetchall()


# def get_paragraphs(conn: sqlite3.Connection) -> list[tuple[str, str]]:
#     """
#     Retrieve all paragraphs from provenance.db.

#     Args:
#         conn: SQLite connection to provenance.db

#     Returns:
#         List of (paragraph_id, text) tuples
#     """
#     cursor = conn.cursor()
#     cursor.execute("SELECT paragraph_id, text FROM paragraphs ORDER BY paragraph_id")
#     return cursor.fetchall()


def insert_entity_embedding(conn: sqlite3.Connection, entity_id: int, embedding: np.ndarray, model_name: str) -> None:
    """
    Insert entity embedding into database.

    Args:
        conn: SQLite connection to entities.db
        entity_id: Entity ID
        embedding: Embedding vector as numpy array
        model_name: Name of the embedding model
    """
    cursor = conn.cursor()

    # Convert numpy array to bytes for storage
    embedding_bytes = embedding.astype(np.float32).tobytes()

    cursor.execute(
        """
        INSERT OR REPLACE INTO entity_embeddings
        (entity_id, embedding, model_name)
        VALUES (?, ?, ?)
    """,
        (entity_id, embedding_bytes, model_name),
    )

    conn.commit()


# def insert_paragraph_embedding(conn: sqlite3.Connection, paragraph_id: str, embedding: np.ndarray, model_name: str) -> None:
#     """
#     Insert paragraph embedding into database.

#     Args:
#         conn: SQLite connection to provenance.db
#         paragraph_id: Paragraph ID
#         embedding: Embedding vector as numpy array
#         model_name: Name of the embedding model
#     """
#     cursor = conn.cursor()

#     # Convert numpy array to bytes for storage
#     embedding_bytes = embedding.astype(np.float32).tobytes()

#     cursor.execute(
#         """
#         INSERT OR REPLACE INTO paragraph_embeddings
#         (paragraph_id, embedding, model_name)
#         VALUES (?, ?, ?)
#     """,
#         (paragraph_id, embedding_bytes, model_name),
#     )

#     conn.commit()


def create_paragraph_embeddings_table_sqlite(conn: sqlite3.Connection) -> None:
    """Create paragraph_embeddings table in SQLite database."""
    cursor = conn.cursor()
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS paragraph_embeddings (
            paragraph_id TEXT PRIMARY KEY,
            paper_id TEXT NOT NULL,
            embedding BLOB,
            model_name TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """
    )
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_paragraph_embeddings_para_id ON paragraph_embeddings(paragraph_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_paragraph_embeddings_paper_id ON paragraph_embeddings(paper_id)")
    conn.commit()


def create_paragraph_embeddings_table_postgres(session: Session) -> None:
    """Create paragraph_embeddings table in PostgreSQL with pgvector support."""
    session.execute(
        text(
            """
        CREATE TABLE IF NOT EXISTS paragraph_embeddings (
            paragraph_id TEXT PRIMARY KEY,
            paper_id TEXT NOT NULL,
            embedding vector(768),
            model_name TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """
        )
    )
    session.execute(text("CREATE INDEX IF NOT EXISTS idx_paragraph_embeddings_paper_id ON paragraph_embeddings(paper_id)"))
    try:
        session.execute(
            text(
                """
            CREATE INDEX IF NOT EXISTS idx_paragraph_embeddings_vector
            ON paragraph_embeddings USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100)
        """
            )
        )
    except Exception:
        pass  # pgvector might not be available
    session.commit()


def extract_paragraphs_from_papers(storage: PipelineStorageInterface, xml_dir: Optional[Path] = None) -> list[tuple[str, str, str]]:
    """Extract paragraphs from papers. Returns list of (paragraph_id, text, paper_id) tuples."""
    paragraphs = []
    papers = storage.papers.list_papers(limit=None)

    if xml_dir and xml_dir.exists():
        xml_files = {f.stem: f for f in xml_dir.glob("*.xml")}
        for paper in papers:
            xml_path = xml_files.get(paper.paper_id)
            if not xml_path:
                continue
            try:
                tree = etree.parse(str(xml_path))
                root = tree.getroot()
                para_idx = 0
                for p in root.findall(".//abstract//p"):
                    if p.text and p.text.strip():
                        paragraphs.append((f"{paper.paper_id}_abstract_para_{para_idx}", p.text.strip(), paper.paper_id))
                        para_idx += 1
                para_idx = 0
                for sec in root.findall(".//body//sec"):
                    sec_type = (sec.get("sec-type") or "").lower()
                    if sec_type in {"ref", "references", "ack", "acknowledgements"}:
                        continue
                    for p in sec.findall(".//p"):
                        if p.text and p.text.strip():
                            paragraphs.append((f"{paper.paper_id}_{sec_type}_para_{para_idx}", p.text.strip(), paper.paper_id))
                            para_idx += 1
            except Exception as e:
                print(f"    Warning: Failed to parse {xml_path}: {e}")
    else:
        for paper in papers:
            if paper.abstract:
                paragraphs.append((f"{paper.paper_id}_abstract_para_0", paper.abstract, paper.paper_id))
    return paragraphs


def insert_paragraph_embedding_sqlite(conn: sqlite3.Connection, paragraph_id: str, paper_id: str, embedding: np.ndarray, model_name: str) -> None:
    """Insert paragraph embedding into SQLite database."""
    cursor = conn.cursor()
    embedding_bytes = embedding.astype(np.float32).tobytes()
    cursor.execute(
        """
        INSERT OR REPLACE INTO paragraph_embeddings (paragraph_id, paper_id, embedding, model_name)
        VALUES (?, ?, ?, ?)
    """,
        (paragraph_id, paper_id, embedding_bytes, model_name),
    )
    conn.commit()


def insert_paragraph_embedding_postgres(session: Session, paragraph_id: str, paper_id: str, embedding: list[float], model_name: str) -> None:
    """Insert paragraph embedding into PostgreSQL database with pgvector."""
    embedding_str = "[" + ",".join(map(str, embedding)) + "]"
    session.execute(
        text(
            """
        INSERT INTO paragraph_embeddings (paragraph_id, paper_id, embedding, model_name)
        VALUES (:paragraph_id, :paper_id, :embedding::vector, :model_name)
        ON CONFLICT (paragraph_id)
        DO UPDATE SET embedding = :embedding::vector, model_name = :model_name, created_at = CURRENT_TIMESTAMP
    """
        ),
        {"paragraph_id": paragraph_id, "paper_id": paper_id, "embedding": embedding_str, "model_name": model_name},
    )
    session.commit()


def load_embedding(embedding_bytes: bytes) -> np.ndarray:
    """
    Load embedding from bytes.

    Args:
        embedding_bytes: Embedding stored as bytes

    Returns:
        Numpy array of shape (dim,)
    """
    return np.frombuffer(embedding_bytes, dtype=np.float32).reshape(EMBEDDING_DIM)


# ============================================================================
# Embedding Generation
# ============================================================================


def generate_entity_embeddings(entities_db_path: Path, model_name: str = DEFAULT_MODEL, batch_size: int = 32, ollama_host: str = "http://localhost:11434") -> int:
    """
    Generate embeddings for all entities in entities.db.

    Args:
        entities_db_path: Path to entities.db
        model_name: Name of Ollama model to use
        batch_size: Batch size for encoding

    Returns:
        Number of entity embeddings created
    """
    print(f"Loading embedding model: {model_name}")
    embedding_generator = OllamaEmbeddingGenerator(model_name=model_name, host=ollama_host)

    # Use the dynamically determined embedding dimension
    global EMBEDDING_DIM
    EMBEDDING_DIM = embedding_generator.embedding_dim

    print(f"Connecting to {entities_db_path}")
    conn = sqlite3.connect(entities_db_path)

    # Create embeddings table if it doesn't exist
    create_entity_embeddings_table(conn)

    # Get all entities
    entities = get_entities(conn)
    print(f"Found {len(entities)} entities")

    if not entities:
        print("No entities found in database")
        conn.close()
        return 0

    # Extract entity names and IDs
    entity_ids = [e[0] for e in entities]
    entity_names = [e[1] for e in entities]

    print(f"Generating embeddings (batch size: {batch_size})...")

    # Generate embeddings in batches
    embeddings_list = embedding_generator.generate_embeddings_batch(entity_names, batch_size=batch_size)
    embeddings = np.array(embeddings_list)

    # Insert embeddings into database
    print("Storing embeddings in database...")
    for entity_id, embedding in zip(entity_ids, embeddings):
        insert_entity_embedding(conn, entity_id, embedding, model_name)

    conn.close()

    print(f"Created {len(embeddings)} entity embeddings")
    return len(embeddings)


def generate_paragraph_embeddings(
    storage: PipelineStorageInterface,
    model_name: str = DEFAULT_MODEL,
    batch_size: int = 32,
    ollama_host: str = "http://localhost:11434",
    xml_dir: Optional[Path] = None,
) -> int:
    """
    Generate embeddings for all paragraphs from papers in storage.

    Args:
        storage: Storage interface to get papers from
        model_name: Name of Ollama model to use
        batch_size: Batch size for encoding
        ollama_host: Ollama server URL
        xml_dir: Optional directory containing XML files for re-parsing

    Returns:
        Number of paragraph embeddings created
    """
    print(f"Loading embedding model: {model_name}")
    embedding_generator = OllamaEmbeddingGenerator(model_name=model_name, host=ollama_host)

    # Use the dynamically determined embedding dimension
    global EMBEDDING_DIM
    EMBEDDING_DIM = embedding_generator.embedding_dim

    # Extract paragraphs from papers
    print("Extracting paragraphs from papers...")
    paragraphs = extract_paragraphs_from_papers(storage, xml_dir)
    print(f"Found {len(paragraphs)} paragraphs")

    if not paragraphs:
        print("No paragraphs found")
        return 0

    # Extract paragraph IDs, texts, and paper IDs
    paragraph_ids = [p[0] for p in paragraphs]
    paragraph_texts = [p[1] for p in paragraphs]
    paper_ids = [p[2] for p in paragraphs]

    # Create embeddings table based on storage type
    if isinstance(storage, SQLitePipelineStorage):
        create_paragraph_embeddings_table_sqlite(storage.papers.conn)
    elif isinstance(storage, PostgresPipelineStorage):
        create_paragraph_embeddings_table_postgres(storage.session)

    print(f"Generating embeddings (batch size: {batch_size})...")

    # Generate embeddings in batches
    embeddings_list = embedding_generator.generate_embeddings_batch(paragraph_texts, batch_size=batch_size)

    # Insert embeddings into database
    print("Storing embeddings in database...")
    stored_count = 0
    for (para_id, paper_id), embedding in zip(zip(paragraph_ids, paper_ids), embeddings_list):
        if isinstance(storage, SQLitePipelineStorage):
            embedding_array = np.array(embedding)
            insert_paragraph_embedding_sqlite(storage.papers.conn, para_id, paper_id, embedding_array, model_name)
        elif isinstance(storage, PostgresPipelineStorage):
            insert_paragraph_embedding_postgres(storage.session, para_id, paper_id, embedding, model_name)
        stored_count += 1

    print(f"Created {stored_count} paragraph embeddings")
    return stored_count


# ============================================================================
# Similarity Search Functions
# ============================================================================


def find_similar_entities(entities_db_path: Path, entity_id: int, top_k: int = 5) -> list[tuple[int, str, float]]:
    """
    Find entities most similar to the given entity.

    Args:
        entities_db_path: Path to entities.db
        entity_id: Entity ID to find similar entities for
        top_k: Number of similar entities to return

    Returns:
        List of (entity_id, entity_name, similarity_score) tuples, sorted by similarity
    """
    conn = sqlite3.connect(entities_db_path)
    cursor = conn.cursor()

    # Get target entity embedding
    cursor.execute("SELECT embedding FROM entity_embeddings WHERE entity_id = ?", (entity_id,))
    row = cursor.fetchone()
    if not row:
        print(f"No embedding found for entity {entity_id}")
        conn.close()
        return []

    target_embedding = load_embedding(row[0])

    # Get all entity embeddings
    cursor.execute(
        """
        SELECT e.id, e.canonical_name, ee.embedding
        FROM entities e
        JOIN entity_embeddings ee ON e.id = ee.entity_id
        WHERE e.id != ?
    """,
        (entity_id,),
    )

    # Calculate cosine similarities
    similarities = []
    for eid, name, emb_bytes in cursor.fetchall():
        embedding = load_embedding(emb_bytes)
        # Cosine similarity
        similarity = np.dot(target_embedding, embedding) / (np.linalg.norm(target_embedding) * np.linalg.norm(embedding))
        similarities.append((eid, name, float(similarity)))

    conn.close()

    # Sort by similarity (descending) and return top_k
    similarities.sort(key=lambda x: x[2], reverse=True)
    return similarities[:top_k]


def find_similar_paragraphs(provenance_db_path: Path, paragraph_id: str, top_k: int = 5) -> list[tuple[str, str, float]]:
    """
    Find paragraphs most similar to the given paragraph.

    Args:
        provenance_db_path: Path to provenance.db
        paragraph_id: Paragraph ID to find similar paragraphs for
        top_k: Number of similar paragraphs to return

    Returns:
        List of (paragraph_id, text_preview, similarity_score) tuples, sorted by similarity
    """
    conn = sqlite3.connect(provenance_db_path)
    cursor = conn.cursor()

    # Get target paragraph embedding
    cursor.execute("SELECT embedding FROM paragraph_embeddings WHERE paragraph_id = ?", (paragraph_id,))
    row = cursor.fetchone()
    if not row:
        print(f"No embedding found for paragraph {paragraph_id}")
        conn.close()
        return []

    target_embedding = load_embedding(row[0])

    # Get all paragraph embeddings
    cursor.execute(
        """
        SELECT p.paragraph_id, p.text, pe.embedding
        FROM paragraphs p
        JOIN paragraph_embeddings pe ON p.paragraph_id = pe.paragraph_id
        WHERE p.paragraph_id != ?
    """,
        (paragraph_id,),
    )

    # Calculate cosine similarities
    similarities = []
    for pid, txt, emb_bytes in cursor.fetchall():
        embedding = load_embedding(emb_bytes)
        # Cosine similarity
        similarity = np.dot(target_embedding, embedding) / (np.linalg.norm(target_embedding) * np.linalg.norm(embedding))
        # Truncate text for preview
        text_preview = txt[:100] + "..." if len(txt) > 100 else txt
        similarities.append((pid, text_preview, float(similarity)))

    conn.close()

    # Sort by similarity (descending) and return top_k
    similarities.sort(key=lambda x: x[2], reverse=True)
    return similarities[:top_k]


# ============================================================================
# Main Pipeline
# ============================================================================


def main():
    """Main ingest execution."""
    parser = argparse.ArgumentParser(description="Stage 3: Embeddings Generation Pipeline")
    parser.add_argument("--output-dir", type=str, default="output", help="Output directory containing databases")
    parser.add_argument("--storage", type=str, choices=["sqlite", "postgres"], default="sqlite", help="Storage backend (default: sqlite)")
    parser.add_argument("--database-url", type=str, help="PostgreSQL connection URL (required for --storage postgres)")
    parser.add_argument("--model", type=str, default=DEFAULT_MODEL, help="Ollama model name for embeddings")
    parser.add_argument("--batch-size", type=int, default=32, help="Batch size for encoding")
    parser.add_argument("--entities-only", action="store_true", help="Generate only entity embeddings")
    parser.add_argument("--paragraphs-only", action="store_true", help="Generate only paragraph embeddings")
    parser.add_argument("--ollama-host", type=str, default=None, help="Ollama server URL (defaults to OLLAMA_HOST env var or http://localhost:11434)")
    parser.add_argument("--xml-dir", type=str, default="ingest/pmc_xmls", help="Directory containing XML files for paragraph extraction")

    args = parser.parse_args()

    # Use OLLAMA_HOST environment variable as fallback if --ollama-host not provided
    import os
    ollama_host = args.ollama_host or os.getenv("OLLAMA_HOST", "http://localhost:11434")

    output_dir = Path(args.output_dir)

    # Validate arguments
    if args.storage == "postgres" and not args.database_url:
        print("Error: --database-url is required when using --storage postgres")
        return 1

    # Validate output directory (for SQLite)
    if args.storage == "sqlite" and not output_dir.exists():
        print(f"Error: Output directory not found: {output_dir}")
        return 1

    print("=" * 60)
    print("Stage 3: Embeddings Generation Pipeline")
    print("=" * 60)
    print(f"Storage: {args.storage}")
    print(f"Model: {args.model}")
    print(f"Batch size: {args.batch_size}")
    print()

    total_embeddings = 0
    xml_dir = Path(args.xml_dir) if args.xml_dir else None

    # Generate entity embeddings (SQLite only for now)
    if not args.paragraphs_only:
        if args.storage == "postgres":
            print("⚠️  Note: Entity embeddings for PostgreSQL are not yet fully implemented.")
            print("   Relationship embeddings are generated in Stage 4 (claims_pipeline).")
            print("   Skipping entity embeddings generation.")
        else:
            entities_db_path = output_dir / "ingest.db"
            if not entities_db_path.exists():
                print(f"Warning: ingest.db not found at {entities_db_path}")
                print("Skipping entity embeddings")
            else:
                print("Generating entity embeddings...")
                print("-" * 60)
                count = generate_entity_embeddings(entities_db_path, model_name=args.model, batch_size=args.batch_size, ollama_host=ollama_host)
                total_embeddings += count
                print()

    # Generate paragraph embeddings (supports both SQLite and PostgreSQL)
    if not args.entities_only:
        print("Generating paragraph embeddings...")
        print("-" * 60)

        if args.storage == "sqlite":
            entities_db_path = output_dir / "ingest.db"
            if not entities_db_path.exists():
                print(f"Warning: ingest.db not found at {entities_db_path}")
                print("Skipping paragraph embeddings")
            else:
                storage = SQLitePipelineStorage(entities_db_path)
                try:
                    count = generate_paragraph_embeddings(storage=storage, model_name=args.model, batch_size=args.batch_size, ollama_host=ollama_host, xml_dir=xml_dir)
                    total_embeddings += count
                finally:
                    storage.close()
        else:  # postgres
            if not args.database_url:
                print("Warning: --database-url required for PostgreSQL")
                print("Skipping paragraph embeddings")
            else:
                engine = create_engine(args.database_url)
                with Session(engine) as session:
                    storage = PostgresPipelineStorage(session)
                    count = generate_paragraph_embeddings(storage=storage, model_name=args.model, batch_size=args.batch_size, ollama_host=ollama_host, xml_dir=xml_dir)
                    total_embeddings += count
        print()

    # Print summary
    print("=" * 60)
    print("Embeddings generation complete!")
    print(f"Total embeddings created: {total_embeddings}")
    print("=" * 60)

    return 0


if __name__ == "__main__":
    exit(main())

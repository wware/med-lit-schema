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

from pydantic import BaseModel, Field
from med_lit_schema.ingest.ollama_embedding_generator import OllamaEmbeddingGenerator


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


def generate_entity_embeddings(entities_db_path: Path, model_name: str = DEFAULT_MODEL, batch_size: int = 32) -> int:
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
    embedding_generator = OllamaEmbeddingGenerator(model_name=model_name)

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


# def generate_paragraph_embeddings(provenance_db_path: Path, model_name: str = DEFAULT_MODEL, batch_size: int = 32) -> int:
#     """
#     Generate embeddings for all paragraphs in provenance.db.

#     Args:
#         provenance_db_path: Path to provenance.db
#         model_name: Name of Ollama model to use
#         batch_size: Batch size for encoding

#     Returns:
#         Number of paragraph embeddings created
#     """
#     print(f"Loading embedding model: {model_name}")
#     embedding_generator = OllamaEmbeddingGenerator(model_name=model_name)

#     # Use the dynamically determined embedding dimension
#     global EMBEDDING_DIM
#     EMBEDDING_DIM = embedding_generator.embedding_dim

#     print(f"Connecting to {provenance_db_path}")
#     conn = sqlite3.connect(provenance_db_path)

#     # Create embeddings table if it doesn't exist
#     create_paragraph_embeddings_table(conn)

#     # Get all paragraphs
#     paragraphs = get_paragraphs(conn)
#     print(f"Found {len(paragraphs)} paragraphs")

#     if not paragraphs:
#         print("No paragraphs found in database")
#         conn.close()
#         return 0

#     # Extract paragraph IDs and texts
#     paragraph_ids = [p[0] for p in paragraphs]
#     paragraph_texts = [p[1] for p in paragraphs]

#     print(f"Generating embeddings (batch size: {batch_size})...")

#     # Generate embeddings in batches
#     embeddings_list = embedding_generator.generate_embeddings_batch(paragraph_texts, batch_size=batch_size)
#     embeddings = np.array(embeddings_list)

#     # Insert embeddings into database
#     print("Storing embeddings in database...")
#     for paragraph_id, embedding in zip(paragraph_ids, embeddings):
#         insert_paragraph_embedding(conn, paragraph_id, embedding, model_name)

#     conn.close()

#     print(f"Created {len(embeddings)} paragraph embeddings")
#     return len(embeddings)


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
    for pid, text, emb_bytes in cursor.fetchall():
        embedding = load_embedding(emb_bytes)
        # Cosine similarity
        similarity = np.dot(target_embedding, embedding) / (np.linalg.norm(target_embedding) * np.linalg.norm(embedding))
        # Truncate text for preview
        text_preview = text[:100] + "..." if len(text) > 100 else text
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
    parser.add_argument("--model", type=str, default=DEFAULT_MODEL, help="Sentence-transformers model name")
    parser.add_argument("--batch-size", type=int, default=32, help="Batch size for encoding")
    parser.add_argument("--entities-only", action="store_true", help="Generate only entity embeddings")
    parser.add_argument("--paragraphs-only", action="store_true", help="Generate only paragraph embeddings")

    args = parser.parse_args()

    output_dir = Path(args.output_dir)

    # Validate output directory
    if not output_dir.exists():
        print(f"Error: Output directory not found: {output_dir}")
        return 1

    entities_db_path = output_dir / "ingest.db"
    # provenance_db_path = output_dir / "ingest.db"

    print("=" * 60)
    print("Stage 3: Embeddings Generation Pipeline")
    print("=" * 60)
    print(f"Model: {args.model}")
    print(f"Batch size: {args.batch_size}")
    print()

    total_embeddings = 0

    # Generate entity embeddings
    if not args.paragraphs_only:
        if not entities_db_path.exists():
            print(f"Warning: entities.db not found at {entities_db_path}")
            print("Skipping entity embeddings")
        else:
            print("Generating entity embeddings...")
            print("-" * 60)
            count = generate_entity_embeddings(entities_db_path, model_name=args.model, batch_size=args.batch_size)
            total_embeddings += count
            print()

    # # Generate paragraph embeddings
    # if not args.entities_only:
    #     if not provenance_db_path.exists():
    #         print(f"Warning: provenance.db not found at {provenance_db_path}")
    #         print("Skipping paragraph embeddings")
    #     else:
    #         print("Generating paragraph embeddings...")
    #         print("-" * 60)
    #         count = generate_paragraph_embeddings(provenance_db_path, model_name=args.model, batch_size=args.batch_size)
    #         total_embeddings += count
    #         print()

    # Print summary
    print("=" * 60)
    print("Embeddings generation complete!")
    print(f"Total embeddings created: {total_embeddings}")
    print("=" * 60)

    return 0


if __name__ == "__main__":
    exit(main())

"""
SQLite implementation of ingest storage interfaces.

This implementation uses SQLite for testing and development.
It stores domain models as JSON in SQLite tables, with indexes for common queries.
"""

import json
import sqlite3
from pathlib import Path
from typing import Optional

from med_lit_schema.storage.interfaces import (
    PaperStorageInterface,
    RelationshipStorageInterface,
    EvidenceStorageInterface,
    PipelineStorageInterface,
)
from med_lit_schema.ingest.embedding_interfaces import RelationshipEmbeddingStorageInterface
from med_lit_schema.entity import (
    Paper,
    EvidenceItem,
    EntityCollectionInterface,
)
from med_lit_schema.storage.backends.sqlite_entity_collection import SQLiteEntityCollection
from med_lit_schema.relationship import BaseRelationship, create_relationship
from med_lit_schema.base import PredicateType


class SQLitePaperStorage(PaperStorageInterface):
    """SQLite implementation of paper storage."""

    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn
        self._create_tables()

    def _create_tables(self) -> None:
        """Create papers table if it doesn't exist."""
        cursor = self.conn.cursor()
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS papers (
                paper_id TEXT PRIMARY KEY,
                paper_json TEXT NOT NULL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """
        )
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_papers_paper_id ON papers(paper_id)")
        self.conn.commit()

    def add_paper(self, paper: Paper) -> None:
        """Add or update a paper in storage."""
        cursor = self.conn.cursor()
        cursor.execute(
            "INSERT OR REPLACE INTO papers (paper_id, paper_json, updated_at) VALUES (?, ?, CURRENT_TIMESTAMP)",
            (paper.paper_id, paper.model_dump_json()),
        )
        self.conn.commit()

    def get_paper(self, paper_id: str) -> Optional[Paper]:
        """Get a paper by ID."""
        cursor = self.conn.cursor()
        cursor.execute("SELECT paper_json FROM papers WHERE paper_id = ?", (paper_id,))
        row = cursor.fetchone()
        if row:
            return Paper.model_validate_json(row[0])
        return None

    def list_papers(self, limit: Optional[int] = None, offset: int = 0) -> list[Paper]:
        """List papers, optionally with pagination."""
        cursor = self.conn.cursor()
        query = "SELECT paper_json FROM papers ORDER BY paper_id"
        if limit:
            query += f" LIMIT {limit} OFFSET {offset}"
        cursor.execute(query)
        return [Paper.model_validate_json(row[0]) for row in cursor.fetchall()]

    @property
    def paper_count(self) -> int:
        """Total number of papers in storage."""
        cursor = self.conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM papers")
        return cursor.fetchone()[0]


class SQLiteRelationshipStorage(RelationshipStorageInterface):
    """SQLite implementation of relationship storage."""

    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn
        self._create_tables()

    def _create_tables(self) -> None:
        """Create relationships table if it doesn't exist."""
        cursor = self.conn.cursor()
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS relationships (
                subject_id TEXT NOT NULL,
                predicate TEXT NOT NULL,
                object_id TEXT NOT NULL,
                relationship_json TEXT NOT NULL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (subject_id, predicate, object_id)
            )
        """
        )
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_relationships_subject ON relationships(subject_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_relationships_object ON relationships(object_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_relationships_predicate ON relationships(predicate)")
        self.conn.commit()

    def add_relationship(self, relationship: BaseRelationship) -> None:
        """Add or update a relationship in storage."""
        cursor = self.conn.cursor()
        cursor.execute(
            """
            INSERT OR REPLACE INTO relationships
            (subject_id, predicate, object_id, relationship_json, updated_at)
            VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
        """,
            (
                relationship.subject_id,
                relationship.predicate.value if hasattr(relationship.predicate, "value") else str(relationship.predicate),
                relationship.object_id,
                relationship.model_dump_json(),
            ),
        )
        self.conn.commit()

    def get_relationship(self, subject_id: str, predicate: str, object_id: str) -> Optional[BaseRelationship]:
        """Get a relationship by its canonical triple."""
        cursor = self.conn.cursor()
        cursor.execute(
            """
            SELECT relationship_json FROM relationships
            WHERE subject_id = ? AND predicate = ? AND object_id = ?
        """,
            (subject_id, predicate, object_id),
        )
        row = cursor.fetchone()
        if row:
            data = json.loads(row[0])
            # Reconstruct the relationship using create_relationship
            predicate_enum = PredicateType(predicate)
            # Remove subject_id and object_id from data since we pass them explicitly
            data.pop("subject_id", None)
            data.pop("object_id", None)
            data.pop("predicate", None)  # Also remove predicate since we pass it explicitly
            return create_relationship(predicate_enum, subject_id, object_id, **data)
        return None

    def find_relationships(
        self,
        subject_id: Optional[str] = None,
        predicate: Optional[str] = None,
        object_id: Optional[str] = None,
        limit: Optional[int] = None,
    ) -> list[BaseRelationship]:
        """Find relationships matching criteria."""
        cursor = self.conn.cursor()
        conditions = []
        params = []

        if subject_id:
            conditions.append("subject_id = ?")
            params.append(subject_id)
        if predicate:
            conditions.append("predicate = ?")
            params.append(predicate)
        if object_id:
            conditions.append("object_id = ?")
            params.append(object_id)

        query = "SELECT relationship_json FROM relationships"
        if conditions:
            query += " WHERE " + " AND ".join(conditions)
        query += " ORDER BY created_at DESC"
        if limit:
            query += f" LIMIT {limit}"

        cursor.execute(query, params)
        results = []
        for row in cursor.fetchall():
            data = json.loads(row[0])
            predicate_enum = PredicateType(data["predicate"])
            subject_id = data.pop("subject_id")
            object_id = data.pop("object_id")
            data.pop("predicate", None)  # Remove predicate since we pass it explicitly
            results.append(create_relationship(predicate_enum, subject_id, object_id, **data))
        return results

    def list_relationships(self, limit: Optional[int] = None, offset: int = 0) -> list[BaseRelationship]:
        """List relationships, optionally with pagination."""
        cursor = self.conn.cursor()
        query = "SELECT relationship_json FROM relationships ORDER BY created_at DESC"
        if limit:
            query += f" LIMIT {limit} OFFSET {offset}"
        cursor.execute(query)
        results = []
        for row in cursor.fetchall():
            data = json.loads(row[0])
            predicate_enum = PredicateType(data["predicate"])
            subject_id = data.pop("subject_id")
            object_id = data.pop("object_id")
            data.pop("predicate", None)  # Remove predicate since we pass it explicitly
            results.append(create_relationship(predicate_enum, subject_id, object_id, **data))
        return results

    @property
    def relationship_count(self) -> int:
        """Total number of relationships in storage."""
        cursor = self.conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM relationships")
        return cursor.fetchone()[0]


class SQLiteEvidenceStorage(EvidenceStorageInterface):
    """SQLite implementation of evidence storage."""

    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn
        self._create_tables()

    def _create_tables(self) -> None:
        """Create evidence table if it doesn't exist."""
        cursor = self.conn.cursor()
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS evidence (
                evidence_id TEXT PRIMARY KEY,
                paper_id TEXT NOT NULL,
                subject_id TEXT,
                predicate TEXT,
                object_id TEXT,
                evidence_json TEXT NOT NULL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """
        )
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_evidence_paper_id ON evidence(paper_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_evidence_relationship ON evidence(subject_id, predicate, object_id)")
        self.conn.commit()

    def add_evidence(self, evidence: EvidenceItem) -> None:
        """Add or update evidence in storage."""
        cursor = self.conn.cursor()
        # Generate evidence_id from paper_id and a hash or sequence
        evidence_id = f"{evidence.paper_id}_evidence_{hash(evidence.model_dump_json()) % 1000000}"

        # Extract relationship info if available (would need to be passed separately)
        subject_id = None
        predicate = None
        object_id = None

        cursor.execute(
            """
            INSERT OR REPLACE INTO evidence
            (evidence_id, paper_id, subject_id, predicate, object_id, evidence_json)
            VALUES (?, ?, ?, ?, ?, ?)
        """,
            (
                evidence_id,
                evidence.paper_id,
                subject_id,
                predicate,
                object_id,
                evidence.model_dump_json(),
            ),
        )
        self.conn.commit()

    def get_evidence_by_paper(self, paper_id: str) -> list[EvidenceItem]:
        """Get all evidence items for a paper."""
        cursor = self.conn.cursor()
        cursor.execute("SELECT evidence_json FROM evidence WHERE paper_id = ?", (paper_id,))
        return [EvidenceItem.model_validate_json(row[0]) for row in cursor.fetchall()]

    def get_evidence_for_relationship(self, subject_id: str, predicate: str, object_id: str) -> list[EvidenceItem]:
        """Get all evidence items supporting a relationship."""
        cursor = self.conn.cursor()
        cursor.execute(
            """
            SELECT evidence_json FROM evidence
            WHERE subject_id = ? AND predicate = ? AND object_id = ?
        """,
            (subject_id, predicate, object_id),
        )
        return [EvidenceItem.model_validate_json(row[0]) for row in cursor.fetchall()]

    @property
    def evidence_count(self) -> int:
        """Total number of evidence items in storage."""
        cursor = self.conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM evidence")
        return cursor.fetchone()[0]


class SQLiteRelationshipEmbeddingStorage(RelationshipEmbeddingStorageInterface):
    """SQLite implementation of relationship embedding storage."""

    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn
        self._create_tables()

    def _create_tables(self) -> None:
        """Create relationship_embeddings table if it doesn't exist."""
        cursor = self.conn.cursor()
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS relationship_embeddings (
                subject_id TEXT NOT NULL,
                predicate TEXT NOT NULL,
                object_id TEXT NOT NULL,
                embedding BLOB NOT NULL,
                model_name TEXT NOT NULL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (subject_id, predicate, object_id, model_name),
                FOREIGN KEY (subject_id, predicate, object_id)
                    REFERENCES relationships(subject_id, predicate, object_id)
                    ON DELETE CASCADE
            )
        """
        )
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_rel_embeddings_triple ON relationship_embeddings(subject_id, predicate, object_id)")
        self.conn.commit()

    def store_relationship_embedding(self, subject_id: str, predicate: str, object_id: str, embedding: list[float], model_name: str) -> None:
        """Store an embedding for a relationship."""
        import struct

        cursor = self.conn.cursor()
        # Convert embedding list to bytes (float32)
        embedding_bytes = struct.pack(f"{len(embedding)}f", *embedding)

        cursor.execute(
            """
            INSERT OR REPLACE INTO relationship_embeddings
            (subject_id, predicate, object_id, embedding, model_name, created_at)
            VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
        """,
            (subject_id, predicate, object_id, embedding_bytes, model_name),
        )
        self.conn.commit()

    def get_relationship_embedding(self, subject_id: str, predicate: str, object_id: str) -> Optional[list[float]]:
        """Get the embedding for a relationship."""
        import struct

        cursor = self.conn.cursor()
        cursor.execute(
            """
            SELECT embedding FROM relationship_embeddings
            WHERE subject_id = ? AND predicate = ? AND object_id = ?
            ORDER BY created_at DESC
            LIMIT 1
        """,
            (subject_id, predicate, object_id),
        )
        row = cursor.fetchone()
        if not row:
            return None

        # Convert bytes back to list of floats
        embedding_bytes = row[0]
        embedding = list(struct.unpack(f"{len(embedding_bytes) // 4}f", embedding_bytes))
        return embedding

    def find_similar_relationships(self, query_embedding: list[float], top_k: int = 5, threshold: float = 0.85) -> list[tuple[tuple[str, str, str], float]]:
        """Find relationships similar to query embedding using cosine similarity."""
        import struct
        from math import sqrt

        cursor = self.conn.cursor()
        cursor.execute("SELECT subject_id, predicate, object_id, embedding FROM relationship_embeddings")

        # Compute cosine similarity for each embedding
        query_norm = sqrt(sum(x * x for x in query_embedding))
        results = []

        for row in cursor.fetchall():
            subject_id, predicate, object_id, embedding_bytes = row
            # Convert bytes to list
            embedding = list(struct.unpack(f"{len(embedding_bytes) // 4}f", embedding_bytes))

            # Compute cosine similarity
            dot_product = sum(a * b for a, b in zip(query_embedding, embedding))
            embedding_norm = sqrt(sum(x * x for x in embedding))
            similarity = dot_product / (query_norm * embedding_norm) if embedding_norm > 0 else 0.0

            if similarity >= threshold:
                results.append(((subject_id, predicate, object_id), similarity))

        # Sort by similarity and return top_k
        results.sort(key=lambda x: x[1], reverse=True)
        return results[:top_k]


class SQLitePipelineStorage(PipelineStorageInterface):
    """SQLite implementation of combined ingest storage.

    Uses SQLite databases for all storage needs. Suitable for testing and development.
    """

    def __init__(self, db_path: Path | str):
        """Initialize SQLite storage.

        Args:
            db_path: Path to SQLite database file, or ":memory:" for in-memory database
        """
        self.db_path = db_path if isinstance(db_path, Path) else Path(db_path) if db_path != ":memory:" else None
        self.conn = sqlite3.connect(str(db_path) if db_path != ":memory:" else ":memory:")
        self.conn.execute("PRAGMA foreign_keys = ON")

        # Initialize storage components
        self._papers = SQLitePaperStorage(self.conn)
        self._relationships = SQLiteRelationshipStorage(self.conn)
        self._evidence = SQLiteEvidenceStorage(self.conn)
        self._relationship_embeddings = SQLiteRelationshipEmbeddingStorage(self.conn)

        # Use SQLite entity collection with sqlite-vec support
        self._entities = SQLiteEntityCollection(self.conn)

    @property
    def entities(self) -> EntityCollectionInterface:
        """Access to entity storage."""
        return self._entities

    @property
    def papers(self) -> PaperStorageInterface:
        """Access to paper storage."""
        return self._papers

    @property
    def relationships(self) -> RelationshipStorageInterface:
        """Access to relationship storage."""
        return self._relationships

    @property
    def evidence(self) -> EvidenceStorageInterface:
        """Access to evidence storage."""
        return self._evidence

    @property
    def relationship_embeddings(self) -> RelationshipEmbeddingStorageInterface:
        """Access to relationship embedding storage."""
        return self._relationship_embeddings

    def __enter__(self):
        """Enter context manager."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Exit context manager and close connection."""
        self.close()
        return False

    def close(self) -> None:
        """Close connections and clean up resources."""
        self.conn.close()

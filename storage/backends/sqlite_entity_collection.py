"""
SQLite implementation of EntityCollectionInterface with sqlite-vec support.

This provides entity storage in SQLite with vector similarity search using sqlite-vec.
"""

import json
import sqlite3
from typing import Optional, TYPE_CHECKING
from med_lit_schema.entity import BaseMedicalEntity

if TYPE_CHECKING:
    from med_lit_schema.entity import (
        Disease,
        Gene,
        Drug,
        Protein,
        Hypothesis,
        StudyDesign,
        StatisticalMethod,
        EvidenceLine,
        Symptom,
        Procedure,
        Biomarker,
        Pathway,
    )

from med_lit_schema.entity import EntityCollectionInterface
from med_lit_schema.mapper import to_persistence, to_domain
from med_lit_schema.storage.models.entity import Entity


class SQLiteEntityCollection(EntityCollectionInterface):
    """SQLite implementation of entity collection with sqlite-vec for embedding search.

    Stores entities in SQLite with vector embeddings for similarity search.
    Requires sqlite-vec extension to be loaded.
    """

    def __init__(self, conn: sqlite3.Connection):
        """Initialize SQLite entity collection.

        Args:
            conn: SQLite connection (should have sqlite-vec extension loaded)
        """
        self.conn = conn
        self._create_tables()
        self._load_extension()

    def _load_extension(self) -> None:
        """Load sqlite-vec extension if available."""
        try:
            # Try to load sqlite-vec extension
            # On Linux, this might be at various paths
            possible_paths = [
                "/usr/lib/sqlite3/libvec0.so",
                "/usr/local/lib/libvec0.so",
                "./libvec0.so",
                "libvec0.so",
            ]

            for path in possible_paths:
                try:
                    self.conn.enable_load_extension(True)
                    self.conn.load_extension(path)
                    self.conn.enable_load_extension(False)
                    print(f"Loaded sqlite-vec extension from {path}")
                    return
                except Exception:
                    continue

            # If loading fails, we'll still work but without vector search
            print("Warning: sqlite-vec extension not found. Vector search will be disabled.")
            print("Install sqlite-vec from https://github.com/asg017/sqlite-vec")
        except Exception as e:
            print(f"Warning: Could not load sqlite-vec extension: {e}")
            print("Vector search will be disabled. Install sqlite-vec for embedding support.")

    def _create_tables(self) -> None:
        """Create entities table with vector column for embeddings."""
        cursor = self.conn.cursor()

        # Create entities table
        # Note: sqlite-vec uses a special vector type
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS entities (
                id TEXT PRIMARY KEY,
                entity_type TEXT NOT NULL,
                name TEXT NOT NULL,
                synonyms TEXT,  -- JSON array
                abbreviations TEXT,  -- JSON array
                embedding BLOB,  -- Vector embedding (sqlite-vec format)
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                source TEXT,
                -- Type-specific fields (flattened from Entity SQLModel)
                umls_id TEXT,
                hgnc_id TEXT,
                rxnorm_id TEXT,
                uniprot_id TEXT,
                -- Store full entity JSON for reconstruction
                entity_json TEXT
            )
        """
        )

        # Create indexes
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_entities_type ON entities(entity_type)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_entities_umls ON entities(umls_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_entities_hgnc ON entities(hgnc_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_entities_rxnorm ON entities(rxnorm_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_entities_uniprot ON entities(uniprot_id)")

        # Note: sqlite-vec vector operations use functions like vec_distance_cosine()
        # The embedding column stores vectors in sqlite-vec's binary format
        # Vector indexes are created automatically by sqlite-vec when needed

        self.conn.commit()

    def _add_entity(self, entity: BaseMedicalEntity) -> None:
        """Internal method to add any entity type."""
        # Convert to persistence model to get flattened fields
        persistence = to_persistence(entity)

        # Serialize embedding if present
        embedding_blob = None
        if entity.embedding:
            # sqlite-vec expects embeddings in a specific format
            # For now, store as JSON - will need proper conversion for sqlite-vec
            import struct

            if isinstance(entity.embedding, list):
                # Convert list to bytes for sqlite-vec
                # sqlite-vec uses float32 arrays
                embedding_blob = struct.pack(f"{len(entity.embedding)}f", *entity.embedding)

        cursor = self.conn.cursor()
        cursor.execute(
            """
            INSERT OR REPLACE INTO entities
            (id, entity_type, name, synonyms, abbreviations, embedding, created_at, source,
             umls_id, hgnc_id, rxnorm_id, uniprot_id, entity_json)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
            (
                entity.entity_id,
                entity.entity_type.value if hasattr(entity.entity_type, "value") else str(entity.entity_type),
                entity.name,
                json.dumps(entity.synonyms) if entity.synonyms else None,
                json.dumps(entity.abbreviations) if entity.abbreviations else None,
                embedding_blob,
                entity.created_at,
                entity.source,
                getattr(persistence, "umls_id", None),
                getattr(persistence, "hgnc_id", None),
                getattr(persistence, "rxnorm_id", None),
                getattr(persistence, "uniprot_id", None),
                entity.model_dump_json(),  # Store full JSON for reconstruction
            ),
        )
        self.conn.commit()

    def add_disease(self, entity: "Disease") -> None:
        """Add a disease entity to the collection."""
        self._add_entity(entity)

    def add_gene(self, entity: "Gene") -> None:
        """Add a gene entity to the collection."""
        self._add_entity(entity)

    def add_drug(self, entity: "Drug") -> None:
        """Add a drug entity to the collection."""
        self._add_entity(entity)

    def add_protein(self, entity: "Protein") -> None:
        """Add a protein entity to the collection."""
        self._add_entity(entity)

    def add_hypothesis(self, entity: "Hypothesis") -> None:
        """Add a hypothesis entity to the collection."""
        self._add_entity(entity)

    def add_study_design(self, entity: "StudyDesign") -> None:
        """Add a study design entity to the collection."""
        self._add_entity(entity)

    def add_statistical_method(self, entity: "StatisticalMethod") -> None:
        """Add a statistical method entity to the collection."""
        self._add_entity(entity)

    def add_evidence_line(self, entity: "EvidenceLine") -> None:
        """Add an evidence line entity to the collection."""
        self._add_entity(entity)

    def add_symptom(self, entity: "Symptom") -> None:
        """Add a symptom entity to the collection."""
        self._add_entity(entity)

    def add_procedure(self, entity: "Procedure") -> None:
        """Add a procedure entity to the collection."""
        self._add_entity(entity)

    def add_biomarker(self, entity: "Biomarker") -> None:
        """Add a biomarker entity to the collection."""
        self._add_entity(entity)

    def add_pathway(self, entity: "Pathway") -> None:
        """Add a pathway entity to the collection."""
        self._add_entity(entity)

    def get_by_id(self, entity_id: str) -> Optional[BaseMedicalEntity]:
        """Get entity by ID, searching across all types."""
        cursor = self.conn.cursor()
        cursor.execute("SELECT entity_json FROM entities WHERE id = ?", (entity_id,))
        row = cursor.fetchone()
        if row:
            # Use mapper to properly reconstruct the entity type
            # Create a temporary Entity persistence model and convert
            cursor.execute("SELECT id, entity_type, name, synonyms, abbreviations, embedding, created_at, source, umls_id, hgnc_id, rxnorm_id, uniprot_id FROM entities WHERE id = ?", (entity_id,))
            row = cursor.fetchone()
            if row:
                # Reconstruct Entity persistence model
                entity_dict = {
                    "id": row[0],
                    "entity_type": row[1],
                    "name": row[2],
                    "synonyms": json.loads(row[3]) if row[3] else [],
                    "abbreviations": json.loads(row[4]) if row[4] else [],
                    "embedding": json.loads(row[5]) if row[5] else None,
                    "created_at": row[6],
                    "source": row[7],
                    "umls_id": row[8],
                    "hgnc_id": row[9],
                    "rxnorm_id": row[10],
                    "uniprot_id": row[11],
                }
            # Filter out None values
            entity_dict = {k: v for k, v in entity_dict.items() if v is not None}
            # Ensure synonyms and abbreviations are JSON strings for mapper
            if "synonyms" in entity_dict and isinstance(entity_dict["synonyms"], list):
                entity_dict["synonyms"] = json.dumps(entity_dict["synonyms"])
            if "abbreviations" in entity_dict and isinstance(entity_dict["abbreviations"], list):
                entity_dict["abbreviations"] = json.dumps(entity_dict["abbreviations"])
            persistence = Entity(**entity_dict)
            return to_domain(persistence)
        return None

    def get_by_umls(self, umls_id: str) -> Optional["Disease"]:
        """Get disease by UMLS ID."""
        cursor = self.conn.cursor()
        cursor.execute("SELECT entity_json FROM entities WHERE umls_id = ? AND entity_type = 'disease'", (umls_id,))
        row = cursor.fetchone()
        if row:
            data = json.loads(row[0])
            from med_lit_schema.entity import Disease

            return Disease.model_validate(data)
        return None

    def get_by_hgnc(self, hgnc_id: str) -> Optional["Gene"]:
        """Get gene by HGNC ID."""
        cursor = self.conn.cursor()
        cursor.execute("SELECT entity_json FROM entities WHERE hgnc_id = ? AND entity_type = 'gene'", (hgnc_id,))
        row = cursor.fetchone()
        if row:
            data = json.loads(row[0])
            from med_lit_schema.entity import Gene

            return Gene.model_validate(data)
        return None

    def find_by_embedding(self, query_embedding: list[float], top_k: int = 5, threshold: float = 0.85) -> list[tuple[BaseMedicalEntity, float]]:
        """Find entities similar to query embedding using sqlite-vec."""
        if not query_embedding:
            return []

        try:
            # Use sqlite-vec for similarity search
            import struct

            # Convert query embedding to bytes
            query_bytes = struct.pack(f"{len(query_embedding)}f", *query_embedding)

            # Use sqlite-vec's distance function
            # Note: sqlite-vec provides vec_distance_cosine() function
            # The embedding column stores vectors in sqlite-vec format
            cursor = self.conn.cursor()
            cursor.execute(
                """
                SELECT
                    e.entity_json,
                    1.0 - vec_distance_cosine(e.embedding, ?) as similarity
                FROM entities e
                WHERE e.embedding IS NOT NULL
                ORDER BY similarity DESC
                LIMIT ?
                """,
                (query_bytes, top_k),
            )

            results = []
            for row in cursor.fetchall():
                similarity = float(row[1])
                if similarity >= threshold:
                    data = json.loads(row[0])
                    # Reconstruct entity from JSON
                    # This is simplified - full implementation would use mapper
                    entity = BaseMedicalEntity.model_validate(data)
                    results.append((entity, similarity))

            return results
        except sqlite3.OperationalError as e:
            # sqlite-vec not available or query failed
            print(f"Warning: Vector search failed: {e}")
            print("Falling back to simple embedding comparison")
            # Fallback: simple cosine similarity in Python
            return self._find_by_embedding_fallback(query_embedding, top_k, threshold)

    def _find_by_embedding_fallback(self, query_embedding: list[float], top_k: int = 5, threshold: float = 0.85) -> list[tuple[BaseMedicalEntity, float]]:
        """Fallback embedding search using Python cosine similarity."""
        import math

        cursor = self.conn.cursor()
        cursor.execute("SELECT entity_json, embedding FROM entities WHERE embedding IS NOT NULL")

        def cosine_similarity(a: list[float], b: list[float]) -> float:
            """Calculate cosine similarity between two vectors."""
            dot_product = sum(x * y for x, y in zip(a, b))
            norm_a = math.sqrt(sum(x * x for x in a))
            norm_b = math.sqrt(sum(x * x for x in b))
            if norm_a == 0 or norm_b == 0:
                return 0.0
            return dot_product / (norm_a * norm_b)

        results = []
        for row in cursor.fetchall():
            entity_json = row[0]
            embedding_json = row[1]
            if embedding_json:
                # Parse embedding from stored format
                import struct

                try:
                    # Try to parse as struct-packed bytes
                    embedding = list(struct.unpack(f"{len(query_embedding)}f", embedding_json))
                except (struct.error, TypeError):
                    # Fall back to JSON
                    embedding = json.loads(embedding_json) if isinstance(embedding_json, str) else embedding_json

                similarity = cosine_similarity(query_embedding, embedding)
                if similarity >= threshold:
                    data = json.loads(entity_json)
                    entity = BaseMedicalEntity.model_validate(data)
                    results.append((entity, similarity))

        # Sort by similarity and return top_k
        results.sort(key=lambda x: x[1], reverse=True)
        return results[:top_k]

    def list_entities(self, limit: Optional[int] = None, offset: int = 0) -> list[BaseMedicalEntity]:
        """List entities, optionally with pagination."""
        cursor = self.conn.cursor()

        # Build query with pagination
        query = "SELECT entity_json FROM entities"
        if limit is not None:
            query += f" LIMIT {limit} OFFSET {offset}"
        else:
            query += f" OFFSET {offset}"

        cursor.execute(query)
        results = []
        for row in cursor.fetchall():
            data = json.loads(row[0])
            entity = BaseMedicalEntity.model_validate(data)
            results.append(entity)

        return results

    @property
    def entity_count(self) -> int:
        """Total number of entities across all types."""
        cursor = self.conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM entities")
        return cursor.fetchone()[0]

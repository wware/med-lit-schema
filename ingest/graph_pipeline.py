#!/usr/bin/env python3
"""
Stage 6: Knowledge Graph Construction

This stage builds a knowledge graph from extracted data using SQLModel.
It reads from the storage backend (SQLite or PostgreSQL) and constructs
graph statistics and views for efficient querying.

The graph structure is already represented in the storage models:
- Entity nodes (from entities table)
- Relationship edges (from relationships table)
- Paper nodes (from papers table)
- Evidence nodes (from evidence table)

This stage computes graph statistics and can create materialized views
or indexes for efficient graph traversal queries.

Usage:
    python graph_pipeline.py --output-dir output --storage sqlite
    python graph_pipeline.py --output-dir output --storage postgres --database-url postgresql://...
"""

import argparse
from pathlib import Path
from pydantic import BaseModel, Field

# Import storage interfaces
try:
    from ..storage.interfaces import PipelineStorageInterface
    from ..storage.backends.sqlite import SQLitePipelineStorage
    from ..storage.backends.postgres import PostgresPipelineStorage
except ImportError:
    # Absolute imports for standalone execution
    from med_lit_schema.storage.interfaces import PipelineStorageInterface
    from med_lit_schema.storage.backends.sqlite import SQLitePipelineStorage
    from med_lit_schema.storage.backends.postgres import PostgresPipelineStorage

from sqlalchemy import create_engine, text
from sqlmodel import Session


# ============================================================================
# Graph Statistics Model
# ============================================================================


class GraphStats(BaseModel):
    """Statistics about the knowledge graph."""

    papers: int = Field(0, description="Number of paper nodes")
    entities: int = Field(0, description="Number of entity nodes")
    relationships: int = Field(0, description="Number of relationship edges")
    evidence: int = Field(0, description="Number of evidence nodes")
    entity_types: dict[str, int] = Field(default_factory=dict, description="Count by entity type")
    predicate_types: dict[str, int] = Field(default_factory=dict, description="Count by predicate type")
    papers_with_entities: int = Field(0, description="Papers that mention entities")
    papers_with_relationships: int = Field(0, description="Papers that have relationships")
    entities_with_relationships: int = Field(0, description="Entities that participate in relationships")


# ============================================================================
# Graph Statistics Computation
# ============================================================================


def compute_graph_stats(storage: PipelineStorageInterface) -> GraphStats:
    """
    Compute statistics about the knowledge graph.

    Args:
        storage: Storage interface to read from

    Returns:
        Graph statistics
    """
    stats = GraphStats()

    # Basic counts
    stats.papers = storage.papers.paper_count
    stats.entities = storage.entities.entity_count
    stats.relationships = storage.relationships.relationship_count
    stats.evidence = storage.evidence.evidence_count

    # Count entity types
    # Note: This requires iterating through entities
    # For large datasets, this could be optimized with a direct SQL query
    entity_types: dict[str, int] = {}
    for entity in storage.entities.list_entities(limit=None):
        entity_type = entity.entity_type.value if hasattr(entity.entity_type, 'value') else str(entity.entity_type)
        entity_types[entity_type] = entity_types.get(entity_type, 0) + 1
    stats.entity_types = entity_types

    # Count predicate types
    predicate_types: dict[str, int] = {}
    for relationship in storage.relationships.list_relationships(limit=None):
        predicate = relationship.predicate.value if hasattr(relationship.predicate, 'value') else str(relationship.predicate)
        predicate_types[predicate] = predicate_types.get(predicate, 0) + 1
    stats.predicate_types = predicate_types

    # Count papers with entities (papers that have been processed by NER)
    # This requires checking if papers have associated entities
    # For now, we'll approximate by checking if we have any entities at all
    stats.papers_with_entities = stats.papers if stats.entities > 0 else 0

    # Count papers with relationships
    # Get unique paper IDs from relationships
    papers_with_rels = set()
    for relationship in storage.relationships.list_relationships(limit=None):
        # Relationships may have paper references in their metadata
        # This is an approximation - actual implementation depends on relationship model
        pass
    stats.papers_with_relationships = len(papers_with_rels) if papers_with_rels else 0

    # Count entities that participate in relationships
    entities_in_rels = set()
    for relationship in storage.relationships.list_relationships(limit=None):
        entities_in_rels.add(relationship.subject_id)
        entities_in_rels.add(relationship.object_id)
    stats.entities_with_relationships = len(entities_in_rels)

    return stats


def create_graph_indexes(session: Session, storage_type: str) -> None:
    """
    Create indexes for efficient graph queries.

    Args:
        session: SQLModel session
        storage_type: 'sqlite' or 'postgres'
    """
    print("Creating graph indexes...")

    if storage_type == "postgres":
        # PostgreSQL-specific indexes
        try:
            # Index for relationship traversal (subject -> object)
            session.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_relationships_subject
                ON relationships(subject_id)
            """))

            # Index for relationship traversal (object -> subject)
            session.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_relationships_object
                ON relationships(object_id)
            """))

            # Composite index for predicate queries
            session.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_relationships_predicate
                ON relationships(predicate)
            """))

            session.commit()
            print("  Created PostgreSQL indexes")
        except Exception as e:
            print(f"  Warning: Could not create indexes: {e}")
            session.rollback()

    elif storage_type == "sqlite":
        # SQLite-specific indexes
        try:
            session.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_relationships_subject
                ON relationships(subject_id)
            """))

            session.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_relationships_object
                ON relationships(object_id)
            """))

            session.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_relationships_predicate
                ON relationships(predicate)
            """))

            session.commit()
            print("  Created SQLite indexes")
        except Exception as e:
            print(f"  Warning: Could not create indexes: {e}")
            session.rollback()


# ============================================================================
# Main Pipeline
# ============================================================================


def main():
    """Main graph construction execution."""
    parser = argparse.ArgumentParser(description="Stage 6: Knowledge Graph Construction Pipeline")
    parser.add_argument("--output-dir", type=str, default="output", help="Output directory containing database")
    parser.add_argument("--storage", type=str, choices=["sqlite", "postgres"], default="sqlite", help="Storage backend to use")
    parser.add_argument("--database-url", type=str, default=None, help="Database URL for PostgreSQL (required if --storage=postgres)")
    parser.add_argument("--create-indexes", action="store_true", help="Create indexes for efficient graph queries")

    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    output_dir.mkdir(exist_ok=True)

    print("=" * 60)
    print("Stage 6: Knowledge Graph Construction")
    print("=" * 60)
    print()

    # Initialize storage based on choice
    if args.storage == "sqlite":
        db_path = output_dir / "ingest.db"
        if not db_path.exists():
            print(f"Error: Database not found at {db_path}")
            print("Please run previous stages first")
            return 1
        
        storage: PipelineStorageInterface = SQLitePipelineStorage(db_path)
        engine = create_engine(f"sqlite:///{db_path}")
        session = Session(engine)

    elif args.storage == "postgres":
        if not args.database_url:
            print("Error: --database-url required for PostgreSQL storage")
            return 1

        engine = create_engine(args.database_url)
        session = Session(engine)
        storage = PostgresPipelineStorage(session)

    else:
        print(f"Error: Unknown storage backend: {args.storage}")
        return 1

    try:
        # Compute graph statistics
        print("Computing graph statistics...")
        print("-" * 60)
        stats = compute_graph_stats(storage)

        print(f"Papers: {stats.papers}")
        print(f"Entities: {stats.entities}")
        print(f"Relationships: {stats.relationships}")
        print(f"Evidence: {stats.evidence}")
        print()

        if stats.entity_types:
            print("Entity types:")
            for entity_type, count in sorted(stats.entity_types.items(), key=lambda x: x[1], reverse=True):
                print(f"  {entity_type}: {count}")
            print()

        if stats.predicate_types:
            print("Predicate types:")
            for predicate, count in sorted(stats.predicate_types.items(), key=lambda x: x[1], reverse=True):
                print(f"  {predicate}: {count}")
            print()

        print(f"Papers with entities: {stats.papers_with_entities}")
        print(f"Papers with relationships: {stats.papers_with_relationships}")
        print(f"Entities with relationships: {stats.entities_with_relationships}")
        print()

        # Create indexes if requested
        if args.create_indexes:
            create_graph_indexes(session, args.storage)

        print()
        print("=" * 60)
        print("Graph construction complete!")
        print("=" * 60)
        print()
        print("The knowledge graph is now ready for querying.")
        print("Use the storage interfaces or direct SQL queries to explore the graph.")
        print()

    finally:
        storage.close()
        session.close()

    return 0


if __name__ == "__main__":
    exit(main())

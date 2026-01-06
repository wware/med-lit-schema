"""
Database setup script for Medical Knowledge Graph.

This script:
1. Enables required PostgreSQL extensions (uuid-ossp, pgvector)
2. Creates all tables from SQLModel definitions
3. Creates the update_updated_at trigger function
4. Applies triggers to entities and relationships tables
5. Creates pgvector HNSW index for embeddings

Usage:
    python setup_database.py --database-url postgresql://user:pass@localhost/dbname
"""

import argparse
from sqlalchemy import create_engine, text
from sqlmodel import SQLModel

# Import all SQLModel classes so they register with SQLModel.metadata
# Note: Only import models that are actually used/needed
from med_lit_schema.entity_sqlmodel import Entity  # noqa: F401
from med_lit_schema.relationship_sqlmodel import Relationship  # noqa: F401
# Paper and Evidence models have issues and aren't currently used in main tables
# from med_lit_schema.paper_sqlmodel import Paper  # noqa: F401
# from med_lit_schema.evidence_sqlmodel import Evidence  # noqa: F401


def create_extensions(engine):
    """Enable required PostgreSQL extensions."""
    print("Creating PostgreSQL extensions...")
    with engine.connect() as conn:
        # UUID generation
        conn.execute(text('CREATE EXTENSION IF NOT EXISTS "uuid-ossp"'))

        # pgvector for semantic search
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))

        conn.commit()
    print("✓ Extensions created")


def create_trigger_function(engine):
    """Create trigger function for auto-updating updated_at timestamps."""
    print("Creating trigger function...")
    with engine.connect() as conn:
        conn.execute(
            text(
                """
            CREATE OR REPLACE FUNCTION update_updated_at_column()
            RETURNS TRIGGER AS $$
            BEGIN
                NEW.updated_at = CURRENT_TIMESTAMP;
                RETURN NEW;
            END;
            $$ language 'plpgsql'
        """
            )
        )
        conn.commit()
    print("✓ Trigger function created")


def create_triggers(engine):
    """Apply update triggers to tables with updated_at columns."""
    print("Creating triggers...")
    with engine.connect() as conn:
        # Trigger for entities
        conn.execute(
            text(
                """
            DROP TRIGGER IF EXISTS update_entities_updated_at ON entities
        """
            )
        )
        conn.execute(
            text(
                """
            CREATE TRIGGER update_entities_updated_at
                BEFORE UPDATE ON entities
                FOR EACH ROW
                EXECUTE FUNCTION update_updated_at_column()
        """
            )
        )

        # Trigger for relationships
        conn.execute(
            text(
                """
            DROP TRIGGER IF EXISTS update_relationships_updated_at ON relationships
        """
            )
        )
        conn.execute(
            text(
                """
            CREATE TRIGGER update_relationships_updated_at
                BEFORE UPDATE ON relationships
                FOR EACH ROW
                EXECUTE FUNCTION update_updated_at_column()
        """
            )
        )

        conn.commit()
    print("✓ Triggers created")


def create_vector_index(engine):
    """Create HNSW index for vector similarity search on embeddings.

    Note: This assumes embeddings are stored as vector(768).
    You may need to adjust the dimension if using different embedding models.
    """
    print("Creating vector index (this may take a while on large tables)...")
    with engine.connect() as conn:
        # First, ensure the embedding column is cast to vector type
        # This ALTER TABLE is idempotent - safe to run multiple times
        try:
            conn.execute(
                text(
                    """
                ALTER TABLE entities
                ALTER COLUMN embedding TYPE vector(768)
                USING embedding::vector(768)
            """
                )
            )
        except Exception as e:
            print(f"  Note: Could not alter embedding column type: {e}")
            print("  This is expected if the column is already vector(768)")

        # Create the HNSW index for fast cosine similarity search
        conn.execute(
            text(
                """
            CREATE INDEX IF NOT EXISTS idx_entities_embedding
            ON entities
            USING hnsw (embedding vector_cosine_ops)
        """
            )
        )

        conn.commit()
    print("✓ Vector index created")


def setup_database(database_url: str, skip_vector_index: bool = False):
    """Complete database setup."""
    print(f"Setting up database: {database_url}")

    # Create engine
    engine = create_engine(database_url, echo=False)

    # 1. Create extensions
    create_extensions(engine)

    # 2. Create all tables from SQLModel definitions
    print("Creating tables...")
    SQLModel.metadata.create_all(engine)
    print("✓ Tables created")

    # 3. Create trigger function
    create_trigger_function(engine)

    # 4. Apply triggers
    create_triggers(engine)

    # 5. Ensure embedding column is vector type (needed for vector operations)
    print("Setting embedding column type to vector(768)...")
    with engine.connect() as conn:
        # Drop and recreate as vector type (simpler than trying to convert)
        try:
            conn.execute(text("ALTER TABLE entities DROP COLUMN IF EXISTS embedding"))
            conn.execute(text("ALTER TABLE entities ADD COLUMN embedding vector(768)"))
            conn.commit()
            print("✓ Embedding column set to vector(768)")
        except Exception as e:
            print(f"  Warning: Could not set embedding column type: {e}")
            print("  Vector operations may not work correctly")

    # 6. Create vector index (optional, can be slow on large tables)
    if not skip_vector_index:
        create_vector_index(engine)
    else:
        print("Skipping vector index creation (use --create-vector-index to enable)")

    print("\n✅ Database setup complete!")


def main():
    parser = argparse.ArgumentParser(description="Set up Medical Knowledge Graph database")
    parser.add_argument("--database-url", required=True, help="PostgreSQL database URL (e.g., postgresql://user:pass@localhost/dbname)")
    parser.add_argument("--skip-vector-index", action="store_true", help="Skip creating vector index (useful for development or if embeddings aren't populated yet)")

    args = parser.parse_args()
    setup_database(args.database_url, skip_vector_index=args.skip_vector_index)


if __name__ == "__main__":
    main()

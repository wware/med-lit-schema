"""
Storage backend implementations.

This package contains concrete implementations of storage interfaces for
different database backends.

Available Backends:

- **sqlite**: SQLite implementation for testing and development
- **postgres**: PostgreSQL+pgvector implementation for production
- **sqlite_entity_collection**: SQLite-based entity collection

Example:

    >>> from storage.backends.sqlite import SQLitePipelineStorage
    >>> storage = SQLitePipelineStorage("my_database.db")

    >>> from storage.backends.postgres import PostgresPipelineStorage
    >>> storage = PostgresPipelineStorage("postgresql://user:pass@localhost/db")

For detailed backend comparison and usage, see backends/README.md.
"""

__all__ = [
    "sqlite",
    "postgres",
    "sqlite_entity_collection",
]

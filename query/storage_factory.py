"""
Storage factory for creating and managing storage backend instances.

This module provides a singleton pattern for accessing the storage backend,
ensuring that a single connection pool is used throughout the application.
"""

import os
from typing import Optional

from storage.backends.postgres import PostgresPipelineStorage
from storage.interfaces import PipelineStorageInterface

_storage_instance: Optional[PipelineStorageInterface] = None


def get_storage() -> PipelineStorageInterface:
    """
    Returns a singleton instance of the storage backend.

    Initializes the storage on first call. Reads the DATABASE_URL
    from environment variables.
    """
    global _storage_instance
    if _storage_instance is None:
        db_url = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/medlit")
        if not db_url:
            raise ValueError("DATABASE_URL environment variable is not set.")
        _storage_instance = PostgresPipelineStorage(database_url=db_url)
    return _storage_instance


def close_storage():
    """
    Closes the storage connection if it exists.
    """
    global _storage_instance
    if _storage_instance:
        _storage_instance.close()
        _storage_instance = None

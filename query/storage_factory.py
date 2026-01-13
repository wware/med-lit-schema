"""
Storage factory for creating and managing storage backend instances.
"""

import os
from typing import Generator
from sqlalchemy import create_engine
from sqlmodel import Session
from storage.backends.postgres import PostgresPipelineStorage
from storage.interfaces import PipelineStorageInterface

# Singleton engine
_engine = None


def get_engine():
    """
    Returns a singleton instance of the SQLAlchemy engine.
    """
    global _engine
    if _engine is None:
        db_url = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/medlit")
        if not db_url:
            raise ValueError("DATABASE_URL environment variable is not set.")
        _engine = create_engine(db_url)
    return _engine


def get_storage() -> Generator[PipelineStorageInterface, None, None]:
    """
    FastAPI dependency that provides a storage instance with a request-scoped session.
    """
    engine = get_engine()
    with Session(engine) as session:
        try:
            storage = PostgresPipelineStorage(session)
            yield storage
            session.commit()
        except Exception:
            session.rollback()
            raise


def close_storage():
    """
    Closes the engine connection.
    """
    global _engine
    if _engine:
        _engine.dispose()
        _engine = None

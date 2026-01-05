from datetime import datetime
from typing import Dict, Optional
from uuid import UUID, uuid4

from sqlalchemy import Column
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import Field, SQLModel


class Evidence(SQLModel, table=True):
    """
    Persistence model for evidence supporting relationships.
    Matches the 'evidence' table in migration.sql.
    """

    __tablename__ = "evidence"

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    relationship_id: UUID = Field(index=True)
    paper_id: str = Field(index=True)
    section: Optional[str] = None
    text_span: Optional[str] = None
    confidence: Optional[float] = Field(default=0.0)

    # Store metadata as JSONB
    metadata_: Optional[Dict] = Field(default=None, sa_column=Column("metadata", JSONB))

    created_at: datetime = Field(default_factory=datetime.utcnow)

from sqlmodel import Field, SQLModel, Column
from datetime import datetime
from typing import Optional
from sqlalchemy import text, DateTime
from sqlalchemy.dialects.postgresql import JSONB


class Paper(SQLModel, table=True):
    __tablename__ = "papers"

    # Changed ID type from Optional[int] to str to match PMC IDs
    id: str = Field(primary_key=True, description="Canonical paper ID (e.g. PMC ID)")
    title: str = Field(index=True)
    authors: Optional[str] = None  # Assuming authors might not always be available
    abstract: Optional[str] = None
    publication_date: Optional[str] = None  # Changed to str as LLM extracts it as string
    journal: Optional[str] = None
    doi: Optional[str] = Field(default=None, index=True)
    pubmed_id: Optional[str] = Field(default=None, index=True)
    entity_count: int = Field(default=0)  # Changed to int, default 0
    relationship_count: int = Field(default=0)  # Changed to int, default 0

    # Store extraction provenance as JSONB
    extraction_provenance_json: Optional[dict] = Field(default=None, sa_column=Column(JSONB, nullable=True))
    # Store paper metadata as JSONB
    metadata_json: Optional[dict] = Field(default=None, sa_column=Column(JSONB, nullable=True))

    created_at: datetime = Field(default_factory=datetime.utcnow, sa_column=Column(DateTime(timezone=False), nullable=False, server_default=text("CURRENT_TIMESTAMP")))
    updated_at: datetime = Field(
        default_factory=datetime.utcnow, sa_column=Column(DateTime(timezone=False), nullable=False, server_default=text("CURRENT_TIMESTAMP"), onupdate=text("CURRENT_TIMESTAMP"))
    )

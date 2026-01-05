from datetime import date, datetime
from typing import List, Optional

from sqlalchemy import Column, String
from sqlalchemy.dialects.postgresql import ARRAY
from sqlmodel import Field, SQLModel


class Paper(SQLModel, table=True):
    """
    Persistence model for research papers.
    Matches the 'papers' table in migration.sql.
    """

    __tablename__ = "papers"

    id: str = Field(primary_key=True, description="PMC ID or DOI")
    title: str
    abstract: Optional[str] = None

    # Store authors as Postgres ARRAY
    authors: Optional[List[str]] = Field(default=None, sa_column=Column(ARRAY(String)))

    publication_date: Optional[date] = None
    journal: Optional[str] = None
    entity_count: int = Field(default=0)
    relationship_count: int = Field(default=0)
    created_at: datetime = Field(default_factory=datetime.utcnow)

from sqlmodel import Field, SQLModel
from datetime import datetime
from typing import Optional
from sqlalchemy import text


class Paper(SQLModel, table=True):
    __tablename__ = "papers"

    id: Optional[int] = Field(default=None, primary_key=True)
    title: str = Field(index=True)
    authors: str
    abstract: Optional[str] = None
    publication_date: Optional[datetime] = None
    journal: Optional[str] = None
    doi: Optional[str] = Field(default=None, index=True)
    pubmed_id: Optional[str] = Field(default=None, index=True)
    created_at: datetime = Field(default_factory=datetime.utcnow, server_default=text("CURRENT_TIMESTAMP"), nullable=False)
    updated_at: Optional[datetime] = None

from sqlalchemy import DateTime, Column, ForeignKey, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import Field, SQLModel
from typing import Optional, Dict, Any
from datetime import datetime


class Evidence(SQLModel, table=True):
    __tablename__ = "evidence"

    id: Optional[int] = Field(default=None, primary_key=True)

    # Foreign key with CASCADE delete for relationship_id
    relationship_id: int = Field(sa_column=Column("relationship_id", ForeignKey("relationships.id", ondelete="CASCADE"), nullable=False))

    # Foreign key with CASCADE delete for paper_id
    paper_id: int = Field(sa_column=Column("paper_id", ForeignKey("papers.id", ondelete="CASCADE"), nullable=False))

    evidence_type: str = Field(max_length=50)
    confidence_score: Optional[float] = Field(default=None)

    # JSONB field with server_default
    metadata_: Dict[str, Any] = Field(default_factory=dict, sa_column=Column("metadata_", JSONB, server_default=text("'{}'::jsonb"), nullable=False))

    # Timestamp with server_default
    created_at: datetime = Field(sa_column=Column("created_at", DateTime, server_default=text("CURRENT_TIMESTAMP"), nullable=False))

    # Relationships (if needed)
    # relationship: Optional["Relationship"] = Relationship(back_populates="evidence")
    # paper: Optional["Paper"] = Relationship(back_populates="evidence")

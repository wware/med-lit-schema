"""
SQLModel-based relationship schema with single table inheritance.

This module defines the Persistence Models for relationships, mapping the rich
Domain Models from `med_lit_schema/relationship.py` to a flattened database structure.
"""

from datetime import datetime
from typing import Optional
from uuid import UUID, uuid4

from sqlmodel import Field, SQLModel, UniqueConstraint


class Relationship(SQLModel, table=True):
    """
    Base relationship table with single table inheritance.
    All relationship types are stored in this single table.
    """

    __tablename__ = "relationships"
    __table_args__ = (UniqueConstraint("subject_id", "object_id", "predicate", name="uq_relationship"),)  # Add this line

    # Core fields
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    subject_id: str = Field(index=True)
    object_id: str = Field(index=True)
    predicate: str = Field(index=True)

    # Common medical relationship fields
    confidence: Optional[float] = Field(default=None)
    source_papers: Optional[str] = Field(default=None)
    evidence_count: Optional[int] = Field(default=None)

    # Type-specific fields
    frequency: Optional[str] = Field(default=None)
    onset: Optional[str] = Field(default=None)
    severity: Optional[str] = Field(default=None)
    efficacy: Optional[str] = Field(default=None)
    response_rate: Optional[float] = Field(default=None)
    line_of_therapy: Optional[str] = Field(default=None)
    indication: Optional[str] = Field(default=None)
    risk_ratio: Optional[float] = Field(default=None)
    penetrance: Optional[float] = Field(default=None)
    age_of_onset: Optional[str] = Field(default=None)
    population: Optional[str] = Field(default=None)
    association_type: Optional[str] = Field(default=None)
    strength: Optional[str] = Field(default=None)
    statistical_significance: Optional[float] = Field(default=None)
    interaction_type: Optional[str] = Field(default=None)
    mechanism: Optional[str] = Field(default=None)
    clinical_significance: Optional[str] = Field(default=None)
    transcript_variants: Optional[int] = Field(default=None)
    tissue_specificity: Optional[str] = Field(default=None)
    role: Optional[str] = Field(default=None)
    regulatory_effect: Optional[str] = Field(default=None)
    reason: Optional[str] = Field(default=None)
    sensitivity: Optional[float] = Field(default=None)
    specificity: Optional[float] = Field(default=None)
    standard_of_care: Optional[bool] = Field(default=None)
    reversible: Optional[bool] = Field(default=None)
    context: Optional[str] = Field(default=None)
    sentiment: Optional[str] = Field(default=None)
    position: Optional[str] = Field(default=None)
    publication_type: Optional[str] = Field(default=None)
    prediction_type: Optional[str] = Field(default=None)
    conditions: Optional[str] = Field(default=None)
    testable: Optional[bool] = Field(default=None)
    refutation_strength: Optional[str] = Field(default=None)
    alternative_explanation: Optional[str] = Field(default=None)
    limitations: Optional[str] = Field(default=None)
    test_outcome: Optional[str] = Field(default=None)
    methodology: Optional[str] = Field(default=None)
    study_design_id: Optional[str] = Field(default=None)
    evidence_type: Optional[str] = Field(default=None)
    eco_type: Optional[str] = Field(default=None)
    quality_score: Optional[float] = Field(default=None)

    # Metadata
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

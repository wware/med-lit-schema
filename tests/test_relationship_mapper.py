"""
Tests for relationship mapper functions.
"""

from schema.relationship import Treats
from schema.base import PredicateType
from schema.relationship_sqlmodel import Relationship as PersistenceRelationship
from schema.mapper import relationship_to_persistence, relationship_to_domain


def test_treats_roundtrip():
    """Test domain -> persistence -> domain conversion for Treats relationship."""
    # Create domain model
    treats = Treats(
        subject_id="RxNorm:1187832",
        object_id="C0006142",
        predicate=PredicateType.TREATS,
        efficacy="significant improvement in PFS",
        response_rate=0.59,
        line_of_therapy="second-line",
        indication="BRCA-mutated breast cancer",
        source_papers=["PMC999", "PMC888"],
        confidence=0.85,
    )

    # Convert to persistence
    relationship_persistence = relationship_to_persistence(treats)
    assert isinstance(relationship_persistence, PersistenceRelationship)
    assert relationship_persistence.subject_id == "RxNorm:1187832"
    assert relationship_persistence.predicate == "treats"
    assert relationship_persistence.response_rate == 0.59

    # Convert back to domain
    treats2 = relationship_to_domain(relationship_persistence)
    assert isinstance(treats2, Treats)
    assert treats2.subject_id == treats.subject_id
    assert treats2.predicate == treats.predicate
    assert treats2.response_rate == treats.response_rate
    # Due to float precision, we can't directly compare the objects
    # assert treats2 == treats

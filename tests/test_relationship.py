from med_lit_schema.relationship import (
    create_relationship,
    PredicateType,
    Treats,
    Causes,
    Cites,
)


def test_create_relationship_returns_typed_class():
    rel = create_relationship(
        PredicateType.TREATS,
        subject_id="RxNorm:1",
        object_id="C0",
        response_rate=0.5,
        source_papers=["PMC1"],
    )
    assert isinstance(rel, Treats)
    assert rel.subject_id == "RxNorm:1"
    assert rel.object_id == "C0"
    assert rel.confidence >= 0.0
    assert "PMC1" in rel.source_papers


def test_create_causes_and_cites():
    c = create_relationship(PredicateType.CAUSES, subject_id="C1", object_id="S1", frequency="often")
    assert isinstance(c, Causes)
    cites = create_relationship(PredicateType.CITES, subject_id="P1", object_id="P2", context="discussion")
    assert isinstance(cites, Cites)
    assert cites.predicate == PredicateType.CITES

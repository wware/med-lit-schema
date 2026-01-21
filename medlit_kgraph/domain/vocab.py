"""Vocabulary and validation for medical literature domain.

Defines valid predicates and their constraints (which entity types
can participate in which relationships).
"""

# Valid predicate strings (matching med-lit-schema's PredicateType enum)
PREDICATE_TREATS = "treats"
PREDICATE_CAUSES = "causes"
PREDICATE_INCREASES_RISK = "increases_risk"
PREDICATE_DECREASES_RISK = "decreases_risk"
PREDICATE_ASSOCIATED_WITH = "associated_with"
PREDICATE_INTERACTS_WITH = "interacts_with"
PREDICATE_DIAGNOSED_BY = "diagnosed_by"
PREDICATE_SIDE_EFFECT = "side_effect"
PREDICATE_ENCODES = "encodes"
PREDICATE_PARTICIPATES_IN = "participates_in"
PREDICATE_CONTRAINDICATED_FOR = "contraindicated_for"
PREDICATE_PREVENTS = "prevents"
PREDICATE_MANAGES = "manages"
PREDICATE_BINDS_TO = "binds_to"
PREDICATE_INHIBITS = "inhibits"
PREDICATE_ACTIVATES = "activates"
PREDICATE_UPREGULATES = "upregulates"
PREDICATE_DOWNREGULATES = "downregulates"
PREDICATE_METABOLIZES = "metabolizes"
PREDICATE_DIAGNOSES = "diagnoses"
PREDICATE_INDICATES = "indicates"
PREDICATE_PRECEDES = "precedes"
PREDICATE_CO_OCCURS_WITH = "co_occurs_with"
PREDICATE_LOCATED_IN = "located_in"
PREDICATE_AFFECTS = "affects"
PREDICATE_SUPPORTS = "supports"

# Research metadata predicates (less common, but included for completeness)
PREDICATE_CITES = "cites"
PREDICATE_STUDIED_IN = "studied_in"
PREDICATE_AUTHORED_BY = "authored_by"
PREDICATE_PART_OF = "part_of"
PREDICATE_PREDICTS = "predicts"
PREDICATE_REFUTES = "refutes"
PREDICATE_TESTED_BY = "tested_by"
PREDICATE_GENERATES = "generates"

# All valid predicates
ALL_PREDICATES = {
    PREDICATE_TREATS,
    PREDICATE_CAUSES,
    PREDICATE_INCREASES_RISK,
    PREDICATE_DECREASES_RISK,
    PREDICATE_ASSOCIATED_WITH,
    PREDICATE_INTERACTS_WITH,
    PREDICATE_DIAGNOSED_BY,
    PREDICATE_SIDE_EFFECT,
    PREDICATE_ENCODES,
    PREDICATE_PARTICIPATES_IN,
    PREDICATE_CONTRAINDICATED_FOR,
    PREDICATE_PREVENTS,
    PREDICATE_MANAGES,
    PREDICATE_BINDS_TO,
    PREDICATE_INHIBITS,
    PREDICATE_ACTIVATES,
    PREDICATE_UPREGULATES,
    PREDICATE_DOWNREGULATES,
    PREDICATE_METABOLIZES,
    PREDICATE_DIAGNOSES,
    PREDICATE_INDICATES,
    PREDICATE_PRECEDES,
    PREDICATE_CO_OCCURS_WITH,
    PREDICATE_LOCATED_IN,
    PREDICATE_AFFECTS,
    PREDICATE_SUPPORTS,
    PREDICATE_CITES,
    PREDICATE_STUDIED_IN,
    PREDICATE_AUTHORED_BY,
    PREDICATE_PART_OF,
    PREDICATE_PREDICTS,
    PREDICATE_REFUTES,
    PREDICATE_TESTED_BY,
    PREDICATE_GENERATES,
}


def get_valid_predicates(subject_type: str, object_type: str) -> list[str]:
    """Return predicates valid between two entity types.

    This implements domain-specific constraints. For example:
    - Drug → Disease: TREATS, PREVENTS, CONTRAINDICATED_FOR, SIDE_EFFECT
    - Gene → Disease: INCREASES_RISK, DECREASES_RISK, ASSOCIATED_WITH
    - Gene → Protein: ENCODES
    - Drug → Drug: INTERACTS_WITH
    - Disease → Symptom: CAUSES
    - Disease → Procedure: DIAGNOSED_BY

    Args:
        subject_type: The entity type of the relationship subject.
        object_type: The entity type of the relationship object.

    Returns:
        List of predicate names that are valid for this entity type pair.
    """
    # Drug → Disease relationships
    if subject_type == "drug" and object_type == "disease":
        return [
            PREDICATE_TREATS,
            PREDICATE_PREVENTS,
            PREDICATE_MANAGES,
            PREDICATE_CONTRAINDICATED_FOR,
        ]

    # Disease → Symptom relationships
    if subject_type == "disease" and object_type == "symptom":
        return [PREDICATE_CAUSES]

    # Drug → Symptom relationships
    if subject_type == "drug" and object_type == "symptom":
        return [PREDICATE_SIDE_EFFECT]

    # Gene → Disease relationships
    if subject_type == "gene" and object_type == "disease":
        return [
            PREDICATE_INCREASES_RISK,
            PREDICATE_DECREASES_RISK,
            PREDICATE_ASSOCIATED_WITH,
        ]

    # Gene → Protein relationships
    if subject_type == "gene" and object_type == "protein":
        return [PREDICATE_ENCODES]

    # Drug → Drug relationships
    if subject_type == "drug" and object_type == "drug":
        return [PREDICATE_INTERACTS_WITH]

    # Disease → Procedure/Biomarker relationships
    if subject_type == "disease" and object_type in ("procedure", "biomarker"):
        return [PREDICATE_DIAGNOSED_BY]

    # Gene/Protein → Pathway relationships
    if subject_type in ("gene", "protein") and object_type == "pathway":
        return [PREDICATE_PARTICIPATES_IN]

    # General associations (many entity type pairs)
    if subject_type != object_type:  # No self-loops for ASSOCIATED_WITH
        return [PREDICATE_ASSOCIATED_WITH]

    # If no specific rules match, return empty list (no predicates valid)
    return []

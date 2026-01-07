import uuid
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field

# TODO - define these here

# ============================================================================
# Predicate Types
# ============================================================================


class PredicateType(str, Enum):
    AUTHORED_BY = "authored_by"
    CITES = "cites"
    CITED_BY = "cited_by"
    CONTRADICTS = "contradicts"
    REFUTES = "refutes"
    STUDIED_IN = "studied_in"
    PREDICTS = "predicts"
    TESTED_BY = "tested_by"
    PART_OF = "part_of"
    GENERATES = "generates"
    CAUSES = "causes"
    PREVENTS = "prevents"
    INCREASES_RISK = "increases_risk"
    DECREASES_RISK = "decreases_risk"
    TREATS = "treats"
    MANAGES = "manages"
    CONTRAINDICATED_FOR = "contraindicated_for"
    SIDE_EFFECT = "side_effect"
    BINDS_TO = "binds_to"
    INHIBITS = "inhibits"
    ACTIVATES = "activates"
    UPREGULATES = "upregulates"
    DOWNREGULATES = "downregulates"
    ENCODES = "encodes"
    METABOLIZES = "metabolizes"
    PARTICIPATES_IN = "participates_in"
    DIAGNOSES = "diagnoses"
    DIAGNOSED_BY = "diagnosed_by"
    INDICATES = "indicates"
    PRECEDES = "precedes"
    CO_OCCURS_WITH = "co_occurs_with"
    ASSOCIATED_WITH = "associated_with"
    INTERACTS_WITH = "interacts_with"
    LOCATED_IN = "located_in"
    AFFECTS = "affects"
    SUPPORTS = "supports"


class ClaimPredicate(BaseModel):
    """
    Describes the nature of a claim made in a paper.
    """

    predicate_type: PredicateType = Field(..., description="The type of relationship asserted in the claim.")
    description: str = Field(..., description="A natural language description of the predicate as it appears in the text.")


class Provenance(BaseModel):
    """
    Information about the origin of a piece of data.
    """

    source_type: str = Field(..., description="The type of source (e.g., 'paper', 'database', 'model_extraction').")
    source_id: str = Field(..., description="An identifier for the source (e.g., a DOI for a paper, a database record ID).")
    source_version: Optional[str] = Field(None, description="The version of the source, if applicable.")
    notes: Optional[str] = Field(None, description="Additional notes about the provenance.")


PaperId = uuid.UUID
EdgeId = uuid.UUID


class Polarity(Enum):
    # supports / refutes / neutral
    SUPPORTS = "supports"
    REFUTES = "refutes"
    NEUTRAL = "neutral"


class EvidenceType(BaseModel):
    """
    The type of evidence supporting a relationship, potentially linked to an ontology.
    """

    ontology_id: str = Field(..., description="Identifier from an evidence ontology (e.g., SEPIO, Evidence & Conclusion Ontology).")
    ontology_label: str = Field(..., description="Human-readable label for the ontology term.")
    description: Optional[str] = Field(None, description="A fuller description of the evidence type.")


class ModelInfo(BaseModel):
    """
    Information about a model used in extraction.

    Allows comparing extraction quality across different LLMs and versions.
    """

    name: str = Field(..., description="Model name/identifier")
    provider: str = Field(..., description="Model provider (e.g., 'ollama', 'anthropic')")
    temperature: Optional[float] = Field(None, description="Temperature parameter if applicable")
    version: Optional[str] = Field(None, description="Model version if known")


# ============================================================================
# Entity Type Enumeration
# ============================================================================


class EntityType(str, Enum):
    """
    All possible entity types in the knowledge graph.

    This enum provides type safety for entity categorization and enables
    validation of entity-relationship compatibility.
    """

    # Core medical entities
    DISEASE = "disease"
    SYMPTOM = "symptom"
    DRUG = "drug"
    GENE = "gene"
    MUTATION = "mutation"
    PROTEIN = "protein"
    PATHWAY = "pathway"
    ANATOMICAL_STRUCTURE = "anatomical_structure"
    PROCEDURE = "procedure"
    TEST = "test"
    BIOMARKER = "biomarker"

    # Research metadata
    PAPER = "paper"
    AUTHOR = "author"
    INSTITUTION = "institution"
    CLINICAL_TRIAL = "clinical_trial"

    # Scientific method entities (ontology-based)
    HYPOTHESIS = "hypothesis"  # IAO:0000018
    STUDY_DESIGN = "study_design"  # OBI study designs
    STATISTICAL_METHOD = "statistical_method"  # STATO methods
    EVIDENCE_LINE = "evidence_line"  # SEPIO evidence structures


class EntityReference(BaseModel):
    """
    Reference to an entity in the knowledge graph.

    Lightweight pointer to a canonical entity (Disease, Drug, Gene, etc.)
    with the name as it appeared in this specific paper.
    """

    id: str = Field(..., description="Canonical entity ID")
    name: str = Field(..., description="Entity name as mentioned in paper")
    type: EntityType = Field(..., description="Entity type (drug, disease, gene, protein, etc.)")


class Edge(BaseModel):
    id: EdgeId
    subject: EntityReference
    object: EntityReference
    provenance: Provenance


class ExtractionEdge(Edge):
    extractor: ModelInfo
    confidence: float


class ClaimEdge(Edge):
    predicate: ClaimPredicate
    asserted_by: PaperId
    polarity: Polarity  # supports / refutes / neutral


class EvidenceEdge(Edge):
    evidence_type: EvidenceType
    strength: float

"""
## Canonical IDs

This schema uses **canonical IDs** for both entities and relationships to ensure
consistency, deduplication, and interoperability across the knowledge graph.

### Why Canonical IDs?

1. **Deduplication** - Multiple papers may mention the same entity using different names
   ("Type 2 Diabetes", "T2DM", "NIDDM"). Canonical IDs ensure they all link to the same
   entity in the graph.

2. **Interoperability** - Using standard ontology IDs (UMLS, HGNC, RxNorm, etc.) enables
   integration with external medical databases and tools.

3. **Consistency** - Relationships between canonical entities are stable and queryable,
   regardless of how entities were mentioned in source papers.

4. **Provenance** - Each relationship tracks which papers support it, allowing evidence
   aggregation and confidence scoring.

### Entity Canonical IDs

Entities use type-specific canonical ID systems:

- **Diseases**: UMLS Concept IDs (e.g., `C0006142` for "Breast Cancer")
- **Genes**: HGNC IDs (e.g., `HGNC:1100` for BRCA1)
- **Drugs**: RxNorm IDs (e.g., `RxNorm:1187832` for Olaparib)
- **Proteins**: UniProt IDs (e.g., `P38398` for BRCA1 protein)

Examples:

    - Disease: `C0006142` (Breast Cancer) - from UMLS
    - Gene: `HGNC:1100` (BRCA1) - from HUGO Gene Nomenclature Committee
    - Drug: `RxNorm:1187832` (Olaparib) - from RxNorm

### Relationship Canonical IDs

Relationships are identified by their **triple**: `(subject_id, predicate, object_id)`.

The canonical form ensures that:
- The same relationship extracted from multiple papers is recognized as one relationship
- Evidence can be aggregated across papers
- Confidence scores can be computed from multiple sources

Example canonical relationships:

    - `(RxNorm:1187832, TREATS, C0006142)` - Olaparib treats Breast Cancer
    - `(HGNC:1100, INCREASES_RISK, C0006142)` - BRCA1 increases risk of Breast Cancer
    - `(C0006142, DIAGNOSED_BY, LOINC:12345)` - Breast Cancer diagnosed by Mammography

When the same relationship appears in multiple papers, they all reference the same
canonical triple, allowing the system to:
- Count supporting evidence
- Track contradictions
- Compute aggregate confidence scores
- Identify temporal evolution of medical knowledge
"""

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

    Examples:

        - "Olaparib significantly improved progression-free survival" (TREATS)
        - "BRCA1 mutations increase breast cancer risk by 5-fold" (INCREASES_RISK)
        - "Warfarin and aspirin interact synergistically" (INTERACTS_WITH)

    Attributes:

        predicate_type: The type of relationship asserted in the claim
        description: A natural language description of the predicate as it appears in the text
    """

    predicate_type: PredicateType = Field(..., description="The type of relationship asserted in the claim.")
    description: str = Field(..., description="A natural language description of the predicate as it appears in the text.")


class Provenance(BaseModel):
    """
    Information about the origin of a piece of data.

    Examples:

        - Research paper: source_type="paper", source_id="10.1234/nejm.2023.001"
        - Database record: source_type="database", source_id="UMLS:C0006142"
        - LLM extraction: source_type="model_extraction", source_id="extraction_batch_2024_01_15"

    Attributes:

        source_type: The type of source (e.g., 'paper', 'database', 'model_extraction')
        source_id: An identifier for the source (e.g., a DOI for a paper, a database record ID)
        source_version: The version of the source, if applicable
        notes: Additional notes about the provenance
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

    Examples:

        - Randomized controlled trial: ontology_id="ECO:0007673", ontology_label="randomized controlled trial evidence"
        - Observational study: ontology_id="ECO:0000203", ontology_label="observational study evidence"
        - Case report: ontology_id="ECO:0006016", ontology_label="case study evidence"

    Attributes:

        ontology_id: Identifier from an evidence ontology (e.g., SEPIO, Evidence & Conclusion Ontology)
        ontology_label: Human-readable label for the ontology term
        description: A fuller description of the evidence type
    """

    ontology_id: str = Field(..., description="Identifier from an evidence ontology (e.g., SEPIO, Evidence & Conclusion Ontology).")
    ontology_label: str = Field(..., description="Human-readable label for the ontology term.")
    description: Optional[str] = Field(None, description="A fuller description of the evidence type.")


class ModelInfo(BaseModel):
    """
    Information about a model used in extraction.

    Allows comparing extraction quality across different LLMs and versions.

    Attributes:

        name: Model name/identifier
        provider: Model provider (e.g., 'ollama', 'anthropic')
        temperature: Temperature parameter if applicable
        version: Model version if known
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

    Attributes:

        id: Canonical entity ID
        name: Entity name as mentioned in paper
        type: Entity type (drug, disease, gene, protein, etc.)
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

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from .base import PredicateType
from .entity import EvidenceItem, Measurement

# ============================================================================
# Base Relationship Classes
# ============================================================================


class BaseRelationship(BaseModel):
    """
    Minimal relationship base for all types.

    Attributes:

        subject_id: Entity ID of the subject (source node)
        predicate: Relationship type
        object_id: Entity ID of the object (target node)
        directed: Whether this relationship is directional
    """

    model_config = ConfigDict(use_enum_values=True, table_name="relationships")

    subject_id: str
    predicate: PredicateType
    object_id: str

    # Direction
    directed: bool = True


class BaseMedicalRelationship(BaseRelationship):
    """
    Base class for all medical relationships with comprehensive provenance tracking.

    All medical relationships inherit from this class and include evidence-based
    provenance fields to support confidence scoring, contradiction detection,
    and temporal tracking of medical knowledge.

    Combines lightweight tracking (just paper IDs) with optional rich provenance
    (detailed Evidence objects) and quantitative measurements.

    Attributes:

        subject_id: Entity ID of the subject (source node)
        predicate: Relationship type
        object_id: Entity ID of the object (target node)
        confidence: Confidence score (0.0-1.0) based on evidence strength
        source_papers: List of PMC IDs supporting this relationship (lightweight)
        evidence_count: Number of papers providing supporting evidence
        contradicted_by: List of PMC IDs with contradicting findings
        first_reported: Date when this relationship was first observed
        last_updated: Date of most recent supporting evidence
        evidence: List of detailed EvidenceItem objects (optional, for rich provenance)
        measurements: List of quantitative measurements (optional)
        properties: Flexible dict for relationship-specific properties

    Example (lightweight):
        >>> relationship = Treats(
        ...     subject_id="RxNorm:1187832",
        ...     predicate=PredicateType.TREATS,
        ...     object_id="C0006142",
        ...     source_papers=["PMC123", "PMC456"],
        ...     confidence=0.85,
        ...     evidence_count=2,
        ...     response_rate=0.59
        ... )

    Example (rich provenance):
        >>> relationship = Treats(
        ...     subject_id="RxNorm:1187832",
        ...     predicate=PredicateType.TREATS,
        ...     object_id="C0006142",
        ...     confidence=0.85,
        ...     evidence=[EvidenceItem(paper_id="PMC123", study_type="rct", sample_size=302)],
        ...     measurements=[Measurement(value=0.59, value_type="response_rate")],
        ...     response_rate=0.59
        ... )
    """

    # Core provenance (always present)
    confidence: float = Field(ge=0.0, le=1.0, default=0.5)

    # Lightweight tracking
    source_papers: list[str] = Field(default_factory=list)  # PMC IDs supporting this relationship
    evidence_count: int = 0  # Number of papers supporting
    contradicted_by: list[str] = Field(default_factory=list)  # PMC IDs of contradicting papers
    first_reported: str | None = None  # Date first observed
    last_updated: str | None = None  # Most recent evidence

    # Rich provenance (optional)
    evidence: list[EvidenceItem] = Field(default_factory=list)

    # Measurements (optional)
    measurements: list[Measurement] = Field(default_factory=list)

    # Relationship-specific properties (flexible)
    properties: dict = Field(default_factory=dict)


class Causes(BaseMedicalRelationship):
    """
    Represents a causal relationship between a disease and a symptom.

    Direction: Disease -> Symptom

    Attributes:

        frequency: How often the symptom occurs (always, often, sometimes, rarely)
        onset: When the symptom typically appears (early, late)
        severity: Typical severity of the symptom

    Example:
        >>> causes = Causes(
        ...     subject_id="C0006142",  # Breast Cancer
        ...     predicate=PredicateType.CAUSES,
        ...     object_id="C0030193",  # Pain
        ...     frequency="often",
        ...     onset="late",
        ...     severity="moderate",
        ...     source_papers=["PMC123"],
        ...     confidence=0.75
        ... )
    """

    predicate: Literal[PredicateType.CAUSES] = PredicateType.CAUSES
    frequency: Literal["always", "often", "sometimes", "rarely"] | None = None
    onset: Literal["early", "late"] | None = None
    severity: Literal["mild", "moderate", "severe"] | None = None


class Treats(BaseMedicalRelationship):
    """
    Represents a therapeutic relationship between a drug and a disease.

    Direction: Drug -> Disease

    Attributes:

        efficacy: Effectiveness measure or description
        response_rate: Percentage of patients responding (0.0-1.0)
        line_of_therapy: Treatment sequence (first-line, second-line, etc.)
        indication: Specific approved use or condition

    Example:
        >>> treats = Treats(
        ...     subject_id="RxNorm:1187832",  # Olaparib
        ...     predicate=PredicateType.TREATS,
        ...     object_id="C0006142",  # Breast Cancer
        ...     efficacy="significant improvement in PFS",
        ...     response_rate=0.59,
        ...     line_of_therapy="second-line",
        ...     indication="BRCA-mutated breast cancer",
        ...     source_papers=["PMC999", "PMC888"],
        ...     confidence=0.85
        ... )
    """

    predicate: Literal[PredicateType.TREATS] = PredicateType.TREATS
    efficacy: str | None = None  # Effectiveness measure
    response_rate: float | None = Field(None, ge=0.0, le=1.0)  # Percentage of patients responding
    line_of_therapy: Literal["first-line", "second-line", "third-line", "maintenance", "salvage"] | None = None
    indication: str | None = None  # Specific approved use


class IncreasesRisk(BaseMedicalRelationship):
    """
    Represents genetic risk factors for diseases.

    Direction: Gene/Mutation -> Disease

    Attributes:

        risk_ratio: Numeric risk increase (e.g., 2.5 means 2.5x higher risk)
        penetrance: Percentage who develop condition (0.0-1.0)
        age_of_onset: Typical age when disease manifests
        population: Studied population or ethnic group

    Example:
        >>> risk = IncreasesRisk(
        ...     subject_id="HGNC:1100",  # BRCA1
        ...     predicate=PredicateType.INCREASES_RISK,
        ...     object_id="C0006142",  # Breast Cancer
        ...     risk_ratio=5.0,
        ...     penetrance=0.72,
        ...     age_of_onset="40-50 years",
        ...     population="Ashkenazi Jewish",
        ...     source_papers=["PMC123", "PMC456"],
        ...     confidence=0.92
        ... )
    """

    predicate: Literal[PredicateType.INCREASES_RISK] = PredicateType.INCREASES_RISK
    risk_ratio: float | None = Field(None, gt=0.0)  # Numeric risk increase (e.g., 2.5x)
    penetrance: float | None = Field(None, ge=0.0, le=1.0)  # Percentage who develop condition
    age_of_onset: str | None = None  # Typical age
    population: str | None = None  # Studied population


class AssociatedWith(BaseMedicalRelationship):
    """
    Represents a general association between entities.

    This is used for relationships where causality is not established but
    statistical association exists.

    Valid directions:

        - Disease -> Disease (comorbidities)
        - Gene -> Disease
        - Biomarker -> Disease

    Attributes:

        association_type: Nature of association (positive, negative, neutral)
        strength: Association strength (strong, moderate, weak)
        statistical_significance: p-value from statistical tests

    Example:
        >>> assoc = AssociatedWith(
        ...     subject_id="C0011849",  # Diabetes
        ...     predicate=PredicateType.ASSOCIATED_WITH,
        ...     object_id="C0020538",  # Hypertension
        ...     association_type="positive",
        ...     strength="strong",
        ...     statistical_significance=0.001,
        ...     source_papers=["PMC111"],
        ...     confidence=0.80
        ... )
    """

    predicate: Literal[PredicateType.ASSOCIATED_WITH] = PredicateType.ASSOCIATED_WITH
    association_type: Literal["positive", "negative", "neutral"] | None = None
    strength: Literal["strong", "moderate", "weak"] | None = None
    statistical_significance: float | None = Field(None, ge=0.0, le=1.0)  # p-value


class InteractsWith(BaseMedicalRelationship):
    """
    Represents drug-drug interactions.

    Direction: Drug <-> Drug (bidirectional)

    Attributes:

        interaction_type: Nature of interaction (synergistic, antagonistic, additive)
        severity: Clinical severity (major, moderate, minor)
        mechanism: Pharmacological mechanism of interaction
        clinical_significance: Description of clinical implications

    Example:
        >>> interaction = InteractsWith(
        ...     subject_id="RxNorm:123",  # Warfarin
        ...     predicate=PredicateType.INTERACTS_WITH,
        ...     object_id="RxNorm:456",  # Aspirin
        ...     interaction_type="synergistic",
        ...     severity="major",
        ...     mechanism="Additive anticoagulant effect",
        ...     clinical_significance="Increased bleeding risk",
        ...     source_papers=["PMC789"],
        ...     confidence=0.90
        ... )
    """

    predicate: Literal[PredicateType.INTERACTS_WITH] = PredicateType.INTERACTS_WITH
    directed: bool = False  # Bidirectional
    interaction_type: Literal["synergistic", "antagonistic", "additive"] | None = None
    severity: Literal["major", "moderate", "minor"] | None = None
    mechanism: str | None = None  # How they interact
    clinical_significance: str | None = None  # Description


class Encodes(BaseMedicalRelationship):
    """
    Gene -[ENCODES]-> Protein
    """

    predicate: Literal[PredicateType.ENCODES] = PredicateType.ENCODES
    transcript_variants: int | None = None  # Number of variants
    tissue_specificity: str | None = None  # Where expressed


class ParticipatesIn(BaseMedicalRelationship):
    """
    Gene/Protein -[PARTICIPATES_IN]-> Pathway
    """

    predicate: Literal[PredicateType.PARTICIPATES_IN] = PredicateType.PARTICIPATES_IN
    role: str | None = None  # Function in pathway
    regulatory_effect: Literal["activates", "inhibits", "modulates"] | None = None


class ContraindicatedFor(BaseMedicalRelationship):
    """
    Drug -[CONTRAINDICATED_FOR]-> Disease/Condition
    """

    predicate: Literal[PredicateType.CONTRAINDICATED_FOR] = PredicateType.CONTRAINDICATED_FOR
    severity: Literal["absolute", "relative"] | None = None
    reason: str | None = None  # Why contraindicated


class DiagnosedBy(BaseMedicalRelationship):
    """
    Represents diagnostic tests or biomarkers used to diagnose a disease.

    Direction: Disease -> Procedure/Biomarker

    Attributes:

        sensitivity: True positive rate (0.0-1.0)
        specificity: True negative rate (0.0-1.0)
        standard_of_care: Whether this is standard clinical practice

    Example:
        >>> diagnosis = DiagnosedBy(
        ...     subject_id="C0006142",  # Breast Cancer
        ...     predicate=PredicateType.DIAGNOSED_BY,
        ...     object_id="LOINC:123",  # Mammography
        ...     sensitivity=0.87,
        ...     specificity=0.91,
        ...     standard_of_care=True,
        ...     source_papers=["PMC555"],
        ...     confidence=0.88
        ... )
    """

    predicate: Literal[PredicateType.DIAGNOSED_BY] = PredicateType.DIAGNOSED_BY
    sensitivity: float | None = Field(None, ge=0.0, le=1.0)  # True positive rate
    specificity: float | None = Field(None, ge=0.0, le=1.0)  # True negative rate
    standard_of_care: bool = False  # Whether this is standard practice


class SideEffect(BaseMedicalRelationship):
    """
    Represents adverse effects of medications.

    Direction: Drug -> Symptom

    Attributes:

        frequency: How often it occurs (common, uncommon, rare)
        severity: Severity level (mild, moderate, severe)
        reversible: Whether the side effect resolves after stopping the drug

    Example:
        >>> side_effect = SideEffect(
        ...     subject_id="RxNorm:1187832",  # Olaparib
        ...     predicate=PredicateType.SIDE_EFFECT,
        ...     object_id="C0027497",  # Nausea
        ...     frequency="common",
        ...     severity="mild",
        ...     reversible=True,
        ...     source_papers=["PMC999"],
        ...     confidence=0.75
        ... )
    """

    predicate: Literal[PredicateType.SIDE_EFFECT] = PredicateType.SIDE_EFFECT
    frequency: Literal["common", "uncommon", "rare"] | None = None
    severity: Literal["mild", "moderate", "severe"] | None = None
    reversible: bool = True  # Whether side effect is reversible


# ============================================================================
# Research Metadata Relationships
# ============================================================================


class ResearchRelationship(BaseRelationship):
    """
    Base class for research metadata relationships.

    These relationships connect papers, authors, and clinical trials.
    Unlike medical relationships, they don't require provenance tracking
    since they represent bibliographic metadata rather than medical claims.

    Attributes:

        subject_id: ID of the subject entity
        predicate: Relationship type
        object_id: ID of the object entity
        properties: Flexible dict for relationship-specific properties
    """

    properties: dict = Field(default_factory=dict)


class Cites(ResearchRelationship):
    """
    Represents a citation from one paper to another.

    Direction: Paper -> Paper (citing -> cited)

    Attributes:

        context: Section where citation appears (introduction, methods, discussion)
        sentiment: How the citation is used (supports, contradicts, mentions)

    Example:
        >>> citation = Cites(
        ...     subject_id="PMC123",
        ...     predicate=PredicateType.CITES,
        ...     object_id="PMC456",
        ...     context="discussion",
        ...     sentiment="supports"
        ... )
    """

    predicate: Literal[PredicateType.CITES] = PredicateType.CITES
    context: Literal["introduction", "methods", "results", "discussion"] | None = None
    sentiment: Literal["supports", "contradicts", "mentions"] | None = None


class StudiedIn(ResearchRelationship):
    """
    Links medical entities to papers that study them.

    Direction: Any medical entity -> Paper

    Attributes:

        role: Importance in the paper (primary_focus, secondary_finding, mentioned)
        section: Where discussed (results, methods, discussion, introduction)

    Example:
        >>> studied = StudiedIn(
        ...     subject_id="RxNorm:1187832",  # Olaparib
        ...     predicate=PredicateType.STUDIED_IN,
        ...     object_id="PMC999",
        ...     role="primary_focus",
        ...     section="results"
        ... )
    """

    predicate: Literal[PredicateType.STUDIED_IN] = PredicateType.STUDIED_IN
    role: Literal["primary_focus", "secondary_finding", "mentioned"] | None = None
    section: Literal["results", "methods", "discussion", "introduction"] | None = None


class AuthoredBy(ResearchRelationship):
    """
    Paper -[AUTHORED_BY]-> Author
    """

    predicate: Literal[PredicateType.AUTHORED_BY] = PredicateType.AUTHORED_BY
    position: Literal["first", "last", "corresponding", "middle"] | None = None


class PartOf(ResearchRelationship):
    """
    Paper -[PART_OF]-> ClinicalTrial
    """

    predicate: Literal[PredicateType.PART_OF] = PredicateType.PART_OF
    publication_type: Literal["protocol", "results", "analysis"] | None = None


# ============================================================================
# Hypothesis and Evidence Relationships
# ============================================================================


class Predicts(BaseMedicalRelationship):
    """
    Represents a hypothesis predicting an observable outcome.

    Direction: Hypothesis -> Entity (Disease, Outcome, etc.)

    Attributes:

        prediction_type: Nature of prediction (positive, negative, conditional)
        conditions: Conditions under which prediction holds
        testable: Whether the prediction is empirically testable

    Example:
        >>> predicts = Predicts(
        ...     subject_id="HYPOTHESIS:amyloid_cascade",
        ...     predicate=PredicateType.PREDICTS,
        ...     object_id="C0002395",  # Alzheimer's disease
        ...     prediction_type="positive",
        ...     testable=True,
        ...     source_papers=["PMC123456"]
        ... )
    """

    predicate: Literal[PredicateType.PREDICTS] = PredicateType.PREDICTS
    prediction_type: Literal["positive", "negative", "conditional"] | None = None
    conditions: str | None = None  # Conditions under which prediction holds
    testable: bool = True  # Whether empirically testable


class Refutes(BaseMedicalRelationship):
    """
    Represents evidence that refutes a hypothesis.

    Direction: Evidence/Paper -> Hypothesis

    Attributes:

        refutation_strength: Strength of refutation (strong, moderate, weak)
        alternative_explanation: Alternative explanation for observations
        limitations: Limitations of the refuting evidence

    Example:
        >>> refutes = Refutes(
        ...     subject_id="PMC999888",
        ...     predicate=PredicateType.REFUTES,
        ...     object_id="HYPOTHESIS:amyloid_cascade",
        ...     refutation_strength="moderate",
        ...     source_papers=["PMC999888"],
        ...     confidence=0.75
        ... )
    """

    predicate: Literal[PredicateType.REFUTES] = PredicateType.REFUTES
    refutation_strength: Literal["strong", "moderate", "weak"] | None = None
    alternative_explanation: str | None = None
    limitations: str | None = None


class TestedBy(BaseMedicalRelationship):
    """
    Represents a hypothesis being tested by a study or clinical trial.

    Direction: Hypothesis -> Paper/ClinicalTrial

    Attributes:

        test_outcome: Result of the test (supported, refuted, inconclusive)
        methodology: Study methodology used
        study_design_id: OBI study design ID

    Example:
        >>> tested = TestedBy(
        ...     subject_id="HYPOTHESIS:parp_inhibitor_synthetic_lethality",
        ...     predicate=PredicateType.TESTED_BY,
        ...     object_id="PMC999888",
        ...     test_outcome="supported",
        ...     methodology="randomized controlled trial",
        ...     study_design_id="OBI:0000008",
        ...     source_papers=["PMC999888"],
        ...     confidence=0.90
        ... )
    """

    predicate: Literal[PredicateType.TESTED_BY] = PredicateType.TESTED_BY
    test_outcome: Literal["supported", "refuted", "inconclusive"] | None = None
    methodology: str | None = None
    study_design_id: str | None = None  # OBI study design ID


class Generates(BaseMedicalRelationship):
    """
    Represents a study generating evidence for analysis.

    Direction: ClinicalTrial/Paper -> Evidence

    Attributes:

        evidence_type: Type of evidence generated (experimental, observational, etc.)
        eco_type: ECO evidence type ID
        quality_score: Quality assessment score

    Example:
        >>> generates = Generates(
        ...     subject_id="PMC999888",
        ...     predicate=PredicateType.GENERATES,
        ...     object_id="EVIDENCE_LINE:olaparib_brca_001",
        ...     evidence_type="experimental",
        ...     eco_type="ECO:0007673",
        ...     quality_score=0.92,
        ...     source_papers=["PMC999888"]
        ... )
    """

    predicate: Literal[PredicateType.GENERATES] = PredicateType.GENERATES
    evidence_type: str | None = None
    eco_type: str | None = None  # ECO evidence type ID
    quality_score: float | None = Field(None, ge=0.0, le=1.0)


# ============================================================================
# Convenience Factory Function
# ============================================================================


def create_relationship(predicate: PredicateType, subject_id: str, object_id: str, **kwargs) -> BaseMedicalRelationship | ResearchRelationship:
    """
    Factory function to create the appropriate relationship type.

    This allows you to use either the generic interface or the strongly-typed one.

    Args:

        predicate: The type of relationship
        subject_id: ID of the subject entity
        object_id: ID of the object entity
        **kwargs: Additional fields specific to the relationship type

    Returns:

        Appropriately typed relationship instance

    Example:
        >>> rel = create_relationship(
        ...     PredicateType.TREATS,
        ...     subject_id="RxNorm:1187832",
        ...     object_id="C0006142",
        ...     response_rate=0.59,
        ...     source_papers=["PMC999"]
        ... )
    """
    relationship_classes = {
        PredicateType.CAUSES: Causes,
        PredicateType.TREATS: Treats,
        PredicateType.INCREASES_RISK: IncreasesRisk,
        PredicateType.ASSOCIATED_WITH: AssociatedWith,
        PredicateType.INTERACTS_WITH: InteractsWith,
        PredicateType.DIAGNOSED_BY: DiagnosedBy,
        PredicateType.SIDE_EFFECT: SideEffect,
        PredicateType.ENCODES: Encodes,
        PredicateType.PARTICIPATES_IN: ParticipatesIn,
        PredicateType.CONTRAINDICATED_FOR: ContraindicatedFor,
        PredicateType.CITES: Cites,
        PredicateType.STUDIED_IN: StudiedIn,
        PredicateType.AUTHORED_BY: AuthoredBy,
        PredicateType.PART_OF: PartOf,
        PredicateType.PREDICTS: Predicts,
        PredicateType.REFUTES: Refutes,
        PredicateType.TESTED_BY: TestedBy,
        PredicateType.GENERATES: Generates,
    }

    cls = relationship_classes.get(predicate, BaseMedicalRelationship)
    return cls(subject_id=subject_id, object_id=object_id, predicate=predicate, **kwargs)

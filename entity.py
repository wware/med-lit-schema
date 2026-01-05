"""
## Overview

This schema defines the **Domain Models** for the knowledge graph.
These are the Pydantic classes used by application code, pipelines, and the API.
For database storage, these are mapped to the Persistence Models in `schema/entity_sqlmodel.py`.

This schema is designed to support clinical decision-making by representing medical knowledge
extracted from research papers. The graph enables multi-hop reasoning, contradiction detection,
and evidence-based inference. It uses strongly-typed entity classes (Disease, Gene, Drug,
Protein, etc.) as the canonical representation for all entities in the knowledge graph.
This approach provides type safety and validation.

## Design Principles

1. **Clinical utility first** - Schema supports queries doctors actually ask
2. **Provenance always** - Every relationship traces back to source papers
3. **Handle uncertainty** - Represent confidence, contradictions, and evolution over time
4. **Standards-based** - Use UMLS, MeSH, and other medical ontologies for entity IDs
5. **Scalable** - Can grow from thousands to millions of papers

All medical entities (Disease, Gene, Drug, Protein, etc.) share these base properties:

- entity_id: Unique identifier (type-specific, e.g., UMLS ID, HGNC ID)
- name: Primary canonical name
- synonyms: [list of alternate names]
- abbreviations: [common abbreviations, e.g., "T2DM", "NIDDM"]
- embedding: Pre-computed biomedical embedding vector
- created_at: Timestamp when entity was added
- source: Origin ("umls", "mesh", "rxnorm", "hgnc", "uniprot", "extracted")
"""

import json
from datetime import datetime
from typing import Any, Dict, List, Literal, Optional, cast

from pydantic import BaseModel, ConfigDict, Field, field_validator
from tqdm import tqdm

from .base import EntityReference, EntityType, ModelInfo, PredicateType


class BaseMedicalEntity(BaseModel):
    """
    Base class for all medical entities in the knowledge graph.

    Serves as the canonical entity representation with external ontology mappings,
    pre-computed embeddings for semantic search, and provenance tracking.
    All specific entity types (Disease, Gene, Drug, etc.) inherit from this class.

    Attributes:
        entity_id: Unique identifier (e.g., UMLS ID, HGNC ID, RxNorm ID)
        entity_type: Type of entity (disease, drug, gene, etc.)
        name: Primary canonical name for the entity
        synonyms: Alternative names and variants
        abbreviations: Common abbreviations (e.g., "T2DM" for Type 2 Diabetes)
        embedding: Pre-computed biomedical embedding vector
        created_at: Timestamp when entity was added to the system
        source: Origin of this entity (umls, mesh, rxnorm, extracted)

    Example:
        >>> disease = Disease(
        ...     entity_id="C0011860",
        ...     name="Type 2 Diabetes Mellitus",
        ...     synonyms=["Type II Diabetes", "Adult-Onset Diabetes"],
        ...     abbreviations=["T2DM", "NIDDM"],
        ...     source="umls"
        ... )
    """

    model_config = ConfigDict(use_enum_values=True)

    entity_id: str
    entity_type: EntityType
    name: str
    synonyms: list[str] = Field(default_factory=list)
    abbreviations: list[str] = Field(default_factory=list)

    # Embeddings for semantic search (pre-computed)
    embedding: list[float] | None = Field(None, description="Pre-computed biomedical embedding vector for semantic search")

    # Metadata for provenance tracking
    created_at: datetime = Field(default_factory=datetime.now)
    source: Literal["umls", "mesh", "rxnorm", "hgnc", "uniprot", "extracted"] = "extracted"


class Disease(BaseMedicalEntity):
    """
    Represents medical conditions, disorders, and syndromes.

    Uses UMLS as the primary identifier system with additional mappings to
    MeSH and ICD-10 for interoperability with clinical systems.

    Attributes:
        umls_id: UMLS Concept ID (e.g., "C0006142" for Breast Cancer)
        mesh_id: Medical Subject Heading ID for literature indexing
        icd10_codes: List of ICD-10 diagnostic codes
        category: Disease classification (genetic, infectious, autoimmune, etc.)

    Example:
        >>> breast_cancer = Disease(
        ...     entity_id="C0006142",
        ...     name="Breast Cancer",
        ...     synonyms=["Breast Carcinoma", "Mammary Cancer"],
        ...     umls_id="C0006142",
        ...     mesh_id="D001943",
        ...     icd10_codes=["C50.9"],
        ...     category="genetic"
        ... )
    """

    entity_type: Literal[EntityType.DISEASE] = EntityType.DISEASE
    umls_id: str | None = None  # UMLS Concept ID (e.g., C0006142 for "Breast Cancer")
    mesh_id: str | None = None
    icd10_codes: list[str] = Field(default_factory=list)
    category: str | None = None  # genetic, infectious, autoimmune, etc.


class Gene(BaseMedicalEntity):
    """
    Represents genes and their genomic information.

    Uses HGNC (HUGO Gene Nomenclature Committee) as the primary identifier
    with additional mappings to NCBI Entrez Gene.

    Attributes:
        symbol: Official gene symbol (e.g., "BRCA1")
        hgnc_id: HGNC identifier (e.g., "HGNC:1100")
        chromosome: Chromosomal location (e.g., "17q21.31")
        entrez_id: NCBI Gene ID for cross-referencing

    Example:
        >>> brca1 = Gene(
        ...     entity_id="HGNC:1100",
        ...     name="BRCA1 DNA repair associated",
        ...     synonyms=["BRCA1", "breast cancer 1"],
        ...     symbol="BRCA1",
        ...     hgnc_id="HGNC:1100",
        ...     chromosome="17q21.31",
        ...     entrez_id="672"
        ... )
    """

    entity_type: Literal[EntityType.GENE] = EntityType.GENE
    symbol: str | None = None  # Gene symbol (e.g., BRCA1)
    hgnc_id: str | None = None  # HGNC ID (e.g., HGNC:1100)
    chromosome: str | None = None  # Location (e.g., 17q21.31)
    entrez_id: str | None = None  # NCBI Gene ID


class Mutation(BaseMedicalEntity):
    """
    Represents specific genetic variants
    """

    entity_type: Literal[EntityType.MUTATION] = EntityType.MUTATION
    gene_id: str | None = None
    variant_type: str | None = None
    notation: str | None = None
    consequence: str | None = None


class Drug(BaseMedicalEntity):
    """
    Represents medications and therapeutic substances.

    Uses RxNorm as the primary identifier for standardized medication naming.

    Attributes:
        rxnorm_id: RxNorm Concept ID for drug identification
        brand_names: List of commercial/brand names
        drug_class: Therapeutic class (chemotherapy, immunotherapy, etc.)
        mechanism: Mechanism of action description

    Example:
        >>> olaparib = Drug(
        ...     entity_id="RxNorm:1187832",
        ...     name="Olaparib",
        ...     synonyms=["AZD2281"],
        ...     rxnorm_id="1187832",
        ...     brand_names=["Lynparza"],
        ...     drug_class="PARP inhibitor",
        ...     mechanism="Inhibits poly ADP-ribose polymerase enzymes"
        ... )
    """

    entity_type: Literal[EntityType.DRUG] = EntityType.DRUG
    rxnorm_id: str | None = None
    brand_names: list[str] | None = None
    drug_class: str | None = None
    mechanism: str | None = None


class Protein(BaseMedicalEntity):
    """
    Represents proteins and their biological functions.

    Uses UniProt as the primary identifier for protein sequences and annotations.

    Attributes:
        uniprot_id: UniProt accession number
        gene_id: ID of the gene that encodes this protein
        function: Description of biological function
        pathways: List of biological pathways this protein participates in

    Example:
        >>> brca1_protein = Protein(
        ...     entity_id="P38398",
        ...     name="Breast cancer type 1 susceptibility protein",
        ...     synonyms=["BRCA1"],
        ...     uniprot_id="P38398",
        ...     gene_id="HGNC:1100",
        ...     function="DNA repair and tumor suppression",
        ...     pathways=["DNA damage response", "Homologous recombination"]
        ... )
    """

    entity_type: Literal[EntityType.PROTEIN] = EntityType.PROTEIN
    uniprot_id: str | None = None  # UniProt ID
    gene_id: str | None = None  # Encoding gene
    function: str | None = None  # Biological function
    pathways: list[str] = Field(default_factory=list)  # Biological pathways involved in


class Symptom(BaseMedicalEntity):
    """
    Represents clinical signs and symptoms
    """

    entity_type: Literal[EntityType.SYMPTOM] = EntityType.SYMPTOM
    severity_scale: str | None = None


class Procedure(BaseMedicalEntity):
    """
    Represents medical tests, diagnostics, treatments
    """

    entity_type: Literal[EntityType.PROCEDURE] = EntityType.PROCEDURE
    type: str | None = None
    invasiveness: str | None = None


class Biomarker(BaseMedicalEntity):
    """
    Represents measurable indicators
    """

    entity_type: Literal[EntityType.BIOMARKER] = EntityType.BIOMARKER
    loinc_code: str | None = None  # LOINC code
    measurement_type: str | None = None  # blood, tissue, imaging
    normal_range: str | None = None  # Reference values


class Pathway(BaseMedicalEntity):
    """
    Represents biological pathways
    """

    entity_type: Literal[EntityType.PATHWAY] = EntityType.PATHWAY
    kegg_id: str | None = None  # KEGG ID
    reactome_id: str | None = None  # Reactome ID
    category: str | None = None  # signaling, metabolic, etc.
    genes_involved: list[str] = Field(default_factory=list)


# ============================================================================
# Provenance Classes
# ============================================================================


class ExtractionPipelineInfo(BaseModel):
    """
    Information about the extraction pipeline version.

    Tracks the exact code version that performed entity/relationship extraction.
    Essential for reproducibility and debugging extraction quality issues.
    """

    name: str = Field(..., description="Pipeline name (e.g., 'ollama_langchain_pipeline')")
    version: str = Field(..., description="Semantic version of the pipeline")
    git_commit: str = Field(..., description="Full git commit hash")
    git_commit_short: str = Field(..., description="Short git commit hash (7 chars)")
    git_branch: str = Field(..., description="Git branch name")
    git_dirty: bool = Field(..., description="Whether working directory had uncommitted changes")
    repo_url: str = Field(..., description="Repository URL")


class PromptInfo(BaseModel):
    """
    Information about the prompt used.

    Tracks prompt evolution.  Critical for understanding extraction behavior changes.
    """

    version: str = Field(..., description="Prompt version identifier")
    template: str = Field(..., description="Prompt template name")
    checksum: Optional[str] = Field(None, description="SHA256 of actual prompt text for exact reproduction")


class ExecutionInfo(BaseModel):
    """
    Information about when and where extraction was performed.

    Useful for debugging issues related to specific machines or time periods.
    """

    timestamp: str = Field(..., description="ISO 8601 UTC timestamp")
    hostname: str = Field(..., description="Hostname of machine that ran extraction")
    python_version: str = Field(..., description="Python version")
    duration_seconds: Optional[float] = Field(None, description="Extraction duration in seconds")


class EntityResolutionInfo(BaseModel):
    """
    Information about entity resolution process.

    Tracks how entities were matched to canonical IDs.  Helps identify when
    entity deduplication is working poorly.
    """

    canonical_entities_matched: int = Field(..., description="Number of entities matched to existing canonical IDs")
    new_entities_created: int = Field(..., description="Number of new canonical entities created")
    similarity_threshold: float = Field(..., description="Similarity threshold used for matching")
    embedding_model: str = Field(..., description="Embedding model used for similarity")


class ExtractionProvenance(BaseModel):
    """
    Complete provenance metadata for an extraction.

    This is the complete audit trail of how extraction was performed.
    Enables:
    - Reproducing exact extraction with same code/models/prompts
    - Comparing outputs from different parser versions
    - Debugging quality issues
    - Tracking parser evolution over time
    - Meeting reproducibility requirements for research

    Example queries enabled by provenance:
    - "Find all papers extracted with prompt v1 so I can re-extract with v2"
    - "Which papers were extracted with uncommitted code changes?"
    - "Compare entity extraction quality between llama3.1:70b and claude-4"
    """

    extraction_pipeline: ExtractionPipelineInfo
    models: Dict[str, ModelInfo] = Field(..., description="Models used, keyed by role (e.g., 'llm', 'embeddings')")
    prompt: PromptInfo
    execution: ExecutionInfo
    entity_resolution: Optional[EntityResolutionInfo] = Field(None, description="Entity resolution details if applicable")


# ============================================================================
# Entity and Relationship Classes
# ============================================================================


class AssertedRelationship(BaseModel):
    """
    Evidence for a relationship extracted from a paper.

    Represents a claim like "Drug X treats Disease Y" with supporting evidence
    and confidence scoring.
    """

    subject_id: str = Field(..., description="Subject entity canonical ID")
    predicate: str = Field(..., description="Relationship type")
    object_id: str = Field(..., description="Object entity canonical ID")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Confidence score")
    evidence: str = Field(..., description="Direct quote from paper supporting this relationship")
    section: str = Field(..., description="Paper section (abstract, methods, results, discussion)")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Additional metadata (study_type, measurements, etc.)")


# ============================================================================
# Enhanced Paper Metadata
# ============================================================================


class PaperMetadata(BaseModel):
    """
    Extended metadata about the research paper.

    Combines study characteristics (for evidence quality assessment) with
    bibliographic information (for citations and filtering).

    This is MORE than just storage - these fields enable critical queries:
    - "Show me only RCT evidence for this drug-disease relationship"
    - "What's the sample size distribution for studies on this topic?"
    - "Find papers from high-impact journals on this mutation"
    """

    # Study characteristics (for evidence quality)
    study_type: Optional[Literal["observational", "rct", "meta_analysis", "case_report", "review"]] = Field(None, description="Type of study - used for evidence level filtering")
    sample_size: Optional[int] = Field(None, description="Study sample size - larger = more reliable")
    study_population: Optional[str] = Field(None, description="Description of study population")
    primary_outcome: Optional[str] = Field(None, description="Primary outcome measured")
    clinical_phase: Optional[str] = Field(None, description="Clinical trial phase if applicable")

    # Bibliographic information
    publication_date: Optional[str] = Field(None, description="Publication date (YYYY-MM-DD)")
    journal: Optional[str] = Field(None, description="Journal name")
    doi: Optional[str] = Field(None, description="Digital Object Identifier")
    pmid: Optional[str] = Field(None, description="PubMed ID")

    # Indexing and categorization
    mesh_terms: List[str] = Field(default_factory=list, description="Medical Subject Headings - NLM's controlled vocabulary for indexing")


# ============================================================================
# Best-of-Breed Paper Model
# ============================================================================


class Paper(BaseModel):
    """
    A research paper with extracted entities, relationships, and full provenance.

    This is the COMPLETE representation of a paper in the knowledge graph, combining:
    1. Bibliographic metadata (authors, journal, identifiers)
    2. Text content (title, abstract)
    3. Extracted knowledge (entities and relationships)
    4. Extraction provenance (how extraction was performed)

    Design philosophy:
    - Top-level fields are FREQUENTLY QUERIED (paper_id, title, authors, publication_date)
    - Nested objects group related data (metadata for study info, provenance for extraction)
    - Field aliases provide backward compatibility with existing code

    Why certain fields are top-level:
    - `paper_id`: Primary key, referenced everywhere
    - `title`, `abstract`: Core content, always displayed
    - `authors`: Essential for citations, frequently filtered
    - `publication_date`: Frequently used for filtering by recency
    - `journal`: Frequently used for quality filtering

    Why other fields are nested:
    - `metadata`: Study details, accessed together for evidence assessment
    - `extraction_provenance`: Technical details, only for debugging/reproducibility
    """

    # Pydantic v2 configuration - use model_config, NOT Config class
    model_config = ConfigDict(
        use_enum_values=True,  # Serialize enums as their values
        populate_by_name=True,  # Allow setting fields by alias OR field name
        json_schema_extra={  # This replaces the old Config. schema_extra
            "example": {
                "paper_id": "PMC8437152",
                "pmid": "34567890",
                "doi": "10.1234/nejm.2023.001",
                "title": "Efficacy of Olaparib in BRCA-Mutated Breast Cancer",
                "abstract": "Background:  PARP inhibitors have shown promise...",
                "authors": ["Smith J", "Johnson A", "Williams K"],
                "publication_date": "2023-06-15",
                "journal": "New England Journal of Medicine",
                "entities": [
                    {"id": "DRUG: olaparib", "name": "Olaparib", "type": "drug", "canonical_id": "RxNorm:1187832"},
                    {"id": "DISEASE:breast_cancer", "name": "Breast Cancer", "type": "disease", "canonical_id": "UMLS:C0006142"},
                ],
                "relationships": [
                    {
                        "subject_id": "DRUG:olaparib",
                        "predicate": "TREATS",
                        "object_id": "DISEASE:breast_cancer",
                        "confidence": 0.95,
                        "evidence": "Olaparib significantly improved progression-free survival",
                        "section": "abstract",
                    }
                ],
                "metadata": {
                    "study_type": "rct",
                    "sample_size": 302,
                    "study_population": "Women with BRCA1/2-mutated metastatic breast cancer",
                    "primary_outcome": "Progression-free survival",
                    "clinical_phase": "III",
                    "journal": "New England Journal of Medicine",
                    "publication_date": "2023-06-15",
                    "mesh_terms": ["Breast Neoplasms", "BRCA1 Protein", "PARP Inhibitors"],
                },
                "extraction_provenance": {
                    "extraction_pipeline": {
                        "name": "ollama_langchain_pipeline",
                        "version": "1.0.0",
                        "git_commit": "abc123def456...",
                        "git_commit_short": "abc123d",
                        "git_branch": "main",
                        "git_dirty": False,
                        "repo_url": "https://github.com/wware/med-lit-graph",
                    },
                    "models": {
                        "llm": {"name": "llama3.1:70b", "provider": "ollama", "temperature": 0.1},
                        "embeddings": {"name": "microsoft/BiomedNLP-BiomedBERT-base-uncased-abstract-fulltext", "provider": "huggingface"},
                    },
                    "prompt": {"version": "v1_detailed", "template": "medical_extraction_prompt_v1"},
                    "execution": {"timestamp": "2025-12-15T14:30:00Z", "hostname": "extraction-server-01", "python_version": "3.12.0", "duration_seconds": 45.3},
                },
            }
        },
    )

    # ========== CORE IDENTIFICATION ==========

    paper_id: str = Field(..., description="Unique identifier - PMC ID preferred, but can be DOI or PMID")

    pmid: Optional[str] = Field(None, description="PubMed ID - different from PMC ID")

    doi: Optional[str] = Field(None, description="Digital Object Identifier")

    # ========== CONTENT ==========

    title: str = Field(..., description="Full paper title")
    abstract: str = Field(..., description="Complete abstract text")

    # ========== BIBLIOGRAPHIC METADATA ==========

    authors: List[str] = Field(default_factory=list, description="List of author names in citation order")

    publication_date: Optional[str] = Field(None, description="Publication date in ISO format (YYYY-MM-DD)")

    journal: Optional[str] = Field(None, description="Journal name")

    # ========== EXTRACTED KNOWLEDGE ==========

    entities: List[EntityReference] = Field(default_factory=list, description="Entities mentioned in paper")

    relationships: List[AssertedRelationship] = Field(default_factory=list, description="Relationships extracted from paper")

    # ========== STUDY METADATA ==========

    metadata: PaperMetadata = Field(default_factory=PaperMetadata, description="Extended metadata including study type, sample size, MeSH terms")

    # ========== EXTRACTION PROVENANCE ==========

    extraction_provenance: ExtractionProvenance = Field(..., description="Complete provenance of how extraction was performed")

    # ========== CONVENIENCE PROPERTIES ==========

    @property
    def study_type(self) -> Optional[str]:
        """Convenience property for accessing study_type from metadata."""
        return self.metadata.study_type  # pylint: disable=no-member

    @property
    def sample_size(self) -> Optional[int]:
        """Convenience property for accessing sample_size from metadata."""
        return self.metadata.sample_size  # pylint: disable=no-member

    @property
    def mesh_terms(self) -> List[str]:
        """Convenience property for accessing mesh_terms from metadata."""
        return self.metadata.mesh_terms  # pylint:  disable=no-member

    # ========== VALIDATION ==========

    @field_validator("publication_date")
    @classmethod
    def validate_publication_date(cls, v: Optional[str]) -> Optional[str]:
        """Ensure publication_date is in ISO format if provided."""
        if v is not None:
            try:
                datetime.fromisoformat(v.replace("Z", "+00:00"))
            except ValueError:
                raise ValueError(f"publication_date must be in ISO format (YYYY-MM-DD), got: {v}")
        return v


# ============================================================================
# HOW ALIASES WORK - EXAMPLES
# ============================================================================

"""
ALIAS EXAMPLE 1: Reading data with different field names
---------------------------------------------------------

If you have old JSON with 'pmc_id' instead of 'paper_id':

    old_json = {
        "pmc_id": "PMC123456",  # Old field name
        "title": "Some paper",
        "abstract": "Some abstract",
        ...
    }

    # Pydantic will automatically map 'pmc_id' to 'paper_id'
    paper = Paper.model_validate(old_json)
    print(paper.paper_id)  # "PMC123456"


ALIAS EXAMPLE 2: Accessing the field
-------------------------------------

Once you have a Paper object, you ALWAYS use the real field name:

    paper = Paper(paper_id="PMC123456", ...)
    print(paper.paper_id)  # "PMC123456"

    # NOTE: paper. pmc_id is a PROPERTY that returns paper_id
    print(paper. pmc_id)  # "PMC123456" (same value)


ALIAS EXAMPLE 3: Serialization
-------------------------------

When you serialize to JSON/dict, the alias is used:

    paper_dict = paper.model_dump()
    # paper_dict contains 'paper_id', NOT 'pmc_id'

    paper_dict = paper.model_dump(by_alias=True)
    # paper_dict contains 'paper_id' (the alias)


PROPERTY PATTERN: Convenience access to nested fields
------------------------------------------------------

The @property decorators provide convenient access to frequently-used nested fields:

    # Instead of:
    if paper.metadata.study_type == "rct":
        ...

    # You can write:
    if paper.study_type == "rct":
        ...

    # Both work!  The property just makes it more convenient.
"""


#############################################


class Author(BaseModel):
    """
    Represents a researcher or author of scientific publications.

    Attributes:
        orcid: ORCID identifier (unique researcher ID)
        name: Full name of the researcher
        affiliations: List of institutional affiliations
        h_index: Citation metric indicating research impact

    Example:
        >>> author = Author(
        ...     orcid="0000-0001-2345-6789",
        ...     name="Jane Smith",
        ...     affiliations=["Harvard Medical School", "Massachusetts General Hospital"],
        ...     h_index=45
        ... )
    """

    model_config = ConfigDict(use_enum_values=True)

    orcid: str  # ORCID identifier
    name: str  # Full name
    affiliations: list[str] = Field(default_factory=list)  # Institutions
    h_index: int | None = None  # Citation metric


class ClinicalTrial(BaseModel):
    """
    Represents a clinical trial registered on ClinicalTrials.gov.

    Attributes:
        nct_id: ClinicalTrials.gov identifier (e.g., "NCT01234567")
        title: Official trial title
        phase: Trial phase (I, II, III, IV)
        status: Current status (recruiting, completed, terminated, etc.)
        intervention: Description of treatment being tested

    Example:
        >>> trial = ClinicalTrial(
        ...     nct_id="NCT01234567",
        ...     title="Study of Drug X in Patients with Disease Y",
        ...     phase="III",
        ...     status="completed",
        ...     intervention="Drug X 100mg daily"
        ... )
    """

    model_config = ConfigDict(use_enum_values=True)

    nct_id: str  # ClinicalTrials.gov identifier
    title: str  # Trial title
    phase: Literal["I", "II", "III", "IV"] | None = None
    status: str | None = None  # recruiting, completed, etc.
    intervention: str | None = None  # Treatment being tested


# ============================================================================
# Scientific Method Entities (Ontology-Based)
# ============================================================================


class Hypothesis(BaseMedicalEntity):
    """
    Represents a scientific hypothesis tracked across the literature.

    Uses IAO (Information Artifact Ontology) for standardized representation
    of hypotheses as information content entities. Enables tracking of
    hypothesis evolution: from proposal through testing to acceptance/refutation.

    Attributes:
        iao_id: IAO identifier (typically IAO:0000018 for hypothesis)
        sepio_id: SEPIO identifier for assertions (SEPIO:0000001)
        proposed_by: Paper ID where hypothesis was first proposed
        proposed_date: Date when hypothesis was first proposed
        status: Current status (proposed, supported, controversial, refuted)
        description: Natural language description of the hypothesis
        predicts: List of entity IDs that this hypothesis predicts outcomes for

    Example:
        >>> hypothesis = Hypothesis(
        ...     entity_id="HYPOTHESIS:amyloid_cascade_alzheimers",
        ...     name="Amyloid Cascade Hypothesis",
        ...     iao_id="IAO:0000018",
        ...     sepio_id="SEPIO:0000001",
        ...     proposed_by="PMC123456",
        ...     proposed_date="1992",
        ...     status="controversial",
        ...     description="Beta-amyloid accumulation drives Alzheimer's disease pathology",
        ...     predicts=["C0002395"]  # Alzheimer's disease
        ... )
    """

    entity_type: Literal[EntityType.HYPOTHESIS] = EntityType.HYPOTHESIS
    iao_id: str | None = None  # IAO:0000018 (hypothesis)
    sepio_id: str | None = None  # SEPIO:0000001 (assertion)
    proposed_by: str | None = None  # Paper ID
    proposed_date: str | None = None  # ISO date
    status: Literal["proposed", "supported", "controversial", "refuted"] | None = None
    description: str | None = None  # Natural language description
    predicts: list[str] = Field(default_factory=list)  # Entity IDs


class StudyDesign(BaseMedicalEntity):
    """
    Represents a study design or experimental protocol.

    Uses OBI (Ontology for Biomedical Investigations) to standardize
    study design classifications. Enables filtering by evidence quality
    based on study design.

    Attributes:
        obi_id: OBI identifier for study design type
        stato_id: STATO identifier for study design (if applicable)
        design_type: Human-readable design type
        description: Description of the study design
        evidence_level: Quality level (1-5, where 1 is highest quality)

    Example:
        >>> rct = StudyDesign(
        ...     entity_id="OBI:0000008",
        ...     name="Randomized Controlled Trial",
        ...     obi_id="OBI:0000008",
        ...     stato_id="STATO:0000402",
        ...     design_type="interventional",
        ...     evidence_level=1
        ... )
    """

    entity_type: Literal[EntityType.STUDY_DESIGN] = EntityType.STUDY_DESIGN
    obi_id: str | None = None  # OBI study design ID
    stato_id: str | None = None  # STATO study design ID
    design_type: str | None = None  # interventional, observational, etc.
    description: str | None = None
    evidence_level: int | None = Field(None, ge=1, le=5)  # 1=highest quality


class StatisticalMethod(BaseMedicalEntity):
    """
    Represents a statistical method or test used in analysis.

    Uses STATO (Statistics Ontology) to standardize statistical method
    classifications. Enables tracking of analytical approaches across studies.

    Attributes:
        stato_id: STATO identifier for the statistical method
        method_type: Category of method (hypothesis_test, regression, etc.)
        description: Description of the method
        assumptions: Key assumptions of the method

    Example:
        >>> ttest = StatisticalMethod(
        ...     entity_id="STATO:0000288",
        ...     name="Student's t-test",
        ...     stato_id="STATO:0000288",
        ...     method_type="hypothesis_test",
        ...     description="Parametric test comparing means of two groups"
        ... )
    """

    entity_type: Literal[EntityType.STATISTICAL_METHOD] = EntityType.STATISTICAL_METHOD
    stato_id: str | None = None  # STATO ID
    method_type: str | None = None  # hypothesis_test, regression, etc.
    description: str | None = None
    assumptions: list[str] = Field(default_factory=list)  # Method assumptions


class EvidenceLine(BaseMedicalEntity):
    """
    Represents a line of evidence using SEPIO framework.

    Uses SEPIO (Scientific Evidence and Provenance Information Ontology)
    to represent structured evidence chains. Links evidence items to
    assertions they support or refute.

    Attributes:
        sepio_type: SEPIO evidence line type ID
        eco_type: ECO evidence type ID
        assertion_id: ID of the assertion this evidence supports
        supports: List of hypothesis IDs this evidence supports
        refutes: List of hypothesis IDs this evidence refutes
        evidence_items: List of paper IDs providing evidence
        strength: Evidence strength classification
        provenance: Provenance information

    Example:
        >>> evidence = EvidenceLine(
        ...     entity_id="EVIDENCE_LINE:olaparib_brca_001",
        ...     name="Clinical evidence for Olaparib in BRCA-mutated breast cancer",
        ...     sepio_type="SEPIO:0000084",
        ...     eco_type="ECO:0007673",
        ...     assertion_id="ASSERTION:olaparib_brca",
        ...     supports=["HYPOTHESIS:parp_inhibitor_synthetic_lethality"],
        ...     evidence_items=["PMC999888", "PMC888777"],
        ...     strength="strong"
        ... )
    """

    entity_type: Literal[EntityType.EVIDENCE_LINE] = EntityType.EVIDENCE_LINE
    sepio_type: str | None = None  # SEPIO evidence line type
    eco_type: str | None = None  # ECO evidence type
    assertion_id: str | None = None  # Assertion this supports
    supports: list[str] = Field(default_factory=list)  # Hypothesis IDs
    refutes: list[str] = Field(default_factory=list)  # Hypothesis IDs
    evidence_items: list[str] = Field(default_factory=list)  # Paper IDs
    strength: Literal["strong", "moderate", "weak"] | None = None
    provenance: str | None = None  # Provenance information


# ============================================================================
# Evidence and Measurement Classes
# ============================================================================


class EvidenceItem(BaseModel):
    """
    Detailed evidence for a relationship extracted from a paper.

    Combines lightweight paper tracking with rich provenance when needed.
    Supports both simple paper ID references and detailed text span tracking
    with extraction metadata. Enhanced with ontology references (ECO, OBI, STATO)
    for standardized evidence classification.

    Attributes:
        paper_id: PMC ID of the source paper
        confidence: Confidence score for this evidence (0.0-1.0)
        section_type: Section where evidence was found
        paragraph_idx: Paragraph index within the section
        sentence_idx: Sentence index within the paragraph
        text_span: Actual text where the relationship was found
        extraction_method: Method used to extract this relationship
        study_type: Type of study in the source paper
        sample_size: Number of subjects in the study
        publication_date: When the paper was published
        eco_type: ECO (Evidence & Conclusion Ontology) evidence type ID
        obi_study_design: OBI (Ontology for Biomedical Investigations) study design ID
        stato_methods: List of STATO statistical method IDs used in the study

    Example:
        >>> evidence = EvidenceItem(
        ...     paper_id="PMC999",
        ...     section_type="results",
        ...     paragraph_idx=5,
        ...     text_span="Olaparib showed significant efficacy in BRCA-mutated breast cancer",
        ...     study_type="rct",
        ...     sample_size=302,
        ...     confidence=0.9,
        ...     eco_type="ECO:0007673",  # RCT evidence
        ...     obi_study_design="OBI:0000008",  # Randomized controlled trial
        ...     stato_methods=["STATO:0000288"]  # t-test
        ... )
    """

    model_config = ConfigDict(use_enum_values=True)

    paper_id: str  # PMC ID

    # Lightweight fields (always present)
    confidence: float = Field(ge=0.0, le=1.0, default=0.5)

    # Rich provenance (optional but recommended)
    section_type: Literal["abstract", "introduction", "methods", "results", "discussion", "conclusion"] | None = None
    paragraph_idx: int | None = None
    sentence_idx: int | None = None
    text_span: str | None = None  # Actual text where found

    # Study metadata
    extraction_method: Literal["scispacy_ner", "llm", "table_parser", "pattern_match", "manual"] | None = None
    study_type: Literal["observational", "rct", "meta_analysis", "case_report", "review"] | None = None
    sample_size: int | None = None
    publication_date: str | None = None

    # Ontology references for standardized evidence classification
    eco_type: str | None = None  # ECO evidence type ID (e.g., "ECO:0007673" for RCT)
    obi_study_design: str | None = None  # OBI study design ID (e.g., "OBI:0000008" for RCT)
    stato_methods: list[str] = Field(default_factory=list)  # STATO statistical method IDs


class Measurement(BaseModel):
    """
    Quantitative measurements associated with relationships.

    Stores numerical data with appropriate metadata for statistical
    analysis and evidence quality assessment.

    Attributes:
        value: The numerical value
        unit: Unit of measurement (if applicable)
        value_type: Type of measurement (effect_size, p_value, etc.)
        p_value: Statistical significance
        confidence_interval: 95% confidence interval
        study_population: Description of study population
        measurement_context: Additional context about the measurement

    Example:
        >>> measurement = Measurement(
        ...     value=0.59,
        ...     value_type="response_rate",
        ...     p_value=0.001,
        ...     confidence_interval=(0.52, 0.66),
        ...     study_population="BRCA-mutated breast cancer patients"
        ... )
    """

    model_config = ConfigDict(use_enum_values=True)

    value: float
    unit: str | None = None
    value_type: Literal[
        "effect_size",
        "odds_ratio",
        "hazard_ratio",
        "p_value",
        "ci",
        "correlation",
        "response_rate",
        "risk_ratio",
        "penetrance",
        "sensitivity",
        "specificity",
    ]

    # Statistical context
    p_value: float | None = None
    confidence_interval: tuple[float, float] | None = None

    # Study context
    study_population: str | None = None
    measurement_context: str | None = None


# ============================================================================
# Extraction Results
# ============================================================================


class ExtractedEntity(BaseModel):
    """
    Represents a single entity mention extracted from a paper.

    Captures the exact text span where an entity was mentioned, along with
    its position and the confidence of the extraction model. Links to the
    canonical typed entity (Disease, Gene, Drug, etc.).

    Attributes:
        mention_text: Exact text as it appears in the paper (e.g., "T2DM")
        canonical_id: ID of the canonical entity (e.g., UMLS ID, HGNC ID)
        entity_type: Type of entity (disease, drug, gene, etc.)
        start_char: Character offset where mention starts
        end_char: Character offset where mention ends
        chunk_id: Identifier of the text chunk containing this mention
        confidence: Extraction confidence score (0.0-1.0)
        extraction_method: Name of the NER model used (biobert, scispacy, etc.)
    """

    model_config = ConfigDict(use_enum_values=True)

    mention_text: str  # "T2DM"
    canonical_id: str  # Links to canonical entity ID (e.g., "C0011860")
    entity_type: EntityType  # "disease"

    # Position in text
    start_char: int
    end_char: int
    chunk_id: str  # Which chunk this came from

    # Extraction metadata
    confidence: float = Field(ge=0.0, le=1.0)  # 0.0-1.0 from NER model
    extraction_method: Literal["scispacy_ner", "llm", "table_parser", "pattern_match", "manual"]


class EntityMention(BaseModel):
    """
    Aggregated view of an entity across all its mentions in a paper.

    Combines multiple ExtractedEntity instances that refer to the same
    canonical entity, providing a paper-level summary.

    Attributes:
        entity_id: Canonical entity ID (e.g., UMLS ID, HGNC ID)
        canonical_name: Normalized name of the entity
        entity_type: Type of entity (disease, drug, gene, etc.)
        mention_count: Total number of times mentioned in the paper
        mentions: List of all text variants used (e.g., ["T2DM", "type 2 diabetes"])
        chunk_ids: IDs of chunks where this entity appears
    """

    entity_id: str  # Canonical entity ID (e.g., "C0011860")
    canonical_name: str  # "Type 2 Diabetes Mellitus"
    entity_type: str
    mention_count: int  # How many times mentioned
    mentions: list[str]  # ["T2DM", "type 2 diabetes", ...]
    chunk_ids: list[str]  # Which chunks mention this entity


class Relationship(BaseModel):
    """
    Represents a relationship between two entities extracted from a paper.

    Captures semantic relationships like "Drug X treats Disease Y" with
    supporting evidence and extraction metadata.

    Attributes:
        subject_id: Canonical entity ID of the subject (e.g., RxNorm ID for drug)
        predicate: Relationship type (TREATS, CAUSES, ASSOCIATED_WITH, etc.)
        object_id: Canonical entity ID of the object (e.g., UMLS ID for disease)
        evidence_text: Sentence or paragraph supporting this relationship
        chunk_id: ID of the chunk containing the evidence
        confidence: Confidence score (0.0-1.0)
        extraction_method: How this was extracted (cooccurrence, relationship_extraction)
    """

    subject_id: str  # Canonical entity ID (e.g., "RxNorm:1187832")
    predicate: PredicateType  # "TREATS", "CAUSES", "ASSOCIATED_WITH"
    object_id: str  # Canonical entity ID (e.g., "C0006142")

    # Evidence
    evidence_text: str  # Sentence/paragraph where found
    chunk_id: str
    confidence: float = 0.5  # Start with co-occurrence confidence

    # Provenance
    extraction_method: str  # "cooccurrence", "relationship_extraction"


# ========== Paper Output ==========


class ProcessedPaper(BaseModel):
    """
    Complete processed paper ready for insertion into the knowledge graph.

    Represents the final output of the paper processing pipeline, containing
    all extracted entities, relationships, and metadata.

    Attributes:
        pmc_id: PubMed Central ID
        pmid: PubMed ID
        doi: Digital Object Identifier
        title: Paper title
        abstract: Full abstract
        authors: List of author names
        publication_date: Publication date
        journal: Journal name
        entities: All entities mentioned in the paper
        relationships: All relationships extracted from the paper
        processed_at: Timestamp when processing completed
        entity_count: Total number of unique entities
        relationship_count: Total number of relationships
        full_text: Complete paper text for indexing
    """

    # Metadata (from JATS parser)
    pmc_id: str
    pmid: str | None
    doi: str | None
    title: str
    abstract: str
    authors: list[str]
    publication_date: str | None
    journal: str

    # Extracted entities
    entities: list[EntityMention]

    # Extracted relationships
    relationships: list[Relationship]

    # Processing metadata
    processed_at: datetime = Field(default_factory=datetime.now)
    entity_count: int
    relationship_count: int

    # Full text for indexing
    full_text: str


# ========== Reference Entity Collection ==========


class EntityCollection(BaseModel):
    """
    Collection of canonical entities organized by type.

    Manages the master set of normalized entities that extracted mentions
    are linked to. Stores typed entities (Disease, Gene, Drug, etc.) with
    methods for adding, querying, and persisting the collection.

    Attributes:
        diseases: Dictionary mapping entity_id to Disease entities
        genes: Dictionary mapping entity_id to Gene entities
        drugs: Dictionary mapping entity_id to Drug entities
        proteins: Dictionary mapping entity_id to Protein entities
        symptoms: Dictionary mapping entity_id to Symptom entities
        procedures: Dictionary mapping entity_id to Procedure entities
        biomarkers: Dictionary mapping entity_id to Biomarker entities
        pathways: Dictionary mapping entity_id to Pathway entities
        hypotheses: Dictionary mapping entity_id to Hypothesis entities
        study_designs: Dictionary mapping entity_id to StudyDesign entities
        statistical_methods: Dictionary mapping entity_id to StatisticalMethod entities
        evidence_lines: Dictionary mapping entity_id to EvidenceLine entities
        version: Version identifier for the collection
        created_at: Timestamp when collection was created
    """

    diseases: dict[str, Disease] = Field(default_factory=dict)
    genes: dict[str, Gene] = Field(default_factory=dict)
    drugs: dict[str, Drug] = Field(default_factory=dict)
    proteins: dict[str, Protein] = Field(default_factory=dict)
    symptoms: dict[str, Symptom] = Field(default_factory=dict)
    procedures: dict[str, Procedure] = Field(default_factory=dict)
    biomarkers: dict[str, Biomarker] = Field(default_factory=dict)
    pathways: dict[str, Pathway] = Field(default_factory=dict)
    hypotheses: dict[str, Hypothesis] = Field(default_factory=dict)
    study_designs: dict[str, StudyDesign] = Field(default_factory=dict)
    statistical_methods: dict[str, StatisticalMethod] = Field(default_factory=dict)
    evidence_lines: dict[str, EvidenceLine] = Field(default_factory=dict)

    version: str = "v1"
    created_at: datetime = Field(default_factory=datetime.now)

    @property
    def entity_count(self) -> int:
        """Total number of entities across all types"""
        return (
            len(self.diseases)
            + len(self.genes)
            + len(self.drugs)
            + len(self.proteins)
            + len(self.symptoms)
            + len(self.procedures)
            + len(self.biomarkers)
            + len(self.pathways)
            + len(self.hypotheses)
            + len(self.study_designs)
            + len(self.statistical_methods)
            + len(self.evidence_lines)
        )

    def add_disease(self, entity: Disease):
        """Add a disease entity to the collection"""
        self.diseases[entity.entity_id] = entity

    def add_gene(self, entity: Gene):
        """Add a gene entity to the collection"""
        self.genes[entity.entity_id] = entity

    def add_drug(self, entity: Drug):
        """Add a drug entity to the collection"""
        self.drugs[entity.entity_id] = entity

    def add_protein(self, entity: Protein):
        """Add a protein entity to the collection"""
        self.proteins[entity.entity_id] = entity

    def add_hypothesis(self, entity: Hypothesis):
        """Add a hypothesis entity to the collection"""
        self.hypotheses[entity.entity_id] = entity

    def add_study_design(self, entity: StudyDesign):
        """Add a study design entity to the collection"""
        self.study_designs[entity.entity_id] = entity

    def add_statistical_method(self, entity: StatisticalMethod):
        """Add a statistical method entity to the collection"""
        self.statistical_methods[entity.entity_id] = entity

    def add_evidence_line(self, entity: EvidenceLine):
        """Add an evidence line entity to the collection"""
        self.evidence_lines[entity.entity_id] = entity

    def get_by_id(self, entity_id: str) -> BaseMedicalEntity | None:
        """Get entity by ID, searching across all types"""
        collections_to_search: list[dict[str, BaseMedicalEntity]] = [
            cast(dict[str, BaseMedicalEntity], self.diseases),
            cast(dict[str, BaseMedicalEntity], self.genes),
            cast(dict[str, BaseMedicalEntity], self.drugs),
            cast(dict[str, BaseMedicalEntity], self.proteins),
            cast(dict[str, BaseMedicalEntity], self.symptoms),
            cast(dict[str, BaseMedicalEntity], self.procedures),
            cast(dict[str, BaseMedicalEntity], self.biomarkers),
            cast(dict[str, BaseMedicalEntity], self.pathways),
            cast(dict[str, BaseMedicalEntity], self.hypotheses),
            cast(dict[str, BaseMedicalEntity], self.study_designs),
            cast(dict[str, BaseMedicalEntity], self.statistical_methods),
            cast(dict[str, BaseMedicalEntity], self.evidence_lines),
        ]
        for collection in collections_to_search:
            if entity_id in collection:
                return collection[entity_id]
        return None

    def get_by_umls(self, umls_id: str) -> Disease | None:
        """Get disease by UMLS ID"""
        diseases: dict[str, Disease] = self.diseases
        for entity in diseases.values():  # pylint: disable=no-member
            if entity.umls_id == umls_id:
                return entity
        return None

    def get_by_hgnc(self, hgnc_id: str) -> Gene | None:
        """Get gene by HGNC ID"""
        genes: dict[str, Gene] = self.genes
        for entity in genes.values():  # pylint: disable=no-member
            if entity.hgnc_id == hgnc_id:
                return entity
        return None

    def save(self, path: str):
        """Save to JSONL with type information"""
        with open(path, "w") as f:
            for entity_type, collection in [
                ("disease", self.diseases),
                ("gene", self.genes),
                ("drug", self.drugs),
                ("protein", self.proteins),
                ("symptom", self.symptoms),
                ("procedure", self.procedures),
                ("biomarker", self.biomarkers),
                ("pathway", self.pathways),
                ("hypothesis", self.hypotheses),
                ("study_design", self.study_designs),
                ("statistical_method", self.statistical_methods),
                ("evidence_line", self.evidence_lines),
            ]:
                for entity in cast(dict[str, BaseMedicalEntity], collection).values():
                    data = entity.model_dump()
                    # Convert datetime to ISO string for JSON serialization
                    if isinstance(data.get("created_at"), datetime):
                        data["created_at"] = data["created_at"].isoformat()
                    record = {"type": entity_type, "data": data}
                    f.write(json.dumps(record) + "\n")

    @classmethod
    def load(cls, path: str) -> "EntityCollection":
        """Load from JSONL with type information"""
        collection = cls()

        with open(path) as f:
            for line in f:
                record = json.loads(line)
                entity_type = record["type"]
                data = record["data"]
                entity: BaseMedicalEntity | None = None

                if entity_type == "disease":
                    entity = Disease.model_validate(data)
                    collection.diseases[entity.entity_id] = entity
                elif entity_type == "gene":
                    entity = Gene.model_validate(data)
                    collection.genes[entity.entity_id] = entity
                elif entity_type == "drug":
                    entity = Drug.model_validate(data)
                    collection.drugs[entity.entity_id] = entity
                elif entity_type == "protein":
                    entity = Protein.model_validate(data)
                    collection.proteins[entity.entity_id] = entity
                elif entity_type == "symptom":
                    entity = Symptom.model_validate(data)
                    collection.symptoms[entity.entity_id] = entity
                elif entity_type == "procedure":
                    entity = Procedure.model_validate(data)
                    collection.procedures[entity.entity_id] = entity
                elif entity_type == "biomarker":
                    entity = Biomarker.model_validate(data)
                    collection.biomarkers[entity.entity_id] = entity
                elif entity_type == "pathway":
                    entity = Pathway.model_validate(data)
                    collection.pathways[entity.entity_id] = entity
                elif entity_type == "hypothesis":
                    entity = Hypothesis.model_validate(data)
                    collection.hypotheses[entity.entity_id] = entity
                elif entity_type == "study_design":
                    entity = StudyDesign.model_validate(data)
                    collection.study_designs[entity.entity_id] = entity
                elif entity_type == "statistical_method":
                    entity = StatisticalMethod.model_validate(data)
                    collection.statistical_methods[entity.entity_id] = entity
                elif entity_type == "evidence_line":
                    entity = EvidenceLine.model_validate(data)
                    collection.evidence_lines[entity.entity_id] = entity

        return collection

    def find_by_embedding(self, query_embedding: list[float], top_k: int = 5, threshold: float = 0.85) -> list[tuple[BaseMedicalEntity, float]]:
        """
        Find entities similar to query embedding.
        Returns list of (entity, similarity_score) tuples.
        """
        from numpy import dot
        from numpy.linalg import norm

        results = []

        collections_to_search: list[dict[str, BaseMedicalEntity]] = [
            cast(dict[str, BaseMedicalEntity], self.diseases),
            cast(dict[str, BaseMedicalEntity], self.genes),
            cast(dict[str, BaseMedicalEntity], self.drugs),
            cast(dict[str, BaseMedicalEntity], self.proteins),
        ]
        for collection_dict in collections_to_search:
            for entity in collection_dict.values():
                if entity.embedding is None:
                    continue

                # Cosine similarity
                similarity = dot(query_embedding, entity.embedding) / (norm(query_embedding) * norm(entity.embedding))

                if similarity >= threshold:
                    results.append((entity, similarity))

        # Sort by similarity
        results.sort(key=lambda x: x[1], reverse=True)
        return results[:top_k]


# =====================


def generate_embeddings_for_entities(collection: EntityCollection, embedding_function, batch_size: int = 25) -> EntityCollection:
    """
    Generate embeddings for all entities across all types.

    Args:
        collection: EntityCollection to process
        embedding_function: Callable that takes text and returns embedding vector
        batch_size: Number of entities to process in each batch

    Returns:
        Updated EntityCollection with embeddings

    Example:
        >>> def my_embedding_fn(text: str) -> List[float]:
        ...     # Use your preferred embedding model
        ...     return model.encode(text)
        >>> collection = generate_embeddings_for_entities(collection, my_embedding_fn)
    """

    entities_to_process = []
    collections_to_process: list[dict[str, BaseMedicalEntity]] = [
        cast(dict[str, BaseMedicalEntity], collection.diseases),
        cast(dict[str, BaseMedicalEntity], collection.genes),
        cast(dict[str, BaseMedicalEntity], collection.drugs),
        cast(dict[str, BaseMedicalEntity], collection.proteins),
        cast(dict[str, BaseMedicalEntity], collection.symptoms),
        cast(dict[str, BaseMedicalEntity], collection.procedures),
        cast(dict[str, BaseMedicalEntity], collection.biomarkers),
        cast(dict[str, BaseMedicalEntity], collection.pathways),
        cast(dict[str, BaseMedicalEntity], collection.hypotheses),
        cast(dict[str, BaseMedicalEntity], collection.study_designs),
        cast(dict[str, BaseMedicalEntity], collection.statistical_methods),
        cast(dict[str, BaseMedicalEntity], collection.evidence_lines),
    ]
    for entity_collection_dict in collections_to_process:
        for entity in entity_collection_dict.values():
            if entity.embedding is None:
                entities_to_process.append(entity)

    print(f"Generating embeddings for {len(entities_to_process)} entities...")

    for i in tqdm(range(0, len(entities_to_process), batch_size)):
        batch = entities_to_process[i : i + batch_size]

        for entity in batch:
            # Combine name, synonyms, and abbreviations for richer embedding
            text = entity.name
            if entity.synonyms:
                text += " " + " ".join(entity.synonyms[:5])
            if entity.abbreviations:
                text += " " + " ".join(entity.abbreviations[:3])

            # Generate embedding using provided function
            entity.embedding = embedding_function(text)

    print(f"✓ Generated embeddings for {len(entities_to_process)} entities")
    return collection

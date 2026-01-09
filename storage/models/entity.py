"""
SQLModel-based entity schema with single table inheritance.

This module defines the **Persistence Models** used for database storage.
It maps the rich Domain Models from `med_lit_schema/entity.py` into a flattened, efficient database structure.
while preserving all the rich domain modeling from the original Pydantic schema.

Design:
- Single Entity table with polymorphic discriminator
- All entity-specific fields in one table (nullable)
- No JOINs needed for queries
- Enhanced with JSONB properties, pgvector support, and auto-updating timestamps
"""

from datetime import datetime
from enum import Enum
from typing import Optional

from sqlalchemy import Column, DateTime, Index, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import Field, SQLModel


# ============================================================================
# Enums
# ============================================================================


class EntityType(str, Enum):
    """Entity type enumeration"""

    DISEASE = "disease"
    GENE = "gene"
    DRUG = "drug"
    PROTEIN = "protein"
    MUTATION = "mutation"
    SYMPTOM = "symptom"
    PROCEDURE = "procedure"
    BIOMARKER = "biomarker"
    PATHWAY = "pathway"
    ANATOMICAL_STRUCTURE = "anatomical_structure"
    TEST = "test"
    PAPER = "paper"
    AUTHOR = "author"
    INSTITUTION = "institution"
    CLINICAL_TRIAL = "clinical_trial"
    HYPOTHESIS = "hypothesis"
    STUDY_DESIGN = "study_design"
    STATISTICAL_METHOD = "statistical_method"
    EVIDENCE_LINE = "evidence_line"


# ============================================================================
# Single Table Entity with Polymorphic Identity
# ============================================================================


class Entity(SQLModel, table=True):
    """
    Base entity table with single table inheritance.

    All medical entities (Disease, Gene, Drug, etc.) are stored in this single table.
    Entity-specific fields are nullable and only populated for relevant entity types.

    Attributes:
        id: Unique identifier (canonical ID like RxNorm:123, UMLS:C123, etc.)
        entity_type: Discriminator for polymorphic queries
        name: Primary canonical name
        canonical_id: Duplicate of ID for easy access or external ref
        properties: Dynamic properties (icd10, fda_approved, etc.) stored as JSONB
        embedding: Biomedical embeddings (e.g., PubMedBERT) - will be cast to vector(768)
        mentions: Aggregate mention count
        created_at: Timestamp when entity was added
        updated_at: Timestamp of last update (auto-updated via trigger)
        source: Origin of entity (umls, mesh, rxnorm, extracted, etc.)

        # Disease-specific fields
        umls_id: UMLS Concept ID
        mesh_id: MeSH ID
        icd10_codes: ICD-10 codes (JSON array)
        disease_category: Disease classification

        # Gene-specific fields
        symbol: Gene symbol (e.g., BRCA1)
        hgnc_id: HGNC identifier
        chromosome: Chromosomal location
        entrez_id: NCBI Gene ID

        # Drug-specific fields
        rxnorm_id: RxNorm ID
        brand_names: Brand names (JSON array)
        drug_class: Therapeutic class
        mechanism: Mechanism of action

        # Protein-specific fields
        uniprot_id: UniProt ID
        gene_id: Encoding gene ID
        function: Biological function
        pathways: Biological pathways (JSON array)

        # Mutation-specific fields
        mutation_gene_id: Associated gene
        variant_type: Type of variant
        notation: Variant notation
        consequence: Functional consequence

        # Biomarker-specific fields
        loinc_code: LOINC code
        measurement_type: Type of measurement
        normal_range: Reference values

        # Pathway-specific fields
        kegg_id: KEGG ID
        reactome_id: Reactome ID
        pathway_category: Pathway category
        genes_involved: Genes in pathway (JSON array)

        # Procedure-specific fields
        procedure_type: Procedure type
        invasiveness: Invasiveness level

        # Symptom-specific fields
        severity_scale: Severity scale
    """

    __tablename__ = "entities"

    # ========== CORE FIELDS (ALL ENTITIES) ==========

    id: str = Field(primary_key=True, description="Canonical entity ID")
    entity_type: str = Field(index=True, description="Entity type for polymorphic queries")
    name: str = Field(index=True, description="Primary canonical name")
    canonical_id: Optional[str] = Field(default=None, description="Duplicate of ID for easy access")

    # Store properties as JSONB for flexible schema
    properties: dict = Field(default_factory=dict, sa_column=Column(JSONB, nullable=False, server_default=text("'{}'::jsonb")))

    # Common entity fields stored as JSON strings
    synonyms: Optional[str] = Field(default=None, description="Synonyms (JSON array)")
    abbreviations: Optional[str] = Field(default=None, description="Abbreviations (JSON array)")

    # pgvector embedding - stored as TEXT, will be cast to vector(768) in database
    # The vector extension must be enabled: CREATE EXTENSION IF NOT EXISTS vector;
    embedding: Optional[str] = Field(default=None, description="Biomedical embedding vector (768-dim)")

    # Mention tracking
    mentions: int = Field(default=0, description="Aggregate mention count")

    # Metadata with auto-updating timestamps
    created_at: datetime = Field(default_factory=datetime.utcnow, sa_column=Column(DateTime(timezone=False), nullable=False, server_default=text("CURRENT_TIMESTAMP")))
    updated_at: datetime = Field(default_factory=datetime.utcnow, sa_column=Column(DateTime(timezone=False), nullable=False, server_default=text("CURRENT_TIMESTAMP")))
    source: str = Field(default="extracted", description="Origin (umls, mesh, rxnorm, etc.)")

    # ========== DISEASE-SPECIFIC FIELDS ==========

    umls_id: Optional[str] = Field(default=None, description="UMLS Concept ID")
    mesh_id: Optional[str] = Field(default=None, description="MeSH ID")
    icd10_codes: Optional[str] = Field(default=None, description="ICD-10 codes (JSON array)")
    disease_category: Optional[str] = Field(default=None, description="Disease classification")

    # ========== GENE-SPECIFIC FIELDS ==========

    symbol: Optional[str] = Field(default=None, description="Gene symbol")
    hgnc_id: Optional[str] = Field(default=None, description="HGNC ID")
    chromosome: Optional[str] = Field(default=None, description="Chromosomal location")
    entrez_id: Optional[str] = Field(default=None, description="NCBI Gene ID")

    # ========== DRUG-SPECIFIC FIELDS ==========

    rxnorm_id: Optional[str] = Field(default=None, description="RxNorm ID")
    brand_names: Optional[str] = Field(default=None, description="Brand names (JSON array)")
    drug_class: Optional[str] = Field(default=None, description="Therapeutic class")
    mechanism: Optional[str] = Field(default=None, description="Mechanism of action")

    # ========== PROTEIN-SPECIFIC FIELDS ==========

    uniprot_id: Optional[str] = Field(default=None, description="UniProt ID")
    gene_id: Optional[str] = Field(default=None, description="Encoding gene ID")
    function: Optional[str] = Field(default=None, description="Biological function")
    pathways: Optional[str] = Field(default=None, description="Pathways (JSON array)")

    # ========== MUTATION-SPECIFIC FIELDS ==========

    mutation_gene_id: Optional[str] = Field(default=None, description="Associated gene")
    variant_type: Optional[str] = Field(default=None, description="Variant type")
    notation: Optional[str] = Field(default=None, description="Variant notation")
    consequence: Optional[str] = Field(default=None, description="Functional consequence")

    # ========== BIOMARKER-SPECIFIC FIELDS ==========

    loinc_code: Optional[str] = Field(default=None, description="LOINC code")
    measurement_type: Optional[str] = Field(default=None, description="Measurement type")
    normal_range: Optional[str] = Field(default=None, description="Reference values")

    # ========== PATHWAY-SPECIFIC FIELDS ==========

    kegg_id: Optional[str] = Field(default=None, description="KEGG ID")
    reactome_id: Optional[str] = Field(default=None, description="Reactome ID")
    pathway_category: Optional[str] = Field(default=None, description="Pathway category")
    genes_involved: Optional[str] = Field(default=None, description="Genes (JSON array)")

    # ========== PROCEDURE-SPECIFIC FIELDS ==========

    procedure_type: Optional[str] = Field(default=None, description="Procedure type")
    invasiveness: Optional[str] = Field(default=None, description="Invasiveness level")

    # ========== SYMPTOM-SPECIFIC FIELDS ==========

    severity_scale: Optional[str] = Field(default=None, description="Severity scale")

    # ========== HYPOTHESIS, STUDY_DESIGN, STATISTICAL_METHOD, EVIDENCE_LINE FIELDS ==========

    description: Optional[str] = Field(default=None, description="Description for various entity types")
    predicts: Optional[str] = Field(default=None, description="Hypothesis predictions (JSON array)")

    iao_id: Optional[str] = Field(default=None, description="IAO identifier for Hypothesis")
    sepio_id: Optional[str] = Field(default=None, description="SEPIO identifier for Hypothesis or EvidenceLine")
    proposed_by: Optional[str] = Field(default=None, description="Paper ID where Hypothesis was proposed")
    proposed_date: Optional[str] = Field(default=None, description="Date when Hypothesis was proposed (ISO date string)")
    status: Optional[str] = Field(default=None, description="Status of Hypothesis (proposed, supported, controversial, refuted)")

    obi_id: Optional[str] = Field(default=None, description="OBI identifier for StudyDesign")
    stato_id: Optional[str] = Field(default=None, description="STATO identifier for StudyDesign or StatisticalMethod")
    design_type: Optional[str] = Field(default=None, description="Design type of StudyDesign (interventional, observational, etc.)")
    evidence_level: Optional[str] = Field(default=None, description="Evidence quality level (1-5) for StudyDesign")

    method_type: Optional[str] = Field(default=None, description="Category of StatisticalMethod (hypothesis_test, regression, etc.)")
    assumptions: Optional[str] = Field(default=None, description="Method assumptions (JSON array)")

    eco_type: Optional[str] = Field(default=None, description="ECO evidence type ID for EvidenceLine")
    assertion_id: Optional[str] = Field(default=None, description="Assertion ID this EvidenceLine supports")
    supports: Optional[str] = Field(default=None, description="Hypothesis IDs this EvidenceLine supports (JSON array)")
    refutes: Optional[str] = Field(default=None, description="Hypothesis IDs this EvidenceLine refutes (JSON array)")
    evidence_items: Optional[str] = Field(default=None, description="Paper IDs providing evidence for EvidenceLine (JSON array)")
    strength: Optional[str] = Field(default=None, description="Evidence strength classification for EvidenceLine (strong, moderate, weak)")

    # Note: Vector index for embeddings must be created separately after table creation
    # See setup_database.py: CREATE INDEX idx_entities_embedding ON entities USING hnsw (embedding vector_cosine_ops);
    __table_args__ = (
        Index("idx_entities_type", "entity_type"),
        Index("idx_entities_name", "name"),
        # Vector index requires pgvector extension and must be created via raw SQL
        # See setup_database.py for HNSW index creation
    )

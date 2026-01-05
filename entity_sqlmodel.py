"""
SQLModel-based entity schema with single table inheritance.

This module defines the **Persistence Models** used for database storage.
It maps the rich Domain Models from `schema/entity.py` into a flattened, efficient database structure.
while preserving all the rich domain modeling from the original Pydantic schema.

Design:
- Single Entity table with polymorphic discriminator
- All entity-specific fields in one table (nullable)
- No JOINs needed for queries
- Matches existing migration.sql schema
"""

from datetime import datetime
from enum import Enum
from typing import Optional

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
        synonyms: Alternative names (stored as JSON)
        abbreviations: Common abbreviations (stored as JSON)
        embedding: Pre-computed biomedical embedding vector (stored as JSON)
        created_at: Timestamp when entity was added
        updated_at: Timestamp of last update
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

    # Arrays stored as JSON
    synonyms: Optional[str] = Field(default=None, description="Alternative names (JSON array)")
    abbreviations: Optional[str] = Field(default=None, description="Common abbreviations (JSON array)")
    embedding: Optional[str] = Field(default=None, description="Embedding vector (JSON array)")

    # Metadata
    created_at: datetime = Field(default_factory=datetime.utcnow, description="Creation timestamp")
    updated_at: datetime = Field(default_factory=datetime.utcnow, description="Last update timestamp")
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
    assumptions: Optional[str] = Field(default=None, description="Method assumptions (JSON array)")
    supports: Optional[str] = Field(default=None, description="Evidence supports (JSON array)")
    refutes: Optional[str] = Field(default=None, description="Evidence refutes (JSON array)")
    evidence_items: Optional[str] = Field(default=None, description="Evidence items (JSON array)")

    # Polymorphic configuration - Removed in favor of explicit type management
    # __mapper_args__ = {"polymorphic_on": "entity_type", "polymorphic_identity": "entity"}

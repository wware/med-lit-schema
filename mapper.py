"""
Mapper functions to convert between Domain Models and Persistence Models.

This module bridges the gap between:
- Domain Models (schema/entity.py) - Rich Pydantic classes for application logic
- Persistence Models (schema/entity_sqlmodel.py) - Flattened SQLModel for database
"""

import json

from .entity import (
    BaseMedicalEntity,
    Disease,
    Gene,
    Drug,
    Protein,
    Mutation,
    Symptom,
    Biomarker,
    Pathway,
    Procedure,
    Hypothesis,
    StudyDesign,
    StatisticalMethod,
    EvidenceLine,
    EntityType,
)
from .relationship import (
    BaseRelationship,
    create_relationship,
)
from .base import PredicateType
from .entity_sqlmodel import Entity
from .relationship_sqlmodel import Relationship


def to_persistence(domain: BaseMedicalEntity) -> Entity:
    """
    Convert a domain model to a persistence model for database storage.

    Args:
        domain: Any domain entity (Disease, Gene, Drug, etc.)

    Returns:
        Flattened Entity model ready for database insertion

    Example:
        >>> disease = Disease(
        ...     entity_id="C0006142",
        ...     entity_type=EntityType.DISEASE,
        ...     name="Breast Cancer",
        ...     synonyms=["Breast Carcinoma"],
        ...     umls_id="C0006142"
        ... )
        >>> entity = to_persistence(disease)
        >>> entity.entity_type == "disease"
        True
    """
    # Common fields for all entities
    base_data = {
        "id": domain.entity_id,
        "entity_type": (domain.entity_type.value if hasattr(domain.entity_type, "value") else domain.entity_type),
        "name": domain.name,
        "synonyms": json.dumps(domain.synonyms) if domain.synonyms else None,
        "abbreviations": (json.dumps(domain.abbreviations) if domain.abbreviations else None),
        "embedding": json.dumps(domain.embedding) if domain.embedding else None,
        "created_at": domain.created_at,
        "source": domain.source,
    }

    # Type-specific fields
    if isinstance(domain, Disease):
        base_data.update(
            {
                "umls_id": domain.umls_id,
                "mesh_id": domain.mesh_id,
                "icd10_codes": (json.dumps(domain.icd10_codes) if domain.icd10_codes else None),
                "disease_category": domain.category,
            }
        )
    elif isinstance(domain, Gene):
        base_data.update(
            {
                "symbol": domain.symbol,
                "hgnc_id": domain.hgnc_id,
                "chromosome": domain.chromosome,
                "entrez_id": domain.entrez_id,
            }
        )
    elif isinstance(domain, Drug):
        base_data.update(
            {
                "rxnorm_id": domain.rxnorm_id,
                "brand_names": (json.dumps(domain.brand_names) if domain.brand_names else None),
                "drug_class": domain.drug_class,
                "mechanism": domain.mechanism,
            }
        )
    elif isinstance(domain, Protein):
        base_data.update(
            {
                "uniprot_id": domain.uniprot_id,
                "gene_id": domain.gene_id,
                "function": domain.function,
                "pathways": json.dumps(domain.pathways) if domain.pathways else None,
            }
        )
    elif isinstance(domain, Mutation):
        base_data.update(
            {
                "mutation_gene_id": domain.gene_id,
                "variant_type": domain.variant_type,
                "notation": domain.notation,
                "consequence": domain.consequence,
            }
        )
    elif isinstance(domain, Symptom):
        base_data.update(
            {
                "severity_scale": domain.severity_scale,
            }
        )
    elif isinstance(domain, Procedure):
        base_data.update(
            {
                "procedure_type": domain.type,
                "invasiveness": domain.invasiveness,
            }
        )
    elif isinstance(domain, Biomarker):
        base_data.update(
            {
                "loinc_code": domain.loinc_code,
                "measurement_type": domain.measurement_type,
                "normal_range": domain.normal_range,
            }
        )
    elif isinstance(domain, Pathway):
        base_data.update(
            {
                "kegg_id": domain.kegg_id,
                "reactome_id": domain.reactome_id,
                "pathway_category": domain.category,
                "genes_involved": (json.dumps(domain.genes_involved) if domain.genes_involved else None),
            }
        )
    elif isinstance(domain, Hypothesis):
        base_data.update(
            {
                "description": domain.description,
                "predicts": json.dumps(domain.predicts) if domain.predicts else None,
            }
        )
    elif isinstance(domain, StudyDesign):
        base_data.update(
            {
                "description": domain.description,
            }
        )
    elif isinstance(domain, StatisticalMethod):
        base_data.update(
            {
                "description": domain.description,
                "assumptions": (json.dumps(domain.assumptions) if domain.assumptions else None),
            }
        )
    elif isinstance(domain, EvidenceLine):
        base_data.update(
            {
                "supports": json.dumps(domain.supports) if domain.supports else None,
                "refutes": json.dumps(domain.refutes) if domain.refutes else None,
                "evidence_items": (json.dumps(domain.evidence_items) if domain.evidence_items else None),
            }
        )

    return Entity(**base_data)


def to_domain(persistence: Entity) -> BaseMedicalEntity:
    """
    Convert a persistence model back to a domain model.

    Args:
        persistence: Flattened Entity from database

    Returns:
        Rich domain model (Disease, Gene, Drug, etc.)

    Example:
        >>> entity = Entity(
        ...     id="C0006142",
        ...     entity_type="disease",
        ...     name="Breast Cancer",
        ...     umls_id="C0006142"
        ... )
        >>> disease = to_domain(entity)
        >>> isinstance(disease, Disease)
        True
    """
    # Parse common JSON fields
    synonyms = json.loads(persistence.synonyms) if persistence.synonyms else []
    abbreviations = json.loads(persistence.abbreviations) if persistence.abbreviations else []
    embedding = json.loads(persistence.embedding) if persistence.embedding else None

    # Common fields
    base_data = {
        "entity_id": persistence.id,
        "entity_type": persistence.entity_type,
        "name": persistence.name,
        "synonyms": synonyms,
        "abbreviations": abbreviations,
        "embedding": embedding,
        "created_at": persistence.created_at,
        "source": persistence.source,
    }

    # Polymorphic conversion based on entity_type
    entity_type_str = persistence.entity_type.value if isinstance(persistence.entity_type, EntityType) else persistence.entity_type
    if entity_type_str == EntityType.DISEASE.value:
        return Disease(
            **base_data,
            umls_id=persistence.umls_id,
            mesh_id=persistence.mesh_id,
            icd10_codes=(json.loads(persistence.icd10_codes) if persistence.icd10_codes else []),
            category=persistence.disease_category,
        )
    elif entity_type_str == EntityType.GENE.value:
        return Gene(
            **base_data,
            symbol=persistence.symbol,
            hgnc_id=persistence.hgnc_id,
            chromosome=persistence.chromosome,
            entrez_id=persistence.entrez_id,
        )
    elif entity_type_str == EntityType.DRUG.value:
        return Drug(
            **base_data,
            rxnorm_id=persistence.rxnorm_id,
            brand_names=(json.loads(persistence.brand_names) if persistence.brand_names else []),
            drug_class=persistence.drug_class,
            mechanism=persistence.mechanism,
        )
    elif entity_type_str == EntityType.PROTEIN.value:
        return Protein(
            **base_data,
            uniprot_id=persistence.uniprot_id,
            gene_id=persistence.gene_id,
            function=persistence.function,
            pathways=json.loads(persistence.pathways) if persistence.pathways else [],
        )
    elif entity_type_str == EntityType.MUTATION.value:
        return Mutation(
            **base_data,
            gene_id=persistence.mutation_gene_id,
            variant_type=persistence.variant_type,
            notation=persistence.notation,
            consequence=persistence.consequence,
        )
    elif entity_type_str == EntityType.SYMPTOM.value:
        return Symptom(
            **base_data,
            severity_scale=persistence.severity_scale,
        )
    elif entity_type_str == EntityType.PROCEDURE.value:
        return Procedure(
            **base_data,
            type=persistence.procedure_type,
            invasiveness=persistence.invasiveness,
        )
    elif entity_type_str == EntityType.BIOMARKER.value:
        return Biomarker(
            **base_data,
            loinc_code=persistence.loinc_code,
            measurement_type=persistence.measurement_type,
            normal_range=persistence.normal_range,
        )
    elif entity_type_str == EntityType.PATHWAY.value:
        return Pathway(
            **base_data,
            kegg_id=persistence.kegg_id,
            reactome_id=persistence.reactome_id,
            category=persistence.pathway_category,
            genes_involved=(json.loads(persistence.genes_involved) if persistence.genes_involved else []),
        )
    elif entity_type_str == EntityType.HYPOTHESIS.value:
        return Hypothesis(
            **base_data,
            description=persistence.description,
            predicts=json.loads(persistence.predicts) if persistence.predicts else [],
        )
    elif entity_type_str == EntityType.STUDY_DESIGN.value:
        return StudyDesign(
            **base_data,
            description=persistence.description,
        )
    elif entity_type_str == EntityType.STATISTICAL_METHOD.value:
        return StatisticalMethod(
            **base_data,
            description=persistence.description,
            assumptions=(json.loads(persistence.assumptions) if persistence.assumptions else []),
        )
    elif entity_type_str == EntityType.EVIDENCE_LINE.value:
        return EvidenceLine(
            **base_data,
            supports=json.loads(persistence.supports) if persistence.supports else [],
            refutes=json.loads(persistence.refutes) if persistence.refutes else [],
            evidence_items=(json.loads(persistence.evidence_items) if persistence.evidence_items else []),
        )
    else:
        raise ValueError(f"Unknown entity type: {persistence.entity_type}")


# Convenience functions for batch operations
def to_persistence_batch(domains: list[BaseMedicalEntity]) -> list[Entity]:
    """Convert multiple domain models to persistence models."""
    return [to_persistence(d) for d in domains]


def to_domain_batch(persistences: list[Entity]) -> list[BaseMedicalEntity]:
    """Convert multiple persistence models to domain models."""
    return [to_domain(p) for p in persistences]


def relationship_to_persistence(domain: BaseRelationship) -> Relationship:
    """
    Convert a domain relationship to a persistence model.
    """
    persistence_data = {}
    domain_data = domain.model_dump()
    for key in Relationship.model_fields:
        if key in domain_data:
            value = domain_data[key]
            if isinstance(value, list):
                persistence_data[key] = json.dumps(value) if value else None
            elif hasattr(value, "value"):
                persistence_data[key] = value.value
            else:
                persistence_data[key] = value
    return Relationship(**persistence_data)


def relationship_to_domain(persistence: Relationship) -> BaseRelationship:
    """
    Convert a persistence relationship back to a domain model.
    """
    domain_data = {}
    persistence_data = persistence.model_dump()

    # Find the correct predicate enum member
    predicate_value = persistence.predicate
    try:
        predicate = PredicateType(predicate_value)
    except ValueError as e:
        raise ValueError(f"Unknown predicate type: {predicate_value}") from e

    domain_data["predicate"] = predicate

    # Get the correct class to deserialize into
    cls = create_relationship(predicate, "", "").__class__

    for key, field in cls.model_fields.items():
        if key in persistence_data:
            value = persistence_data[key]
            if field.annotation == list[str] and value and isinstance(value, str):
                domain_data[key] = json.loads(value)
            else:
                domain_data[key] = value

    return create_relationship(**domain_data)

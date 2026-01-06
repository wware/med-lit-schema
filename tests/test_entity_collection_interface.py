"""Tests for EntityCollectionInterface and InMemoryEntityCollection."""

from schema.entity import (
    EntityCollectionInterface,
    InMemoryEntityCollection,
    EntityCollection,
    Disease,
    Gene,
    Drug,
    Protein,
    Hypothesis,
    StudyDesign,
    StatisticalMethod,
    EvidenceLine,
)


def test_interface_can_be_imported():
    """Verify EntityCollectionInterface can be imported."""
    assert EntityCollectionInterface is not None


def test_inmemory_collection_exists():
    """Verify InMemoryEntityCollection can be imported."""
    assert InMemoryEntityCollection is not None


def test_backward_compatibility_alias():
    """Verify EntityCollection is an alias for InMemoryEntityCollection."""
    assert EntityCollection is InMemoryEntityCollection


def test_inmemory_collection_implements_interface():
    """Verify InMemoryEntityCollection inherits from EntityCollectionInterface."""
    assert issubclass(InMemoryEntityCollection, EntityCollectionInterface)


def test_interface_defines_required_methods():
    """Verify EntityCollectionInterface defines all required abstract methods."""
    required_methods = [
        "add_disease",
        "add_gene",
        "add_drug",
        "add_protein",
        "add_hypothesis",
        "add_study_design",
        "add_statistical_method",
        "add_evidence_line",
        "get_by_id",
        "get_by_umls",
        "get_by_hgnc",
        "find_by_embedding",
    ]

    for method in required_methods:
        assert hasattr(EntityCollectionInterface, method), f"Interface missing {method}"


def test_interface_defines_entity_count_property():
    """Verify EntityCollectionInterface defines entity_count property."""
    assert hasattr(EntityCollectionInterface, "entity_count")


def test_inmemory_collection_can_be_instantiated():
    """Verify InMemoryEntityCollection can be created and used."""
    collection = InMemoryEntityCollection()

    # Add entities
    disease = Disease(entity_id="C0001", name="Test Disease", entity_type="disease")
    gene = Gene(entity_id="G0001", name="Test Gene", entity_type="gene")

    collection.add_disease(disease)
    collection.add_gene(gene)

    # Verify entity_count
    assert collection.entity_count == 2

    # Verify get_by_id
    retrieved_disease = collection.get_by_id("C0001")
    assert retrieved_disease is not None
    assert retrieved_disease.name == "Test Disease"

    retrieved_gene = collection.get_by_id("G0001")
    assert retrieved_gene is not None
    assert retrieved_gene.name == "Test Gene"


def test_backward_compatibility_with_alias():
    """Verify existing code using EntityCollection continues to work."""
    # This simulates existing code that uses EntityCollection
    collection = EntityCollection()

    disease = Disease(entity_id="C0002", name="Legacy Disease", entity_type="disease")
    collection.add_disease(disease)

    assert collection.entity_count == 1
    assert collection.get_by_id("C0002") is not None


def test_interface_type_annotations():
    """Verify that InMemoryEntityCollection can be used with interface type hints."""

    def process_collection(coll: EntityCollectionInterface):
        """Function that accepts any EntityCollectionInterface implementation."""
        disease = Disease(entity_id="C0003", name="Typed Disease", entity_type="disease")
        coll.add_disease(disease)
        return coll.entity_count

    # Test with InMemoryEntityCollection
    collection = InMemoryEntityCollection()
    count = process_collection(collection)
    assert count == 1

    # Test with backward compatibility alias
    legacy_collection = EntityCollection()
    count = process_collection(legacy_collection)
    assert count == 1


def test_all_entity_types_supported():
    """Verify all entity types can be added through the interface."""
    collection = InMemoryEntityCollection()

    # Create one of each entity type
    disease = Disease(entity_id="D001", name="Disease", entity_type="disease")
    gene = Gene(entity_id="G001", name="Gene", entity_type="gene")
    drug = Drug(entity_id="R001", name="Drug", entity_type="drug")
    protein = Protein(entity_id="P001", name="Protein", entity_type="protein")
    hypothesis = Hypothesis(
        entity_id="H001",
        name="Hypothesis",
        entity_type="hypothesis",
        statement="Test hypothesis",
        status="proposed",
    )
    study_design = StudyDesign(
        entity_id="SD001",
        name="Study Design",
        entity_type="study_design",
        design_type="rct",
    )
    stat_method = StatisticalMethod(
        entity_id="SM001",
        name="Statistical Method",
        entity_type="statistical_method",
        method_type="t_test",
    )
    evidence_line = EvidenceLine(
        entity_id="EL001",
        name="Evidence Line",
        entity_type="evidence_line",
        evidence_type="clinical_trial",
        strength="strong",
    )

    # Add all entities
    collection.add_disease(disease)
    collection.add_gene(gene)
    collection.add_drug(drug)
    collection.add_protein(protein)
    collection.add_hypothesis(hypothesis)
    collection.add_study_design(study_design)
    collection.add_statistical_method(stat_method)
    collection.add_evidence_line(evidence_line)

    # Verify all were added
    assert collection.entity_count == 8

    # Verify each can be retrieved
    assert collection.get_by_id("D001") is not None
    assert collection.get_by_id("G001") is not None
    assert collection.get_by_id("R001") is not None
    assert collection.get_by_id("P001") is not None
    assert collection.get_by_id("H001") is not None
    assert collection.get_by_id("SD001") is not None
    assert collection.get_by_id("SM001") is not None
    assert collection.get_by_id("EL001") is not None

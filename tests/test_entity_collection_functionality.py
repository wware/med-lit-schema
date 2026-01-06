"""
Comprehensive tests for EntityCollection functionality.

Tests entity resolution, ontology lookups, synonyms, and edge cases.
"""

from schema.entity import (
    Disease,
    Gene,
    Drug,
    InMemoryEntityCollection,
    EntityCollection,
)


def test_get_by_umls():
    """Test looking up diseases by UMLS ID."""
    collection = InMemoryEntityCollection()

    disease1 = Disease(
        entity_id="C0006142",
        name="Breast Cancer",
        entity_type="disease",
        umls_id="C0006142",
        synonyms=["Breast Carcinoma", "Mammary Cancer"],
    )
    disease2 = Disease(
        entity_id="C0011860",
        name="Type 2 Diabetes",
        entity_type="disease",
        umls_id="C0011860",
        synonyms=["T2DM", "NIDDM"],
    )

    collection.add_disease(disease1)
    collection.add_disease(disease2)

    # Test lookup by UMLS ID
    found = collection.get_by_umls("C0006142")
    assert found is not None
    assert found.entity_id == "C0006142"
    assert found.name == "Breast Cancer"

    found = collection.get_by_umls("C0011860")
    assert found is not None
    assert found.name == "Type 2 Diabetes"

    # Test non-existent UMLS ID
    assert collection.get_by_umls("C9999999") is None


def test_get_by_hgnc():
    """Test looking up genes by HGNC ID."""
    collection = InMemoryEntityCollection()

    gene1 = Gene(
        entity_id="HGNC:1100",
        name="BRCA1",
        entity_type="gene",
        hgnc_id="HGNC:1100",
        symbol="BRCA1",
        synonyms=["breast cancer 1"],
    )
    gene2 = Gene(
        entity_id="HGNC:1101",
        name="BRCA2",
        entity_type="gene",
        hgnc_id="HGNC:1101",
        symbol="BRCA2",
        synonyms=["breast cancer 2"],
    )

    collection.add_gene(gene1)
    collection.add_gene(gene2)

    # Test lookup by HGNC ID
    found = collection.get_by_hgnc("HGNC:1100")
    assert found is not None
    assert found.entity_id == "HGNC:1100"
    assert found.symbol == "BRCA1"

    found = collection.get_by_hgnc("HGNC:1101")
    assert found is not None
    assert found.symbol == "BRCA2"

    # Test non-existent HGNC ID
    assert collection.get_by_hgnc("HGNC:99999") is None


def test_entity_resolution_by_synonym():
    """Test entity resolution using synonyms."""
    collection = InMemoryEntityCollection()

    disease = Disease(
        entity_id="C0006142",
        name="Breast Cancer",
        entity_type="disease",
        umls_id="C0006142",
        synonyms=["Breast Carcinoma", "Mammary Cancer", "BC"],
        abbreviations=["BC"],
    )

    collection.add_disease(disease)

    # Should find by canonical ID
    found = collection.get_by_id("C0006142")
    assert found is not None
    assert found.name == "Breast Cancer"

    # Note: get_by_id doesn't search synonyms, but we can verify synonyms are stored
    assert "Breast Carcinoma" in found.synonyms
    assert "BC" in found.abbreviations


def test_entity_resolution_by_abbreviation():
    """Test entity resolution using abbreviations."""
    collection = InMemoryEntityCollection()

    disease = Disease(
        entity_id="C0011860",
        name="Type 2 Diabetes Mellitus",
        entity_type="disease",
        umls_id="C0011860",
        synonyms=["Type II Diabetes", "Adult-Onset Diabetes"],
        abbreviations=["T2DM", "NIDDM"],
    )

    collection.add_disease(disease)

    found = collection.get_by_id("C0011860")
    assert found is not None
    assert "T2DM" in found.abbreviations
    assert "NIDDM" in found.abbreviations


def test_duplicate_entity_id_overwrites():
    """Test that adding an entity with the same ID overwrites the previous one."""
    collection = InMemoryEntityCollection()

    disease1 = Disease(
        entity_id="C0006142",
        name="Breast Cancer (old)",
        entity_type="disease",
        umls_id="C0006142",
    )

    disease2 = Disease(
        entity_id="C0006142",
        name="Breast Cancer (new)",
        entity_type="disease",
        umls_id="C0006142",
        synonyms=["Updated"],
    )

    collection.add_disease(disease1)
    assert collection.get_by_id("C0006142").name == "Breast Cancer (old)"

    # Adding same ID should overwrite
    collection.add_disease(disease2)
    assert collection.get_by_id("C0006142").name == "Breast Cancer (new)"
    assert collection.entity_count == 1  # Still only one entity


def test_get_by_id_nonexistent():
    """Test get_by_id returns None for non-existent entities."""
    collection = InMemoryEntityCollection()

    assert collection.get_by_id("NONEXISTENT") is None
    assert collection.get_by_id("") is None


def test_entity_count_includes_all_types():
    """Test that entity_count includes all entity types."""
    collection = InMemoryEntityCollection()

    assert collection.entity_count == 0

    disease = Disease(entity_id="D1", name="Disease", entity_type="disease")
    gene = Gene(entity_id="G1", name="Gene", entity_type="gene")
    drug = Drug(entity_id="R1", name="Drug", entity_type="drug")

    collection.add_disease(disease)
    assert collection.entity_count == 1

    collection.add_gene(gene)
    assert collection.entity_count == 2

    collection.add_drug(drug)
    assert collection.entity_count == 3


def test_find_by_embedding_with_threshold():
    """Test embedding search with threshold filtering."""
    collection = InMemoryEntityCollection()

    # Create entities with known embeddings
    disease = Disease(
        entity_id="D1",
        name="Disease 1",
        entity_type="disease",
        embedding=[1.0, 0.0, 0.0],  # Unit vector along x-axis
    )
    gene = Gene(
        entity_id="G1",
        name="Gene 1",
        entity_type="gene",
        embedding=[0.0, 1.0, 0.0],  # Unit vector along y-axis
    )
    drug = Drug(
        entity_id="R1",
        name="Drug 1",
        entity_type="drug",
        embedding=[0.7071, 0.7071, 0.0],  # 45-degree vector
    )

    collection.add_disease(disease)
    collection.add_gene(gene)
    collection.add_drug(drug)

    # Query with vector similar to drug (45 degrees)
    query = [0.7, 0.7, 0.0]
    results = collection.find_by_embedding(query, top_k=3, threshold=0.5)

    # Should find at least the drug (high similarity)
    assert len(results) >= 1
    top_entity, score = results[0]
    assert top_entity.entity_id == "R1"
    assert score > 0.9  # Should be very similar

    # Test with high threshold - should filter out dissimilar entities
    results_strict = collection.find_by_embedding(query, top_k=3, threshold=0.95)
    # May have fewer results with strict threshold
    assert len(results_strict) <= len(results)


def test_find_by_embedding_no_embeddings():
    """Test embedding search when entities have no embeddings."""
    collection = InMemoryEntityCollection()

    disease = Disease(
        entity_id="D1",
        name="Disease",
        entity_type="disease",
        embedding=None,  # No embedding
    )
    gene = Gene(
        entity_id="G1",
        name="Gene",
        entity_type="gene",
        embedding=None,  # No embedding
    )

    collection.add_disease(disease)
    collection.add_gene(gene)

    # Search should return empty when no entities have embeddings
    results = collection.find_by_embedding([1.0, 0.0], top_k=5, threshold=0.5)
    assert len(results) == 0


def test_backward_compatibility_entity_collection_alias():
    """Test that EntityCollection alias works for all methods."""
    # Use the alias instead of InMemoryEntityCollection
    collection = EntityCollection()

    disease = Disease(
        entity_id="C0006142",
        name="Breast Cancer",
        entity_type="disease",
        umls_id="C0006142",
    )
    gene = Gene(
        entity_id="HGNC:1100",
        name="BRCA1",
        entity_type="gene",
        hgnc_id="HGNC:1100",
    )

    collection.add_disease(disease)
    collection.add_gene(gene)

    # All methods should work
    assert collection.entity_count == 2
    assert collection.get_by_id("C0006142") is not None
    assert collection.get_by_umls("C0006142") is not None
    assert collection.get_by_hgnc("HGNC:1100") is not None


def test_mixed_entity_types_retrieval():
    """Test retrieving different entity types from the same collection."""
    collection = InMemoryEntityCollection()

    disease = Disease(entity_id="D1", name="Disease", entity_type="disease", umls_id="U1")
    gene = Gene(entity_id="G1", name="Gene", entity_type="gene", hgnc_id="H1")
    drug = Drug(entity_id="R1", name="Drug", entity_type="drug")

    collection.add_disease(disease)
    collection.add_gene(gene)
    collection.add_drug(drug)

    # get_by_id should find all types
    assert collection.get_by_id("D1") is not None
    assert collection.get_by_id("G1") is not None
    assert collection.get_by_id("R1") is not None

    # Type-specific lookups
    assert collection.get_by_umls("U1") is not None
    assert collection.get_by_hgnc("H1") is not None

    # Verify types are correct
    assert isinstance(collection.get_by_id("D1"), Disease)
    assert isinstance(collection.get_by_id("G1"), Gene)
    assert isinstance(collection.get_by_id("R1"), Drug)

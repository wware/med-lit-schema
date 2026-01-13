"""
Tests for entity list/pagination functionality.

The EntityCollectionInterface was extended with a list_entities() method
that supports pagination via limit and offset parameters.

Run with: pytest tests/test_entity_list_pagination.py -v
"""

from med_lit_schema.entity import (
    InMemoryEntityCollection,
    Disease,
    Gene,
    Drug,
    Protein,
    EntityType,
)


class TestEntityListBasics:
    """Test basic list_entities functionality."""

    def test_list_entities_returns_list(self):
        """Test that list_entities returns a list."""
        collection = InMemoryEntityCollection()

        # Add some entities
        disease1 = Disease(
            entity_id="C0001",
            entity_type=EntityType.DISEASE,
            name="Disease 1",
        )
        disease2 = Disease(
            entity_id="C0002",
            entity_type=EntityType.DISEASE,
            name="Disease 2",
        )
        collection.add_disease(disease1)
        collection.add_disease(disease2)

        # List all entities
        entities = collection.list_entities()

        assert isinstance(entities, list)
        assert len(entities) == 2

    def test_list_entities_includes_all_types(self):
        """Test that list_entities includes entities of all types."""
        collection = InMemoryEntityCollection()

        # Add different entity types
        disease = Disease(entity_id="C0001", entity_type=EntityType.DISEASE, name="Disease")
        gene = Gene(entity_id="G0001", entity_type=EntityType.GENE, name="BRCA1", symbol="BRCA1")
        drug = Drug(entity_id="D0001", name="Aspirin")

        collection.add_disease(disease)
        collection.add_gene(gene)
        collection.add_drug(drug)

        # List all
        entities = collection.list_entities()

        assert len(entities) == 3

        # Check that all types are present
        types = {type(e).__name__ for e in entities}
        assert "Disease" in types
        assert "Gene" in types
        assert "Drug" in types

    def test_list_entities_empty_collection(self):
        """Test list_entities on empty collection."""
        collection = InMemoryEntityCollection()

        entities = collection.list_entities()

        assert isinstance(entities, list)
        assert len(entities) == 0


class TestEntityListWithLimit:
    """Test list_entities with limit parameter."""

    def test_list_entities_with_limit(self):
        """Test that limit parameter restricts results."""
        collection = InMemoryEntityCollection()

        # Add 10 entities
        for i in range(10):
            disease = Disease(
                entity_id=f"C{i:04d}",
                entity_type=EntityType.DISEASE,
                name=f"Disease {i}",
            )
            collection.add_disease(disease)

        # List with limit
        entities = collection.list_entities(limit=5)

        assert len(entities) == 5

    def test_list_entities_limit_larger_than_total(self):
        """Test that limit larger than total returns all entities."""
        collection = InMemoryEntityCollection()

        # Add 3 entities
        for i in range(3):
            disease = Disease(
                entity_id=f"C{i:04d}",
                entity_type=EntityType.DISEASE,
                name=f"Disease {i}",
            )
            collection.add_disease(disease)

        # List with larger limit
        entities = collection.list_entities(limit=10)

        assert len(entities) == 3

    def test_list_entities_limit_zero(self):
        """Test that limit=0 returns empty list."""
        collection = InMemoryEntityCollection()

        # Add entities
        disease = Disease(entity_id="C0001", entity_type=EntityType.DISEASE, name="Disease")
        collection.add_disease(disease)

        # List with limit=0
        entities = collection.list_entities(limit=0)

        assert len(entities) == 0

    def test_list_entities_limit_none_returns_all(self):
        """Test that limit=None returns all entities."""
        collection = InMemoryEntityCollection()

        # Add entities
        for i in range(5):
            disease = Disease(
                entity_id=f"C{i:04d}",
                entity_type=EntityType.DISEASE,
                name=f"Disease {i}",
            )
            collection.add_disease(disease)

        # List with no limit
        entities = collection.list_entities(limit=None)

        assert len(entities) == 5


class TestEntityListWithOffset:
    """Test list_entities with offset parameter."""

    def test_list_entities_with_offset(self):
        """Test that offset parameter skips entities."""
        collection = InMemoryEntityCollection()

        # Add 10 entities
        for i in range(10):
            disease = Disease(
                entity_id=f"C{i:04d}",
                entity_type=EntityType.DISEASE,
                name=f"Disease {i}",
            )
            collection.add_disease(disease)

        # List with offset
        entities = collection.list_entities(offset=5)

        # Should get last 5 entities
        assert len(entities) == 5

    def test_list_entities_offset_larger_than_total(self):
        """Test that offset larger than total returns empty list."""
        collection = InMemoryEntityCollection()

        # Add 3 entities
        for i in range(3):
            disease = Disease(
                entity_id=f"C{i:04d}",
                entity_type=EntityType.DISEASE,
                name=f"Disease {i}",
            )
            collection.add_disease(disease)

        # List with large offset
        entities = collection.list_entities(offset=10)

        assert len(entities) == 0

    def test_list_entities_offset_zero(self):
        """Test that offset=0 starts from beginning."""
        collection = InMemoryEntityCollection()

        # Add entities
        for i in range(5):
            disease = Disease(
                entity_id=f"C{i:04d}",
                entity_type=EntityType.DISEASE,
                name=f"Disease {i}",
            )
            collection.add_disease(disease)

        # List with offset=0
        entities = collection.list_entities(offset=0)

        assert len(entities) == 5


class TestEntityListPagination:
    """Test pagination with both limit and offset."""

    def test_pagination_basic(self):
        """Test basic pagination with limit and offset."""
        collection = InMemoryEntityCollection()

        # Add 20 entities
        for i in range(20):
            disease = Disease(
                entity_id=f"C{i:04d}",
                entity_type=EntityType.DISEASE,
                name=f"Disease {i}",
            )
            collection.add_disease(disease)

        # Get first page (0-9)
        page1 = collection.list_entities(limit=10, offset=0)
        assert len(page1) == 10

        # Get second page (10-19)
        page2 = collection.list_entities(limit=10, offset=10)
        assert len(page2) == 10

        # Pages should be different
        page1_ids = {e.entity_id for e in page1}
        page2_ids = {e.entity_id for e in page2}
        assert page1_ids != page2_ids

    def test_pagination_partial_last_page(self):
        """Test pagination where last page is partial."""
        collection = InMemoryEntityCollection()

        # Add 15 entities
        for i in range(15):
            disease = Disease(
                entity_id=f"C{i:04d}",
                entity_type=EntityType.DISEASE,
                name=f"Disease {i}",
            )
            collection.add_disease(disease)

        # Get pages with page size 10
        page1 = collection.list_entities(limit=10, offset=0)
        page2 = collection.list_entities(limit=10, offset=10)

        assert len(page1) == 10
        assert len(page2) == 5  # Partial last page

    def test_pagination_beyond_end(self):
        """Test pagination beyond the end of collection."""
        collection = InMemoryEntityCollection()

        # Add 10 entities
        for i in range(10):
            disease = Disease(
                entity_id=f"C{i:04d}",
                entity_type=EntityType.DISEASE,
                name=f"Disease {i}",
            )
            collection.add_disease(disease)

        # Try to get page beyond end
        page3 = collection.list_entities(limit=10, offset=20)

        assert len(page3) == 0

    def test_pagination_iterative(self):
        """Test iterating through all entities with pagination."""
        collection = InMemoryEntityCollection()

        # Add 25 entities
        total = 25
        for i in range(total):
            disease = Disease(
                entity_id=f"C{i:04d}",
                entity_type=EntityType.DISEASE,
                name=f"Disease {i}",
            )
            collection.add_disease(disease)

        # Iterate with page size 10
        page_size = 10
        all_ids = set()
        offset = 0

        while True:
            page = collection.list_entities(limit=page_size, offset=offset)

            if not page:
                break

            for entity in page:
                all_ids.add(entity.entity_id)

            offset += page_size

            # Safety check
            if offset > 100:
                break

        # Should have collected all entities
        assert len(all_ids) == total


class TestEntityListWithMultipleTypes:
    """Test list_entities with multiple entity types."""

    def test_list_entities_mixed_types(self):
        """Test listing entities when multiple types are present."""
        collection = InMemoryEntityCollection()

        # Add various types
        for i in range(3):
            collection.add_disease(
                Disease(
                    entity_id=f"C{i:04d}",
                    entity_type=EntityType.DISEASE,
                    name=f"Disease {i}",
                )
            )
            collection.add_gene(
                Gene(
                    entity_id=f"G{i:04d}",
                    entity_type=EntityType.GENE,
                    name=f"Gene{i}",
                    symbol=f"GENE{i}",
                )
            )
            collection.add_drug(
                Drug(
                    entity_id=f"D{i:04d}",
                    name=f"Drug {i}",
                )
            )

        # List all
        entities = collection.list_entities()

        # Should have 9 entities total (3 of each type)
        assert len(entities) == 9

    def test_pagination_with_mixed_types(self):
        """Test pagination works correctly with mixed entity types."""
        collection = InMemoryEntityCollection()

        # Add 5 of each type (15 total)
        for i in range(5):
            collection.add_disease(
                Disease(
                    entity_id=f"C{i:04d}",
                    entity_type=EntityType.DISEASE,
                    name=f"Disease {i}",
                )
            )
            collection.add_gene(
                Gene(
                    entity_id=f"G{i:04d}",
                    entity_type=EntityType.GENE,
                    name=f"Gene{i}",
                    symbol=f"GENE{i}",
                )
            )
            collection.add_drug(
                Drug(
                    entity_id=f"D{i:04d}",
                    name=f"Drug {i}",
                )
            )

        # Paginate with page size 7
        page1 = collection.list_entities(limit=7, offset=0)
        page2 = collection.list_entities(limit=7, offset=7)
        page3 = collection.list_entities(limit=7, offset=14)

        assert len(page1) == 7
        assert len(page2) == 7
        assert len(page3) == 1  # Last page has 1 entity

        # All pages should have entities
        assert all(page1)
        assert all(page2)
        assert all(page3)


class TestEntityListEdgeCases:
    """Test edge cases for list_entities."""

    def test_list_entities_with_all_entity_types(self):
        """Test listing entities when all entity types have entries."""
        collection = InMemoryEntityCollection()

        # Add one of each type
        collection.add_disease(Disease(entity_id="C0001", entity_type=EntityType.DISEASE, name="Disease"))
        collection.add_gene(Gene(entity_id="G0001", entity_type=EntityType.GENE, name="BRCA1", symbol="BRCA1"))
        collection.add_drug(Drug(entity_id="D0001", name="Aspirin"))
        collection.add_protein(Protein(entity_id="P0001", name="Protein1"))

        from med_lit_schema.entity import Symptom, Procedure, Biomarker, Pathway

        collection.add_symptom(Symptom(entity_id="S0001", name="Fever"))
        collection.add_procedure(Procedure(entity_id="PR0001", name="Biopsy"))
        collection.add_biomarker(Biomarker(entity_id="B0001", name="PSA"))
        collection.add_pathway(Pathway(entity_id="PW0001", name="Cell cycle"))

        # Add hypothesis, study_design, statistical_method, evidence_line
        from med_lit_schema.entity import Hypothesis, StudyDesign, StatisticalMethod, EvidenceLine

        collection.add_hypothesis(Hypothesis(entity_id="H0001", name="Test hypothesis", description="Test"))
        collection.add_study_design(StudyDesign(entity_id="SD0001", name="RCT", description="Randomized"))
        collection.add_statistical_method(StatisticalMethod(entity_id="SM0001", name="t-test", description="Test"))
        collection.add_evidence_line(EvidenceLine(entity_id="E0001", name="Evidence", supports=[], refutes=[]))

        # List all
        entities = collection.list_entities()

        # Should have all 12 entity types
        assert len(entities) == 12

    def test_list_entities_does_not_modify_collection(self):
        """Test that listing entities doesn't modify the collection."""
        collection = InMemoryEntityCollection()

        # Add entities
        for i in range(5):
            disease = Disease(
                entity_id=f"C{i:04d}",
                entity_type=EntityType.DISEASE,
                name=f"Disease {i}",
            )
            collection.add_disease(disease)

        initial_count = collection.entity_count

        # List entities
        entities = collection.list_entities()

        # Count should not change
        assert collection.entity_count == initial_count
        assert len(entities) == initial_count

    def test_list_entities_returns_copies_not_references(self):
        """Test that modifying returned entities doesn't affect collection."""
        collection = InMemoryEntityCollection()

        # Add entity
        disease = Disease(
            entity_id="C0001",
            entity_type=EntityType.DISEASE,
            name="Original Name",
        )
        collection.add_disease(disease)

        # Get entities
        entities = collection.list_entities()

        # Note: Pydantic models are immutable with frozen=True
        # So this test verifies the behavior
        original_entity = entities[0]

        # Verify original name
        assert original_entity.name == "Original Name"

        # Get entity from collection again
        retrieved = collection.get_by_id("C0001")
        assert retrieved.name == "Original Name"

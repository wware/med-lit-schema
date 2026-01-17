# Testing

Comprehensive test strategy for the medical knowledge graph.

## Running Tests

```bash
# Run all tests
uv run pytest

# Stop on first failure
uv run pytest -x

# Run specific test file
uv run pytest tests/test_mapper.py

# Run tests matching pattern
uv run pytest -k "test_disease"

# Verbose output
uv run pytest -v

# With coverage
uv run pytest --cov=med_lit_schema
```

## Test Organization

```
tests/
├── test_schema_entity.py       # Domain model tests
├── test_mapper.py              # Entity mapper tests
├── test_relationship_mapper.py # Relationship mapper tests
├── storage/
│   ├── models/
│   │   └── test_entity.py      # Persistence model tests
│   └── backends/
│       └── test_sqlite.py      # SQLite backend tests
└── ingest/
    └── ...                     # Pipeline stage tests
```

## Test Categories

### Domain Model Tests

Test Pydantic validation and entity behavior:

```python
def test_disease_creation():
    disease = Disease(
        entity_id="C0006142",
        name="Breast Cancer",
        source="umls"
    )
    assert disease.entity_type == EntityType.DISEASE
    assert disease.name == "Breast Cancer"

def test_disease_requires_valid_fields():
    with pytest.raises(ValidationError):
        Disease(entity_id="", name="")  # Empty fields invalid
```

### Mapper Tests

Test round-trip conversion between domain and persistence:

```python
def test_disease_roundtrip():
    # Create domain model
    disease = Disease(
        entity_id="C0006142",
        name="Breast Cancer",
        synonyms=["Breast Carcinoma"],
        umls_id="C0006142"
    )

    # Convert to persistence
    persistence = to_persistence(disease)
    assert persistence.id == "C0006142"
    assert persistence.entity_type == "disease"

    # Convert back to domain
    roundtrip = to_domain(persistence)
    assert roundtrip.entity_id == disease.entity_id
    assert roundtrip.name == disease.name
    assert roundtrip.synonyms == disease.synonyms
```

### Storage Backend Tests

Test database operations:

```python
def test_sqlite_store_and_retrieve():
    storage = SQLitePipelineStorage(":memory:")

    disease = Disease(
        entity_id="C0006142",
        name="Breast Cancer"
    )
    storage.entities.add_disease(disease)

    retrieved = storage.entities.get_by_id("C0006142")
    assert retrieved.name == "Breast Cancer"
```

## Linting

```bash
# Check formatting
uv run black . --check

# Lint check
uv run ruff check .

# Auto-format
uv run black .
```

## Test Philosophy

### Provenance as Design Invariant

From `EPISTEMOLOGY_VIBES.md`: Test that queries target the correct graph layer:

```python
def test_clinical_query_targets_claim_layer():
    """Clinician queries should target claims, not extractions."""
    query = build_clinical_query()
    assert query.target_layer == Layer.CLAIM

def test_audit_query_can_reach_extraction_layer():
    """Debugging queries must be able to trace to extractions."""
    query = build_audit_query()
    assert query.can_traverse_to(Layer.EXTRACTION)
```

### Expressibility Tests

Test that certain questions CAN be expressed, not that they return specific results:

```python
def test_clinician_question_is_expressible():
    """Can we express: 'Which FDA-approved drugs treat Disease X?'"""
    query = (
        Query()
        .start(EntityType.DISEASE)
        .rel(PredicateType.TREATS)
        .to(EntityType.DRUG)
        .filter(Drug.approval_status == "FDA_APPROVED")
    )
    assert query.is_valid()
```

### Forbidden Traversals

Test that invalid operations are rejected:

```python
def test_invalid_direct_disease_to_evidence_query_fails():
    """Diseases shouldn't directly connect to evidence."""
    with pytest.raises(QueryValidationError):
        Query().start(EntityType.DISEASE).to(EntityType.EVIDENCE)
```

## Continuous Integration

Tests run automatically on:

- Pull requests
- Pushes to main branch

## Next Steps

- [Docker Setup](docker.md) - Development environment
- [Architecture](architecture.md) - Understanding the codebase

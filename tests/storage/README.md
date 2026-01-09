# Storage Layer Tests

This directory contains tests for the storage layer, organized to mirror the main storage structure.

## Test Organization

```
tests/storage/
├── backends/           # Tests for storage backend implementations
│   ├── test_sqlite.py  # SQLite backend tests
│   └── conftest.py     # Shared fixtures (to be added)
└── models/             # Tests for SQLModel persistence schemas
    └── test_entity.py  # Entity model tests
```

## Running Tests

### All Storage Tests
```bash
# Run all storage tests
pytest tests/storage/ -v

# Run with coverage
pytest tests/storage/ --cov=storage --cov-report=html
```

### Backend Tests
```bash
# All backend tests
pytest tests/storage/backends/ -v

# Specific backend
pytest tests/storage/backends/test_sqlite.py -v

# Specific test
pytest tests/storage/backends/test_sqlite.py::test_entity_storage -v
```

### Model Tests
```bash
# All model tests
pytest tests/storage/models/ -v

# Specific model
pytest tests/storage/models/test_entity.py -v
```

## Test Database Setup

### SQLite Tests

SQLite tests use in-memory databases by default, requiring no setup:

```python
@pytest.fixture
def storage():
    """Create in-memory SQLite storage for testing."""
    storage = SQLitePipelineStorage(":memory:")
    yield storage
    storage.close()
```

### PostgreSQL Tests

PostgreSQL tests require a running PostgreSQL instance with pgvector:

1. **Using Docker Compose** (recommended):
```bash
# Start PostgreSQL
docker-compose up -d postgres

# Run tests
pytest tests/storage/models/test_entity.py -v

# Stop PostgreSQL
docker-compose down
```

2. **Using Local PostgreSQL**:
```bash
# Install PostgreSQL and pgvector
sudo apt install postgresql postgresql-pgvector

# Create test database
createdb medlit_test

# Run tests with custom database URL
export DATABASE_URL="postgresql://localhost/medlit_test"
pytest tests/storage/models/test_entity.py -v
```

## Test Structure

### Backend Tests (`backends/`)

Test concrete storage implementations:

- **Connection handling**: Opening, closing, connection pooling
- **CRUD operations**: Create, read, update, delete for entities, papers, relationships
- **Query functionality**: Filtering, searching, pagination
- **Error handling**: Invalid inputs, constraint violations
- **Performance**: Bulk operations, transaction handling

**Example test:**
```python
def test_entity_storage(storage):
    """Test entity storage and retrieval."""
    disease = Disease(
        entity_id="C0006142",
        entity_type=EntityType.DISEASE,
        name="Breast Cancer"
    )
    storage.entities.add_disease(disease)
    
    retrieved = storage.entities.get_by_id("C0006142")
    assert retrieved is not None
    assert retrieved.name == "Breast Cancer"
```

### Model Tests (`models/`)

Test SQLModel schema definitions:

- **Model creation**: Valid instances, field validation
- **Database persistence**: Saving, loading from database
- **Field constraints**: Required fields, validation rules
- **Relationships**: Foreign keys, constraints
- **Special features**: JSONB fields, timestamps, indexes

**Example test:**
```python
def test_create_disease(session):
    """Test creating a disease entity in database."""
    disease = Entity(
        entity_id="C0006142",
        entity_type=EntityType.DISEASE,
        name="Breast Cancer"
    )
    session.add(disease)
    session.commit()
    
    # Verify it was saved
    result = session.exec(
        select(Entity).where(Entity.entity_id == "C0006142")
    ).first()
    assert result.name == "Breast Cancer"
```

## Writing Tests for New Backends

When implementing a new storage backend:

1. **Create test file**: `tests/storage/backends/test_mybackend.py`

2. **Use common test patterns**:
```python
import pytest
from med_lit_schema.storage.backends.mybackend import MyBackendStorage

@pytest.fixture
def storage():
    """Create storage instance for testing."""
    storage = MyBackendStorage("connection_string")
    yield storage
    storage.close()

def test_entity_storage(storage):
    """Test entity storage."""
    # ... test implementation

def test_paper_storage(storage):
    """Test paper storage."""
    # ... test implementation

def test_relationship_storage(storage):
    """Test relationship storage."""
    # ... test implementation
```

3. **Test all interface methods**: Ensure all methods from storage interfaces are tested

4. **Test backend-specific features**: Vector search, transactions, etc.

5. **Add to CI/CD**: Update `.github/workflows/` to run new tests

## Available Fixtures

### Current Fixtures

**`storage` (in test files)**:
- Creates in-memory SQLite storage
- Automatically closes after test
- Clean slate for each test

### Planned Fixtures (conftest.py)

```python
# tests/storage/backends/conftest.py

@pytest.fixture
def sqlite_storage():
    """In-memory SQLite storage."""
    storage = SQLitePipelineStorage(":memory:")
    yield storage
    storage.close()

@pytest.fixture
def sample_disease():
    """Sample disease entity."""
    return Disease(
        entity_id="C0006142",
        entity_type=EntityType.DISEASE,
        name="Breast Cancer",
        synonyms=["Breast Carcinoma"]
    )

@pytest.fixture
def sample_paper():
    """Sample paper."""
    return Paper(
        paper_id="PMC123456",
        title="Test Paper",
        abstract="Test abstract",
        authors=[{"name": "Smith J"}]
    )
```

## Test Data

### Using Small Test Data

For unit tests, use minimal data:
```python
def test_basic_storage(storage):
    disease = Disease(entity_id="C0001", name="Test Disease")
    storage.entities.add_disease(disease)
    assert storage.entities.entity_count == 1
```

### Using Realistic Test Data

For integration tests, use realistic data:
```python
def test_complete_paper_ingestion(storage):
    # Create paper with full metadata
    paper = create_test_paper_with_all_fields()
    
    # Add related entities
    entities = create_test_entities()
    for entity in entities:
        storage.entities.add_entity(entity)
    
    # Add relationships
    relationships = create_test_relationships(entities)
    for rel in relationships:
        storage.add_relationship(rel)
    
    # Verify everything is connected
    assert storage.paper_count == 1
    assert storage.entities.entity_count == len(entities)
    # ... more assertions
```

## Mocking Storage

For testing pipeline stages without database:

```python
from unittest.mock import Mock
from med_lit_schema.storage.interfaces import PipelineStorageInterface

def test_pipeline_stage():
    # Create mock storage
    mock_storage = Mock(spec=PipelineStorageInterface)
    mock_storage.entities.get_by_id.return_value = Disease(...)
    
    # Use in pipeline
    stage = MyPipelineStage(mock_storage)
    result = stage.process()
    
    # Verify interactions
    mock_storage.entities.get_by_id.assert_called_once_with("C0006142")
```

## Test Coverage

Current coverage (as of this writing):

- SQLite backend: ~90%
- Entity model: ~85%
- Other models: To be tested

**Goals:**
- Backend coverage: > 90%
- Model coverage: > 95%
- Integration tests: Full pipeline flows

**Check coverage:**
```bash
pytest tests/storage/ --cov=storage --cov-report=term --cov-report=html
open htmlcov/index.html
```

## Continuous Integration

Storage tests run automatically in CI/CD:

```yaml
# .github/workflows/test.yml
- name: Run storage tests
  run: pytest tests/storage/ -v --cov=storage
```

SQLite tests run on all commits. PostgreSQL tests may require:
- Docker service in CI
- Credentials in secrets
- Conditional execution

## Troubleshooting

### "Package not installed" error
```bash
# Install in editable mode
pip install -e .
```

### "Database is locked" (SQLite)
- Use separate database files per test
- Enable WAL mode in fixture
- Consider using PostgreSQL for concurrent tests

### "PostgreSQL not available" (PostgreSQL tests)
- Check Docker is running: `docker ps`
- Check connection string
- Tests may be skipped if PostgreSQL unavailable

### Import errors after reorganization
- Ensure you're using absolute imports: `med_lit_schema.storage.*`
- Reinstall package: `pip install -e .`
- Clear Python cache: `find . -type d -name __pycache__ -exec rm -r {} +`

## Further Reading

- [Storage Layer Overview](../../storage/README.md)
- [Backend Documentation](../../storage/backends/README.md)
- [Model Documentation](../../storage/models/README.md)
- [Testing Guide (main)](../TESTING.md)

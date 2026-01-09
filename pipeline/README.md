# Medical Literature Ingestion Pipeline

## Overview

The pipeline extracts structured knowledge from medical literature (PMC XML files), including:
- **Entities**: Diseases, genes, drugs, proteins, and other biomedical entities
- **Relationships**: Semantic relationships between entities (e.g., "Drug X treats Disease Y")
- **Evidence**: Quantitative metrics supporting relationships (sample sizes, p-values, etc.)
- **Papers**: Metadata and structure of source papers

The pipeline uses ABC-style storage interfaces, allowing you to choose your storage backend (SQLite for testing, PostgreSQL+pgvector for production, or custom implementations).

## Pipeline Stages

The pipeline consists of four main stages:

1. **`ner_pipeline.py`** - Entity extraction using BioBERT NER
   - Extracts biomedical entities from paper text
   - Resolves entity mentions to canonical IDs (UMLS, HGNC, RxNorm, etc.)
   - Stores entities with embeddings for similarity search

2. **`provenance_pipeline.py`** - Paper metadata and document structure
   - Parses PMC XML files
   - Extracts paper metadata (title, authors, journal, dates)
   - Extracts document structure (sections, paragraphs)

3. **`claims_pipeline.py`** - Relationship extraction
   - Extracts semantic relationships from paragraphs
   - Uses pattern matching to identify relationships (CAUSES, TREATS, etc.)
   - Optionally generates embeddings for relationship similarity search

4. **`evidence_pipeline.py`** - Evidence metrics extraction
   - Extracts quantitative evidence (sample sizes, p-values, percentages)
   - Links evidence to relationships
   - Calculates evidence strength

## Quick Start

### Using SQLite (Testing/Development)

```python
from pathlib import Path
from med_lit_schema.storage.backends.sqlite import SQLitePipelineStorage

# Initialize storage
storage = SQLitePipelineStorage(Path("output/pipeline.db"))
# or for in-memory testing:
storage = SQLitePipelineStorage(":memory:")

# Use in pipeline stages
# All pipeline scripts accept --storage sqlite
```

### Using PostgreSQL (Production)

```python
from med_lit_schema.storage.backends.postgres import PostgresPipelineStorage

# Initialize storage
storage = PostgresPipelineStorage("postgresql://user:pass@localhost/dbname")

# Use in pipeline stages
# All pipeline scripts accept --storage postgres --database-url <url>
```

### Running Pipeline Stages

```bash
# Stage 1: Extract entities
python pipeline/ner_pipeline.py --storage sqlite --output-dir output

# Stage 2: Extract paper metadata
python pipeline/provenance_pipeline.py --storage sqlite --output-dir output

# Stage 3: Extract relationships
python pipeline/claims_pipeline.py --storage sqlite --output-dir output

# Stage 4: Extract evidence
python pipeline/evidence_pipeline.py --storage sqlite --output-dir output
```

## Storage Interfaces

The pipeline uses storage interfaces to support different backends. All storage-related code is now organized in the `storage/` directory. For detailed information, see [storage/README.md](../storage/README.md).

### Main Interface: `PipelineStorageInterface`

**Location**: `storage/interfaces.py`

This is the primary interface that all pipeline stages use. It provides access to:

- `entities`: EntityCollectionInterface - Store and retrieve biomedical entities
- `papers`: PaperStorageInterface - Store and retrieve paper metadata
- `relationships`: RelationshipStorageInterface - Store and retrieve relationships
- `evidence`: EvidenceStorageInterface - Store and retrieve evidence
- `relationship_embeddings`: RelationshipEmbeddingStorageInterface - Store and retrieve relationship embeddings

### Sub-Interfaces

When implementing `PipelineStorageInterface`, you need to provide implementations for:

1. **`EntityCollectionInterface`** (from `entity.py`)
   - Methods: `add_disease()`, `add_gene()`, `get_by_id()`, `find_by_embedding()`, etc.
   - See `ENTITY_COLLECTION_INTERFACE.md` for detailed documentation

2. **`PaperStorageInterface`**
   - Methods: `add_paper()`, `get_paper()`, `list_papers()`, `paper_count`

3. **`RelationshipStorageInterface`**
   - Methods: `add_relationship()`, `get_relationship()`, `find_relationships()`, `relationship_count`

4. **`EvidenceStorageInterface`**
   - Methods: `add_evidence()`, `get_evidence_by_paper()`, `get_evidence_for_relationship()`, `evidence_count`

5. **`RelationshipEmbeddingStorageInterface`**
   - Methods: `store_relationship_embedding()`, `get_relationship_embedding()`, `find_similar_relationships()`

## Reference Implementations

Two complete implementations are provided in `storage/backends/`:

### SQLitePipelineStorage

**Location**: `storage/backends/sqlite.py`

**Use case**: Testing, development, small datasets

**Features**:
- Uses `sqlite-vec` extension for vector similarity search (optional)
- Falls back to Python-based cosine similarity if extension not available
- Supports in-memory databases (`:memory:`) for testing
- Install sqlite-vec from https://github.com/asg017/sqlite-vec for embedding search

### PostgresPipelineStorage

**Location**: `storage/backends/postgres.py`

**Use case**: Production, large datasets, vector search

**Features**:
- Uses pgvector for vector similarity search
- Requires PostgreSQL with pgvector extension installed

For detailed backend comparison, see [storage/backends/README.md](../storage/backends/README.md).

## Usage Example

```python
from med_lit_schema.storage.interfaces import PipelineStorageInterface
from med_lit_schema.storage.backends.sqlite import SQLitePipelineStorage
from med_lit_schema.entity import Disease, EntityType
from med_lit_schema.relationship import create_relationship
from med_lit_schema.base import PredicateType

# Initialize storage
storage: PipelineStorageInterface = SQLitePipelineStorage(Path("output/pipeline.db"))

# Add entities
disease = Disease(
    entity_id="C0006142",
    entity_type=EntityType.DISEASE,
    name="Breast Cancer",
    source="umls"
)
storage.entities.add_disease(disease)

# Add relationships
relationship = create_relationship(
    predicate=PredicateType.TREATS,
    subject_id="RxNorm:1187832",  # Olaparib
    object_id="C0006142",  # Breast Cancer
    confidence=0.95
)
storage.relationships.add_relationship(relationship)

# Generate and store embeddings (optional)
from med_lit_schema.pipeline.embedding_generators import SentenceTransformerEmbeddingGenerator
embedding_generator = SentenceTransformerEmbeddingGenerator()
embedding = embedding_generator.generate_embedding("Olaparib treats breast cancer")
storage.relationship_embeddings.store_relationship_embedding(
    subject_id="RxNorm:1187832",
    predicate="TREATS",
    object_id="C0006142",
    embedding=embedding,
    model_name=embedding_generator.model_name
)

# Clean up
storage.close()
```

## Implementing a Custom Storage Backend

To create your own storage backend:

1. **Implement `PipelineStorageInterface`**:
   ```python
   from med_lit_schema.pipeline.storage_interfaces import PipelineStorageInterface
   
   class MyCustomStorage(PipelineStorageInterface):
       def __init__(self, connection_string: str):
           # Initialize your storage backend
           self._entities = MyEntityCollection(connection_string)
           self._papers = MyPaperStorage(connection_string)
           # ... implement other sub-interfaces
       
       @property
       def entities(self) -> EntityCollectionInterface:
           return self._entities
       
       # Implement other properties...
       
       def close(self) -> None:
           # Clean up connections
           pass
   ```

2. **Implement each sub-interface** (see reference implementations for examples)

3. **Use your implementation**:
   ```python
   storage = MyCustomStorage("your-connection-string")
   # All pipeline stages will work with your implementation
   ```

## Parser Interfaces

The pipeline uses parser interfaces to support different input formats for papers. These interfaces allow you to parse papers from various sources (XML files, APIs, PDFs, etc.).

### Main Interface: `PaperParserInterface`

**Location**: `pipeline/parser_interfaces.py`

This interface is for file-based parsers that extract paper metadata from files. It provides:

- `format_name`: Property that returns a human-readable name of the format
- `parse_file()`: Parse a single file and return a Paper object
- `parse_directory()`: Parse all matching files in a directory
- `validate_file()`: Check if a file is parseable by this parser

**Example Implementation**:

```python
from med_lit_schema.pipeline.parser_interfaces import PaperParserInterface
from med_lit_schema.entity import Paper
from pathlib import Path

class MyCustomParser(PaperParserInterface):
    @property
    def format_name(self) -> str:
        return "My Custom Format"

    def parse_file(self, file_path: Path) -> Optional[Paper]:
        # Parse the file and return Paper object
        pass
```

### Streaming Interface: `StreamingParserInterface`

**Location**: `pipeline/parser_interfaces.py`

This interface is for parsers that work with APIs, databases, or other non-file sources:

- `source_name`: Property that returns the name of the data source
- `parse_from_id()`: Fetch and parse a paper by its identifier (DOI, PMID, etc.)
- `parse_batch()`: Parse multiple papers by their identifiers

### Reference Implementation: PMCXMLParser

**Location**: `pipeline/pmc_parser.py`

The `PMCXMLParser` class implements `PaperParserInterface` for parsing PubMed Central XML files. It extracts:
- Paper metadata (PMCID, title, authors, journal, dates)
- Document structure (sections, paragraphs)
- Abstract and full text content

**Usage**:

```python
from med_lit_schema.pipeline.pmc_parser import PMCXMLParser
from pathlib import Path

parser = PMCXMLParser()
paper = parser.parse_file(Path("data/PMC12345.xml"))
if paper:
    print(f"Parsed: {paper.title}")
```

## Domain Models

The pipeline uses domain models from the main schema package:
- `Paper` - Paper metadata and structure
- `BaseRelationship` / `BaseMedicalRelationship` - Relationships between entities
- `EvidenceItem` - Evidence supporting relationships
- `Disease`, `Gene`, `Drug`, `Protein`, etc. - Entity types

Domain models are automatically converted to/from persistence models via `mapper.py` when using the reference implementations.

## Embedding Generation

The pipeline supports generating embeddings for relationships using the `EmbeddingGeneratorInterface`:

```python
from med_lit_schema.pipeline.embedding_generators import SentenceTransformerEmbeddingGenerator

# Initialize embedding generator
generator = SentenceTransformerEmbeddingGenerator(
    model_name="sentence-transformers/all-mpnet-base-v2"
)

# Generate embeddings
embedding = generator.generate_embedding("Some text")
embeddings = generator.generate_embeddings_batch(["Text 1", "Text 2"], batch_size=32)
```

The claims pipeline automatically generates embeddings for relationships when run without `--skip-embeddings`.

## Testing

See `TESTING.md` for information on testing the pipeline with in-memory SQLite and fake data.

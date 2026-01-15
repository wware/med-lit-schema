# Medical Literature Ingestion

## Overview

The ingest process extracts structured knowledge from medical literature (PMC XML files), including:
- **Entities**: Diseases, genes, drugs, proteins, and other biomedical entities
- **Relationships**: Semantic relationships between entities (e.g., "Drug X treats Disease Y")
- **Evidence**: Quantitative metrics supporting relationships (sample sizes, p-values, etc.)
- **Papers**: Metadata and structure of source papers

The ingest process uses ABC-style storage interfaces, allowing you to choose your storage backend (SQLite for testing, PostgreSQL+pgvector for production, or custom implementations).

## Ingest Stages

The ingest process consists of seven stages that should be run in sequence:

0. **`download_pipeline.py`** - Download PMC XML files
   - Downloads PubMed Central XML files from NCBI E-utilities API
   - Stores XML files locally for processing
   - Supports downloading by PMC ID list, PubMed search, or file
   - Handles rate limiting and error recovery automatically
   - **Note**: Currently downloads full-text XML only (abstract-only option planned)

1. **`ner_pipeline.py`** - Entity extraction using BioBERT NER or Ollama LLM
   - Extracts biomedical entities from paper text
   - Resolves entity mentions to canonical IDs (UMLS, HGNC, RxNorm, etc.)
   - Stores entities with embeddings for similarity search
   - Supports GPU acceleration via Ollama (`--ollama-host`)

2. **`provenance_pipeline.py`** - Paper metadata and document structure
   - Parses PMC XML files from local directory
   - Extracts paper metadata (title, authors, journal, dates)
   - Extracts document structure (sections, paragraphs)

3. **`embeddings_pipeline.py`** - Standalone embeddings generation (optional)
   - Generates semantic embeddings for entities and relationships
   - Can be run independently after provenance extraction
   - Supports Ollama for GPU acceleration

4. **`claims_pipeline.py`** - Relationship extraction
   - Extracts semantic relationships from paragraphs
   - Uses pattern matching to identify relationships (CAUSES, TREATS, etc.)
   - Optionally generates embeddings for relationship similarity search (can also use Stage 3)
   - Supports Ollama for GPU-accelerated embeddings

5. **`evidence_pipeline.py`** - Evidence metrics extraction
   - Extracts quantitative evidence (sample sizes, p-values, percentages)
   - Links evidence to relationships
   - Calculates evidence strength

6. **`graph_pipeline.py`** - Knowledge graph construction
   - Builds knowledge graph from extracted data using SQLModel
   - Creates graph structure from entities, relationships, papers, and evidence
   - Supports both SQLite and PostgreSQL storage backends

## Quick Start

### Quick Reference

The `pipeline.sh` script is a **command generator** - it emits shell commands to stdout rather than executing them directly. This allows you to preview, edit, or save the pipeline before running.

| Scenario | Command |
|----------|---------|
| **Preview commands** | `bash ingest/pipeline.sh --storage sqlite` |
| **Run directly** | `bash ingest/pipeline.sh --storage sqlite \| bash` |
| **Save for editing** | `bash ingest/pipeline.sh --storage sqlite > run.sh` |
| **Process existing papers with Lambda Labs GPU** | `export OLLAMA_HOST=http://<LAMBDA_IP>:11434`<br>`bash ingest/pipeline.sh --skip-download --no-ollama \| bash` |
| **Full pipeline with local Ollama** | `bash ingest/pipeline.sh \| bash` |
| **Custom PostgreSQL URL** | `bash ingest/pipeline.sh --database-url postgresql://... \| bash` |

**Command-line Options:**
- `--skip-download` - Skip Stage 0 (download) - use when papers already exist
- `--no-ollama` - Exclude Ollama from Docker Compose - use with Lambda Labs GPU
- `--storage sqlite|postgres` - Choose storage backend (default: postgres)
- `--database-url URL` - PostgreSQL connection string
- `--xml-dir DIR` - Directory containing PMC XML files (default: `ingest/pmc_xmls`)
- `--output-dir DIR` - Output directory (default: `output`)

**Environment Variables:**
- `OLLAMA_HOST` - Set to `http://<LAMBDA_IP>:11434` for Lambda Labs GPU (or leave unset for local)
- `DB_URL` - PostgreSQL connection string (default: `postgresql://postgres:postgres@localhost:5432/medlit`)

### Complete Workflow: Processing Existing Papers with Docker Compose + Lambda Labs GPU

**Scenario:** You have papers already downloaded in `ingest/pmc_xmls/` and want to process them using Docker Compose (PostgreSQL) and a Lambda Labs GPU instance.

**1. Set up Lambda Labs GPU instance** (see [CLOUD_OLLAMA.md](CLOUD_OLLAMA.md) for detailed setup):

```bash
# After setting up Lambda Labs instance, set the Ollama host
export OLLAMA_HOST=http://<LAMBDA_IP>:11434

# Verify connection
curl $OLLAMA_HOST/api/tags
```

**2. Run the complete pipeline:**

```bash
# Preview the commands first (optional)
bash ingest/pipeline.sh --skip-download --no-ollama

# Run the pipeline
bash ingest/pipeline.sh --skip-download --no-ollama | bash

# Or save to a file for editing
bash ingest/pipeline.sh --skip-download --no-ollama > my_pipeline.sh
# Edit my_pipeline.sh to skip stages, modify parameters, etc.
bash my_pipeline.sh
```

The generated script handles:
- Starting Docker Compose services (PostgreSQL & Redis only)
- Waiting for PostgreSQL to be ready (via `wait_for_postgres.py`)
- Setting up the database schema
- Running all stages with GPU acceleration via Lambda Labs
- Using existing papers from `ingest/pmc_xmls/`

**Alternative: Run stages individually** (if you need more control):

```bash
# Start Docker Compose manually
docker compose up -d postgres redis

# Wait for PostgreSQL
export DB_URL="postgresql://postgres:postgres@localhost:5432/medlit"
uv run python ingest/wait_for_postgres.py --database-url $DB_URL

# Setup database
uv run python setup_database.py --database-url $DB_URL

# Run stages
export OLLAMA_HOST=http://<LAMBDA_IP>:11434
uv run python ingest/provenance_pipeline.py --input-dir ingest/pmc_xmls --output-dir output --storage postgres --database-url $DB_URL
uv run python ingest/ner_pipeline.py --xml-dir ingest/pmc_xmls --output-dir output --storage postgres --database-url $DB_URL --ollama-host $OLLAMA_HOST
uv run python ingest/claims_pipeline.py --output-dir output --storage postgres --database-url $DB_URL --skip-embeddings --ollama-host $OLLAMA_HOST
uv run python ingest/evidence_pipeline.py --output-dir output --storage postgres --database-url $DB_URL
uv run python ingest/graph_pipeline.py --output-dir output --storage postgres --database-url $DB_URL
```

### Using SQLite (Testing/Development)

```python
from pathlib import Path
from med_lit_schema.storage.backends.sqlite import SQLitePipelineStorage

# Initialize storage
storage = SQLitePipelineStorage(Path("output/ingest.db"))
# or for in-memory testing:
storage = SQLitePipelineStorage(":memory:")

# Use in ingest stages
# All ingest scripts accept --storage sqlite
```

### Using PostgreSQL (Production)

```python
from med_lit_schema.storage.backends.postgres import PostgresPipelineStorage

# Initialize storage
storage = PostgresPipelineStorage("postgresql://user:pass@localhost/dbname")

# Use in ingest stages
# All ingest scripts accept --storage postgres --database-url <url>
```

### Running Ingest Stages

```bash
# Stage 0: Download PMC XML files
python ingest/download_pipeline.py \
    --pmc-id-file ingest/sample_pmc_ids.txt \
    --output-dir ingest/pmc_xmls

# Or download via PubMed search:
python ingest/download_pipeline.py \
    --search "BRCA1 AND breast cancer AND 2020:2024[pdat]" \
    --max-results 50 \
    --output-dir ingest/pmc_xmls

# Stage 1: Extract entities
python ingest/ner_pipeline.py \
    --xml-dir ingest/pmc_xmls \
    --storage sqlite \
    --output-dir output

# Stage 2: Extract paper metadata
python ingest/provenance_pipeline.py \
    --input-dir ingest/pmc_xmls \
    --storage sqlite \
    --output-dir output

# Stage 3: Generate embeddings (optional, standalone)
python ingest/embeddings_pipeline.py \
    --output-dir output \
    --storage sqlite

# Stage 4: Extract relationships
python ingest/claims_pipeline.py \
    --output-dir output \
    --storage sqlite

# Stage 5: Extract evidence
python ingest/evidence_pipeline.py \
    --output-dir output \
    --storage sqlite

# Stage 6: Build knowledge graph
python ingest/graph_pipeline.py \
    --output-dir output \
    --storage sqlite
```

### Using Ollama for GPU Acceleration

The pipeline supports offloading heavy computation to a remote GPU server via Ollama:

```bash
# Set Ollama host (local or cloud)
export OLLAMA_HOST=http://localhost:11434  # Local
# or
export OLLAMA_HOST=http://<LAMBDA_IP>:11434  # Cloud GPU

# Run stages with GPU acceleration
python ingest/ner_pipeline.py \
    --xml-dir ingest/pmc_xmls \
    --storage sqlite \
    --output-dir output \
    --ollama-host "${OLLAMA_HOST:-http://localhost:11434}"

python ingest/claims_pipeline.py \
    --output-dir output \
    --storage sqlite \
    --ollama-host "${OLLAMA_HOST:-http://localhost:11434}"
```

See [CLOUD_OLLAMA.md](CLOUD_OLLAMA.md) for cloud GPU setup instructions.

## Storage Interfaces

The ingest process uses storage interfaces to support different backends. All storage-related code is now organized in the `storage/` directory. For detailed information, see [storage/README.md](../storage/README.md).

### Main Interface: `PipelineStorageInterface`

**Location**: `storage/interfaces.py`

This is the primary interface that all ingest stages use. It provides access to:

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
storage: PipelineStorageInterface = SQLitePipelineStorage(Path("output/ingest.db"))

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
from med_lit_schema.ingest.embedding_generators import SentenceTransformerEmbeddingGenerator
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

**Location**: `ingest/parser_interfaces.py`

This interface is for file-based parsers that extract paper metadata from files. It provides:

- `format_name`: Property that returns a human-readable name of the format
- `parse_file()`: Parse a single file and return a Paper object
- `parse_directory()`: Parse all matching files in a directory
- `validate_file()`: Check if a file is parseable by this parser

**Example Implementation**:

```python
from med_lit_schema.ingest.parser_interfaces import PaperParserInterface
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

**Location**: `ingest/parser_interfaces.py`

This interface is for parsers that work with APIs, databases, or other non-file sources:

- `source_name`: Property that returns the name of the data source
- `parse_from_id()`: Fetch and parse a paper by its identifier (DOI, PMID, etc.)
- `parse_batch()`: Parse multiple papers by their identifiers

### Reference Implementation: PMCXMLParser

**Location**: `ingest/pmc_parser.py`

The `PMCXMLParser` class implements `PaperParserInterface` for parsing PubMed Central XML files. It extracts:
- Paper metadata (PMCID, title, authors, journal, dates)
- Document structure (sections, paragraphs)
- Abstract and full text content

**Usage**:

```python
from med_lit_schema.ingest.pmc_parser import PMCXMLParser
from pathlib import Path

parser = PMCXMLParser()
paper = parser.parse_file(Path("data/PMC12345.xml"))
if paper:
    print(f"Parsed: {paper.title}")
```

## Domain Models

The ingest process uses domain models from the main schema package:
- `Paper` - Paper metadata and structure
- `BaseRelationship` / `BaseMedicalRelationship` - Relationships between entities
- `EvidenceItem` - Evidence supporting relationships
- `Disease`, `Gene`, `Drug`, `Protein`, etc. - Entity types

Domain models are automatically converted to/from persistence models via `mapper.py` when using the reference implementations.

## Embedding Generation

The ingest process supports generating embeddings for relationships using the `EmbeddingGeneratorInterface`:

```python
from med_lit_schema.ingest.embedding_generators import SentenceTransformerEmbeddingGenerator

# Initialize embedding generator
generator = SentenceTransformerEmbeddingGenerator(
    model_name="sentence-transformers/all-mpnet-base-v2"
)

# Generate embeddings
embedding = generator.generate_embedding("Some text")
embeddings = generator.generate_embeddings_batch(["Text 1", "Text 2"], batch_size=32)
```

**Note:** Embeddings can be generated in two ways:
- **Standalone (Stage 3)**: Run `embeddings_pipeline.py` separately for batch embedding generation
- **Inline (Stage 4)**: Claims pipeline can generate embeddings automatically (use `--skip-embeddings` to disable)

For PostgreSQL storage, relationship embeddings are not yet fully implemented - use `--skip-embeddings` with claims pipeline until PostgreSQL embedding storage is complete.

## Stage 0: Download Pipeline Details

### Why a Separate Download Stage?

Having a dedicated download stage provides several benefits:

1. **Separation of Concerns**: Downloading is independent from processing
2. **Resumable**: Can restart processing without re-downloading
3. **Local Archive**: Build a local corpus of papers for offline work
4. **Rate Limiting**: Handles NCBI API rate limits transparently
5. **Error Recovery**: Failed downloads can be retried independently

### Input Options

**Option 1: Direct PMC IDs**
```bash
python ingest/download_pipeline.py \
    --pmc-ids PMC123456 PMC234567 PMC345678 \
    --output-dir ingest/pmc_xmls
```

**Option 2: PMC ID File**
```bash
python ingest/download_pipeline.py \
    --pmc-id-file ingest/sample_pmc_ids.txt \
    --output-dir ingest/pmc_xmls
```

**Option 3: PubMed Search**
```bash
python ingest/download_pipeline.py \
    --search "olaparib AND BRCA1" \
    --max-results 100 \
    --output-dir ingest/pmc_xmls
```

**PubMed Search Tips:**
- Use standard PubMed query syntax
- Add date filters: `"breast cancer 2020:2024[pdat]"`
- Combine terms with AND/OR: `"BRCA1 AND (breast OR ovarian)"`
- Filter by article type: `"review[ptyp]"`
- See [PubMed Help](https://pubmed.ncbi.nlm.nih.gov/help/) for query syntax

### Advanced Options

**NCBI API Key** (increases rate limit from 3 to 10 requests/second):
```bash
python ingest/download_pipeline.py \
    --pmc-id-file ingest/sample_pmc_ids.txt \
    --api-key YOUR_API_KEY_HERE \
    --output-dir ingest/pmc_xmls
```

Get a free API key: https://www.ncbi.nlm.nih.gov/account/

**Resume Interrupted Downloads:**
```bash
python ingest/download_pipeline.py \
    --pmc-id-file ingest/sample_pmc_ids.txt \
    --skip-existing \
    --output-dir ingest/pmc_xmls
```

### Rate Limiting

The pipeline respects NCBI's rate limits automatically:
- **Without API key**: 3 requests/second (~90 seconds for 100 papers)
- **With API key**: 10 requests/second (~30 seconds for 100 papers)

### Output

Downloaded XML files are saved to the specified output directory:
```
ingest/pmc_xmls/
├── PMC123456.xml
├── PMC234567.xml
└── PMC345678.xml
```

Each file contains the complete PMC XML for one paper, ready for processing by subsequent stages.

### Error Handling

The pipeline handles common errors gracefully:
- **404 Not Found**: Paper doesn't exist or isn't in PMC
- **429 Rate Limited**: Automatic retry with backoff
- **Network errors**: Automatic retry (up to 3 attempts)
- **Invalid XML**: Reports error and continues with next paper

### Command-Line Options

| Option | Description | Example |
|--------|-------------|---------|
| `--pmc-ids` | Space-separated list of PMC IDs | `--pmc-ids PMC123 PMC456` |
| `--pmc-id-file` | File with PMC IDs (one per line) | `--pmc-id-file ids.txt` |
| `--search` | PubMed search query | `--search "cancer therapy"` |
| `--output-dir` | Where to save XML files | `--output-dir pmc_xmls` |
| `--max-results` | Max search results (default: 100) | `--max-results 500` |
| `--api-key` | NCBI API key (optional) | `--api-key YOUR_KEY` |
| `--skip-existing` | Skip already downloaded files | `--skip-existing` |

**Note**: Currently downloads full-text XML only. Abstract-only downloads are planned for a future release.

## Testing

See `TESTING.md` for information on testing the ingest with in-memory SQLite and fake data.

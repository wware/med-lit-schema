# Next steps as of 13 Jan 2026

## Summary of Recent Progress

✅ **All 5 pipeline stages are now working end-to-end!**

We have successfully completed the data ingestion pipeline with PostgreSQL backend. Here is the summary:

1.  **Database Setup:** PostgreSQL database successfully set up with required schema, pgvector extension, and JSONB columns for provenance tracking.
2.  **Provenance Pipeline (Stage 2):** Successfully processed 105 XML papers and stored complete metadata with extraction provenance in PostgreSQL.
3.  **NER Pipeline (Stage 3):** Successfully extracted 396 entities and 1,056 extraction edges from the 105 papers.
4.  **Claims Pipeline (Stage 4):** Successfully extracted 273 relationships from paper abstracts using pattern matching. **Note:** Relationship embedding storage is skipped (see TODO below).
5.  **Evidence Pipeline (Stage 5):** Successfully completed. Found 0 quantitative evidence items, which is expected since relationship text from claims extraction typically doesn't contain statistical metrics (sample sizes, p-values, etc.).

## Complete Pipeline Instructions (Updated)

The ingestion pipeline consists of seven stages that should be run in order. Here are the verified commands to run the pipeline:

### Prerequisites

1.  **PostgreSQL Database**: Set up a PostgreSQL database and ensure it is running (optional - SQLite also supported).
2.  **Ollama** (optional): For GPU acceleration, make sure Ollama is running with required models:
    ```bash
    docker compose exec ollama ollama pull nomic-embed-text
    docker compose exec ollama ollama pull llama3.1:8b
    # And ensure ollama service is running via: docker compose up -d ollama
    ```

### Pipeline Execution

To run the complete pipeline with PostgreSQL:

```bash
# Set your database URL (adjust user/password/host/port/database as needed)
export DB_URL="postgresql://postgres:postgres@localhost:5432/medlit"

# Stage 0: Download PMC XML files (if not already downloaded)
uv run python ingest/download_pipeline.py \
    --pmc-id-file ingest/sample_pmc_ids.txt \
    --output-dir ingest/pmc_xmls

# Stage 1: Setup PostgreSQL Database (creates tables)
uv run python setup_database.py --database-url $DB_URL

# Stage 2: Run Provenance Pipeline (to populate papers table in PostgreSQL)
uv run python ingest/provenance_pipeline.py \
    --input-dir ingest/pmc_xmls \
    --output-dir output \
    --storage postgres \
    --database-url $DB_URL

# Stage 3: Extract entities (NER) and store in PostgreSQL
uv run python ingest/ner_pipeline.py \
    --xml-dir ingest/pmc_xmls \
    --output-dir output \
    --storage postgres \
    --database-url $DB_URL \
    --ollama-host "${OLLAMA_HOST:-http://localhost:11434}"

# Stage 4: Extract claims (--skip-embeddings because PostgreSQL embedding storage not yet implemented)
uv run python ingest/claims_pipeline.py \
    --output-dir output \
    --storage postgres \
    --database-url $DB_URL \
    --skip-embeddings \
    --ollama-host "${OLLAMA_HOST:-http://localhost:11434}"

# Stage 5: Extract evidence
uv run python ingest/evidence_pipeline.py \
    --output-dir output \
    --storage postgres \
    --database-url $DB_URL

# Stage 6: Build knowledge graph
uv run python ingest/graph_pipeline.py \
    --output-dir output \
    --storage postgres \
    --database-url $DB_URL
```

Or use the convenience script: `bash ingest/pipeline.sh`

### Database Reset Procedures

To clear out the database for a fresh start, follow these instructions for your respective database type:

#### PostgreSQL

If you're using PostgreSQL (as configured in `X.sh`), you'll typically want to drop the existing database and recreate it.

**Prerequisite**: Ensure you have the `postgresql-client` tools installed on your system. On Debian/Ubuntu, you can install them via:
```bash
sudo apt-get update
sudo apt-get install postgresql-client
```

Once installed, use the following commands:

1.  **Drop the existing database:**
    ```bash
    dropdb medlit
    ```
2.  **Create a new, empty database:**
    ```bash
    createdb medlit
    ```
3.  **Set up the schema:**
    After recreating the database, you must run the setup script to re-initialize the tables and indexes:
    ```bash
    uv run python setup_database.py --database-url "postgresql://postgres:postgres@localhost:5432/medlit"
    ```

#### SQLite

If you are using SQLite (e.g., `output/ingest.db`), resetting the database is simpler:

1.  **Delete the database file:**
    ```bash
    rm output/ingest.db
    ```
    This command will permanently remove the SQLite database file.


### Outputs

After running these stages, you'll have:

*   **PostgreSQL database:** A queryable knowledge graph containing:
    *   **papers table:** 105 papers with complete metadata and extraction provenance (stored as JSONB)
    *   **entities table:** 79 canonical entities (396 entity mentions matched to 79 unique canonical IDs)
    *   **relationships table:** 273 relationships/claims between entities
    *   **evidence table:** Evidence items (currently empty - see caveats below)
*   **JSONL files (output/):**
    *   `extraction_edges.jsonl`: 1,056 extraction edges from NER pipeline
    *   `extraction_provenance.json`: Detailed provenance tracking for all extractions

## Caveats and Known Limitations

### Stage 5: Evidence Pipeline - Zero Quantitative Evidence

The evidence pipeline (Stage 5) successfully ran but found **0 quantitative evidence items**. This is expected behavior, not a bug:

*   **Why:** The evidence extraction logic looks for statistical metrics (sample sizes, p-values, confidence intervals) in the relationship text
*   **The Issue:** Relationship text comes from the claims pipeline, which extracts sentences from abstracts. These sentences rarely contain quantitative statistical data - that's usually in the "Results" section of full papers
*   **Impact:** The `evidence` table remains empty, and relationships don't have rich statistical support
*   **Future Fix:** To populate evidence properly, we need to:
    1. Extract relationships from full paper "Results" sections (not just abstracts)
    2. Or implement a separate evidence extraction pass that reads full paper text
    3. Or link relationships to result paragraphs that contain statistical data

### Stage 4: Relationship Embeddings Disabled for PostgreSQL

Relationship embedding generation is currently **disabled** for PostgreSQL in the claims pipeline:

*   **Why:** The PostgreSQL relationship embedding storage interface (`PostgresRelationshipEmbeddingStorage`) is not yet implemented
*   **Current State:** The implementation raises `NotImplementedError` in `storage/backends/postgres.py:418`
*   **Workaround:** Stage 4 runs with `--skip-embeddings` flag for PostgreSQL
*   **SQLite:** Relationship embeddings work fine with SQLite storage
*   **Impact:** Cannot perform semantic similarity searches on relationships in PostgreSQL
*   **See TODO below for implementation plan**

## TODO: Critical Implementation Tasks

### 1. Implement PostgreSQL Relationship Embedding Storage

**Priority:** High
**File:** `med_lit_schema/storage/backends/postgres.py`
**Class:** `PostgresRelationshipEmbeddingStorage`

The following three methods need implementation:

```python
def store_relationship_embedding(
    self, subject_id: str, predicate: str, object_id: str,
    embedding: list[float], model_name: str
) -> None:
    """Store an embedding for a relationship."""
    # TODO: Implement pgvector-based storage
    # Should store in relationships table or separate relationship_embeddings table
    # Use pgvector for efficient similarity search
    raise NotImplementedError("PostgreSQL relationship embedding storage not yet implemented")

def get_relationship_embedding(
    self, subject_id: str, predicate: str, object_id: str
) -> Optional[list[float]]:
    """Get the embedding for a relationship."""
    # TODO: Implement pgvector-based retrieval
    raise NotImplementedError("PostgreSQL relationship embedding storage not yet implemented")

def find_similar_relationships(
    self, query_embedding: list[float], top_k: int = 5, threshold: float = 0.85
) -> list[tuple[tuple[str, str, str], float]]:
    """Find relationships similar to query embedding."""
    # TODO: Implement pgvector-based similarity search
    raise NotImplementedError("PostgreSQL relationship embedding storage not yet implemented")
```

**Implementation Options:**
1. Add `embedding` column (vector type) to existing `relationships` table
2. Create separate `relationship_embeddings` table with foreign key to relationships
3. Store embeddings in JSONB column (less efficient for similarity search)

**Recommended:** Option 1 - add vector column to relationships table, similar to how entities table has embeddings.

Once implemented, remove `--skip-embeddings` flag from Stage 4 in `X.sh`.

### 2. Improve Evidence Extraction

**Priority:** Medium
**Goal:** Populate evidence table with meaningful statistical data

**Options:**
*   Parse full paper XML to extract "Results" sections
*   Run evidence pipeline on full paper text, not just relationship text spans
*   Implement paragraph-level storage so relationships can reference result paragraphs
*   Add more sophisticated NLP patterns to detect statistical claims

### 3. Entity Resolution

**Priority:** High
**Current State:** Relationships use placeholder IDs like `PLACEHOLDER_SUBJECT_PMC12775696_claim_2`

**Goal:** Link placeholder IDs to canonical entities in the `entities` table

**Approach:**
*   Extract entity mentions from relationship text spans
*   Match mentions to canonical entities (by name, synonyms, embedding similarity)
*   Update relationships to use canonical entity IDs
*   This will enable proper graph traversal and querying

## Next Steps (from current state)

1.  **Implement Relationship Embedding Storage:** Priority task to enable semantic querying of claims in PostgreSQL
2.  **Entity Resolution:** Link placeholder relationship IDs to canonical entities for proper graph structure
3.  **Improve Evidence Extraction:** Parse full papers to extract quantitative evidence
4.  **Run Graph Pipeline (Stage 6):** Build final graph structure from extracted data using SQLModel
5.  **Query the Knowledge Graph:** Start exploring data using `query/` directory tools or custom SQL queries

## Python packaging

I did a package on test.pypi.org but I want to get a little more progress and then push it to
pypi.org.

That will allow me to share stuff. I like the idea of involving my nephew in this, if he's
interested. And if not him, maybe other folks.

I have some preliminary notes on how to do this. I want to make sure that when I'm ready, it's
a smooth thing to do.

## Future Considerations

### Note on Evidence Extraction
To get meaningful evidence for the extracted relationships, it's important to remember that the current pipeline is only processing abstracts. The simple regex-based evidence extraction logic is not finding quantitative data (sample sizes, p-values, etc.) in these abstracts.

**To improve evidence extraction, we will need to:**
1.  **Source full-text papers**, not just abstracts.
2.  **Enhance the extraction logic**, as the current regexes may not be sufficient for the complexity of full-text articles. This might involve more advanced NLP techniques.
# Next steps as of 12 Jan 2026

## Summary of Recent Progress

We have successfully run the initial stages of the data ingestion pipeline. Here is a summary of the steps that worked:

1.  **Database Setup:** The PostgreSQL database was successfully set up with the required schema by running the `setup_database.py` script.
2.  **NER Pipeline (PostgreSQL):** The `ner_pipeline.py` was successfully run to extract entities from the XML files and store them in the PostgreSQL database.
3.  **Claims Pipeline (PostgreSQL):** *Currently debugging.* The `claims_pipeline.py` ran, but found 0 papers, leading to 0 relationships extracted. This indicates an issue with how papers are being stored or retrieved from the PostgreSQL backend. We need to investigate the `PostgresPaperStorage` class and the `provenance_pipeline.py` to ensure papers are being correctly added and retrieved.
4.  **Embeddings Pipeline (SQLite):** The `embeddings_pipeline.py` was successfully run to generate entity embeddings using the `nomic-embed-text` model and store them in a SQLite database. This involved several fixes to the script to handle Ollama client errors and database schema mismatches.

## Complete Pipeline Instructions (Updated)

The ingestion pipeline consists of several stages that should be run in order. Here are the verified commands to run the pipeline so far:

### Prerequisites

1.  **PostgreSQL Database**: Set up a PostgreSQL database and ensure it is running.
2.  **Ollama**: Make sure Ollama is running with the `nomic-embed-text` model:
    ```bash
    docker compose exec ollama ollama pull nomic-embed-text
    # And ensure ollama service is running via: docker compose up -d ollama
    ```

### Pipeline Execution

To run the complete pipeline on your 100 downloaded papers:

```bash
# Set your database URL (adjust user/password/host/port/database as needed)
export DB_URL="postgresql://postgres:postgres@localhost:5432/medlit"

# Stage 1: Setup PostgreSQL Database (creates tables)
uv run python setup_database.py --database-url $DB_URL

# Stage 2: Run Provenance Pipeline (to populate papers table in PostgreSQL)
uv run python ingest/provenance_pipeline.py --input-dir ingest/download/pmc_xmls --output-dir output --storage postgres --database-url $DB_URL

# Stage 3: Extract entities (NER) and store in PostgreSQL
uv run python ingest/ner_pipeline.py --xml-dir ingest/download/pmc_xmls --output-dir output --storage postgres --database-url $DB_URL

# Stage 4: Extract claims (Currently debugging - found 0 papers)
uv run python ingest/claims_pipeline.py --output-dir output --storage postgres --database-url $DB_URL

# Stage 5: Extract evidence (Pending successful completion of Stage 4)
uv run python ingest/evidence_pipeline.py --output-dir output --storage postgres --database-url $DB_URL
```

### Outputs

After running these stages, you'll have:

*   **PostgreSQL database:** A queryable knowledge graph containing:
    *   **papers table:** Metadata for each paper (expected, but currently being debugged for retrieval by claims pipeline).
    *   **entities table:** Canonical entities.
    *   **relationships table:** Claims/relationships between entities (expected to be populated after claims pipeline fix).
*   **SQLite database (output/ingest.db):** Contains entity embeddings (from the initial `embeddings_pipeline.py` run on SQLite).

## Next Steps (from current state)

1.  **Debug Claims Pipeline:** The immediate next step is to investigate why `claims_pipeline.py` is finding 0 papers when running with PostgreSQL. This involves inspecting the `PostgresPaperStorage` class in `med_lit_schema/storage/backends/postgres.py` to understand how `add_paper` stores papers and how `list_papers` retrieves them.
2.  **Run the Evidence Pipeline:** Once the claims pipeline is successfully populating relationships, the `evidence_pipeline.py` can be run.
3.  **Run the Graph Pipeline:** The `graph_pipeline.py` script likely builds the final graph structure from the extracted data. This should be run after all other ingestion pipelines are complete.
4.  **Generate Relationship Embeddings:** The `claims_pipeline.py` has an option to generate embeddings for the extracted relationships. This would be a valuable next step for semantic querying of claims.
5.  **Entity Resolution:** The `claims_pipeline.py` creates relationships with placeholder entity IDs. A crucial next step is to implement and run an entity resolution process to link these placeholders to the canonical entities in the `entities` table.
6.  **Query the Knowledge Graph:** Once the data is ingested and linked, you can start exploring the knowledge graph using the `query/` directory tools or by writing custom SQL/ORM queries.

## Python packaging

I did a package on test.pypi.org but I want to get a little more progress and then push it to
pypi.org.

That will allow me to share stuff. I like the idea of involving my nephew in this, if he's
interested. And if not him, maybe other folks.

I have some preliminary notes on how to do this. I want to make sure that when I'm ready, it's
a smooth thing to do.

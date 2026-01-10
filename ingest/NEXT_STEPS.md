# Next steps as of 10 Jan 2026

I've downloaded 100 PMC papers (see `ingest/download` directory). So those are avilable
to work with.

## Building and sharing a small corpus

I want to tweak the `ingest/*.py` files to load these files, and I want to do ingestion with
local Ollama (not the Lambda Labs cloud instance) because it's only 100 papers, I'm not in a
rush, and I want to save money.

That will produce a JSON file for each paper, and the last ingestion step is to pull those
into one big graph (however the storage HW represents that graph).

Then I can share that corpus with others who want to tinker with querying.

## Python packaging

I did a package on test.pypi.org but I want to get a little more progress and then push it to
pypi.org.

That will allow me to share stuff. I like the idea of involving my nephew in this, if he's
interested. And if not him, maybe other folks.

I have some preliminary notes on how to do this. I want to make sure that when I'm ready, it's
a smooth thing to do.

## Other stuff

1. Ollama Integration:

* I've installed the ollama Python library.
* I've created `ingest/ollama_embedding_generator.py` to provide an EmbeddingGeneratorInterface implementation for Ollama.
* I've updated `ingest/embeddings_pipeline.py` to use OllamaEmbeddingGenerator instead of SentenceTransformer, and it now dynamically determines the embedding dimension
  from the Ollama model.

2. JSON Output for Papers:

    * I've updated `ingest/parser_interfaces.py` to include a parse_directory method in the PaperParserInterface.
    * I've implemented the parse_directory method in ingest/pmc_parser.py to allow parsing all XML files in a given directory.
    * I've added an optional --json-output-dir argument to ingest/provenance_pipeline.py. If provided, this script will now save each parsed Paper object as a JSON file
      in the specified directory, alongside storing data in the SQLite database.

To test the updated ingestion pipeline:

### Generate Provenance and JSON (if desired):

First, ensure you have PMC XML files in a directory (e.g., `ingest/download/pmc_xmls`). You can then run the `provenance_pipeline.py` to parse them and optionally output
JSON files:

    uv run python ingest/provenance_pipeline.py --input-dir ingest/download/pmc_xmls --output-dir output --json-output-dir output/json_papers

This will create output/provenance.db, output/entities.db, and a directory `output/json_papers` containing the JSON representations of each paper.

### Generate Embeddings using Ollama:

Before running this, make sure Ollama is running and you have pulled the nomic-embed-text model (or your preferred embedding model) using ollama pull nomic-embed-text.

    uv run python `ingest/embeddings_pipeline.py` --output-dir output --model nomic-embed-text

This will generate embeddings for entities and paragraphs in output/entities.db and output/provenance.db using your local Ollama instance.

### Regarding PyPI Publication Preparation:

The `PYPI_PREPARATION.md` file contains detailed instructions. Please review the "Required Actions" section:

1. Update Author Email: You need to manually edit pyproject.toml (line 9) to change wware@example.com to your actual email address.
2. Test Installation Locally: Follow the instructions in `PYPI_PREPARATION.md` to build and install the package locally.
3. Test on TestPyPI First: This is highly recommended. You will need to create an account and generate an API token on test.pypi.org as described in the document.
4. Verify Package Contents: Manually check the contents of the generated package to ensure all necessary files are included.

Once these steps are completed and you are satisfied with the package, you can proceed with publishing to pypi.org using the instructions provided in `PYPI_PREPARATION.md`.

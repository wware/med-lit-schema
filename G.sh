# Create temp directory with just the one file
mkdir -p ingest/temp_single
cp ingest/pmc_xmls/PMC12778424.xml ingest/temp_single/

# Run pipeline on just that file
uv run python ingest/provenance_pipeline.py \
    --input-dir ingest/temp_single \
    --output-dir output \
    --storage postgres \
    --database-url $DB_URL

uv run python ingest/ner_pipeline.py \
    --xml-dir ingest/temp_single \
    --output-dir output \
    --storage postgres \
    --database-url $DB_URL

uv run python ingest/claims_pipeline.py \
    --output-dir output \
    --storage postgres \
    --database-url $DB_URL \
    --skip-embeddings

# Clean up
rm -rf ingest/temp_single

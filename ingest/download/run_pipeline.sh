#!/bin/bash
# Complete Medical Literature Ingest Workflow
# This script demonstrates the full pipeline from download to graph ingestion

set -e  # Exit on error

# Configuration
OUTPUT_DIR="output"
XML_DIR="pmc_xmls"
STORAGE="sqlite"  # or "postgres" with --database-url

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo "=============================================================="
echo "Medical Literature Knowledge Graph Ingest Pipeline"
echo "=============================================================="
echo ""

# ============================================================================
# Stage 0: Download PMC XML Files
# ============================================================================

echo -e "${BLUE}Stage 0: Downloading PMC XML files${NC}"
echo "--------------------------------------------------------------"

# Option A: Download from sample file
python ingest/download_pipeline.py \
    --pmc-id-file ingest/sample_pmc_ids.txt \
    --output-dir "$XML_DIR" \
    --skip-existing

# Option B: Search and download (commented out)
# python ingest/download_pipeline.py \
#     --search "BRCA1 breast cancer 2020:2024[pdat]" \
#     --max-results 10 \
#     --output-dir "$XML_DIR"

echo ""
echo -e "${GREEN}✓ Stage 0 Complete${NC}"
echo ""

# ============================================================================
# Stage 1: Entity Extraction (NER)
# ============================================================================

echo -e "${BLUE}Stage 1: Extracting biomedical entities${NC}"
echo "--------------------------------------------------------------"

python ingest/ner_pipeline.py \
    --xml-dir "$XML_DIR" \
    --output-dir "$OUTPUT_DIR" \
    --storage "$STORAGE"

echo ""
echo -e "${GREEN}✓ Stage 1 Complete${NC}"
echo ""

# ============================================================================
# Stage 2: Provenance Extraction
# ============================================================================

echo -e "${BLUE}Stage 2: Extracting paper metadata and structure${NC}"
echo "--------------------------------------------------------------"

python ingest/provenance_pipeline.py \
    --input-dir "$XML_DIR" \
    --output-dir "$OUTPUT_DIR" \
    --storage "$STORAGE"

echo ""
echo -e "${GREEN}✓ Stage 2 Complete${NC}"
echo ""

# ============================================================================
# Stage 3: Embeddings Generation (Optional)
# ============================================================================

echo -e "${BLUE}Stage 3: Generating embeddings${NC}"
echo "--------------------------------------------------------------"

python ingest/embeddings_pipeline.py \
    --output-dir "$OUTPUT_DIR"

echo ""
echo -e "${GREEN}✓ Stage 3 Complete${NC}"
echo ""

# ============================================================================
# Stage 4: Claims Extraction
# ============================================================================

echo -e "${BLUE}Stage 4: Extracting relationships (claims)${NC}"
echo "--------------------------------------------------------------"

python ingest/claims_pipeline.py \
    --output-dir "$OUTPUT_DIR" \
    --storage "$STORAGE"

echo ""
echo -e "${GREEN}✓ Stage 4 Complete${NC}"
echo ""

# ============================================================================
# Stage 5: Evidence Extraction
# ============================================================================

echo -e "${BLUE}Stage 5: Extracting quantitative evidence${NC}"
echo "--------------------------------------------------------------"

python ingest/evidence_pipeline.py \
    --output-dir "$OUTPUT_DIR" \
    --storage "$STORAGE"

echo ""
echo -e "${GREEN}✓ Stage 5 Complete${NC}"
echo ""

# ============================================================================
# Summary
# ============================================================================

echo "=============================================================="
echo "Pipeline Complete! 🎉"
echo "=============================================================="
echo ""
echo "Output Directory: $OUTPUT_DIR"
echo ""
echo "Files created:"
echo "  - ingest.db (SQLite database with all data)"
echo "  - extraction_edges.jsonl (entity co-occurrences)"
echo "  - extraction_provenance.json (metadata)"
echo ""
echo "Next steps:"
echo "  1. Query the database:"
echo "     sqlite3 $OUTPUT_DIR/ingest.db"
echo ""
echo "  2. Load into graph database (Stage 6):"
echo "     python ingest/graph_pipeline.py --output-dir $OUTPUT_DIR"
echo ""
echo "  3. Explore with Python:"
echo "     from med_lit_schema.storage.backends.sqlite import SQLitePipelineStorage"
echo "     storage = SQLitePipelineStorage('$OUTPUT_DIR/ingest.db')"
echo "     print(f'Entities: {storage.entities.entity_count}')"
echo "     print(f'Papers: {storage.papers.paper_count}')"
echo "     print(f'Relationships: {storage.relationships.relationship_count}')"
echo ""
echo "=============================================================="

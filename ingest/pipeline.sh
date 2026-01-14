#!/bin/bash
# Complete Medical Literature Ingest Workflow
# This script runs the full pipeline from download to graph ingestion
#
# Usage:
#   bash ingest/pipeline.sh                    # PostgreSQL (default)
#   bash ingest/pipeline.sh --storage sqlite   # SQLite
#   bash ingest/pipeline.sh --storage postgres --database-url postgresql://...  # Custom PostgreSQL
#   bash ingest/pipeline.sh --skip-download --no-ollama  # Skip download, use external Ollama (e.g., Lambda Labs)

set -e  # Exit on error

# Parse arguments
STORAGE="postgres"  # default
DB_URL="postgresql://postgres:postgres@localhost:5432/medlit"
XML_DIR="ingest/pmc_xmls"
OUTPUT_DIR="output"
SKIP_DOWNLOAD=false
NO_OLLAMA=false

while [[ $# -gt 0 ]]; do
    case $1 in
        --storage)
            STORAGE="$2"
            shift 2
            ;;
        --database-url)
            DB_URL="$2"
            shift 2
            ;;
        --xml-dir)
            XML_DIR="$2"
            shift 2
            ;;
        --output-dir)
            OUTPUT_DIR="$2"
            shift 2
            ;;
        --skip-download)
            SKIP_DOWNLOAD=true
            shift
            ;;
        --no-ollama)
            NO_OLLAMA=true
            shift
            ;;
        *)
            echo "Unknown option: $1"
            echo "Usage: $0 [--storage sqlite|postgres] [--database-url URL] [--xml-dir DIR] [--output-dir DIR] [--skip-download] [--no-ollama]"
            exit 1
            ;;
    esac
done

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo "=============================================================="
echo "Medical Literature Knowledge Graph Ingest Pipeline"
echo "=============================================================="
echo "Storage: $STORAGE"
if [ "$STORAGE" = "postgres" ]; then
    echo "Database: $DB_URL"
fi
if [ "$SKIP_DOWNLOAD" = true ]; then
    echo "Stage 0 (Download): SKIPPED"
fi
if [ "$NO_OLLAMA" = true ]; then
    echo "Ollama: External (OLLAMA_HOST=$OLLAMA_HOST)"
else
    echo "Ollama: Local (Docker Compose)"
fi
echo ""

# Start Docker services only if using PostgreSQL
if [ "$STORAGE" = "postgres" ]; then
    # Stop any running containers
    docker compose down

    # Start Docker services (PostgreSQL & Redis, optionally Ollama)
    if [ "$NO_OLLAMA" = true ]; then
        docker compose up -d postgres redis
        echo "Starting PostgreSQL and Redis (Ollama excluded - using external instance)"
    else
        docker compose up -d postgres redis ollama
        echo "Starting PostgreSQL, Redis, and Ollama"
    fi

    # Wait for PostgreSQL to be ready
    echo "Waiting for PostgreSQL to be ready..."
    until docker exec med-lit-postgres pg_isready -U postgres; do
        echo "  Waiting for PostgreSQL..."
        sleep 2
    done
    echo "PostgreSQL is ready!"
    echo ""

    # Stage 1: Setup PostgreSQL Database (creates tables)
    echo -e "${BLUE}Stage 1: Setting up PostgreSQL database${NC}"
    echo "--------------------------------------------------------------"
    uv run python setup_database.py --database-url "$DB_URL"
    echo ""
    echo -e "${GREEN}✓ Stage 1 Complete${NC}"
    echo ""
fi

# ============================================================================
# Stage 0: Download PMC XML Files
# ============================================================================

if [ "$SKIP_DOWNLOAD" = false ]; then
    echo -e "${BLUE}Stage 0: Downloading PMC XML files${NC}"
    echo "--------------------------------------------------------------"

    # Option A: Download from sample file
    uv run python ingest/download_pipeline.py \
        --pmc-id-file ingest/sample_pmc_ids.txt \
        --output-dir "$XML_DIR" \
        --skip-existing

    # Option B: Search and download (commented out)
    # uv run python ingest/download_pipeline.py \
    #     --search "BRCA1 breast cancer 2020:2024[pdat]" \
    #     --max-results 10 \
    #     --output-dir "$XML_DIR"

    echo ""
    echo -e "${GREEN}✓ Stage 0 Complete${NC}"
    echo ""
else
    echo -e "${BLUE}Stage 0: Skipped (using existing papers in $XML_DIR)${NC}"
    echo "--------------------------------------------------------------"
    echo ""
fi

# ============================================================================
# Stage 1: Entity Extraction (NER)
# ============================================================================

echo -e "${BLUE}Stage 1: Extracting biomedical entities${NC}"
echo "--------------------------------------------------------------"

if [ "$STORAGE" = "postgres" ]; then
    uv run python ingest/ner_pipeline.py \
        --xml-dir "$XML_DIR" \
        --output-dir "$OUTPUT_DIR" \
        --storage postgres \
        --database-url "$DB_URL" \
        --ollama-host "${OLLAMA_HOST:-http://localhost:11434}"
else
    uv run python ingest/ner_pipeline.py \
        --xml-dir "$XML_DIR" \
        --output-dir "$OUTPUT_DIR" \
        --storage sqlite \
        --ollama-host "${OLLAMA_HOST:-http://localhost:11434}"
fi

echo ""
echo -e "${GREEN}✓ Stage 1 Complete${NC}"
echo ""

# ============================================================================
# Stage 2: Provenance Extraction
# ============================================================================

echo -e "${BLUE}Stage 2: Extracting paper metadata and structure${NC}"
echo "--------------------------------------------------------------"

if [ "$STORAGE" = "postgres" ]; then
    uv run python ingest/provenance_pipeline.py \
        --input-dir "$XML_DIR" \
        --output-dir "$OUTPUT_DIR" \
        --storage postgres \
        --database-url "$DB_URL"
else
    uv run python ingest/provenance_pipeline.py \
        --input-dir "$XML_DIR" \
        --output-dir "$OUTPUT_DIR" \
        --storage sqlite
fi

echo ""
echo -e "${GREEN}✓ Stage 2 Complete${NC}"
echo ""

# ============================================================================
# Stage 3: Embeddings Generation (Optional, Standalone)
# ============================================================================

echo -e "${BLUE}Stage 3: Generating embeddings${NC}"
echo "--------------------------------------------------------------"

if [ "$STORAGE" = "postgres" ]; then
    uv run python ingest/embeddings_pipeline.py \
        --output-dir "$OUTPUT_DIR" \
        --storage postgres \
        --database-url "$DB_URL"
else
    uv run python ingest/embeddings_pipeline.py \
        --output-dir "$OUTPUT_DIR" \
        --storage sqlite
fi

echo ""
echo -e "${GREEN}✓ Stage 3 Complete${NC}"
echo ""

# ============================================================================
# Stage 4: Claims Extraction
# ============================================================================

echo -e "${BLUE}Stage 4: Extracting relationships (claims)${NC}"
echo "--------------------------------------------------------------"

if [ "$STORAGE" = "postgres" ]; then
    # PostgreSQL: skip embeddings (not yet implemented)
    uv run python ingest/claims_pipeline.py \
        --output-dir "$OUTPUT_DIR" \
        --storage postgres \
        --database-url "$DB_URL" \
        --skip-embeddings \
        --ollama-host "${OLLAMA_HOST:-http://localhost:11434}"
else
    uv run python ingest/claims_pipeline.py \
        --output-dir "$OUTPUT_DIR" \
        --storage sqlite \
        --ollama-host "${OLLAMA_HOST:-http://localhost:11434}"
fi

echo ""
echo -e "${GREEN}✓ Stage 4 Complete${NC}"
echo ""

# ============================================================================
# Stage 5: Evidence Extraction
# ============================================================================

echo -e "${BLUE}Stage 5: Extracting quantitative evidence${NC}"
echo "--------------------------------------------------------------"

if [ "$STORAGE" = "postgres" ]; then
    uv run python ingest/evidence_pipeline.py \
        --output-dir "$OUTPUT_DIR" \
        --storage postgres \
        --database-url "$DB_URL"
else
    uv run python ingest/evidence_pipeline.py \
        --output-dir "$OUTPUT_DIR" \
        --storage sqlite
fi

echo ""
echo -e "${GREEN}✓ Stage 5 Complete${NC}"
echo ""

# ============================================================================
# Stage 6: Graph Construction
# ============================================================================

echo -e "${BLUE}Stage 6: Building knowledge graph${NC}"
echo "--------------------------------------------------------------"

if [ "$STORAGE" = "postgres" ]; then
    uv run python ingest/graph_pipeline.py \
        --output-dir "$OUTPUT_DIR" \
        --storage postgres \
        --database-url "$DB_URL"
else
    uv run python ingest/graph_pipeline.py \
        --output-dir "$OUTPUT_DIR" \
        --storage sqlite
fi

echo ""
echo -e "${GREEN}✓ Stage 6 Complete${NC}"
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

if [ "$STORAGE" = "sqlite" ]; then
    echo "Files created:"
    echo "  - ingest.db (SQLite database with all data)"
    echo "  - extraction_edges.jsonl (entity co-occurrences)"
    echo "  - extraction_provenance.json (metadata)"
    echo ""
    echo "Next steps:"
    echo "  1. Query the database:"
    echo "     sqlite3 $OUTPUT_DIR/ingest.db"
    echo ""
    echo "  2. Explore with Python:"
    echo "     from med_lit_schema.storage.backends.sqlite import SQLitePipelineStorage"
    echo "     storage = SQLitePipelineStorage('$OUTPUT_DIR/ingest.db')"
    echo "     print(f'Entities: {storage.entities.entity_count}')"
    echo "     print(f'Papers: {storage.papers.paper_count}')"
    echo "     print(f'Relationships: {storage.relationships.relationship_count}')"
else
    echo "Data stored in PostgreSQL database: $DB_URL"
    echo ""
    echo "Next steps:"
    echo "  1. Query the database using SQL or the query/ directory tools"
    echo "  2. Explore with Python using PostgresPipelineStorage"
fi

echo ""
echo "=============================================================="

# Stop Docker services if we started them
if [ "$STORAGE" = "postgres" ]; then
    docker compose down
fi

#!/bin/bash
# Medical Literature Ingest Pipeline - Command Generator
#
# This script generates a sequence of commands for the ingest pipeline.
# Instead of executing commands directly, it emits them to stdout.
#
# Usage:
#   bash ingest/pipeline.sh [options]              # Preview commands
#   bash ingest/pipeline.sh [options] | bash       # Execute directly
#   bash ingest/pipeline.sh [options] > run.sh     # Save for editing
#
# Options:
#   --storage sqlite|postgres    Storage backend (default: postgres)
#   --database-url URL           PostgreSQL connection string
#   --xml-dir DIR                Directory containing PMC XML files
#   --output-dir DIR             Output directory
#   --skip-download              Skip Stage 0 (download)
#   --no-ollama                  Don't start Ollama via Docker Compose
#
# Examples:
#   # Preview what will run
#   bash ingest/pipeline.sh --storage sqlite
#
#   # Run directly
#   bash ingest/pipeline.sh --storage sqlite | bash
#
#   # Save, edit, then run
#   bash ingest/pipeline.sh --storage postgres > my_pipeline.sh
#   # Edit my_pipeline.sh to comment out stages you don't need
#   bash my_pipeline.sh

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
            echo "Unknown option: $1" >&2
            echo "Usage: $0 [--storage sqlite|postgres] [--database-url URL] [--xml-dir DIR] [--output-dir DIR] [--skip-download] [--no-ollama]" >&2
            exit 1
            ;;
    esac
done

# Resolve OLLAMA_HOST with default
OLLAMA_HOST_RESOLVED="${OLLAMA_HOST:-http://localhost:11434}"

# ============================================================================
# Emit the pipeline commands
# ============================================================================

cat << 'HEADER'
#!/bin/bash
# Generated Medical Literature Ingest Pipeline
# Edit this file to skip stages or modify parameters as needed.

set -e  # Exit on error

HEADER

echo "# Configuration"
echo "# Storage: $STORAGE"
if [ "$STORAGE" = "postgres" ]; then
    echo "# Database: $DB_URL"
fi
echo "# XML Directory: $XML_DIR"
echo "# Output Directory: $OUTPUT_DIR"
echo "# Ollama Host: $OLLAMA_HOST_RESOLVED"
echo ""

# PostgreSQL setup (only for postgres storage)
if [ "$STORAGE" = "postgres" ]; then
    echo "# ============================================================================"
    echo "# Docker Compose Setup"
    echo "# ============================================================================"
    echo ""
    echo "echo 'Stopping any running containers...'"
    echo "docker compose down"
    echo ""

    if [ "$NO_OLLAMA" = true ]; then
        echo "echo 'Starting PostgreSQL and Redis (Ollama excluded - using external instance)...'"
        echo "docker compose up -d postgres redis"
    else
        echo "echo 'Starting PostgreSQL, Redis, and Ollama...'"
        echo "docker compose up -d postgres redis ollama"
    fi
    echo ""

    echo "# Wait for PostgreSQL to be ready"
    echo "echo 'Waiting for PostgreSQL...'"
    echo "uv run python ingest/wait_for_postgres.py --database-url \"$DB_URL\" --timeout 60"
    echo ""

    echo "# Setup database schema"
    echo "echo 'Setting up PostgreSQL database...'"
    echo "uv run python setup_database.py --database-url \"$DB_URL\""
    echo ""
fi

# Stage 0: Download
if [ "$SKIP_DOWNLOAD" = false ]; then
    echo "# ============================================================================"
    echo "# Stage 0: Download PMC XML files"
    echo "# ============================================================================"
    echo ""
    echo "echo 'Stage 0: Downloading PMC XML files...'"
    echo "uv run python ingest/download_pipeline.py \\"
    echo "    --pmc-id-file ingest/sample_pmc_ids.txt \\"
    echo "    --output-dir \"$XML_DIR\" \\"
    echo "    --skip-existing"
    echo ""
else
    echo "# Stage 0: Download - SKIPPED (--skip-download)"
    echo "# Using existing papers in $XML_DIR"
    echo ""
fi

# Stage 1: NER Pipeline
echo "# ============================================================================"
echo "# Stage 1: Entity Extraction (NER)"
echo "# ============================================================================"
echo ""
echo "echo 'Stage 1: Extracting biomedical entities...'"

# Use smaller model for local docker-compose Ollama, default for external
if [ "$NO_OLLAMA" = true ]; then
    NER_MODEL="llama3.1:8b"
else
    NER_MODEL="llama3.2:1b"
fi

if [ "$STORAGE" = "postgres" ]; then
    echo "uv run python ingest/ner_pipeline.py \\"
    echo "    --xml-dir \"$XML_DIR\" \\"
    echo "    --output-dir \"$OUTPUT_DIR\" \\"
    echo "    --storage postgres \\"
    echo "    --database-url \"$DB_URL\" \\"
    echo "    --ollama-host \"$OLLAMA_HOST_RESOLVED\" \\"
    echo "    --ollama-model \"$NER_MODEL\""
else
    echo "uv run python ingest/ner_pipeline.py \\"
    echo "    --xml-dir \"$XML_DIR\" \\"
    echo "    --output-dir \"$OUTPUT_DIR\" \\"
    echo "    --storage sqlite \\"
    echo "    --ollama-host \"$OLLAMA_HOST_RESOLVED\" \\"
    echo "    --ollama-model \"$NER_MODEL\""
fi
echo ""

# Stage 2: Provenance Pipeline
echo "# ============================================================================"
echo "# Stage 2: Provenance Extraction"
echo "# ============================================================================"
echo ""
echo "echo 'Stage 2: Extracting paper metadata and structure...'"
if [ "$STORAGE" = "postgres" ]; then
    echo "uv run python ingest/provenance_pipeline.py \\"
    echo "    --input-dir \"$XML_DIR\" \\"
    echo "    --output-dir \"$OUTPUT_DIR\" \\"
    echo "    --storage postgres \\"
    echo "    --database-url \"$DB_URL\""
else
    echo "uv run python ingest/provenance_pipeline.py \\"
    echo "    --input-dir \"$XML_DIR\" \\"
    echo "    --output-dir \"$OUTPUT_DIR\" \\"
    echo "    --storage sqlite"
fi
echo ""

# Stage 3: Embeddings Pipeline
echo "# ============================================================================"
echo "# Stage 3: Embeddings Generation"
echo "# ============================================================================"
echo ""
echo "echo 'Stage 3: Generating embeddings...'"
if [ "$STORAGE" = "postgres" ]; then
    echo "uv run python ingest/embeddings_pipeline.py \\"
    echo "    --output-dir \"$OUTPUT_DIR\" \\"
    echo "    --storage postgres \\"
    echo "    --database-url \"$DB_URL\""
else
    echo "uv run python ingest/embeddings_pipeline.py \\"
    echo "    --output-dir \"$OUTPUT_DIR\" \\"
    echo "    --storage sqlite"
fi
echo ""

# Stage 4: Claims Pipeline
echo "# ============================================================================"
echo "# Stage 4: Claims Extraction"
echo "# ============================================================================"
echo ""
echo "echo 'Stage 4: Extracting relationships (claims)...'"
if [ "$STORAGE" = "postgres" ]; then
    echo "uv run python ingest/claims_pipeline.py \\"
    echo "    --output-dir \"$OUTPUT_DIR\" \\"
    echo "    --storage postgres \\"
    echo "    --database-url \"$DB_URL\" \\"
    echo "    --skip-embeddings \\"
    echo "    --ollama-host \"$OLLAMA_HOST_RESOLVED\""
else
    echo "uv run python ingest/claims_pipeline.py \\"
    echo "    --output-dir \"$OUTPUT_DIR\" \\"
    echo "    --storage sqlite \\"
    echo "    --ollama-host \"$OLLAMA_HOST_RESOLVED\""
fi
echo ""

# Stage 5: Evidence Pipeline
echo "# ============================================================================"
echo "# Stage 5: Evidence Extraction"
echo "# ============================================================================"
echo ""
echo "echo 'Stage 5: Extracting quantitative evidence...'"
if [ "$STORAGE" = "postgres" ]; then
    echo "uv run python ingest/evidence_pipeline.py \\"
    echo "    --output-dir \"$OUTPUT_DIR\" \\"
    echo "    --storage postgres \\"
    echo "    --database-url \"$DB_URL\""
else
    echo "uv run python ingest/evidence_pipeline.py \\"
    echo "    --output-dir \"$OUTPUT_DIR\" \\"
    echo "    --storage sqlite"
fi
echo ""

# Stage 6: Graph Pipeline
echo "# ============================================================================"
echo "# Stage 6: Graph Construction"
echo "# ============================================================================"
echo ""
echo "echo 'Stage 6: Building knowledge graph...'"
if [ "$STORAGE" = "postgres" ]; then
    echo "uv run python ingest/graph_pipeline.py \\"
    echo "    --output-dir \"$OUTPUT_DIR\" \\"
    echo "    --storage postgres \\"
    echo "    --database-url \"$DB_URL\""
else
    echo "uv run python ingest/graph_pipeline.py \\"
    echo "    --output-dir \"$OUTPUT_DIR\" \\"
    echo "    --storage sqlite"
fi
echo ""

# Summary
echo "# ============================================================================"
echo "# Pipeline Complete"
echo "# ============================================================================"
echo ""
echo "echo 'Pipeline complete!'"
echo "echo 'Output directory: $OUTPUT_DIR'"
if [ "$STORAGE" = "sqlite" ]; then
    echo "echo 'Database: $OUTPUT_DIR/ingest.db'"
else
    echo "echo 'Database: $DB_URL'"
fi
echo ""

# Docker cleanup (only for postgres)
if [ "$STORAGE" = "postgres" ]; then
    echo "# Uncomment the following line to stop Docker containers when done"
    echo "# docker compose down"
fi

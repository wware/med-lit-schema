#!/bin/bash
# Generated Medical Literature Ingest Pipeline
# Edit this file to skip stages or modify parameters as needed.

set -e  # Exit on error

# Configuration
# Storage: postgres
# Database: postgresql://postgres:postgres@localhost:5432/medlit
# XML Directory: ingest/pmc_xmls
# Output Directory: output
# Ollama Host: http://localhost:11434

# ============================================================================
# Docker Compose Setup
# ============================================================================

echo 'Stopping any running containers...'
docker compose down

echo 'Starting PostgreSQL, Redis, and Ollama...'
docker compose up -d postgres redis ollama

# Wait for PostgreSQL to be ready
echo 'Waiting for PostgreSQL...'
uv run python ingest/wait_for_postgres.py --database-url "postgresql://postgres:postgres@localhost:5432/medlit" --timeout 60

# Setup database schema
echo 'Setting up PostgreSQL database...'
uv run python setup_database.py --database-url "postgresql://postgres:postgres@localhost:5432/medlit"

# Stage 0: Download - SKIPPED (--skip-download)
# Using existing papers in ingest/pmc_xmls

# ============================================================================
# Stage 1: Entity Extraction (NER)
# ============================================================================

echo 'Stage 1: Extracting biomedical entities...'
uv run python ingest/ner_pipeline.py \
    --xml-dir "ingest/pmc_xmls" \
    --output-dir "output" \
    --storage postgres \
    --database-url "postgresql://postgres:postgres@localhost:5432/medlit" \
    --ollama-host "http://localhost:11434" \
    --ollama-model "llama3.2:1b"

# ============================================================================
# Pipeline Complete
# ============================================================================

echo 'Pipeline complete!'
echo 'Output directory: output'
echo 'Database: postgresql://postgres:postgres@localhost:5432/medlit'

# Uncomment the following line to stop Docker containers when done
# docker compose down

-- schema/migration.sql
-- Migration script to set up vanilla PostgreSQL tables for the Medical Knowledge Graph

-- Enable UUID extension for primary keys if not already available
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Enable pgvector for semantic search
CREATE EXTENSION IF NOT EXISTS vector;

-- 1. Entities table: Nodes in the graph (genes, drugs, diseases, etc.)
CREATE TABLE IF NOT EXISTS entities (
    id TEXT PRIMARY KEY,               -- Canonical ID (e.g., 'RxNorm:1187832')
    entity_type TEXT NOT NULL,         -- 'gene', 'drug', 'disease', etc.
    name TEXT NOT NULL,                -- Preferred/canonical name
    canonical_id TEXT,                 -- Duplicate of ID for easy access or external ref
    properties JSONB DEFAULT '{}',     -- Dynamic properties (icd10, fda_approved, etc.)
    embedding vector(768),             -- Biomedical embeddings (e.g., PubMedBERT)
    mentions INT DEFAULT 0,            -- Aggregate mention count
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_entities_type ON entities(entity_type);
CREATE INDEX IF NOT EXISTS idx_entities_name ON entities(name);
-- Vector index for fast similarity search (HNSW)
CREATE INDEX IF NOT EXISTS idx_entities_embedding ON entities USING hnsw (embedding vector_cosine_ops);

-- 2. Papers table: Source documents
CREATE TABLE IF NOT EXISTS papers (
    id TEXT PRIMARY KEY,               -- PMC ID or DOI
    title TEXT NOT NULL,
    abstract TEXT,
    authors TEXT[],                    -- Array of author names
    publication_date DATE,
    journal TEXT,
    entity_count INT DEFAULT 0,
    relationship_count INT DEFAULT 0,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- 3. Relationships table: Edges in the graph (TREATS, CAUSES, etc.)
CREATE TABLE IF NOT EXISTS relationships (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    subject_id TEXT NOT NULL REFERENCES entities(id) ON DELETE CASCADE,
    object_id TEXT NOT NULL REFERENCES entities(id) ON DELETE CASCADE,
    predicate TEXT NOT NULL,           -- 'TREATS', 'CAUSES', 'BINDS_TO', etc.
    confidence FLOAT DEFAULT 0.0,      -- Weighted confidence score
    properties JSONB DEFAULT '{}',     -- Additional relationship data
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,

    -- Ensure we don't duplicate identical semantic triples easily,
    -- though multi-provenance often means we aggregate rather than unique-constrain here.
    UNIQUE(subject_id, object_id, predicate)
);

CREATE INDEX IF NOT EXISTS idx_relationships_subject ON relationships(subject_id);
CREATE INDEX IF NOT EXISTS idx_relationships_object ON relationships(object_id);
CREATE INDEX IF NOT EXISTS idx_relationships_predicate ON relationships(predicate);

-- 4. Evidence table: Direct links from relationships to paper segments
-- This fulfills the requirement that every relationship must be traceable.
CREATE TABLE IF NOT EXISTS evidence (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    relationship_id UUID NOT NULL REFERENCES relationships(id) ON DELETE CASCADE,
    paper_id TEXT NOT NULL REFERENCES papers(id) ON DELETE CASCADE,
    section TEXT,                      -- 'results', 'abstract', etc.
    text_span TEXT,                    -- The specific sentence or paragraph excerpt
    confidence FLOAT DEFAULT 0.0,      -- Extraction confidence for this specific item
    metadata JSONB DEFAULT '{}',       -- Paragraph index, sentence index, model info, etc.
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_evidence_rel ON evidence(relationship_id);
CREATE INDEX IF NOT EXISTS idx_evidence_paper ON evidence(paper_id);

-- Helper function to update updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Trigger for entities
CREATE TRIGGER update_entities_updated_at
    BEFORE UPDATE ON entities
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- Hybrid Search Demo - Schema Creation
-- Creates the documents and demo_queries tables with TimescaleDB hypertable support

-- Ensure required extensions are enabled
CREATE EXTENSION IF NOT EXISTS timescaledb;
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS vectorscale;

-- Drop existing tables if they exist (for clean re-runs)
DROP TABLE IF EXISTS demo_queries CASCADE;
DROP TABLE IF EXISTS documents CASCADE;

-- Create documents table
CREATE TABLE documents (
    id TEXT NOT NULL,
    title TEXT NOT NULL,
    body TEXT NOT NULL,
    category TEXT NOT NULL,
    version TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL,
    is_deprecated BOOLEAN DEFAULT FALSE,
    deprecation_note TEXT,
    tags TEXT[], -- Array of tags for filtering

    -- Full-text search vector (generated column)
    search_vector TSVECTOR GENERATED ALWAYS AS (
        setweight(to_tsvector('english', COALESCE(title, '')), 'A') ||
        setweight(to_tsvector('english', COALESCE(body, '')), 'B')
    ) STORED,

    -- Vector embedding (768 dimensions from MPNet model)
    embedding VECTOR(768),

    -- Temporal filtering - published_date is calculated dynamically at restore time
    -- This allows the demo to work indefinitely with relative dates
    published_date TIMESTAMPTZ,

    -- Trap quartet metadata (for demo purposes)
    trap_set TEXT,
    trap_type TEXT,

    -- Composite primary key including partitioning column
    PRIMARY KEY (id, created_at)
);

-- Convert to hypertable for temporal partitioning
-- This enables efficient time-based filtering and chunk exclusion
SELECT create_hypertable(
    'documents',
    'created_at',
    chunk_time_interval => INTERVAL '6 months',
    if_not_exists => TRUE
);

-- Create demo_queries table
-- Stores pre-defined queries with embeddings for consistent demo results
CREATE TABLE demo_queries (
    id SERIAL PRIMARY KEY,
    query_text TEXT NOT NULL,
    trap_set TEXT NOT NULL,
    embedding VECTOR(768) NOT NULL,
    expected_winner TEXT NOT NULL,
    expected_semantic_bait TEXT,
    expected_keyword_bait TEXT,
    expected_temporal_bait TEXT,
    UNIQUE(query_text)
);

-- Add comments for documentation
COMMENT ON TABLE documents IS 'NovaCLI documentation with embeddings for hybrid search demo';
COMMENT ON COLUMN documents.search_vector IS 'Full-text search vector (title=A, body=B weights)';
COMMENT ON COLUMN documents.embedding IS '768-dimensional vector embedding from MPNet';
COMMENT ON COLUMN documents.created_at IS 'Fixed timestamp for TimescaleDB partitioning (stable chunks)';
COMMENT ON COLUMN documents.published_date IS 'Dynamic timestamp calculated at restore time (relative to NOW)';
COMMENT ON COLUMN documents.trap_set IS 'Trap quartet identifier (authentication, config_format, etc.)';
COMMENT ON COLUMN documents.trap_type IS 'Trap type (winner, semantic_bait, keyword_bait, temporal_bait)';

COMMENT ON TABLE demo_queries IS 'Pre-defined demo queries with expected trap behavior';
COMMENT ON COLUMN demo_queries.expected_winner IS 'Document ID that should rank first with hybrid+temporal search';

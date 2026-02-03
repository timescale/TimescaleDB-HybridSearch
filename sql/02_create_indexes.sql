-- Hybrid Search Demo - Index Creation
-- Creates indexes for vector search, full-text search, and temporal queries

-- 1. Full-Text Search Index (GIN)
-- Enables fast keyword-based text search using PostgreSQL's built-in capabilities
CREATE INDEX IF NOT EXISTS idx_documents_search
ON documents USING GIN (search_vector);

COMMENT ON INDEX idx_documents_search IS 'GIN index for full-text search on title and body';

-- 2. Vector Similarity Index (DiskANN via pgvectorscale)
-- Enables fast approximate nearest neighbor search for semantic similarity
CREATE INDEX IF NOT EXISTS idx_documents_embedding
ON documents USING diskann (embedding vector_cosine_ops)
WITH (
    num_neighbors = 50,           -- HNSW parameter: number of bidirectional links
    search_list_size = 100,       -- Size of search list during index build
    max_alpha = 1.2,              -- Heuristic factor for index build
    num_dimensions = 768,         -- Embedding dimensions (MPNet)
    num_bits_per_dimension = 2    -- Quantization bits (lower = smaller index)
);

COMMENT ON INDEX idx_documents_embedding IS 'DiskANN index for vector similarity search (cosine distance)';

-- 3. Temporal Query Index
-- Optimizes time-based filtering (crucial for hybrid+temporal search)
CREATE INDEX IF NOT EXISTS idx_documents_temporal
ON documents (created_at DESC, category);

COMMENT ON INDEX idx_documents_temporal IS 'B-tree index for temporal filtering with category support';

-- 4. Trap Quartet Lookup Index
-- Speeds up filtering by trap type during demo validation
CREATE INDEX IF NOT EXISTS idx_documents_trap
ON documents (trap_set, trap_type)
WHERE trap_set IS NOT NULL;

COMMENT ON INDEX idx_documents_trap IS 'Partial index for trap quartet lookups';

-- 5. Category Filter Index
-- Optimizes filtering by document category
CREATE INDEX IF NOT EXISTS idx_documents_category
ON documents (category);

COMMENT ON INDEX idx_documents_category IS 'B-tree index for category filtering';

-- 6. Deprecation Filter Index
-- Speeds up queries that filter out deprecated documents
CREATE INDEX IF NOT EXISTS idx_documents_deprecated
ON documents (is_deprecated);

COMMENT ON INDEX idx_documents_deprecated IS 'B-tree index for deprecation filtering';

-- Analyze tables to update statistics for query planner
ANALYZE documents;
ANALYZE demo_queries;

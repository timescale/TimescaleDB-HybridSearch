-- Update timestamps to make trap quartet work with temporal filtering
-- This moves all timestamps forward to be relative to 2026-01-13 (today)

-- Winner documents: 1 month ago (well within 12-month window)
UPDATE documents
SET created_at = NOW() - INTERVAL '1 month'
WHERE trap_type = 'winner';

-- Semantic bait: 6 months ago (within 12-month window, but older than winner)
UPDATE documents
SET created_at = NOW() - INTERVAL '6 months'
WHERE trap_type = 'semantic_bait';

-- Keyword bait: 18 months ago (outside 12-month window)
UPDATE documents
SET created_at = NOW() - INTERVAL '18 months'
WHERE trap_type = 'keyword_bait';

-- Temporal bait: 3 years ago (way outside 12-month window)
UPDATE documents
SET created_at = NOW() - INTERVAL '3 years'
WHERE trap_type = 'temporal_bait';

-- Non-trap documents: spread them across last 2 years
UPDATE documents
SET created_at = NOW() - (INTERVAL '1 day' * (RANDOM() * 730)::int)
WHERE trap_type IS NULL;

-- Verify the changes
SELECT
    trap_type,
    COUNT(*) as count,
    MIN(created_at) as oldest,
    MAX(created_at) as newest
FROM documents
GROUP BY trap_type
ORDER BY trap_type NULLS LAST;

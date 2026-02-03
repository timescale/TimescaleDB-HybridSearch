"""
Search functions for the hybrid search demo.

Implements four search methods:
1. Vector search (semantic similarity only)
2. Text search (full-text search only)
3. Hybrid search (vector + text with RRF)
4. Hybrid + Temporal (hybrid with time-based filtering)
"""

from typing import List, Dict, Optional
import time
import psycopg
from psycopg.rows import dict_row


def search_vector(
    embedding: List[float],
    limit: int = 5,
    conn_string: str = None
) -> Dict:
    """
    Vector search using pgvectorscale DiskANN index.

    Args:
        embedding: Query embedding vector (768 dimensions)
        limit: Number of results to return
        conn_string: Database connection string

    Returns:
        Dict with results, execution time, and method name
    """
    # Format embedding as PostgreSQL array string
    embedding_str = '[' + ','.join(str(x) for x in embedding) + ']'

    query = """
        SELECT
            id,
            title,
            body,
            version,
            created_at,
            published_date,
            trap_type,
            trap_set,
            tags,
            category,
            deprecation_note,
            1 - (embedding <=> %s::vector) AS score
        FROM documents
        ORDER BY embedding <=> %s::vector
        LIMIT %s;
    """

    # Measure execution time
    start_time = time.perf_counter()

    with psycopg.connect(conn_string, row_factory=dict_row) as conn:
        with conn.cursor() as cur:
            cur.execute(query, (embedding_str, embedding_str, limit))
            results = cur.fetchall()

    elapsed_ms = (time.perf_counter() - start_time) * 1000

    return {
        'results': [dict(row) for row in results],
        'execution_time_ms': round(elapsed_ms, 2),
        'method': 'Vector Search',
        'sql': query  # Include SQL for display
    }


def search_text(
    query: str,
    limit: int = 5,
    conn_string: str = None
) -> Dict:
    """
    Full-text search using PostgreSQL GIN index.

    Args:
        query: Search query text
        limit: Number of results to return
        conn_string: Database connection string

    Returns:
        Dict with results, execution time, and method name
    """
    sql = """
        SELECT
            id,
            title,
            body,
            version,
            created_at,
            published_date,
            trap_type,
            trap_set,
            tags,
            category,
            deprecation_note,
            ts_rank(search_vector, websearch_to_tsquery('english', %s)) AS score
        FROM documents
        WHERE search_vector @@ websearch_to_tsquery('english', %s)
        ORDER BY score DESC
        LIMIT %s;
    """

    # Measure execution time
    start_time = time.perf_counter()

    with psycopg.connect(conn_string, row_factory=dict_row) as conn:
        with conn.cursor() as cur:
            cur.execute(sql, (query, query, limit))
            results = cur.fetchall()

    elapsed_ms = (time.perf_counter() - start_time) * 1000

    return {
        'results': [dict(row) for row in results],
        'execution_time_ms': round(elapsed_ms, 2),
        'method': 'Text Search',
        'sql': sql  # Include SQL for display
    }


def search_hybrid(
    query: str,
    embedding: List[float],
    limit: int = 5,
    vector_weight: float = 0.5,
    text_weight: float = 0.5,
    conn_string: str = None
) -> Dict:
    """
    Hybrid search combining vector and text search with RRF.

    Uses Reciprocal Rank Fusion (RRF) to combine rankings from
    both vector and text search methods.

    Args:
        query: Search query text
        embedding: Query embedding vector
        limit: Number of results to return
        vector_weight: Weight for vector search (0-1)
        text_weight: Weight for text search (0-1)
        conn_string: Database connection string

    Returns:
        Dict with results, execution time, and method name
    """
    # Format embedding as PostgreSQL array string
    embedding_str = '[' + ','.join(str(x) for x in embedding) + ']'

    sql = """
        WITH vector_search AS (
            SELECT
                id,
                title,
                body,
                version,
                created_at,
                published_date,
                trap_type,
                trap_set,
                tags,
                category,
                deprecation_note,
                ROW_NUMBER() OVER (ORDER BY embedding <=> %s::vector) AS rank
            FROM documents
            ORDER BY embedding <=> %s::vector
            LIMIT 20
        ),
        text_search AS (
            SELECT
                id,
                title,
                body,
                version,
                created_at,
                published_date,
                trap_type,
                trap_set,
                tags,
                category,
                deprecation_note,
                ROW_NUMBER() OVER (ORDER BY ts_rank(search_vector, websearch_to_tsquery('english', %s)) DESC) AS rank
            FROM documents
            WHERE search_vector @@ websearch_to_tsquery('english', %s)
            ORDER BY ts_rank(search_vector, websearch_to_tsquery('english', %s)) DESC
            LIMIT 20
        ),
        combined AS (
            SELECT
                COALESCE(v.id, t.id) AS id,
                COALESCE(v.title, t.title) AS title,
                COALESCE(v.body, t.body) AS body,
                COALESCE(v.version, t.version) AS version,
                COALESCE(v.created_at, t.created_at) AS created_at,
                COALESCE(v.published_date, t.published_date) AS published_date,
                COALESCE(v.trap_type, t.trap_type) AS trap_type,
                COALESCE(v.trap_set, t.trap_set) AS trap_set,
                COALESCE(v.tags, t.tags) AS tags,
                COALESCE(v.category, t.category) AS category,
                COALESCE(v.deprecation_note, t.deprecation_note) AS deprecation_note,
                COALESCE(1.0 / (60 + v.rank), 0.0) * %s +
                COALESCE(1.0 / (60 + t.rank), 0.0) * %s AS score
            FROM vector_search v
            FULL OUTER JOIN text_search t ON v.id = t.id
        )
        SELECT * FROM combined
        ORDER BY score DESC
        LIMIT %s;
    """

    # Measure execution time
    start_time = time.perf_counter()

    with psycopg.connect(conn_string, row_factory=dict_row) as conn:
        with conn.cursor() as cur:
            cur.execute(
                sql,
                (
                    embedding_str, embedding_str,  # vector_search CTE
                    query, query, query,   # text_search CTE
                    vector_weight, text_weight,  # RRF weights
                    limit
                )
            )
            results = cur.fetchall()

    elapsed_ms = (time.perf_counter() - start_time) * 1000

    return {
        'results': [dict(row) for row in results],
        'execution_time_ms': round(elapsed_ms, 2),
        'method': 'Hybrid Search',
        'sql': sql  # Include SQL for display
    }


def search_hybrid_temporal(
    query: str,
    embedding: List[float],
    time_window: str = "12 months",
    limit: int = 5,
    vector_weight: float = 0.5,
    text_weight: float = 0.5,
    conn_string: str = None
) -> Dict:
    """
    Hybrid search with temporal filtering (hybrid + time).

    Combines vector + text search with RRF and filters by time window.
    Uses published_date for filtering (dynamically calculated at restore time)
    to ensure the demo works indefinitely with relative dates.

    Args:
        query: Search query text
        embedding: Query embedding vector
        time_window: PostgreSQL interval string (e.g., "12 months", "1 year")
        limit: Number of results to return
        vector_weight: Weight for vector search (0-1)
        text_weight: Weight for text search (0-1)
        conn_string: Database connection string

    Returns:
        Dict with results, execution time, and method name
    """
    # Validate time_window format to prevent SQL injection
    # PostgreSQL INTERVAL format: "N unit" where unit is day(s), month(s), year(s), etc.
    import re
    if not re.match(r'^\d+\s+(day|days|month|months|year|years|week|weeks|hour|hours)s?$', time_window.strip()):
        raise ValueError(
            f"Invalid time_window format: '{time_window}'. "
            f"Expected format: 'N unit' (e.g., '12 months', '1 year', '30 days')"
        )

    # Format embedding as PostgreSQL array string
    embedding_str = '[' + ','.join(str(x) for x in embedding) + ']'

    # Use f-string for INTERVAL since it can't be parameterized
    # Filter on published_date (dynamic relative dates) instead of created_at (fixed dates)
    sql = f"""
        WITH vector_search AS (
            SELECT
                id,
                title,
                body,
                version,
                created_at,
                published_date,
                trap_type,
                trap_set,
                tags,
                category,
                deprecation_note,
                ROW_NUMBER() OVER (ORDER BY embedding <=> %s::vector) AS rank
            FROM documents
            WHERE published_date >= NOW() - INTERVAL '{time_window}'
            ORDER BY embedding <=> %s::vector
            LIMIT 20
        ),
        text_search AS (
            SELECT
                id,
                title,
                body,
                version,
                created_at,
                published_date,
                trap_type,
                trap_set,
                tags,
                category,
                deprecation_note,
                ROW_NUMBER() OVER (ORDER BY ts_rank(search_vector, websearch_to_tsquery('english', %s)) DESC) AS rank
            FROM documents
            WHERE published_date >= NOW() - INTERVAL '{time_window}'
              AND search_vector @@ websearch_to_tsquery('english', %s)
            ORDER BY ts_rank(search_vector, websearch_to_tsquery('english', %s)) DESC
            LIMIT 20
        ),
        combined AS (
            SELECT
                COALESCE(v.id, t.id) AS id,
                COALESCE(v.title, t.title) AS title,
                COALESCE(v.body, t.body) AS body,
                COALESCE(v.version, t.version) AS version,
                COALESCE(v.created_at, t.created_at) AS created_at,
                COALESCE(v.published_date, t.published_date) AS published_date,
                COALESCE(v.trap_type, t.trap_type) AS trap_type,
                COALESCE(v.trap_set, t.trap_set) AS trap_set,
                COALESCE(v.tags, t.tags) AS tags,
                COALESCE(v.category, t.category) AS category,
                COALESCE(v.deprecation_note, t.deprecation_note) AS deprecation_note,
                COALESCE(1.0 / (60 + v.rank), 0.0) * %s +
                COALESCE(1.0 / (60 + t.rank), 0.0) * %s AS score
            FROM vector_search v
            FULL OUTER JOIN text_search t ON v.id = t.id
        )
        SELECT * FROM combined
        ORDER BY score DESC
        LIMIT %s;
    """

    # Measure execution time
    start_time = time.perf_counter()

    with psycopg.connect(conn_string, row_factory=dict_row) as conn:
        with conn.cursor() as cur:
            cur.execute(
                sql,
                (
                    embedding_str, embedding_str,  # vector_search CTE
                    query, query, query,           # text_search CTE
                    vector_weight, text_weight,    # RRF weights
                    limit
                )
            )
            results = cur.fetchall()

    elapsed_ms = (time.perf_counter() - start_time) * 1000

    return {
        'results': [dict(row) for row in results],
        'execution_time_ms': round(elapsed_ms, 2),
        'method': 'Hybrid + Temporal',
        'sql': sql  # Include SQL for display
    }


def get_document_by_id(doc_id: str, conn_string: str = None) -> Optional[Dict]:
    """
    Get a document by its ID.

    Args:
        doc_id: Document identifier
        conn_string: Database connection string

    Returns:
        Document dictionary or None if not found
    """
    query = """
        SELECT
            id,
            title,
            body,
            category,
            version,
            created_at,
            is_deprecated,
            deprecation_note,
            tags,
            trap_set,
            trap_type
        FROM documents
        WHERE id = %s
        LIMIT 1;
    """

    with psycopg.connect(conn_string, row_factory=dict_row) as conn:
        with conn.cursor() as cur:
            cur.execute(query, (doc_id,))
            result = cur.fetchone()

    return dict(result) if result else None


def get_all_trap_sets(conn_string: str = None) -> List[str]:
    """
    Get list of all trap set names in the database.

    Args:
        conn_string: Database connection string

    Returns:
        List of unique trap set names
    """
    query = """
        SELECT DISTINCT trap_set
        FROM documents
        WHERE trap_set IS NOT NULL
        ORDER BY trap_set;
    """

    with psycopg.connect(conn_string, row_factory=dict_row) as conn:
        with conn.cursor() as cur:
            cur.execute(query)
            results = cur.fetchall()

    return [row['trap_set'] for row in results]


def get_trap_quartet(trap_set: str, conn_string: str = None) -> Dict[str, Dict]:
    """
    Get all four documents in a trap quartet.

    Args:
        trap_set: Name of the trap set (e.g., "authentication")
        conn_string: Database connection string

    Returns:
        Dictionary mapping trap_type to document
    """
    query = """
        SELECT
            id,
            title,
            body,
            version,
            created_at,
            trap_type,
            trap_set
        FROM documents
        WHERE trap_set = %s
        ORDER BY trap_type;
    """

    with psycopg.connect(conn_string, row_factory=dict_row) as conn:
        with conn.cursor() as cur:
            cur.execute(query, (trap_set,))
            results = cur.fetchall()

    quartet = {}
    for row in results:
        trap_type = row['trap_type']
        quartet[trap_type] = dict(row)

    return quartet

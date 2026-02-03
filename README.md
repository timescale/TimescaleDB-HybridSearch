# Hybrid Search Demo with TimescaleDB

An interactive demonstration of hybrid search combining vector embeddings, full-text search, and temporal filtering using TimescaleDB.

## What This Demo Shows

This tutorial demonstrates four search methods using "trap quartets"; carefully crafted document sets that show when each method succeeds or fails:

1. **Vector Search** - Semantic similarity using `pgvectorscale` DiskANN
2. **Text Search** - Full-text search using PostgreSQL GIN indexes
3. **Hybrid Search** - Combines vector + text with Reciprocal Rank Fusion (RRF)
4. **Hybrid + Temporal** - Adds time-based filtering with TimescaleDB chunk exclusion

## Prerequisites

1. **uv package manager** - Fast Python package installer

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

2. **TimescaleDB database** - Either:

- **Tiger Cloud** (easiest): Create a free database at [console.cloud.timescale.com](https://console.cloud.timescale.com)
- **Kubernetes**: Deploy TimescaleDB with pgvector and pgvectorscale
- **Local PostgreSQL**: Install TimescaleDB extensions

## Setting Up the Demo

### Step 1: Configure Database Connection

```bash
# Copy example environment file
cp .env.example .env

# Edit .env and set DATABASE_URL
```

**For Tiger Cloud:**
```bash
DATABASE_URL=postgres://tsdbadmin:PASSWORD@HOST.tsdb.cloud.timescale.com:PORT/tsdb?sslmode=require
```

**For Kubernetes (with port-forward):**
```bash
# Terminal 1: Start port-forward
kubectl port-forward svc/timescaledb 5432:5432

# Terminal 2: Set DATABASE_URL
DATABASE_URL=postgresql://app:PASSWORD@localhost:5432/app
```

### Step 2: Run Setup Script

The setup script automatically:
- Creates Python virtual environment
- Installs all dependencies
- Detects database type (K8s vs Tiger Cloud)
- Restores database with 150 documents + embeddings
- Creates indexes and hypertable

```bash
./setup_demo.sh
```

### Step 3: Run Demo

```bash
./run_demo.sh
```

That's it! 🎉

## Understanding the Results

- **Vector Search**: Cosine similarity scores (0.0-1.0), higher is better
- **Text Search**: PostgreSQL ts_rank scores - values depend on document length and term frequency
- **Hybrid Search**: Reciprocal Rank Fusion (RRF) scores - typically small values (0.01-0.02), focus on relative ranking
- **Hybrid + Temporal**: Same as Hybrid but with time-window filtering

**Note:** For Hybrid methods, the absolute scores are typically very small (e.g., 0.016) because RRF combines rankings, not raw scores. What matters is the relative order - the top result is what you want, regardless of the numerical value.

### Status Indicators

- ✓ Green checkmark - Correct result (Winner)
- ✗ Red X - Incorrect result (Bait document)


## Technical Details

### Embeddings

- **Model**: Sentence Transformers `all-mpnet-base-v2`
- **Dimensions**: 768
- **Pre-computed**: Included in database backup (no API needed)

### Database

- **Documents**: 150 technical documentation entries
- **Demo Queries**: 5 trap quartets with embeddings
- **Backup Size**: ~0.75 MB compressed

## Troubleshooting

### "DATABASE_URL not configured"

Create `.env` file with your connection string:
```bash
cp .env.example .env
# Edit .env with your database URL
```

### "Connection refused" (K8s)

Ensure port-forward is running:
```bash
kubectl port-forward -n timescaledb svc/timescaledb-cluster-rw 5432:5432
```

### "Cannot connect to database" (Tiger Cloud)

1. Verify credentials in Tiger Cloud console
2. Check connection string format:

```bash
postgres://tsdbadmin:PASSWORD@HOST.tsdb.cloud.timescale.com:PORT/tsdb?sslmode=require
```

3. Ensure database is running (not paused)


## Learning Resources

### TimescaleDB
- [Hypertables Documentation](https://docs.timescale.com/use-timescale/latest/hypertables/)
- [Chunk Exclusion](https://docs.timescale.com/use-timescale/latest/hypertables/about-hypertables/#chunk-time-intervals)

### pgvector & pgvectorscale
- [pgvector GitHub](https://github.com/pgvector/pgvector)
- [pgvectorscale Documentation](https://github.com/timescale/pgvectorscale)
- [DiskANN Index](https://github.com/timescale/pgvectorscale#diskann-index)

### Hybrid Search
- [Reciprocal Rank Fusion (RRF)](https://plg.uwaterloo.ca/~gvcormac/cormacksigir09-rrf.pdf)
- [Hybrid Search Best Practices](https://www.timescale.com/blog/how-to-build-hybrid-search/)

## Next Steps

After completing this tutorial:

1. **Experiment** with different queries and time windows
2. **Analyze** trap quartet results to understand failure patterns
3. **Customize** with your own documentation corpus
4. **Deploy** hybrid search in your application

## Acknowledgments

Built with:
- [TimescaleDB](https://www.timescale.com/) - Time-series database
- [pgvector](https://github.com/pgvector/pgvector) - Vector similarity search
- [pgvectorscale](https://github.com/timescale/pgvectorscale) - DiskANN for pgvector
- [Sentence Transformers](https://www.sbert.net/) - Embedding generation
- [Rich](https://github.com/Textualize/rich) - Terminal UI library

---

**Happy searching! 🔍**
